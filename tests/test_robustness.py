"""Tests for eval/robustness.py and the published figures that rest on it.

A ship count is the easiest number in this repository to over-read, and the two
analyses in `eval/robustness.py` exist to publish its margin: what the board
looks like without any one judge, and what it looks like if the judgments that
were attempted and never pooled are refilled at the least-assuming value
available. Those figures are quoted in prose in
`docs/skill-judge-dashboard.md`, in `README.md` and in `eval/run5-refusals.md`,
and a number in prose is a claim. These tests turn each of them back into
evidence:

1. The analyses are arithmetically right on a corpus small enough to check by
   hand, and they apply the LIVE gate rather than a second copy of it.
2. `eval/robustness.json` is what the recorded scorecards produce — it cannot be
   edited into agreeing with the page.
3. Every figure the dashboard publishes in its fragility section equals what the
   corpus produces: the ship count with all judges, the ship count without each
   one, every newly-blocked `ci_lower`, and every row of the imputation table.
4. `eval/run5-refusals.md`'s what-if table is the same computation, so the two
   documents cannot drift apart from each other either.
5. The section is where a reader will meet it — ahead of the controlled results
   and the calibration tables, not at the bottom of the page.

None of these assert a *particular* headline (that dropping `qwen3-235b` costs
three ships, that `AST01` flips). They assert that whatever the corpus says is
what the page says. A future run that moves the numbers must move the page, and
these fail until it does.
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

REPO_ROOT = Path(__file__).resolve().parents[1]
ROBUSTNESS_PY = REPO_ROOT / "eval" / "robustness.py"
ROBUSTNESS_JSON = REPO_ROOT / "eval" / "robustness.json"
CALIBRATION_PY = REPO_ROOT / "eval" / "calibration.py"
DASHBOARD = REPO_ROOT / "docs" / "skill-judge-dashboard.md"
README = REPO_ROOT / "README.md"
READING = REPO_ROOT / "docs" / "reading-the-results.md"
LEDGER = REPO_ROOT / "eval" / "run5-refusals.md"
SCORECARDS = REPO_ROOT / "eval" / "scorecards"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rob = _load(ROBUSTNESS_PY, "robustness_under_test")


def _flat(path: Path) -> str:
    """File text with typographic dashes folded to ASCII and whitespace collapsed.

    Published prose uses U+2212 MINUS SIGN and U+2192 RIGHTWARDS ARROW; the
    script prints `-` and `->`. The two must compare equal or every figure fails
    for a glyph.
    """
    text = path.read_text(encoding="utf-8")
    return " ".join(text.replace("−", "-").replace("→", "->").split())


@pytest.fixture(scope="module")
def panels():
    loaded = rob.load_panels(SCORECARDS)
    if not loaded:
        pytest.skip("no scorecards recorded — there is nothing to perturb")
    return loaded


@pytest.fixture(scope="module")
def computed(panels):
    return rob.robustness(panels)


# ---------------------------------------------------------------------------
# 1. The arithmetic, on a corpus small enough to check by hand
# ---------------------------------------------------------------------------


RUBRIC_SHA = "3027f20f3181758385a1bb8c022d4041dfb4de84"
DIMS = {"D1": 18.0, "D2": 14.0, "D3": 14.0, "D4": 14.0, "D5": 14.0, "D6": 14.0, "D7": 9.0, "D8": 14.0}


def _card(skill: str, rows: list[tuple[str, float]], rounds: int, providers: list[str]) -> dict:
    return {
        "skill": skill,
        "rounds": rounds,
        "providers": providers,
        "judgments": [{"provider": p, "total": t, "scores": dict(DIMS)} for p, t in rows],
        "aggregate": {"method": "multi-round-independent-pooled", "rubric_sha": RUBRIC_SHA},
    }


def _write(tmp_path: Path, cards: list[dict]) -> Path:
    directory = tmp_path / "cards"
    directory.mkdir(parents=True, exist_ok=True)
    for card in cards:
        (directory / f"{card['skill']}.json").write_text(json.dumps(card), encoding="utf-8")
    return directory


def test_dropping_a_judge_drops_exactly_that_judges_judgments(tmp_path):
    providers = ["a", "b", "c", "d"]
    rows = [(p, 112.0) for p in providers] + [(p, 112.0) for p in providers]
    directory = _write(tmp_path, [_card("S1", rows, 2, providers)])
    data = rob.robustness(rob.load_panels(directory))
    by_provider = {entry["provider"]: entry for entry in data["leave_one_judge_out"]["judges"]}
    assert set(by_provider) == set(providers)
    for entry in by_provider.values():
        assert entry["judgments_dropped"] == 2
        assert entry["skills"][0]["n"] == 6


def test_an_exclusion_that_pushes_a_skill_under_min_rounds_blocks_it_and_says_why(tmp_path):
    """Below MIN_ROUNDS the gate refuses to compute, and that refusal is the finding.

    A judge whose removal leaves a skill with too few judgments to pool is
    carrying part of the panel's coverage, and reporting that as SHIP would be a
    lie of omission.
    """
    providers = ["a", "b", "c", "d"]  # MIN_ROUNDS is 4; dropping one leaves 3
    directory = _write(tmp_path, [_card("S1", [(p, 112.0) for p in providers], 1, providers)])
    data = rob.robustness(rob.load_panels(directory))
    assert data["as_measured"]["ships"] == 1
    entry = data["leave_one_judge_out"]["judges"][0]
    assert entry["ships"] == 0
    assert "pooled judgments" in entry["skills"][0]["reason"]


def test_a_missing_attempt_is_refilled_at_that_providers_own_mean_on_that_skill(tmp_path):
    """The imputation is stated as an assumption, so it has to be the stated one."""
    providers = ["a", "b", "c", "d"]
    rows = [
        ("a", 100.0),
        ("b", 112.0),
        ("c", 112.0),
        ("d", 112.0),
        ("a", 104.0),  # `a`'s two surviving rounds average 102.0
        ("b", 112.0),
        ("c", 112.0),
        ("d", 112.0),
        ("b", 112.0),  # round 3: `a` never answered
        ("c", 112.0),
        ("d", 112.0),
    ]
    directory = _write(tmp_path, [_card("S1", rows, 3, providers)])
    data = rob.robustness(rob.load_panels(directory))
    row = data["missing_data"]["skills"][0]
    assert row["missing"] == 1
    assert row["imputed"] == [{"provider": "a", "round": 3, "imputed_total": 102.0, "from_n": 2}]
    assert row["imputed_verdict"]["n"] == 12


def test_a_skill_with_no_gap_is_absent_from_the_sensitivity_table(tmp_path):
    providers = ["a", "b", "c", "d"]
    directory = _write(tmp_path, [_card("S1", [(p, 112.0) for p in providers], 1, providers)])
    data = rob.robustness(rob.load_panels(directory))
    assert data["missing_data"]["skills"] == []
    assert "no gap to be sensitive to" in rob.format_report(data)


def test_a_provider_with_no_surviving_judgment_is_reported_not_invented(tmp_path):
    """No own-mean to borrow means no imputation, and the attempt is named as such."""
    providers = ["a", "b", "c", "d", "e"]
    rows = [(p, 112.0) for p in providers if p != "e"] * 2
    directory = _write(tmp_path, [_card("S1", rows, 2, providers)])
    data = rob.robustness(rob.load_panels(directory))
    row = data["missing_data"]["skills"][0]
    assert row["imputed"] == []
    assert row["not_imputable"] == ["e round 1", "e round 2"]


def test_an_empty_corpus_is_refused_rather_than_summarised(tmp_path):
    with pytest.raises(rob.RobustnessError):
        rob.robustness(rob.load_panels(tmp_path / "nothing-here"))


def test_it_applies_the_live_gate_rather_than_a_second_copy_of_the_rule():
    """The one thing a robustness report must not do is re-implement the gate.

    A copy of the two clauses here would drift from `ship_floor` silently and
    would publish a margin around a rule nothing enforces. Checked on the code
    rather than on the prose: the verdict must come from
    `aggregate_verdict`, and the comparisons against `POOLED_TARGET` that decide
    SHIP must not be re-written in this file.
    """
    source = ROBUSTNESS_PY.read_text(encoding="utf-8")
    tree = ast.parse(source)
    called = {
        node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert "aggregate_verdict" in called, "the verdict must come from the live gate, not from this file"
    body = source.split('"""', 2)[-1]  # skip the module docstring, which discusses the rule
    for forbidden in ("< POOLED_TARGET", ">= POOLED_TARGET", "< FLOORS", "CONFIDENCE_K *"):
        assert forbidden not in body, f"{forbidden!r} re-implements a gate clause in eval/robustness.py"


def test_it_changes_no_gate_constant():
    """Diagnostics import constants to print them; they must never assign to one."""
    tree = ast.parse(ROBUSTNESS_PY.read_text(encoding="utf-8"))
    locked = {"FLOORS", "POOLED_TARGET", "CONFIDENCE_K", "MIN_ROUNDS", "RUBRIC_SHA", "AGG_METHOD"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                assert getattr(target, "id", None) not in locked, "eval/robustness.py must not rebind a gate constant"


# ---------------------------------------------------------------------------
# 2. The committed JSON is what the corpus produces
# ---------------------------------------------------------------------------


def test_the_committed_robustness_file_matches_the_recorded_corpus(computed):
    assert ROBUSTNESS_JSON.is_file(), "eval/robustness.json is not committed; run python3 eval/calibration.py"
    stored = json.loads(ROBUSTNESS_JSON.read_text(encoding="utf-8"))
    expected = rob.robustness_document(computed, SCORECARDS)
    assert stored == expected, (
        "eval/robustness.json disagrees with what eval/scorecards/*.json produces — "
        "regenerate it with `python3 eval/calibration.py`"
    )


def test_the_script_runs_and_emits_json():
    proc = subprocess.run(
        [sys.executable, str(ROBUSTNESS_PY), "--json", "--no-emit"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert set(payload) == {"gate", "as_measured", "leave_one_judge_out", "missing_data"}


def test_calibration_prints_the_robustness_block_and_writes_the_file():
    """The published regeneration command is `eval/calibration.py`, so it must carry both."""
    proc = subprocess.run(
        [sys.executable, str(CALIBRATION_PY), "--no-emit"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Leave one judge out" in proc.stdout
    assert "Missing-data sensitivity" in proc.stdout
    assert "--robustness-out" in CALIBRATION_PY.read_text(encoding="utf-8")


def test_a_foreign_corpus_never_overwrites_the_committed_file(tmp_path):
    """`--scorecards somewhere-else` describes that corpus; it must not republish it as ours."""
    providers = ["a", "b", "c", "d"]
    directory = _write(tmp_path, [_card("S1", [(p, 112.0) for p in providers], 1, providers)])
    before = ROBUSTNESS_JSON.read_bytes()
    rob.main(["--scorecards", str(directory)])
    assert ROBUSTNESS_JSON.read_bytes() == before


# ---------------------------------------------------------------------------
# 3. The dashboard publishes exactly these figures
# ---------------------------------------------------------------------------


def test_the_dashboard_publishes_the_as_measured_ship_count(computed):
    measured = computed["as_measured"]
    flat = _flat(DASHBOARD)
    assert f"it is {measured['ships']} of {measured['n_skills']}" in flat, (
        f"the board is {measured['ships']} of {measured['n_skills']} as measured and the "
        "fragility section must say so first"
    )


def test_the_dashboard_publishes_the_worst_leave_one_out_ship_count(computed):
    lojo = computed["leave_one_judge_out"]
    flat = _flat(DASHBOARD)
    assert f"it is {lojo['worst_ships']} of {lojo['of']}" in flat, (
        f"dropping {', '.join(lojo['worst_judges'])} takes the board to {lojo['worst_ships']} of "
        f"{lojo['of']} and the dashboard does not say so"
    )
    for judge in lojo["worst_judges"]:
        assert f"`{judge}`" in DASHBOARD.read_text(encoding="utf-8")


@pytest.mark.parametrize("index", range(6))
def test_every_leave_one_out_row_is_published(computed, index):
    """One assertion per judge, so a failure names the row that drifted."""
    judges = computed["leave_one_judge_out"]["judges"]
    if index >= len(judges):
        pytest.skip(f"panel has {len(judges)} judges")
    entry = judges[index]
    flat = _flat(DASHBOARD)
    row = re.search(
        rf"\| `{re.escape(entry['provider'])}` \| (\d+) \| \*?\*?(\d+) of (\d+)\*?\*? \| (.*?) \|",
        flat,
    )
    assert row, f"no leave-one-judge-out row for {entry['provider']} in the dashboard"
    assert int(row.group(1)) == entry["judgments_dropped"]
    assert int(row.group(2)) == entry["ships"]
    assert int(row.group(3)) == entry["of"]
    for blocked in entry["newly_blocked"]:
        assert f"`{blocked['skill']}` {blocked['ci_lower']:.1f}" in row.group(4), (
            f"{entry['provider']} newly blocks {blocked['skill']} at {blocked['ci_lower']}; "
            f"the published cell reads {row.group(4)!r}"
        )
    if not entry["newly_blocked"]:
        assert row.group(4).strip() in {"—", "-"}


def test_every_missing_data_row_is_published(computed):
    flat = _flat(DASHBOARD)
    for row in computed["missing_data"]["skills"]:
        before, after = row["as_measured"], row["imputed_verdict"]
        cell = (
            rf"\| `{re.escape(row['skill'])}` \| {row['pooled']} \| {row['attempted']} \| "
            rf"{before['mean']:.1f} -> {after['mean']:.1f} \| "
            rf"{before['ci_lower']:.1f} -> \*?\*?{after['ci_lower']:.1f}\*?\*? \| "
            rf"{before['verdict']} -> \*?\*?{after['verdict']}\*?\*? \|"
        )
        assert re.search(cell, flat), (
            f"the dashboard's imputation row for {row['skill']} does not match the corpus: "
            f"expected {before['mean']:.1f} -> {after['mean']:.1f}, "
            f"{before['ci_lower']:.1f} -> {after['ci_lower']:.1f}, "
            f"{before['verdict']} -> {after['verdict']}"
        )


def test_every_verdict_that_does_not_survive_imputation_is_named(computed):
    flat = _flat(DASHBOARD)
    changed = computed["missing_data"]["verdicts_changed"]
    for skill in changed:
        row = next(r for r in computed["missing_data"]["skills"] if r["skill"] == skill)
        assert f"`{skill}`" in flat
        assert f"{row['imputed_verdict']['ci_lower']:.1f}" in flat, (
            f"{skill} lands at ci_lower {row['imputed_verdict']['ci_lower']} under imputation and "
            "the dashboard does not publish that number"
        )
    if not changed:
        assert "No verdict changes under this imputation" in rob.format_report(computed)


def test_the_readme_carries_the_two_counts_a_reader_would_otherwise_miss(computed):
    flat = _flat(README)
    lojo = computed["leave_one_judge_out"]
    assert f"{lojo['worst_ships']} of {lojo['of']}" in flat, (
        "the README publishes the ship count; it must publish the leave-one-judge-out count beside it"
    )
    # The imputation result travels with the fragility prose it belongs to; the
    # README links there rather than restating it.
    assert "does not survive imputation" in _flat(READING)


def test_the_ledger_and_the_robustness_report_agree_on_every_what_if(computed):
    """Two documents, one computation. Neither may drift from the corpus or from the other."""
    flat = _flat(LEDGER)
    for row in computed["missing_data"]["skills"]:
        before, after = row["as_measured"], row["imputed_verdict"]
        pattern = (
            rf"\| {re.escape(row['skill'])} \| {row['pooled']} \| {before['mean']:.1f} \| "
            rf"{before['ci_lower']:.1f} \| {before['verdict']} \| {after['n']} \| {after['mean']:.1f} \| "
            rf"{after['ci_lower']:.1f} \| \*?\*?{after['verdict']}\*?\*? \|"
        )
        assert re.search(pattern, flat), (
            f"eval/run5-refusals.md's what-if row for {row['skill']} does not match the corpus"
        )


# ---------------------------------------------------------------------------
# 4. Placement: adjacent to the claim, not at the bottom
# ---------------------------------------------------------------------------


def test_the_fragility_section_comes_before_everything_it_qualifies():
    """A caveat a reader has to scroll to find is a caveat the next quoter will not have read."""
    text = DASHBOARD.read_text(encoding="utf-8")
    fragility = text.find("\n## How fragile 11 of 11 is")
    assert fragility != -1, "the dashboard has no fragility section"
    for later in (
        "\n## The controlled results",
        "\n## Judge calibration",
        "\n## The ship rule",
        "\n## Results",
    ):
        assert text.find(later) > fragility, f"{later.strip()} must come after the fragility section"


def test_the_headline_callout_points_at_the_fragility_section():
    text = DASHBOARD.read_text(encoding="utf-8")
    callout = text.find("## Judged run recorded")
    fragility = text.find("\n## How fragile 11 of 11 is")
    pointer = text.find("#how-fragile-11-of-11-is")
    assert callout != -1 and pointer != -1
    assert callout < pointer < fragility, (
        "the run callout that states 11 of 11 must link to the fragility section before the section itself begins"
    )
