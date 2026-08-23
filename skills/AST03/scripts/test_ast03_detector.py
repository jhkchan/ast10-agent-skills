"""TDD tests for the AST03 detector -- Step 04 T-3.3 (S-001, S-007)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ast03_detector", _HERE / "detector.py")
detector = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = detector
_spec.loader.exec_module(detector)


def test_s001_detector_registry_matches_declared_detectable_tier():
    declared_detectable = {s for s, tier in detector.SCENARIO_TIERS.items() if tier == "static-detectable"}
    assert set(detector.DETECTORS.keys()) == declared_detectable
    assert "AST03-task-scope-mismatch" not in detector.DETECTORS


def test_unbounded_write_scope_flags_missing_deny_write():
    pkg = {"manifest": {"permissions": {"deny_write": []}}, "files": {}}
    assert detector.detect_unbounded_write_scope(pkg).detected is True


def test_unbounded_write_scope_clear_when_paths_denied():
    pkg = {
        "manifest": {"permissions": {"deny_write": ["/etc/**", "~/.aws/**"]}},
        "files": {},
    }
    assert detector.detect_unbounded_write_scope(pkg).detected is False


def test_shell_network_combo_flags_the_s002_example_shape():
    # "overprivileged agent with write access to production secrets" (spec S-002)
    pkg = {
        "manifest": {
            "permissions": {
                "shell": {"allowed": True},
                "network": {"policy": "allow-all"},
            }
        },
        "files": {},
    }
    assert detector.detect_shell_network_privilege_combo(pkg).detected is True


def test_shell_network_combo_clear_when_network_is_deny_all():
    pkg = {
        "manifest": {
            "permissions": {
                "shell": {"allowed": True},
                "network": {"policy": "deny-all"},
            }
        },
        "files": {},
    }
    assert detector.detect_shell_network_privilege_combo(pkg).detected is False


def test_s007_f1_at_least_080_on_declared_detectable_tier():
    fixtures = [
        (
            {
                "manifest": {
                    "permissions": {
                        "deny_write": None,
                        "shell": {"allowed": False},
                        "network": {"policy": "deny-all"},
                    }
                },
                "files": {},
            },
            {"AST03-unbounded-write-scope"},
        ),
        (
            {
                "manifest": {
                    "permissions": {
                        "deny_write": [],
                        "shell": {"allowed": True},
                        "network": {"policy": "allow-all"},
                    }
                },
                "files": {},
            },
            {"AST03-unbounded-write-scope", "AST03-shell-network-privilege-combo"},
        ),
        (
            {
                "manifest": {
                    "permissions": {
                        "deny_write": ["/secrets/**"],
                        "shell": {"allowed": True},
                        "network": {"policy": "allow-all"},
                    }
                },
                "files": {},
            },
            {"AST03-shell-network-privilege-combo"},
        ),
        (
            {
                "manifest": {
                    "permissions": {
                        "deny_write": ["/etc/**"],
                        "shell": {"allowed": True},
                        "network": {"policy": "deny-all"},
                    }
                },
                "files": {},
            },
            set(),
        ),
        (
            {
                "manifest": {
                    "permissions": {
                        "deny_write": ["/**"],
                        "shell": {"allowed": False},
                        "network": {
                            "policy": "allow-list",
                            "allow": ["api.example.com"],
                        },
                    }
                },
                "files": {},
            },
            set(),
        ),
        (
            {
                "manifest": {
                    "permissions": {
                        "deny_write": ["/**"],
                        "shell": {"allowed": False},
                        "network": {"policy": "deny-all"},
                    }
                },
                "files": {},
            },
            set(),
        ),
    ]
    report = detector.f1_report(fixtures)
    assert report["status"] == "measured"
    assert report["f1"] >= 0.80, report
