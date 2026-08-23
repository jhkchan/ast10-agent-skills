"""Deterministic detector engine for OWASP AST detector skills.

Runs a category's ``static-detectable``-tier fixture corpus through a
detector function and computes precision/recall/F1 for that category alone.

The F1 denominator is drawn *only* from scenarios the category's coverage
matrix tiers ``static-detectable`` (spec.md S-007 Given: "restricted to the
subset classified as static-detectable in the coverage matrix"; gate-4 sizes
the fixture corpus off this same tier: ``cases = max(6, 2 x
detectable_scenarios)``).

``out-of-artifact`` scenarios must never appear in the fixture corpus at all
(spec.md S-003: "The scenario never appears in the fixture corpus") -- the
engine raises rather than silently dropping such a case.

``agent-judgable`` scenarios have no fixture corpus in this engine (they are
scored by the judge harness, not a deterministic detector) and are reported
separately, never folded into the F1 denominator.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class Tier(str, Enum):
    """Per-scenario detectability tier from the coverage matrix (spec.md gate-1)."""

    STATIC_DETECTABLE = "static-detectable"
    AGENT_JUDGABLE = "agent-judgable"
    OUT_OF_ARTIFACT = "out-of-artifact"


@dataclass(frozen=True)
class CoverageEntry:
    """One row of a category's coverage matrix."""

    scenario_id: str
    category: str
    tier: Tier
    reason: str


@dataclass(frozen=True)
class FixtureCase:
    """One hand-labeled fixture case bound to a scenario."""

    case_id: str
    scenario_id: str
    category: str
    is_vulnerable: bool
    sample: object


@dataclass(frozen=True)
class CategoryResult:
    """Detector engine output for a single AST category."""

    category: str
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float | None
    recall: float | None
    f1: float | None
    scored_case_ids: tuple[str, ...]
    declared_uncovered: tuple[str, ...]
    agent_judgable: tuple[str, ...]


class OutOfArtifactFixtureError(ValueError):
    """Raised when a fixture case references an out-of-artifact scenario."""


class UnregisteredScenarioFixtureError(ValueError):
    """Raised when a fixture case references a scenario_id absent from the
    coverage matrix entirely (typo or an unregistered scenario) -- this must
    be loud, exactly like OutOfArtifactFixtureError, rather than silently
    shrinking the F1 denominator by one fixture."""


def run_category(
    category: str,
    coverage_matrix: list[CoverageEntry],
    fixtures: list[FixtureCase],
    detector_fn: Callable[[object], bool],
) -> CategoryResult:
    """Run ``detector_fn`` over one category's static-detectable fixtures.

    Fixtures bound to scenarios tiered anything other than
    ``static-detectable`` do not enter the F1 denominator. A fixture bound to
    an ``out-of-artifact`` scenario is a contract violation and raises
    :class:`OutOfArtifactFixtureError` immediately. A fixture whose
    scenario_id is absent from the coverage matrix altogether -- a typo or an
    unregistered scenario -- is the same kind of contract violation and
    raises :class:`UnregisteredScenarioFixtureError` immediately, rather than
    silently dropping out of the denominator via a `.get()` miss.
    """
    tier_by_scenario = {entry.scenario_id: entry.tier for entry in coverage_matrix}

    unregistered_hits = sorted(
        {f.scenario_id for f in fixtures if f.scenario_id not in tier_by_scenario}
    )
    if unregistered_hits:
        raise UnregisteredScenarioFixtureError(
            "fixture(s) reference scenario_id(s) absent from the coverage "
            f"matrix for category {category!r}: {unregistered_hits}"
        )

    out_of_artifact_hits = sorted(
        {
            f.scenario_id
            for f in fixtures
            if tier_by_scenario.get(f.scenario_id) is Tier.OUT_OF_ARTIFACT
        }
    )
    if out_of_artifact_hits:
        raise OutOfArtifactFixtureError(
            "out-of-artifact scenario(s) present in fixture corpus for "
            f"category {category!r}: {out_of_artifact_hits}"
        )

    scored = [
        f
        for f in fixtures
        if tier_by_scenario.get(f.scenario_id) is Tier.STATIC_DETECTABLE
    ]

    declared_uncovered = tuple(
        sorted(
            entry.scenario_id
            for entry in coverage_matrix
            if entry.tier is Tier.OUT_OF_ARTIFACT
        )
    )
    agent_judgable = tuple(
        sorted(
            entry.scenario_id
            for entry in coverage_matrix
            if entry.tier is Tier.AGENT_JUDGABLE
        )
    )

    tp = fp = fn = tn = 0
    for case in scored:
        predicted = bool(detector_fn(case.sample))
        if predicted and case.is_vulnerable:
            tp += 1
        elif predicted and not case.is_vulnerable:
            fp += 1
        elif not predicted and case.is_vulnerable:
            fn += 1
        else:
            tn += 1

    if not scored:
        precision = recall = f1 = None
    else:
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )

    return CategoryResult(
        category=category,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        precision=precision,
        recall=recall,
        f1=f1,
        scored_case_ids=tuple(c.case_id for c in scored),
        declared_uncovered=declared_uncovered,
        agent_judgable=agent_judgable,
    )
