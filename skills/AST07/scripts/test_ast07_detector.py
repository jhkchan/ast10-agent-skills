"""TDD tests for the AST07 detector -- Step 04 T-3.3 (S-001, S-003, S-007)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ast07_detector", _HERE / "detector.py")
detector = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = detector
_spec.loader.exec_module(detector)


def test_s001_detector_registry_matches_declared_detectable_tier():
    declared_detectable = {s for s, tier in detector.SCENARIO_TIERS.items() if tier == "static-detectable"}
    assert set(detector.DETECTORS.keys()) == declared_detectable == set()


def test_s003_all_three_registry_scenarios_declared_out_of_artifact():
    """The table names all three AST07 scenarios, under registry ids.

    It previously named two, under local slugs, and omitted AST07-S01 Malicious
    Update entirely -- so a reader checking the module alone would have counted
    two scenarios in a category that has three. The keys are asserted exactly,
    not by subset, so a scenario cannot be dropped again without failing here.
    """
    assert detector.SCENARIO_TIERS == {
        "AST07-S01": "out-of-artifact",
        "AST07-S02": "out-of-artifact",
        "AST07-S03": "out-of-artifact",
    }


def test_the_registry_is_the_authority_for_those_three_tiers():
    """The module restates the registry; it does not get its own opinion."""
    import pathlib

    import yaml

    registry_path = pathlib.Path(__file__).resolve().parents[3] / "scenarios" / "registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    from_registry = {s["id"]: s["tier"] for s in registry["scenarios"] if s["category"] == "AST07"}
    assert detector.SCENARIO_TIERS == from_registry


def test_s007_empty_tier_never_manufactures_an_f1():
    report = detector.f1_report([])
    assert report["status"] == "declared-and-uncovered"
    assert report["f1"] is None
    # No checks ship, so there is no coverage to scope. The label travels with
    # the report either way so a number can never be quoted without one.
    assert report["scope"] == "none"
    assert detector.CHECK_COVERAGE == {}
    assert detector.F1_SCOPE == "none"


def test_zero_detectors_is_a_finished_state_because_the_registry_says_so():
    """The empty map is only legitimate while the registry tiers nothing here static.

    Stated as its own assertion rather than left implied by the two tests above,
    because "this module ships no detector" reads identically whether it is a
    considered result or an unwritten one. It is the former, and this is the
    check that would turn it into the latter the moment the tiering moved.
    """
    import pathlib

    import yaml

    registry_path = pathlib.Path(__file__).resolve().parents[3] / "scenarios" / "registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    ast07 = [s for s in registry["scenarios"] if s["category"] == "AST07"]
    assert len(ast07) == 3
    assert [s["tier"] for s in ast07] == ["out-of-artifact"] * 3, (
        "the registry now tiers an AST07 scenario as decidable; skills/AST07/scripts/detector.py "
        "owes it a detector function and skills/AST07/coverage-matrix.md owes it a row that says so"
    )
    assert detector.DETECTORS == {}
