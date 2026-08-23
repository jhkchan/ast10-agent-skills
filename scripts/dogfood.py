"""Run this repository's own detectors over this repository's own skills.

A skill-security repo that never points its detectors at itself is asserting a
capability it has not exercised. This module is the exercise: it loads every
`skills/<ID>/` package the way an installing agent would see it, hands each
package to *every* category detector this repo ships (not just its own), and
fails on any finding.

Two things make it non-trivial, and both are the point.

**1. USF v1 is not the detector package shape.** The detectors were authored
against a flatter internal package dict (`manifest.permissions.deny_write`,
`permissions.shell.allowed`, `permissions.network.policy`) while the shipped
manifests are Universal Skill Format v1.0 (`permissions.files.deny_write`,
`permissions.shell` as a bare boolean, `permissions.network.allow` as a
default-deny host list). Feeding a USF manifest to the detectors raw produces
eleven false positives on AST03 alone, because `permissions.get("deny_write")`
misses a key that is nested one level down. `translate_permissions()` below is
the explicit adapter, and translating security metadata between two
vocabularies that express the same intent differently is precisely the AST10
failure this repo is about — so the mapping is written down, tested, and
conservative: where USF cannot express a detector concept at all (there is no
USF spelling for "allow-all egress"), the translation says so rather than
guessing a permissive default.

**2. A finding is not automatically a bug.** `config/dogfood_waivers.yml`
carries per-(skill, scenario) waivers, each with a written reason and an
`evidence_contains` fragment that pins the waiver to the exact file it was
written for, so a waiver cannot silently absorb a different, real finding in
the same skill later. An unwaived finding fails. A waiver that matches nothing
also fails — a waiver file that can silently accumulate dead entries is the
AST09 "we have logs" problem in miniature, so stale waivers are as loud as new
findings.

CLI::

    python3 scripts/dogfood.py            # exit 1 on unwaived finding or stale waiver
    python3 scripts/dogfood.py --json     # machine-readable report
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

if str(REPO_ROOT) not in sys.path:  # pragma: no cover - import-path bootstrap
    sys.path.insert(0, str(REPO_ROOT))

from scripts.content_hash import SURFACE_GLOBS  # noqa: E402

SKILLS_DIR = REPO_ROOT / "skills"
WAIVERS_PATH = REPO_ROOT / "config" / "dogfood_waivers.yml"

MANIFEST_FILENAME = "skill.usf.yaml"
DETECTOR_RELPATH = Path("scripts") / "detector.py"


# --------------------------------------------------------------------------- errors


class DogfoodError(RuntimeError):
    """A dogfood run could not be completed as specified."""


# --------------------------------------------------------------------------- model


@dataclass(frozen=True)
class DogfoodFinding:
    """One detector firing on one skill package."""

    skill: str
    detector: str
    scenario: str
    evidence: str
    waived: bool = False
    waiver_reason: str = ""


@dataclass(frozen=True)
class DogfoodReport:
    findings: tuple[DogfoodFinding, ...]
    stale_waivers: tuple[str, ...]
    skills_scanned: tuple[str, ...]
    detectors_run: tuple[str, ...]

    @property
    def unwaived(self) -> tuple[DogfoodFinding, ...]:
        return tuple(f for f in self.findings if not f.waived)

    @property
    def ok(self) -> bool:
        return not self.unwaived and not self.stale_waivers


# ------------------------------------------------------------------ USF translation


def _network_policy(network: dict) -> str:
    """USF v1 egress declaration -> the detectors' `network.policy` string.

    USF v1 evaluates network access default-deny against an explicit host
    allowlist (`permissions.network.allow`); an empty list means no egress,
    never unrestricted egress. The detectors instead branch on a `policy`
    string. The mapping is therefore:

    * ``allow: []``           -> ``"deny-all"``
    * ``allow: [host, ...]``  -> ``"allow-list"`` (entries pass through, so a
      `"*"` or a bare-TLD wildcard still reaches AST05's wildcard check)

    There is deliberately no branch producing ``"allow-all"``: USF v1 has no
    spelling for it, and inventing one here would mean this translator, not
    the manifest, decided a package had unrestricted egress.
    """
    allow = network.get("allow") or []
    return "allow-list" if allow else "deny-all"


def translate_permissions(usf_permissions: dict | None) -> dict:
    """Translate a USF v1 `permissions` block into the detector package shape.

    Returns ``{}`` for an absent or empty block, so AST06's
    ``missing-sandbox-declaration`` still fires on a package that declares no
    isolation posture at all — the one case where "translate nothing" is the
    correct answer rather than a lookup miss.
    """
    if not usf_permissions:
        return {}

    files = usf_permissions.get("files") or {}
    network = usf_permissions.get("network") or {}
    shell = usf_permissions.get("shell")

    translated: dict = {
        "read": list(files.get("read") or []),
        "write": list(files.get("write") or []),
        "deny_write": list(files.get("deny_write") or []),
        # USF v1 `shell` is a bare boolean with no command allowlist to carry,
        # so `true` translates to shell-allowed-with-no-allowlist -- which is
        # what AST06's unrestricted-shell-exec check means. `false` must stay
        # a present-but-closed declaration, not an absent one.
        "shell": {"allowed": bool(shell), "commands": []},
        "network": {
            "policy": _network_policy(network),
            "allow": list(network.get("allow") or []),
        },
        "tools": list(usf_permissions.get("tools") or []),
    }
    return translated


def translate_content_hash(declared: object) -> dict | None:
    """``"sha256:<hex>"`` -> ``{"algorithm": "sha256", "value": "<hex>"}``.

    Returns ``None`` for an absent hash so AST01's ``content-hash-missing``
    fires, and for a malformed one so the gap is reported as missing rather
    than silently compared against a value no signer could have produced.
    """
    if not isinstance(declared, str) or ":" not in declared:
        return None
    algorithm, _, value = declared.partition(":")
    if not algorithm or not value:
        return None
    return {"algorithm": algorithm, "value": value}


def surface_files(skill_dir: Path) -> dict[str, str]:
    """The skill's shipped surface as ``{relative_path: text}``.

    Exactly ``scripts/content_hash.py``'s ``SURFACE_GLOBS`` — the same file set
    the manifest's ``content_hash`` covers — so AST01's re-derived digest is
    comparable to the declared one instead of hashing a different corpus.
    """
    out: dict[str, str] = {}
    for pattern in SURFACE_GLOBS:
        for path in sorted(skill_dir.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(skill_dir).as_posix()
            out[rel] = path.read_text(encoding="utf-8")
    return dict(sorted(out.items()))


def load_package(skill_dir: Path) -> dict:
    """Load one `skills/<ID>/` directory as a detector package dict."""
    manifest_path = skill_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise DogfoodError(f"{skill_dir.name}: no {MANIFEST_FILENAME} to dogfood")
    with manifest_path.open(encoding="utf-8") as fh:
        usf = yaml.safe_load(fh) or {}

    return {
        "name": usf.get("name", skill_dir.name),
        "manifest": {
            "description": usf.get("description", "") or "",
            "permissions": translate_permissions(usf.get("permissions")),
            "content_hash": translate_content_hash(usf.get("content_hash")),
            # Passed through untranslated: `risk_tier` means the same thing in USF
            # and to a detector, and AST04's risk-tier cross-check has nothing to
            # cross-reference without it. Withholding the field would have left
            # `AST04-risk-tier-spoofing` permanently inert against this repo's own
            # packages -- a check exempt from its own dogfood, which is the
            # "capability it has not exercised" failure this module exists to stop.
            "risk_tier": usf.get("risk_tier"),
        },
        "files": surface_files(skill_dir),
    }


# ------------------------------------------------------------------ detector loading


def _load_detector_module(skill_dir: Path) -> ModuleType | None:
    detector_path = skill_dir / DETECTOR_RELPATH
    if not detector_path.is_file():
        return None
    module_name = f"_dogfood_detector_{skill_dir.name}"
    spec = importlib.util.spec_from_file_location(module_name, detector_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise DogfoodError(f"{skill_dir.name}: cannot load {detector_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def skill_dirs(skills_root: Path = SKILLS_DIR) -> list[Path]:
    return sorted(p for p in skills_root.iterdir() if p.is_dir() and not p.name.startswith("."))


# ------------------------------------------------------------------------- waivers


WAIVER_REQUIRED_FIELDS = ("skill", "scenario", "evidence_contains", "reason")


def load_waivers(path: Path = WAIVERS_PATH) -> list[dict]:
    """Read the waiver file. A missing file means "no waivers", not an error.

    Every field in :data:`WAIVER_REQUIRED_FIELDS` is mandatory. ``reason`` is
    what makes the exception reviewable; ``evidence_contains`` is what keeps it
    narrow — without it, one waiver would silence every future finding of that
    scenario in that skill, which is how a suppression list becomes a blindfold.
    """
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    waivers = doc.get("waivers") or []
    for entry in waivers:
        missing = [k for k in WAIVER_REQUIRED_FIELDS if not entry.get(k)]
        if missing:
            raise DogfoodError(
                f"{path.name}: waiver {entry!r} is missing required field(s) "
                f"{missing}; a waiver without a written reason and a pinned "
                "evidence fragment is an undeclared exception"
            )
    return waivers


def _waiver_key(entry: dict) -> str:
    return f"{entry['skill']}::{entry['scenario']}"


def _waiver_matches(entry: dict, skill: str, scenario: str, evidence: str) -> bool:
    return entry["skill"] == skill and entry["scenario"] == scenario and entry["evidence_contains"] in evidence


# ----------------------------------------------------------------------------- run


def run(skills_root: Path = SKILLS_DIR, waivers_path: Path = WAIVERS_PATH) -> DogfoodReport:
    """Every detector this repo ships, over every skill package this repo ships."""
    dirs = skill_dirs(skills_root)
    packages = {d.name: load_package(d) for d in dirs}

    detectors: dict[str, ModuleType] = {}
    for d in dirs:
        module = _load_detector_module(d)
        if module is not None:
            detectors[d.name] = module

    waivers = load_waivers(waivers_path)
    matched_keys: set[str] = set()

    findings: list[DogfoodFinding] = []
    for skill_name in sorted(packages):
        pkg = packages[skill_name]
        for detector_name in sorted(detectors):
            for finding in detectors[detector_name].run_all(pkg):
                if not finding.detected:
                    continue
                waiver = next(
                    (w for w in waivers if _waiver_matches(w, skill_name, finding.scenario, finding.evidence)),
                    None,
                )
                if waiver is not None:
                    matched_keys.add(_waiver_key(waiver))
                findings.append(
                    DogfoodFinding(
                        skill=skill_name,
                        detector=detector_name,
                        scenario=finding.scenario,
                        evidence=finding.evidence,
                        waived=waiver is not None,
                        waiver_reason=(waiver or {}).get("reason", ""),
                    )
                )

    stale = tuple(sorted({_waiver_key(w) for w in waivers} - matched_keys))
    return DogfoodReport(
        findings=tuple(findings),
        stale_waivers=stale,
        skills_scanned=tuple(sorted(packages)),
        detectors_run=tuple(sorted(detectors)),
    )


def check_executions(skills_root: Path = SKILLS_DIR) -> int:
    """How many individual checks a full dogfood run actually executes.

    Every module's ``run_all`` returns one `Finding` per registered check, fired
    or not, so this is the honest denominator behind "N findings": without it,
    a report saying "9 findings" is unanchored — nine out of how many?
    """
    dirs = skill_dirs(skills_root)
    packages = [load_package(d) for d in dirs]
    modules = [m for m in (_load_detector_module(d) for d in dirs) if m is not None]
    return sum(len(module.run_all(pkg)) for module in modules for pkg in packages)


def scan_view_findings(skills_root: Path = SKILLS_DIR) -> set[tuple[str, str, str]]:
    """The same detectors over the WIDER file view the `audit` CLI uses.

    `load_package` above scans a skill's declared shipped surface (`SKILL.md`
    plus `scripts/*.py`). That is the correct view for the content-hash checks,
    which recompute a digest specified over exactly that set — but it means a
    dogfood run over the surface never reads `skill.usf.yaml` or
    `coverage-matrix.md` as *text*, only as a declaration. A metadata-injection
    or Unicode-smuggling check therefore never sees the manifest it is supposed
    to be able to scan.

    `cli/lib/bridge.py::audit` already builds both views and hands each category
    the one its checks are specified over. Running it here closes the gap and,
    more importantly, makes the claim falsifiable: if scanning the manifests
    ever finds something the surface run does not, the difference shows up as a
    row in `docs/dogfood-report.md` instead of as an unexamined assumption.

    Imported inside the function because `cli/lib/bridge.py` imports this module
    — it delegates USF translation here rather than carrying a second copy.
    """
    from cli.lib import bridge  # noqa: PLC0415 - deliberate, see docstring

    found: set[tuple[str, str, str]] = set()
    for skill_dir in skill_dirs(skills_root):
        for category in bridge.audit(str(skill_dir))["categories"]:
            for finding in category["findings"]:
                if finding["detected"]:
                    found.add((skill_dir.name, finding["scenario"], finding["evidence"]))
    return found


def report_to_dict(report: DogfoodReport) -> dict:
    return {
        "ok": report.ok,
        "skills_scanned": list(report.skills_scanned),
        "detectors_run": list(report.detectors_run),
        "stale_waivers": list(report.stale_waivers),
        "findings": [
            {
                "skill": f.skill,
                "detector": f.detector,
                "scenario": f.scenario,
                "evidence": f.evidence,
                "waived": f.waived,
                "waiver_reason": f.waiver_reason,
            }
            for f in report.findings
        ],
    }


MARKDOWN_PREAMBLE = """# Dogfood report — this repository's detectors over its own skills

Generated by `python3 scripts/dogfood.py --markdown`. Do not hand-edit: run the
generator.

A skill-security repository that never points its detectors at itself is
asserting a capability it has not exercised. This is the exercise. Every
detector module this repo ships is run over every skill package this repo ships
— not only its own category's — and every firing is listed below, waived or not.

**A detector firing on this repository's own skills is a real result, and none
of them is hidden.** Each waiver names the exact evidence fragment it covers and
carries a written reason, so it cannot silently absorb a different finding in the
same skill later; a waiver that stops matching anything fails the run just as
loudly as a new finding, because a suppression list that can accumulate dead
entries is the AST09 "we have logs" problem in miniature.
"""


def render_markdown(report: DogfoodReport, skills_root: Path = SKILLS_DIR) -> str:
    """The dogfood run as a document. Every finding, every waiver, every count."""
    executions = check_executions(skills_root)
    waived = [f for f in report.findings if f.waived]
    unwaived = list(report.unwaived)
    scan_only = sorted(scan_view_findings(skills_root) - {(f.skill, f.scenario, f.evidence) for f in report.findings})

    lines = [MARKDOWN_PREAMBLE.rstrip(), "", "## Run", ""]
    lines += [
        f"- **{len(report.detectors_run)} detector modules × {len(report.skills_scanned)} skill "
        f"packages = {executions} individual check executions.**",
        f"- Packages scanned: {', '.join(f'`{s}`' for s in report.skills_scanned)}.",
        f"- Detector modules run: {', '.join(f'`{d}`' for d in report.detectors_run)}.",
        f"- **{len(report.findings)} checks fired.** {len(waived)} waived, "
        f"**{len(unwaived)} unwaived**. Stale waivers: {len(report.stale_waivers)}.",
        f"- Verdict: **{'PASS' if report.ok else 'FAIL'}** — the run exits {0 if report.ok else 1}.",
        "",
    ]

    lines += ["## Findings", ""]
    if not report.findings:
        lines += ["No detector fired on any package.", ""]
    else:
        lines += ["| Skill | Check | Found by | Status | Evidence |", "| --- | --- | --- | --- | --- |"]
        for finding in report.findings:
            status = "waived" if finding.waived else "**UNWAIVED**"
            evidence = finding.evidence.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{finding.skill}` | `{finding.scenario}` | `{finding.detector}` | {status} | {evidence} |")
        lines.append("")

    if unwaived:
        lines += ["### Unwaived", ""]
        for finding in unwaived:
            lines += [f"**`{finding.skill}` — `{finding.scenario}`** (found by `{finding.detector}`)", ""]
            lines += [f"> {finding.evidence}", ""]

    if waived:
        lines += ["### Why each waived finding is waived", ""]
        for finding in waived:
            lines += [
                f"**`{finding.skill}` — `{finding.scenario}`** (found by `{finding.detector}`)",
                "",
                f"> {finding.evidence}",
                "",
                finding.waiver_reason,
                "",
            ]

    if report.stale_waivers:
        lines += ["### Stale waivers", ""]
        lines += [f"- `{key}`: nothing fires this scenario any more." for key in report.stale_waivers]
        lines.append("")

    lines += [
        "## Does scanning the manifests change anything?",
        "",
        "The run above scans each skill's **declared shipped surface** "
        "(`SKILL.md` plus `scripts/*.py`), which is the view the content-hash "
        "checks are specified over. `skill.usf.yaml` reaches those detectors as a "
        "parsed *declaration* rather than as scanned text, so this section re-runs "
        "the same detectors through `cli/lib/bridge.py::audit`, whose wider scan "
        "view additionally reads `skill.usf.yaml`, `coverage-matrix.md` and every "
        "other text file in the package.",
        "",
    ]
    if scan_only:
        lines += [
            f"**{len(scan_only)} finding(s) appear only when the manifests and prose are scanned as text:**",
            "",
        ]
        for skill, scenario, evidence in scan_only:
            lines.append(f"- `{skill}` — `{scenario}`: {evidence}")
        lines.append("")
    else:
        lines += [
            "**No.** The wider view finds exactly the same set — nothing hides in "
            "`skill.usf.yaml` or in a coverage matrix that the surface run misses.",
            "",
        ]

    lines += [
        "## What this run does not prove",
        "",
        "It proves these detectors do not convict this repository's own packages, "
        "and that the exceptions are written down. It does not prove the detectors "
        "are correct, that they generalise, or that they resist an author who has "
        "read them. The per-category F1 in [`f1-report.md`](f1-report.md) is "
        "measured over hand-authored fixtures and carries the same caveat.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scripts/dogfood.py",
        description="Run this repo's detectors over this repo's own skills.",
    )
    parser.add_argument("--json", action="store_true", help="emit a JSON report")
    parser.add_argument("--markdown", action="store_true", help="emit the report as markdown")
    parser.add_argument("--out", default=None, help="with --markdown, write to this path instead of stdout")
    parser.add_argument(
        "--check",
        action="store_true",
        help="with --markdown --out, exit 1 if the file is stale; write nothing",
    )
    args = parser.parse_args(argv)

    report = run()

    if args.markdown:
        text = render_markdown(report)
        if args.out is None:
            print(text, end="")
        elif args.check:
            path = Path(args.out)
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                print(f"{args.out}: out of date — run scripts/dogfood.py --markdown --out {args.out}")
                return 1
            print(f"{args.out}: up to date")
        else:
            Path(args.out).write_text(text, encoding="utf-8")
            print(f"{args.out}: written")
    elif args.json:
        print(json.dumps(report_to_dict(report), indent=2, sort_keys=True))
    else:
        print(
            f"dogfood: {len(report.detectors_run)} detector module(s) x {len(report.skills_scanned)} skill package(s)"
        )
        for finding in report.findings:
            mark = "WAIVED " if finding.waived else "FINDING"
            print(f"  {mark} {finding.skill} [{finding.scenario}] {finding.evidence}")
            if finding.waived:
                print(f"          reason: {finding.waiver_reason}")
        for key in report.stale_waivers:
            print(f"  STALE WAIVER {key}: nothing fires this scenario any more")
        if report.ok:
            print("dogfood: OK — no unwaived findings, no stale waivers")

    return 0 if report.ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
