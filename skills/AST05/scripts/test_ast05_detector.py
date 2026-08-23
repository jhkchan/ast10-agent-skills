"""TDD tests for the AST05 detector -- Step 04 T-3.3 (S-001, S-007)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ast05_detector", _HERE / "detector.py")
detector = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = detector
_spec.loader.exec_module(detector)


def test_s001_detector_registry_matches_declared_detectable_tier():
    declared_detectable = {s for s, tier in detector.SCENARIO_TIERS.items() if tier == "static-detectable"}
    assert set(detector.DETECTORS.keys()) == declared_detectable
    assert "AST05-injected-instruction-compliance" not in detector.DETECTORS


def test_unrestricted_network_fetch_flags_allow_all():
    pkg = {
        "manifest": {"permissions": {"network": {"policy": "allow-all"}}},
        "files": {},
    }
    assert detector.detect_unrestricted_network_fetch(pkg).detected is True


def test_unrestricted_network_fetch_clear_on_allow_list():
    pkg = {
        "manifest": {"permissions": {"network": {"policy": "allow-list", "allow": ["api.example.com"]}}},
        "files": {},
    }
    assert detector.detect_unrestricted_network_fetch(pkg).detected is False


def test_wildcard_allowlist_flags_bare_wildcard():
    pkg = {
        "manifest": {"permissions": {"network": {"policy": "allow-list", "allow": ["*"]}}},
        "files": {},
    }
    assert detector.detect_wildcard_domain_allowlist(pkg).detected is True


def test_wildcard_allowlist_flags_bare_tld_wildcard():
    pkg = {
        "manifest": {"permissions": {"network": {"policy": "allow-list", "allow": ["*.com"]}}},
        "files": {},
    }
    assert detector.detect_wildcard_domain_allowlist(pkg).detected is True


def test_wildcard_allowlist_clear_on_scoped_subdomain_wildcard():
    pkg = {
        "manifest": {"permissions": {"network": {"policy": "allow-list", "allow": ["*.example.com"]}}},
        "files": {},
    }
    assert detector.detect_wildcard_domain_allowlist(pkg).detected is False


def test_wildcard_allowlist_not_applicable_outside_allowlist_mode():
    pkg = {
        "manifest": {"permissions": {"network": {"policy": "deny-all"}}},
        "files": {},
    }
    assert detector.detect_wildcard_domain_allowlist(pkg).detected is False


def test_s007_f1_at_least_080_on_declared_detectable_tier():
    fixtures = [
        (
            {
                "manifest": {"permissions": {"network": {"policy": "allow-all"}}},
                "files": {},
            },
            {"AST05-unrestricted-network-fetch"},
        ),
        (
            {
                "manifest": {"permissions": {"network": {"policy": "allow-list", "allow": ["*"]}}},
                "files": {},
            },
            {"AST05-wildcard-domain-allowlist"},
        ),
        (
            {
                "manifest": {"permissions": {"network": {"policy": "allow-list", "allow": ["*.io"]}}},
                "files": {},
            },
            {"AST05-wildcard-domain-allowlist"},
        ),
        (
            {
                "manifest": {"permissions": {"network": {"policy": "deny-all"}}},
                "files": {},
            },
            set(),
        ),
        (
            {
                "manifest": {
                    "permissions": {
                        "network": {
                            "policy": "allow-list",
                            "allow": ["api.example.com"],
                        }
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
                        "network": {
                            "policy": "allow-list",
                            "allow": ["*.example.com", "cdn.example.org"],
                        }
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
