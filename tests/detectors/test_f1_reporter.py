"""Tests for detectors.f1_reporter — spec.md S-007 (T-2.4)."""

from __future__ import annotations

from detectors.engine import CategoryResult
from detectors.f1_reporter import F1_THRESHOLD, report_category, report_suite


def _result(category: str, f1: float | None, **overrides) -> CategoryResult:
    base = dict(
        category=category,
        true_positives=0,
        false_positives=0,
        false_negatives=0,
        true_negatives=0,
        precision=None if f1 is None else 0.0,
        recall=None if f1 is None else 0.0,
        f1=f1,
        scored_case_ids=(),
        declared_uncovered=(),
        agent_judgable=(),
    )
    base.update(overrides)
    return CategoryResult(**base)


def test_f1_threshold_is_locked_at_point_eight():
    """spec.md Gate B half 2: 'F1 >= 0.80 per category'."""
    assert F1_THRESHOLD == 0.80


def test_category_below_threshold_fails_independently_of_passing_sibling():
    """S-007: a below-threshold category fails Gate B half 2 alone; siblings unaffected."""
    failing = _result("AST04", 8 / 12)  # 0.6667, below 0.80
    passing = _result("AST01", 0.85)

    rows = report_suite([failing, passing])
    by_category = {row.category: row for row in rows}

    assert by_category["AST04"].status == "fail"
    assert by_category["AST01"].status == "pass"
    assert (
        by_category["AST01"].f1 == 0.85
    )  # sibling's score is untouched by the failure


def test_report_shows_per_category_breakdown_with_no_suite_wide_average():
    """S-007: report shows the per-category breakdown, no suite-wide average anywhere."""
    rows = report_suite([_result("AST04", 0.62), _result("AST01", 0.9)])

    assert isinstance(rows, list)
    assert len(rows) == 2
    banned = {"average", "mean", "overall", "suite_f1", "aggregate"}
    for row in rows:
        field_names = set(row.__dataclass_fields__)
        assert not field_names & banned


def test_empty_declared_detectable_tier_reports_declared_and_uncovered():
    """gate-4: an empty static-detectable tier publishes no F1, status declared-and-uncovered."""
    result = _result("AST09", None, declared_uncovered=("AST09-orphaned-skill",))

    row = report_category(result)

    assert row.f1 is None
    assert row.status == "declared-and-uncovered"
