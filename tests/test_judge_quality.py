"""Tests for the judge-quality diagnostics in `eval/calibration.py`.

Bias tests (`tests/test_calibration.py`) ask whether a judge's number is in the
right place. These ask the prior question: whether the number is a measurement
at all. Run 2 contains a judge that returned exactly 120.0 on all eleven skills
— three distinct values, every one of them a dimension's maximum — and no bias
figure can express that, because +10.8 reads as "lenient" when what happened was
that nothing was ranked.

Four things are held here:

1. **The verdict rule works on judges built to order.** A saturating judge and a
   discriminating one are synthesised from scratch, so the rule is exercised
   against data whose right answer is known independently of the panel that
   motivated it. A judge that is merely coarse — rounds to fives but still ranks
   skills — must come out COARSE and must *not* be flagged, because conflating
   the two would make the flag useless.
2. **The rule lands correctly on the real recorded panels, and the published
   verdicts are a recomputation of them.** No verdict is written down here as a
   constant. Every provider's verdict is recomputed from the corpus and checked
   against `eval/judge-quality.json`, so the artifact cannot disagree with the
   data; and the two claims that carry the argument are pinned to **frozen**
   corpora, from opposite sides. On run 2 (`eval/scorecards-run2/`)
   `bedrock/qwen3-235b` must still come out NON-DISCRIMINATING — the detector
   detects. On run 3 (`eval/scorecards-run3/`), the first corpus scored by the
   rubric-grounded prompt, *nobody* is NON-DISCRIMINATING: the same judge varies
   and ranks. That is the repair, recorded as a result, and the run-2 pin is
   what stops it being mistaken for a relaxed detector.

   Both were once asserted against whichever directory was live, and run 4 is
   why they are not any more. It flags `bedrock/qwen3-235b` again — not by
   going flat, but because the *skills* improved into a judge that puts 77% of
   its scores at a dimension maximum, compressing its per-skill means below the
   across-skill floor. A claim about what one panel measured has to live on that
   panel's frozen directory or it decays into a claim about the newest run. What
   `eval/scorecards/` gets instead is the assertion true of it in any state: the
   published signals are what an independent recount of the same JSON produces,
   and whatever is flagged is named on the dashboard with its reasons.

   The third claim is that the harshest judge on a panel — whoever that is on a
   given run — is never flagged: a rule that flags a strict judge as a broken
   one would be worse than no rule.
3. **Nothing is silently excluded.** A flagged judge stays in every pooled
   figure, `eval/judge-quality.json` says so in words, and the report shows the
   with- and without- columns side by side so the size of the effect is visible
   rather than pre-applied. When a panel has nothing to exclude, it says that
   instead of printing an empty column. Declare and record.
4. **The thresholds are justified rather than fitted.** `MIN_DISTINCT_
   DIMENSION_VALUES` is asserted against the actual band count in the pinned
   rubric, and the vendored maxima table against the rubric's own headings, so
   neither can drift into being a number that only happens to catch one judge.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pytest

from eval import calibration as cal

REPO_ROOT = Path(__file__).resolve().parents[1]
CALIBRATION_PY = REPO_ROOT / "eval" / "calibration.py"
DASHBOARD = REPO_ROOT / "docs" / "skill-judge-dashboard.md"
SCORECARDS = REPO_ROOT / "eval" / "scorecards"
#: Run 2, archived and frozen: the corpus in which the flat judge is on record.
#: Nothing writes here, which is what makes it usable as a fixed point — the
#: detector's behaviour on it can only change if the detector changes.
SCORECARDS_RUN2 = REPO_ROOT / "eval" / "scorecards-run2"
#: Run 3, archived and frozen: the corpus in which the *repaired* judge is on
#: record. Both halves of "the prompt fix repaired the judge" now live on frozen
#: corpora, so neither half can be un-made by a later run. It was the live corpus
#: when that finding was written, and the finding started degrading the moment
#: run 4 landed — a claim about a specific measurement belongs on the directory
#: holding that measurement, not on whichever directory is current.
SCORECARDS_RUN3 = REPO_ROOT / "eval" / "scorecards-run3"
JUDGE_QUALITY_JSON = REPO_ROOT / "eval" / "judge-quality.json"
RUBRIC = REPO_ROOT / "vendor" / "skill-judge" / "SKILL.md"

QWEN = "bedrock/qwen3-235b"

MAXIMA = cal.FALLBACK_DIMENSION_MAXIMA


def _flat(path: Path) -> str:
    """File text with U+2212 folded to ASCII and whitespace collapsed."""
    return " ".join(path.read_text(encoding="utf-8").replace("−", "-").split())


# ---------------------------------------------------------------------------
# Synthetic judges, built so the right answer is known before the rule runs
# ---------------------------------------------------------------------------

SKILLS = [f"S{n}" for n in range(1, 7)]
ROUNDS = 3


def _write_corpus(directory: Path, judges: dict[str, object]) -> Path:
    """One scorecard per skill; every judge scores every skill every round.

    ``judges`` maps a provider name to ``f(skill_index, round_index) -> scores``.
    """
    directory.mkdir(parents=True, exist_ok=True)
    for index, skill in enumerate(SKILLS):
        rows = []
        for round_index in range(ROUNDS):
            for provider, score_fn in judges.items():
                scores = score_fn(index, round_index)  # type: ignore[operator]
                rows.append({"provider": provider, "scores": scores, "total": float(sum(scores.values()))})
        (directory / f"{skill}.json").write_text(
            json.dumps({"skill": skill, "judgments": rows}, indent=2), encoding="utf-8"
        )
    return directory


def _saturating(_skill: int, _round: int) -> dict[str, float]:
    """Every dimension at its maximum, on every skill, every round."""
    return {d: float(m) for d, m in MAXIMA.items()}


def _discriminating(skill: int, round_index: int) -> dict[str, float]:
    """Ranks the skills, uses the interior of every band, rarely lands on a five."""
    offsets = [-4, -2, -1, 1, 2, 4]
    shift = offsets[skill % len(offsets)] + (1 if round_index == 2 else 0)
    base = {"D1": 16, "D2": 12, "D3": 11, "D4": 13, "D5": 12, "D6": 11, "D7": 7, "D8": 12}
    return {d: float(max(0, min(MAXIMA[d], v + shift))) for d, v in base.items()}


def _coarse_but_ranking(skill: int, _round: int) -> dict[str, float]:
    """Ranks the skills, but reports the ranking in multiples of five only."""
    step = [0, 5, 5, 10, 10, 15][skill % 6]
    base = {"D1": 5, "D2": 5, "D3": 5, "D4": 5, "D5": 5, "D6": 5, "D7": 0, "D8": 5}
    return {d: float(min(MAXIMA[d], v + step)) for d, v in base.items()}


def _constant_but_unsaturated(_skill: int, _round: int) -> dict[str, float]:
    """The same mid-scale profile for everything — flat without ever touching a ceiling."""
    return {"D1": 14.0, "D2": 11.0, "D3": 12.0, "D4": 13.0, "D5": 11.0, "D6": 12.0, "D7": 7.0, "D8": 11.0}


@pytest.fixture()
def synthetic(tmp_path):
    directory = _write_corpus(
        tmp_path / "cards",
        {
            "fake/saturator": _saturating,
            "fake/grader": _discriminating,
            "fake/rounder": _coarse_but_ranking,
            "fake/metronome": _constant_but_unsaturated,
        },
    )
    rows = cal.provider_quality(cal.load_judgments(directory), MAXIMA)
    return {row["provider"]: row for row in rows}


def test_a_saturating_judge_is_flagged_non_discriminating(synthetic):
    row = synthetic["fake/saturator"]
    assert row["verdict"] == cal.VERDICT_NON_DISCRIMINATING
    assert row["discrimination"]["across_skill_sd"] == 0.0
    assert row["discrimination"]["distinct_dimension_values"] == len(set(MAXIMA.values()))
    assert row["saturation"]["dimension_max_rate"] == 1.0
    assert row["saturation"]["full_total_rate"] == 1.0
    assert row["granularity"]["multiple_of_five_rate"] == 1.0


def test_a_discriminating_judge_is_not_flagged(synthetic):
    row = synthetic["fake/grader"]
    assert row["verdict"] == cal.VERDICT_DISCRIMINATING
    assert row["reasons"] == []
    assert row["discrimination"]["across_skill_sd"] >= cal.DISCRIMINATION_SD_FLOOR
    assert row["discrimination"]["across_skill_variance"] > 0
    assert row["granularity"]["multiple_of_five_rate"] < cal.GRANULARITY_CEILING
    assert row["saturation"]["dimension_max_rate"] < cal.SATURATION_DIM_MAX_CEILING


def test_a_coarse_judge_that_still_ranks_is_recorded_but_not_flagged(synthetic):
    """COARSE and NON-DISCRIMINATING must not collapse into each other.

    This judge rounds every score to a multiple of five — a real defect, and the
    rule says so — but its per-skill means genuinely separate the six skills. It
    is ranking; it is just ranking coarsely. Flagging it would make the flag
    mean "I disapprove of this judge" rather than "this judge ranked nothing".
    """
    row = synthetic["fake/rounder"]
    assert row["verdict"] == cal.VERDICT_COARSE
    assert row["granularity"]["multiple_of_five_rate"] == 1.0
    assert row["discrimination"]["across_skill_sd"] >= cal.DISCRIMINATION_SD_FLOOR
    assert any("multiples of 5" in reason for reason in row["reasons"])
    assert cal.flagged_providers(list(synthetic.values())) == ["fake/metronome", "fake/saturator"]


def test_a_flat_judge_is_flagged_even_though_it_never_saturates(synthetic):
    """Discrimination decides the verdict on its own.

    `fake/metronome` returns a mid-scale profile — no maximum, no full total,
    12.5% multiples of five — and repeats it for every skill. Saturation is the
    mechanism by which the recorded panel's flat judge went flat; it is not the
    definition. A rule that required saturation would miss this one entirely.
    """
    row = synthetic["fake/metronome"]
    assert row["verdict"] == cal.VERDICT_NON_DISCRIMINATING
    assert row["saturation"]["dimension_max_rate"] == 0.0
    assert row["saturation"]["full_total_rate"] == 0.0
    assert row["granularity"]["multiple_of_five_rate"] < cal.GRANULARITY_CEILING
    assert any("across-skill sd" in reason for reason in row["reasons"])


def test_one_skill_is_insufficient_data_rather_than_a_verdict(tmp_path):
    """A judge that saw one skill cannot be accused of not ranking them."""
    (tmp_path / "S1.json").write_text(
        json.dumps(
            {
                "skill": "S1",
                "judgments": [{"provider": "fake/once", "scores": _saturating(0, 0), "total": 120.0}] * 3,
            }
        ),
        encoding="utf-8",
    )
    row = cal.provider_quality(cal.load_judgments(tmp_path), MAXIMA)[0]
    assert row["verdict"] == cal.VERDICT_INSUFFICIENT_DATA
    assert cal.flagged_providers([row]) == []


def test_a_totals_only_corpus_reports_absent_signals_as_absent(tmp_path):
    """No dimension scores recorded is not the same as "never rounded to five"."""
    for index, skill in enumerate(SKILLS):
        (tmp_path / f"{skill}.json").write_text(
            json.dumps(
                {
                    "skill": skill,
                    "judgments": [
                        {"provider": "fake/totals", "total": 100.0 + index},
                        {"provider": "fake/flat", "total": 110.0},
                    ],
                }
            ),
            encoding="utf-8",
        )
    rows = {r["provider"]: r for r in cal.provider_quality(cal.load_judgments(tmp_path), MAXIMA)}
    assert rows["fake/totals"]["granularity"]["multiple_of_five_rate"] is None
    assert rows["fake/totals"]["saturation"]["dimension_max_rate"] is None
    assert rows["fake/totals"]["discrimination"]["distinct_dimension_values"] is None
    # Totals alone are still enough to answer the discrimination question.
    assert rows["fake/totals"]["verdict"] == cal.VERDICT_DISCRIMINATING
    assert rows["fake/flat"]["verdict"] == cal.VERDICT_NON_DISCRIMINATING


def test_a_corrupt_scores_block_is_refused_rather_than_read_as_absent(tmp_path):
    (tmp_path / "S1.json").write_text(
        json.dumps({"skill": "S1", "judgments": [{"provider": "p", "total": 100.0, "scores": {"D1": "high"}}]}),
        encoding="utf-8",
    )
    with pytest.raises(cal.ScorecardError):
        cal.load_judgments(tmp_path)


# ---------------------------------------------------------------------------
# The real recorded panel
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def recorded():
    rows = cal.load_judgments(SCORECARDS)
    if not rows:
        pytest.skip("no scorecards recorded — nothing to diagnose")
    return rows


@pytest.fixture(scope="module")
def quality(recorded):
    return cal.judge_quality(recorded)


@pytest.fixture(scope="module")
def archived_run2():
    """The frozen run-2 panel, diagnosed by today's rule.

    Not skipped when absent. `eval/scorecards-run2/` is committed history, and a
    missing one means the fixed point these tests measure the detector against
    has been deleted — which is a failure, not a reason to stay quiet.
    """
    assert SCORECARDS_RUN2.is_dir() and any(SCORECARDS_RUN2.glob("*.json")), (
        f"{SCORECARDS_RUN2.relative_to(REPO_ROOT)} is the archived run-2 corpus and must stay committed: "
        "it is what pins that the NON-DISCRIMINATING rule still fires on the judge it was built for"
    )
    return cal.judge_quality(cal.load_judgments(SCORECARDS_RUN2))


@pytest.fixture(scope="module")
def archived_run3():
    """The frozen run-3 panel, diagnosed by today's rule.

    The other fixed point. Run 2 pins that the rule fires on a flat judge; run 3
    pins that the same rule, unmodified, clears a panel where nobody is flat.
    Not skipped when absent, for the same reason run 2 is not.
    """
    assert SCORECARDS_RUN3.is_dir() and any(SCORECARDS_RUN3.glob("*.json")), (
        f"{SCORECARDS_RUN3.relative_to(REPO_ROOT)} is the archived run-3 corpus and must stay committed: "
        "it is what pins that the NON-DISCRIMINATING rule clears a panel it has nothing against"
    )
    return cal.judge_quality(cal.load_judgments(SCORECARDS_RUN3))


def _row(quality: dict, provider: str) -> dict:
    return next(r for r in quality["providers"] if r["provider"] == provider)


#: The three recorded panels a corpus-parametrised test can run against, as
#: ``(directory, diagnosed panel)``. Named "current" rather than by a run number
#: on purpose: `eval/scorecards/` is whichever run is live, and labelling that
#: parameter "run3" is exactly the drift this file exists to catch — it went on
#: reading "run3" for a whole run after the directory held run 4.
def _corpus(name: str, quality: dict, archived_run2: dict, archived_run3: dict) -> tuple[Path, dict]:
    return {
        "current": (SCORECARDS, quality),
        "run3": (SCORECARDS_RUN3, archived_run3),
        "run2": (SCORECARDS_RUN2, archived_run2),
    }[name]


def _signals_from_disk(directory: Path, provider: str) -> dict[str, object]:
    """One judge's four signals, recomputed straight out of the scorecard files.

    A second opinion on `eval/calibration.py`, in the same spirit as the rubric
    re-slice in `tests/scripts/test_judge_harness.py`: a test that only asked the
    module under test what it measured would agree just as happily with a
    provider_quality() that had lost a scorecard or divided by the wrong count.
    """
    totals: dict[str, list[float]] = defaultdict(list)
    dimension_scores: list[tuple[str, float]] = []
    for card in sorted(directory.glob("*.json")):
        payload = json.loads(card.read_text(encoding="utf-8"))
        for judgment in payload.get("judgments") or []:
            if judgment.get("provider") != provider:
                continue
            totals[payload["skill"]].append(float(judgment["total"]))
            dimension_scores.extend((d, float(v)) for d, v in (judgment.get("scores") or {}).items())
    flat_totals = [t for values in totals.values() for t in values]
    assert flat_totals and dimension_scores, f"{provider} cast no recorded judgments in {directory.name}"
    skill_means = [statistics.fmean(values) for values in totals.values()]
    n_dimension = len(dimension_scores)
    return {
        "n_judgments": len(flat_totals),
        "n_skills": len(totals),
        "dimension_values": sorted({v for _, v in dimension_scores}),
        "distinct_dimension_values": len({v for _, v in dimension_scores}),
        "across_skill_sd": round(statistics.pstdev(skill_means), 2),
        "skill_mean_min": round(min(skill_means), 1),
        "skill_mean_max": round(max(skill_means), 1),
        "multiple_of_five_rate": round(sum(1 for _, v in dimension_scores if v % 5 == 0) / n_dimension, 3),
        "dimension_max_rate": round(sum(1 for d, v in dimension_scores if v >= MAXIMA[d]) / n_dimension, 3),
        "full_total_rate": round(sum(1 for t in flat_totals if t >= sum(MAXIMA.values())) / len(flat_totals), 3),
    }


def _measured(row: dict) -> dict[str, object]:
    """The same signals, as `eval/calibration.py` published them."""
    disc, gran, sat = row["discrimination"], row["granularity"], row["saturation"]
    return {
        "n_judgments": row["n_judgments"],
        "n_skills": row["n_skills"],
        "dimension_values": disc["dimension_values"],
        "distinct_dimension_values": disc["distinct_dimension_values"],
        "across_skill_sd": disc["across_skill_sd"],
        "skill_mean_min": disc["skill_mean_min"],
        "skill_mean_max": disc["skill_mean_max"],
        "multiple_of_five_rate": gran["multiple_of_five_rate"],
        "dimension_max_rate": sat["dimension_max_rate"],
        "full_total_rate": sat["full_total_rate"],
    }


def test_the_published_verdicts_are_a_recomputation_of_the_recorded_corpus(quality):
    """No verdict in this repository is a constant anybody typed.

    This replaces an assertion that `eval/judge-quality.json` flags exactly
    `bedrock/qwen3-235b`. That was true of run 2 and false of run 3, and it was
    brittle in the way the thing it guards is brittle: a hard-coded verdict has
    to be edited whenever the measurement moves, and the edit is indistinguish-
    able from someone quietly making a failure go away. What is asserted instead
    is the invariant — for *every* provider, the published verdict, its reasons
    and the signals behind it are exactly what recomputing from
    `eval/scorecards/` produces — so the artifact can never disagree with the
    data, whatever the data says next time.
    """
    published = json.loads(JUDGE_QUALITY_JSON.read_text(encoding="utf-8"))
    recomputed = {row["provider"]: row for row in cal.provider_quality(cal.load_judgments(SCORECARDS))}

    assert {row["provider"] for row in published["providers"]} == set(recomputed), (
        "eval/judge-quality.json names a different panel than eval/scorecards/ contains"
    )
    for row in published["providers"]:
        provider = row["provider"]
        expected = recomputed[provider]
        assert row["verdict"] == expected["verdict"], (
            f"{provider}: eval/judge-quality.json publishes {row['verdict']} but the recorded scorecards "
            f"produce {expected['verdict']} — re-run `python3 eval/calibration.py`"
        )
        assert row["reasons"] == expected["reasons"], f"{provider}: published reasons are not the measured ones"
        for block in ("discrimination", "granularity", "saturation", "self_consistency"):
            assert row[block] == expected[block], f"{provider}: published {block} signals are not the measured ones"

    # The flag list is a projection of the rows, not a separate claim: it must be
    # derivable from the published rows *and* agree with the recomputation.
    assert published["flagged"] == cal.flagged_providers(published["providers"])
    assert published["flagged"] == cal.flagged_providers(list(recomputed.values())) == quality["flagged"]


def test_no_judge_on_the_frozen_run_3_panel_is_non_discriminating(archived_run3):
    """A result, not a regression — and deliberately asserted rather than assumed.

    Under the pre-2026-08-23 prompt `bedrock/qwen3-235b` returned exactly 120.0
    on all eleven skills from three distinct values, and this file's central
    assertion was that it got flagged. Run 3 sent the judges the rubric's own
    score bands, and that judge varied across skills and ranked them: it came out
    COARSE, and that panel has no NON-DISCRIMINATING judge at all. The fix
    repaired the broken judge; the flag did not go soft.

    This was written against `eval/scorecards/` while run 3 was the live corpus,
    and run 4 broke it — not because the rule went soft but because the *skills*
    improved into `bedrock/qwen3-235b`'s ceiling and compressed its across-skill
    spread below the floor (see the test below). A claim about what one panel
    measured belongs on that panel's frozen directory, where it is permanent.
    Both of this file's load-bearing claims are now pinned to archives: run 2
    must still produce the flag, run 3 must still not, and neither can be
    disturbed by whatever the next live run says.
    """
    verdicts = {row["provider"]: row["verdict"] for row in archived_run3["providers"]}
    assert cal.VERDICT_NON_DISCRIMINATING not in verdicts.values(), (
        f"a judge on the run-3 panel is returning no ranking information: {verdicts}"
    )
    assert archived_run3["flagged"] == []
    # Every judge still has to have been *examined* — an empty flag list is only
    # meaningful if the rule actually ran on all of them.
    assert len(verdicts) == len({j.provider for j in cal.load_judgments(SCORECARDS_RUN3)})
    assert all(verdict in archived_run3["verdicts"] for verdict in verdicts.values())


def test_the_live_panels_flag_state_is_published_with_every_reason(quality):
    """Whatever the live panel measures, the dashboard says it — in either state.

    The pair above pins the rule's behaviour on two frozen corpora. This is the
    forward-facing half: it makes no claim about *which* judges are flagged on
    `eval/scorecards/`, only that the page a reader opens agrees with the file
    the tool wrote, reason for reason. A flag that is measured and not published
    is worse than no diagnostic, and so is a page that goes on describing a clean
    panel after one stops being clean — which is exactly what run 4 would have
    done here if the only assertion in this file had been "nobody is flagged".
    """
    flat = _flat(DASHBOARD)
    for provider in quality["flagged"]:
        row = _row(quality, provider)
        assert row["verdict"] == cal.VERDICT_NON_DISCRIMINATING
        assert row["reasons"], f"{provider} is flagged with no recorded reason"
        assert f"`{provider}`" in flat, f"the dashboard does not name the flagged judge {provider}"
        assert cal.VERDICT_NON_DISCRIMINATING in flat
        for signal in ("across_skill_sd", "skill_mean_min", "skill_mean_max"):
            value = row["discrimination"][signal]
            assert f"{value:g}" in flat, (
                f"{provider} is flagged on its across-skill spread; the dashboard must publish "
                f"{signal} = {value:g} so a reader can see why"
            )
    if not quality["flagged"]:
        assert "nothing to exclude" in _flat(DASHBOARD).lower(), (
            "a clean live panel must say so on the page rather than leaving the reader to assume"
        )
    # And whatever the state, every judge was examined and got a known verdict.
    verdicts = {row["provider"]: row["verdict"] for row in quality["providers"]}
    assert len(verdicts) == len({j.provider for j in cal.load_judgments(SCORECARDS)})
    assert all(verdict in quality["verdicts"] for verdict in verdicts.values())


def test_the_rule_still_flags_the_archived_run_2_judge(archived_run2):
    """The detector detects: the same rule, on the corpus that motivated it.

    This is the load-bearing half of the pair above. `eval/scorecards-run2/` is
    frozen, so this assertion can only break by someone loosening the rule —
    which is exactly the change that "nobody is flagged in run 3" would
    otherwise be able to hide.
    """
    assert archived_run2["flagged"] == [QWEN], "the run-2 flat judge must still be flagged, and no one else with it"
    assert _row(archived_run2, QWEN)["verdict"] == cal.VERDICT_NON_DISCRIMINATING


def test_the_qwen_signals_are_recomputed_from_disk_on_every_corpus(quality, archived_run2, archived_run3):
    """The measurement that motivated all of this, and the one that closed it.

    Every side is recomputed from the scorecard files rather than transcribed:
    the run-2 numbers (three distinct values, zero across-skill sd, every
    judgment at the full 120) are re-derived, not quoted, and the run-3 numbers
    are never written down at all — what is asserted about them is which side of
    the *published thresholds* they fall on. So the pair keeps working when the
    next run moves the figures again, and it states the finding precisely: the
    same judge crossed both discrimination thresholds when the prompt changed.

    The run-3 half is asserted against the frozen archive, not the live corpus,
    because it is a claim about the run that repaired the judge. The live corpus
    gets the assertion that is true of it in any state — that
    `eval/calibration.py`'s published signals are the ones a second, independent
    pass over the same JSON produces.
    """
    run2, run3 = _row(archived_run2, QWEN), _row(archived_run3, QWEN)
    assert _measured(run2) == _signals_from_disk(SCORECARDS_RUN2, QWEN)
    assert _measured(run3) == _signals_from_disk(SCORECARDS_RUN3, QWEN)
    assert _measured(_row(quality, QWEN)) == _signals_from_disk(SCORECARDS, QWEN)

    # Run 2: below both thresholds, in the two ways the rule cares about.
    r2 = run2["discrimination"]
    assert r2["distinct_dimension_values"] < cal.MIN_DISTINCT_DIMENSION_VALUES
    assert r2["across_skill_sd"] < cal.DISCRIMINATION_SD_FLOOR
    assert r2["skill_mean_min"] == r2["skill_mean_max"], "run 2's flat judge placed every skill on one number"
    assert run2["saturation"]["full_total_rate"] >= cal.SATURATION_FULL_TOTAL_CEILING

    # Run 3: above both, and separating the skills it was given.
    r3 = run3["discrimination"]
    assert r3["distinct_dimension_values"] >= cal.MIN_DISTINCT_DIMENSION_VALUES
    assert r3["across_skill_sd"] >= cal.DISCRIMINATION_SD_FLOOR
    assert r3["skill_mean_min"] < r3["skill_mean_max"], "run 3's qwen must rank the skills, not repeat one total"
    assert run3["verdict"] != cal.VERDICT_NON_DISCRIMINATING
    assert QWEN not in archived_run3["flagged"]


def test_a_saturating_judge_can_be_flagged_by_the_population_narrowing_under_it(quality, archived_run3):
    """Run 4's finding, stated as the mechanism rather than as a verdict.

    `bedrock/qwen3-235b` clears the distinct-value threshold on both corpora and
    ranks the roster on both, yet run 4 flags it. The reason is not that the
    judge degraded: it puts most of its dimension scores at a dimension's
    maximum, so it has very little room above a roster, and when the skills
    improved into that ceiling its per-skill means compressed. This asserts the
    mechanism is what the numbers actually show — a judge still ranking, still
    using enough of the scale, whose across-skill spread narrowed because its
    ceiling did not move with the population.

    Written as a conditional on the live corpus rather than as "qwen is flagged",
    because pinning the flag would make a future repair look like a regression.
    What must never happen silently is the *other* reading: a judge flagged here
    while the panel's own numbers say it collapsed to one value.
    """
    live = _row(quality, QWEN)
    if QWEN not in quality["flagged"]:
        pytest.skip("the live panel does not flag this judge; the mechanism has nothing to describe")

    disc, frozen = live["discrimination"], archived_run3["providers"]
    before = next(r for r in frozen if r["provider"] == QWEN)["discrimination"]

    assert disc["across_skill_sd"] < cal.DISCRIMINATION_SD_FLOOR, "the flag must be the across-skill one"
    assert disc["distinct_dimension_values"] >= cal.MIN_DISTINCT_DIMENSION_VALUES, (
        "a judge flagged on spread alone must still be using more values than one dimension has bands — "
        "if it is not, this is the flat pathology and not the compression one"
    )
    assert disc["skill_mean_min"] < disc["skill_mean_max"], "a compressed ranking is still a ranking"
    assert live["saturation"]["dimension_max_rate"] >= cal.SATURATION_DIM_MAX_CEILING, (
        "compression against a ceiling is only the explanation for a judge that sits at the ceiling"
    )
    assert disc["skill_mean_min"] > before["skill_mean_min"], (
        "the mechanism is the roster rising into a fixed ceiling: this judge's worst-scored skill "
        f"must have risen since run 3 ({before['skill_mean_min']} -> {disc['skill_mean_min']})"
    )


def test_every_judge_on_the_panel_gets_a_verdict(quality, recorded):
    named = {row["provider"] for row in quality["providers"]}
    assert named == {j.provider for j in recorded}
    assert all(row["verdict"] in quality["verdicts"] for row in quality["providers"])


@pytest.mark.parametrize("corpus", ["current", "run3", "run2"])
def test_the_harshest_judge_on_the_panel_is_never_flagged(corpus, quality, archived_run2, archived_run3):
    """A strict judge is a judge, not a defect.

    This used to name `claude-cli/sonnet` and quote its −3.7 bias. Sonnet is not
    the harshest judge on run 3 — `bedrock/gpt-oss-120b` is, at a bias the panel
    computes — so the test had stopped exercising the claim its docstring makes.
    The judge is now *found* rather than named: whoever sits lowest against the
    pooled mean on a given corpus must come out DISCRIMINATING with no reasons
    against it. If the rule could not tell a harsh grader apart from a judge
    returning 120.0 eleven times, it would be measuring severity and calling it
    quality — and that failure would now be caught on whichever judge is harsh
    next run, not only on the one that was harsh when this was written.
    """
    directory, panel = _corpus(corpus, quality, archived_run2, archived_run3)
    biases = cal.provider_bias(cal.load_judgments(directory))
    harshest = min(biases, key=lambda r: r["bias"])
    row = _row(panel, harshest["provider"])
    assert harshest["bias"] < 0, "the harshest judge must actually sit below the pooled mean"
    assert row["verdict"] == cal.VERDICT_DISCRIMINATING, (
        f"{corpus}: the harshest judge ({harshest['provider']}, bias {harshest['bias']:+.1f}) is flagged "
        f"{row['verdict']} — the rule is reading severity as a defect"
    )
    assert row["reasons"] == []
    assert harshest["provider"] not in panel["flagged"]


@pytest.mark.parametrize("corpus", ["current", "run3", "run2"])
def test_granularity_across_the_panel_is_measured_not_asserted(corpus, quality, archived_run2, archived_run3):
    """Every published granularity figure is re-derived from the scorecards here.

    The old form hard-coded run 2's two extremes (100% for qwen, 0% for sonnet)
    and so had to be edited the moment the prompt changed them. What actually
    matters is that the figure is a measurement and that it separates judges on
    one rubric, and both are now checked against the files: every provider's
    published rate equals a from-disk recount, the panel's spread is wider than
    the chance rate the ceiling is justified against, and the coarsest judge is
    identified rather than assumed.
    """
    directory, panel = _corpus(corpus, quality, archived_run2, archived_run3)
    rates = {r["provider"]: r["granularity"]["multiple_of_five_rate"] for r in panel["providers"]}
    assert all(rate is not None for rate in rates.values()), "a rate of None is an unrecorded signal, not a zero"

    for provider, rate in rates.items():
        assert rate == _signals_from_disk(directory, provider)["multiple_of_five_rate"], (
            f"{corpus}: the published multiple-of-five rate for {provider} is not what the scorecards say"
        )

    chance = cal.multiple_of_five_chance_rate(MAXIMA)
    assert max(rates.values()) - min(rates.values()) > chance, (
        f"{corpus}: judges on one rubric span {min(rates.values()):.0%}-{max(rates.values()):.0%}, "
        f"less than the {chance:.0%} chance rate — the signal would not be separating anyone"
    )
    assert max(rates, key=lambda p: rates[p]) == QWEN, (
        f"{corpus}: the coarsest judge on the panel is no longer {QWEN}; the granularity narrative "
        "on the dashboard and in ADR-0005 is about that judge and needs rewriting"
    )


# ---------------------------------------------------------------------------
# Declare and record: flagged is not excluded
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("corpus", ["current", "run3", "run2"])
def test_the_exclusion_block_agrees_with_the_flag_list(corpus, quality, archived_run2, archived_run3):
    """The exclusion block is a function of who is flagged, on any panel.

    The old form asserted both columns unconditionally, which only held while
    some judge was flagged; on run 3 nobody is, and it fell over on a `None`
    rather than on a claim. Both states are now checked, and against real
    corpora rather than only synthetic ones: run 2 exercises the two-column
    path — including the delta arithmetic, which the old test named in its title
    but only half-checked — and run 3 exercises the path where the honest output
    is a sentence instead of a column.
    """
    panel = _corpus(corpus, quality, archived_run2, archived_run3)[1]
    exclusion = panel["exclusion"]
    with_flagged, without_flagged = exclusion["with_flagged"], exclusion["without_flagged"]

    assert exclusion["flagged"] == panel["flagged"]
    assert with_flagged is not None, "the unfiltered column is the panel itself and always exists"
    assert with_flagged["providers"] == sorted(r["provider"] for r in panel["providers"])

    if not panel["flagged"]:
        assert without_flagged is None, "a panel with nothing to exclude must not print an exclusion column"
        assert exclusion["delta"] is None
        assert "nothing to exclude" in exclusion["note"].lower()
        return

    assert without_flagged is not None
    assert with_flagged["n_judgments"] > without_flagged["n_judgments"]
    for flagged in panel["flagged"]:
        assert flagged in with_flagged["providers"]
        assert flagged not in without_flagged["providers"]
    delta = exclusion["delta"]
    for key in ("n_judgments", "pooled_mean", "bias_spread", "sigma_min", "sigma_max", "sigma_median"):
        assert delta[key] == round(without_flagged[key] - with_flagged[key], 2), f"{corpus}: {key} delta is not the gap"
    assert delta["sigma_median"] < 0, "dropping a flat judge must visibly narrow the panel"


def test_the_flagged_judge_is_still_in_every_pooled_figure(recorded, quality):
    """The point of the whole design: the evidence is published, the pool is untouched."""
    full = cal.panel_summary(recorded)
    assert full["n_providers"] == len(quality["providers"])
    assert full["pooled_mean"] == quality["exclusion"]["with_flagged"]["pooled_mean"]
    assert full["n_judgments"] == quality["exclusion"]["with_flagged"]["n_judgments"]


@pytest.mark.parametrize("corpus", ["current", "run3", "run2"])
def test_the_exclusion_note_says_the_decision_is_a_human_one(corpus, quality, archived_run2, archived_run3):
    """Whichever note a panel produces, it must say the true thing for that panel.

    Both branches are pinned against real corpora rather than only synthetic
    ones, and both are pinned permanently: run 2 has a flagged judge and always
    will, run 3 has none and always will. The live corpus is checked against
    whichever branch its own flag list puts it in — which is the assertion that
    survives a run moving from one state to the other, as run 4 did.
    """
    panel = {"current": quality, "run3": archived_run3, "run2": archived_run2}[corpus]
    note = panel["exclusion"]["note"].lower()

    if corpus == "run2":
        assert panel["flagged"], "run 2 is the corpus that has a flagged judge; without one this proves nothing"
    if corpus == "run3":
        assert not panel["flagged"], "run 3 is the corpus with nothing to exclude; without that this proves nothing"

    if panel["flagged"]:
        assert "no judge has been excluded" in note
        assert "human decision" in note
        assert "adr" in note
    else:
        assert "nothing to exclude" in note
        assert "excluded from" not in note, "a clean panel must not imply a judge was held out of anything"


def test_exclusion_is_reported_as_impossible_rather_than_faked(tmp_path):
    """Two judges, one flagged: excluding it leaves one score per skill and no sigma.

    The honest answer is "cannot be shown, and here is why" — not a sigma of
    zero, and not a silently dropped column.
    """
    directory = _write_corpus(tmp_path / "cards", {"fake/saturator": _saturating, "fake/grader": _discriminating})
    judgments = [j for j in cal.load_judgments(directory) if j.round_index == 0]
    quality = cal.judge_quality(judgments, MAXIMA)
    assert quality["flagged"] == ["fake/saturator"]
    assert quality["exclusion"]["without_flagged"] is None
    assert "cannot be shown" in quality["exclusion"]["note"]


def test_a_clean_panel_says_so_instead_of_showing_an_empty_column(tmp_path):
    directory = _write_corpus(tmp_path / "cards", {"fake/grader": _discriminating, "fake/rounder": _coarse_but_ranking})
    quality = cal.judge_quality(cal.load_judgments(directory), MAXIMA)
    assert quality["flagged"] == []
    assert quality["exclusion"]["without_flagged"] is None
    assert "nothing to exclude" in quality["exclusion"]["note"]


# ---------------------------------------------------------------------------
# The thresholds are justified, not fitted
# ---------------------------------------------------------------------------


def _rubric_band_counts() -> dict[str, int]:
    """Score-band rows per dimension, re-parsed straight out of the pinned rubric."""
    counts: dict[str, int] = {}
    current: str | None = None
    for line in RUBRIC.read_text(encoding="utf-8").splitlines():
        if line.startswith("### D") and ":" in line:
            current = line.split(":", 1)[0].removeprefix("### ").strip()
            counts.setdefault(current, 0)
        elif current and line.startswith("| ") and "-" in line.split("|")[1]:
            head = line.split("|")[1].strip()
            if head[:1].isdigit():
                counts[current] += 1
    return counts


def test_the_distinct_value_threshold_equals_the_rubrics_own_band_count():
    """`MIN_DISTINCT_DIMENSION_VALUES` must stay derived from the rubric.

    It is 4 because every dimension in `vendor/skill-judge/SKILL.md` defines
    four score bands — not because 4 happens to sit between qwen's 3 and
    sonnet's 8. If a re-vendored rubric changes the band count, this fails and
    the constant gets revisited deliberately.
    """
    counts = _rubric_band_counts()
    assert counts, "no dimension band tables found in the pinned rubric"
    assert set(counts) == set(MAXIMA), f"expected one band table per dimension, found {sorted(counts)}"
    assert set(counts.values()) == {cal.MIN_DISTINCT_DIMENSION_VALUES}, (
        f"the rubric's dimensions define {sorted(set(counts.values()))} bands each, but "
        f"eval/calibration.MIN_DISTINCT_DIMENSION_VALUES is {cal.MIN_DISTINCT_DIMENSION_VALUES}"
    )


def test_the_vendored_maxima_table_matches_the_pinned_rubric():
    """The fallback copy of the maxima cannot rot in silence."""
    from scripts.judge_harness import load_rubric

    assert cal.FALLBACK_DIMENSION_MAXIMA == load_rubric().maxima
    assert cal.dimension_maxima() == load_rubric().maxima
    assert sum(cal.FALLBACK_DIMENSION_MAXIMA.values()) == cal.RUBRIC_MAX


def test_the_chance_rate_behind_the_granularity_ceiling_is_computed():
    """0.60 is defensible only against a stated baseline, so the baseline is derived."""
    chance = cal.multiple_of_five_chance_rate(MAXIMA)
    assert 0.20 < chance < 0.30, f"expected ~25% by chance on this rubric, computed {chance}"
    assert cal.GRANULARITY_CEILING > 2 * chance, "the ceiling must be unreachable by an unlucky judge"


def test_every_threshold_is_published_in_the_machine_readable_output(quality):
    published = quality["thresholds"]
    assert published["min_distinct_dimension_values"] == cal.MIN_DISTINCT_DIMENSION_VALUES
    assert published["discrimination_sd_floor"] == cal.DISCRIMINATION_SD_FLOOR
    assert published["granularity_ceiling"] == cal.GRANULARITY_CEILING
    assert published["saturation_dim_max_ceiling"] == cal.SATURATION_DIM_MAX_CEILING
    assert published["saturation_full_total_ceiling"] == cal.SATURATION_FULL_TOTAL_CEILING


# ---------------------------------------------------------------------------
# The published artifacts: stdout, eval/judge-quality.json, the dashboard
# ---------------------------------------------------------------------------


def _run(*args: str):
    return subprocess.run(
        [sys.executable, str(CALIBRATION_PY), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_the_report_prints_the_verdict_prominently(quality, archived_run2):
    """The banner is asserted where a banner is owed, and its absence where it is not.

    `assert VERDICT_NON_DISCRIMINATING in head` was a test of run 2's panel
    wearing the clothes of a test of the printer. Run 3 flags nobody, so the
    banner is correctly absent — and a test that only checked the present run
    would now be checking nothing at all. The printer is therefore exercised on
    both corpora: run 2 must still lead with the flagged judge by name, and run
    3 must lead with the panel line instead of a banner it has no grounds for.
    """
    proc = _run("--no-emit")
    assert proc.returncode == 0, proc.stderr
    head = "\n".join(proc.stdout.splitlines()[:6])
    for flagged in quality["flagged"]:
        assert flagged in head, f"{flagged} is flagged but is not in the first lines of the report"
    if not quality["flagged"]:
        assert not proc.stdout.startswith("!!"), "the report must not raise a banner for a panel it has not flagged"
        assert f"{cal.VERDICT_NON_DISCRIMINATING} JUDGE(S) ON THIS PANEL" not in proc.stdout
        assert proc.stdout.startswith("Panel:")
    assert "Judge quality" in proc.stdout
    assert "WITH and WITHOUT" in proc.stdout
    # Every verdict the panel produced has to reach the printed table, not just the banner.
    for row in quality["providers"]:
        assert row["provider"] in proc.stdout and row["verdict"] in proc.stdout

    flagged_run = _run("--scorecards", str(SCORECARDS_RUN2), "--no-emit")
    assert flagged_run.returncode == 0, flagged_run.stderr
    flagged_head = "\n".join(flagged_run.stdout.splitlines()[:6])
    assert archived_run2["flagged"], "run 2 is the corpus with a flagged judge; without one this proves nothing"
    for flagged in archived_run2["flagged"]:
        assert flagged in flagged_head, f"{flagged} is flagged in run 2 but is not in the first lines of the report"
    assert cal.VERDICT_NON_DISCRIMINATING in flagged_head
    assert "Still pooled into every figure below" in flagged_run.stdout


def test_judge_quality_json_is_committed_and_current(recorded):
    """A stale committed verdict is worse than none: it is a verdict nobody re-ran."""
    assert JUDGE_QUALITY_JSON.is_file(), (
        f"{JUDGE_QUALITY_JSON.relative_to(REPO_ROOT)} is missing — run `python3 eval/calibration.py`"
    )
    on_disk = json.loads(JUDGE_QUALITY_JSON.read_text(encoding="utf-8"))
    expected = cal.judge_quality_document(cal.report(recorded), SCORECARDS)
    assert on_disk == expected, "eval/judge-quality.json is stale — re-run `python3 eval/calibration.py`"


def test_judge_quality_json_carries_no_timestamp():
    """Deterministic output, so a regenerated file diffs only when a verdict moves."""
    text = JUDGE_QUALITY_JSON.read_text(encoding="utf-8")
    for field in ("generated_at", "timestamp", "recorded_at"):
        assert field not in text, f"{field!r} would make every regeneration a diff"


def test_judge_quality_json_states_that_nothing_was_excluded():
    """The doctrine is unconditional; the flag list is derived from the file's own rows.

    `payload["flagged"] == ["bedrock/qwen3-235b"]` was a transcription of run 2
    living inside the test that guards against transcriptions. The list is now
    recomputed from the rows the file publishes, so a hand-edited `flagged` — a
    name added to it, or one quietly dropped out of it — fails here even if the
    edit is internally tidy.
    """
    payload = json.loads(JUDGE_QUALITY_JSON.read_text(encoding="utf-8"))
    doctrine = payload["doctrine"].lower()
    assert "does not remove that judge" in doctrine
    assert "as an exclusion list" in doctrine
    assert "human decision" in doctrine
    assert payload["flagged"] == cal.flagged_providers(payload["providers"])
    assert payload["flagged"] == payload["exclusion"]["flagged"]
    # And whatever is flagged is still pooled: the with-column is the whole panel.
    assert payload["exclusion"]["with_flagged"]["providers"] == sorted(r["provider"] for r in payload["providers"])


def test_running_against_another_corpus_does_not_overwrite_the_committed_file(tmp_path):
    """`--scorecards` points somewhere else; the recorded panel's verdicts must survive it."""
    before = JUDGE_QUALITY_JSON.read_bytes()
    directory = _write_corpus(tmp_path / "cards", {"fake/saturator": _saturating, "fake/grader": _discriminating})
    proc = _run("--scorecards", str(directory))
    assert proc.returncode == 0, proc.stderr
    assert JUDGE_QUALITY_JSON.read_bytes() == before
    assert "fake/saturator" in proc.stdout

    out = tmp_path / "elsewhere.json"
    assert _run("--scorecards", str(directory), "--judge-quality-out", str(out)).returncode == 0
    assert json.loads(out.read_text(encoding="utf-8"))["flagged"] == ["fake/saturator"]
    assert JUDGE_QUALITY_JSON.read_bytes() == before


def test_no_emit_prints_without_writing():
    before = JUDGE_QUALITY_JSON.read_bytes()
    assert _run("--no-emit").returncode == 0
    assert JUDGE_QUALITY_JSON.read_bytes() == before


# ---------------------------------------------------------------------------
# The dashboard publishes the same verdicts
# ---------------------------------------------------------------------------


def test_dashboard_publishes_a_judge_quality_row_for_every_judge(quality):
    flat = _flat(DASHBOARD)
    for row in quality["providers"]:
        assert f"`{row['provider']}`" in flat, f"the dashboard's judge-quality table omits {row['provider']}"
        assert row["verdict"] in flat, f"the dashboard does not publish {row['provider']}'s verdict"


def test_dashboard_publishes_the_measured_judge_quality_figures(quality):
    """Every figure in the published table is re-derived from the scorecards here."""
    flat = _flat(DASHBOARD)
    for row in quality["providers"]:
        disc, gran, sat = row["discrimination"], row["granularity"], row["saturation"]
        for figure in (
            f"| {disc['distinct_dimension_values']} |",
            f"| {disc['across_skill_variance']:.2f} |",
            f"| {gran['multiple_of_five_rate']:.0%} |".replace("%", "%"),
        ):
            assert figure in flat, f"{row['provider']}: dashboard is missing the measured figure {figure!r}"
        assert f"| {sat['full_total_rate']:.0%} |" in flat


def test_dashboard_publishes_the_exclusion_delta_without_applying_it(quality):
    """The page's headline figures are the unfiltered ones, in either state.

    Before run 3 this dereferenced the without-flagged column unconditionally
    and crashed on `None` the moment a panel had nobody to exclude — an
    unhelpful failure, because "there is no such column" is the correct answer
    and not a defect in the page. What the test is actually for survives in both
    branches: the numbers the dashboard publishes must be the *with*-flagged
    ones, so no pre-filtered figure can reach a reader as the panel's result.
    """
    exclusion = quality["exclusion"]
    with_flagged, without_flagged = exclusion["with_flagged"], exclusion["without_flagged"]
    flat = _flat(DASHBOARD)

    assert f"{with_flagged['pooled_mean']}" in flat
    assert f"{with_flagged['sigma_median']:.2f}" in flat
    assert "eval/judge-quality.json" in flat
    assert "human decision" in flat.lower(), "the dashboard must say whose decision an exclusion is"

    if without_flagged is None:
        # Nothing is flagged, so there is no second column to publish. The page
        # has to say that rather than leave the reader to assume a filter ran;
        # the sentence asserted is the one `eval/calibration.py` itself prints.
        assert not quality["flagged"]
        # Quoted from the tool rather than paraphrased, for the same reason the
        # judge prompt quotes the rubric's band rows byte-for-byte: a paraphrase
        # is a second claim that nothing regenerates. Only the sentence-final
        # stop is forgiven, so the note can be quoted inside a sentence.
        quoted = exclusion["note"].rstrip(".")
        assert quoted in " ".join(DASHBOARD.read_text(encoding="utf-8").split()), (
            "the dashboard must carry the exclusion note this run produces, word for word:\n"
            f"  {exclusion['note']}\n"
            "(print it with `python3 eval/calibration.py`)"
        )
        return

    assert f"{without_flagged['pooled_mean']}" in flat
    assert f"{without_flagged['sigma_median']:.2f}" in flat
    assert "not excluded" in flat.lower(), "the dashboard must say the flagged judge is still pooled"


def test_dashboard_records_which_runs_predate_the_rubric_bands():
    """The note the absolute numbers on this page depend on — pointed at the right runs.

    Run 1 and run 2 were both scored by a prompt that sent dimension names and
    no bands, so their absolute values are weaker evidence than a run scored
    against the bands. That was written when `eval/scorecards/` *was* run 2; it
    has since been run 3 and is now run 4, and a page that still files the
    current corpus under "no bands were sent" is telling the reader the opposite
    of the truth. The archived runs are therefore asserted by the directory a
    reader can go and open, which the pre-band claim can no longer drift away
    from — and every archive has to be named, so a third one cannot quietly stop
    being mentioned the day it is created.

    Which run the page publishes is derived too. `eval/scorecards/` is always the
    live corpus, so the run it holds is one past the highest archived number, and
    a page that goes on announcing the previous run is the same drift with a
    different surface. Asserting the literal string "run 3" was what let that
    slip through for a whole run.
    """
    flat = _flat(DASHBOARD).lower()
    archives = sorted(d.name for d in (REPO_ROOT / "eval").glob("scorecards-run*") if d.is_dir())
    assert archives, "the repository must retain at least one archived run for this claim to be about anything"
    for archive in archives:
        assert archive in flat, (
            f"the dashboard must name eval/{archive}/ as an archived corpus a reader can open, "
            "rather than a run number that has since been reused"
        )
    assert "rubric bands" in flat or "scoring bands" in flat
    assert "weaker evidence" in flat

    current_run = 1 + max(int(name.rsplit("run", 1)[1]) for name in archives)
    assert f"run {current_run}" in flat, (
        f"eval/scorecards/ holds run {current_run} (one past the {len(archives)} archived run(s)); "
        "the page has to say which run its figures come from"
    )
