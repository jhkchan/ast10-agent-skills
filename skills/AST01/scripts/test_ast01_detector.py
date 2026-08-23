"""TDD tests for the AST01 detector -- Step 04 T-3.3 (S-001, S-007).

Loaded by absolute path under a category-unique module name so ten
identically-named `detector.py` siblings never collide in `sys.modules`
when the whole suite is collected in one pytest session.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ast01_detector", _HERE / "detector.py")
detector = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = detector  # dataclass needs the module registered before exec
_spec.loader.exec_module(detector)


def _clean_package(files: dict[str, str]) -> dict:
    """Build a package whose declared content_hash truthfully matches its files."""
    pkg = {
        "manifest": {"content_hash": {"algorithm": "sha256", "value": ""}},
        "files": files,
    }
    pkg["manifest"]["content_hash"]["value"] = detector._package_digest(pkg)
    return pkg


def test_s001_detector_registry_matches_declared_detectable_tier():
    """No orphan detector, no unimplemented declared-detectable scenario."""
    declared_detectable = {
        s for s, tier in detector.SCENARIO_TIERS.items() if tier == "static-detectable"
    }
    assert set(detector.DETECTORS.keys()) == declared_detectable
    # agent-judgable scenarios must NOT have a detector function (out of this tier's scope).
    assert "AST01-obfuscated-payload-intent" not in detector.DETECTORS


def test_content_hash_missing_flags_when_no_hash_declared():
    pkg = {"manifest": {}, "files": {"SKILL.md": "# a skill"}}
    finding = detector.detect_content_hash_missing(pkg)
    assert finding.detected is True


def test_content_hash_missing_clear_when_hash_present():
    pkg = _clean_package({"SKILL.md": "# a skill"})
    finding = detector.detect_content_hash_missing(pkg)
    assert finding.detected is False


def test_content_hash_mismatch_flags_tampered_package():
    pkg = _clean_package({"SKILL.md": "# original"})
    pkg["files"]["SKILL.md"] = "# tampered after signing"
    finding = detector.detect_content_hash_mismatch(pkg)
    assert finding.detected is True


def test_content_hash_mismatch_clear_on_untampered_package():
    pkg = _clean_package({"SKILL.md": "# untouched"})
    finding = detector.detect_content_hash_mismatch(pkg)
    assert finding.detected is False


def test_s007_f1_at_least_080_on_declared_detectable_tier():
    fixtures = [
        # vulnerable: missing hash entirely
        ({"manifest": {}, "files": {"SKILL.md": "a"}}, {"AST01-content-hash-missing"}),
        (
            {"manifest": {"content_hash": None}, "files": {"scripts/x.py": "print(1)"}},
            {"AST01-content-hash-missing"},
        ),
        # vulnerable: hash present but package tampered after signing
        (
            {
                "manifest": {
                    "content_hash": {"algorithm": "sha256", "value": "0" * 64}
                },
                "files": {"SKILL.md": "# tampered"},
            },
            {"AST01-content-hash-mismatch"},
        ),
        # clean: hash present and correct
        (_clean_package({"SKILL.md": "# clean 1"}), set()),
        (
            _clean_package({"SKILL.md": "# clean 2", "scripts/detector.py": "pass"}),
            set(),
        ),
        (_clean_package({"references/notes.md": "n/a"}), set()),
    ]
    report = detector.f1_report(fixtures)
    assert report["status"] == "measured"
    assert report["f1"] >= 0.80, report
