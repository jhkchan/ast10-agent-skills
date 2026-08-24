"""Structural gate on the hand-authored `evals/evals.json` case files.

This is the input side of the repository's THIRD kind of evidence, and it is
worth naming what the other two are so nothing here gets read as one of them:

  * judge scores  grade the TEXT of a SKILL.md against the vendored 8-dimension
    rubric. No prompt is ever executed. (`eval/scorecards*/`)
  * detector F1   grades the Python check scripts against labelled fixtures.
    Real output measurement — of the scripts, not of an agent. (`fixtures/`)
  * eval cases    THIS surface. Each case is run twice, once by an agent holding
    the skill and once by an agent holding nothing, and the delta between the two
    pass rates is the deliverable.

Nothing in this module executes a prompt or produces a pass rate; it asserts that
the authored cases are well-formed, convention-compliant, and point at inputs that
exist, so a harness run cannot fail for a reason that is really a typo. The
field names and the file path are the ones the agentskills.io "Evaluating skills"
guidance fixes — `skill_name`, `evals`, and per case `id` / `prompt` /
`expected_output` / optional `files` / `assertions` — and the top-level key check
below exists to stop this repository inventing its own dialect of them.

`skills/<AST>/evals/evals.json` is inside `scripts/content_hash.py`'s
`SURFACE_GLOBS`, so authoring one changes that skill's `content_hash`. That is
deliberate and long anticipated: a surface definition that silently stops covering
a shipped file is the AST10 metadata-loss shape.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"

#: Skills that MUST ship authored eval cases. Discovery below is by directory, so
#: a skill can join the set by adding the file — but it cannot LEAVE the set by
#: deleting it, which is the direction that loses evidence quietly.
REQUIRED_EVAL_SKILLS = (
    "AST01",
    "AST02",
    "AST03",
    "AST04",
    "AST05",
    "AST06",
    "AST07",
    "AST08",
    "AST09",
    "AST10",
    "advisory",
)

#: The guidance's schema, stated as data so a drifting dialect fails here rather
#: than inside a harness run.
TOP_LEVEL_KEYS = {"skill_name", "evals"}
REQUIRED_CASE_KEYS = {"id", "prompt", "expected_output", "assertions"}
OPTIONAL_CASE_KEYS = {"files"}

#: The guidance says start at two to three cases per skill and do not over-invest
#: before the first results are in.
MIN_CASES_PER_SKILL = 2
MAX_CASES_PER_SKILL = 3

#: An assertion is only useful if a skill-less baseline can plausibly fail it, and
#: one assertion per case cannot express a with/without delta at all.
MIN_ASSERTIONS_PER_CASE = 2


def _skills_with_evals() -> list[str]:
    """Every skill directory that ships an `evals/` directory, discovered on disk.

    Discovered rather than hard-coded so a skill that adds cases is validated the
    moment the file lands, without anybody remembering to widen a tuple here.
    """
    return sorted(d.name for d in SKILLS_DIR.iterdir() if (d / "evals").is_dir())


def _load(skill: str) -> dict:
    path = SKILLS_DIR / skill / "evals" / "evals.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _skill_md_name(skill: str) -> str:
    text = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{skill}/SKILL.md must open with YAML frontmatter"
    end = text.find("\n---\n", 4)
    assert end != -1, f"{skill}/SKILL.md frontmatter is not closed"
    frontmatter = yaml.safe_load(text[4:end])
    return frontmatter["name"]


SKILLS_WITH_EVALS = _skills_with_evals()

#: (skill, case) pairs, flattened so a bad case names itself in the test id.
CASES = [
    pytest.param(skill, case, id=f"{skill}-{case.get('id')}")
    for skill in SKILLS_WITH_EVALS
    for case in _load(skill).get("evals", [])
]


# --------------------------------------------------------------------------- #
# The file exists, parses, and is the shape the convention fixes
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("skill", REQUIRED_EVAL_SKILLS)
def test_required_skill_ships_eval_cases(skill):
    """The authored set may grow; it may not shrink by deletion."""
    path = SKILLS_DIR / skill / "evals" / "evals.json"
    assert path.is_file(), (
        f"{skill} is in REQUIRED_EVAL_SKILLS but ships no evals/evals.json. "
        f"With/without evidence for this skill would silently stop being produced."
    )
    assert skill in SKILLS_WITH_EVALS


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_eval_file_parses_as_json(skill):
    payload = _load(skill)
    assert isinstance(payload, dict), f"{skill}: evals.json must be a JSON object"


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_eval_file_uses_exactly_the_convention_top_level_keys(skill):
    """Convention-compliance is the point; a local dialect defeats it."""
    assert set(_load(skill)) == TOP_LEVEL_KEYS


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_evals_dir_ships_only_the_case_file_and_optional_input_files(skill):
    """`evals/evals.json` is in the hashed surface; a stray sibling is not."""
    evals_dir = SKILLS_DIR / skill / "evals"
    stray = sorted(
        p.relative_to(evals_dir).as_posix() for p in evals_dir.iterdir() if p.name not in {"evals.json", "files"}
    )
    assert not stray, f"{skill}/evals/ carries unexpected entries: {stray}"


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_skill_name_matches_the_skill_md_frontmatter(skill):
    """The case file must name the skill it grades, not a directory label."""
    assert _load(skill)["skill_name"] == _skill_md_name(skill)


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_case_count_is_within_the_guidance_band(skill):
    evals = _load(skill)["evals"]
    assert isinstance(evals, list)
    assert MIN_CASES_PER_SKILL <= len(evals) <= MAX_CASES_PER_SKILL, (
        f"{skill}: {len(evals)} cases; the guidance band is "
        f"{MIN_CASES_PER_SKILL}-{MAX_CASES_PER_SKILL} — start small, do not "
        f"over-invest before the first with/without results exist"
    )


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_case_ids_are_unique_within_a_skill(skill):
    ids = [case["id"] for case in _load(skill)["evals"]]
    assert len(ids) == len(set(ids)), f"{skill}: duplicate case ids in {ids}"


# --------------------------------------------------------------------------- #
# Each case is runnable: a real prompt, a stated success condition, real inputs
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("skill", "case"), CASES)
def test_case_has_exactly_the_convention_keys(skill, case):
    keys = set(case)
    missing = REQUIRED_CASE_KEYS - keys
    unknown = keys - REQUIRED_CASE_KEYS - OPTIONAL_CASE_KEYS
    assert not missing, f"{skill} case {case.get('id')}: missing {sorted(missing)}"
    assert not unknown, f"{skill} case {case.get('id')}: unknown key(s) {sorted(unknown)}"


@pytest.mark.parametrize(("skill", "case"), CASES)
def test_case_id_is_a_positive_integer(skill, case):
    assert isinstance(case["id"], int) and not isinstance(case["id"], bool)
    assert case["id"] > 0


@pytest.mark.parametrize(("skill", "case"), CASES)
def test_case_prompt_is_a_realistic_non_empty_message(skill, case):
    prompt = case["prompt"]
    assert isinstance(prompt, str) and prompt.strip(), "prompt must be a non-empty string"
    assert len(prompt.split()) >= 12, (
        f"{skill} case {case['id']}: prompt is {len(prompt.split())} words. "
        f'"check this skill" is too vague to test anything — name paths, files, context'
    )


@pytest.mark.parametrize(("skill", "case"), CASES)
def test_case_expected_output_is_non_empty(skill, case):
    expected = case["expected_output"]
    assert isinstance(expected, str) and expected.strip()


@pytest.mark.parametrize(("skill", "case"), CASES)
def test_case_has_at_least_two_assertions(skill, case):
    assertions = case["assertions"]
    assert isinstance(assertions, list)
    assert len(assertions) >= MIN_ASSERTIONS_PER_CASE, (
        f"{skill} case {case['id']}: {len(assertions)} assertion(s); at least {MIN_ASSERTIONS_PER_CASE} required"
    )
    for text in assertions:
        assert isinstance(text, str) and text.strip(), "every assertion must be a non-empty string"


@pytest.mark.parametrize(("skill", "case"), CASES)
def test_case_assertions_are_distinct(skill, case):
    assertions = case["assertions"]
    assert len(assertions) == len(set(assertions)), (
        f"{skill} case {case['id']}: a repeated assertion double-counts one behaviour in the pass rate"
    )


@pytest.mark.parametrize(("skill", "case"), CASES)
def test_every_referenced_input_file_exists_on_disk(skill, case):
    """`files` paths are repo-root-relative, and a missing one is a harness failure
    that would be scored as a skill failure."""
    files = case.get("files", [])
    assert isinstance(files, list)
    for rel in files:
        assert isinstance(rel, str) and rel.strip()
        assert not Path(rel).is_absolute(), f"{skill} case {case['id']}: {rel!r} must be repo-relative"
        assert (REPO_ROOT / rel).exists(), f"{skill} case {case['id']}: referenced input {rel!r} does not exist"


# --------------------------------------------------------------------------- #
# The one case shape a with/without eval is uniquely good at catching
# --------------------------------------------------------------------------- #


def _clean_fixture_packages(skill: str) -> list[Path]:
    """Labelled clean packages for a category: `fixtures/<AST>/C<n>-*`.

    Empty for `advisory` and for the categories that ship no detector and so no
    fixture corpus (AST07, AST09) — those have no clean package to feed, and
    their with/without value lies in refusing to convict at all rather than in
    surviving a clean input.
    """
    directory = REPO_ROOT / "fixtures" / skill
    if not directory.is_dir():
        return []
    return sorted(d for d in directory.iterdir() if d.is_dir() and d.name.startswith("C"))


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_at_least_one_case_feeds_the_skill_a_clean_fixture(skill):
    """A detector-shaped skill that convicts everything scores well until it meets
    a clean package. This is the failure mode a with/without eval is best placed to
    expose, so every category that HAS a labelled clean package must feed one."""
    if not _clean_fixture_packages(skill):
        pytest.skip(f"fixtures/{skill}/ ships no labelled clean package")
    clean = [
        case["id"]
        for case in _load(skill)["evals"]
        for rel in case.get("files", [])
        if Path(rel).parts[:2] == ("fixtures", skill)
        and len(Path(rel).parts) > 2
        and Path(rel).parts[2].startswith("C")
    ]
    assert clean, (
        f"{skill}: no case feeds a labelled clean fixture from fixtures/{skill}/. "
        f"Without one, a skill that cries wolf on every package passes this eval."
    )


# --------------------------------------------------------------------------- #
# What the attached inputs give away, counted rather than assumed
# --------------------------------------------------------------------------- #

#: A scenario id as the fixtures and the assertions both spell it.
_SCENARIO_ID_RE = re.compile(r"\b(?:AST\d\d|advisory)-S\d\d\b")

#: Assertions whose scenario id appears VERBATIM in the case's own attached files,
#: as `(eval-slug, 1-based assertion index)`.
#:
#: This is a measured property of the authored corpus, frozen here so it is a
#: number a reader can see rather than a caveat somebody remembers. The labelled
#: fixture packages carry their own provenance header — `fixture_scenario_id:
#: AST01-S10`, "labeled vulnerable" — and a case that attaches such a package hands
#: BOTH arms the answer to any assertion that only asks for the scenario id back.
#: The first live smoke run showed exactly this: on `AST01-case-2` the
#: without_skill arm named AST01-S10 correctly, having read it off the fixture's
#: front matter, and the delta on that case came entirely from the one assertion
#: that asks for a piece of reasoning instead of a label.
#:
#: This does NOT invalidate a delta — both arms see the same input, which is the
#: whole design — but it does mean these assertions are weak discriminators, and
#: `assertion-review.json`'s `passed_in_both` bucket is where they will surface.
#: The set is frozen so that growth is loud: an eval author adding a case that
#: leans on a leaked label has to come here and say so.
LEAKED_SCENARIO_ID_ASSERTIONS: frozenset[tuple[str, int]] = frozenset(
    {
        ("AST01-case-1", 1),
        ("AST01-case-2", 1),
        ("AST01-case-2", 5),
        ("AST02-case-1", 1),
        ("AST02-case-2", 2),
        ("AST03-case-1", 1),
        ("AST03-case-2", 1),
        ("AST03-case-3", 4),
        ("AST08-case-2", 1),
        ("AST08-case-2", 5),
    }
)


def _attached_text(case: dict) -> str:
    """Every byte of every file the case attaches, concatenated.

    A `files` entry may name a directory, matching what `eval/skill_evals.py`
    inlines into the prompt, so this reads what the agent actually sees.
    """
    chunks: list[str] = []
    for rel in case.get("files") or []:
        target = REPO_ROOT / rel
        paths = sorted(p for p in target.rglob("*") if p.is_file()) if target.is_dir() else [target]
        for path in paths:
            try:
                chunks.append(path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, OSError):
                continue  # binary fixture bytes carry no scenario id to leak
    return "\n".join(chunks)


def _measured_leaks() -> set[tuple[str, int]]:
    found: set[tuple[str, int]] = set()
    for skill in SKILLS_WITH_EVALS:
        for case in _load(skill)["evals"]:
            blob = _attached_text(case)
            if not blob:
                continue
            for index, assertion in enumerate(case["assertions"], start=1):
                if any(sid in blob for sid in _SCENARIO_ID_RE.findall(assertion)):
                    found.add((f"{skill}-case-{case['id']}", index))
    return found


def test_the_assertions_answerable_from_the_attached_files_are_the_recorded_ones():
    """Which assertions the inputs give away is a published number, not a footnote."""
    measured = _measured_leaks()
    added = sorted(measured - LEAKED_SCENARIO_ID_ASSERTIONS)
    removed = sorted(LEAKED_SCENARIO_ID_ASSERTIONS - measured)
    assert not added, (
        f"new assertion(s) answerable straight off the attached fixture files: {added}. "
        f"Both arms can read the scenario id out of the fixture's own provenance header, so "
        f"these discriminate nothing between with_skill and without_skill. Either ask for the "
        f"reasoning rather than the label, or add them to LEAKED_SCENARIO_ID_ASSERTIONS and say why."
    )
    assert not removed, (
        f"recorded leak(s) no longer measurable: {removed}. Good news, but the frozen set has to "
        f"shrink with it or it stops describing the corpus."
    )


def test_no_case_is_made_entirely_of_assertions_the_inputs_give_away():
    """A case every assertion of which is readable off its own inputs measures the
    reading comprehension of the agent, not the value of the skill."""
    measured = _measured_leaks()
    for skill in SKILLS_WITH_EVALS:
        for case in _load(skill)["evals"]:
            slug = f"{skill}-case-{case['id']}"
            leaked = {index for eval_slug, index in measured if eval_slug == slug}
            assert len(leaked) < len(case["assertions"]), (
                f"{slug}: all {len(case['assertions'])} assertions are answerable from the "
                f"attached files alone; this case cannot show a with/without delta."
            )


# --------------------------------------------------------------------------- #
# The workspace is committed evidence, not scratch
# --------------------------------------------------------------------------- #

#: The artifacts that must reach git no matter what else is pruned. Two of them do
#: not exist until a run happens, so the check is on the ignore rules and not on
#: the files: a rule that would swallow them is wrong before it ever swallows one.
PUBLISHED_WORKSPACE_ARTIFACTS = (
    "eval/skill-eval-workspace/iteration-1/benchmark.json",
    "eval/skill-eval-workspace/iteration-1/feedback.json",
    "eval/skill-eval-workspace/iteration-1/assertion-review.json",
    "eval/skill-eval-workspace/iteration-1/AST01-case-1/with_skill/grading.json",
    "eval/skill-eval-workspace/iteration-1/AST01-case-1/with_skill/timing.json",
    "eval/skill-eval-workspace/iteration-1/AST01-case-1/with_skill/prompt.txt",
    "eval/skill-eval-workspace/iteration-1/AST01-case-1/with_skill/outputs/response.md",
)


def test_the_eval_workspace_is_not_git_ignored():
    """Committing this evidence was a decision, recorded in .gitignore; this is the
    test that makes reversing it loud.

    `prompt.txt` is in the list on purpose. It is the biggest file in the workspace
    and the obvious thing to prune, and it is the only artifact that lets a reader
    verify AFTER the fact that the two arms differed in exactly one respect.
    """
    import shutil
    import subprocess

    if shutil.which("git") is None:  # pragma: no cover - git is present in CI
        pytest.skip("git unavailable; the ignore rules cannot be interrogated")
    result = subprocess.run(
        ["git", "check-ignore", "-v", *PUBLISHED_WORKSPACE_ARTIFACTS],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0 or not result.stdout.strip(), (
        "an ignore rule now swallows published with/without eval evidence:\n"
        f"{result.stdout.strip()}\n"
        "This repository commits its evidence; see the block at the end of .gitignore."
    )


def test_the_gitignore_states_why_the_workspace_is_committed():
    """The reason travels with the rule, so the next person to want the megabyte back
    meets the argument rather than an unexplained absence."""
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "eval/skill-eval-workspace/ is DELIBERATELY NOT IGNORED" in text
    assert "prompt.txt" in text
