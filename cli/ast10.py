#!/usr/bin/env python3
"""cli/ast10.py — discover, install, route, and report on this repo's AST skills.

Install method (c) in README.md. Deliberately dependency-light: PyYAML is the
only import beyond the standard library, because an installer that needs a
build step is an installer people skip.

Subcommands
    list      every shipped skill with its detection focus and F1 status
    install   copy skill packages into an agent runtime's skills directory
    route     triage a free-text finding to its primary AST category
    status    per-category coverage and F1 state, straight off the manifests

Every subcommand reads the repository's own artifacts (`skills/*/SKILL.md`,
`fixtures/manifest.yaml`, `scenarios/registry.yaml`). Nothing here restates a
number that lives somewhere else — a stale CLI that disagrees with the
manifests would be the AST04 shape this repo is about.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
FIXTURE_MANIFEST = REPO_ROOT / "fixtures" / "manifest.yaml"
REGISTRY = REPO_ROOT / "scenarios" / "registry.yaml"

#: Default install target for Claude Code. Overridable with ``--target``.
DEFAULT_TARGET = Path.home() / ".claude" / "skills"

#: The ten detector categories, in whitepaper order, plus the triage skill.
AST_IDS = tuple(f"AST{n:02d}" for n in range(1, 11))
ADVISORY_ID = "advisory"
ALL_IDS = AST_IDS + (ADVISORY_ID,)


class CliError(RuntimeError):
    """Any user-facing failure. Caught by main() and printed without a traceback."""


# --------------------------------------------------------------------------
# reading the repo's own artifacts
# --------------------------------------------------------------------------


def _split_frontmatter(text: str) -> dict[str, Any]:
    """Parse the YAML frontmatter block at the top of a SKILL.md."""
    if not text.startswith("---\n"):
        raise CliError("SKILL.md does not open with YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise CliError("SKILL.md frontmatter is not terminated by a closing ---")
    return yaml.safe_load(text[4:end]) or {}


def skill_dir(skill_id: str) -> Path:
    path = SKILLS_DIR / skill_id
    if not (path / "SKILL.md").is_file():
        raise CliError(f"unknown skill {skill_id!r}; choose one of {', '.join(ALL_IDS)}")
    return path


def read_skill(skill_id: str) -> dict[str, Any]:
    """One skill's identity as the package itself declares it."""
    path = skill_dir(skill_id)
    front = _split_frontmatter((path / "SKILL.md").read_text(encoding="utf-8"))
    name = front.get("name")
    if not name:
        raise CliError(f"{skill_id}/SKILL.md frontmatter has no `name`")
    return {
        "id": skill_id,
        "name": name,
        "description": (front.get("description") or "").strip(),
        "path": path,
    }


def _fixture_categories() -> dict[str, dict[str, Any]]:
    if not FIXTURE_MANIFEST.is_file():
        return {}
    data = yaml.safe_load(FIXTURE_MANIFEST.read_text(encoding="utf-8")) or {}
    return data.get("categories") or {}


def _registry_tiers() -> dict[str, dict[str, int]]:
    """Per-category scenario counts by tier, from the scenario registry."""
    if not REGISTRY.is_file():
        return {}
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}
    out: dict[str, dict[str, int]] = {}
    for scenario in data.get("scenarios") or []:
        bucket = out.setdefault(scenario["category"], {})
        bucket[scenario["tier"]] = bucket.get(scenario["tier"], 0) + 1
    return out


def f1_state(category: str) -> str:
    """How this category reports F1 today, in the manifest's own vocabulary.

    Three outcomes, never blended: a published number, ``pending-detector``
    (a labeled corpus exists and no detector consumes it), or
    ``declared-and-uncovered`` (the labeled detectable tier is empty, so the
    never-pad rule forbids manufacturing a number at all).
    """
    entry = _fixture_categories().get(category)
    if entry is None:
        return "not-in-manifest"
    published = entry.get("published_f1")
    if published in (None, "null"):
        return str(entry.get("status") or "declared-and-uncovered")
    if isinstance(published, (int, float)):
        # One category stores `published_f1` as a bare number with its scope in
        # the sibling `f1_scope` field. Printing it raw put an unlabelled `1.0`
        # next to nine labelled numbers, which is the one shape this repository
        # tells everyone else never to quote. Label it from its own siblings.
        scope = str(entry.get("f1_scope") or "").strip() or "unscoped"
        cases = (entry.get("registry_coverage") or {}).get("cases_present")
        suffix = f", n={cases}" if cases else ""
        return f"{scope} {float(published):.3f}{suffix and ' (' + suffix.lstrip(', ') + ')'}"
    return str(published)


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> int:
    rows = []
    for skill_id in ALL_IDS:
        info = read_skill(skill_id)
        rows.append(
            {
                "id": skill_id,
                "name": info["name"],
                "f1": f1_state(skill_id) if skill_id in AST_IDS else "not-scored-on-f1",
                "description": info["description"],
            }
        )
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    width = max(len(r["name"]) for r in rows)
    for row in rows:
        print(f"{row['id']:<9} {row['name']:<{width}}  {row['f1']}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    categories = _fixture_categories()
    tiers = _registry_tiers()
    rows = []
    for category in AST_IDS:
        entry = categories.get(category) or {}
        tier = tiers.get(category, {})
        rows.append(
            {
                "category": category,
                "status": entry.get("status", "unknown"),
                "f1": f1_state(category),
                "cases": len(entry.get("cases") or []),
                "labeled_detectable": len(entry.get("detectable_scenarios") or []),
                "registry_static_detectable": tier.get("static-detectable", 0),
                "registry_agent_judgable": tier.get("agent-judgable", 0),
                "registry_out_of_artifact": tier.get("out-of-artifact", 0),
            }
        )
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    header = f"{'CATEGORY':<9} {'STATUS':<24} {'F1':<24} {'CASES':>5} {'LABELED':>8} {'REGISTRY s/a/o':>15}"
    print(header)
    print("-" * len(header))
    for row in rows:
        registry = (
            f"{row['registry_static_detectable']}/{row['registry_agent_judgable']}/{row['registry_out_of_artifact']}"
        )
        print(
            f"{row['category']:<9} {row['status']:<24} {row['f1']:<24} "
            f"{row['cases']:>5} {row['labeled_detectable']:>8} {registry:>15}"
        )
    return 0


def cmd_route(args: argparse.Namespace) -> int:
    """Delegate to the advisory skill's own router — never a second copy of the tree."""
    triage_path = SKILLS_DIR / ADVISORY_ID / "scripts" / "triage.py"
    spec = importlib.util.spec_from_file_location("ast10_cli_triage", triage_path)
    if spec is None or spec.loader is None:  # pragma: no cover - unreachable on disk
        raise CliError(f"cannot load {triage_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    finding = " ".join(args.finding).strip()
    if not finding:
        raise CliError("route needs a finding to triage")
    print(json.dumps(module.triage(finding), indent=2))
    return 0


def resolve_ids(requested: list[str], want_all: bool) -> list[str]:
    if want_all:
        return list(ALL_IDS)
    if not requested:
        raise CliError("install needs --all or at least one --skill")
    resolved = []
    for raw in requested:
        candidate = raw.strip()
        upper = candidate.upper()
        if upper in AST_IDS:
            resolved.append(upper)
        elif candidate == ADVISORY_ID:
            resolved.append(ADVISORY_ID)
        else:
            # accept the frontmatter name too: `--skill ast03-over-privileged-skills`
            match = [i for i in ALL_IDS if read_skill(i)["name"] == candidate]
            if not match:
                raise CliError(f"unknown skill {raw!r}; choose one of {', '.join(ALL_IDS)}")
            resolved.append(match[0])
    return resolved


#: Never copied into a user's skills directory. Running the test suite leaves
#: `__pycache__/` and `.pytest_cache/` inside a skill package, and a plain
#: `copytree` would install that local build residue as part of the package. A
#: repository whose subject is *what is actually inside a skill you install*
#: cannot ship bytes nobody authored and nobody reviewed.
INSTALL_EXCLUDE = shutil.ignore_patterns(
    "__pycache__",
    "*.py[co]",
    ".pytest_cache",
    ".ruff_cache",
    ".DS_Store",
)


def cmd_install(args: argparse.Namespace) -> int:
    """Copy skill packages into an agent runtime's skills directory.

    The destination directory is named after the package's frontmatter `name`,
    not its `ASTnn` directory, because that is the identifier a runtime matches
    a skill invocation against.
    """
    target = Path(args.target).expanduser()
    ids = resolve_ids(args.skill, args.all)
    for skill_id in ids:
        info = read_skill(skill_id)
        dest = target / info["name"]
        if dest.exists() and not args.force:
            print(f"skip  {info['name']} (exists; pass --force to overwrite)")
            continue
        if args.dry_run:
            print(f"plan  {info['path'].relative_to(REPO_ROOT)} -> {dest}")
            continue
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(info["path"], dest, ignore=INSTALL_EXCLUDE)
        print(f"ok    {info['name']} -> {dest}")
    if args.dry_run:
        print(f"\n{len(ids)} skill(s) planned; nothing written (--dry-run).")
    return 0


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ast10",
        description=(
            "Discover, install, route and report on the OWASP Agentic Skills "
            "Top 10 detector skills. Independent implementation; not an "
            "official OWASP project."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="list every shipped skill")
    p_list.add_argument("--json", action="store_true", help="machine-readable output")
    p_list.set_defaults(func=cmd_list)

    p_status = sub.add_parser("status", help="per-category coverage and F1 state")
    p_status.add_argument("--json", action="store_true", help="machine-readable output")
    p_status.set_defaults(func=cmd_status)

    p_route = sub.add_parser("route", help="triage a free-text finding to an AST id")
    p_route.add_argument("finding", nargs="+", help="the finding text")
    p_route.set_defaults(func=cmd_route)

    p_install = sub.add_parser("install", help="copy skills into a skills directory")
    p_install.add_argument(
        "--target",
        default=str(DEFAULT_TARGET),
        help=f"destination skills directory (default: {DEFAULT_TARGET})",
    )
    p_install.add_argument(
        "--skill",
        action="append",
        default=[],
        metavar="ID",
        help="skill to install (ASTnn, advisory, or a frontmatter name); repeatable",
    )
    p_install.add_argument("--all", action="store_true", help="install all 11 skills")
    p_install.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    p_install.add_argument("--force", action="store_true", help="overwrite an existing destination")
    p_install.set_defaults(func=cmd_install)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
