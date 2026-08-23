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
  * corpus join — the tier-lock hash quoted in the matrix is the manifest's, each matrix's
    F1 statement matches its manifest entry (AST09: `published_f1: null` /
    `declared-and-uncovered`; AST10: the same number the manifest publishes, its scope, and
    its confusion matrix), and the fixture count the matrix reports is the corpus actually
    on disk.
  * detector join — the "what the detector actually checks" column is a claim about
    running code, so the modules are imported and checked against it. AST09 ships zero
    detector functions and its matrix must say so in those words; AST10 ships exactly one,
    for the one scenario the registry tiers static-detectable, and its matrix must name
    that function, both of its firing conditions, and the F1 it publishes. Neither claim
    can rot silently.

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


def test_ast10s_one_detectable_scenario_is_covered_not_declared_a_gap(manifest):
    """AST10-S06 is detectable AND built: the coverage debt for this category is zero.

    This test replaces an earlier one that pinned AST10-S06 as an uncovered gap. The gap
    was closed by implementing the detector, so the pin now runs the other way: the
    manifest must claim no uncovered static-detectable scenario, the matrix must show the
    row as static-detectable, and it must still say explicitly that S06 is *not* one of
    the out-of-artifact scenarios -- so a reader who remembers the gap is told where it
    went rather than left to infer it.
    """
    text = _matrix_text("AST10")
    coverage = manifest["categories"]["AST10"]["registry_coverage"]
    assert coverage["uncovered_static_detectable"] == []
    assert coverage["labeled_detectable_checks"] == 1
    rows = _matrix_rows("AST10")
    assert rows["AST10-S06"][1] == "static-detectable"
    section = text.split("## Declared and uncovered", 1)[1].split("\n## ", 1)[0]
    assert "AST10-S06" in _flat(section) and "not" in _flat(section), (
        "AST10-S06 must be explicitly excluded from the out-of-artifact section"
    )


def test_ast10_matrix_describes_the_mechanism_its_detector_actually_runs():
    """The "what the detector checks" column is a claim about running code.

    A matrix that said "decodes encoded blocks" while the module shipped a keyword grep
    would launder the drift as an audit trail, which is the whole failure mode this file
    exists to catch. The function must exist and be callable, both firing conditions must
    be named, and so must the exclusion that makes the check discriminate -- a reader who
    is told only what fires cannot tell a detector from a base64 alarm.
    """
    text = _flat(_matrix_text("AST10"))
    module = _load_detector("AST10")
    assert callable(getattr(module, "detect_encoded_payload_injection", None))
    assert "detect_encoded_payload_injection" in text
    for phrase in ("decode-and-rescan", "decode-then-execute", "content_hash"):
        assert phrase in text, f"AST10 matrix does not describe {phrase!r}"


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


def test_ast09_f1_statement_matches_the_manifest(manifest):
    """AST09's detectable tier is empty, so its matrix must publish no number at all."""
    cat = manifest["categories"]["AST09"]
    assert cat["published_f1"] is None
    assert cat["status"] == "declared-and-uncovered"
    assert cat["f1_scope"] == "none"
    text = _flat(_matrix_text("AST09"))
    assert "## F1 denominator" in text
    assert "declared-and-uncovered" in text
    assert "publishes no F1" in text or "no F1 number" in text


def test_ast10_f1_statement_matches_the_manifest(manifest):
    """AST10 publishes a number, so the matrix must publish the SAME number and its scope."""
    cat = manifest["categories"]["AST10"]
    published = cat["published_f1"]
    assert isinstance(published, float), f"AST10 published_f1 must be a measured number, got {published!r}"
    assert cat["status"] == "covered"
    assert cat["f1_scope"] == "scenario-level"
    text = _flat(_matrix_text("AST10"))
    assert "## F1 denominator" in text
    assert f"{published:.2f}" in text, f"AST10 matrix does not quote its published F1 {published:.2f}"
    assert "scenario-level" in text
    # A perfect score on a self-authored corpus is a claim about the corpus as much as
    # about the detector, so the matrix has to say what the corpus is before it is quoted.
    assert "tp 3" in text and "fp 0" in text, "the matrix must publish the confusion matrix, not just the F1"
    assert "hard" in text, "the matrix must state why the negatives are hard negatives"


@pytest.mark.parametrize("category", CATEGORIES)
def test_reported_fixture_count_matches_disk_and_manifest(manifest, category):
    """The matrix's corpus-size table must be the corpus that is actually on disk."""
    fixture_dir = REPO_ROOT / "fixtures" / category
    packages = sorted(p.name for p in fixture_dir.iterdir() if p.is_dir()) if fixture_dir.is_dir() else []
    declared = manifest["categories"][category]["cases"]
    text = _flat(_matrix_text(category))
    assert "## Corpus size" in text

    assert len(packages) == len(declared), (
        f"{category}: {len(packages)} fixture package(s) on disk, {len(declared)} declared in the manifest"
    )
    for case in declared:
        assert (REPO_ROOT / case["path"]).is_file(), f"{category} case {case['id']} path is missing"

    if not declared:
        assert "directory exists and is empty" in text
    else:
        assert f"**{len(packages)}**" in text, f"{category} matrix does not report its {len(packages)} fixture packages"


def test_ast10_corpus_is_the_size_the_locked_formula_demands(manifest):
    """max(6, 2*1) = 6 -- pre-committed before the corpus was built, and met."""
    cat = manifest["categories"]["AST10"]
    assert cat["registry_coverage"]["cases_at_full_static_coverage"] == 6
    assert cat["registry_coverage"]["declared_expected_cases"] == 6
    assert len(cat["cases"]) == 6
    labels = [c["label"] for c in cat["cases"]]
    assert labels.count("vulnerable") == labels.count("clean") == 3
    assert "6 cases" in _flat(_matrix_text("AST10"))


def test_ast09_has_no_detectable_tier_at_any_corpus_size(registry, manifest):
    tiers = {s["tier"] for s in _registry_scenarios(registry, "AST09")}
    assert tiers == {"out-of-artifact"}
    assert manifest["categories"]["AST09"]["detectable_scenarios"] == []
    assert manifest["categories"]["AST09"]["registry_coverage"]["cases_at_full_static_coverage"] is None
    assert "at any corpus size" in _flat(_matrix_text("AST09"))


# --- detector join --------------------------------------------------------


@pytest.mark.parametrize("category", CATEGORIES)
def test_registered_detectors_are_exactly_the_registrys_static_detectable_tier(registry, category):
    """The detector join, run in both directions.

    A module may not ship a check for a scenario the registry does not tier
    static-detectable (granting itself a detectability), and may not omit one it does
    (a silent coverage gap that the matrix would then have to be trusted to disclose).
    """
    module = _load_detector(category)
    expected = {s["id"] for s in _registry_scenarios(registry, category) if s["tier"] == "static-detectable"}
    assert set(module.DETECTORS) == expected, (
        f"{category}: detector.py registers {sorted(module.DETECTORS)}, the registry tiers "
        f"{sorted(expected)} static-detectable"
    )
    assert module.STATIC_DETECTABLE == expected
    assert set(module.CHECK_COVERAGE) == expected


def test_ast09_matrix_claim_that_no_detector_function_is_registered_is_true():
    """AST09 alone ships nothing, and its matrix has to say so in those words."""
    module = _load_detector("AST09")
    assert module.DETECTORS == {}
    assert module.STATIC_DETECTABLE == set()
    assert module.f1_report([]) == {"status": "declared-and-uncovered", "f1": None, "scope": "none"}
    # No shipped check means nothing whose coverage could be claimed, so the
    # scope label the report carries is "none" rather than absent.
    assert module.CHECK_COVERAGE == {}
    assert module.F1_SCOPE == "none"
    text = _flat(_matrix_text("AST09"))
    assert "no detector function is registered" in text or "zero detector functions" in text


def test_ast10_detector_reports_a_scenario_level_scope_the_matrix_agrees_with():
    module = _load_detector("AST10")
    assert module.F1_SCOPE == "scenario-level"
    assert module.CHECK_COVERAGE["AST10-S06"]["covers"] == "full"
    assert "scenario-level" in _flat(_matrix_text("AST10"))


@pytest.mark.parametrize("category", CATEGORIES)
def test_detector_scenario_tiers_are_canonical_registry_ids_and_complete(registry, category):
    """The successor to the old interim-drift pin, run the other way round.

    Both modules used to key SCENARIO_TIERS by private slugs
    (`AST09-orphaned-skill`, `AST10-cross-registry-arbitrage`) and to enumerate only a
    subset of their category's scenarios; the matrices recorded that as a known drift.
    The drift is closed, so what is pinned now is the closed state: registry ids, every
    scenario, and the registry's own tier for each. The matrices' reconciliation
    paragraphs must keep saying which document is the tier of record.
    """
    module = _load_detector(category)
    scenarios = {s["id"]: s["tier"] for s in _registry_scenarios(registry, category)}
    assert set(module.SCENARIO_TIERS) == set(scenarios), (
        f"{category}: SCENARIO_TIERS is {sorted(module.SCENARIO_TIERS)}, registry has {sorted(scenarios)}"
    )
    for scenario_id, tier in scenarios.items():
        assert re.fullmatch(r"AST\d{2}-S\d{2}", scenario_id)
        assert module.SCENARIO_TIERS[scenario_id] == tier, scenario_id
    text = _flat(_matrix_text(category))
    assert "SCENARIO_TIERS" in text
    assert "tier of record" in text
