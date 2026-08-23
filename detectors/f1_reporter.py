"""Per-category F1 gate reporter (spec.md Gate B half 2).

Publishes each category's F1 verdict independently of every other category
-- no suite-wide average is ever computed or included in the output
(spec.md S-007: "the release is blocked per-category, not by suite-wide
averaged F1 ... the report shows the per-category breakdown"). A category
whose declared-detectable tier is empty (no static-detectable fixtures)
publishes no F1 number at all and is reported ``declared-and-uncovered``
(spec.md gate-4).
"""

from __future__ import annotations

from dataclasses import dataclass

from detectors.engine import CategoryResult

F1_THRESHOLD = 0.80  # locked: spec.md Gate B half 2, "F1 >= 0.80 per category"


@dataclass(frozen=True)
class CategoryReportRow:
    """One category's Gate B half 2 verdict. Carries no suite-wide field."""

    category: str
    f1: float | None
    threshold: float
    status: str  # "pass" | "fail" | "declared-and-uncovered"
    declared_uncovered: tuple[str, ...]
    agent_judgable: tuple[str, ...]


def report_category(result: CategoryResult) -> CategoryReportRow:
    """Build one category's verdict row, deciding on that category alone."""
    if result.f1 is None:
        status = "declared-and-uncovered"
    elif result.f1 >= F1_THRESHOLD:
        status = "pass"
    else:
        status = "fail"

    return CategoryReportRow(
        category=result.category,
        f1=result.f1,
        threshold=F1_THRESHOLD,
        status=status,
        declared_uncovered=result.declared_uncovered,
        agent_judgable=result.agent_judgable,
    )


def report_suite(results: list[CategoryResult]) -> list[CategoryReportRow]:
    """Build the per-category breakdown for every category, independently.

    Returns a plain list of rows -- deliberately not a dict/object carrying
    any suite-wide average, mean, or aggregate F1 field. One category
    failing its 0.80 floor never changes another category's row.
    """
    return [report_category(result) for result in results]
