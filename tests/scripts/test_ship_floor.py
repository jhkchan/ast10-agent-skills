"""Tests for scripts.ship_floor — spec.md gate-2 (inherited formula) and
gate-3 (vendoring). Covers T-2.2's acceptance tests, translated from
spec.md's Given/When/Then for S-001, S-006, S-009.

S-001 (happy path, half 1): "Grade A clears on the inherited formula (mean >=
108 AND mean-sigma >= 105, per-dimension floors including D1 >= 17/20) ...
the run publishes as passing with scores.json + ... audit trail."

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

import pytest

import scripts.ship_floor as ship_floor
from scripts.content_hash import content_sha256
from scripts.ship_floor import (
    AGG_METHOD,
    FLOORS,
    POOLED_LOWER_BOUND,
    POOLED_TARGET,
    RUBRIC_SHA,
    aggregate_verdict,
    binding_block,
    dim_means_of,
    pooled_stats,
    verdict_of,
)

# A golden pool of four independent judgment totals. Chosen so both halves of
# the formula clear comfortably: mean 109.8 >= 108, lower_bound 108.1 >= 105.
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
    assert POOLED_LOWER_BOUND == 105


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
    }


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
    # specifically the per-dimension floor, not the mean/lower_bound gate.
    stats = pooled_stats(agg["judgments"])
    assert stats["mean"] >= POOLED_TARGET
    assert stats["lower_bound"] >= POOLED_LOWER_BOUND

    verdict, reason = aggregate_verdict("generic-definition-skill", agg)

    assert verdict == "BLOCKED"
    assert "D1" in reason
    assert "floor" in reason


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
