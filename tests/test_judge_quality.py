"""Tests for the judge-quality diagnostics in `eval/calibration.py`.

Bias tests (`tests/test_calibration.py`) ask whether a judge's number is in the
right place. These ask the prior question: whether the number is a measurement
at all. The recorded panel contains a judge that returned exactly 120.0 on all
eleven skills — three distinct values, every one of them a dimension's maximum —
and no bias figure can express that, because +10.8 reads as "lenient" when what
happened was that nothing was ranked.

Four things are held here:

1. **The verdict rule works on judges built to order.** A saturating judge and a
   discriminating one are synthesised from scratch, so the rule is exercised
   against data whose right answer is known independently of the panel that
   motivated it. A judge that is merely coarse — rounds to fives but still ranks
   skills — must come out COARSE and must *not* be flagged, because conflating
   the two would make the flag useless.
2. **The rule lands correctly on the real recorded panel.** `bedrock/qwen3-235b`
   is flagged; `claude-cli/sonnet` is not. Both are asserted, and the second is
   the load-bearing one: a rule that flags a strict judge as a broken one would
   be worse than no rule.
3. **Nothing is silently excluded.** The flagged judge stays in every pooled
   figure, `eval/judge-quality.json` says so in words, and the report shows the
   with- and without- columns side by side so the size of the effect is visible
   rather than pre-applied. Declare and record.
4. **The thresholds are justified rather than fitted.** `MIN_DISTINCT_
   DIMENSION_VALUES` is asserted against the actual band count in the pinned
   rubric, and the vendored maxima table against the rubric's own headings, so
   neither can drift into being a number that only happens to catch one judge.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from eval import calibration as cal

REPO_ROOT = Path(__file__).resolve().parents[1]
CALIBRATION_PY = REPO_ROOT / "eval" / "calibration.py"
DASHBOARD = REPO_ROOT / "docs" / "skill-judge-dashboard.md"
SCORECARDS = REPO_ROOT / "eval" / "scorecards"
JUDGE_QUALITY_JSON = REPO_ROOT / "eval" / "judge-quality.json"
RUBRIC = REPO_ROOT / "vendor" / "skill-judge" / "SKILL.md"

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


def test_the_recorded_panel_flags_qwen(quality):
    assert quality["flagged"] == ["bedrock/qwen3-235b"], (
        "the recorded panel's flat judge must be flagged, and no one else with it"
    )


def test_the_recorded_panel_does_not_flag_sonnet(quality):
    """The harshest judge on the panel is a judge, not a defect.

    `claude-cli/sonnet` sits 3.7 points below the pooled mean and never once
    awards a dimension maximum. Both are things a strict grader does. If the
    rule could not tell it apart from a judge returning 120.0 eleven times, the
    rule would be measuring severity and calling it quality.
    """
    row = next(r for r in quality["providers"] if r["provider"] == "claude-cli/sonnet")
    assert row["verdict"] == cal.VERDICT_DISCRIMINATING
    assert row["reasons"] == []
    assert "claude-cli/sonnet" not in quality["flagged"]


def test_qwen_signals_are_the_measured_ones(quality):
    """The specific measurement that motivated all of this, asserted directly."""
    row = next(r for r in quality["providers"] if r["provider"] == "bedrock/qwen3-235b")
    disc, gran, sat, cons = row["discrimination"], row["granularity"], row["saturation"], row["self_consistency"]
    assert row["n_judgments"] == 33 and row["n_skills"] == 11
    assert disc["distinct_dimension_values"] == 3
    assert disc["dimension_values"] == [10.0, 15.0, 20.0]
    assert (disc["across_skill_sd"], disc["across_skill_variance"]) == (0.0, 0.0)
    assert (disc["skill_mean_min"], disc["skill_mean_max"]) == (120.0, 120.0)
    assert gran["multiple_of_five_rate"] == 1.0
    assert (sat["dimension_max_rate"], sat["full_total_rate"]) == (1.0, 1.0)
    assert cons["same_skill_spread_max"] == 0.0


def test_every_judge_on_the_panel_gets_a_verdict(quality, recorded):
    named = {row["provider"] for row in quality["providers"]}
    assert named == {j.provider for j in recorded}
    assert all(row["verdict"] in quality["verdicts"] for row in quality["providers"])


def test_granularity_across_the_panel_is_measured_not_asserted(quality):
    """The spread the defect report quotes: 100% down to 0%, on the same rubric."""
    rates = {r["provider"]: r["granularity"]["multiple_of_five_rate"] for r in quality["providers"]}
    assert rates["bedrock/qwen3-235b"] == 1.0
    assert rates["claude-cli/sonnet"] == 0.0
    assert all(rate is not None for rate in rates.values())


# ---------------------------------------------------------------------------
# Declare and record: flagged is not excluded
# ---------------------------------------------------------------------------


def test_the_exclusion_block_shows_both_columns_and_the_delta(quality):
    exclusion = quality["exclusion"]
    with_flagged, without_flagged = exclusion["with_flagged"], exclusion["without_flagged"]
    assert with_flagged is not None and without_flagged is not None
    assert with_flagged["n_judgments"] > without_flagged["n_judgments"]
    assert "bedrock/qwen3-235b" in with_flagged["providers"]
    assert "bedrock/qwen3-235b" not in without_flagged["providers"]
    assert exclusion["delta"]["pooled_mean"] == round(without_flagged["pooled_mean"] - with_flagged["pooled_mean"], 2)
    assert exclusion["delta"]["sigma_median"] < 0, "dropping the flat judge must visibly narrow the panel"


def test_the_flagged_judge_is_still_in_every_pooled_figure(recorded, quality):
    """The point of the whole design: the evidence is published, the pool is untouched."""
    full = cal.panel_summary(recorded)
    assert full["n_providers"] == len(quality["providers"])
    assert full["pooled_mean"] == quality["exclusion"]["with_flagged"]["pooled_mean"]
    assert full["n_judgments"] == quality["exclusion"]["with_flagged"]["n_judgments"]


def test_the_exclusion_note_says_the_decision_is_a_human_one(quality):
    note = quality["exclusion"]["note"].lower()
    assert "no judge has been excluded" in note
    assert "adr" in note


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


def test_the_report_prints_the_verdict_prominently(quality):
    proc = _run("--no-emit")
    assert proc.returncode == 0, proc.stderr
    head = "\n".join(proc.stdout.splitlines()[:6])
    for flagged in quality["flagged"]:
        assert flagged in head, f"{flagged} is flagged but is not in the first lines of the report"
    assert cal.VERDICT_NON_DISCRIMINATING in head
    assert "Judge quality" in proc.stdout
    assert "WITH and WITHOUT" in proc.stdout


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
    payload = json.loads(JUDGE_QUALITY_JSON.read_text(encoding="utf-8"))
    doctrine = payload["doctrine"].lower()
    assert "does not remove that judge" in doctrine
    assert "as an exclusion list" in doctrine
    assert "human decision" in doctrine
    assert payload["flagged"] == ["bedrock/qwen3-235b"]


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
    exclusion = quality["exclusion"]
    flat = _flat(DASHBOARD)
    assert f"{exclusion['with_flagged']['pooled_mean']}" in flat
    assert f"{exclusion['without_flagged']['pooled_mean']}" in flat
    assert f"{exclusion['with_flagged']['sigma_median']:.2f}" in flat
    assert f"{exclusion['without_flagged']['sigma_median']:.2f}" in flat
    assert "eval/judge-quality.json" in flat
    for phrase in ("human decision", "not excluded"):
        assert phrase in flat.lower(), f"the dashboard must say the panel is {phrase!r} here"


def test_dashboard_records_that_the_recorded_runs_predate_the_rubric_bands():
    """The note the absolute numbers on this page depend on.

    Run 1 and run 2 were both scored by a prompt that sent dimension names and
    no bands. Their relative orderings are still evidence; their absolute values
    are weaker evidence than a future run's, and the page has to say so next to
    the table rather than only in a callout at the top.
    """
    flat = _flat(DASHBOARD).lower()
    assert "run 1" in flat and "run 2" in flat
    assert "rubric bands" in flat or "scoring bands" in flat
    assert "weaker evidence" in flat
