"""T-3.1b — the authored coverage matrices for AST09 and AST10 are auditable and true.

`skills/<ID>/coverage-matrix.md` is the tier of record a reviewer reads: every SKILL.md in
these two categories points at it for the binding tier and written reason, and ADR-0004
makes it the document the F1 denominator is defended by. A matrix that has drifted from
`scenarios/registry.yaml`, from `fixtures/manifest.yaml`, or from the detector it claims to
describe is worse than no matrix, because it launders the drift as an audit trail.

These tests pin the three joins that make the matrix checkable:

  * registry join — every scenario the registry assigns to the category appears as a row,
    with the registry's own tier. A scenario dropped from the matrix, or tiered differently
    there than in the registry, fails.
  * corpus join — the tier-lock hash quoted in the matrix is the manifest's, the "no F1"
    claim matches `published_f1: null` / `status: declared-and-uncovered`, and the fixture
    count the matrix reports is the number of files actually on disk.
  * detector join — the matrix says these detectors register zero detector functions; the
    modules are imported and checked, so the claim cannot rot silently.

Scoped deliberately to AST09 and AST10 (this task's two categories) so it passes before the
other eight matrices are authored.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pytest
import yaml

from validators.tier_lock import check_tier_lock

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "scenarios" / "registry.yaml"
MANIFEST_PATH = REPO_ROOT / "fixtures" / "manifest.yaml"

CATEGORIES = ["AST09", "AST10"]
VALID_TIERS = {"static-detectable", "agent-judgable", "out-of-artifact"}

# One table row: "| AST09-S01 | Undetected Compromise | out-of-artifact | ... | ... |"
_ROW_RE = re.compile(r"^\|\s*(AST\d{2}-S\d{2})\s*\|(.+?)\|(.+?)\|", re.MULTILINE)


def _clean(cell: str) -> str:
    """Strip markdown emphasis and whitespace from a table cell."""
    return cell.replace("**", "").replace("`", "").strip()


@pytest.fixture(scope="module")
def registry() -> dict:
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def _matrix_path(category: str) -> pathlib.Path:
    return REPO_ROOT / "skills" / category / "coverage-matrix.md"


def _matrix_text(category: str) -> str:
    return _matrix_path(category).read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Whitespace-collapsed text, so a phrase test is not defeated by a line wrap."""
    return re.sub(r"\s+", " ", text)


def _matrix_rows(category: str) -> dict[str, tuple[str, str]]:
    """{scenario_id: (title, tier)} parsed from the matrix's scenario table."""
    rows: dict[str, tuple[str, str]] = {}
    for match in _ROW_RE.finditer(_matrix_text(category)):
        rows[match.group(1)] = (_clean(match.group(2)), _clean(match.group(3)))
    return rows


def _registry_scenarios(registry: dict, category: str) -> list[dict]:
    return [s for s in registry["scenarios"] if s["category"] == category]


def _load_detector(category: str):
    path = REPO_ROOT / "skills" / category / "scripts" / "detector.py"
    spec = importlib.util.spec_from_file_location(f"{category.lower()}_cm_detector", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- the file exists and is a real artifact -------------------------------


@pytest.mark.parametrize("category", CATEGORIES)
def test_coverage_matrix_exists(category):
    path = _matrix_path(category)
    assert path.is_file(), f"{path} does not exist"
    assert path.stat().st_size > 0


@pytest.mark.parametrize("category", CATEGORIES)
def test_skill_md_promise_is_kept(category):
    """Each SKILL.md defers the binding tier to coverage-matrix.md; the file must be there."""
    skill_md = (REPO_ROOT / "skills" / category / "SKILL.md").read_text(encoding="utf-8")
    assert "coverage-matrix.md" in skill_md
    assert _matrix_path(category).is_file()


# --- registry join --------------------------------------------------------


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_registry_scenario_has_a_row(registry, category):
    expected = {s["id"] for s in _registry_scenarios(registry, category)}
    assert expected, f"registry declares no scenarios for {category}"
    assert set(_matrix_rows(category)) == expected


@pytest.mark.parametrize("category", CATEGORIES)
def test_row_titles_are_the_registry_titles(registry, category):
    rows = _matrix_rows(category)
    for scenario in _registry_scenarios(registry, category):
        assert rows[scenario["id"]][0] == scenario["title"], (
            f"{scenario['id']}: matrix title {rows[scenario['id']][0]!r} "
            f"is not the whitepaper title {scenario['title']!r}"
        )


@pytest.mark.parametrize("category", CATEGORIES)
def test_row_tiers_match_the_authoritative_registry(registry, category):
    rows = _matrix_rows(category)
    for scenario in _registry_scenarios(registry, category):
        tier = rows[scenario["id"]][1]
        assert tier in VALID_TIERS, f"{scenario['id']}: {tier!r} is not a valid tier"
        assert tier == scenario["tier"], (
            f"{scenario['id']}: matrix says {tier!r}, registry says {scenario['tier']!r} "
            "-- the registry is authoritative; re-authoring the matrix is the fix"
        )


@pytest.mark.parametrize("category", CATEGORIES)
def test_declared_and_uncovered_section_lists_every_out_of_artifact_scenario(registry, category):
    text = _matrix_text(category)
    heading = "## Declared and uncovered"
    assert heading in text, f"{category} matrix has no '{heading}' section"
    section = text.split(heading, 1)[1].split("\n## ", 1)[0]
    for scenario in _registry_scenarios(registry, category):
        if scenario["tier"] != "out-of-artifact":
            continue
        assert scenario["id"] in section, (
            f"{scenario['id']} is out-of-artifact but absent from {category}'s declared-and-uncovered section"
        )
        assert "vidence" in _flat(section), "the section must say what evidence would decide it"


def test_ast10_records_its_uncovered_static_detectable_scenario(manifest):
    """AST10-S06 is detectable and unbuilt: declared as a gap, never as undetectable."""
    text = _matrix_text("AST10")
    uncovered = manifest["categories"]["AST10"]["registry_coverage"]["uncovered_static_detectable"]
    assert uncovered == ["AST10-S06"]
    assert "uncovered_static_detectable" in _flat(text)
    rows = _matrix_rows("AST10")
    assert rows["AST10-S06"][1] == "static-detectable"
    section = text.split("## Declared and uncovered", 1)[1].split("\n## ", 1)[0]
    assert "AST10-S06" in _flat(section) and "not" in _flat(section), (
        "AST10-S06 must be explicitly excluded from the out-of-artifact section"
    )


# --- corpus join ----------------------------------------------------------


@pytest.mark.parametrize("category", CATEGORIES)
def test_matrix_quotes_the_manifest_tier_lock_hash(manifest, category):
    locked = manifest["categories"][category]["tier_lock_hash"]
    assert locked in _flat(_matrix_text(category)), (
        f"{category} matrix does not quote the manifest's tier_lock_hash {locked}"
    )


@pytest.mark.parametrize("category", CATEGORIES)
def test_quoted_tier_lock_hash_still_recomputes(manifest, category):
    """S-011: the hash the matrix publishes must still bind the current tiering."""
    cat = manifest["categories"][category]
    scenarios = list(cat["detectable_scenarios"]) + list(cat.get("out_of_artifact_scenarios") or [])
    ok, reason = check_tier_lock(scenarios, cat["tier_lock_hash"])
    assert ok, reason


@pytest.mark.parametrize("category", CATEGORIES)
def test_no_f1_statement_matches_the_manifest(manifest, category):
    cat = manifest["categories"][category]
    assert cat["published_f1"] is None
    assert cat["status"] == "declared-and-uncovered"
    text = _flat(_matrix_text(category))
    assert "## F1 denominator" in text
    assert "declared-and-uncovered" in text
    assert "publishes no F1" in text or "no F1 number" in text


@pytest.mark.parametrize("category", CATEGORIES)
def test_reported_fixture_count_matches_disk_and_manifest(manifest, category):
    fixture_dir = REPO_ROOT / "fixtures" / category
    on_disk = [p for p in fixture_dir.rglob("*") if p.is_file()]
    assert on_disk == [], f"{category} matrix reports 0 fixture files; {len(on_disk)} are on disk"
    assert manifest["categories"][category]["cases"] == []
    text = _flat(_matrix_text(category))
    assert "## Corpus size" in text
    assert "directory exists and is empty" in text


def test_ast10_states_the_entitlement_it_would_owe_once_s06_is_labeled(manifest):
    """max(6, 2*1) = 6 -- pre-committed, so the corpus cannot later be sized to fit."""
    cat = manifest["categories"]["AST10"]
    assert cat["registry_coverage"]["cases_at_full_static_coverage"] == 6
    assert "6 cases" in _flat(_matrix_text("AST10"))


def test_ast09_has_no_detectable_tier_at_any_corpus_size(registry, manifest):
    tiers = {s["tier"] for s in _registry_scenarios(registry, "AST09")}
    assert tiers == {"out-of-artifact"}
    assert manifest["categories"]["AST09"]["detectable_scenarios"] == []
    assert manifest["categories"]["AST09"]["registry_coverage"]["cases_at_full_static_coverage"] is None
    assert "at any corpus size" in _flat(_matrix_text("AST09"))


# --- detector join --------------------------------------------------------


@pytest.mark.parametrize("category", CATEGORIES)
def test_matrix_claim_that_no_detector_function_is_registered_is_true(category):
    module = _load_detector(category)
    assert module.DETECTORS == {}, (
        f"{category}'s matrix says no detector function is registered, but "
        f"detector.py registers {sorted(module.DETECTORS)}"
    )
    assert module.STATIC_DETECTABLE == set()
    assert module.f1_report([]) == {"status": "declared-and-uncovered", "f1": None}
    text = _flat(_matrix_text(category))
    assert "no detector function is registered" in text or "zero detector functions" in text


@pytest.mark.parametrize("category", CATEGORIES)
def test_matrix_records_the_interim_scenario_tier_drift_in_detector_py(category):
    """The detector's interim SCENARIO_TIERS is a subset keyed by non-registry slugs.

    The matrix names that drift explicitly rather than letting a reader assume the module
    and the registry agree. If the module is ever brought onto registry ids, this test
    fails and the matrix's reconciliation paragraph must be rewritten -- which is the
    point: the two must not drift apart again unnoticed.
    """
    module = _load_detector(category)
    keys = set(module.SCENARIO_TIERS)
    assert keys and not any(re.fullmatch(r"AST\d{2}-S\d{2}", k) for k in keys)
    text = _flat(_matrix_text(category))
    assert "SCENARIO_TIERS" in text
    assert "tier of record" in text
