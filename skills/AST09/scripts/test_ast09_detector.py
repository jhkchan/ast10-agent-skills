"""TDD tests for the AST09 detector -- Step 04 T-3.3 (S-001, S-003, S-007)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ast09_detector", _HERE / "detector.py")
detector = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = detector
_spec.loader.exec_module(detector)


def test_s001_detector_registry_matches_declared_detectable_tier():
    declared_detectable = {s for s, tier in detector.SCENARIO_TIERS.items() if tier == "static-detectable"}
    assert set(detector.DETECTORS.keys()) == declared_detectable == set()


def test_s003_all_scenarios_declared_out_of_artifact_with_reason():
    assert detector.SCENARIO_TIERS["AST09-orphaned-skill"] == "out-of-artifact"
    assert detector.SCENARIO_TIERS["AST09-regulatory-exposure"] == "out-of-artifact"
    assert detector.SCENARIO_TIERS["AST09-undetected-compromise"] == "out-of-artifact"


def test_s007_empty_tier_never_manufactures_an_f1():
    report = detector.f1_report([])
    assert report["status"] == "declared-and-uncovered"
    assert report["f1"] is None
