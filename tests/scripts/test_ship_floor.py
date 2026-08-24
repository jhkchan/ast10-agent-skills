"""Tests for scripts.ship_floor — spec.md gate-2 (inherited formula) and
gate-3 (vendoring). Covers T-2.2's acceptance tests, translated from
spec.md's Given/When/Then for S-001, S-006, S-009.

S-001 (happy path, half 1): "Grade A clears on the inherited formula (mean >=
108 AND mean-sigma >= 105, per-dimension floors including D1 >= 17/20) ...
the run publishes as passing with scores.json + ... audit trail."

**The second clause has changed once since spec.md was written**, and these
tests are pointed at the rule in force rather than at the sentence above.
`docs/adr/0006-confidence-bound-on-the-pooled-mean.md` (2026-08-24) retired
`mean - stdev >= POOLED_LOWER_BOUND (105)` and replaced it with
`mean - CONFIDENCE_K (1.0) * stdev/sqrt(n) >= POOLED_TARGET (108)`, because a
spread statistic used as a confidence bound on a mean made the verdict a
function of the panel rather than of the artifact. spec.md's wording is left
quoted as written -- it is the contract as it stood -- and the constants below
are asserted against ADR-0006, which must also *document* each of them, so a
constant and its justification cannot drift apart.

S-006 (D1 floor breach): "D1 scores <=5 for the generic-definition shape;
pooled D1 falls below its 17/20 floor; the skill fails Grade A regardless of
other dimensions ... the sub-score for D1 is surfaced in scores.json, not
just an aggregate fail."

S-009 (retained judgments, deterministic recompute): "All individual provider
judgments are retained with timestamps; the aggregate verdict is
deterministically recomputed from recorded judgments; non-determinism is
visible in judge outputs, not hidden in aggregation."
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.ship_floor as ship_floor
from scripts.content_hash import content_sha256
from scripts.ship_floor import (
    AGG_METHOD,
    CONFIDENCE_K,
    FLOORS,
    MIN_ROUNDS,
    POOLED_LOWER_BOUND,
    POOLED_TARGET,
    RUBRIC_SHA,
    aggregate_verdict,
    binding_block,
    dim_means_of,
    pooled_stats,
    verdict_of,
)

ADR_0006 = Path(__file__).resolve().parents[2] / "docs" / "adr" / "0006-confidence-bound-on-the-pooled-mean.md"

# A golden pool of four independent judgment totals. Chosen so both halves of
# the formula clear comfortably: mean 109.8 >= 108, ci_lower 109.0 >= 108.
GOLDEN_JUDGMENTS = [110, 112, 108, 109]
GOLDEN_DIM_MEANS = {
    "D1": 17.0,
    "D2": 13.0,
    "D3": 13.0,
    "D4": 13.0,
    "D5": 13.0,
    "D6": 13.0,
    "D7": 8.0,
    "D8": 13.0,
}
# A single judge block's dims: every floor cleared AND total >= TARGETS["A"] (108) --
# verdict_of() checks both, unlike the pooled dim_means which only need to clear the
# floor individually (the pooled mean/lower_bound gate is computed over `judgments`,
# not over dim_means).
BLOCK_DIMS = {
    "D1": 18,
    "D2": 14,
    "D3": 14,
    "D4": 14,
    "D5": 14,
    "D6": 14,
    "D7": 9,
    "D8": 14,
}


def _golden_agg(**overrides) -> dict:
    agg = {
        "method": AGG_METHOD,
        "rubric_sha": RUBRIC_SHA,
        "judgments": list(GOLDEN_JUDGMENTS),
        "n": 4,
        "mean": 109.8,
        "median": 109.5,
        "min": 108,
        "max": 112,
        "range": 4,
        "stdev": 1.71,
        "lower_bound": 108.1,
        "sem": 0.85,
        "ci_lower": 109.0,
        "dim_means": dict(GOLDEN_DIM_MEANS),
    }
    agg.update(overrides)
    return agg


def test_floors_match_spec_gate_2_locked_values():
    """spec.md gate-2: 'per-dimension floors {D1:17, D2:13, D3:13, D4:13, D5:13, D6:13, D7:8, D8:13}'."""
    assert FLOORS == {
        "D1": 17,
        "D2": 13,
        "D3": 13,
        "D4": 13,
        "D5": 13,
        "D6": 13,
        "D7": 8,
        "D8": 13,
    }
    assert POOLED_TARGET == 108


def test_the_live_gate_constants_are_the_ones_adr_0006_documents():
    """The constant and its justification must not be able to drift apart.

    Pinning a number alone is how a gate quietly becomes undocumented: the
    literal stays green while the record explaining it rots. So each constant is
    asserted twice — against its value, and against ADR-0006 *stating* that
    value — and a change to either half without the other fails here.
    """
    assert CONFIDENCE_K == 1.0
    assert POOLED_TARGET == 108
    assert MIN_ROUNDS == 4

    adr = " ".join(ADR_0006.read_text(encoding="utf-8").split())
    for fragment in (
        "POOLED_TARGET = 108",
        "CONFIDENCE_K = 1.0",
        "MIN_ROUNDS = 4",
        "mean - CONFIDENCE_K * sem",
        "ci_lower >= POOLED_TARGET",
    ):
        assert fragment in adr, f"ADR-0006 no longer documents {fragment!r}; the gate constant is now unexplained"


def test_the_retired_lower_bound_is_retired_and_read_by_nothing():
    """ADR-0006 retires POOLED_LOWER_BOUND without deleting it.

    It stays at 105 because ADR-0005's diagnosis is arithmetic on that exact
    number and `eval/calibration.py` regenerates those figures from it. What
    must stay true is that the *gate* no longer reads it: an aggregate whose
    `mean - stdev` sits far below 105 still SHIPs when the clause in force is
    satisfied.
    """
    assert POOLED_LOWER_BOUND == 105

    # mean 110.0, stdev 5.12 -> lower_bound 104.9, under the retired 105;
    # sem 1.71, ci_lower 108.3 -> clears the clause in force.
    totals = [110, 118, 102, 114, 106, 110, 110, 105, 115]
    stats = pooled_stats(totals)
    assert stats["lower_bound"] < POOLED_LOWER_BOUND
    assert stats["ci_lower"] >= POOLED_TARGET

    agg = _golden_agg(judgments=totals, **stats)
    assert aggregate_verdict("retired-bound-check", agg) == ("SHIP", "")


def test_pooled_stats_reproduces_reference_verdict_bit_for_bit():
    """A golden fixture of recorded judgments reproduces the reference stats
    bit-for-bit (plan.md T-2.2 test #1)."""
    stats = pooled_stats(GOLDEN_JUDGMENTS)

    assert stats == {
        "n": 4,
        "mean": 109.8,
        "median": 109.5,
        "min": 108,
        "max": 112,
        "range": 4,
        "stdev": 1.71,
        "lower_bound": 108.1,
        "sem": 0.85,
        "ci_lower": 109.0,
    }
    # Recomputable by hand from the three numbers a reader is given, which is
    # the whole point of rounding once: 1.71/sqrt(4) = 0.855 -> 0.85 (the float
    # nearest 0.855 is below it, so round() goes down, and the published value
    # is what the gate uses); 109.8 - 1.0 * 0.85 = 108.95 -> 109.0.
    assert stats["ci_lower"] == round(stats["mean"] - CONFIDENCE_K * stats["sem"], 1)


def test_compliant_skill_clears_both_halves_and_ships(tmp_path):
    """S-001: dual formula clears -> SHIP, and the run publishes scores plus
    an audit trail a reader can inspect (scores.json + binding block)."""
    skill_dir = tmp_path / "skills" / "AST01"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# AST01\n")
    sha = content_sha256(skill_dir)

    live_block = {
        "method": "live-subagent-skill-judge",
        "dims": dict(BLOCK_DIMS),
        "total": sum(BLOCK_DIMS.values()),
        "content_sha256": sha,
        "verdict": "SHIP",
    }
    iters = {"iter-1-live": live_block, "aggregate": _golden_agg(verdict="SHIP")}

    blk = binding_block("AST01", iters, skills_dir=tmp_path / "skills")
    assert blk is live_block
    v, why = verdict_of("AST01", blk)
    assert (v, why) == ("SHIP", "")

    av, awhy = aggregate_verdict("AST01", iters["aggregate"])
    assert (av, awhy) == ("SHIP", "")

    # Audit trail: scores.json round-trips through JSON without losing the
    # judgments or the per-block verdict a reader would audit.
    scores_path = tmp_path / "scores.json"
    scores_path.write_text(json.dumps({"AST01": iters}))
    reloaded = json.loads(scores_path.read_text())
    assert reloaded["AST01"]["aggregate"]["judgments"] == GOLDEN_JUDGMENTS
    assert reloaded["AST01"]["iter-1-live"]["verdict"] == "SHIP"


def test_d1_below_floor_blocks_even_though_aggregate_clears_108():
    """S-006: pooled D1 of 16 fails the run on the per-dimension floor even
    when the aggregate mean clears 108; the D1 sub-score is surfaced in the
    BLOCKED reason, not just an aggregate fail."""
    agg = _golden_agg(dim_means={**GOLDEN_DIM_MEANS, "D1": 16.0})

    # The aggregate half still clears on its own -- proves the block is
    # specifically the per-dimension floor, not the mean/confidence-bound gate.
    stats = pooled_stats(agg["judgments"])
    assert stats["mean"] >= POOLED_TARGET
    assert stats["ci_lower"] >= POOLED_TARGET

    verdict, reason = aggregate_verdict("generic-definition-skill", agg)

    assert verdict == "BLOCKED"
    assert "D1" in reason
    assert "floor" in reason


def test_a_grade_a_mean_that_is_not_confidently_grade_a_is_blocked_and_says_why():
    """ADR-0006's clause 2, and the reason string a reader must be able to check.

    The message has to carry the statistic, the computed value, the bar and n,
    because a BLOCKED reason nobody can verify from the scorecard is an
    assertion rather than a finding.
    """
    # mean 110.0 (Grade A) on a wide pool: stdev 8.77, sem 2.92, ci_lower 107.1.
    totals = [110, 122, 98, 118, 102, 110, 110, 100, 120]
    stats = pooled_stats(totals)
    assert stats["mean"] >= POOLED_TARGET  # clause 1 clears
    agg = _golden_agg(judgments=totals, **stats)

    verdict, reason = aggregate_verdict("wide-panel-skill", agg)

    assert verdict == "BLOCKED"
    assert "stdev/sqrt(n)" in reason, "the reason must name the statistic, not just its value"
    assert str(stats["ci_lower"]) in reason, "the reason must publish the computed bound"
    assert f"target {POOLED_TARGET}" in reason, "the reason must publish the bar it failed"
    assert f"n {stats['n']}" in reason, "the reason must publish n — the bound is meaningless without it"
    # Hand-checkable end to end from the four numbers the message prints.
    assert round(stats["mean"] - CONFIDENCE_K * stats["sem"], 1) == stats["ci_lower"] < POOLED_TARGET


def test_a_stored_confidence_bound_that_disagrees_with_the_recompute_is_refused():
    """The two keys ADR-0006 added are tolerated when ABSENT, never when WRONG.

    Absence dates a scorecard to before 2026-08-24; a wrong value is a claim the
    judgments do not support, and the gate's whole premise is that it believes
    the judgments and nothing else.
    """
    pre_adr = _golden_agg()
    del pre_adr["sem"]
    del pre_adr["ci_lower"]
    assert aggregate_verdict("run-4-shaped", pre_adr) == ("SHIP", "")

    for key in ("sem", "ci_lower"):
        doctored = _golden_agg(**{key: 0.01})
        verdict, reason = aggregate_verdict("doctored", doctored)
        assert verdict == "BLOCKED", f"a stored {key} that disagrees with the recompute must not pass"
        assert key in reason


def test_an_aggregate_missing_a_required_statistic_is_refused():
    """Tolerating the two new keys must not tolerate an empty aggregate."""
    for key in ("mean", "stdev", "lower_bound", "n"):
        agg = _golden_agg()
        del agg[key]
        verdict, reason = aggregate_verdict("hollow", agg)
        assert verdict == "BLOCKED", f"an aggregate with no {key} must not pass"
        assert key in reason


def test_aggregate_verdict_is_deterministic_across_repeat_calls():
    """S-009: 'the aggregate verdict is deterministically recomputed from
    recorded judgments; non-determinism is visible in judge outputs, not
    hidden in aggregation.'"""
    agg = _golden_agg()

    first = aggregate_verdict("AST01", agg)
    second = aggregate_verdict("AST01", agg)

    assert first == second == ("SHIP", "")


def test_second_scoring_run_appends_and_retains_the_first(tmp_path):
    """S-009: 'Both scoring runs are recorded in the artifact (scores.json
    retains all individual judgments, never overwrites) ... a reader can
    audit both runs and the reconciliation.'"""
    round_1 = list(GOLDEN_JUDGMENTS)
    stats_before = pooled_stats(round_1)

    # A second, independent scoring run adds a judgment -- it must be a new
    # list, not a mutation, mirroring "retains ... never overwrites".
    round_2 = round_1 + [111]

    stats_after_recompute_of_round_1 = pooled_stats(round_1)
    stats_of_round_2 = pooled_stats(round_2)

    assert round_1 == GOLDEN_JUDGMENTS  # round 1's recorded judgments untouched
    assert stats_after_recompute_of_round_1 == stats_before  # deterministic recompute
    assert stats_of_round_2["n"] == 5  # round 2 pools all 5, not just the new one
    assert stats_of_round_2 != stats_before  # the two runs are distinguishable


def test_pooled_stats_requires_min_rounds():
    with pytest.raises(ValueError, match="need >= 4"):
        pooled_stats([120, 118, 119])


def test_dim_means_of_averages_across_recorded_breakdowns():
    high = {**BLOCK_DIMS, "D1": 18, "D2": 14}
    low = {**BLOCK_DIMS, "D1": 16, "D2": 12}
    means = dim_means_of([high, low])
    assert means["D1"] == 17.0
    assert means["D2"] == 13.0


def test_main_reports_ok_for_a_compliant_repo(tmp_path, monkeypatch, capsys):
    """S-001 end-to-end: main() reads scores.json under OWASP_AST10_ROOT and
    publishes a passing run with its scores."""
    skill_dir = tmp_path / "skills" / "AST01"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# AST01\n")
    sha = content_sha256(skill_dir)

    live_block = {
        "method": "live-subagent-skill-judge",
        "dims": dict(BLOCK_DIMS),
        "total": sum(BLOCK_DIMS.values()),
        "content_sha256": sha,
        "verdict": "SHIP",
    }
    scores = {"AST01": {"iter-1-live": live_block, "aggregate": _golden_agg(verdict="SHIP")}}
    (tmp_path / "scores.json").write_text(json.dumps(scores))

    monkeypatch.setattr(ship_floor, "ROOT", tmp_path)
    rc = ship_floor.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "OK: 1 skill(s) shipped." in out


def test_main_fails_when_stored_verdict_disagrees_with_recompute(tmp_path, monkeypatch, capsys):
    skill_dir = tmp_path / "skills" / "AST01"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# AST01\n")
    sha = content_sha256(skill_dir)

    live_block = {
        "method": "live-subagent-skill-judge",
        "dims": dict(BLOCK_DIMS),
        "total": sum(BLOCK_DIMS.values()),
        "content_sha256": sha,
        "verdict": "BLOCKED",  # self-asserted, wrong -- must disagree with recompute
    }
    scores = {"AST01": {"iter-1-live": live_block}}
    (tmp_path / "scores.json").write_text(json.dumps(scores))

    monkeypatch.setattr(ship_floor, "ROOT", tmp_path)
    rc = ship_floor.main()
    out = capsys.readouterr().out

    assert rc == 1
    assert "FAIL: AST01" in out
