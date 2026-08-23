"""TDD tests for the AST06 detector -- Step 04 T-3.3 (S-001, S-007)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ast06_detector", _HERE / "detector.py")
detector = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = detector
_spec.loader.exec_module(detector)


def test_s001_detector_registry_matches_declared_detectable_tier():
    declared_detectable = {
        s for s, tier in detector.SCENARIO_TIERS.items() if tier == "static-detectable"
    }
    assert set(detector.DETECTORS.keys()) == declared_detectable
    assert "AST06-cross-skill-data-leak" not in detector.DETECTORS


def test_unrestricted_shell_exec_flags_no_command_allowlist():
    pkg = {"manifest": {"permissions": {"shell": {"allowed": True}}}, "files": {}}
    assert detector.detect_unrestricted_shell_exec(pkg).detected is True


def test_unrestricted_shell_exec_clear_with_command_allowlist():
    pkg = {
        "manifest": {
            "permissions": {"shell": {"allowed": True, "commands": ["git", "npm"]}}
        },
        "files": {},
    }
    assert detector.detect_unrestricted_shell_exec(pkg).detected is False


def test_missing_sandbox_declaration_flags_absent_permissions_block():
    pkg = {"manifest": {}, "files": {}}
    assert detector.detect_missing_sandbox_declaration(pkg).detected is True
    # every detector must tolerate this same sparse fixture without crashing
    assert detector.detect_unrestricted_shell_exec(pkg).detected is False


def test_missing_sandbox_declaration_clear_when_permissions_present():
    pkg = {"manifest": {"permissions": {"shell": {"allowed": False}}}, "files": {}}
    assert detector.detect_missing_sandbox_declaration(pkg).detected is False


def test_s007_f1_at_least_080_on_declared_detectable_tier():
    fixtures = [
        (
            {"manifest": {"permissions": {"shell": {"allowed": True}}}},
            {"AST06-unrestricted-shell-exec"},
        ),
        ({"manifest": {}}, {"AST06-missing-sandbox-declaration"}),
        ({"manifest": {"permissions": None}}, {"AST06-missing-sandbox-declaration"}),
        (
            {
                "manifest": {
                    "permissions": {"shell": {"allowed": True, "commands": ["git"]}}
                }
            },
            set(),
        ),
        ({"manifest": {"permissions": {"shell": {"allowed": False}}}}, set()),
        ({"manifest": {"permissions": {"network": {"policy": "deny-all"}}}}, set()),
    ]
    fixtures = [({**pkg, "files": {}}, expected) for pkg, expected in fixtures]
    report = detector.f1_report(fixtures)
    assert report["status"] == "measured"
    assert report["f1"] >= 0.80, report
