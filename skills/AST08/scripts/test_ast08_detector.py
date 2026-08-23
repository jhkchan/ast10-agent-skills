"""TDD tests for the AST08 detector -- Step 04 T-3.3 (S-001, S-007)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ast08_detector", _HERE / "detector.py")
detector = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = detector
_spec.loader.exec_module(detector)


def test_s001_detector_registry_matches_declared_detectable_tier():
    declared_detectable = {
        s for s, tier in detector.SCENARIO_TIERS.items() if tier == "static-detectable"
    }
    assert set(detector.DETECTORS.keys()) == declared_detectable
    assert "AST08-scan-evasion-narrative" not in detector.DETECTORS


def test_invisible_unicode_smuggling_detected_in_file_content():
    pkg = {
        "manifest": {},
        "files": {"scripts/helper.py": "x = 1​  # zero-width space smuggled in\n"},
    }
    assert detector.detect_invisible_unicode_smuggling(pkg).detected is True


def test_invisible_unicode_smuggling_clear_on_plain_ascii():
    pkg = {"manifest": {}, "files": {"scripts/helper.py": "x = 1  # plain\n"}}
    assert detector.detect_invisible_unicode_smuggling(pkg).detected is False


def test_s007_f1_at_least_080_on_declared_detectable_tier():
    fixtures = [
        (
            {"manifest": {"description": "run​now"}, "files": {}},
            {"AST08-invisible-unicode-smuggling"},
        ),
        (
            {"manifest": {}, "files": {"a.md": "hidden‮text"}},
            {"AST08-invisible-unicode-smuggling"},
        ),
        (
            {"manifest": {}, "files": {"b.md": "no tricks here﻿"}},
            {"AST08-invisible-unicode-smuggling"},
        ),
        ({"manifest": {"description": "clean text"}, "files": {}}, set()),
        ({"manifest": {}, "files": {"a.md": "also clean"}}, set()),
        ({"manifest": {}, "files": {"b.md": "still clean"}}, set()),
    ]
    report = detector.f1_report(fixtures)
    assert report["status"] == "measured"
    assert report["f1"] >= 0.80, report
