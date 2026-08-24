"""Tests for eval/calibration.py and the ADR whose argument rests on its output.

`docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md` claims the ship
rule's `mean − stdev` clause measures judge disagreement rather than skill
quality, and every step of that claim is a number. A number in prose is a claim;
a number a script derives from `eval/scorecards/*.json` is evidence. These tests
hold the two together:

1. `eval/calibration.py` runs, and its arithmetic is correct on a corpus small
   enough to check by hand.
2. Every per-provider bias figure printed in the ADR's table equals what the
   script computes from the recorded scorecards — the ADR cannot drift from the
   data without failing here.
3. The panel-level figures the ADR quotes in prose (pooled mean, spread,
   within-judge round spread, sigma range, the mean the locked rule implies)
   equal the script's.
4. `docs/skill-judge-dashboard.md`'s calibration note quotes the same figures.
   It is where the drift actually happened: an earlier draft published a
   `nova-pro` bias of −7.9 and a 20.1-point spread against scorecards that say
   −5.4 and 17.9.
5. The gate constants the ADR promises it did not touch are still the values it
   names. This is the ADR's central claim — that the bar was not retuned after
   seeing the results — and the only way to keep it true a year from now is to
   make changing a constant fail a test that names the record.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ship_floor import FLOORS, MIN_ROUNDS, POOLED_LOWER_BOUND, POOLED_TARGET

REPO_ROOT = Path(__file__).resolve().parents[1]
CALIBRATION_PY = REPO_ROOT / "eval" / "calibration.py"
ADR = REPO_ROOT / "docs" / "adr" / "0005-judge-panel-calibration-and-the-lower-bound.md"
DASHBOARD = REPO_ROOT / "docs" / "skill-judge-dashboard.md"
SCORECARDS = REPO_ROOT / "eval" / "scorecards"
#: Run 2, archived and frozen. Used where a claim needs a panel that has a
#: flagged judge on it: run 3 has none, and a check that only runs when someone
#: is flagged is a check that stops running the moment the panel improves.
SCORECARDS_RUN2 = REPO_ROOT / "eval" / "scorecards-run2"


def _load_calibration():
    spec = importlib.util.spec_from_file_location("calibration_under_test", CALIBRATION_PY)
    module = importlib.util.module_from_spec(spec)
    # Registered before exec: @dataclass resolves annotations through
    # sys.modules[cls.__module__], and a module absent from it raises.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cal = _load_calibration()


def _text(path: Path) -> str:
    """File text with U+2212 MINUS SIGN folded to ASCII and whitespace collapsed.

    Published prose uses a typographic minus; the script prints a hyphen. The
    two must compare equal or every negative bias fails for a glyph.
    """
    return " ".join(path.read_text(encoding="utf-8").replace("−", "-").split())


@pytest.fixture(scope="module")
def judgments():
    rows = cal.load_judgments(SCORECARDS)
    if not rows:
        pytest.skip("no scorecards recorded — calibration has nothing to measure")
    return rows


@pytest.fixture(scope="module")
def computed(judgments):
    return cal.report(judgments)


# ---------------------------------------------------------------------------
# 1. The script runs, and its arithmetic is checkable by hand
# ---------------------------------------------------------------------------


def test_calibration_runs_as_a_script():
    proc = subprocess.run(
        [sys.executable, str(CALIBRATION_PY)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"eval/calibration.py exited {proc.returncode}: {proc.stderr}"
    assert "Per-provider bias" in proc.stdout
    assert "Per-skill dispersion" in proc.stdout


def test_calibration_emits_json():
    proc = subprocess.run(
        [sys.executable, str(CALIBRATION_PY), "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert set(payload) == {"summary", "providers", "skills", "judge_quality"}


def test_the_headline_figures_still_describe_the_whole_panel(computed):
    """Judge-quality diagnostics must not quietly filter the tables above them.

    `judge_quality` may flag a judge, and its exclusion block may show what
    dropping that judge would do. `summary`, `providers` and `skills` describe
    the panel as recorded — every judge, flagged or not — because that is the
    panel the scorecards, the dashboard and ADR-0005 all report.

    This used to `skip` when nothing was flagged, which run 3 made permanent:
    the check that the published headline figures are unfiltered went silent on
    exactly the panel that is published. Nothing here needed a flagged judge
    except one line, so the rest now always runs, and that line is exercised
    against the archived run-2 corpus — which has a flagged judge and, being
    frozen, always will.
    """
    named = {row["provider"] for row in computed["providers"]}
    with_flagged = computed["judge_quality"]["exclusion"]["with_flagged"]
    assert with_flagged["providers"] == sorted(named), "the with-flagged column is the panel, or it is nothing"
    assert with_flagged["pooled_mean"] == computed["summary"]["pooled_mean"]
    assert with_flagged["n_judgments"] == computed["summary"]["n_judgments"]
    assert set(computed["judge_quality"]["flagged"]) <= named

    archived = cal.report(cal.load_judgments(SCORECARDS_RUN2))
    flagged = archived["judge_quality"]["flagged"]
    assert flagged, (
        f"{SCORECARDS_RUN2.relative_to(REPO_ROOT)} is the recorded panel that has a flagged judge; "
        "without one, the assertion below proves nothing"
    )
    archived_named = {row["provider"] for row in archived["providers"]}
    assert set(flagged) <= archived_named, "a flagged judge vanished from the per-provider bias table"
    archived_with = archived["judge_quality"]["exclusion"]["with_flagged"]
    assert archived_with["pooled_mean"] == archived["summary"]["pooled_mean"]
    assert archived_with["n_judgments"] == archived["summary"]["n_judgments"]


def test_empty_corpus_is_reported_not_crashed(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(CALIBRATION_PY), "--scorecards", str(tmp_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0
    assert "nothing to calibrate" in proc.stdout


def _write_card(directory: Path, skill: str, rows: list[tuple[str, float]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{skill}.json").write_text(
        json.dumps({"skill": skill, "judgments": [{"provider": p, "total": t} for p, t in rows]}),
        encoding="utf-8",
    )


def test_bias_is_provider_mean_minus_pooled_mean(tmp_path):
    """Hand-checkable: pooled mean 100, one judge +10, one −10."""
    _write_card(tmp_path, "S1", [("high", 110.0), ("low", 90.0)])
    _write_card(tmp_path, "S2", [("high", 110.0), ("low", 90.0)])
    rows = {r["provider"]: r for r in cal.provider_bias(cal.load_judgments(tmp_path))}
    assert cal.pooled_mean(cal.load_judgments(tmp_path)) == 100.0
    assert rows["high"]["bias"] == 10.0
    assert rows["low"]["bias"] == -10.0
    assert rows["high"]["round_spread"] == 0.0


def test_rounds_are_attributed_per_provider_not_by_block_slicing(tmp_path):
    """A provider missing from one round must not shift another judge's rounds.

    Round two here has no `low` judgment. Slicing the list into fixed-size
    blocks would file `high`'s third score as round two's, and quietly.
    """
    _write_card(
        tmp_path,
        "S1",
        [("high", 100.0), ("low", 80.0), ("high", 102.0), ("high", 104.0), ("low", 82.0)],
    )
    rows = {r["provider"]: r for r in cal.provider_bias(cal.load_judgments(tmp_path))}
    assert rows["high"]["round_means"] == [100.0, 102.0, 104.0]
    assert rows["low"]["round_means"] == [80.0, 82.0]


def test_dispersion_matches_the_shipped_aggregate_block(judgments):
    """The script must reproduce each scorecard's own stored mean/stdev/bound.

    Same rounding order as `ship_floor.pooled_stats`, so the calibration table
    and the dashboard cannot print two different numbers for one measurement.
    """
    rows = {r["skill"]: r for r in cal.skill_dispersion(judgments)}
    for path in sorted(SCORECARDS.glob("*.json")):
        card = json.loads(path.read_text(encoding="utf-8"))
        agg = card.get("aggregate")
        if not agg:
            continue
        row = rows[card["skill"]]
        assert (row["n"], row["mean"], row["sigma"], row["lower_bound"]) == (
            agg["n"],
            agg["mean"],
            agg["stdev"],
            agg["lower_bound"],
        ), f"{path.name}: calibration disagrees with the stored aggregate block"


def test_a_malformed_judgment_is_refused_rather_than_averaged(tmp_path):
    (tmp_path / "S1.json").write_text(
        json.dumps({"skill": "S1", "judgments": [{"provider": "p", "total": None}]}),
        encoding="utf-8",
    )
    with pytest.raises(cal.ScorecardError):
        cal.load_judgments(tmp_path)


# ---------------------------------------------------------------------------
# 2. The ADR's provider table equals the computed biases
# ---------------------------------------------------------------------------

#: `| \`provider\` | n | mean | bias | round means |`
ADR_ROW_RE = re.compile(
    r"\|\s*`([^`]+)`\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|\s*([+-][\d.]+)\s*\|\s*([^|]+)\|",
)


def _adr_provider_rows() -> dict[str, tuple[int, float, float, str]]:
    rows = {}
    for provider, n, mean, bias, round_means in ADR_ROW_RE.findall(_text(ADR)):
        rows[provider] = (int(n), float(mean), float(bias), round_means.strip())
    return rows


def test_adr_publishes_a_row_for_every_judge_on_the_panel(computed):
    published = _adr_provider_rows()
    measured = {row["provider"] for row in computed["providers"]}
    assert set(published) == measured, (
        "the ADR's bias table must name exactly the judges in eval/scorecards/ — "
        f"missing {sorted(measured - set(published))}, extra {sorted(set(published) - measured)}"
    )


def test_adr_bias_figures_match_the_computed_biases(computed):
    published = _adr_provider_rows()
    for row in computed["providers"]:
        n, mean, bias, round_means = published[row["provider"]]
        assert n == row["n"], f"{row['provider']}: ADR says n={n}, scorecards say {row['n']}"
        assert mean == row["mean"], f"{row['provider']}: ADR says mean={mean}, scorecards say {row['mean']}"
        assert bias == row["bias"], f"{row['provider']}: ADR says bias={bias}, scorecards say {row['bias']}"
        expected = " / ".join(f"{m:g}" for m in row["round_means"])
        assert round_means == expected, f"{row['provider']}: ADR round means {round_means!r} != {expected!r}"


# ---------------------------------------------------------------------------
# 3. The panel-level figures the ADR quotes in prose
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def summary(computed):
    data = dict(computed["summary"])
    data["ast04"] = next(r for r in computed["skills"] if r["skill"] == "AST04")
    return data


def _panel_phrases(summary: dict) -> list[str]:
    """Every prose figure the ADR's argument depends on, as the ADR must state it."""
    ast04 = summary["ast04"]
    return [
        f"pooled mean of **{summary['pooled_mean']}**",
        f"**{summary['bias_spread']}-point spread**",
        f"more than **{summary['max_round_spread']} points**",
        f"**{summary['sigma_min']} to {summary['sigma_max']}**",
        f"**{summary['implied_mean_bar_min']} to {summary['implied_mean_bar_max']}**",
        f"{summary['implied_pct_min']}% to {summary['implied_pct_max']}%",
        f"{summary['pooled_target']} ({summary['target_pct']}%)",
        f"{ast04['mean']} - {ast04['sigma']} = {ast04['lower_bound']} < {POOLED_LOWER_BOUND}",
        f"{ast04['mean']} - {ast04['sigma']}/",
    ]


def test_adr_prose_figures_match_the_computed_panel(summary):
    flat = _text(ADR)
    missing = [phrase for phrase in _panel_phrases(summary) if phrase not in flat]
    assert not missing, (
        "these figures are derived from eval/scorecards/ by eval/calibration.py but the ADR "
        f"does not state them: {missing}"
    )


def test_adr_names_the_correct_bound_without_applying_it():
    flat = _text(ADR)
    assert "mean - stdev/sqrt(n)" in flat, "the ADR must name the standard error of the mean as the correct bound"
    for alternative in ("Trimmed judge vote", "z-scoring"):
        assert alternative in flat, f"the ADR must record {alternative!r} as an alternative worth evaluating"
    assert "fresh judged run" in flat
    assert "A bar changed after seeing the data it is applied to is not a bar" in flat


def test_adr_records_the_cross_repo_incomparability():
    flat = _text(ADR)
    assert "gpt-oss-120b" in flat
    assert "single-judge score and a pooled multi-judge score are not comparable" in flat


def test_adr_is_nygard_shaped_and_accepted():
    text = ADR.read_text(encoding="utf-8")
    for heading in ("## Status", "## Context", "## Decision", "## Consequences"):
        assert heading in text, f"ADR-0005 is missing the {heading!r} section"
    assert re.search(r"^Accepted$", text, re.M), "ADR-0005 must record Status: Accepted"


def test_adr_reports_the_gate_honestly_in_both_directions():
    """The record must state the cost as plainly as the flaw.

    The count is DERIVED from the recorded scorecards rather than hard-coded, so the
    ADR cannot quietly keep claiming an old, more flattering (or more self-flagellating)
    number after a fresh run moves it. The point of the assertion is that the record
    states what the gate actually costs, not that the cost is any particular figure.
    """
    flat = _text(ADR)
    cards = sorted(SCORECARDS.glob("*.json"))
    assert cards, "no scorecards recorded — nothing to hold the ADR to"
    shipped = sum(1 for c in cards if json.loads(c.read_text())["verdict"] == "SHIP")
    assert f"{shipped} of {len(cards)} skills" in flat, (
        f"the ADR must state what the gate currently costs: {shipped} of {len(cards)} skills "
        f"clear it, and that exact phrase does not appear in ADR-0005"
    )
    assert "worth more than shipping" in flat, (
        "the ADR must still say plainly why the cost is accepted rather than engineered away"
    )


# ---------------------------------------------------------------------------
# 4. The dashboard quotes the same figures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", ["bedrock/qwen3-235b", "bedrock/nova-pro"])
def test_dashboard_calibration_note_matches_the_computed_bias(computed, provider):
    row = next(r for r in computed["providers"] if r["provider"] == provider)
    assert f"{row['bias']:+g}" in _text(DASHBOARD), (
        f"docs/skill-judge-dashboard.md quotes a bias for {provider} that eval/calibration.py "
        f"does not produce; the measured figure is {row['bias']:+g}"
    )


def test_dashboard_calibration_note_matches_the_computed_spread(summary):
    flat = _text(DASHBOARD)
    assert f"{summary['bias_spread']:g}-point spread" in flat
    assert f"{summary['sigma_min']:g}" in flat and f"{summary['sigma_max']:g}" in flat


def test_dashboard_points_at_the_record_and_the_regenerator():
    flat = _text(DASHBOARD)
    assert "eval/calibration.py" in flat
    assert "0005-judge-panel-calibration-and-the-lower-bound" in flat


# ---------------------------------------------------------------------------
# 5. The constants the ADR promises it did not touch
# ---------------------------------------------------------------------------

#: The gate as ADR-0005 found it and left it. Changing any of these is a
#: decision, and a decision needs a record that supersedes 0005.
LOCKED_CONSTANTS = {
    "POOLED_TARGET": (POOLED_TARGET, 108),
    "POOLED_LOWER_BOUND": (POOLED_LOWER_BOUND, 105),
    "MIN_ROUNDS": (MIN_ROUNDS, 4),
}


@pytest.mark.parametrize("name", sorted(LOCKED_CONSTANTS))
def test_ship_floor_constants_are_unchanged_since_the_record(name):
    actual, recorded = LOCKED_CONSTANTS[name]
    assert actual == recorded, (
        f"scripts/ship_floor.{name} is {actual}, but ADR-0005 records it as {recorded} and states "
        "that no gate constant changed. Retuning the gate requires a superseding ADR written "
        "BEFORE the run it judges — see docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md."
    )


def test_dimension_floors_are_unchanged_since_the_record():
    assert FLOORS == {"D1": 17, "D2": 13, "D3": 13, "D4": 13, "D5": 13, "D6": 13, "D7": 8, "D8": 13}


def test_adr_quotes_the_constants_it_leaves_in_force():
    flat = _text(ADR)
    assert f"`POOLED_TARGET` ({POOLED_TARGET})" in flat
    assert f"`POOLED_LOWER_BOUND` ({POOLED_LOWER_BOUND})" in flat


def test_calibration_imports_only_the_constants_it_reports():
    """Diagnostics only, checked on the code rather than on the prose.

    The script may *discuss* `aggregate_verdict` in a docstring — explaining
    which bound is in force is half its job — but it must not call it, and it
    must not pull anything from `ship_floor` beyond the two constants it prints
    for context. A calibration tool that reaches into the gate is a second gate.
    """
    tree = ast.parse(CALIBRATION_PY.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("ship_floor"):
            imported |= {alias.name for alias in node.names}
        if isinstance(node, ast.Import):
            assert all(alias.name != "scripts.ship_floor" for alias in node.names), (
                "eval/calibration.py must import named constants from ship_floor, not the module"
            )
    assert imported == {"POOLED_LOWER_BOUND", "POOLED_TARGET"}, (
        f"eval/calibration.py imports {sorted(imported)} from ship_floor; it may only read the "
        "two constants it prints for context, never the verdict machinery"
    )
    called = {
        node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert "aggregate_verdict" not in called and "verdict_of" not in called, (
        "eval/calibration.py must not compute a ship verdict"
    )
