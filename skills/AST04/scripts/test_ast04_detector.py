"""TDD tests for the AST04 detector -- Step 04 T-3.3 (S-001, S-005, S-007)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ast04_detector", _HERE / "detector.py")
detector = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = detector
_spec.loader.exec_module(detector)

# --- fixtures, one vulnerable + one clean per scenario ----------------------

YAML_VULN = {
    "manifest": {},
    "files": {"scripts/loader.py": "cfg = yaml.load(raw_text)\n"},
}
YAML_CLEAN = {
    "manifest": {},
    "files": {"scripts/loader.py": "cfg = yaml.safe_load(raw_text)\n"},
}

JSON_VULN = {
    "manifest": {},
    "files": {"config.json": '{"user": {"__proto__": {"isAdmin": true}}}'},
}
JSON_CLEAN = {
    "manifest": {},
    "files": {"config.json": '{"user": {"name": "alice", "role": "member"}}'},
}

TOML_VULN = {
    "manifest": {},
    "files": {"config.toml": 'name = "svc"\n[admin]\nrole = "root"\n'},
}
TOML_CLEAN = {
    "manifest": {},
    "files": {"config.toml": 'name = "svc"\n\n[settings]\nallow = ["a", "b"]\n'},
}

UNICODE_VULN = {"manifest": {"description": "Fetch data​and‮execute"}, "files": {}}
UNICODE_CLEAN = {"manifest": {"description": "Fetch data and execute"}, "files": {}}


def test_s001_detector_registry_matches_declared_detectable_tier():
    declared_detectable = {s for s, tier in detector.SCENARIO_TIERS.items() if tier == "static-detectable"}
    assert set(detector.DETECTORS.keys()) == declared_detectable


def test_s005_yaml_json_toml_are_three_distinct_functions():
    assert detector.detect_yaml_injection is not detector.detect_json_injection
    assert detector.detect_yaml_injection is not detector.detect_toml_injection
    assert detector.detect_json_injection is not detector.detect_toml_injection


def test_s005_yaml_detector_flags_only_its_own_vulnerable_fixture():
    assert detector.detect_yaml_injection(YAML_VULN).detected is True
    assert detector.detect_yaml_injection(YAML_CLEAN).detected is False
    # cross-format fixtures must not trip the YAML path (no shared generic matcher)
    assert detector.detect_yaml_injection(JSON_VULN).detected is False
    assert detector.detect_yaml_injection(TOML_VULN).detected is False


def test_s005_json_detector_flags_only_its_own_vulnerable_fixture():
    assert detector.detect_json_injection(JSON_VULN).detected is True
    assert detector.detect_json_injection(JSON_CLEAN).detected is False
    assert detector.detect_json_injection(YAML_VULN).detected is False
    assert detector.detect_json_injection(TOML_VULN).detected is False


def test_s005_toml_detector_flags_only_its_own_vulnerable_fixture():
    assert detector.detect_toml_injection(TOML_VULN).detected is True
    assert detector.detect_toml_injection(TOML_CLEAN).detected is False
    assert detector.detect_toml_injection(YAML_VULN).detected is False
    assert detector.detect_toml_injection(JSON_VULN).detected is False


def test_invisible_unicode_smuggling_detected_in_description():
    assert detector.detect_invisible_unicode_smuggling(UNICODE_VULN).detected is True
    assert detector.detect_invisible_unicode_smuggling(UNICODE_CLEAN).detected is False


def test_s007_f1_at_least_080_on_declared_detectable_tier():
    fixtures = [
        (YAML_VULN, {"AST04-yaml-injection"}),
        (YAML_CLEAN, set()),
        (JSON_VULN, {"AST04-json-injection"}),
        (JSON_CLEAN, set()),
        (TOML_VULN, {"AST04-toml-injection"}),
        (TOML_CLEAN, set()),
        (UNICODE_VULN, {"AST04-invisible-unicode-smuggling"}),
        (UNICODE_CLEAN, set()),
    ]
    report = detector.f1_report(fixtures)
    assert report["status"] == "measured"
    assert report["f1"] >= 0.80, report
