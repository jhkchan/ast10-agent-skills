"""Tests for eval/generate_dashboard.py.

The generator's two load-bearing promises:

1. It never believes a stored verdict. Grade and SHIP/BLOCKED are recomputed
   from ``aggregate.judgments`` through the same ``ship_floor.aggregate_verdict``
   the ship gate calls, so a scorecard cannot publish a grade its own numbers do
   not support.
2. An empty scorecard directory renders as an explicit "no judged run recorded
   yet" state, never as a table of zeros and never by omitting the table.

A third promise belongs to the published page rather than to the generator, and
it changed shape when run 5 landed. Between ADR-0006 and run 5 the committed
Results table was run 4's, issued under a clause the gate no longer applies, so
the table was FROZEN and the assertion was that the freeze hid nothing. Run 5 was
scored under the rule in force, so the table is a regeneration again and
``--check`` is once more the right question. The claim the freeze was carrying
does not disappear with it:
``test_the_gate_change_moved_no_verdict_on_the_corpus_it_did_not_judge`` re-derives
every run-4 verdict through today's gate against the frozen archive. That is the
arithmetic ADR-0006 rests its "zero verdicts change" on, and it stays checkable
long after run 4 stops being the page's subject.
"""

from __future__ import annotations

import importlib.util
import json
import math
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
    """A self-consistent aggregate block, exactly as ship_floor recomputes it.

    Written the shape a post-ADR-0006 run writes, `sem` and `ci_lower` included,
    so these fixtures exercise the STRICT half of the drift check: the gate
    tolerates those two keys being absent (that dates a scorecard to run 4 or
    earlier) but never tolerates them being wrong.
    """
    mean = round(statistics.fmean(totals), 1)
    stdev = round(statistics.stdev(totals), 2)
    sem = round(stdev / math.sqrt(len(totals)), 2)
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
        "sem": sem,
        "ci_lower": round(mean - 1.0 * sem, 1),
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
    assert set(gen.PLACEHOLDER_SKILLS) == shipped, (
        "every shipped skill must have a row, judged or not — and the roster is keyed by the "
        "directory name because that is what a scorecard's `skill` field carries"
    )


def test_placeholder_roster_is_in_the_namespace_scorecards_key_on():
    """The bug this pins is a namespace split, and it was invisible in the output's shape.

    A scorecard's `skill` field is the directory under `skills/` (`AST01`); that
    same skill's `SKILL.md` frontmatter calls it `ast01-malicious-skills`. While
    `PLACEHOLDER_SKILLS` held the frontmatter names, `render_block`'s
    "which of these did no scorecard cover?" set difference matched nothing at
    all: the committed board carried its eleven judged rows plus ten more rows
    asserting that ten of those same eleven skills were NOT YET JUDGED — 21 rows
    for 11 skills, every extra one false.

    Asserting the tuple against the shipped directories is not enough on its own,
    because a future roster could be renamed on one side only. This asserts the
    property that actually matters: every recorded scorecard's own key is a
    member of the placeholder roster, so the two can never again describe the
    same skill in two vocabularies.
    """
    keyed = {
        json.loads(path.read_text(encoding="utf-8")).get("skill")
        for directory in sorted((REPO_ROOT / "eval").glob("scorecards*"))
        if directory.is_dir()
        for path in sorted(directory.glob("*.json"))
    }
    keyed.discard(None)
    assert keyed, "no recorded scorecards — the namespace claim is unverifiable"
    assert keyed <= set(gen.PLACEHOLDER_SKILLS), (
        f"scorecards key on {sorted(keyed - set(gen.PLACEHOLDER_SKILLS))}, which the placeholder "
        "roster does not contain — those skills will render twice, once judged and once as "
        "NOT YET JUDGED"
    )


def test_a_full_corpus_renders_one_row_per_skill_and_no_phantom_placeholders():
    """Eleven judged skills must produce eleven rows, not eleven plus a shadow roster."""
    cards = gen.load_scorecards(REPO_ROOT / "eval" / "scorecards")
    if not cards:
        pytest.skip("no scorecards recorded")
    block = gen.render_block(cards)
    assert "NOT YET JUDGED" not in block, (
        "every skill on the roster is judged, so no placeholder row belongs on the board"
    )
    rows = [line for line in block.splitlines() if line.startswith("| `")]
    assert len(rows) == len(cards) == len(gen.PLACEHOLDER_SKILLS)


def _published_rows() -> dict[str, str]:
    """Skill -> verdict cell, read out of the committed Results block."""
    text = (REPO_ROOT / "docs" / "skill-judge-dashboard.md").read_text(encoding="utf-8")
    block = text.split(gen.BEGIN, 1)[1].split(gen.END, 1)[0]
    rows: dict[str, str] = {}
    for line in block.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 7 and cells[0].startswith("`") and cells[-1] not in ("Verdict", "NOT YET JUDGED"):
            rows[cells[0].strip("`")] = cells[-1]
    assert rows, "no judged rows found in the committed Results block"
    return rows


def _last_corpus_judged_under_the_retired_clause() -> Path:
    """The newest recorded run scored before ADR-0006, found by reading the bytes.

    ADR-0006 added `sem` and `ci_lower` to every aggregate written under it, so a
    corpus carrying neither was scored under the retired clause. Deriving the
    directory this way means the check keeps pointing at the evidence rather than
    at whichever run is topical: when run 5 is archived it will carry both keys and
    this will still find run 4.
    """
    dated: list[tuple[int, Path]] = []
    for directory in sorted((REPO_ROOT / "eval").glob("scorecards*")):
        if not directory.is_dir():
            continue
        cards = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))]
        aggregates = [c["aggregate"] for c in cards if c.get("aggregate")]
        if not aggregates or any("ci_lower" in agg for agg in aggregates):
            continue
        suffix = directory.name.rsplit("run", 1)[-1]
        dated.append((int(suffix) if suffix.isdigit() else 0, directory))
    assert dated, "no recorded corpus predates ADR-0006; its zero-verdicts-change claim is unverifiable"
    return max(dated)[1]


def test_the_committed_results_table_is_the_live_corpus_under_the_rule_in_force():
    """The published board is what today's generator emits from today's corpus.

    This was a freeze check for exactly one run. ADR-0006 changed the gate's second
    clause on 2026-08-24, after run 4 was published, so regenerating would have
    restated a run-4 verdict in the words of a rule that never judged it, and the
    table stayed as issued. Run 5 was scored under the rule in force, which ends
    the freeze and restores the stronger question: is the committed table exactly
    what the generator produces from `eval/scorecards/` today?

    Both halves are asserted, because `--check` alone would pass on a table
    regenerated from a corpus whose stored statistics lie. Every verdict published
    here is also re-derived through `aggregate_verdict`, so a row reading SHIP has
    been recomputed rather than transcribed. A stale table and a fabricated one
    fail differently, and both fail.
    """
    from scripts.ship_floor import aggregate_verdict

    assert gen.main(["--check"]) == 0, (
        "the committed Results table is not what eval/generate_dashboard.py produces from "
        "eval/scorecards/ — run `python3 eval/generate_dashboard.py`. The table was frozen only "
        "while the published corpus predated the rule in force; run 5 was judged under it, so "
        "staleness is no longer excused."
    )

    published = _published_rows()
    cards = {str(c.get("skill")): c for c in gen.load_scorecards()}
    assert set(published) == set(cards), "the committed table and eval/scorecards/ describe different skills"
    for skill, cell in published.items():
        recomputed, _why = aggregate_verdict(skill, cards[skill].get("aggregate"))
        assert cell.split(" — ")[0] == recomputed, (
            f"{skill}: the published table says {cell.split(' — ')[0]!r} but the rule in force computes "
            f"{recomputed!r} from that scorecard's own judgments"
        )


def test_the_gate_change_moved_no_verdict_on_the_corpus_it_did_not_judge():
    """ADR-0006's central claim — "Zero verdicts change" — kept permanently checkable.

    The claim is arithmetic over a frozen corpus: run 4 was scored under
    `mean − stdev ≥ 105`, and running today's `mean − 1.0 × stdev/√n ≥ 108` across
    those same bytes must reproduce every verdict as issued. While run 4 was live
    the freeze check made that claim in passing. Now that run 5 has replaced it the
    claim needs a home of its own, or it stops being tested the moment it stops
    being topical — and it is the whole reason a reader may read 11 of 11 as a
    statement about the skills rather than about the rule.

    The corpus is found, not named, and so is the row: whichever skill the retired
    clause blocked on its own must still be BLOCKED, by the new clause, for the new
    clause's stated reason.
    """
    from scripts.ship_floor import POOLED_LOWER_BOUND, aggregate_verdict

    directory = _last_corpus_judged_under_the_retired_clause()
    cards = {}
    for path in sorted(directory.glob("*.json")):
        card = json.loads(path.read_text(encoding="utf-8"))
        cards[card["skill"]] = card

    for skill, card in cards.items():
        recomputed, _why = aggregate_verdict(skill, card.get("aggregate"))
        assert recomputed == card["verdict"], (
            f"eval/{directory.name}/{skill}.json was issued {card['verdict']} under the retired clause "
            f"and the rule in force computes {recomputed}. ADR-0006 was accepted on the arithmetic that "
            "the change moves no verdict; if that is false, the record is wrong and so is every page "
            "citing it."
        )

    blocked_by_the_retired_clause = [
        skill
        for skill, card in cards.items()
        if (agg := card.get("aggregate"))
        and agg["mean"] >= 108
        and agg["lower_bound"] < POOLED_LOWER_BOUND
        and all(agg["dim_means"][d] >= f for d, f in gen.FLOORS.items())
    ]
    assert len(blocked_by_the_retired_clause) == 1, (
        f"expected exactly one skill in eval/{directory.name}/ blocked by the retired clause alone, found "
        f"{blocked_by_the_retired_clause} — it is the worked example ADR-0005 and ADR-0006 both argue from"
    )
    example = blocked_by_the_retired_clause[0]
    assert cards[example]["verdict"] == "BLOCKED"
    recomputed, why = aggregate_verdict(example, cards[example]["aggregate"])
    assert recomputed == "BLOCKED" and "confidence bound" in why, (
        f"{example} was blocked by a spread statistic and must still be blocked by the confidence bound "
        f"— a change of reason, not of outcome. Today's gate says: {recomputed} — {why}"
    )


# ---------------------------------------------------------------------------
# recompute, never trust
# ---------------------------------------------------------------------------


def _results_row(dashboard: Path, skill: str) -> str:
    """The Results-table row for `skill`, scoped to the generated block.

    Scoped, not grepped. The page carries other tables that name the same skills
    — the robustness section publishes a `ci_lower` row per skill with a gap —
    so "the first line mentioning AST06" stopped being the generated row the
    moment the page grew a second table, and silently asserted against the wrong
    one rather than failing.
    """
    text = dashboard.read_text(encoding="utf-8")
    block = text.split(gen.BEGIN, 1)[1].split(gen.END, 1)[0]
    prefix = f"| `{skill}` |"
    rows = [line for line in block.splitlines() if line.startswith(prefix)]
    assert len(rows) == 1, f"expected exactly one Results row for {skill}, found {len(rows)}"
    return rows[0]


def test_a_passing_scorecard_renders_ship_and_grade_a(tmp_path, dashboard):
    cards = tmp_path / "cards"
    _write_card(cards, "AST01", _aggregate([109, 111, 108, 112]))
    gen.main(["--dashboard", str(dashboard), "--scorecards", str(cards)])
    text = dashboard.read_text(encoding="utf-8")
    row = _results_row(dashboard, "AST01")
    assert row.endswith("| A | SHIP |")
    assert "1 of 11 skills judged; 1 clears the ship rule" in text


def test_a_stored_verdict_is_never_copied(tmp_path, dashboard):
    """A scorecard claiming SHIP on failing numbers must render BLOCKED."""
    cards = tmp_path / "cards"
    aggregate = _aggregate([80, 82, 79, 81])
    aggregate["verdict"] = "SHIP"  # the lie
    _write_card(cards, "AST02", aggregate)
    gen.main(["--dashboard", str(dashboard), "--scorecards", str(cards)])
    row = _results_row(dashboard, "AST02")
    assert "BLOCKED" in row
    assert "pooled mean 80.5 < target 108" in row


def test_stats_that_disagree_with_the_judgments_block(tmp_path, dashboard):
    cards = tmp_path / "cards"
    aggregate = _aggregate([109, 111, 108, 112])
    aggregate["mean"] = 118.0  # inflated, contradicted by `judgments`
    _write_card(cards, "AST03", aggregate)
    gen.main(["--dashboard", str(dashboard), "--scorecards", str(cards)])
    row = _results_row(dashboard, "AST03")
    assert "BLOCKED" in row
    assert "stored stats disagree with recompute" in row
    assert "118" not in row, "the inflated stored mean must not be rendered"


def test_a_wrong_rubric_sha_blocks(tmp_path, dashboard):
    cards = tmp_path / "cards"
    aggregate = _aggregate([109, 111, 108, 112])
    aggregate["rubric_sha"] = "0" * 40
    _write_card(cards, "AST04", aggregate)
    gen.main(["--dashboard", str(dashboard), "--scorecards", str(cards)])
    row = _results_row(dashboard, "AST04")
    assert "BLOCKED" in row and "rubric_sha" in row


def test_fewer_than_min_rounds_blocks(tmp_path, dashboard):
    cards = tmp_path / "cards"
    _write_card(cards, "AST05", _aggregate([110, 111]))
    gen.main(["--dashboard", str(dashboard), "--scorecards", str(cards)])
    row = _results_row(dashboard, "AST05")
    assert "BLOCKED" in row and "pooled judgments" in row


def test_a_dimension_below_its_floor_blocks_a_high_total(tmp_path, dashboard):
    """The floors exist so a strong total cannot buy past a weak dimension."""
    cards = tmp_path / "cards"
    dims = dict(PASSING_DIMS, D1=12.0)  # floor is 17
    _write_card(cards, "AST06", _aggregate([115, 116, 114, 117], dims))
    gen.main(["--dashboard", str(dashboard), "--scorecards", str(cards)])
    row = _results_row(dashboard, "AST06")
    assert "BLOCKED" in row
    assert "dimension means below floor: D1" in row
    assert "`D1` 12/17 ⚠" in row


# ---------------------------------------------------------------------------
# table shape
# ---------------------------------------------------------------------------


def test_unjudged_skills_keep_their_row(tmp_path, dashboard):
    cards = tmp_path / "cards"
    _write_card(cards, "AST01", _aggregate([109, 111, 108, 112]))
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
    _write_card(cards, "AST08", _aggregate([109, 111, 108, 112]))
    args = ["--dashboard", str(dashboard), "--scorecards", str(cards)]
    gen.main(args)
    once = dashboard.read_text(encoding="utf-8")
    gen.main(args)
    assert dashboard.read_text(encoding="utf-8") == once
    assert gen.main(args + ["--check"]) == 0


def test_check_flag_reports_drift_without_writing(tmp_path, dashboard):
    cards = tmp_path / "cards"
    _write_card(cards, "AST09", _aggregate([109, 111, 108, 112]))
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
