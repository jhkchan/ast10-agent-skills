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
import re
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
F1_REPORT = REPO_ROOT / "docs" / "f1-report.md"
DOGFOOD_REPORT = REPO_ROOT / "docs" / "dogfood-report.md"
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
    "docs/skill-judge-dashboard.md": DASHBOARD,
    # Generated, but subject to exactly the same orphan-reference contract: a
    # generated document that names a path or a test that does not exist is
    # still a document a reader checks and finds wrong.
    "docs/f1-report.md": F1_REPORT,
    "docs/dogfood-report.md": DOGFOOD_REPORT,
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
    assert f"{total} whitepaper scenarios" in _flat(README), (
        f"README.md's repository-layout block must say '{total} whitepaper scenarios'"
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


def _readme_row(category: str) -> list[str]:
    rows = [line for line in README.read_text(encoding="utf-8").splitlines() if line.startswith(f"| {category} |")]
    assert len(rows) == 1, f"README skills table needs exactly one {category} row"
    return [cell.strip() for cell in rows[0].strip().strip("|").split("|")]


#: Column order of the README skills table, so a row that gains or loses a cell
#: fails loudly instead of silently shifting what every index below refers to.
README_SKILL_COLUMNS = ("AST", "Skill", "decides", "Detector state", "F1", "Judged")


@pytest.mark.parametrize("category", AST_IDS)
def test_readme_detector_state_matches_the_state_derived_from_the_manifests(category):
    """The blocking finding, as a test: no row may describe a check that does not exist."""
    state = _derived_detector_state(category)
    cells = _readme_row(category)
    assert len(cells) == len(README_SKILL_COLUMNS), (
        f"{category} row must be {' | '.join(README_SKILL_COLUMNS)}, got {len(cells)} cells"
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


@pytest.mark.parametrize("category", AST_IDS)
def test_readme_judged_column_matches_the_recorded_scorecards(category):
    """The front page may not publish a verdict the gate did not produce.

    Same rule as the detector-state column, applied to the other measurement the
    table now carries: the value is derived from `eval/scorecards/`, never typed.
    A README that says SHIP where the scorecard says BLOCKED is the most costly
    possible drift, because it is the one claim a reader takes at face value and
    never checks.
    """
    recorded = _recorded_verdict(category)
    cell = _readme_row(category)[5]
    if recorded is None:
        assert "not judged" in cell.lower(), (
            f"{category} has no scorecard in eval/scorecards/; its Judged cell must say so, got {cell!r}"
        )
        return
    verdict, mean = recorded
    assert verdict in cell, f"README says {cell!r} for {category}; eval/scorecards/ records {verdict}"
    assert f"{mean}" in cell, f"README's Judged cell for {category} omits the recorded pooled mean {mean}"


def test_readme_ship_count_matches_the_recorded_scorecards():
    """ "Nine of the eleven skills clear the ship rule" has to be nine, and eleven.

    Counted from the scorecards rather than from the table, so the prose and the
    rows cannot drift apart or drift together in the same wrong direction.
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
    decides = _readme_row(category)[2]
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
    decides = _readme_row(category)[2]
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
    """Every value the two state columns can take must be defined above the table."""
    flat = _flat(README)
    states = {_derived_detector_state(c) for c in AST_IDS} | {"coverage-debt"}
    scopes = {str((_manifest_category(c).get("f1_scope") or "")).strip() for c in AST_IDS} - {"", "none", "mixed-proxy"}
    for token in sorted(states | scopes):
        assert f"**`{token}`**" in flat, f"README.md's skills legend must define the state `{token}`"


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


def test_readme_does_not_imply_a_references_directory_that_exists_nowhere():
    shipped = [p.name for p in SKILLS_DIR.iterdir() if (p / "references").is_dir()]
    flat = _flat(README)
    if shipped:
        return
    assert "which no skill ships today" in flat, (
        "no skill ships a `references/` directory; README.md must say so where it names one"
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


def test_readme_does_not_claim_an_install_method_brings_in_the_commands():
    flat = _flat(README).lower()
    for overclaim in ("also brings in commands/", "installs commands/", "installing via method 2 also brings"):
        assert overclaim not in flat, f"README.md must not claim: {overclaim!r} — no install path copies commands/"
    assert "none of the three methods above copies them" in flat, (
        "README.md must state plainly that no install method copies commands/ast/"
    )


# ---------------------------------------------------------------------------
# docs/architecture.md must describe marketplace.json as it actually is
# ---------------------------------------------------------------------------


def test_architecture_does_not_invent_marketplace_plugins():
    """It is a flat skill index; it declares no plugins, and said so wrongly once."""
    marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    assert "plugins" not in marketplace, "marketplace.json now declares plugins; update docs/architecture.md"
    flat = _flat(ARCHITECTURE)
    assert "declares two plugins" not in flat
    for invented in ("ast-detectors", "ast-advisory"):
        assert invented not in flat, (
            f"docs/architecture.md names a marketplace plugin that does not exist: {invented!r}"
        )


def test_architecture_states_the_marketplace_skill_count_the_file_carries():
    marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    count = len(marketplace["skills"])
    assert count == 11
    assert "eleven skills" in _flat(ARCHITECTURE), "docs/architecture.md must state how many skills the index carries"


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
        assert "match **no file in this repository**" in flat, (
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
