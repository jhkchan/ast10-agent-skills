#!/usr/bin/env python3
"""cli/lib/bridge.py -- the Python half of the `ast10-skills` CLI.

`cli/bin/cli.js` is a zero-dependency Node program. It reads *data* directly
(SKILL.md frontmatter, the scenario registry's tier lines, the fixture
manifest's per-category counters) but it never re-implements a *decision*
this repository already owns in Python. Those two decisions are:

    route  ->  skills/advisory/scripts/triage.py
               the whitepaper's own "Which AST Does My Finding Belong To?"
               decision tree, including its branch-5 primary-vs-contributing
               rule.
    audit  ->  skills/AST01..AST10/scripts/detector.py
               the per-category deterministic detectors.

This module loads those modules, runs them, and prints one JSON object on
stdout. Node parses it and formats the human-readable output. Duplicating
either decision in JavaScript would create a second source of truth for a
rule the repo deliberately keeps in one place.

Usage:
    python3 cli/lib/bridge.py route "<free-text finding>"
    python3 cli/lib/bridge.py audit <path-to-candidate-skill-package>

This repository is an independent community reference implementation. It is
NOT an official OWASP project and carries no OWASP endorsement (see NOTICE).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    # The skill detector modules import `detectors.scaffold` from the repo
    # root; the bridge may be invoked from any working directory.
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402  (after the sys.path fix-up, deliberately)

from scripts import dogfood  # noqa: E402

CATEGORIES: tuple[str, ...] = tuple(f"AST{n:02d}" for n in range(1, 11))

# Categories whose detectors are defined over the package's DECLARED SHIPPED
# SURFACE rather than over every file present. Today that is AST01 alone: its
# two checks re-derive `scripts/content_hash.py`'s digest, which is specified
# over SURFACE_GLOBS. Feeding those checks every file in the directory would
# report a content-hash mismatch for every well-formed package -- a false
# positive manufactured by the harness, not by the package.
SURFACE_SCOPED: frozenset[str] = frozenset({"AST01"})

# Files the scan view reads. Detectors scan text; anything else is recorded as
# skipped rather than silently decoded.
TEXT_SUFFIXES: frozenset[str] = frozenset(
    {
        ".md",
        ".py",
        ".json",
        ".toml",
        ".yaml",
        ".yml",
        ".txt",
        ".cfg",
        ".ini",
        ".sh",
        ".bash",
        ".zsh",
        ".js",
        ".mjs",
        ".ts",
        ".lock",
        ".env",
    }
)
SKIPPED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".tox",
    }
)
MAX_FILE_BYTES = 512 * 1024


class BridgeError(RuntimeError):
    """A condition the CLI must report to the operator, not swallow."""


# ---------------------------------------------------------------------------
# Module loading -- by path, because skills/ is not an importable package
# ---------------------------------------------------------------------------


def _load_module(path: Path, module_name: str) -> types.ModuleType:
    if not path.is_file():
        raise BridgeError(f"expected module not found: {path}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise BridgeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_triage() -> types.ModuleType:
    return _load_module(ROOT / "skills" / "advisory" / "scripts" / "triage.py", "ast_advisory_triage")


def load_detector(category: str) -> types.ModuleType:
    return _load_module(
        ROOT / "skills" / category / "scripts" / "detector.py",
        f"ast_{category.lower()}_detector",
    )


# ---------------------------------------------------------------------------
# USF -> detector-package shape adapter
# ---------------------------------------------------------------------------
#
# `schemas/usf-v1.schema.json` and the detector modules describe the same
# package from two angles and do not share field names. The USF semantics of
# that translation -- an empty `network.allow` is no egress rather than
# unrestricted egress, `shell: true` is shell-allowed-with-no-command-
# allowlist, a malformed `content_hash` reads as missing rather than as a
# mismatch -- are owned by `scripts/dogfood.py` (`translate_permissions`,
# `translate_content_hash`, `surface_files`), which points these same
# detectors at this repo's own skills. Translating security metadata between
# two vocabularies is the AST10 failure this repo is about, so there is
# exactly ONE such translator and the CLI calls it rather than carrying a
# second copy that could drift.
#
# What this module adds on top, because a candidate under audit is not one of
# this repo's own well-formed packages:
#
#   * a manifest source other than `skill.usf.yaml` (SKILL.md frontmatter, or
#     nothing at all);
#   * a manifest that is already detector-shaped, passed through untranslated
#     instead of being flattened into the wrong keys;
#   * bare-boolean `network:`/`shell:` frontmatter, which USF cannot express
#     and dogfood's translator is not built to receive;
#   * `notes` -- the audit trail of every translation step and every absent
#     field, which the CLI prints so a finding can always be traced back to a
#     declared field rather than to an adapter guess.


def _already_detector_shaped(permissions: dict) -> bool:
    """A permissions block written in the detectors' own vocabulary.

    USF nests file scopes under `files:` and spells `shell` as a boolean, so
    a top-level `deny_write`, a mapping-valued `shell`, or a `network.policy`
    means the author already wrote the detector shape. Running the USF
    translator over it would drop `deny_write` on the floor (it looks for
    `files.deny_write`) and read a populated `shell` mapping as `True`.
    """
    if "deny_write" in permissions:
        return True
    if isinstance(permissions.get("shell"), dict):
        return True
    network = permissions.get("network")
    return isinstance(network, dict) and "policy" in network


def _normalize_bare_booleans(permissions: dict, notes: list[str]) -> dict:
    """Frontmatter shorthand (`network: false`, `write: false`) -> USF shape.

    Nothing in USF v1 spells a permission as a bare boolean, but SKILL.md
    frontmatter in the wild does. A bare `network: true` is an author
    declaring unrestricted egress, and it is translated as such -- stated
    here, in the notes, rather than silently.
    """
    normalized = dict(permissions)
    network = normalized.get("network")
    if isinstance(network, bool):
        normalized["network"] = {"allow": ["*"]} if network else {"allow": []}
        notes.append(
            f"permissions.network={network!r} is a bare boolean, which USF v1 "
            "cannot express; read as "
            f"{'unrestricted egress' if network else 'no egress'}"
        )
    return normalized


def adapt_manifest(raw: dict | None) -> tuple[dict, list[str]]:
    """Translate a candidate's manifest into the detector package shape.

    Returns (manifest, notes). The USF translation itself is delegated to
    `scripts/dogfood.py`; `notes` records what was translated and what was
    absent, so no finding rests on an unexplained adapter step.
    """
    notes: list[str] = []
    if not raw:
        notes.append("no manifest found -- detectors see an empty declaration")
        return {}, notes

    manifest: dict = {}
    permissions_raw = raw.get("permissions")
    if isinstance(permissions_raw, dict) and permissions_raw:
        if _already_detector_shaped(permissions_raw):
            manifest["permissions"] = dict(permissions_raw)
            notes.append(
                "permissions are already in the detector shape "
                "(top-level deny_write / shell mapping / network.policy) -- "
                "passed through untranslated"
            )
        else:
            normalized = _normalize_bare_booleans(permissions_raw, notes)
            translated = dogfood.translate_permissions(normalized)
            if translated:
                manifest["permissions"] = translated
                notes.append(
                    "permissions.files.deny_write -> permissions.deny_write "
                    f"({len(translated.get('deny_write') or [])} path(s))"
                )
                notes.append(
                    "permissions.shell -> shell.allowed="
                    f"{translated['shell']['allowed']} with no command "
                    "allow-list (USF declares no command scoping)"
                )
                notes.append(
                    "permissions.network.allow="
                    f"{translated['network']['allow']!r} -> network.policy="
                    f"{translated['network']['policy']} "
                    "(USF evaluates default-deny; an empty allowlist is no egress)"
                )
    elif permissions_raw is None:
        notes.append("permissions block absent -- no isolation posture declared")
    else:
        notes.append(f"permissions is {type(permissions_raw).__name__}, not a map -- ignored")

    if raw.get("description") is not None:
        manifest["description"] = str(raw["description"])

    declared_hash = raw.get("content_hash")
    if isinstance(declared_hash, dict):
        manifest["content_hash"] = dict(declared_hash)
        notes.append("content_hash is already detector-shaped -- passed through")
    else:
        content_hash = dogfood.translate_content_hash(declared_hash)
        if content_hash is None:
            notes.append(
                "content_hash absent or malformed -- reported as missing rather "
                "than compared against a value no signer could have produced"
            )
        else:
            manifest["content_hash"] = content_hash
            notes.append(f"content_hash '{declared_hash}' -> algorithm={content_hash['algorithm']} value=<hex>")

    for passthrough in ("name", "version", "risk_tier", "signature", "platforms"):
        if passthrough in raw:
            manifest[passthrough] = raw[passthrough]
    return manifest, notes


# ---------------------------------------------------------------------------
# Candidate package loading
# ---------------------------------------------------------------------------


def parse_frontmatter(text: str) -> dict | None:
    """YAML frontmatter of a SKILL.md, parsed with safe_load only.

    Never `yaml.load`: AST04's own decision rule is that the loader choice is
    the finding, and a tool that unsafe-loads a candidate under audit executes
    the injection it exists to report.
    """
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    block = text[text.find("\n", 3) + 1 : end + 1]
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def read_manifest(pkg_dir: Path) -> tuple[dict | None, str]:
    """The candidate's manifest and where it came from.

    A `skill.usf.yaml` wins over SKILL.md frontmatter: it is the declaration
    the USF schema and validators/usf.py govern.
    """
    usf = pkg_dir / "skill.usf.yaml"
    if usf.is_file():
        try:
            data = yaml.safe_load(usf.read_text(encoding="utf-8"))
        except (yaml.YAMLError, UnicodeDecodeError) as exc:
            raise BridgeError(f"{usf}: unparseable USF manifest: {exc}") from exc
        if isinstance(data, dict):
            return data, "skill.usf.yaml"
    skill_md = pkg_dir / "SKILL.md"
    if skill_md.is_file():
        frontmatter = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        if frontmatter is not None:
            return frontmatter, "SKILL.md frontmatter"
        return None, "SKILL.md (no parseable frontmatter)"
    return None, "none"


def read_scan_files(pkg_dir: Path) -> tuple[dict[str, str], list[str]]:
    """Every text file in the package, keyed by relative posix path.

    This is the view the scanning detectors (AST04's yaml/json/toml checks,
    the invisible-Unicode scans) operate on: a candidate's `package.json` or
    `pyproject.toml` is exactly where those findings live, and neither is part
    of the declared shipped surface.
    """
    files: dict[str, str] = {}
    skipped: list[str] = []
    for path in sorted(pkg_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(pkg_dir).as_posix()
        if any(part in SKIPPED_DIRS for part in path.relative_to(pkg_dir).parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            skipped.append(f"{rel} (non-text suffix)")
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            skipped.append(f"{rel} (> {MAX_FILE_BYTES} bytes)")
            continue
        try:
            files[rel] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skipped.append(f"{rel} (not valid UTF-8)")
    return files, skipped


def read_surface_files(pkg_dir: Path) -> dict[str, str]:
    """The declared shipped surface -- `scripts/content_hash.py`'s
    SURFACE_GLOBS, read through `scripts/dogfood.py` so the CLI hashes exactly
    the file set the manifest's `content_hash` covers and never reports a
    spurious mismatch."""
    return dogfood.surface_files(pkg_dir)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def audit(target: str) -> dict:
    """Run every AST category's detectors over one candidate skill package."""
    pkg_dir = Path(target).expanduser()
    if pkg_dir.is_file():
        pkg_dir = pkg_dir.parent
    if not pkg_dir.is_dir():
        raise BridgeError(f"no such skill package: {target}")

    raw_manifest, manifest_source = read_manifest(pkg_dir)
    manifest, adapter_notes = adapt_manifest(raw_manifest)
    scan_files, skipped = read_scan_files(pkg_dir)
    surface_files = read_surface_files(pkg_dir)

    scan_pkg = {"manifest": manifest, "files": scan_files}
    surface_pkg = {"manifest": manifest, "files": surface_files}

    categories: list[dict] = []
    checks_run = 0
    detected_total = 0
    for category in CATEGORIES:
        module = load_detector(category)
        tiers: dict[str, str] = dict(getattr(module, "SCENARIO_TIERS", {}))
        agent_judgable = sorted(s for s, t in tiers.items() if t == "agent-judgable")
        out_of_artifact = sorted(s for s, t in tiers.items() if t == "out-of-artifact")
        detectors = getattr(module, "DETECTORS", {})
        if not detectors:
            categories.append(
                {
                    "category": category,
                    "status": "no-static-detectors",
                    "scope": None,
                    "findings": [],
                    "agent_judgable": agent_judgable,
                    "out_of_artifact": out_of_artifact,
                }
            )
            continue
        surface_scoped = category in SURFACE_SCOPED
        findings = [
            {
                "scenario": f.scenario,
                "tier": tiers.get(f.scenario),
                "detected": bool(f.detected),
                "evidence": f.evidence,
            }
            for f in module.run_all(surface_pkg if surface_scoped else scan_pkg)
        ]
        checks_run += len(findings)
        detected_total += sum(1 for f in findings if f["detected"])
        categories.append(
            {
                "category": category,
                "status": "ran",
                "scope": "declared-surface" if surface_scoped else "all-files",
                "findings": findings,
                "agent_judgable": agent_judgable,
                "out_of_artifact": out_of_artifact,
            }
        )

    return {
        "command": "audit",
        "path": str(pkg_dir),
        "manifest_source": manifest_source,
        "adapter_notes": adapter_notes,
        "scan_files": sorted(scan_files),
        "surface_files": sorted(surface_files),
        "skipped_files": skipped,
        "categories": categories,
        "totals": {
            "categories": len(CATEGORIES),
            "categories_without_detectors": sum(1 for c in categories if c["status"] == "no-static-detectors"),
            "checks_run": checks_run,
            "detected": detected_total,
        },
    }


def route(finding: str) -> dict:
    """Route a free-text finding through the whitepaper's decision tree."""
    if not finding.strip():
        raise BridgeError("route needs a non-empty finding")
    triage_module = load_triage()
    result = triage_module.triage(finding)
    matches = triage_module.matched_rules(finding)
    return {
        "command": "route",
        "finding": finding,
        "ast_id": result["ast_id"],
        "category": result["category"],
        "matched_phrase": result.get("matched_phrase"),
        "branch": result.get("branch"),
        "reasoning": result["reasoning"],
        "guidance": result["guidance"],
        "contributing": result["contributing"],
        "matches": matches,
        "total_rules": int(getattr(triage_module, "RULE_COUNT", len(matches))),
        "f1_eligible": bool(getattr(triage_module, "F1_ELIGIBLE", False)),
        "source": "skills/advisory/scripts/triage.py",
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(json.dumps({"error": "usage: bridge.py {route|audit} <arg>"}))
        return 2
    command, args = argv[1], argv[2:]
    try:
        if command == "route":
            payload = route(" ".join(args))
        elif command == "audit":
            if not args:
                raise BridgeError("audit needs a path")
            payload = audit(args[0])
        else:
            raise BridgeError(f"unknown bridge command: {command}")
    except BridgeError as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(payload, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
