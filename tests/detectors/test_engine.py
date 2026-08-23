"""Tests for detectors.engine — spec.md S-003, S-007 (T-2.4)."""

from __future__ import annotations

import pytest

from detectors.engine import (
    CoverageEntry,
    FixtureCase,
    OutOfArtifactFixtureError,
    Tier,
    run_category,
)


def _matrix_ast09() -> list[CoverageEntry]:
    return [
        CoverageEntry(
            scenario_id="AST09-orphaned-skill",
            category="AST09",
            tier=Tier.OUT_OF_ARTIFACT,
            reason=(
                "requires version history and release metadata maintained "
                "outside the artifact"
            ),
        ),
        CoverageEntry(
            scenario_id="AST09-stale-manifest-pin",
            category="AST09",
            tier=Tier.STATIC_DETECTABLE,
            reason="manifest pins a dependency version resolvable at parse time",
        ),
    ]


def _stale_pin_detector(sample: dict) -> bool:
    return bool(sample.get("pinned_version_stale"))


def test_out_of_artifact_scenario_excluded_from_denominator():
    """S-003: out-of-artifact tier never enters the F1 denominator."""
    matrix = _matrix_ast09()
    fixtures = [
        FixtureCase(
            "c1",
            "AST09-stale-manifest-pin",
            "AST09",
            True,
            {"pinned_version_stale": True},
        ),
        FixtureCase(
            "c2",
            "AST09-stale-manifest-pin",
            "AST09",
            False,
            {"pinned_version_stale": False},
        ),
    ]

    result = run_category("AST09", matrix, fixtures, _stale_pin_detector)

    assert result.f1 == pytest.approx(1.0)
    assert "AST09-orphaned-skill" not in result.scored_case_ids
    assert result.declared_uncovered == ("AST09-orphaned-skill",)


def test_out_of_artifact_scenario_never_appears_in_fixture_corpus():
    """S-003: a fixture case bound to an out-of-artifact scenario is a contract violation."""
    matrix = _matrix_ast09()
    fixtures = [FixtureCase("bad", "AST09-orphaned-skill", "AST09", True, {})]

    with pytest.raises(OutOfArtifactFixtureError):
        run_category("AST09", matrix, fixtures, _stale_pin_detector)


def test_declared_detectable_tier_empty_yields_no_f1():
    """gate-4: a category with an empty static-detectable tier publishes no F1."""
    matrix = [
        CoverageEntry(
            "AST09-orphaned-skill", "AST09", Tier.OUT_OF_ARTIFACT, "process property"
        ),
        CoverageEntry(
            "AST09-regulatory-exposure",
            "AST09",
            Tier.AGENT_JUDGABLE,
            "needs contextual judgment",
        ),
    ]

    result = run_category("AST09", matrix, fixtures=[], detector_fn=_stale_pin_detector)

    assert result.f1 is None
    assert result.declared_uncovered == ("AST09-orphaned-skill",)
    assert result.agent_judgable == ("AST09-regulatory-exposure",)


def test_category_f1_reflects_only_static_detectable_predictions():
    """S-007 Given: F1 is computed restricted to the static-detectable subset."""
    matrix = _matrix_ast09()
    fixtures = [
        FixtureCase(
            "v1",
            "AST09-stale-manifest-pin",
            "AST09",
            True,
            {"pinned_version_stale": True},
        ),
        FixtureCase(
            "v2",
            "AST09-stale-manifest-pin",
            "AST09",
            True,
            {"pinned_version_stale": False},
        ),  # false negative
        FixtureCase(
            "c1",
            "AST09-stale-manifest-pin",
            "AST09",
            False,
            {"pinned_version_stale": True},
        ),  # false positive
        FixtureCase(
            "c2",
            "AST09-stale-manifest-pin",
            "AST09",
            False,
            {"pinned_version_stale": False},
        ),
    ]

    result = run_category("AST09", matrix, fixtures, _stale_pin_detector)

    assert result.true_positives == 1
    assert result.false_negatives == 1
    assert result.false_positives == 1
    assert result.true_negatives == 1
    assert result.precision == pytest.approx(0.5)
    assert result.recall == pytest.approx(0.5)
    assert result.f1 == pytest.approx(0.5)
