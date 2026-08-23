"""Tests for the AST09 detector -- the empty-detectable-tier contract (S-001, S-003, S-007).

AST09 is the one category where shipping no detector is the correct outcome, so
"no detector" has to be tested as hard as a detector would be. Asserting
``DETECTORS == {}`` alone would pass just as well if someone had simply not
written one yet. These tests instead bind the emptiness to its cause:

  * the module enumerates all seven of the registry's AST09 scenarios, by
    canonical id, at the registry's own tier -- so a scenario cannot be quietly
    dropped from the module's view of the category;
  * the emptiness is derived from that enumeration rather than asserted
    independently, so re-tiering any scenario static-detectable makes the
    module owe a check and makes these tests fail;
  * ``f1_report`` refuses to produce a number for any corpus, including a
    non-empty one -- the never-pad rule is a property of the code, not of the
    fact that the fixture directory happens to be empty today.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import yaml

_HERE = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[2]
if str(_REPO_ROOT) not in sys.path:  # pragma: no cover - import-path bootstrap
    sys.path.insert(0, str(_REPO_ROOT))

_spec = importlib.util.spec_from_file_location("ast09_detector", _HERE / "detector.py")
detector = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = detector
_spec.loader.exec_module(detector)

REGISTRY_PATH = _REPO_ROOT / "scenarios" / "registry.yaml"


def _registry_ast09() -> list[dict]:
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    return [s for s in registry["scenarios"] if s["category"] == "AST09"]


def test_module_enumerates_every_registry_scenario_by_canonical_id():
    scenarios = _registry_ast09()
    assert len(scenarios) == 7
    assert set(detector.SCENARIO_TIERS) == {s["id"] for s in scenarios}


def test_module_agrees_with_the_authoritative_registry_on_every_tier():
    for scenario in _registry_ast09():
        assert detector.SCENARIO_TIERS[scenario["id"]] == scenario["tier"], scenario["id"]


def test_s003_all_seven_scenarios_are_out_of_artifact():
    assert set(detector.SCENARIO_TIERS.values()) == {"out-of-artifact"}


def test_s001_the_empty_detector_set_is_derived_from_the_empty_detectable_tier():
    """Not "nobody wrote one": there is nothing static-detectable to write."""
    declared_detectable = {s for s, tier in detector.SCENARIO_TIERS.items() if tier == "static-detectable"}
    assert declared_detectable == set()
    assert detector.STATIC_DETECTABLE == declared_detectable
    assert set(detector.DETECTORS) == declared_detectable


def test_no_check_means_no_coverage_claim_and_no_scope():
    assert detector.CHECK_COVERAGE == {}
    assert detector.F1_SCOPE == "none"


def test_running_the_empty_detector_set_over_a_package_yields_no_findings():
    package = {
        "manifest": {"name": "orphaned-helper", "description": "installed by a developer who has since left"},
        "files": {"SKILL.md": "This skill processes PHI and has no audit trail.\n"},
    }
    assert detector.run_all(package) == []


def test_s007_empty_tier_never_manufactures_an_f1():
    report = detector.f1_report([])
    assert report == {"status": "declared-and-uncovered", "f1": None, "scope": "none"}


def test_s007_a_non_empty_corpus_still_gets_no_f1():
    """The never-pad rule lives in the code, not in an empty fixture directory.

    If someone hand-writes AST09 fixtures -- a SKILL.md whose prose says the
    author left, a description that mentions PHI -- the report must still refuse
    to score them. Scoring them would measure the fixture author.
    """
    manufactured = [
        ({"manifest": {"description": "author left the company"}, "files": {}}, {"AST09-S03"}),
        ({"manifest": {"description": "processes PHI"}, "files": {}}, {"AST09-S04"}),
    ]
    report = detector.f1_report(manufactured)
    assert report["status"] == "declared-and-uncovered"
    assert report["f1"] is None
    assert report["scope"] == "none"
