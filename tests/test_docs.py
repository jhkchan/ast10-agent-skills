"""Contract tests for the repository's published documentation.

Four things are asserted here, all of them promises this repository makes to a
reader who never opens a Python file:

1. `README.md` carries the non-endorsement disclaimer, in the words that make it
   unambiguous — a repo named `ast10-agent-skills` that does not say
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
5. Every path, CLI subcommand, slash command and pytest node id these documents
   name **exists**, and every count and detector state they publish is derived
   from the manifests rather than typed by hand. This is the class of finding an
   independent review called the orphan-reference failure: a doc that points at
   something the repo does not have costs more than no doc, because it is the
   half a reader checks. Prose alone cannot hold that line — a paragraph reflowed
   six months from now silently outlives the file it describes — so each claim
   below is re-derived at test time from the artifact it describes.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import statistics
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.ship_floor import (
    AGG_METHOD,
    CONFIDENCE_K,
    FLOORS,
    MIN_ROUNDS,
    POOLED_LOWER_BOUND,
    POOLED_TARGET,
    RUBRIC_SHA,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
DASHBOARD = REPO_ROOT / "docs" / "skill-judge-dashboard.md"
ARCHITECTURE = REPO_ROOT / "docs" / "architecture.md"
#: Pages the README's long-form detail moved to. The guards follow the content;
#: they are not relaxed because it left the front page.
DETECTORS = REPO_ROOT / "docs" / "detectors.md"
LIMITS = REPO_ROOT / "docs" / "limits.md"
READING = REPO_ROOT / "docs" / "reading-the-results.md"
DEVELOPMENT = REPO_ROOT / "docs" / "development.md"
SIGNING = REPO_ROOT / "docs" / "signing.md"
F1_REPORT = REPO_ROOT / "docs" / "f1-report.md"
DOGFOOD_REPORT = REPO_ROOT / "docs" / "dogfood-report.md"
SKILL_EVAL_REPORT = REPO_ROOT / "docs" / "skill-eval-report.md"
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
#: The three documented install paths, each pinned by the token that proves the
#: page actually documents it. The plugin path is the only one that delivers the
#: slash commands, which is why it is named first and asserted first.
INSTALL_METHODS = (
    ("As a Claude Code plugin — recommended", "claude plugin marketplace add"),
    ("From npm — no clone", "npx ast10-agent-skills"),
    ("Copy the skills only", "~/.claude/skills"),
    ("From a clone — the full repository", "cli/ast10.py"),
)


@pytest.mark.parametrize("heading,token", INSTALL_METHODS)
def test_readme_documents_three_install_methods(heading, token):
    flat = _flat(README)
    assert f"### {heading}" in flat, f"README.md is missing install path {heading!r}"
    assert token in flat, f"install path {heading!r} must reference {token!r}"


def test_install_methods_point_at_paths_that_exist():
    assert (REPO_ROOT / ".claude-plugin" / "marketplace.json").is_file()
    assert (REPO_ROOT / "cli" / "ast10.py").is_file()
    for skill_id in AST_IDS + ("advisory",):
        assert (REPO_ROOT / "skills" / skill_id / "SKILL.md").is_file()


def test_readme_install_section_lists_every_documented_method():
    """The plugin path is first because it is the only one that also installs
    the commands; npm is second because it is the shortest route to running
    anything at all. The count is derived from INSTALL_METHODS so adding a path
    means declaring it there too, with the token that proves it is documented."""
    body = README.read_text(encoding="utf-8")
    install = body[body.index("\n## Install") : body.index("\n## Usage")]
    headings = re.findall(r"^### (.+)$", install, re.M)
    assert len(headings) == len(INSTALL_METHODS), (
        f"README documents {len(headings)} install paths, INSTALL_METHODS declares "
        f"{len(INSTALL_METHODS)}: {headings}"
    )
    assert "plugin" in headings[0].lower(), f"the plugin path must be listed first, got {headings[0]!r}"
    assert headings == [h for h, _ in INSTALL_METHODS], (
        f"README install order {headings} does not match INSTALL_METHODS"
    )


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
        f"`CONFIDENCE_K` = **{CONFIDENCE_K}**",
        f"≥ **{MIN_ROUNDS}**",
        "multi-round-independent-pooled",
    ],
)
def test_dashboard_publishes_the_ship_rule_constants(fragment):
    assert fragment in _flat(DASHBOARD), f"the ship rule table must publish {fragment!r} from scripts/ship_floor.py"


def test_dashboard_says_which_rule_produced_the_table_it_shows():
    """The gate changed once; a board that does not say under which rule it was
    gated is a number without units.

    The published Results table is run 4's, issued under the clause ADR-0006
    retired. The dashboard has to name that clause, name the one in force, and
    say the table is not re-gated — otherwise a reader cannot tell whether they
    are looking at a measurement or a restatement.
    """
    flat = _flat(DASHBOARD)
    assert "0006-confidence-bound-on-the-pooled-mean" in flat, (
        "the dashboard must link the record that changed the gate"
    )
    assert "Which rule produced the table on this page" in flat
    assert f"`POOLED_LOWER_BOUND` ({POOLED_LOWER_BOUND})" in flat, (
        "the retired constant must stay published, or the archived verdicts lose their units"
    )
    assert "re-gated" in flat and "run 5" in flat.lower()


def test_dashboard_does_not_present_the_retired_clause_as_the_rule_in_force():
    """The ship-rule table is the rule a contributor will act on, so it publishes
    the clause in force. The retired one may only appear as history."""
    flat = _flat(DASHBOARD)
    assert f"| `POOLED_LOWER_BOUND` | ≥ **{POOLED_LOWER_BOUND}** |" not in flat, (
        "the ship rule table still lists the retired lower bound as a live condition"
    )


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


#: One chunk of a manifest `published_f1` string: a scope, a value, and the
#: corpus size it was measured over, behind whatever parenthetical detail the
#: manifest chose to carry in front of `n=`.
F1_CHUNK_RE = re.compile(r"^(?P<scope>[a-z][a-z-]+)\s+(?P<value>\d(?:\.\d+)?)\s*\((?:[^)]*,\s*)?n=(?P<n>\d+)\)$")

#: The only two scopes an F1 may be published under. `mixed-proxy` is a
#: category-level word for "both of these", never a scope a number carries.
F1_SCOPES = frozenset({"scenario-level", "artifact-signal-only"})


def _manifest_f1_parts(category: str) -> list[tuple[str, float, int]]:
    """(scope, value, n) triples for one category, parsed out of the manifest.

    The parse is the point. The README prints every F1 in one shape, and a
    normalisation that is typed rather than derived is exactly the drift these
    tests exist to catch. Two things are re-derived on the way through: the
    per-scope corpus sizes must sum to the manifest's own `cases_present`, so a
    split that stops accounting for the whole corpus fails here instead of
    being published, and every scope must be one the labels define.
    """
    entry = _manifest_category(category)
    published = entry.get("published_f1")
    cases = int((entry.get("registry_coverage") or {}).get("cases_present") or 0)
    if published in (None, "null"):
        return []
    if isinstance(published, (int, float)):
        # AST10 alone stores a bare float; its scope lives in the sibling field.
        scope = str(entry.get("f1_scope") or "").strip()
        assert scope in F1_SCOPES, f"{category} publishes a bare F1 with no scope to label it: {scope!r}"
        return [(scope, float(published), cases)]
    parts: list[tuple[str, float, int]] = []
    for chunk in str(published).split(";"):
        match = F1_CHUNK_RE.match(chunk.strip())
        assert match, f"{category}: unparsable published_f1 chunk {chunk.strip()!r}"
        parts.append((match["scope"], float(match["value"]), int(match["n"])))
    unknown = {scope for scope, _, _ in parts} - F1_SCOPES
    assert not unknown, f"{category}: published_f1 uses undefined scope(s) {sorted(unknown)}"
    accounted = sum(n for *_, n in parts)
    assert accounted == cases, (
        f"{category}: published_f1 accounts for n={accounted}, but the manifest records {cases} labeled cases"
    )
    return parts


def _normalised_f1(category: str) -> str:
    """The README's single presentation of an F1: `scope value (n=N)`, joined by ` + `."""
    parts = _manifest_f1_parts(category)
    if not parts:
        return f"`{_manifest_f1_state(category)}`"
    return " + ".join(f"`{scope} {value:.2f} (n={n})`" for scope, value, n in parts)


@pytest.mark.parametrize("category", AST_IDS)
def test_readme_skills_table_matches_the_fixture_manifest(category):
    """A README that drifts from the manifests is worse than no README.

    Two assertions, because the section presents each F1 twice on purpose. The
    measured-results table prints every number in one shape so the column can
    be scanned — `1.000`, `1.00` and a bare `1.0` were three renderings of the
    same claim — and the skill's own block quotes the manifest string verbatim,
    parenthetical and all, so the normalisation stays auditable. Both sides are
    derived from `fixtures/manifest.yaml` here; neither is typed.
    """
    normalised = _normalised_f1(category)
    cell = _results_row(category)[1]
    assert cell == normalised, f"README's F1 cell for {category} is {cell!r}; the manifest normalises to {normalised!r}"
    verbatim = _manifest_f1_state(category)
    assert f"`{verbatim}`" in _detector_detail_block(category), (
        f"{category}'s block must quote fixtures/manifest.yaml verbatim: `{verbatim}`"
    )


def test_readme_skills_table_covers_every_skill():
    """Both tables, because the section splits identity from measurement."""
    roster = _readme_table(README_ROSTER_COLUMNS)
    results = _readme_table(README_RESULTS_COLUMNS)
    for category in AST_IDS:
        assert category in roster, f"README skills roster has no {category} row"
        declared = _skill_name(category)
        assert roster[category][1] == f"`{declared}`", (
            f"the roster names {roster[category][1]} for {category}; SKILL.md declares {declared!r}"
        )
    assert {row[1] for row in roster.values()} == set(results), (
        "the roster and the measured-results table must list the same eleven skills"
    )
    assert f"`{_skill_name('advisory')}`" in results


@pytest.mark.parametrize("category", AST_IDS)
def test_every_category_keeps_its_long_form_detector_description(category):
    """The roster cell is a one-liner; the paragraph it summarises must survive.

    This is the guard on the relocation. The long per-detector prose used to sit
    inside the table — one 60-to-90-word paragraph per cell, which is what made
    the section unreadable — and now sits in a per-skill block under the roster.
    A block deleted or emptied would leave the front page publishing a check
    roster it never describes, which is worse than the wall of text was.
    """
    block = _detector_detail_block(category)
    assert f"<code>{_skill_name(category)}</code>" in block, f"{category}'s block must name the skill it describes"
    assert f"skills/{category}/coverage-matrix.md" in block, (
        f"{category}'s block must point at its scenario-by-scenario matrix"
    )
    words = len(re.sub(r"<[^>]+>", " ", block).split())
    assert words >= 40, f"{category}'s block is {words} words — the long-form description is gone"


def test_the_advisory_row_publishes_no_f1_because_it_has_no_corpus():
    """`advisory` is judged, never measured, and the table must not blur that."""
    data = yaml.safe_load(FIXTURE_MANIFEST.read_text(encoding="utf-8")) or {}
    assert "advisory" not in (data.get("categories") or {}), (
        "advisory now has a fixture corpus; the README must publish its F1 like every other skill"
    )
    cell = _results_row("advisory")[1]
    assert not re.search(r"\d", cell), f"advisory publishes no F1; its cell must carry no number, got {cell!r}"
    assert "no F1" in _detector_detail_block("advisory"), (
        "advisory's block must say outright that it publishes no F1, not leave the dash unexplained"
    )


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
        # The third kind of evidence. Judge scores grade the text and detector F1
        # grades the scripts; this is the only surface that grades an agent's output,
        # and an architecture page that omitted it would describe a repository that
        # measures two things when it measures three.
        "eval/skill_evals.py",
        "eval/skill_eval_grade.py",
        "skill-eval-report.md",
    ],
)
def test_architecture_explains_every_moving_part(component):
    assert component in _flat(ARCHITECTURE), f"docs/architecture.md must explain how {component} fits in"


@pytest.mark.parametrize(
    "claim",
    [
        "delta between the two pass rates is the deliverable",
        "always different models",
        "never averaged",
    ],
)
def test_architecture_states_the_three_rules_the_third_surface_lives_by(claim):
    """Run it twice, never let one model grade itself, never mix the units."""
    assert claim in _flat(ARCHITECTURE)


def test_readme_distinguishes_all_three_kinds_of_evidence():
    """A reader must be able to tell a pass_rate from an F1 from a judge total, and
    the README is where most of them will meet all three for the first time."""
    flat = _flat(DEVELOPMENT)
    assert "Three kinds of evidence" in flat
    for link in ("skill-judge-dashboard.md", "f1-report.md", "skill-eval-report.md"):
        assert link in flat, f"the evidence table must link {link}"
    for question in (
        "Is the **text** of a `SKILL.md` well written",
        "Do the shipped Python check scripts separate",
        "Does an agent **holding** a skill behave better",
    ):
        assert question in flat, "each surface needs a sentence saying what it answers, not only a name"
    assert "never averaged with one another" in flat


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


# ---------------------------------------------------------------------------
# 5. Documented paths, commands, subcommands and counts must exist / agree
# ---------------------------------------------------------------------------

REGISTRY = REPO_ROOT / "scenarios" / "registry.yaml"
MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
COMMANDS_DIR = REPO_ROOT / "commands" / "ast"
SKILLS_DIR = REPO_ROOT / "skills"

#: Documents whose every pointer is asserted below. Adding a doc here is the
#: cheapest way to bring it under the same discipline.
DOC_PATHS = {
    "README.md": README,
    "docs/architecture.md": ARCHITECTURE,
    # The signing runbook names commands, key paths, tests and a re-signing
    # trigger. It is read months after it is written, by which time an orphan
    # reference in it is indistinguishable from an instruction.
    "docs/signing.md": SIGNING,
    "docs/skill-judge-dashboard.md": DASHBOARD,
    # Generated, but subject to exactly the same orphan-reference contract: a
    # generated document that names a path or a test that does not exist is
    # still a document a reader checks and finds wrong.
    "docs/f1-report.md": F1_REPORT,
    "docs/dogfood-report.md": DOGFOOD_REPORT,
    "docs/skill-eval-report.md": SKILL_EVAL_REPORT,
}

#: A backticked token is treated as a repository path only when its first
#: segment is one of these. Deliberately an allowlist: `SKILL.md`,
#: `.vscode/tasks.json`, `~/.claude/skills` and `requirements.txt` are all
#: legitimately-backticked strings that are not paths in *this* tree, and a
#: heuristic that guessed would fail on them instead of on real rot.
PATH_ROOTS = frozenset(
    {
        "skills",
        "scenarios",
        "vendor",
        "fixtures",
        "detectors",
        "validators",
        "adapters",
        "scripts",
        "eval",
        "cli",
        "commands",
        "docs",
        "config",
        "schemas",
        "tests",
        ".claude-plugin",
        ".github",
    }
)

TOP_LEVEL_FILES = frozenset(
    {
        "README.md",
        "NOTICE",
        "LICENSE",
        "CONTRIBUTING.md",
        "CODEOWNERS",
        "THIRD_PARTY_LICENSES.md",
        "ruff.toml",
        "package.json",
        "conftest.py",
    }
)

BACKTICK_RE = re.compile(r"`([^`\n]+)`")
NODE_ID_RE = re.compile(r"`([\w./\-]+\.py)::([\w:]+)`")


def _candidate_paths(text: str) -> set[str]:
    """Backticked tokens that claim to be a path inside this repository."""
    found: set[str] = set()
    for raw in BACKTICK_RE.findall(text):
        token = raw.split("::", 1)[0].strip().rstrip(".,;:)")
        if not token or " " in token or "<" in token or ".." in token:
            continue  # prose, a placeholder, or a range like AST01..AST10
        if token.startswith(("http://", "https://", "~", "$")):
            continue
        head = token.split("/", 1)[0]
        if head in PATH_ROOTS or token in TOP_LEVEL_FILES:
            found.add(token.rstrip("/"))
    return found


def _resolves(token: str) -> bool:
    if "*" in token:
        if list(REPO_ROOT.glob(token)):
            return True
        # A glob may legitimately match nothing yet (eval/scorecards/*.json
        # before the first judged run). Its literal ancestor must still exist,
        # which is what catches a typo'd directory.
        literal = [part for part in token.split("/") if "*" not in part]
        prefix = REPO_ROOT
        for part in literal:
            if part.endswith((".py", ".md", ".json", ".yaml", ".yml", ".toml")):
                break
            prefix = prefix / part
        return prefix.is_dir()
    return (REPO_ROOT / token).exists()


@pytest.mark.parametrize("doc", sorted(DOC_PATHS))
def test_every_documented_repository_path_exists(doc):
    """The orphan-reference failure, as a test rather than as a review habit."""
    text = DOC_PATHS[doc].read_text(encoding="utf-8")
    dangling = sorted(token for token in _candidate_paths(text) if not _resolves(token))
    assert not dangling, f"{doc} points at path(s) that do not exist: {dangling}"


@pytest.mark.parametrize("doc", sorted(DOC_PATHS))
def test_every_documented_pytest_node_id_names_a_real_test(doc):
    """`tests/x.py::test_y` in prose must name a test that is actually defined."""
    text = DOC_PATHS[doc].read_text(encoding="utf-8")
    missing: list[str] = []
    for rel, node in NODE_ID_RE.findall(text):
        path = REPO_ROOT / rel
        if not path.is_file():
            missing.append(f"{rel} (file missing)")
            continue
        func = node.split("::")[-1]
        if f"def {func}(" not in path.read_text(encoding="utf-8"):
            missing.append(f"{rel}::{func}")
    assert not missing, f"{doc} cites test(s) that do not exist: {missing}"


def _python_cli_subcommands() -> set[str]:
    """The subcommands cli/ast10.py's own argparse actually registers."""
    spec = importlib.util.spec_from_file_location("_ast10_cli", REPO_ROOT / "cli" / "ast10.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parser = module.build_parser()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    raise AssertionError("cli/ast10.py's parser registers no subcommands")


PY_CLI_RE = re.compile(r"python3 cli/ast10\.py\s+([a-z][a-z0-9-]*)")


@pytest.mark.parametrize("doc", sorted(DOC_PATHS))
def test_every_documented_python_cli_subcommand_exists(doc):
    documented = set(PY_CLI_RE.findall(DOC_PATHS[doc].read_text(encoding="utf-8")))
    real = _python_cli_subcommands()
    assert documented <= real, (
        f"{doc} documents cli/ast10.py subcommand(s) that do not exist: {sorted(documented - real)}"
    )


def test_readme_documents_every_python_cli_subcommand_that_exists():
    """The other direction: a verb nobody documents is a verb nobody finds."""
    documented = set(PY_CLI_RE.findall(README.read_text(encoding="utf-8")))
    assert _python_cli_subcommands() <= documented, (
        f"README.md documents no usage for cli/ast10.py subcommand(s): {sorted(_python_cli_subcommands() - documented)}"
    )


def _node_cli_verbs() -> set[str]:
    """The verbs cli/bin/cli.js's own dispatch switch accepts."""
    source = (REPO_ROOT / "cli" / "bin" / "cli.js").read_text(encoding="utf-8")
    body = source[source.index("switch (command)") :]
    verbs = set(re.findall(r'case "([a-z][a-z0-9-]*)":', body))
    assert verbs, "could not read cli/bin/cli.js's dispatch switch"
    return verbs


NODE_CLI_RE = re.compile(r"(?:node cli/bin/cli\.js|ast10-skills)\s+([a-z][a-z0-9-]*)")


@pytest.mark.parametrize("doc", sorted(DOC_PATHS))
def test_every_documented_node_cli_verb_exists(doc):
    documented = set(NODE_CLI_RE.findall(DOC_PATHS[doc].read_text(encoding="utf-8")))
    real = _node_cli_verbs()
    assert documented <= real, f"{doc} documents cli/bin/cli.js verb(s) that do not exist: {sorted(documented - real)}"


SLASH_RE = re.compile(r"/ast:([a-z0-9][a-z0-9-]*)")


@pytest.mark.parametrize("doc", sorted(DOC_PATHS))
def test_every_documented_slash_command_has_a_file(doc):
    text = DOC_PATHS[doc].read_text(encoding="utf-8")
    # `/ast:audit-ast01` … `/ast:audit-ast10` is a written range, so accept any
    # of the ten as satisfied by the ten files on disk.
    documented = set(SLASH_RE.findall(text))
    missing = sorted(name for name in documented if not (COMMANDS_DIR / f"{name}.md").is_file())
    assert not missing, f"{doc} names slash command(s) with no file in commands/ast/: {missing}"


NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
}

#: Spelled forms, for assertions that must quote a derived count the way prose
#: spells it rather than the way Python prints it.
NUMBER_WORDS_INVERSE = {value: word for word, value in NUMBER_WORDS.items()}


def test_readme_slash_command_count_matches_the_directory():
    """A spelled-out count is the cheapest claim to get wrong and the last to be checked.

    Every occurrence is checked, not the first: README.md states the count twice
    (once in prose, once in the repository-layout block) and the two drifting
    apart is exactly as wrong as either drifting from the directory.
    """
    on_disk = len(sorted(COMMANDS_DIR.glob("*.md")))
    flat = _flat(README)
    stated = re.findall(r"(\w+) slash commands", flat)
    counted = [s for s in stated if s.lower() in NUMBER_WORDS or s.isdigit()]
    assert counted, f"README.md must state how many slash commands commands/ast/ holds, found {stated}"
    for token in counted:
        value = int(token) if token.isdigit() else NUMBER_WORDS[token.lower()]
        assert value == on_disk, f"README.md says {token} slash commands; commands/ast/ holds {on_disk}"


def test_readme_registry_scenario_count_matches_the_registry():
    total = len(yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["scenarios"])
    assert f"{total} whitepaper scenarios" in _flat(DEVELOPMENT), (
        f"docs/development.md's repository-layout block must say '{total} whitepaper scenarios'"
    )


# ---------------------------------------------------------------------------
# The README skills table: detector state is derived, never typed
# ---------------------------------------------------------------------------


def _registry_static_ids(category: str) -> set[str]:
    scenarios = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["scenarios"]
    return {s["id"] for s in scenarios if s["category"] == category and s["tier"] == "static-detectable"}


def _manifest_category(category: str) -> dict:
    data = yaml.safe_load(FIXTURE_MANIFEST.read_text(encoding="utf-8")) or {}
    return (data.get("categories") or {}).get(category) or {}


def _labeled_full_ids(category: str) -> set[str]:
    covered: set[str] = set()
    for entry in _manifest_category(category).get("detectable_scenarios") or []:
        if entry.get("covers") != "full":
            continue
        ids = entry.get("registry_ids") or []
        covered.update([ids] if isinstance(ids, str) else ids)
    return covered


def _derived_detector_state(category: str) -> str:
    """The single definition of the README's Detector-state column.

    registry (rank 2) says what is decidable; the fixture manifest (rank 4) says
    what carries a shipped check and a labeled pair. Nothing here reads the
    README, so the README cannot make itself right.
    """
    static = _registry_static_ids(category)
    declared = _manifest_category(category).get("detectable_scenarios") or []
    if not static and not declared:
        return "declared-and-uncovered"
    if static - _labeled_full_ids(category):
        return "coverage-debt"
    return "implemented"


def _readme_pipe_tables() -> list[tuple[tuple[str, ...], dict[str, list[str]]]]:
    """Every pipe table in README.md as (header tuple, rows keyed by first cell).

    Parsed by header rather than by line prefix, because the skills section now
    splits its data across two tables and both of them key on a skill. A
    `startswith("| AST01 |")` scan cannot tell them apart; a header can.
    """
    tables: list[tuple[tuple[str, ...], dict[str, list[str]]]] = []
    header: tuple[str, ...] | None = None
    for line in README.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            header = None
            continue
        cells = tuple(cell.strip() for cell in stripped.strip("|").split("|"))
        if header is None:
            header = cells
            tables.append((header, {}))
            continue
        if set("".join(cells)) <= set("-:"):
            continue  # the |---|---| rule under the header
        assert len(cells) == len(header), f"README table '{' | '.join(header)}' has a {len(cells)}-cell row: {stripped}"
        tables[-1][1][cells[0]] = list(cells)
    return tables


#: The two tables the skills section splits its data across, by exact header.
#: A column renamed, added or dropped fails here loudly instead of silently
#: shifting what every index below refers to.
README_ROSTER_COLUMNS = ("AST", "Skill", "What the detector decides", "Detector state")
README_RESULTS_COLUMNS = ("Skill", "F1 (measured)", "Judged (run 5)")


def _readme_table(columns: tuple[str, ...]) -> dict[str, list[str]]:
    matching = [rows for header, rows in _readme_pipe_tables() if header == columns]
    assert len(matching) == 1, (
        f"README.md must carry exactly one table headed '{' | '.join(columns)}', found {len(matching)}"
    )
    return matching[0]


def _skill_name(directory: str) -> str:
    """The installed skill name, from the package's own frontmatter."""
    body = (SKILLS_DIR / directory / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(r"^name:\s*(\S+)\s*$", body, re.M)
    assert match, f"skills/{directory}/SKILL.md declares no name in its frontmatter"
    return match.group(1)


def _roster_row(category: str) -> list[str]:
    rows = _readme_table(README_ROSTER_COLUMNS)
    assert category in rows, f"README skills roster has no {category} row"
    return rows[category]


def _results_row(directory: str) -> list[str]:
    rows = _readme_table(README_RESULTS_COLUMNS)
    key = f"`{_skill_name(directory)}`"
    assert key in rows, f"README measured-results table has no {key} row"
    return rows[key]


def _detector_detail_block(label: str) -> str:
    """The one `<details>` block docs/detectors.md devotes to a skill, by its bold label."""
    blocks = re.findall(r"<details>.*?</details>", DETECTORS.read_text(encoding="utf-8"), re.S)
    hits = [b for b in blocks if f"<b>{label}</b>" in b]
    assert len(hits) == 1, f"docs/detectors.md must carry exactly one <details> block for {label}, found {len(hits)}"
    return hits[0]


@pytest.mark.parametrize("category", AST_IDS)
def test_readme_detector_state_matches_the_state_derived_from_the_manifests(category):
    """The blocking finding, as a test: no row may describe a check that does not exist."""
    state = _derived_detector_state(category)
    cells = _roster_row(category)
    assert len(cells) == len(README_ROSTER_COLUMNS), (
        f"{category} row must be {' | '.join(README_ROSTER_COLUMNS)}, got {len(cells)} cells"
    )
    assert cells[3] == f"`{state}`", (
        f"README says detector state {cells[3]!r} for {category}; the manifests derive {state!r}"
    )


def _recorded_verdict(skill: str) -> tuple[str, float] | None:
    """The gate's own verdict and pooled mean for one skill, straight off disk."""
    card = REPO_ROOT / "eval" / "scorecards" / f"{skill}.json"
    if not card.is_file():
        return None
    payload = json.loads(card.read_text(encoding="utf-8"))
    return payload["verdict"], payload["aggregate"]["mean"]


@pytest.mark.parametrize("skill", (*AST_IDS, "advisory"))
def test_readme_judged_column_matches_the_recorded_scorecards(skill):
    """The front page may not publish a verdict the gate did not produce.

    Same rule as the detector-state column, applied to the other measurement the
    section carries: the value is derived from `eval/scorecards/`, never typed.
    A README that says SHIP where the scorecard says BLOCKED is the most costly
    possible drift, because it is the one claim a reader takes at face value and
    never checks. `advisory` is checked here too — it holds a scorecard like
    every other skill and is one of the eleven the ship count counts.
    """
    recorded = _recorded_verdict(skill)
    cell = _results_row(skill)[2]
    if recorded is None:
        assert "not judged" in cell.lower(), (
            f"{skill} has no scorecard in eval/scorecards/; its Judged cell must say so, got {cell!r}"
        )
        return
    verdict, mean = recorded
    assert verdict in cell, f"README says {cell!r} for {skill}; eval/scorecards/ records {verdict}"
    assert f"{mean}" in cell, f"README's Judged cell for {skill} omits the recorded pooled mean {mean}"


def test_readme_ship_count_matches_the_recorded_scorecards():
    """ "Eleven of the eleven skills clear the ship rule" has to be eleven, and eleven.

    Counted from the scorecards rather than from the table, so the prose and the
    rows cannot drift apart or drift together in the same wrong direction. The
    words are derived too — the sentence read "Nine of the eleven" for a run and
    was not edited by hand when the count moved; this test failed instead.
    """
    cards = sorted((REPO_ROOT / "eval" / "scorecards").glob("*.json"))
    if not cards:
        pytest.skip("no scorecards recorded — nothing for the README to count")
    shipped = sum(1 for c in cards if json.loads(c.read_text(encoding="utf-8"))["verdict"] == "SHIP")
    words = {n: w for n, w in enumerate("zero one two three four five six seven eight nine ten eleven".split())}
    flat = _flat(README)
    assert f"{words[shipped].capitalize()} of the {words[len(cards)]} skills clear the ship rule" in flat, (
        f"{shipped} of {len(cards)} recorded skills clear the ship rule; README.md must say so in those words"
    )


@pytest.mark.parametrize("category", AST_IDS)
def test_readme_declared_and_uncovered_rows_promise_no_detection(category):
    """A category with no shipped check may not be described in the present tense."""
    if _derived_detector_state(category) != "declared-and-uncovered":
        return
    decides = _roster_row(category)[2]
    assert "No check ships" in decides, (
        f"{category} ships no detector check; its README cell must say so outright, not describe detection: {decides!r}"
    )


def _detector_check_count(category: str) -> int:
    spec = importlib.util.spec_from_file_location(
        f"_detector_{category}", SKILLS_DIR / category / "scripts" / "detector.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return len(module.run_all({"manifest": {}, "files": {}}))


@pytest.mark.parametrize("category", AST_IDS)
def test_readme_check_count_matches_the_detector_module(category):
    """ "Ten checks:" has to be ten checks. Counting them is one import away."""
    decides = _roster_row(category)[2]
    actual = _detector_check_count(category)
    match = re.match(r"\*?\*?([A-Za-z]+) checks?\b", decides)
    word = match.group(1).lower() if match else None
    stated = NUMBER_WORDS.get(word) if word else None
    if actual == 0:
        assert stated is None, f"{category} runs no check; its README cell claims {word!r} check(s): {decides[:60]!r}"
        return
    assert stated is not None, (
        f"{category} runs {actual} check(s); its README cell must open with that count, got {decides[:60]!r}"
    )
    assert stated == actual, f"README says {word} check(s) for {category}; detector.py registers {actual}"


@pytest.mark.parametrize("category", AST_IDS)
def test_declared_and_uncovered_categories_really_register_no_check(category):
    """Guards the row above from being satisfied by prose over a live detector."""
    if _derived_detector_state(category) == "declared-and-uncovered":
        assert _detector_check_count(category) == 0, (
            f"{category} claims declared-and-uncovered but run_all returns checks"
        )
    else:
        assert _detector_check_count(category) > 0, f"{category} claims a detector state but run_all returns nothing"


def test_readme_legend_defines_every_state_it_uses():
    """Every value the two state columns can take must be defined where they are explained."""
    flat = _flat(READING)
    states = {_derived_detector_state(c) for c in AST_IDS} | {"coverage-debt"}
    scopes = {str((_manifest_category(c).get("f1_scope") or "")).strip() for c in AST_IDS} - {"", "none", "mixed-proxy"}
    for token in sorted(states | scopes):
        assert f"**`{token}`**" in flat, f"docs/reading-the-results.md must define the state `{token}`"


# ---------------------------------------------------------------------------
# Coverage matrices: the re-derivation command each one ships must actually work
# ---------------------------------------------------------------------------

REDERIVE_RE = re.compile(r"^(python3 -c \"import yaml; \[print\(s\['id'\].*?)$", re.M)


@pytest.mark.parametrize("category", AST_IDS)
def test_every_coverage_matrix_ships_a_command_that_reproduces_the_registry(category):
    """README: "a reader can check the table rather than believe it". Check it."""
    matrix = SKILLS_DIR / category / "coverage-matrix.md"
    commands = [c for c in REDERIVE_RE.findall(matrix.read_text(encoding="utf-8")) if f"'{category}'" in c]
    assert commands, f"{matrix.relative_to(REPO_ROOT)} ships no command that re-derives its scenario table"

    result = subprocess.run(["bash", "-c", commands[0]], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, f"{category}: re-derivation command failed: {result.stderr.strip()}"

    scenarios = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["scenarios"]
    expected = [f"{s['id']} | {s['title']} | {s['tier']}" for s in scenarios if s["category"] == category]
    assert result.stdout.splitlines() == expected, f"{category}: the shipped command does not reproduce the registry"


# ---------------------------------------------------------------------------
# `references/` — the pointer no skill ships
# ---------------------------------------------------------------------------

REFERENCES_DISCLAIMER = "ships no `references/` directory"


@pytest.mark.parametrize("skill", sorted(p.name for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file()))
def test_no_skill_points_at_a_references_directory_it_does_not_ship(skill):
    """A `references/` pointer is either backed by a directory or disclaimed."""
    body = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
    if "references/" not in body:
        return
    if (SKILLS_DIR / skill / "references").is_dir():
        return
    assert REFERENCES_DISCLAIMER in body, (
        f"skills/{skill}/SKILL.md mentions `references/` but ships none and does not say so"
    )


def test_no_page_implies_a_references_directory_that_exists_nowhere():
    """Whichever page names `references/` has to say no skill ships one.

    The claim used to live only on the README, so moving the prose into docs/
    would have silently retired the guard. It now follows the mention.
    """
    if [p.name for p in SKILLS_DIR.iterdir() if (p / "references").is_dir()]:
        return
    caveats = ("which no skill ships today", "no skill ships a `references/` directory")
    # docs/architecture.md is the page that enumerates the hashed surface globs,
    # so it is where a reader meets `references/*.md` as a thing that could exist.
    # Other pages name it inside a glob list or as a layout convention; the claim
    # that matters is that the repository states somewhere that none ships.
    architecture = _flat(ARCHITECTURE)
    assert any(c in architecture for c in caveats), (
        "docs/architecture.md enumerates `references/*.md` as a hashed surface; it must say no skill ships one"
    )
    readme = _flat(README)
    if "references/" in readme:
        assert any(c in readme for c in caveats), (
            "README.md names `references/`, which no skill ships; it must say so where it names it"
        )


# ---------------------------------------------------------------------------
# No documented install path copies `commands/`
# ---------------------------------------------------------------------------


def test_no_install_path_copies_the_commands_directory(tmp_path):
    """README says the slash commands come with the clone, not with an install.

    Asserted by running the installer, because the previous version of this
    claim said the opposite and nothing caught it.
    """
    spec = importlib.util.spec_from_file_location("_ast10_install", REPO_ROOT / "cli" / "ast10.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = tmp_path / "skills"
    assert module.main(["install", "--all", "--target", str(target)]) == 0
    assert target.is_dir() and any(target.iterdir()), "install --all wrote nothing"
    assert not (target / "commands").exists(), "cli/ast10.py install copied commands/ — the docs say it does not"
    for skill in target.iterdir():
        assert not (skill / "commands").exists(), f"{skill.name} was installed with a commands/ payload"


def test_readme_is_accurate_about_which_install_path_delivers_the_commands():
    """One install path delivers the slash commands and the others do not.

    The retired version of this guard required the README to say no install
    method brings them, which was true only while the manifest was a flat
    index. The plugin now declares `./commands/ast`, so `/plugin install`
    delivers them — and `cli/ast10.py install` and a `cp -r` of `skills/` still
    do not, which is asserted against the real installer in
    `test_no_install_path_copies_the_commands_directory`. A README that makes
    one blanket claim is wrong either way, so it has to distinguish them.
    """
    flat = _flat(README).lower()
    assert "none of the three methods above copies them" not in flat, (
        "README.md still carries the retired blanket claim; the plugin install now delivers the commands"
    )
    assert "installs the skills and the slash commands together" in flat, (
        "README.md must say which install path delivers commands/ast/"
    )
    assert "does not copy `commands/ast/`" in flat, (
        "README.md must say which install paths do not deliver commands/ast/"
    )


# ---------------------------------------------------------------------------
# docs/architecture.md must describe marketplace.json as it actually is
# ---------------------------------------------------------------------------


def test_architecture_names_only_plugins_the_manifest_actually_declares():
    """The manifest is a real plugin marketplace now, so the page may describe
    plugins — but only the ones it declares, and by the names it declares them
    under. It named two invented plugins once and nothing caught it."""
    marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    declared = {plugin["name"] for plugin in marketplace["plugins"]}
    flat = _flat(ARCHITECTURE)
    assert "declares two plugins" not in flat, f"the manifest declares {len(declared)} plugin(s): {sorted(declared)}"
    for invented in ("ast-detectors", "ast-advisory"):
        assert invented not in flat or invented in declared, (
            f"docs/architecture.md names a marketplace plugin that does not exist: {invented!r}"
        )
    for name in declared:
        assert name in flat, f"docs/architecture.md does not name the plugin the manifest ships: {name!r}"


def test_architecture_states_the_skill_count_the_plugin_installs():
    """Derived from the directory the plugin installs from, not from a restated
    index — the manifest no longer carries a count to drift against."""
    marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    installed = (REPO_ROOT / marketplace["plugins"][0]["skills"]).resolve()
    assert len([d for d in installed.iterdir() if d.is_dir()]) == 11
    assert "eleven skills" in _flat(ARCHITECTURE), "docs/architecture.md must state how many skills the plugin installs"


# ---------------------------------------------------------------------------
# The hashed surface the docs describe is the surface content_hash.py defines
# ---------------------------------------------------------------------------


def test_docs_describe_the_content_hash_surface_the_code_defines():
    from scripts.content_hash import (
        POPULATED_SURFACE_GLOBS,
        SURFACE_GLOBS,
        UNPOPULATED_SURFACE_GLOBS,
    )

    flat = _flat(ARCHITECTURE)
    for pattern in SURFACE_GLOBS:
        assert f"`{pattern}`" in flat, f"docs/architecture.md must name surface glob {pattern!r}"
    if UNPOPULATED_SURFACE_GLOBS:
        # The verb is deliberately outside the match. When `evals/evals.json`
        # moved into POPULATED_SURFACE_GLOBS the prose went from "two of those
        # four patterns match" to "one of those four patterns matches", and an
        # assertion that pinned the plural failed on correct documentation.
        # What has to be present is the claim, not its subject-verb agreement.
        assert "**no file in this repository**" in flat, (
            "docs/architecture.md must say which surface globs match nothing here"
        )
    assert set(POPULATED_SURFACE_GLOBS) | set(UNPOPULATED_SURFACE_GLOBS) == set(SURFACE_GLOBS)


def test_dashboard_pins_the_rubric_sha_the_gate_pins():
    """A rubric SHA printed in the docs that the gate does not pin is a lie.

    `RUBRIC_SHA` is the constant that turns "scored against a different rubric
    version" into BLOCKED rather than into a lower number, so the published
    value has to be the enforced one.
    """
    flat = _flat(DASHBOARD)
    assert f"`{RUBRIC_SHA}`" in flat, f"docs/skill-judge-dashboard.md must publish RUBRIC_SHA {RUBRIC_SHA}"
    stray = [sha for sha in re.findall(r"\b[0-9a-f]{40}\b", flat) if sha != RUBRIC_SHA]
    assert not stray, f"the dashboard prints rubric sha(s) the gate does not pin: {sorted(set(stray))}"


def test_dashboard_names_the_aggregation_method_the_gate_requires():
    assert f"`{AGG_METHOD}`" in _flat(DASHBOARD)


def test_dashboard_available_provider_rows_name_an_adapter_module_that_exists():
    """Every "Available — verified live" row must point at a real adapter file."""
    rows = [
        line
        for line in DASHBOARD.read_text(encoding="utf-8").splitlines()
        if line.startswith("| `") and "adapters/" in line
    ]
    assert len(rows) >= 3, f"expected the available-provider roster, found {len(rows)} row(s)"
    for row in rows:
        for module in re.findall(r"`(adapters/[\w./]+\.py)`", row):
            assert (REPO_ROOT / module).is_file(), f"dashboard names a missing adapter module: {module}"


def test_dashboard_unavailable_rows_match_the_audit_config_exactly():
    """Both directions: a provider declared unavailable in config must appear in
    the roster table, and the table may not invent one the config does not carry."""
    declared = set(_unavailable_providers())
    text = DASHBOARD.read_text(encoding="utf-8")
    start = text.index("### Unavailable")
    section = text[start : text.index("\n---", start)]
    tabled = {
        m.group(1)
        for m in (re.match(r"\| `([\w./\-]+)` \|", line) for line in section.splitlines() if line.startswith("| `"))
        if m
    }
    assert declared <= tabled, (
        f"config/audit.yml declares unavailable provider(s) the dashboard omits: {sorted(declared - tabled)}"
    )
    assert tabled <= declared, (
        f"the dashboard tables unavailable provider(s) config/audit.yml does not declare: {sorted(tabled - declared)}"
    )


# ---------------------------------------------------------------------------
# The slash-command pages document a check roster that must be the real one
# ---------------------------------------------------------------------------


def _command_page(category: str) -> str:
    path = COMMANDS_DIR / f"audit-{category.lower()}.md"
    assert path.is_file(), f"no slash-command page for {category}"
    return path.read_text(encoding="utf-8")


def _documented_checks(category: str) -> set[str]:
    """Check ids the command page's "Checks this command runs" table presents as
    running, excluding rows that say outright they are not implemented.

    A page may legitimately carry no such table — AST07 and AST09 ship no check
    and say "Why there is nothing to run" instead — and an empty set is then the
    correct answer, which the assertions below compare against the module.
    """
    page = _command_page(category)
    heading = "## Checks this command runs"
    if heading not in page:
        assert "## Why there is nothing to run" in page, (
            f"audit-{category.lower()}.md documents no check roster and does not explain why"
        )
        return set()
    start = page.index(heading)
    section = page[start : page.index("\n## ", start + 1)]
    listed: set[str] = set()
    for line in section.splitlines():
        if not line.startswith("| `"):
            continue
        if "not implemented as code" in line:
            continue
        listed.update(re.findall(r"`(AST\d\d-[A-Za-z0-9-]+)`", line))
    return listed


@pytest.mark.parametrize("category", AST_IDS)
def test_command_page_lists_exactly_the_checks_the_detector_registers(category):
    """A command page promising a check the module does not register is the
    orphan-reference failure aimed at the person about to run it."""
    spec = importlib.util.spec_from_file_location(
        f"_cmd_detector_{category}", SKILLS_DIR / category / "scripts" / "detector.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    registered = {finding.scenario for finding in module.run_all({"manifest": {}, "files": {}})}
    documented = _documented_checks(category)
    assert documented == registered, (
        f"commands/ast/audit-{category.lower()}.md documents {sorted(documented)} "
        f"but skills/{category}/scripts/detector.py registers {sorted(registered)}"
    )


@pytest.mark.parametrize("category", AST_IDS)
def test_command_page_checks_run_line_matches_the_detector(category):
    page = _command_page(category)
    line = next((ln for ln in page.splitlines() if ln.startswith("CHECKS RUN:")), None)
    assert line, f"audit-{category.lower()}.md's sample output must carry a CHECKS RUN footer"
    stated = int(re.search(r"(\d+)", line).group(1))
    assert stated == len(_documented_checks(category)), (
        f"audit-{category.lower()}.md says {line.strip()!r} but documents {len(_documented_checks(category))} check(s)"
    )


@pytest.mark.parametrize("category", AST_IDS)
def test_command_page_quotes_the_f1_state_the_manifest_publishes(category):
    """The stalest thing on a command page is the number in its sample output."""
    page = _command_page(category)
    line = next((ln for ln in page.splitlines() if ln.startswith("F1:")), None)
    assert line, f"audit-{category.lower()}.md's sample output must carry an F1 footer"
    published = _manifest_category(category).get("published_f1")
    if published is None:
        assert "not published" in line, f"{category} publishes no F1; the page must say so: {line!r}"
        return
    forms = {str(published)}
    if isinstance(published, float):
        forms |= {f"{published:.2f}", f"{published:.3f}"}
    assert any(form in line for form in forms), (
        f"audit-{category.lower()}.md's F1 footer says {line.strip()!r}; fixtures/manifest.yaml publishes {published!r}"
    )


def _heading_slugs(text: str) -> set[str]:
    """GitHub's slug rule, near enough: lowercase, drop punctuation, spaces to dashes."""
    slugs: set[str] = set()
    for line in text.splitlines():
        if not line.startswith("#"):
            continue
        title = line.lstrip("#").strip()
        slug = re.sub(r"[^\w\s-]", "", title.lower()).strip()
        slugs.add(re.sub(r"[\s]+", "-", slug))
    return slugs


@pytest.mark.parametrize("doc", sorted(DOC_PATHS))
def test_every_in_page_anchor_link_resolves_to_a_heading(doc):
    """A `](#section)` link to a heading that was renamed is dead on the page."""
    text = DOC_PATHS[doc].read_text(encoding="utf-8")
    slugs = _heading_slugs(text)
    dangling = sorted(a for a in re.findall(r"\]\(#([\w-]+)\)", text) if a not in slugs)
    assert not dangling, f"{doc} links to anchor(s) with no matching heading: {dangling}"


@pytest.mark.parametrize("doc", sorted(DOC_PATHS))
def test_every_relative_markdown_link_points_at_a_file_that_exists(doc):
    """`[text](path/to/thing.md)` must resolve, including `../` out of docs/."""
    path = DOC_PATHS[doc]
    text = path.read_text(encoding="utf-8")
    dangling: list[str] = []
    for target in re.findall(r"\]\(([^)#\s]+)(?:#[\w-]+)?\)", text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if not (path.parent / target).exists():
            dangling.append(target)
    assert not dangling, f"{doc} links to file(s) that do not exist: {sorted(set(dangling))}"


# ---------------------------------------------------------------------------
# 6. Claims a pre-publication review found overstated, pinned to the artifact
# ---------------------------------------------------------------------------
#
# Each test below re-derives a published claim from the corpus or the code, so
# the prose cannot go back to the flattering version once the numbers move. They
# are grouped because they share a failure shape: every one of them was a true
# sentence about an earlier run that stayed on the page after it stopped being
# true, which is the most expensive kind of documentation defect this repository
# can ship — a reader has no way to date a sentence.


def _plain(path: Path) -> str:
    """`_flat`, with Markdown emphasis, code ticks and typographic dashes removed.

    An assertion about a *figure* must not fail because the figure was bolded,
    and must not pass because it was not.
    """
    text = _flat(path)
    for glyph, ascii_form in (("−", "-"), ("–", "-"), ("→", "->"), ("×", "x")):
        text = text.replace(glyph, ascii_form)
    return text.replace("**", "").replace("`", "")


def _live_scorecards() -> dict[str, dict]:
    directory = REPO_ROOT / "eval" / "scorecards"
    return {
        json.loads(p.read_text(encoding="utf-8"))["skill"]: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(directory.glob("*.json"))
    }


def _ships_under_each_clause() -> tuple[int, int, int]:
    """(retired-clause ships, live-clause ships, skills) over the live corpus.

    The retired clause is `mean - stdev >= POOLED_LOWER_BOUND`; the live one is
    `mean - CONFIDENCE_K * sem >= POOLED_TARGET`. Both are recomputed from each
    scorecard's stored statistics rather than read from a `verdict` field,
    because the point is to compare two rules over one corpus.
    """
    cards = _live_scorecards()
    retired = live = 0
    for card in cards.values():
        agg = card["aggregate"]
        floors_clear = all(agg["dim_means"].get(d, 0) >= f for d, f in FLOORS.items())
        grade_a = agg["mean"] >= POOLED_TARGET
        retired += bool(floors_clear and grade_a and agg["lower_bound"] >= POOLED_LOWER_BOUND)
        live += bool(floors_clear and grade_a and agg["ci_lower"] >= POOLED_TARGET)
    return retired, live, len(cards)


def test_the_readme_states_what_the_gate_change_bought_on_the_run_it_gates():
    """ "The change bought nothing" was true of run 4 and is false of run 5.

    Derived, not hard-coded: whatever the two clauses say about the live corpus,
    the README must state the retired clause's count when it differs from the
    live one, and must not carry the unqualified claim that the change cost
    nothing.
    """
    retired, live, total = _ships_under_each_clause()
    flat = _plain(README)
    if retired == live:
        pytest.skip(f"both clauses ship {live} of {total} on this corpus; there is nothing to disclose")
    assert f"run 5 is {retired} of {total}" in _plain(READING), (
        f"the live corpus ships {live} of {total} under the rule in force and {retired} of {total} "
        f"under the retired one; docs/reading-the-results.md must say so"
    )
    for name, page in (("README.md", flat), ("docs/reading-the-results.md", _plain(READING))):
        assert "it bought nothing when adopted" not in page, (
            f"{name} must not claim the gate change bought nothing without naming the run that is "
            f"true of — it bought {live - retired} ship(s) on the corpus it now gates"
        )


def test_the_docs_do_not_present_the_confidence_bound_as_the_stricter_rule():
    """Whichever clause is harsher on this corpus, the page has to say which.

    `mean - sigma >= 105` and `mean - sigma/sqrt(n) >= 108` cross over at
    `sigma = 3/(1 - 1/sqrt(n))`. Above that sigma the adopted clause demands the
    LOWER mean, which is the case for every skill in the live corpus, and a
    reader told only that a confidence bound replaced a spread statistic will
    assume the opposite.
    """
    cards = _live_scorecards()
    harder = [
        skill
        for skill, card in cards.items()
        if POOLED_TARGET + CONFIDENCE_K * card["aggregate"]["sem"] > POOLED_LOWER_BOUND + card["aggregate"]["stdev"]
    ]
    if harder:
        pytest.skip(f"the adopted clause is the harder one on {sorted(harder)}; the caveat does not apply")
    gaps = {
        skill: (POOLED_LOWER_BOUND + card["aggregate"]["stdev"])
        - (POOLED_TARGET + CONFIDENCE_K * card["aggregate"]["sem"])
        for skill, card in cards.items()
    }
    adr_0006 = REPO_ROOT / "docs" / "adr" / "0006-confidence-bound-on-the-pooled-mean.md"
    for name, text in (("the dashboard", _plain(DASHBOARD)), ("ADR-0006", _plain(adr_0006))):
        assert "demands a lower mean than the retired" in text, (
            f"at every (n, sigma) in the live corpus the adopted clause demands a lower mean than "
            f"the retired one, and {name} must publish that rather than leaving 'confidence bound' "
            "to imply strictness"
        )
        # The size of the gap, not just its sign: "slightly more permissive" and
        # "two points more permissive on the row that decides the board" are
        # different claims, and only one of them is true here.
        for value in (min(gaps.values()), max(gaps.values())):
            assert f"{value:.2f}" in text, f"{name} must publish the {value:.2f}-point gap it derives from"


#: Every judged corpus on disk, live first. The crossover tally below is a
#: statement about all of them, so it may not be derived from the live one alone.
ALL_CORPORA = ("scorecards", "scorecards-run1", "scorecards-run2", "scorecards-run3", "scorecards-run4")


def _clause_bars() -> list[tuple[str, str, int, float, float, float]]:
    """`(corpus, skill, n, sigma, retired_bar, adopted_bar)` for every judged skill-run.

    The two clauses are the bars `mean >= POOLED_LOWER_BOUND + sigma` and
    `mean >= POOLED_TARGET + CONFIDENCE_K * sem`, so comparing the bars compares
    the rules independently of what any particular skill scored. `sem` is derived
    from the ROUNDED `stdev`, exactly as `ship_floor.pooled_stats` derives it, so
    this lands on the gate's own arithmetic rather than near it.
    """
    rows = []
    for corpus in ALL_CORPORA:
        directory = REPO_ROOT / "eval" / corpus
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            card = json.loads(path.read_text(encoding="utf-8"))
            agg = card.get("aggregate")
            if not isinstance(agg, dict) or not agg.get("judgments"):
                continue
            judgments = agg["judgments"]
            n = len(judgments)
            sigma = round(statistics.stdev(judgments), 2)
            sem = round(sigma / math.sqrt(n), 2)
            rows.append(
                (
                    corpus,
                    str(card.get("skill", path.stem)),
                    n,
                    sigma,
                    POOLED_LOWER_BOUND + sigma,
                    POOLED_TARGET + CONFIDENCE_K * sem,
                )
            )
    return rows


def test_the_crossover_tally_every_page_publishes_is_the_one_the_corpora_yield():
    """How often the adopted clause was the harder one is a measured count, not a memory.

    Three pages state it. It was hand-tallied once as "exactly four skill-runs"
    and it is three — the fourth, `AST06` in run 4, is an exact tie at the
    precision the gate publishes (both clauses demand 109.04), and a tie is not
    an instance of the new rule being stricter. The direction of that error is
    the one that matters: it made the adopted clause look harder more often than
    it has ever been, which is precisely the impression ADR-0006 is required not
    to leave.
    """
    rows = _clause_bars()
    assert rows, "no judged corpus on disk; the tally cannot be derived"
    harder = [(c, s) for c, s, _n, _sd, ret, ado in rows if ado > ret]
    tied = [(c, s) for c, s, _n, _sd, ret, ado in rows if ado == ret]

    pages = {
        "docs/reading-the-results.md": _plain(READING),
        "the dashboard": _plain(DASHBOARD),
        "ADR-0006": _plain(REPO_ROOT / "docs" / "adr" / "0006-confidence-bound-on-the-pooled-mean.md"),
    }
    for name, text in pages.items():
        assert "exactly four skill-runs" not in text, (
            f"{name} carries the hand-tallied 'exactly four skill-runs'; the corpora yield "
            f"{len(harder)} strictly harder ({sorted(harder)}) and {len(tied)} tied ({sorted(tied)})"
        )
        assert f"{len(rows)} skill-runs" in text, f"{name} must state the {len(rows)} skill-runs the tally is over"
        # Spelled, not digits: "three" is how all three pages say it, and a bare
        # "3" would also match a sigma or a round number somewhere on the page.
        word = NUMBER_WORDS_INVERSE.get(len(harder), str(len(harder)))
        assert f"strictly higher mean on exactly {word}" in text, (
            f"{name} must state that the adopted clause demanded a strictly higher mean on exactly "
            f"{word} of {len(rows)} skill-runs: {sorted(harder)}"
        )

    # The tie is a named row, not a footnote: it is the one a re-tally trips over.
    for name, text in pages.items():
        for _corpus, skill in tied:
            assert skill in text, f"{name} must name {skill}, the exact tie, rather than absorbing it into the count"


def _skills_without_an_anti_pattern_section() -> list[str]:
    """Roster entries whose `SKILL.md` contains no `NEVER` prohibition at all."""
    out = []
    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        if "NEVER" not in path.read_text(encoding="utf-8"):
            out.append(path.parent.name)
    return out


def test_the_d3_anti_pattern_claim_is_qualified_by_the_skill_that_contradicts_it():
    """A controlled result licenses the narrow claim, and the page must not widen it.

    The run-3 -> run-4 arm shows that ADDING an anti-pattern section raises `D3`
    on a skill that is at or under the floor. It does not show that a
    consolidated `NEVER` section is what a good `D3` is made of — and this
    repository ships the counterexample. Any skill with no such section that
    nonetheless scores above every treated skill's starting `D3` has to be named
    on the page that makes the claim, with its score, or the claim is wider than
    the evidence.
    """
    untreated = _skills_without_an_anti_pattern_section()
    if not untreated:
        pytest.skip("every shipped skill carries an anti-pattern section; there is no counterexample")
    cards = _live_scorecards()
    run3 = REPO_ROOT / "eval" / "scorecards-run3"
    treated = ("AST02", "AST03", "AST04", "AST05", "AST06", "AST07", "AST09", "AST10")
    starting = [
        json.loads((run3 / f"{s}.json").read_text(encoding="utf-8"))["aggregate"]["dim_means"]["D3"]
        for s in treated
        if (run3 / f"{s}.json").is_file()
    ]
    assert starting, "run 3 is not on disk; the treated skills' starting D3 cannot be derived"

    adr_path = REPO_ROOT / "docs" / "adr" / "0005-judge-panel-calibration-and-the-lower-bound.md"
    dashboard, adr = _plain(DASHBOARD), _plain(adr_path)
    for skill in untreated:
        card = cards.get(skill)
        if card is None:
            continue
        d3 = card["aggregate"]["dim_means"]["D3"]
        if d3 <= max(starting):
            continue
        for name, text in (("dashboard", dashboard), ("ADR-0005", adr)):
            assert skill in text, f"{name} makes the D3 claim without naming {skill}, which contradicts it"
            assert "no consolidated anti-pattern section" in text or "no anti-pattern section" in text, (
                f"{name} must say plainly that {skill} has no anti-pattern section at all"
            )
        assert f"{d3:g}" in dashboard, (
            f"{skill} scores D3 {d3:g} with no anti-pattern section, above every treated skill's "
            f"starting D3 (max {max(starting):g}); the dashboard must publish that number"
        )


#: Below this, a "<n> checks" phrase is a per-category count rather than a
#: repository-wide total. The largest single category ships ten, so any figure
#: from twelve up is claiming a roll-up and has to match the roll-up.
DETECTOR_TOTAL_FLOOR = 12


def test_no_document_claims_a_detector_total_the_modules_do_not_ship():
    """Per-category counts are checked row by row; this catches the roll-up.

    A repository-wide "N detectors ship" is the figure a reader quotes, it is
    the figure nothing else here derives, and it was wrong: prose claimed 37
    against 36 registered checks. Every candidate total in any committed
    Markdown must now equal the sum of the modules' own registries.
    """
    total = sum(_detector_check_count(category) for category in AST_IDS)
    offenders: list[str] = []
    pattern = re.compile(r"\b(\d+)\s+(?:\w+\s+){0,2}?(?:detector|check)s\b", re.IGNORECASE)
    for path in _committed_files():
        if path.suffix != ".md":
            continue
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            claimed = int(match.group(1))
            if claimed >= DETECTOR_TOTAL_FLOOR and claimed != total:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {match.group(0)!r}")
    assert not offenders, f"{total} checks ship across the ten modules; these claim otherwise: {offenders}"


def test_the_readme_rows_sum_to_the_shipped_check_count():
    """The table is the only place the total is derivable, so its parts must add up."""
    stated = 0
    for category in AST_IDS:
        match = re.match(r"\*?\*?([A-Za-z]+) checks?\b", _roster_row(category)[2])
        if match:
            stated += NUMBER_WORDS.get(match.group(1).lower(), 0)
    assert stated == sum(_detector_check_count(c) for c in AST_IDS)


def test_the_sweep_page_check_table_matches_the_detector_modules():
    """`/ast:audit-skill-package` publishes a per-category check roster; it must be the real one.

    Every single-category command page is already checked against its module by
    `test_command_page_lists_exactly_the_checks_the_detector_registers`. The
    all-ten sweep page was not, and it drifted furthest: it carried a
    scaffold-era roster — 13 checks over six categories — long after 36 shipped
    across eight, which is the figure a reader of the sweep page quotes.
    """
    page = (COMMANDS_DIR / "audit-skill-package.md").read_text(encoding="utf-8")
    stated: dict[str, int] = {}
    for line in page.splitlines():
        match = re.match(r"\|\s*(AST\d\d)\s[^|]*\|\s*(\d+)\s*\|", line)
        if match:
            stated[match.group(1)] = int(match.group(2))
    actual = {category: _detector_check_count(category) for category in AST_IDS}
    assert stated == actual, f"commands/ast/audit-skill-package.md publishes {stated}; the modules register {actual}"
    assert f"**{sum(actual.values())} in total**" in page, (
        f"the sweep page must state the roll-up too: {sum(actual.values())} checks ship"
    )


CAVEAT_SECTION = "What 11 of 11 is, and what it is not"

#: The four limits the headline number may never be published without. Each is
#: (label, the substrings that together prove the caveat is actually MADE rather
#: than merely alluded to). Kept as data because the failure mode this guards is
#: a caveat being softened one clause at a time until only its heading survives.
REQUIRED_CAVEATS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("self-authored corpus", ("corpus is self-authored", "not** external validation")),
    ("panel bias with the flagged judge", ("11.4-point spread", "COARSE", "8 of 11")),
    ("k = 1.0 is not a confidence level", ("not a confidence level", "design effect")),
    ("leave-one-out / missing-data fragility", ("198 attempted", "107.6", "single-judge exclusions")),
)


def _caveat_section() -> str:
    """The body of the caveats section, heading excluded, next `##` excluded."""
    text = LIMITS.read_text(encoding="utf-8")
    start = text.find(f"## {CAVEAT_SECTION}")
    assert start != -1, f"docs/limits.md no longer has a '## {CAVEAT_SECTION}' section"
    rest = text[start + len(CAVEAT_SECTION) :]
    end = rest.find("\n## ")
    return rest[:end] if end != -1 else rest


def test_the_headline_number_carries_all_four_caveats_in_its_own_section():
    """11 of 11 is the figure a reader quotes, so its limits live beside it.

    A pre-publication review found the section carrying three of the four: the
    leave-one-out result (the board is 8 of 11 without one judge, and three of
    six single-judge exclusions block AST01) was published elsewhere and not
    here, where someone reading only the headline would meet it. Each caveat is
    asserted by the figures that make it a claim rather than a gesture — a
    heading alone does not satisfy this test.
    """
    section = _caveat_section()
    missing = [
        f"{label} (missing: {[frag for frag in frags if frag not in section]})"
        for label, frags in REQUIRED_CAVEATS
        if any(frag not in section for frag in frags)
    ]
    assert not missing, f"'{CAVEAT_SECTION}' must carry all four caveats; incomplete: {missing}"


def test_the_caveat_section_states_its_own_length_correctly():
    """ "The three limits" outlived the third limit once; it must not do so again.

    The count is re-derived from the bolded lead-ins actually present, so adding
    or removing a caveat fails here until the prose that introduces them agrees.
    """
    section = _caveat_section()
    # DOTALL: a lead-in that reflows across a line break is still a lead-in.
    leads = re.findall(r"^\*\*(.+?)\*\*", section, re.MULTILINE | re.DOTALL)
    count = len(leads)
    word = {3: "three", 4: "four", 5: "five", 6: "six"}[count]
    flat = _plain(LIMITS)
    assert f"the {word} limits on it sit here" in flat, (
        f"the section opens with {count} bolded limits ({leads}); its preamble must say '{word}'"
    )
    assert f"it is {word} paragraphs" in _plain(READING), (
        f"the cross-reference to the limits page must call it {word} paragraphs, not another count"
    )
    for stale in {"three", "four", "five", "six"} - {word}:
        assert f"the {stale} limits on it sit here" not in flat


def test_the_readme_audit_example_is_real_output_from_the_command_it_shows():
    """A fabricated sample transcript is a lie a reader cannot check.

    The README shows a trimmed `audit` run. Every non-elided line of it must
    appear in the real output of the exact command printed above it, so the
    example cannot drift from the tool and cannot have been invented.
    """
    body = README.read_text(encoding="utf-8")
    command = next(line for line in body.splitlines() if line.startswith("node cli/bin/cli.js audit fixtures/")).strip()
    block = next(
        chunk for chunk in body.split("```") if "AST01-obfuscated-payload-exec" in chunk and "FINDING" in chunk
    )

    result = subprocess.run(command.split(), cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    # `--fail-on-detect` on a fixture that detects: a non-zero exit IS the contract,
    # and a zero exit here would mean the example no longer demonstrates a finding.
    assert result.returncode != 0, f"the documented example stopped detecting anything:\n{result.stdout}"
    produced = " ".join(result.stdout.split())
    for line in (ln.strip() for ln in block.splitlines()):
        if not line or line.startswith("AST01   Malicious Skills"):
            continue  # the header carries column padding the shell may reflow
        assert " ".join(line.split()) in produced, (
            f"README's audit example shows a line the command does not print: {line!r}"
        )


def test_no_commit_in_history_names_a_sibling_repo():
    """The working-tree guard above is structurally blind to history.

    `_committed_files()` builds its list from `git ls-files`, so it sees the
    tree as it is now. A pre-publication audit found six pushed commits naming
    every forbidden sibling repo -- including a clickable URL to a private one
    -- while that guard passed, because the names had been scrubbed from the
    tree and left in history. Publishing makes every commit browsable, so the
    tree being clean proves nothing on its own.

    History was rewritten on 2026-08-26 to remove them. This is what keeps it
    that way: it scans every commit, not the checkout.
    """
    if not (REPO_ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    revs = subprocess.run(["git", "rev-list", "--all"], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if revs.returncode != 0:
        pytest.skip("git rev-list unavailable")
    commits = revs.stdout.split()
    assert commits, "no commits to scan"

    pattern = "|".join(FORBIDDEN_NAMES)
    dirty: list[str] = []
    for commit in commits:
        hit = subprocess.run(
            ["git", "grep", "-l", "-I", "-E", pattern, commit, "--"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if hit.returncode == 0 and hit.stdout.strip():
            files = sorted({line.split(":", 1)[-1] for line in hit.stdout.strip().splitlines()})
            dirty.append(f"{commit[:8]}: {files[:4]}")
    assert not dirty, (
        "commits in history name a sibling repository; a clean working tree does not fix this, "
        "because publishing makes every commit browsable:\n  " + "\n  ".join(dirty)
    )
