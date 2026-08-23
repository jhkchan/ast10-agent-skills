"""Contract tests for the repository's published documentation.

Four things are asserted here, all of them promises this repository makes to a
reader who never opens a Python file:

1. `README.md` carries the non-endorsement disclaimer, in the words that make it
   unambiguous — a repo named `owasp-ast10-agent-skills` that does not say
   loudly that it is not an OWASP project is itself the AST04 shape (a
   brand-impersonating name with understated provenance).
2. `README.md` documents all three installation methods, each pointing at
   something that actually exists on disk.
3. `docs/skill-judge-dashboard.md` publishes all eight rubric dimensions summing
   to 120, with per-dimension floors matching `ship_floor.FLOORS`, and gives
   every unavailable provider in `config/audit.yml` a written reason.
4. No committed file names a sibling agent-skill repository. Those repos were
   install-pattern reference only; citing them here would misrepresent them as
   prior art this project builds on.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.ship_floor import FLOORS, MIN_ROUNDS, POOLED_LOWER_BOUND, POOLED_TARGET

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
DASHBOARD = REPO_ROOT / "docs" / "skill-judge-dashboard.md"
ARCHITECTURE = REPO_ROOT / "docs" / "architecture.md"
AUDIT = REPO_ROOT / "config" / "audit.yml"
FIXTURE_MANIFEST = REPO_ROOT / "fixtures" / "manifest.yaml"

AST_IDS = tuple(f"AST{n:02d}" for n in range(1, 11))


def _flat(path: Path) -> str:
    """File text with all runs of whitespace collapsed to single spaces.

    Lets an assertion match a sentence regardless of where the source file
    happened to wrap it, so reflowing a paragraph never breaks a test.
    """
    return " ".join(path.read_text(encoding="utf-8").split())


# ---------------------------------------------------------------------------
# 1. Non-endorsement disclaimer
# ---------------------------------------------------------------------------

#: Every clause the disclaimer must actually state. Kept as separate phrases
#: rather than one long quote so a rewording that preserves the meaning does
#: not fail, but a rewording that drops a claim does.
DISCLAIMER_CLAUSES = (
    "NOT an official OWASP project",
    "no OWASP endorsement",
    "despite the repository name",
    "independent",
    "Ken Huang",
    "project leader",
    "Reviewer/Contributor",
    "the whitepaper wins",
)


@pytest.mark.parametrize("clause", DISCLAIMER_CLAUSES)
def test_readme_carries_every_non_endorsement_clause(clause):
    assert clause in _flat(README), f"README.md must state {clause!r} in its non-endorsement disclaimer"


def test_readme_disclaimer_is_prominent():
    """The disclaimer must sit above the fold, not in a footer nobody reads."""
    lines = README.read_text(encoding="utf-8").splitlines()
    heading_indexes = [i for i, line in enumerate(lines) if "Not an OWASP project" in line]
    assert heading_indexes, "README.md needs a 'Not an OWASP project' section heading"
    assert heading_indexes[0] < 40, (
        "the non-endorsement heading must appear in the first 40 lines of README.md, "
        f"found at line {heading_indexes[0] + 1}"
    )


def test_readme_never_claims_authorship_of_the_publication():
    """Guard the exact overclaim the attribution decision forbids."""
    flat = _flat(README).lower()
    for overclaim in (
        "official owasp project",
        "owasp-endorsed",
        "authored the owasp agentic skills top 10",
        "leads the owasp agentic skills top 10",
    ):
        if overclaim == "official owasp project":
            # Legal in the negated form only.
            assert "not an official owasp project" in flat
            continue
        assert overclaim not in flat, f"README.md must not claim: {overclaim!r}"


# ---------------------------------------------------------------------------
# 2. Three installation methods
# ---------------------------------------------------------------------------

#: (heading fragment, a token proving the method points at something real)
INSTALL_METHODS = (
    ("Method 1", "~/.claude/skills"),
    ("Method 2", ".claude-plugin/marketplace.json"),
    ("Method 3", "cli/ast10.py"),
)


@pytest.mark.parametrize("heading,token", INSTALL_METHODS)
def test_readme_documents_three_install_methods(heading, token):
    flat = _flat(README)
    assert f"### {heading}" in flat, f"README.md is missing install {heading}"
    assert token in flat, f"install {heading} must reference {token!r}"


def test_install_methods_point_at_paths_that_exist():
    assert (REPO_ROOT / ".claude-plugin" / "marketplace.json").is_file()
    assert (REPO_ROOT / "cli" / "ast10.py").is_file()
    for skill_id in AST_IDS + ("advisory",):
        assert (REPO_ROOT / "skills" / skill_id / "SKILL.md").is_file()


def test_readme_install_section_lists_exactly_three_methods():
    headings = re.findall(r"^### Method \d+", README.read_text(encoding="utf-8"), re.M)
    assert len(headings) == 3, f"expected exactly three install methods, got {headings}"


# ---------------------------------------------------------------------------
# 3. The dashboard: rubric, ship rule, provider roster
# ---------------------------------------------------------------------------

RUBRIC_ROW_RE = re.compile(r"^\|\s*\*\*(D[1-8])\*\*[^|]*\|\s*(\d+)\s*\|\s*(\d+)\s*\|", re.M)


def _rubric_rows() -> dict[str, tuple[int, int]]:
    text = DASHBOARD.read_text(encoding="utf-8")
    return {m[0]: (int(m[1]), int(m[2])) for m in RUBRIC_ROW_RE.findall(text)}


def test_dashboard_lists_all_eight_rubric_dimensions():
    rows = _rubric_rows()
    assert sorted(rows) == [f"D{n}" for n in range(1, 9)], (
        f"dashboard must table all eight dimensions D1-D8, found {sorted(rows)}"
    )


def test_dashboard_rubric_dimensions_sum_to_120():
    total = sum(maximum for maximum, _floor in _rubric_rows().values())
    assert total == 120, f"the eight dimension maxima must sum to 120, got {total}"


def test_dashboard_rubric_maxima_match_the_published_weights():
    expected = {
        "D1": 20,
        "D2": 15,
        "D3": 15,
        "D4": 15,
        "D5": 15,
        "D6": 15,
        "D7": 10,
        "D8": 15,
    }
    assert {d: m for d, (m, _f) in _rubric_rows().items()} == expected


def test_dashboard_floors_match_the_shipped_gate():
    """A floor printed in the docs that the gate does not enforce is a lie."""
    assert {d: f for d, (_m, f) in _rubric_rows().items()} == FLOORS


@pytest.mark.parametrize(
    "fragment",
    [
        f"≥ **{POOLED_TARGET}**",
        f"≥ **{POOLED_LOWER_BOUND}**",
        f"≥ **{MIN_ROUNDS}**",
        "multi-round-independent-pooled",
    ],
)
def test_dashboard_publishes_the_ship_rule_constants(fragment):
    assert fragment in _flat(DASHBOARD), f"the ship rule table must publish {fragment!r} from scripts/ship_floor.py"


@pytest.mark.parametrize("grade,band", [("A", "108"), ("B", "96"), ("C", "84"), ("D", "72")])
def test_dashboard_publishes_the_grade_bands(grade, band):
    flat = _flat(DASHBOARD)
    assert f"**{grade}**" in flat and band in flat


def test_dashboard_declares_no_judged_run_yet():
    """Until eval/scorecards/ has a scorecard, the empty state must be explicit."""
    scorecards = sorted((REPO_ROOT / "eval" / "scorecards").glob("*.json"))
    if scorecards:
        pytest.skip(f"{len(scorecards)} scorecard(s) recorded; empty-state check n/a")
    flat = _flat(DASHBOARD)
    assert "No judged run recorded yet" in flat
    assert "NOT YET JUDGED" in flat


def _unavailable_providers() -> dict[str, dict]:
    data = yaml.safe_load(AUDIT.read_text(encoding="utf-8")) or {}
    return {
        name: entry for name, entry in (data.get("providers") or {}).items() if entry.get("status") == "unavailable"
    }


def test_audit_declares_at_least_one_unavailable_provider():
    """Guards the test below from passing vacuously on an empty roster."""
    assert _unavailable_providers(), "config/audit.yml must declare the providers this environment cannot reach"


@pytest.mark.parametrize("provider", sorted(_unavailable_providers()))
def test_dashboard_gives_every_unavailable_provider_a_reason(provider):
    """spec.md S-004: declared with a recorded reason, never silently dropped."""
    rows = [line for line in DASHBOARD.read_text(encoding="utf-8").splitlines() if line.startswith(f"| `{provider}` |")]
    assert len(rows) == 1, (
        f"expected exactly one dashboard row for unavailable provider {provider!r}, found {len(rows)}"
    )
    cells = [c.strip() for c in rows[0].strip().strip("|").split("|")]
    assert len(cells) == 4, f"row for {provider!r} must be Provider|Adapter|Model|Reason"
    reason = cells[-1]
    assert len(reason) >= 30, f"reason for {provider!r} is too thin to be a reason: {reason!r}"


def test_audit_reasons_are_non_empty_at_the_source():
    for provider, entry in _unavailable_providers().items():
        assert (entry.get("reason") or "").strip(), (
            f"config/audit.yml: {provider} is unavailable with no recorded reason"
        )


# ---------------------------------------------------------------------------
# README skills table must agree with the manifests
# ---------------------------------------------------------------------------


def _manifest_f1_state(category: str) -> str:
    data = yaml.safe_load(FIXTURE_MANIFEST.read_text(encoding="utf-8")) or {}
    entry = (data.get("categories") or {}).get(category) or {}
    published = entry.get("published_f1")
    if published in (None, "null"):
        return str(entry.get("status") or "declared-and-uncovered")
    return str(published)


@pytest.mark.parametrize("category", AST_IDS)
def test_readme_skills_table_matches_the_fixture_manifest(category):
    """A README that drifts from the manifests is worse than no README."""
    rows = [line for line in README.read_text(encoding="utf-8").splitlines() if line.startswith(f"| {category} |")]
    assert len(rows) == 1, f"README skills table needs exactly one {category} row"
    state = _manifest_f1_state(category)
    assert f"`{state}`" in rows[0], f"README says something other than {state!r} for {category}: {rows[0]}"


def test_readme_skills_table_covers_every_skill():
    text = README.read_text(encoding="utf-8")
    for category in AST_IDS:
        assert f"| {category} |" in text
    assert "`advisory`" in text


# ---------------------------------------------------------------------------
# docs/architecture.md
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "component",
    [
        "SKILL.md",
        "scripts/detector.py",
        "coverage-matrix.md",
        "skill.usf.yaml",
        "fixtures/manifest.yaml",
        "scenarios/registry.yaml",
        "scripts/ship_floor.py",
        "judge matrix",
    ],
)
def test_architecture_explains_every_moving_part(component):
    assert component in _flat(ARCHITECTURE), f"docs/architecture.md must explain how {component} fits in"


def test_architecture_carries_the_non_endorsement_note():
    flat = _flat(ARCHITECTURE)
    assert "not** an official OWASP project" in flat or "NOT an official OWASP project" in flat


def test_architecture_publishes_the_authority_chain():
    flat = _flat(ARCHITECTURE)
    assert "Authority chain" in flat
    for tier in ("static-detectable", "agent-judgable", "out-of-artifact"):
        assert tier in flat


# ---------------------------------------------------------------------------
# 4. No committed file names a sibling agent-skill repository
# ---------------------------------------------------------------------------

# Assembled from fragments on purpose: spelling these out as literals would make
# THIS file the counter-example its own assertion is hunting for.
_SUFFIX = "-agent-skills"
FORBIDDEN_NAMES = (
    "magic" + _SUFFIX,
    "aws" + _SUFFIX,
    "programming" + _SUFFIX,
    "sales" + _SUFFIX,
    "startup" + _SUFFIX,
    "magic" + "-linguistic",
    "magic" + "-model",
)

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".omc",
    ".venv",
    "node_modules",
}


def _committed_files() -> list[Path]:
    """Everything git would include in a commit: tracked plus unignored-untracked.

    Falls back to a filesystem walk when git is unavailable, which is stricter
    (it also sees ignored-but-present files) and therefore safe.
    """
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
            text=True,
            timeout=30,
        ).stdout
        paths = [REPO_ROOT / name for name in out.split("\0") if name]
        if paths:
            return [p for p in paths if p.is_file()]
    except (OSError, subprocess.SubprocessError):
        pass
    return [p for p in REPO_ROOT.rglob("*") if p.is_file() and not SKIP_DIRS & set(p.relative_to(REPO_ROOT).parts)]


def test_committed_file_listing_is_not_empty():
    """Guards the scan below from passing because it found nothing to scan."""
    files = _committed_files()
    assert len(files) > 50, f"expected the repo tree, found {len(files)} file(s)"
    assert README in files


def test_no_committed_file_names_a_sibling_repo():
    hits: list[str] = []
    for path in _committed_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: cannot carry a prose citation
        lowered = text.lower()
        for name in FORBIDDEN_NAMES:
            if name in lowered:
                rel = path.relative_to(REPO_ROOT)
                line = next(
                    (i for i, raw in enumerate(text.splitlines(), 1) if name in raw.lower()),
                    0,
                )
                hits.append(f"{rel}:{line} mentions {name!r}")
    assert not hits, (
        "sibling agent-skill repositories are install-pattern reference only and must "
        "never be cited as prior art in a committed file:\n  " + "\n  ".join(hits)
    )
