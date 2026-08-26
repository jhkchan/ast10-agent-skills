"""T-3.1a — the authoritative per-scenario registry and its reconciliation with the corpus.

`scenarios/registry.yaml` enumerates every attack scenario named in the OWASP Agentic
Skills Top 10 whitepaper's ten "Attack Scenarios" sections and assigns each exactly one
tier. It is authoritative: `fixtures/manifest.yaml` links its labeled fixture checks back
to registry scenario ids and must agree with the registry on tier.

What these tests defend:

  * The count is extracted, not assumed. 62 scenarios — four of them body sub-headings the
    whitepaper's own table of contents omits. A silent drift in either direction fails.
  * Every scenario has a unique canonical id, exactly one valid tier, and a written reason.
    An untiered or unreasoned scenario cannot enter the registry.
  * `artifact_signal` — the enabling precondition a package CAN show for a scenario it
    cannot decide — never appears on a static-detectable scenario, because a
    static-detectable scenario is decided outright rather than proxied.
  * The manifest and the registry agree on tier. A fixture check declared `covers: full`
    must link only to registry scenarios the registry independently tiers the same way;
    a check that measures a proxy must say `covers: artifact-signal-only` and link a
    scenario that actually declares an `artifact_signal`. This is what stops an F1 for
    "unpinned reference detection" being published as an F1 for "Author Rug-Pull".
  * The gate-4 corpus-size formula still holds, and each category's coverage debt against
    the registry is recorded rather than hidden.
  * Every category's `tier_lock_hash` recomputes (S-011), so the reconciliation itself is
    bound to the tiering it was performed against.
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

from validators.tier_lock import check_manifest_tier_locks, tier_lock_hash

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "scenarios" / "registry.yaml"
MANIFEST_PATH = REPO_ROOT / "fixtures" / "manifest.yaml"

CATEGORIES = [f"AST{i:02d}" for i in range(1, 11)]
VALID_TIERS = {"static-detectable", "agent-judgable", "out-of-artifact"}
VALID_COVERS = {"full", "artifact-signal-only", "category-precondition"}

# Extracted from the whitepaper body, not from its table of contents (which omits four).
WHITEPAPER_SCENARIOS_PER_CATEGORY = {
    "AST01": 11,
    "AST02": 4,
    "AST03": 5,
    "AST04": 7,
    "AST05": 6,
    "AST06": 5,
    "AST07": 3,
    "AST08": 8,
    "AST09": 7,
    "AST10": 6,
}
TOTAL_SCENARIOS = 62

_ID_RE = re.compile(r"^(AST\d{2})-S(\d{2})$")


@pytest.fixture(scope="module")
def registry() -> dict:
    assert REGISTRY_PATH.exists(), f"missing {REGISTRY_PATH}"
    data = yaml.safe_load(REGISTRY_PATH.read_text())
    assert data is not None, "registry.yaml parsed to nothing"
    return data


@pytest.fixture(scope="module")
def scenarios(registry) -> list[dict]:
    return registry["scenarios"]


@pytest.fixture(scope="module")
def by_id(scenarios) -> dict[str, dict]:
    return {s["id"]: s for s in scenarios}


@pytest.fixture(scope="module")
def manifest() -> dict:
    data = yaml.safe_load(MANIFEST_PATH.read_text())
    assert data is not None, "manifest.yaml parsed to nothing"
    return data


def _manifest_entries(manifest: dict):
    """Yield (category, entry) for every scenario entry in every category."""
    for category, cat in manifest["categories"].items():
        for entry in list(cat["detectable_scenarios"]) + list(cat.get("out_of_artifact_scenarios") or []):
            yield category, entry


# --- registry shape --------------------------------------------------------


def test_every_scenario_id_is_unique(scenarios):
    ids = [s["id"] for s in scenarios]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicates, f"duplicate scenario ids: {duplicates}"


def test_every_scenario_id_is_canonical_and_matches_its_category(scenarios):
    for s in scenarios:
        match = _ID_RE.match(s["id"])
        assert match, f"{s['id']!r} is not of the form ASTnn-Snn"
        assert match.group(1) == s["category"], f"{s['id']} declares category {s['category']!r}"


def test_scenario_ids_are_contiguous_within_each_category(scenarios):
    """No gaps: a missing number would mean a scenario was dropped silently."""
    for category in CATEGORIES:
        numbers = sorted(int(_ID_RE.match(s["id"]).group(2)) for s in scenarios if s["category"] == category)
        assert numbers == list(range(1, len(numbers) + 1)), f"{category} ids are not contiguous: {numbers}"


def test_every_scenario_has_exactly_one_valid_tier(scenarios):
    for s in scenarios:
        assert s["tier"] in VALID_TIERS, f"{s['id']}: invalid tier {s['tier']!r}"


def test_every_scenario_has_a_nonempty_written_reason(scenarios):
    for s in scenarios:
        assert str(s.get("reason", "")).strip(), f"{s['id']} has no written reason"


def test_every_scenario_has_a_title_and_description(scenarios):
    for s in scenarios:
        assert str(s.get("title", "")).strip(), f"{s['id']} has no whitepaper title"
        assert str(s.get("description", "")).strip(), f"{s['id']} has no description"


def test_all_ten_ast_categories_appear(scenarios, registry):
    present = {s["category"] for s in scenarios}
    assert present == set(CATEGORIES), f"missing categories: {set(CATEGORIES) - present}"
    assert set(registry["categories"]) == set(CATEGORIES)


def test_scenario_counts_match_the_whitepaper_extraction(scenarios):
    """Guards the extraction itself: the TOC lists 58, the body names 62."""
    counted = {c: sum(1 for s in scenarios if s["category"] == c) for c in CATEGORIES}
    assert counted == WHITEPAPER_SCENARIOS_PER_CATEGORY
    assert len(scenarios) == TOTAL_SCENARIOS


def test_declared_counts_agree_with_the_scenario_list(registry, scenarios):
    assert registry["counts"]["total"] == len(scenarios)
    for category, meta in registry["categories"].items():
        actual = sum(1 for s in scenarios if s["category"] == category)
        assert meta["scenario_count"] == actual, f"{category} count drifted"
    for tier, declared in registry["counts"]["by_tier"].items():
        actual = sum(1 for s in scenarios if s["tier"] == tier)
        assert declared == actual, f"declared {tier} count {declared} != actual {actual}"


def test_static_detectable_scenarios_carry_no_artifact_signal(scenarios):
    """`artifact_signal` is a partial proxy for a scenario the package cannot decide.

    A static-detectable scenario is decided outright, so attaching a proxy to one would
    blur exactly the line the tiering exists to draw.
    """
    for s in scenarios:
        if s["tier"] == "static-detectable":
            assert not s.get("artifact_signal"), f"{s['id']} is static-detectable yet declares an artifact_signal"


def test_the_locked_out_of_artifact_scenarios_are_tiered_out_of_artifact(by_id):
    """The doctrine's named examples must not drift back into the detectable tier."""
    locked = {
        "AST02-S04": "Maintainer Account Takeover",
        "AST07-S02": "Rollback Attack",
        "AST07-S03": "Hot-Reload Abuse",
        "AST09-S01": "Undetected Compromise",
        "AST09-S03": "Orphaned Skill",
        "AST09-S04": "Regulatory Exposure",
        "AST10-S02": "Cross-Registry Arbitrage",
        "AST10-S03": "Multi-Platform Campaign",
    }
    for scenario_id, title in locked.items():
        scenario = by_id[scenario_id]
        assert scenario["title"] == title, f"{scenario_id} title drifted"
        assert scenario["tier"] == "out-of-artifact", f"{scenario_id} ({title}) must stay out-of-artifact"


def test_ast09_has_no_static_detectable_scenario(scenarios):
    """Every AST09 scenario turns on organisational process, so AST09 publishes no F1."""
    ast09 = [s for s in scenarios if s["category"] == "AST09"]
    assert ast09
    assert all(s["tier"] == "out-of-artifact" for s in ast09)


# --- registry <-> fixtures/manifest.yaml reconciliation --------------------


def test_manifest_points_at_the_registry(manifest, scenarios):
    assert manifest["registry"] == "scenarios/registry.yaml"
    assert manifest["registry_scenario_count"] == len(scenarios)


def test_every_manifest_entry_declares_registry_ids_and_a_covers_mode(manifest):
    for category, entry in _manifest_entries(manifest):
        assert "registry_ids" in entry, f"{category}/{entry['id']} has no registry_ids"
        assert entry.get("covers") in VALID_COVERS, (
            f"{category}/{entry['id']} has invalid covers {entry.get('covers')!r}"
        )


def test_every_referenced_registry_id_resolves(manifest, by_id):
    for category, entry in _manifest_entries(manifest):
        for rid in entry["registry_ids"]:
            assert rid in by_id, f"{category}/{entry['id']} references unknown registry id {rid!r}"


def test_registry_and_manifest_agree_on_tiers(manifest, by_id):
    """The core reconciliation invariant.

    `covers: full` asserts the fixture pair measures the named scenario itself, so every
    linked registry scenario must carry the same tier the manifest entry claims. Anything
    else is the manifest declaring a detectability the registry does not grant.
    """
    for category, entry in _manifest_entries(manifest):
        if entry["covers"] != "full":
            continue
        for rid in entry["registry_ids"]:
            assert by_id[rid]["tier"] == entry["tier"], (
                f"{category}/{entry['id']} claims tier {entry['tier']!r} at covers: full "
                f"but registry tiers {rid} as {by_id[rid]['tier']!r} — the registry wins"
            )


def test_manifest_entries_keyed_by_a_registry_id_match_that_scenario(manifest, by_id):
    """Where a manifest entry IS a whitepaper scenario, id, title, and tier must line up."""
    for category, entry in _manifest_entries(manifest):
        if entry["id"] not in by_id:
            continue
        scenario = by_id[entry["id"]]
        assert entry["tier"] == scenario["tier"], (
            f"{category}/{entry['id']} tier {entry['tier']!r} != registry {scenario['tier']!r}"
        )
        assert entry["name"] == scenario["title"], (
            f"{category}/{entry['id']} name {entry['name']!r} != whitepaper title {scenario['title']!r}"
        )
        assert entry["registry_ids"] == [entry["id"]]


def test_artifact_signal_only_entries_proxy_a_scenario_that_declares_a_signal(manifest, by_id):
    """A proxy corpus must name what it proxies, and the target must not be decidable."""
    for category, entry in _manifest_entries(manifest):
        if entry["covers"] != "artifact-signal-only":
            continue
        assert entry["registry_ids"], f"{category}/{entry['id']} is artifact-signal-only but links no scenario"
        for rid in entry["registry_ids"]:
            scenario = by_id[rid]
            assert scenario["tier"] != "static-detectable", (
                f"{category}/{entry['id']} proxies {rid}, which the registry already "
                f"tiers static-detectable — it should be covers: full"
            )
            assert str(scenario.get("artifact_signal") or "").strip(), (
                f"{category}/{entry['id']} proxies {rid}, which declares no artifact_signal to proxy"
            )


def test_category_precondition_entries_state_their_derivation(manifest):
    for category, entry in _manifest_entries(manifest):
        if entry["covers"] != "category-precondition":
            continue
        assert entry["registry_ids"] == [], f"{category}/{entry['id']} is category-precondition yet links a scenario"
        assert str(entry.get("derivation", "")).strip(), (
            f"{category}/{entry['id']} must state where it derives from instead"
        )


@pytest.mark.parametrize("category", CATEGORIES)
def test_registry_coverage_block_matches_the_registry(manifest, scenarios, category):
    cat = manifest["categories"][category]
    coverage = cat["registry_coverage"]
    in_category = [s for s in scenarios if s["category"] == category]
    by_tier = {tier: sum(1 for s in in_category if s["tier"] == tier) for tier in VALID_TIERS}
    assert coverage["registry_scenarios"] == len(in_category)
    assert coverage["registry_static_detectable"] == by_tier["static-detectable"]
    assert coverage["registry_agent_judgable"] == by_tier["agent-judgable"]
    assert coverage["registry_out_of_artifact"] == by_tier["out-of-artifact"]


@pytest.mark.parametrize("category", CATEGORIES)
def test_declared_expected_size_follows_the_locked_formula(manifest, category):
    """gate-4 stays satisfied after reconciliation, and the declared size is explicit."""
    min_floor = manifest["min_floor"]
    cat = manifest["categories"][category]
    coverage = cat["registry_coverage"]
    labeled = len(cat["detectable_scenarios"])

    assert coverage["labeled_detectable_checks"] == labeled
    assert coverage["cases_present"] == len(cat["cases"])

    expected = max(min_floor, 2 * labeled) if labeled else 0
    assert coverage["declared_expected_cases"] == expected
    # ADR-0007: the formula is a floor. `declared_expected_cases` stays the
    # entitlement the formula yields; the corpus may exceed it, and AST02 does.
    assert len(cat["cases"]) >= expected


@pytest.mark.parametrize("category", CATEGORIES)
def test_full_registry_coverage_target_follows_the_same_formula(manifest, category):
    """What the corpus WOULD have to be to cover the registry's static tier."""
    min_floor = manifest["min_floor"]
    coverage = manifest["categories"][category]["registry_coverage"]
    static = coverage["registry_static_detectable"]
    expected = max(min_floor, 2 * static) if static else None
    assert coverage["cases_at_full_static_coverage"] == expected


def test_uncovered_static_detectable_lists_are_accurate(manifest, scenarios):
    """The published coverage debt must be the real one, computed from covers: full."""
    covered = {
        rid for _, entry in _manifest_entries(manifest) if entry["covers"] == "full" for rid in entry["registry_ids"]
    }
    for category in CATEGORIES:
        static_ids = {s["id"] for s in scenarios if s["category"] == category and s["tier"] == "static-detectable"}
        declared = manifest["categories"][category]["registry_coverage"]["uncovered_static_detectable"]
        assert sorted(declared or []) == sorted(static_ids - covered), (
            f"{category}: declared uncovered list does not match the registry"
        )


def test_every_category_declares_an_f1_scope_consistent_with_its_checks(manifest):
    for category, cat in manifest["categories"].items():
        modes = {e["covers"] for e in cat["detectable_scenarios"]}
        scope = cat["f1_scope"]
        if not modes:
            assert scope == "none", f"{category}: no labeled checks but f1_scope={scope}"
        elif modes == {"full"}:
            assert scope == "scenario-level", f"{category}: f1_scope={scope}"
        elif modes == {"artifact-signal-only"}:
            assert scope == "artifact-signal-only", f"{category}: f1_scope={scope}"
        elif modes == {"category-precondition"}:
            assert scope == "category-precondition", f"{category}: f1_scope={scope}"
        else:
            assert scope == "mixed-proxy", f"{category}: f1_scope={scope}"


def test_status_reflects_whether_any_labeled_check_is_a_proxy(manifest):
    for category, cat in manifest["categories"].items():
        modes = {e["covers"] for e in cat["detectable_scenarios"]}
        if not modes:
            assert cat["status"] == "declared-and-uncovered", category
            assert cat.get("published_f1") is None, category
        elif modes == {"full"}:
            assert cat["status"] == "covered", category
        else:
            assert cat["status"] == "proxy-covered", (
                f"{category}: labels a proxy check but claims status {cat['status']!r}"
            )


# --- S-011 tier lock -------------------------------------------------------


def test_every_tier_lock_hash_recomputes_after_reconciliation(manifest):
    violations = check_manifest_tier_locks(manifest)
    assert violations == [], violations


@pytest.mark.parametrize("category", CATEGORIES)
def test_tier_lock_hash_is_bound_to_the_reconciled_tiering(manifest, category):
    cat = manifest["categories"][category]
    scenarios = list(cat["detectable_scenarios"]) + list(cat.get("out_of_artifact_scenarios") or [])
    assert tier_lock_hash(scenarios) == cat["tier_lock_hash"]


def test_reclassifying_a_registry_scenario_would_trip_a_category_lock(manifest):
    """S-011 end to end: the registry is authoritative, so a tier edit there must force
    the corpus that was labeled against it back through re-labeling and a judge re-run."""
    cat = manifest["categories"]["AST05"]
    entries = [dict(e) for e in cat["detectable_scenarios"]] + [
        dict(e) for e in (cat.get("out_of_artifact_scenarios") or [])
    ]
    assert entries, "AST05 must have entries to reclassify"
    assert tier_lock_hash(entries) == cat["tier_lock_hash"]

    entries[0]["tier"] = "out-of-artifact"
    assert tier_lock_hash(entries) != cat["tier_lock_hash"]
