"""TDD tests for T-4.1 — hand-built fixture corpus at the locked per-category minimum size.

Covers spec.md scenarios as applied by plan.md's T-4.1 acceptance test:
  S-003 — zero fixture cases are drawn from a scenario tiered out-of-artifact; a category with
          an empty detectable tier publishes no F1 and is reported declared-and-uncovered.
  S-007 — each category's case count exactly matches the locked gate-4 formula
          cases = max(MIN_FLOOR, 2 * detectable_scenarios), class-balanced vulnerable/clean.
  S-011 — the label manifest is bound to a content hash over its scenario tiering, so a later
          tier edit (reclassification) is detectable rather than silently invalidating F1.

Run with: pytest fixtures/test_manifest.py -v
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from validators.tier_lock import check_tier_lock

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
MANIFEST_PATH = FIXTURES_DIR / "manifest.yaml"

CATEGORIES = [f"AST{i:02d}" for i in range(1, 11)]
LABELS = {"vulnerable", "clean"}


@pytest.fixture(scope="module")
def manifest() -> dict:
    assert MANIFEST_PATH.exists(), f"missing {MANIFEST_PATH}"
    with MANIFEST_PATH.open() as fh:
        data = yaml.safe_load(fh)
    assert data is not None, "manifest.yaml parsed to nothing"
    return data


def test_manifest_declares_all_ten_categories(manifest):
    assert set(manifest["categories"].keys()) == set(CATEGORIES)


@pytest.mark.parametrize("category", CATEGORIES)
def test_case_count_matches_locked_gate4_formula(manifest, category):
    """gate-4: cases >= max(MIN_FLOOR, 2 * detectable_scenarios), MIN_FLOOR = 6.

    A floor, not an equality, per ADR-0007. The equality also forbade a category
    from carrying MORE cases than the formula yields, which stopped a corpus
    being strengthened by a further real surface of a scenario it already covers.
    Class balance and the discrimination ablation bound the corpus from the other
    side, so cases cannot be added to move a number.
    """
    min_floor = manifest["min_floor"]
    cat = manifest["categories"][category]
    n_detectable = len(cat["detectable_scenarios"])
    expected = max(min_floor, 2 * n_detectable)
    if n_detectable == 0:
        # gate-4: an empty detectable tier publishes no F1 at all and is never padded.
        assert cat["cases"] == []
        assert cat["status"] == "declared-and-uncovered"
        assert cat.get("published_f1") is None
    else:
        assert len(cat["cases"]) >= expected, (
            f"{category}: expected at least {expected} cases "
            f"(max({min_floor}, 2*{n_detectable})), got {len(cat['cases'])}"
        )


@pytest.mark.parametrize("category", CATEGORIES)
def test_cases_are_class_balanced(manifest, category):
    cat = manifest["categories"][category]
    cases = cat["cases"]
    if not cases:
        return
    vulnerable = [c for c in cases if c["label"] == "vulnerable"]
    clean = [c for c in cases if c["label"] == "clean"]
    assert len(vulnerable) == len(clean), (
        f"{category}: not class-balanced ({len(vulnerable)} vulnerable vs {len(clean)} clean)"
    )
    assert all(c["label"] in LABELS for c in cases)


@pytest.mark.parametrize("category", CATEGORIES)
def test_no_case_drawn_from_out_of_artifact_tier(manifest, category):
    """S-003: the out-of-artifact tier never enters the fixture corpus."""
    cat = manifest["categories"][category]
    detectable_ids = {s["id"] for s in cat["detectable_scenarios"]}
    out_of_artifact_ids = {s["id"] for s in cat.get("out_of_artifact_scenarios", [])}
    assert detectable_ids.isdisjoint(out_of_artifact_ids)
    for case in cat["cases"]:
        assert case["scenario_id"] in detectable_ids, (
            f"{category} case {case['id']} maps to {case['scenario_id']!r}, "
            f"which is not in the declared static-detectable tier"
        )
        assert case["scenario_id"] not in out_of_artifact_ids


def test_ast09_orphaned_skill_is_declared_out_of_artifact_and_uncovered(manifest):
    """S-003 exact scenario: AST09 Orphaned Skill is a process property, not an artifact one."""
    cat = manifest["categories"]["AST09"]
    out_ids = {s["id"]: s for s in cat["out_of_artifact_scenarios"]}
    orphaned = [s for s in out_ids.values() if s["name"] == "Orphaned Skill"]
    assert orphaned, "AST09 must declare an Orphaned Skill scenario"
    assert orphaned[0]["tier"] == "out-of-artifact"
    assert orphaned[0]["reason"].strip() != ""
    assert cat["detectable_scenarios"] == []
    assert cat["cases"] == []
    assert cat["status"] == "declared-and-uncovered"


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_scenario_has_a_written_reason(manifest, category):
    cat = manifest["categories"][category]
    for s in cat["detectable_scenarios"] + cat.get("out_of_artifact_scenarios", []):
        assert s.get("reason", "").strip(), f"{category} scenario {s['id']} missing a written reason"
        assert s["tier"] in {"static-detectable", "agent-judgable", "out-of-artifact"}


@pytest.mark.parametrize("category", CATEGORIES)
def test_case_fixture_files_exist_on_disk(manifest, category):
    cat = manifest["categories"][category]
    for case in cat["cases"]:
        case_path = REPO_ROOT / case["path"]
        assert case_path.exists(), f"{category} case {case['id']} declares missing path {case_path}"
        assert case_path.stat().st_size > 0


@pytest.mark.parametrize("category", CATEGORIES)
def test_tier_lock_hash_round_trips(manifest, category):
    """S-011 precondition: the manifest's stored hash matches a fresh recompute at rest."""
    cat = manifest["categories"][category]
    all_scenarios = cat["detectable_scenarios"] + cat.get("out_of_artifact_scenarios", [])
    ok, reason = check_tier_lock(all_scenarios, cat["tier_lock_hash"])
    assert ok, reason


def test_tier_reclassification_after_labeling_trips_the_lock(manifest):
    """S-011: reclassifying a scenario's tier after fixtures are labeled must be detectable.

    Given: AST01's fixtures were labeled against a tiering where a scenario is
      static-detectable.
    When: that scenario's tier is edited to agent-judgable (simulating a post-lock matrix edit).
    Then: recomputing the tier-lock hash no longer matches the locked hash bound in the
      manifest — the corpus is flagged for re-labeling and a judge re-run, not silently
      republished.
    """
    cat = manifest["categories"]["AST01"]
    scenarios = [dict(s) for s in cat["detectable_scenarios"]] + [
        dict(s) for s in cat.get("out_of_artifact_scenarios", [])
    ]
    assert scenarios, "AST01 must have at least one scenario to reclassify"

    locked_hash = cat["tier_lock_hash"]
    ok_before, _ = check_tier_lock(scenarios, locked_hash)
    assert ok_before, "manifest fixture must start tier-lock-valid before the mutation"

    mutated = [dict(s) for s in scenarios]
    reclassified_id = mutated[0]["id"]
    mutated[0]["tier"] = "agent-judgable"

    ok_after, reason = check_tier_lock(mutated, locked_hash)
    assert ok_after is False, "reclassifying a tier must trip the lock, not pass silently"
    assert reclassified_id in reason
    assert "re-labeling" in reason and "re-run" in reason
