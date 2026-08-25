"""Structural gate on the hand-authored `evals/evals.json` and `evals/heldout.json`
case files.

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

TWO CASE FILES, AND WHY THE SECOND ONE EXISTS
=============================================

`evals/evals.json` is the TUNED set: the cases an iteration reads, argues with,
and edits a `SKILL.md` against. A skill tuned to its own test cases measures
nothing, so a second, disjoint set is needed to tell a real improvement from a
fitted one.

`evals/heldout.json` is that set — one case per skill, eleven in total across the
eleven skills, authored from each `SKILL.md`, its `coverage-matrix.md` and the
whitepaper rather than from any measured result. It is held to the same structural
contract as the tuned file (same keys, same case shape, same "the inputs must not
give the answer away" rule) and to three of its own, below: exactly one case per
skill, a machine-readable `held_out` notice carried in the file itself, and a
floor on how many of the eleven have a refusal or a redirect as the correct
answer. That last one is doctrine, not decoration — over-conviction is the failure
mode a tuned skill is most likely to develop, so the control set has to be able to
see it.

Unlike `evals.json`, `heldout.json` is deliberately OUTSIDE
`scripts/content_hash.py`'s `SURFACE_GLOBS`, and that is a decision rather than an
oversight. The hashed surface binds a judged scorecard to the skill text it
graded; a held-out control set is not skill text, and it is meant to be REPLACED
whenever an iteration compromises it. Re-stamping every skill's `content_hash`
each time a control set is swapped would couple a judged block to an artifact that
is not the thing being judged. `tests/scripts/test_content_hash.py` pins the
surface tuples, so this stays a stated choice rather than a silent one.
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

#: The two case files a skill's `evals/` directory may carry, and the only two.
#: `TUNED_FILE` is the set an iteration edits against; `HELDOUT_FILE` is the
#: control that says whether those edits generalised.
TUNED_FILE = "evals.json"
HELDOUT_FILE = "heldout.json"
CASE_FILES = (TUNED_FILE, HELDOUT_FILE)

#: The guidance's schema, stated as data so a drifting dialect fails here rather
#: than inside a harness run.
TOP_LEVEL_KEYS = {"skill_name", "evals"}
REQUIRED_CASE_KEYS = {"id", "prompt", "expected_output", "assertions"}
OPTIONAL_CASE_KEYS = {"files"}

#: The held-out file carries one key the tuned file does not: the notice that says
#: what the file is for and what using it wrongly costs. It is a top-level string
#: rather than a comment because JSON has no comments and a convention nobody can
#: read at parse time is a convention that gets broken by accident.
HELDOUT_TOP_LEVEL_KEYS = TOP_LEVEL_KEYS | {"held_out"}

#: Phrases the notice must carry. Not the whole sentence — the wording may be
#: improved — but the three claims that make the file a control rather than a
#: second corpus: it is held out, it must not steer an edit, and an iteration that
#: tunes against it owes a replacement.
HELDOUT_NOTICE_CLAIMS = ("HELD OUT", "do not tune against", "replacement")

#: The guidance says start at two to three cases per skill and do not over-invest
#: before the first results are in.
MIN_CASES_PER_SKILL = 2
MAX_CASES_PER_SKILL = 3

#: The held-out set is one case per skill, deliberately. It is a control, not a
#: second corpus: widening it turns it into something an iteration is tempted to
#: mine, and the whole of its value is that nobody has read it while editing.
HELDOUT_CASES_PER_SKILL = 1

#: An assertion is only useful if a skill-less baseline can plausibly fail it, and
#: one assertion per case cannot express a with/without delta at all.
MIN_ASSERTIONS_PER_CASE = 2

#: The held-out cases whose CORRECT answer is a refusal or a redirect — no finding,
#: the wrong input type, a scenario id that may not be assigned, or evidence that
#: does not exist in the artifact. Recorded by slug rather than inferred, because
#: "is the right answer a refusal" is a property of the case an author knows and a
#: parser does not.
#:
#: The floor below it is the point. Iteration 1 measured the largest with/without
#: deltas on exactly these shapes, and over-conviction — a confident category, a
#: manufactured scenario id, a clean bill over a question nobody asked — is what a
#: skill tuned against its own cases is most likely to acquire. A control set made
#: only of cases with a finding in them cannot see that happen.
HELDOUT_REFUSAL_CASES: frozenset[str] = frozenset(
    {
        "AST02-heldout-case-1",  # refuses a scenario id for a pin-posture signal
        "AST03-heldout-case-1",  # refuses to close an LPCI finding on a green scan
        "AST05-heldout-case-1",  # refuses a scenario-level pass over a clean package
        "AST07-heldout-case-1",  # refuses a hot-reload verdict from a hash pair
        "AST09-heldout-case-1",  # refuses the AST03 reroute and the pending-scan status
        "advisory-heldout-case-1",  # refuses to route a finding that is not about a skill
    }
)
MIN_HELDOUT_REFUSAL_CASES = 4


def _skills_with_evals() -> list[str]:
    """Every skill directory that ships an `evals/` directory, discovered on disk.

    Discovered rather than hard-coded so a skill that adds cases is validated the
    moment the file lands, without anybody remembering to widen a tuple here.
    """
    return sorted(d.name for d in SKILLS_DIR.iterdir() if (d / "evals").is_dir())


def _load(skill: str, case_file: str = TUNED_FILE) -> dict:
    path = SKILLS_DIR / skill / "evals" / case_file
    return json.loads(path.read_text(encoding="utf-8"))


def _slug(skill: str, case_file: str, case: dict) -> str:
    """The workspace directory name a run of this case writes into.

    Mirrors `eval/skill_evals.py::EvalCase.slug`: the tuned file keeps the bare
    `AST01-case-1` spelling, and any other case file inserts its own stem, so a
    held-out run and a tuned run can never land in the same directory or the same
    `feedback.json` key.
    """
    stem = Path(case_file).stem
    infix = "" if case_file == TUNED_FILE else f"{stem}-"
    return f"{skill}-{infix}case-{case.get('id')}"


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

#: (skill, case_file, case) triples across BOTH files, for the per-case checks
#: that are about a case being runnable at all and so apply to either set.
ALL_CASES = [
    pytest.param(skill, case_file, case, id=f"{skill}-{Path(case_file).stem}-{case.get('id')}")
    for skill in SKILLS_WITH_EVALS
    for case_file in CASE_FILES
    if (SKILLS_DIR / skill / "evals" / case_file).is_file()
    for case in _load(skill, case_file).get("evals", [])
]

#: Just the held-out ones, for the contract that is the held-out set's own.
HELDOUT_CASES = [
    pytest.param(skill, case, id=f"{skill}-heldout-{case.get('id')}")
    for skill in SKILLS_WITH_EVALS
    if (SKILLS_DIR / skill / "evals" / HELDOUT_FILE).is_file()
    for case in _load(skill, HELDOUT_FILE).get("evals", [])
]


# --------------------------------------------------------------------------- #
# The file exists, parses, and is the shape the convention fixes
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("skill", REQUIRED_EVAL_SKILLS)
def test_required_skill_ships_eval_cases(skill):
    """The authored set may grow; it may not shrink by deletion."""
    path = SKILLS_DIR / skill / "evals" / TUNED_FILE
    assert path.is_file(), (
        f"{skill} is in REQUIRED_EVAL_SKILLS but ships no evals/{TUNED_FILE}. "
        f"With/without evidence for this skill would silently stop being produced."
    )
    assert skill in SKILLS_WITH_EVALS


@pytest.mark.parametrize("skill", REQUIRED_EVAL_SKILLS)
def test_required_skill_ships_a_held_out_case(skill):
    """Deleting the control is the cheapest way to make an iteration look good.

    A tuned set with no held-out counterpart cannot distinguish a skill that got
    better from a skill that got fitted, so the file is required in the same way
    the tuned one is: it may be REPLACED, and it may not be dropped.
    """
    path = SKILLS_DIR / skill / "evals" / HELDOUT_FILE
    assert path.is_file(), (
        f"{skill} ships no evals/{HELDOUT_FILE}. Without it, nothing in this "
        f"repository can tell an improvement in {skill} from an overfit to its own "
        f"three tuned cases."
    )


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_eval_file_parses_as_json(skill):
    payload = _load(skill)
    assert isinstance(payload, dict), f"{skill}: {TUNED_FILE} must be a JSON object"


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_held_out_file_parses_as_json(skill):
    payload = _load(skill, HELDOUT_FILE)
    assert isinstance(payload, dict), f"{skill}: {HELDOUT_FILE} must be a JSON object"


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_eval_file_uses_exactly_the_convention_top_level_keys(skill):
    """Convention-compliance is the point; a local dialect defeats it."""
    assert set(_load(skill)) == TOP_LEVEL_KEYS


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_held_out_file_uses_the_convention_keys_plus_its_own_notice(skill):
    """One key of divergence from the tuned schema, and it is the whole reason the
    file can be trusted later: the notice travels inside the artifact."""
    assert set(_load(skill, HELDOUT_FILE)) == HELDOUT_TOP_LEVEL_KEYS


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_evals_dir_ships_only_the_case_files_and_optional_input_files(skill):
    """`evals/evals.json` is in the hashed surface; a stray sibling is not."""
    evals_dir = SKILLS_DIR / skill / "evals"
    permitted = {*CASE_FILES, "files"}
    stray = sorted(p.relative_to(evals_dir).as_posix() for p in evals_dir.iterdir() if p.name not in permitted)
    assert not stray, f"{skill}/evals/ carries unexpected entries: {stray}"


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_skill_name_matches_the_skill_md_frontmatter(skill):
    """The case file must name the skill it grades, not a directory label."""
    assert _load(skill)["skill_name"] == _skill_md_name(skill)


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_held_out_skill_name_matches_the_skill_md_frontmatter(skill):
    assert _load(skill, HELDOUT_FILE)["skill_name"] == _skill_md_name(skill)


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
def test_held_out_set_is_exactly_one_case_per_skill(skill):
    evals = _load(skill, HELDOUT_FILE)["evals"]
    assert isinstance(evals, list)
    assert len(evals) == HELDOUT_CASES_PER_SKILL, (
        f"{skill}: {len(evals)} held-out case(s); the control set is exactly "
        f"{HELDOUT_CASES_PER_SKILL} per skill. A larger one is a second corpus, and a "
        f"second corpus is something an iteration eventually mines."
    )


def test_the_held_out_set_is_eleven_cases_in_total():
    """The number a reader of a validation run needs, asserted rather than counted
    by hand: one case for each of the eleven skills."""
    total = sum(len(_load(skill, HELDOUT_FILE)["evals"]) for skill in SKILLS_WITH_EVALS)
    assert total == len(REQUIRED_EVAL_SKILLS) == 11, f"the held-out control set holds {total} cases, not eleven"


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_case_ids_are_unique_within_a_skill(skill):
    ids = [case["id"] for case in _load(skill)["evals"]]
    assert len(ids) == len(set(ids)), f"{skill}: duplicate case ids in {ids}"


# --------------------------------------------------------------------------- #
# The held-out set's own contract: it says what it is, and it can see a refusal
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_the_held_out_notice_states_what_the_file_is_and_what_misusing_it_costs(skill):
    """The instruction not to tune against these cases has to live where the next
    author will meet it — inside the file — not in a commit message nobody reads."""
    notice = _load(skill, HELDOUT_FILE)["held_out"]
    assert isinstance(notice, str) and notice.strip()
    for claim in HELDOUT_NOTICE_CLAIMS:
        assert claim in notice, (
            f"{skill}/evals/{HELDOUT_FILE}: the held_out notice does not carry {claim!r}. "
            f"It must say that the cases are held out, that they must not steer a skill "
            f"edit, and that an iteration which tunes against them owes a replacement set."
        )


def test_every_held_out_file_carries_the_same_notice():
    """Eleven copies of a rule are eleven chances for one of them to be softened."""
    notices = {skill: _load(skill, HELDOUT_FILE)["held_out"] for skill in SKILLS_WITH_EVALS}
    distinct = set(notices.values())
    assert len(distinct) == 1, (
        f"the held_out notice differs between files: {sorted(notices)} produced "
        f"{len(distinct)} distinct texts. One rule, one wording."
    )


def test_enough_held_out_cases_have_a_refusal_or_a_redirect_as_the_right_answer():
    """The control has to be able to see the failure mode tuning actually produces.

    A skill edited against cases that all contain a finding gets better at
    convicting and no better at declining, and iteration 1's regressions were all
    of the declining kind — a scenario id invented for a clean artifact, a category
    asserted for the wrong input type. If every held-out case had a finding in it,
    that regression would pass the control unnoticed.
    """
    assert len(HELDOUT_REFUSAL_CASES) >= MIN_HELDOUT_REFUSAL_CASES, (
        f"{len(HELDOUT_REFUSAL_CASES)} held-out case(s) are recorded as refusal- or "
        f"redirect-shaped; the floor is {MIN_HELDOUT_REFUSAL_CASES}"
    )
    authored = {
        _slug(skill, HELDOUT_FILE, case) for skill in SKILLS_WITH_EVALS for case in _load(skill, HELDOUT_FILE)["evals"]
    }
    unknown = sorted(HELDOUT_REFUSAL_CASES - authored)
    assert not unknown, (
        f"HELDOUT_REFUSAL_CASES names {unknown}, which no held-out file authors. "
        f"A refusal floor counted over cases that do not exist is not a floor."
    )


# --------------------------------------------------------------------------- #
# Each case is runnable: a real prompt, a stated success condition, real inputs
#
# These are parameterized over ALL_CASES rather than CASES: a held-out case that
# will not run is worthless in exactly the same way a tuned one is, and the whole
# claim being made about the control set is that it is held to the same contract.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("skill", "case_file", "case"), ALL_CASES)
def test_case_has_exactly_the_convention_keys(skill, case_file, case):
    keys = set(case)
    missing = REQUIRED_CASE_KEYS - keys
    unknown = keys - REQUIRED_CASE_KEYS - OPTIONAL_CASE_KEYS
    assert not missing, f"{skill}/{case_file} case {case.get('id')}: missing {sorted(missing)}"
    assert not unknown, f"{skill}/{case_file} case {case.get('id')}: unknown key(s) {sorted(unknown)}"


@pytest.mark.parametrize(("skill", "case_file", "case"), ALL_CASES)
def test_case_id_is_a_positive_integer(skill, case_file, case):
    assert isinstance(case["id"], int) and not isinstance(case["id"], bool)
    assert case["id"] > 0


@pytest.mark.parametrize(("skill", "case_file", "case"), ALL_CASES)
def test_case_prompt_is_a_realistic_non_empty_message(skill, case_file, case):
    prompt = case["prompt"]
    assert isinstance(prompt, str) and prompt.strip(), "prompt must be a non-empty string"
    assert len(prompt.split()) >= 12, (
        f"{skill}/{case_file} case {case['id']}: prompt is {len(prompt.split())} words. "
        f'"check this skill" is too vague to test anything — name paths, files, context'
    )


@pytest.mark.parametrize(("skill", "case_file", "case"), ALL_CASES)
def test_case_expected_output_is_non_empty(skill, case_file, case):
    expected = case["expected_output"]
    assert isinstance(expected, str) and expected.strip()


@pytest.mark.parametrize(("skill", "case_file", "case"), ALL_CASES)
def test_case_has_at_least_two_assertions(skill, case_file, case):
    assertions = case["assertions"]
    assert isinstance(assertions, list)
    assert len(assertions) >= MIN_ASSERTIONS_PER_CASE, (
        f"{skill}/{case_file} case {case['id']}: {len(assertions)} assertion(s); "
        f"at least {MIN_ASSERTIONS_PER_CASE} required"
    )
    for text in assertions:
        assert isinstance(text, str) and text.strip(), "every assertion must be a non-empty string"


@pytest.mark.parametrize(("skill", "case_file", "case"), ALL_CASES)
def test_case_assertions_are_distinct(skill, case_file, case):
    assertions = case["assertions"]
    assert len(assertions) == len(set(assertions)), (
        f"{skill}/{case_file} case {case['id']}: a repeated assertion double-counts one behaviour"
    )


@pytest.mark.parametrize(("skill", "case_file", "case"), ALL_CASES)
def test_every_referenced_input_file_exists_on_disk(skill, case_file, case):
    """`files` paths are repo-root-relative, and a missing one is a harness failure
    that would be scored as a skill failure."""
    files = case.get("files", [])
    assert isinstance(files, list)
    for rel in files:
        assert isinstance(rel, str) and rel.strip()
        assert not Path(rel).is_absolute(), f"{skill}/{case_file} case {case['id']}: {rel!r} must be repo-relative"
        assert (REPO_ROOT / rel).exists(), (
            f"{skill}/{case_file} case {case['id']}: referenced input {rel!r} does not exist"
        )


@pytest.mark.parametrize(("skill", "case"), HELDOUT_CASES)
def test_no_held_out_case_reuses_a_scenario_the_tuned_set_already_feeds(skill, case):
    """A control that re-runs the tuned set's own inputs is not a control.

    The held-out cases are required to test the same competence against a
    DIFFERENT scenario, so the cheapest mechanical half of that — do not hand the
    agent a fixture package the tuned set already hands it — is checked here. The
    other half, a different register and a different question, is an authoring
    judgement no test can make.
    """
    tuned_packages = {
        Path(rel).parts[:3] for tuned in _load(skill)["evals"] for rel in tuned.get("files", []) if Path(rel).parts
    }
    reused = sorted(
        "/".join(Path(rel).parts[:3]) for rel in case.get("files", []) if Path(rel).parts[:3] in tuned_packages
    )
    assert not reused, (
        f"{skill} held-out case {case['id']} attaches {reused}, which its own tuned "
        f"cases already attach. Re-measuring a tuned input cannot tell a generalised "
        f"skill from a fitted one — pick a different fixture, or a different shape of input."
    )


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
    expose, so every category that HAS a labelled clean package must feed one.

    Scoped to the TUNED file on purpose. The held-out set is one case per skill, so
    requiring a clean fixture there would force all eleven to be clean-package cases
    and the control would stop being able to see a missed finding. The equivalent
    guard on that side is the refusal floor above, which is about the same worry —
    a skill that convicts everything — expressed for a set of eleven single cases
    instead of eleven pairs.
    """
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
#:
#: It shrank from ten entries to three when iteration 1's `passed_in_both` bucket
#: was acted on. Seven of the ten were exactly the assertions that bucket named —
#: "identify the finding as <scenario id>" against a fixture whose own front matter
#: prints that id — and they were deleted rather than reworded, so the leak went
#: with them. The three that remain are not restatements and are not deletable:
#: `AST01-case-1` 1 now also has to scope its negative to the package's bytes, and
#: the other two are `failed_in_both` assertions that name a scenario the signal
#: does NOT establish, which is the claim under test rather than a label read back.
#: `AST08-case-2` moved from index 5 to index 3 because two assertions ahead of it
#: were deleted; it is the same assertion, unedited.
LEAKED_SCENARIO_ID_ASSERTIONS: frozenset[tuple[str, int]] = frozenset(
    {
        ("AST01-case-1", 1),
        ("AST03-case-3", 4),
        ("AST08-case-2", 3),
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
    """Measured over BOTH case files.

    The held-out set is authored to leak nothing — an assertion that asks for a
    scenario id the attached fixture's own front matter prints is exactly the weak
    discriminator a control set cannot afford — so it contributes no entries today.
    If one ever does, the frozen set below has to grow and say why, which is the
    same rule the tuned corpus lives under.
    """
    found: set[tuple[str, int]] = set()
    for skill in SKILLS_WITH_EVALS:
        for case_file in CASE_FILES:
            if not (SKILLS_DIR / skill / "evals" / case_file).is_file():
                continue
            for case in _load(skill, case_file)["evals"]:
                blob = _attached_text(case)
                if not blob:
                    continue
                for index, assertion in enumerate(case["assertions"], start=1):
                    if any(sid in blob for sid in _SCENARIO_ID_RE.findall(assertion)):
                        found.add((_slug(skill, case_file, case), index))
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
        for case_file in CASE_FILES:
            if not (SKILLS_DIR / skill / "evals" / case_file).is_file():
                continue
            for case in _load(skill, case_file)["evals"]:
                slug = _slug(skill, case_file, case)
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
