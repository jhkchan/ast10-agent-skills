"""Structural gate on the hand-authored `evals/evals.json`, `evals/regression.json`
and `evals/control.json` case files.

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

THREE CASE FILES, AND WHY THERE ARE NOW THREE
=============================================

`evals/evals.json` is the TUNED set: the cases an iteration reads, argues with,
and edits a `SKILL.md` against. A skill tuned to its own test cases measures
nothing, so a second, disjoint set is needed to tell a real improvement from a
fitted one. That second set is a CONTROL, and a control has exactly one property:
nobody has read it while editing.

`evals/regression.json` USED to be that control, under the name `heldout.json`.
It is not one any more, and the file says so in its own `regression` notice.
Iteration 3 spent it: advisory's case and its four failed assertions were quoted
into the iteration-3 brief as the specification for an advisory fix, and per-skill
deltas from that corpus were published for all eleven skills. A case that steers
an edit can no longer say whether the edit generalised. The cases were kept rather
than deleted, because a spent control is still a working regression suite — a case
a skill used to pass and now fails is a regression, and catching that is worth
running for. What it may never again be called is a control, and
`test_the_regression_notice_does_not_claim_to_be_a_control` is the mechanical half
of that promise.

`evals/control.json` is the control the third iteration authors to replace it: one
case per skill, eleven in total, authored from each `SKILL.md`, its
`coverage-matrix.md` and `scenarios/registry.yaml` rather than from any measured
result, and built out of scenarios and fixtures that neither older corpus feeds.
It is held to the same structural contract as the tuned file (same keys, same case
shape, same "the inputs must not give the answer away" rule) and to four of its
own, below: exactly one case per skill, a machine-readable notice carried in the
file itself, a floor on how many of the eleven have a refusal, a redirect or a
bounded negative as the correct answer, and mechanical proof that no fixture it
attaches is one the tuned or regression corpora already attach. That last one is
the guard the rename of `heldout.json` shows to be necessary: a replacement
control assembled out of the spent one's own inputs would be a control in name
only.

The refusal floor is doctrine, not decoration. Over-conviction is the failure mode
a tuned skill reliably develops, and it has now been observed twice in two
different disguises — iteration 1 found it keyed to INPUT TYPE (a package answered
as though it were a prose claim), iteration 2 found it keyed to SCOPE (a finding
about an MCP server answered as though it were about a skill). Both are one
disease: a verdict produced where the correct answer is a refusal, a redirect, or a
negative with its boundary stated. A control set made only of cases with a finding
in them cannot see that happen, so the floor makes sure this one can.

Unlike `evals.json`, neither `regression.json` nor `control.json` is inside
`scripts/content_hash.py`'s `SURFACE_GLOBS`, and that is a decision rather than an
oversight. The hashed surface binds a judged scorecard to the skill text it
graded; a control set is not skill text, and it is meant to be REPLACED whenever
an iteration compromises it. Re-stamping every skill's `content_hash` each time a
control is swapped would couple a judged block to an artifact that is not the
thing being judged — and this repository has now swapped one, which is exactly the
event that would have made the coupling expensive.
`tests/scripts/test_content_hash.py` pins the surface tuples, so this stays a
stated choice rather than a silent one.
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

#: The three case files a skill's `evals/` directory may carry, and the only three.
#: `TUNED_FILE` is the set an iteration edits against; `CONTROL_FILE` is the blind
#: control that says whether those edits generalised; `REGRESSION_FILE` is the
#: control that used to do that job, spent by iteration 3 and kept for regressions.
TUNED_FILE = "evals.json"
REGRESSION_FILE = "regression.json"
CONTROL_FILE = "control.json"
CASE_FILES = (TUNED_FILE, REGRESSION_FILE, CONTROL_FILE)

#: The two corpora that are one case per skill and carry a notice of their own.
NOTICED_FILES = (REGRESSION_FILE, CONTROL_FILE)

#: The guidance's schema, stated as data so a drifting dialect fails here rather
#: than inside a harness run.
TOP_LEVEL_KEYS = {"skill_name", "evals"}
REQUIRED_CASE_KEYS = {"id", "prompt", "expected_output", "assertions"}
OPTIONAL_CASE_KEYS = {"files"}

#: Each non-tuned corpus carries one key the tuned file does not: the notice that
#: says what the file is for and what using it wrongly costs. The key is named for
#: the file so a reader who opens one cannot mistake it for the other — the two
#: notices say opposite things about whether a number from the file means anything.
#: It is a top-level string rather than a comment because JSON has no comments and
#: a convention nobody can read at parse time is one that gets broken by accident.
NOTICE_KEY = {REGRESSION_FILE: "regression", CONTROL_FILE: "control"}

#: Phrases each notice must carry. Not the whole sentence — the wording may be
#: improved — but the claims that make the file what it is.
#:
#: For the control: it is blind, it must not steer an edit, using it spends it, an
#: iteration that spends it owes a replacement, and — new in iteration 3, because
#: the programme has now burned one control and is on its third corpus — an honest
#: statement of what that costs and the cheaper alternative of rotating part of a
#: corpus rather than replacing all of it.
#:
#: For the regression corpus: what happened to it, what it is now, and where the
#: control that replaced it lives.
NOTICE_CLAIMS = {
    CONTROL_FILE: (
        "BLIND CONTROL",
        "do not tune against",
        "SPENDS this control",
        "replacement",
        "THIRD corpus",
        "rotate a portion",
    ),
    REGRESSION_FILE: (
        "SPENT AS A CONTROL",
        "REGRESSION corpus",
        "not a control",
        "control.json",
    ),
}

#: The claims that made `heldout.json` a control. The regression corpus is not one
#: and its notice may not carry them — a file that still reads like a control is a
#: file a future iteration will treat as one.
RETIRED_CONTROL_CLAIMS = ("HELD OUT", "do not tune against", "held_out")

#: The guidance says start at two to three cases per skill and do not over-invest
#: before the first results are in.
MIN_CASES_PER_SKILL = 2
MAX_CASES_PER_SKILL = 3

#: The control set is one case per skill, deliberately, and the spent one it
#: replaced was built the same way. A control is not a second corpus: widening it
#: turns it into something an iteration is tempted to mine, and the whole of its
#: value is that nobody has read it while editing.
NOTICED_CASES_PER_SKILL = 1

#: An assertion is only useful if a skill-less baseline can plausibly fail it, and
#: one assertion per case cannot express a with/without delta at all.
MIN_ASSERTIONS_PER_CASE = 2

#: The control cases whose CORRECT answer is a refusal, a redirect, or a negative
#: with its boundary stated — no scenario id the evidence supports, a category that
#: belongs to a different AST, a tally that must not move, a verdict a category
#: ships nothing to produce. Recorded by slug rather than inferred, because "is the
#: right answer a refusal" is a property of the case an author knows and a parser
#: does not.
#:
#: Eight of eleven, against a floor of five. The other three convict, and that
#: balance is deliberate: a control made ENTIRELY of refusals stops being able to
#: see the opposite regression, a skill that has learned to decline everything.
CONTROL_REFUSAL_CASES: frozenset[str] = frozenset(
    {
        "AST01-control-case-1",  # refuses an AST01 tally for a check that decides an AST08 scenario
        "AST03-control-case-1",  # refuses a confused-deputy id neither package can decide
        "AST06-control-case-1",  # refuses an AST06 filing for a proxy the registry gives to AST10
        "AST07-control-case-1",  # refuses "not applicable" for a category routed away from
        "AST08-control-case-1",  # refuses a clean write-up built on a suppressed destination
        "AST09-control-case-1",  # refuses an approval finding produced by a failed hash join
        "AST10-control-case-1",  # refuses "signature verified" from a validator that never verified
        "advisory-control-case-1",  # refuses a confirmation date for a hand-off nothing can confirm
    }
)
MIN_CONTROL_REFUSAL_CASES = 5

#: The same ledger for the spent corpus, kept so the property that made it worth
#: running survives the rename.
REGRESSION_REFUSAL_CASES: frozenset[str] = frozenset(
    {
        "AST02-regression-case-1",  # refuses a scenario id for a pin-posture signal
        "AST03-regression-case-1",  # refuses to close an LPCI finding on a green scan
        "AST05-regression-case-1",  # refuses a scenario-level pass over a clean package
        "AST07-regression-case-1",  # refuses a hot-reload verdict from a hash pair
        "AST09-regression-case-1",  # refuses the AST03 reroute and the pending-scan status
        "advisory-regression-case-1",  # refuses to route a finding that is not about a skill
    }
)
MIN_REGRESSION_REFUSAL_CASES = 4

REFUSAL_LEDGER = {
    CONTROL_FILE: (CONTROL_REFUSAL_CASES, MIN_CONTROL_REFUSAL_CASES),
    REGRESSION_FILE: (REGRESSION_REFUSAL_CASES, MIN_REGRESSION_REFUSAL_CASES),
}


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
    control run, a regression run and a tuned run can never land in the same
    directory or the same `feedback.json` key — which is what stops three corpora
    that answer three different questions from being averaged by a reader who
    assumed one workspace held one of them.
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


def _fixture_packages(case: dict) -> set[tuple[str, ...]]:
    """The `fixtures/<category>/<package>` prefixes a case attaches.

    A `files` entry may name the package directory or a file inside it, so the
    first three path components are the unit a "did another corpus already feed
    this?" question is asked in.
    """
    packages: set[tuple[str, ...]] = set()
    for rel in case.get("files") or []:
        parts = Path(rel).parts
        if len(parts) >= 3:
            packages.add(parts[:3])
    return packages


SKILLS_WITH_EVALS = _skills_with_evals()

#: (skill, case) pairs, flattened so a bad case names itself in the test id.
CASES = [
    pytest.param(skill, case, id=f"{skill}-{case.get('id')}")
    for skill in SKILLS_WITH_EVALS
    for case in _load(skill).get("evals", [])
]

#: (skill, case_file, case) triples across ALL THREE files, for the per-case checks
#: that are about a case being runnable at all and so apply to any set.
ALL_CASES = [
    pytest.param(skill, case_file, case, id=f"{skill}-{Path(case_file).stem}-{case.get('id')}")
    for skill in SKILLS_WITH_EVALS
    for case_file in CASE_FILES
    if (SKILLS_DIR / skill / "evals" / case_file).is_file()
    for case in _load(skill, case_file).get("evals", [])
]

#: (skill, case_file, case) triples for the two one-case-per-skill corpora, for the
#: contracts those two share and the tuned file does not.
NOTICED_CASES = [
    pytest.param(skill, case_file, case, id=f"{skill}-{Path(case_file).stem}-{case.get('id')}")
    for skill in SKILLS_WITH_EVALS
    for case_file in NOTICED_FILES
    if (SKILLS_DIR / skill / "evals" / case_file).is_file()
    for case in _load(skill, case_file).get("evals", [])
]

#: Just the blind control's cases, for the contracts that are the control's own.
CONTROL_CASES = [
    pytest.param(skill, case, id=f"{skill}-control-{case.get('id')}")
    for skill in SKILLS_WITH_EVALS
    if (SKILLS_DIR / skill / "evals" / CONTROL_FILE).is_file()
    for case in _load(skill, CONTROL_FILE).get("evals", [])
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
def test_required_skill_ships_a_blind_control_case(skill):
    """Deleting the control is the cheapest way to make an iteration look good.

    A tuned set with no control counterpart cannot distinguish a skill that got
    better from a skill that got fitted, so the file is required in the same way
    the tuned one is: it may be REPLACED — that is what iteration 3 did — and it
    may not be dropped.
    """
    path = SKILLS_DIR / skill / "evals" / CONTROL_FILE
    assert path.is_file(), (
        f"{skill} ships no evals/{CONTROL_FILE}. Without it, nothing in this "
        f"repository can tell an improvement in {skill} from an overfit to its own "
        f"three tuned cases."
    )


@pytest.mark.parametrize("skill", REQUIRED_EVAL_SKILLS)
def test_required_skill_still_ships_the_spent_regression_cases(skill):
    """A spent control is demoted, never deleted.

    The cases still catch a skill going backwards, and deleting them would also
    delete the record that a control was spent — which is the part a later reader
    needs in order to trust the corpus that replaced it.
    """
    path = SKILLS_DIR / skill / "evals" / REGRESSION_FILE
    assert path.is_file(), (
        f"{skill} ships no evals/{REGRESSION_FILE}. These cases stopped being a control "
        f"when iteration 3 tuned against one of them; they did not stop being able to "
        f"catch a regression, and dropping them loses that for nothing."
    )


@pytest.mark.parametrize("skill", REQUIRED_EVAL_SKILLS)
def test_the_retired_heldout_filename_is_gone(skill):
    """The rename is the load-bearing half of retiring a control.

    A file called `heldout.json` reads as a control to every tool and every reader
    that meets it, whatever its contents say. Re-creating one would resurrect the
    ambiguity this iteration paid to remove.
    """
    stale = SKILLS_DIR / skill / "evals" / "heldout.json"
    assert not stale.exists(), (
        f"{stale} is back. The held-out corpus was spent by iteration 3 and retired to "
        f"{REGRESSION_FILE}; a file under the old name will be read as a control again."
    )


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_eval_file_parses_as_json(skill):
    payload = _load(skill)
    assert isinstance(payload, dict), f"{skill}: {TUNED_FILE} must be a JSON object"


@pytest.mark.parametrize("case_file", NOTICED_FILES)
@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_noticed_file_parses_as_json(skill, case_file):
    payload = _load(skill, case_file)
    assert isinstance(payload, dict), f"{skill}: {case_file} must be a JSON object"


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_eval_file_uses_exactly_the_convention_top_level_keys(skill):
    """Convention-compliance is the point; a local dialect defeats it."""
    assert set(_load(skill)) == TOP_LEVEL_KEYS


@pytest.mark.parametrize("case_file", NOTICED_FILES)
@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_noticed_file_uses_the_convention_keys_plus_its_own_notice(skill, case_file):
    """One key of divergence from the tuned schema, and it is the whole reason the
    file can be trusted later: the notice travels inside the artifact, under a key
    named for the corpus so the two cannot be confused at a glance."""
    assert set(_load(skill, case_file)) == TOP_LEVEL_KEYS | {NOTICE_KEY[case_file]}


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


@pytest.mark.parametrize("case_file", NOTICED_FILES)
@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_noticed_skill_name_matches_the_skill_md_frontmatter(skill, case_file):
    assert _load(skill, case_file)["skill_name"] == _skill_md_name(skill)


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_case_count_is_within_the_guidance_band(skill):
    evals = _load(skill)["evals"]
    assert isinstance(evals, list)
    assert MIN_CASES_PER_SKILL <= len(evals) <= MAX_CASES_PER_SKILL, (
        f"{skill}: {len(evals)} cases; the guidance band is "
        f"{MIN_CASES_PER_SKILL}-{MAX_CASES_PER_SKILL} — start small, do not "
        f"over-invest before the first with/without results exist"
    )


@pytest.mark.parametrize("case_file", NOTICED_FILES)
@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_noticed_set_is_exactly_one_case_per_skill(skill, case_file):
    evals = _load(skill, case_file)["evals"]
    assert isinstance(evals, list)
    assert len(evals) == NOTICED_CASES_PER_SKILL, (
        f"{skill}: {len(evals)} case(s) in {case_file}; this corpus is exactly "
        f"{NOTICED_CASES_PER_SKILL} per skill. A larger one is a second corpus, and a "
        f"second corpus is something an iteration eventually mines."
    )


@pytest.mark.parametrize("case_file", NOTICED_FILES)
def test_each_one_case_per_skill_corpus_is_eleven_cases_in_total(case_file):
    """The number a reader of a validation run needs, asserted rather than counted
    by hand: one case for each of the eleven skills."""
    total = sum(len(_load(skill, case_file)["evals"]) for skill in SKILLS_WITH_EVALS)
    assert total == len(REQUIRED_EVAL_SKILLS) == 11, f"{case_file} holds {total} cases, not eleven"


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_case_ids_are_unique_within_a_skill(skill):
    ids = [case["id"] for case in _load(skill)["evals"]]
    assert len(ids) == len(set(ids)), f"{skill}: duplicate case ids in {ids}"


# --------------------------------------------------------------------------- #
# The control's own contract: it says what it is, it can see a refusal, and it
# was not assembled out of the corpus it replaced
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("case_file", NOTICED_FILES)
@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_the_notice_states_what_the_file_is_and_what_misusing_it_costs(skill, case_file):
    """The instruction has to live where the next author will meet it — inside the
    file — not in a commit message nobody reads."""
    notice = _load(skill, case_file)[NOTICE_KEY[case_file]]
    assert isinstance(notice, str) and notice.strip()
    for claim in NOTICE_CLAIMS[case_file]:
        assert claim in notice, (
            f"{skill}/evals/{case_file}: the {NOTICE_KEY[case_file]} notice does not carry "
            f"{claim!r}. It must say what the corpus is, what using it wrongly costs, and — "
            f"for the control — that the iteration which spends it owes a replacement."
        )


@pytest.mark.parametrize("case_file", NOTICED_FILES)
def test_every_file_in_a_corpus_carries_the_same_notice(case_file):
    """Eleven copies of a rule are eleven chances for one of them to be softened."""
    notices = {skill: _load(skill, case_file)[NOTICE_KEY[case_file]] for skill in SKILLS_WITH_EVALS}
    distinct = set(notices.values())
    assert len(distinct) == 1, (
        f"the {NOTICE_KEY[case_file]} notice differs between files: {sorted(notices)} produced "
        f"{len(distinct)} distinct texts. One rule, one wording."
    )


@pytest.mark.parametrize("skill", SKILLS_WITH_EVALS)
def test_the_regression_notice_does_not_claim_to_be_a_control(skill):
    """The retirement has to be legible to a reader who only opens the file.

    A spent corpus that still carries the phrases which made it a control is a
    corpus the next iteration will quote as one. The claims below are exactly the
    ones `heldout.json` used to make, and none of them may survive into the file
    that replaced it.
    """
    notice = _load(skill, REGRESSION_FILE)[NOTICE_KEY[REGRESSION_FILE]]
    surviving = [claim for claim in RETIRED_CONTROL_CLAIMS if claim in notice]
    assert not surviving, (
        f"{skill}/evals/{REGRESSION_FILE}: the notice still carries {surviving}, which is what "
        f"made this corpus a control before iteration 3 spent it. It is a regression suite now, "
        f"and it has to read like one."
    )


@pytest.mark.parametrize("case_file", NOTICED_FILES)
def test_enough_cases_have_a_refusal_or_a_redirect_as_the_right_answer(case_file):
    """A corpus has to be able to see the failure mode tuning actually produces.

    A skill edited against cases that all contain a finding gets better at
    convicting and no better at declining. Iteration 1's regressions were of the
    declining kind keyed to input type, and iteration 2's to scope; both would pass
    unnoticed against a corpus made only of cases with a finding in them.
    """
    recorded, floor = REFUSAL_LEDGER[case_file]
    assert len(recorded) >= floor, (
        f"{len(recorded)} case(s) in {case_file} are recorded as refusal-, redirect- or "
        f"bounded-negative-shaped; the floor is {floor}"
    )
    authored = {
        _slug(skill, case_file, case) for skill in SKILLS_WITH_EVALS for case in _load(skill, case_file)["evals"]
    }
    unknown = sorted(recorded - authored)
    assert not unknown, (
        f"the ledger for {case_file} names {unknown}, which no file authors. "
        f"A refusal floor counted over cases that do not exist is not a floor."
    )


def test_the_control_does_not_consist_only_of_refusals():
    """The floor guards one direction; this guards the other.

    A control every case of which is answered by declining cannot see a skill that
    has over-corrected into refusing findings it ought to convict — which is the
    regression a fix aimed at over-conviction is most likely to introduce.
    """
    authored = {
        _slug(skill, CONTROL_FILE, case) for skill in SKILLS_WITH_EVALS for case in _load(skill, CONTROL_FILE)["evals"]
    }
    convicting = authored - CONTROL_REFUSAL_CASES
    assert convicting, (
        "every control case is recorded as refusal-shaped. A control that only ever "
        "rewards declining measures half the disease."
    )


@pytest.mark.parametrize(("skill", "case"), CONTROL_CASES)
def test_no_control_case_feeds_a_fixture_either_older_corpus_already_feeds(skill, case):
    """A control assembled out of the spent corpus's inputs is a control in name only.

    Checked across ALL skills rather than within one, because the corpora share
    fixture packages freely — several tuned cases hand an agent a package labelled
    for a different category — and a control case that re-runs any already-fed
    package is measuring an input somebody has already looked at.
    """
    already_fed: set[tuple[str, ...]] = set()
    for other in SKILLS_WITH_EVALS:
        for older in (TUNED_FILE, REGRESSION_FILE):
            if not (SKILLS_DIR / other / "evals" / older).is_file():
                continue
            for prior in _load(other, older)["evals"]:
                already_fed |= _fixture_packages(prior)

    reused = sorted("/".join(pkg) for pkg in _fixture_packages(case) & already_fed)
    assert not reused, (
        f"{skill} control case {case['id']} attaches {reused}, which the tuned or regression "
        f"corpus already attaches somewhere. Re-measuring an input an iteration has already read "
        f"cannot tell a generalised skill from a fitted one — pick an unused fixture package, or "
        f"a different shape of input."
    )


# --------------------------------------------------------------------------- #
# Each case is runnable: a real prompt, a stated success condition, real inputs
#
# These are parameterized over ALL_CASES rather than CASES: a control case that
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


@pytest.mark.parametrize(("skill", "case_file", "case"), NOTICED_CASES)
def test_no_one_case_per_skill_corpus_reuses_a_scenario_its_own_tuned_set_feeds(skill, case_file, case):
    """A corpus that re-runs the tuned set's own inputs measures the tuned set.

    The cheapest mechanical half of "test the same competence against a DIFFERENT
    scenario" — do not hand the agent a fixture package this skill's tuned cases
    already hand it — is checked here. The other half, a different register and a
    different question, is an authoring judgement no test can make. The control has
    a stronger version of this above, applied across every skill and both older
    corpora.
    """
    tuned_packages = {pkg for tuned in _load(skill)["evals"] for pkg in _fixture_packages(tuned)}
    reused = sorted("/".join(pkg) for pkg in _fixture_packages(case) & tuned_packages)
    assert not reused, (
        f"{skill} {case_file} case {case['id']} attaches {reused}, which its own tuned "
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

    Scoped to the TUNED file on purpose. The other two corpora are one case per
    skill, so requiring a clean fixture there would force all eleven to be
    clean-package cases and neither would be able to see a missed finding. The
    equivalent guards on that side are the refusal floor and its opposite above,
    which are about the same worry — a skill that convicts everything, or a skill
    that has stopped convicting anything — expressed for a set of eleven single
    cases instead of eleven triples.
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
    """Measured over ALL THREE case files.

    The control and the regression corpus are authored to leak nothing — an
    assertion that asks for a scenario id the attached fixture's own front matter
    prints is exactly the weak discriminator a control cannot afford — so they
    contribute no entries today. Four of the eleven control cases attach a fixture
    package whose header does print its scenario id, and their assertions name the
    reasoning instead. If one ever does leak, the frozen set below has to grow and
    say why, which is the same rule the tuned corpus lives under.
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
