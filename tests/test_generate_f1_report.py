"""`eval/generate_f1_report.py` publishes the numbers this repository is judged on,
so the tests it needs are the ones that catch a report which *looks* measured.

Four failure shapes are pinned here:

1. **A stale artifact.** `eval/f1-report.json` and `docs/f1-report.md` are
   committed. If either drifts from what the generator produces from the corpus
   on disk, the committed number is a claim about a corpus that no longer exists.
2. **A number that cannot be re-derived.** Every published precision, recall and
   F1 is recomputed here from the individual case verdicts in the same JSON. A
   figure that does not fall out of its own rows is not a measurement.
3. **A decorative bar.** A gate that has never rendered a failure is not known to
   be able to. The renderer is fed a category below 0.80 and must say `FAIL`.
4. **A padded or borrowed number.** An empty static-detectable tier must publish
   no F1 at all, and a proxy corpus must never supply the gate figure.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from detectors.f1_reporter import F1_THRESHOLD
from eval.generate_f1_report import (
    JSON_OUT,
    MARKDOWN_OUT,
    build_report,
    main,
    measure_category,
    registry_tiers,
    render_markdown,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def committed() -> dict:
    return json.loads(JSON_OUT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rows(committed) -> dict[str, dict]:
    return {row["category"]: row for row in committed["categories"]}


# --- 1. the committed artifacts are the current measurement -----------------


def test_the_committed_report_is_up_to_date():
    assert main(["--check"]) == 0, "run `python3 eval/generate_f1_report.py`"


def test_both_artifacts_are_committed():
    assert JSON_OUT.is_file() and MARKDOWN_OUT.is_file()


def test_the_generator_is_idempotent():
    first = build_report()
    second = build_report()
    assert first == second


# --- 2. every published number re-derives from its own rows -----------------


def _confusion_from_verdicts(checks: list[dict]) -> tuple[int, int, int, int]:
    tp = fp = fn = tn = 0
    for check in checks:
        for verdict in check["case_verdicts"]:
            predicted, labeled = verdict["predicted_vulnerable"], verdict["labeled_vulnerable"]
            if predicted and labeled:
                tp += 1
            elif predicted and not labeled:
                fp += 1
            elif labeled:
                fn += 1
            else:
                tn += 1
    return tp, fp, fn, tn


@pytest.mark.parametrize(
    "scope_key,covers", [("scenario_level", "full"), ("artifact_signal_only", "artifact-signal-only")]
)
def test_every_published_block_recomputes_from_its_own_case_verdicts(committed, scope_key, covers):
    """The published precision/recall/F1 must fall out of the rows above it."""
    checked = 0
    for row in committed["categories"]:
        block = row[scope_key]
        scoped = [c for c in row["checks"] if c["covers"] == covers]
        if block is None:
            assert not scoped, f"{row['category']} has {covers} checks but publishes no {scope_key} block"
            continue
        tp, fp, fn, tn = _confusion_from_verdicts(scoped)
        assert (tp, fp, fn, tn) == (
            block["true_positives"],
            block["false_positives"],
            block["false_negatives"],
            block["true_negatives"],
        ), row["category"]
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        assert block["precision"] == pytest.approx(precision, abs=1e-4)
        assert block["recall"] == pytest.approx(recall, abs=1e-4)
        assert block["f1"] == pytest.approx(f1, abs=1e-4)
        checked += 1
    assert checked, f"no category published a {scope_key} block; the assertions above ran on nothing"


def test_the_case_count_in_each_block_matches_the_verdicts_listed(committed):
    for row in committed["categories"]:
        for scope_key, covers in (("scenario_level", "full"), ("artifact_signal_only", "artifact-signal-only")):
            block = row[scope_key]
            if block is None:
                continue
            listed = sum(len(c["case_verdicts"]) for c in row["checks"] if c["covers"] == covers)
            assert block["cases"] == listed, (row["category"], scope_key)


# --- 3. the gate can render a failure ---------------------------------------


def _doctor(report: dict, category: str, tp: int, fp: int, fn: int) -> dict:
    """Return a copy of ``report`` with one category's scenario-level block replaced."""
    doctored = copy.deepcopy(report)
    row = next(r for r in doctored["categories"] if r["category"] == category)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    row["scenario_level"] = {
        "checks": ["X"],
        "cases": tp + fp + fn,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": 0,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }
    row["status"] = "pass" if f1 >= F1_THRESHOLD else "fail"
    return doctored


def test_a_category_below_the_floor_renders_as_a_failure():
    """A bar that has never rendered a failure is not known to be able to."""
    doctored = _doctor(build_report(), "AST04", tp=1, fp=3, fn=3)
    rendered = render_markdown(doctored)
    row = next(line for line in rendered.splitlines() if line.startswith("| `AST04`"))
    assert "FAIL" in row, row
    assert "⚠" in row, row
    assert "**1 fall below it** (`AST04`)" in rendered


def test_one_failing_category_never_changes_another_categorys_row():
    """Per-category, not averaged: the whole point of `detectors/f1_reporter.py`."""
    baseline = build_report()
    doctored = _doctor(baseline, "AST04", tp=1, fp=3, fn=3)
    for before, after in zip(baseline["categories"], doctored["categories"]):
        if before["category"] == "AST04":
            continue
        assert before == after


def test_no_suite_wide_average_is_published(committed):
    text = json.dumps(committed).lower() + MARKDOWN_OUT.read_text(encoding="utf-8").lower()
    for forbidden in ("suite f1", "overall f1", "average f1", "mean f1", "aggregate f1"):
        assert forbidden not in text, f"the report publishes a {forbidden!r}"


# --- 4. nothing is padded, nothing is borrowed ------------------------------

EMPTY_TIER_CATEGORIES = ("AST05", "AST07", "AST09")


@pytest.mark.parametrize("category", EMPTY_TIER_CATEGORIES)
def test_an_empty_static_detectable_tier_publishes_no_f1(category, rows):
    """The locked rule: declared-and-uncovered, never a number, never padded."""
    row = rows[category]
    assert row["registry"]["static_detectable"] == []
    assert row["scenario_level"] is None
    assert row["status"] == "declared-and-uncovered"


def test_the_empty_tier_list_is_exactly_what_the_registry_says():
    """Guards the parametrize list above against going stale in either direction."""
    tiers = registry_tiers()
    empty = tuple(sorted(c for c, t in tiers.items() if not t["static-detectable"]))
    assert empty == EMPTY_TIER_CATEGORIES


def test_ast05_publishes_a_proxy_number_and_an_uncovered_gate_at_the_same_time(rows):
    """Both statements are true and the report has to make both."""
    row = rows["AST05"]
    assert row["artifact_signal_only"]["cases"] == 6
    assert row["scenario_level"] is None
    assert row["status"] == "declared-and-uncovered"
    assert all(c["covers"] == "artifact-signal-only" for c in row["checks"])


def test_a_proxy_check_never_enters_the_scenario_level_block(committed):
    for row in committed["categories"]:
        block = row["scenario_level"]
        if block is None:
            continue
        proxies = {c["corpus_check"] for c in row["checks"] if c["covers"] == "artifact-signal-only"}
        assert not (set(block["checks"]) & proxies), row["category"]


@pytest.mark.parametrize("category", [f"AST{n:02d}" for n in range(1, 11)])
def test_every_corpus_meets_the_size_formula_and_is_class_balanced(category, rows):
    corpus = rows[category]["corpus"]
    assert corpus["meets_formula"], corpus
    if corpus["cases"]:
        assert corpus["class_balance"]["vulnerable"] == corpus["class_balance"]["clean"], corpus


def test_a_broken_tier_lock_blocks_publication_rather_than_publishing(monkeypatch):
    """S-011: republishing an F1 against a re-tiered corpus is the thing the lock exists to stop."""
    import eval.generate_f1_report as generator

    monkeypatch.setattr(generator, "check_manifest_tier_locks", lambda _m: ["AST04: tier-lock mismatch"])
    with pytest.raises(generator.F1ReportError, match="tier lock"):
        generator.build_report()


def test_a_case_that_falls_out_of_the_run_is_refused_rather_than_reported(monkeypatch):
    """A denominator smaller than the manifest declares must raise, not publish."""
    import eval.generate_f1_report as generator

    manifest = yaml.safe_load((REPO_ROOT / "fixtures" / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["categories"]["AST04"]["cases"].append(
        {
            "id": "AST04-GHOST",
            "scenario_id": "AST04-S1",
            "label": "clean",
            "path": "fixtures/AST04/C2-yaml-frontmatter-injection/SKILL.md",
        }
    )

    class _ShortResult:
        checks: tuple = ()

        def cases(self, covers=None):
            return 10

    monkeypatch.setattr(generator, "run_corpus", lambda _c, _m: _ShortResult())
    monkeypatch.setattr(generator, "clean_case_leakage", lambda _c, _m: {"clean_cases": 0, "firings": []})
    with pytest.raises(generator.F1ReportError, match="denominator"):
        measure_category("AST04", manifest, registry_tiers())


# --- the leakage column is a real measurement, not a constant ---------------


def test_the_clean_leakage_column_counts_every_check_not_only_the_labeled_one(rows):
    """Pins that the column is computed over `run_all`, so it can be non-zero."""
    row = rows["AST01"]
    leakage = row["any_check_firing_on_a_clean_case"]
    assert leakage["clean_cases"] == 8
    assert leakage["firings"] == [], leakage["firings"]


def test_leakage_renders_when_a_check_does_fire_on_a_clean_case():
    doctored = copy.deepcopy(build_report())
    row = next(r for r in doctored["categories"] if r["category"] == "AST01")
    row["any_check_firing_on_a_clean_case"] = {
        "clean_cases": 8,
        "firings": [{"case": "AST01-C4", "check": "AST01-websocket-c2", "evidence": "ws:// in a clean package"}],
    }
    rendered = render_markdown(doctored)
    assert "1/8" in rendered
    assert "`AST01-C4` → `AST01-websocket-c2`" in rendered
