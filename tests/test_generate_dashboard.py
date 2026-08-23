"""Tests for eval/generate_dashboard.py.

The generator's two load-bearing promises:

1. It never believes a stored verdict. Grade and SHIP/BLOCKED are recomputed
   from ``aggregate.judgments`` through the same ``ship_floor.aggregate_verdict``
   the ship gate calls, so a scorecard cannot publish a grade its own numbers do
   not support.
2. An empty scorecard directory renders as an explicit "no judged run recorded
   yet" state, never as a table of zeros and never by omitting the table.
"""

from __future__ import annotations

import importlib.util
import json
import statistics
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_dashboard_under_test", REPO_ROOT / "eval" / "generate_dashboard.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gen = _load_generator()

RUBRIC_SHA = "3027f20f3181758385a1bb8c022d4041dfb4de84"
PASSING_DIMS = {
    "D1": 18.0,
    "D2": 14.0,
    "D3": 14.0,
    "D4": 14.0,
    "D5": 14.0,
    "D6": 14.0,
    "D7": 9.0,
    "D8": 14.0,
}


def _aggregate(totals: list[int], dim_means: dict | None = None) -> dict:
    """A self-consistent aggregate block, exactly as ship_floor recomputes it."""
    mean = round(statistics.fmean(totals), 1)
    stdev = round(statistics.stdev(totals), 2)
    return {
        "method": "multi-round-independent-pooled",
        "rubric_sha": RUBRIC_SHA,
        "judgments": totals,
        "n": len(totals),
        "mean": mean,
        "median": round(statistics.median(totals), 1),
        "min": min(totals),
        "max": max(totals),
        "range": max(totals) - min(totals),
        "stdev": stdev,
        "lower_bound": round(mean - stdev, 1),
        "dim_means": dict(dim_means or PASSING_DIMS),
        "dim_n": len(totals),
    }


def _write_card(directory: Path, skill: str, aggregate: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{skill}.json"
    path.write_text(json.dumps({"skill": skill, "aggregate": aggregate}, indent=2), encoding="utf-8")
    return path


@pytest.fixture()
def dashboard(tmp_path: Path) -> Path:
    """A copy of the real dashboard, so tests never mutate the committed one."""
    target = tmp_path / "dash.md"
    target.write_text(
        (REPO_ROOT / "docs" / "skill-judge-dashboard.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return target


# ---------------------------------------------------------------------------
# empty state
# ---------------------------------------------------------------------------


def test_empty_scorecard_dir_renders_the_not_yet_judged_state(tmp_path):
    block = gen.render_block(gen.load_scorecards(tmp_path / "nothing-here"))
    assert "No judged run recorded yet" in block
    assert block.count("NOT YET JUDGED") == len(gen.PLACEHOLDER_SKILLS)
    assert "0.0" not in block, "an unjudged skill must not render as a zero score"


def test_placeholder_roster_matches_the_shipped_skills():
    shipped = {p.parent.name for p in (REPO_ROOT / "skills").glob("*/SKILL.md")}
    names = set()
    for skill_dir in sorted(shipped):
        text = (REPO_ROOT / "skills" / skill_dir / "SKILL.md").read_text(encoding="utf-8")
        for line in text.splitlines()[1:]:
            if line.startswith("name:"):
                names.add(line.split(":", 1)[1].strip())
                break
    assert set(gen.PLACEHOLDER_SKILLS) == names


def test_committed_dashboard_is_up_to_date():
    """`--check` must be clean on the committed tree, so CI can enforce it."""
    assert gen.main(["--check"]) == 0


# ---------------------------------------------------------------------------
# recompute, never trust
# ---------------------------------------------------------------------------


def test_a_passing_scorecard_renders_ship_and_grade_a(tmp_path, dashboard):
    cards = tmp_path / "cards"
    _write_card(cards, "ast01-malicious-skills", _aggregate([109, 111, 108, 112]))
    gen.main(["--dashboard", str(dashboard), "--scorecards", str(cards)])
    text = dashboard.read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if "ast01-malicious-skills" in line)
    assert row.endswith("| A | SHIP |")
    assert "1 of 11 skills judged; 1 clears the ship rule" in text


def test_a_stored_verdict_is_never_copied(tmp_path, dashboard):
    """A scorecard claiming SHIP on failing numbers must render BLOCKED."""
    cards = tmp_path / "cards"
    aggregate = _aggregate([80, 82, 79, 81])
    aggregate["verdict"] = "SHIP"  # the lie
    _write_card(cards, "ast02-supply-chain-compromise", aggregate)
    gen.main(["--dashboard", str(dashboard), "--scorecards", str(cards)])
    row = next(
        line
        for line in dashboard.read_text(encoding="utf-8").splitlines()
        if "ast02-supply-chain-compromise" in line and "|" in line
    )
    assert "BLOCKED" in row
    assert "pooled mean 80.5 < target 108" in row


def test_stats_that_disagree_with_the_judgments_block(tmp_path, dashboard):
    cards = tmp_path / "cards"
    aggregate = _aggregate([109, 111, 108, 112])
    aggregate["mean"] = 118.0  # inflated, contradicted by `judgments`
    _write_card(cards, "ast03-over-privileged-skills", aggregate)
    gen.main(["--dashboard", str(dashboard), "--scorecards", str(cards)])
    row = next(
        line
        for line in dashboard.read_text(encoding="utf-8").splitlines()
        if "ast03-over-privileged-skills" in line and "|" in line
    )
    assert "BLOCKED" in row
    assert "stored stats disagree with recompute" in row
    assert "118" not in row, "the inflated stored mean must not be rendered"


def test_a_wrong_rubric_sha_blocks(tmp_path, dashboard):
    cards = tmp_path / "cards"
    aggregate = _aggregate([109, 111, 108, 112])
    aggregate["rubric_sha"] = "0" * 40
    _write_card(cards, "ast04-insecure-metadata", aggregate)
    gen.main(["--dashboard", str(dashboard), "--scorecards", str(cards)])
    row = next(
        line
        for line in dashboard.read_text(encoding="utf-8").splitlines()
        if "ast04-insecure-metadata" in line and "|" in line
    )
    assert "BLOCKED" in row and "rubric_sha" in row


def test_fewer_than_min_rounds_blocks(tmp_path, dashboard):
    cards = tmp_path / "cards"
    _write_card(cards, "ast05-untrusted-external-instructions", _aggregate([110, 111]))
    gen.main(["--dashboard", str(dashboard), "--scorecards", str(cards)])
    row = next(
        line
        for line in dashboard.read_text(encoding="utf-8").splitlines()
        if "ast05-untrusted-external-instructions" in line and "|" in line
    )
    assert "BLOCKED" in row and "pooled judgments" in row


def test_a_dimension_below_its_floor_blocks_a_high_total(tmp_path, dashboard):
    """The floors exist so a strong total cannot buy past a weak dimension."""
    cards = tmp_path / "cards"
    dims = dict(PASSING_DIMS, D1=12.0)  # floor is 17
    _write_card(cards, "ast06-weak-isolation", _aggregate([115, 116, 114, 117], dims))
    gen.main(["--dashboard", str(dashboard), "--scorecards", str(cards)])
    row = next(
        line
        for line in dashboard.read_text(encoding="utf-8").splitlines()
        if "ast06-weak-isolation" in line and "|" in line
    )
    assert "BLOCKED" in row
    assert "dimension means below floor: D1" in row
    assert "`D1` 12/17 ⚠" in row


# ---------------------------------------------------------------------------
# table shape
# ---------------------------------------------------------------------------


def test_unjudged_skills_keep_their_row(tmp_path, dashboard):
    cards = tmp_path / "cards"
    _write_card(cards, "ast01-malicious-skills", _aggregate([109, 111, 108, 112]))
    gen.main(["--dashboard", str(dashboard), "--scorecards", str(cards)])
    text = dashboard.read_text(encoding="utf-8")
    assert text.count("NOT YET JUDGED") == len(gen.PLACEHOLDER_SKILLS) - 1
    for skill in gen.PLACEHOLDER_SKILLS:
        assert f"`{skill}`" in text


def test_only_the_marked_region_is_rewritten(tmp_path, dashboard):
    before = dashboard.read_text(encoding="utf-8")
    cards = tmp_path / "cards"
    _write_card(cards, "advisory", _aggregate([109, 111, 108, 112]))
    gen.main(["--dashboard", str(dashboard), "--scorecards", str(cards)])
    after = dashboard.read_text(encoding="utf-8")
    head_before, _, _ = before.partition(gen.BEGIN)
    head_after, _, _ = after.partition(gen.BEGIN)
    assert head_before == head_after
    assert before.split(gen.END)[1] == after.split(gen.END)[1]


def test_generator_is_idempotent(tmp_path, dashboard):
    cards = tmp_path / "cards"
    _write_card(cards, "ast08-poor-scanning", _aggregate([109, 111, 108, 112]))
    args = ["--dashboard", str(dashboard), "--scorecards", str(cards)]
    gen.main(args)
    once = dashboard.read_text(encoding="utf-8")
    gen.main(args)
    assert dashboard.read_text(encoding="utf-8") == once
    assert gen.main(args + ["--check"]) == 0


def test_check_flag_reports_drift_without_writing(tmp_path, dashboard):
    cards = tmp_path / "cards"
    _write_card(cards, "ast09-no-governance", _aggregate([109, 111, 108, 112]))
    before = dashboard.read_text(encoding="utf-8")
    assert gen.main(["--dashboard", str(dashboard), "--scorecards", str(cards), "--check"]) == 1
    assert dashboard.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# failure modes
# ---------------------------------------------------------------------------


def test_missing_markers_raise_rather_than_guessing(tmp_path):
    with pytest.raises(gen.ScorecardError, match="markers"):
        gen.rewrite("# a dashboard with no markers\n", "anything")


def test_malformed_scorecard_raises(tmp_path):
    cards = tmp_path / "cards"
    cards.mkdir()
    (cards / "broken.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(gen.ScorecardError, match="not valid JSON"):
        gen.load_scorecards(cards)


def test_non_json_files_are_ignored(tmp_path):
    cards = tmp_path / "cards"
    cards.mkdir()
    (cards / "README.md").write_text("# not a scorecard", encoding="utf-8")
    assert gen.load_scorecards(cards) == []


@pytest.mark.parametrize(
    "mean,grade",
    [(120, "A"), (108, "A"), (107.9, "B"), (96, "B"), (95, "C"), (84, "C"), (83, "D"), (72, "D"), (71, "F"), (0, "F")],
)
def test_grade_bands(mean, grade):
    assert gen.grade_of(mean) == grade
