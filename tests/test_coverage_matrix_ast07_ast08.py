"""T-3.1b — the AST07 and AST08 coverage matrices, bound to what they claim about.

A coverage matrix is the artifact ADR-0004 offers as the defence of a narrowed F1
denominator, so it is only worth anything if it cannot quietly drift away from the three
things it reports on:

  * `scenarios/registry.yaml` — the authoritative tiering. Every scenario the registry
    names for the category must appear as exactly one row, with the registry's own title,
    tier, and *verbatim* written reason. A reworded reason is drift; a missing row is a
    scenario silently dropped from the audit.
  * `skills/<ID>/scripts/detector.py` — the real detector. A row may only name a detector
    function that is actually registered for that scenario id. Where the registry tiers a
    scenario static-detectable and no such function exists, the row must say so out loud
    rather than leaving the column blank or hopeful.
  * `fixtures/manifest.yaml` and `fixtures/<ID>/` — the corpus. The entitlement and the
    on-disk file count printed in the matrix must be the real ones.

Plus one self-referential check: neither matrix may itself carry invisible Unicode. AST08's
matrix quotes an invisible-code-point character class, and pasting the literal glyphs
instead of `\\uXXXX` escapes would smuggle exactly what the rule exists to catch into a
document reviewers read by eye.

Scoped to AST07 and AST08 (this task's categories). The helpers are category-generic, so a
later task adding more matrices extends `CATEGORIES` rather than rewriting the module.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "scenarios" / "registry.yaml"
MANIFEST_PATH = REPO_ROOT / "fixtures" / "manifest.yaml"

CATEGORIES = ["AST07", "AST08"]

# The same class detectors/scaffold.py scans for, written in escapes for the same reason.
INVISIBLE_UNICODE_RE = re.compile("[\\u200b-\\u200f\\u202a-\\u202e\\u2060-\\u2064\\u2066-\\u2069\\ufeff]")

# A scenario row: | `AST08-S01` | Title | `tier` | detector cell | reason |
ROW_RE = re.compile(
    r"^\|\s*`(?P<id>AST\d{2}-S\d{2})`\s*\|(?P<rest>.*)\|\s*$",
    re.MULTILINE,
)

NOT_DETECTABLE_CELL = "—"
NOTHING_SHIPPED_CELL = "**`nothing shipped`**"


@pytest.fixture(scope="module")
def registry() -> dict:
    return yaml.safe_load(REGISTRY_PATH.read_text())


@pytest.fixture(scope="module")
def manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text())


def matrix_path(category: str) -> Path:
    return REPO_ROOT / "skills" / category / "coverage-matrix.md"


def matrix_text(category: str) -> str:
    return matrix_path(category).read_text(encoding="utf-8")


def registry_scenarios(registry: dict, category: str) -> list[dict]:
    return [s for s in registry["scenarios"] if s["category"] == category]


def parse_rows(text: str) -> dict[str, list[str]]:
    """Scenario id -> [title, tier, detector, reason], from the matrix's scenario table."""
    rows: dict[str, list[str]] = {}
    for match in ROW_RE.finditer(text):
        cells = [c.strip() for c in match.group("rest").split("|")]
        assert len(cells) == 4, (
            f"{match.group('id')} row has {len(cells)} cells after the id, expected 4 "
            f"(title | tier | detector | reason)"
        )
        rows[match.group("id")] = cells
    return rows


def load_detector(category: str):
    path = REPO_ROOT / "skills" / category / "scripts" / "detector.py"
    spec = importlib.util.spec_from_file_location(f"{category.lower()}_detector", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fixture_file_count(category: str) -> int:
    """Every file the corpus ships, not only its Markdown.

    Counting `*.md` was right while every fixture was a lone SKILL.md. AST08's
    corpus now ships Python sources, real zip archives, real `.pyc` files and
    symlinks, because three of its four static-detectable scenarios are not
    expressible in Markdown -- and a matrix that printed only the Markdown count
    would understate the corpus an auditor has to review. Symlinks are counted
    without following them: `is_file()` alone resolves the link, which is the
    traversal AST08-S07 is about.
    """
    base = REPO_ROOT / "fixtures" / category
    if not base.exists():
        return 0
    return sum(1 for path in base.rglob("*") if path.is_symlink() or path.is_file())


# --- the file exists and is the one SKILL.md points at ---------------------


@pytest.mark.parametrize("category", CATEGORIES)
def test_coverage_matrix_exists(category):
    assert matrix_path(category).is_file(), f"missing {matrix_path(category)}"


@pytest.mark.parametrize("category", CATEGORIES)
def test_skill_md_references_the_matrix_it_ships(category):
    """SKILL.md defers its frozen tiers to this file; the promise must resolve."""
    skill_md = (REPO_ROOT / "skills" / category / "SKILL.md").read_text(encoding="utf-8")
    assert "coverage-matrix.md" in skill_md
    assert matrix_path(category).is_file()


# --- the table agrees with the authoritative registry ----------------------


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_registry_scenario_has_exactly_one_row(registry, category):
    rows = parse_rows(matrix_text(category))
    expected = {s["id"] for s in registry_scenarios(registry, category)}
    assert set(rows) == expected, (
        f"{category}: matrix rows {sorted(set(rows))} != registry scenarios {sorted(expected)}"
    )


@pytest.mark.parametrize("category", CATEGORIES)
def test_row_titles_and_tiers_match_the_registry(registry, category):
    rows = parse_rows(matrix_text(category))
    for scenario in registry_scenarios(registry, category):
        title, tier, _detector, _reason = rows[scenario["id"]]
        assert title == scenario["title"], (
            f"{scenario['id']}: matrix title {title!r} != whitepaper title {scenario['title']!r}"
        )
        assert tier == f"`{scenario['tier']}`", (
            f"{scenario['id']}: matrix tier {tier!r} != registry tier {scenario['tier']!r} — the registry wins"
        )


@pytest.mark.parametrize("category", CATEGORIES)
def test_row_reasons_are_the_registry_reasons_verbatim(registry, category):
    """A paraphrase is drift: the reason is the load-bearing part of the tiering."""
    rows = parse_rows(matrix_text(category))
    for scenario in registry_scenarios(registry, category):
        _title, _tier, _detector, reason = rows[scenario["id"]]
        assert reason == scenario["reason"].strip(), (
            f"{scenario['id']}: matrix reason has drifted from scenarios/registry.yaml"
        )


# --- the detector column describes the detector that actually ships --------


@pytest.mark.parametrize("category", CATEGORIES)
def test_detector_column_never_claims_a_function_that_is_not_registered(registry, category):
    detector = load_detector(category)
    rows = parse_rows(matrix_text(category))
    for scenario in registry_scenarios(registry, category):
        _title, _tier, cell, _reason = rows[scenario["id"]]
        if cell in (NOT_DETECTABLE_CELL, NOTHING_SHIPPED_CELL):
            continue
        assert scenario["id"] in detector.DETECTORS, (
            f"{scenario['id']}: matrix names a detector ({cell!r}) but "
            f"{category}/scripts/detector.py registers no function for that id "
            f"(registered: {sorted(detector.DETECTORS)})"
        )


@pytest.mark.parametrize("category", CATEGORIES)
def test_unimplemented_static_detectable_rows_say_so(registry, category):
    """The debt must be visible in the table, not only in the prose below it."""
    detector = load_detector(category)
    rows = parse_rows(matrix_text(category))
    for scenario in registry_scenarios(registry, category):
        if scenario["tier"] != "static-detectable":
            continue
        if scenario["id"] in detector.DETECTORS:
            continue
        _title, _tier, cell, _reason = rows[scenario["id"]]
        assert cell == NOTHING_SHIPPED_CELL, (
            f"{scenario['id']} is static-detectable with no detector function, so its "
            f"row must read {NOTHING_SHIPPED_CELL} — found {cell!r}"
        )


@pytest.mark.parametrize("category", CATEGORIES)
def test_non_detectable_rows_carry_the_em_dash(registry, category):
    rows = parse_rows(matrix_text(category))
    for scenario in registry_scenarios(registry, category):
        if scenario["tier"] == "static-detectable":
            continue
        _title, _tier, cell, _reason = rows[scenario["id"]]
        assert cell == NOT_DETECTABLE_CELL, (
            f"{scenario['id']} is {scenario['tier']}, so its detector cell must be "
            f"{NOT_DETECTABLE_CELL!r} — found {cell!r}"
        )


# --- declared-and-uncovered section ----------------------------------------


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    rest = text[start + len(heading) :]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_out_of_artifact_scenario_is_named_in_declared_and_uncovered(registry, category):
    section = _section(matrix_text(category), "\n## Declared and uncovered\n")
    for scenario in registry_scenarios(registry, category):
        if scenario["tier"] != "out-of-artifact":
            continue
        assert scenario["id"] in section, (
            f"{scenario['id']} is out-of-artifact but is not covered in {category}'s 'Declared and uncovered' section"
        )
        assert scenario["title"] in section, f"{scenario['id']} title missing there"


@pytest.mark.parametrize("category", CATEGORIES)
def test_declared_and_uncovered_states_the_evidence_that_would_decide(category):
    """S-003's whole point: an uncovered scenario names what would cover it."""
    section = _section(matrix_text(category), "\n## Declared and uncovered\n")
    assert "Evidence that would decide it" in section, (
        f"{category}: 'Declared and uncovered' must state what evidence would decide "
        f"each scenario, not only why the package cannot"
    )


# --- the F1 denominator statement ------------------------------------------


def test_ast07_publishes_no_f1_and_the_detector_agrees(manifest):
    """Empty detectable tier: the matrix, the manifest, and the module must all say so."""
    text = matrix_text("AST07")
    assert "**Which scenarios count: none. AST07 publishes no F1.**" in text

    cat = manifest["categories"]["AST07"]
    assert cat["status"] == "declared-and-uncovered"
    assert cat["f1_scope"] == "none"
    assert cat["published_f1"] is None

    report = load_detector("AST07").f1_report()
    assert report == {"status": "declared-and-uncovered", "f1": None, "scope": "none"}


def test_ast08_f1_denominator_names_its_four_static_detectable_scenarios(registry):
    """Non-empty detectable tier: the denominator is enumerated, not hand-waved."""
    section = _section(matrix_text("AST08"), "\n## F1 denominator for AST08\n")
    static_ids = sorted(s["id"] for s in registry_scenarios(registry, "AST08") if s["tier"] == "static-detectable")
    assert len(static_ids) == 4
    for scenario_id in static_ids:
        assert scenario_id in section, (
            f"{scenario_id} is in AST08's F1 denominator but the denominator statement does not name it"
        )


def test_ast08_does_not_claim_the_empty_tier_exemption():
    """AST08's silence is a debt; only an empty detectable tier earns the carve-out."""
    text = matrix_text("AST08")
    assert "not entitled to the empty-tier exemption" in text


# --- corpus entitlement versus disk ----------------------------------------


ENTITLEMENT_RE = re.compile(r"^\|\s*\*\*Entitlement[^|]*\|\s*\*\*(\d+)\*\*\s*\|", re.M)
ON_DISK_RE = re.compile(
    r"^\|\s*Fixture files present under `fixtures/AST\d{2}/`\s*\|\s*\*\*(\d+)\*\*\s*\|",
    re.M,
)


@pytest.mark.parametrize("category", CATEGORIES)
def test_stated_entitlement_matches_the_manifest(manifest, category):
    match = ENTITLEMENT_RE.search(matrix_text(category))
    assert match, f"{category}: matrix states no bolded entitlement figure"
    declared = manifest["categories"][category]["registry_coverage"]["declared_expected_cases"]
    assert int(match.group(1)) == declared, (
        f"{category}: matrix claims entitlement {match.group(1)}, manifest declares {declared}"
    )


@pytest.mark.parametrize("category", CATEGORIES)
def test_stated_on_disk_fixture_count_is_the_real_one(category):
    match = ON_DISK_RE.search(matrix_text(category))
    assert match, f"{category}: matrix states no on-disk fixture count"
    assert int(match.group(1)) == fixture_file_count(category), (
        f"{category}: matrix claims {match.group(1)} fixture files, "
        f"fixtures/{category}/ holds {fixture_file_count(category)}"
    )


def test_ast07_ships_no_orphan_fixture_corpus(manifest):
    """Zero cases labeled and zero files on disk, and the matrix says why.

    AST07 used to ship six labeled vulnerable/clean files that the manifest
    declared as zero cases. Three encoded the artifact_signals the registry
    declares for AST07-S01 and AST07-S02, and the other three proxied nothing
    named at all. A category with a zero-case entitlement does not get to keep
    a labeled corpus on disk, so they were deleted; the matrix has to record
    the deletion and the reason rather than let the files quietly vanish.
    """
    assert manifest["categories"]["AST07"]["cases"] == []
    assert fixture_file_count("AST07") == 0
    assert not (REPO_ROOT / "fixtures" / "AST07").exists(), (
        "fixtures/AST07/ must be gone, not emptied — an empty scaffold reads as a corpus in progress"
    )
    text = matrix_text("AST07")
    assert "the six files that used to sit on disk are deleted" in text.lower()
    assert "Why deletion rather than re-labeling." in text


#: The six pre-reconciliation AST02 fixture directories that the manifest declared as
#: zero cases. They proxied an AST01 agent-judgable scenario, AST02-S02's pin-posture
#: artifact_signal, and no named scenario at all. Deleted, and named here so the
#: regression pin survives AST02 later acquiring a real, declared corpus.
_DELISTED_AST02_FIXTURE_DIRS = (
    "V1-typosquatted-dependency",
    "C2-typosquatted-dependency",
    "V3-unpinned-wildcard-dependency",
    "C4-unpinned-wildcard-dependency",
    "V5-lockfile-hash-mismatch",
    "C6-lockfile-hash-mismatch",
)


def test_ast02_ships_no_orphan_fixture_corpus(manifest):
    """The same resolution for the other orphaned corpus (AST02's six files).

    The invariant is "no fixture on disk that the manifest does not declare",
    not "AST02 has no fixtures". AST02 now labels its one static-detectable
    scenario (AST02-S03 Config-File Hijacking) and ships the six cases the
    gate-4 formula entitles it to, every one of them declared. What must stay
    gone is the delisted pre-reconciliation corpus, which is named explicitly
    below so re-adding it cannot hide inside a legitimate corpus.
    """
    entry = manifest["categories"]["AST02"]
    declared = {(REPO_ROOT / case["path"]).parent.name for case in entry["cases"]}
    root = REPO_ROOT / "fixtures" / "AST02"
    on_disk = {p.name for p in root.iterdir() if p.is_dir()} if root.is_dir() else set()
    assert on_disk == declared, (
        f"AST02 fixture directories on disk {sorted(on_disk)} do not match the declared "
        f"cases {sorted(declared)}; an undeclared corpus must be deleted or declared"
    )
    assert on_disk.isdisjoint(_DELISTED_AST02_FIXTURE_DIRS), (
        "a delisted pre-reconciliation AST02 fixture directory is back on disk"
    )


# --- the matrix must not smuggle what it documents -------------------------


@pytest.mark.parametrize("category", CATEGORIES)
def test_matrix_carries_no_invisible_unicode(category):
    text = matrix_text(category)
    hits = sorted({f"U+{ord(c):04X}" for c in INVISIBLE_UNICODE_RE.findall(text)})
    assert not hits, (
        f"{matrix_path(category)} contains invisible Unicode {hits}; quote such code "
        f"points as \\uXXXX escapes, never as literal glyphs"
    )


# --- the executable claims each matrix makes about the engine --------------


def test_ast07_matrix_claim_engine_refuses_an_out_of_artifact_fixture():
    """AST07's matrix says the engine raises rather than scoring these. Prove it."""
    from detectors.engine import (
        CoverageEntry,
        FixtureCase,
        OutOfArtifactFixtureError,
        Tier,
        run_category,
    )

    coverage = [CoverageEntry(f"AST07-S{n:02d}", "AST07", Tier.OUT_OF_ARTIFACT, "temporal") for n in (1, 2, 3)]
    fixture = FixtureCase("AST07-V1", "AST07-S01", "AST07", True, None)
    with pytest.raises(OutOfArtifactFixtureError):
        run_category("AST07", coverage, [fixture], lambda sample: False)

    empty = run_category("AST07", coverage, [], lambda sample: False)
    assert empty.f1 is None
    assert empty.declared_uncovered == ("AST07-S01", "AST07-S02", "AST07-S03")


def test_ast08_matrix_claim_engine_refuses_the_local_fixture_id(registry):
    """The corpus is labeled `AST08-S1`, which is not a registry id — engine must shout."""
    from detectors.engine import (
        CoverageEntry,
        FixtureCase,
        Tier,
        UnregisteredScenarioFixtureError,
        run_category,
    )

    tiers = {
        "static-detectable": Tier.STATIC_DETECTABLE,
        "agent-judgable": Tier.AGENT_JUDGABLE,
        "out-of-artifact": Tier.OUT_OF_ARTIFACT,
    }
    coverage = [
        CoverageEntry(s["id"], "AST08", tiers[s["tier"]], s["reason"]) for s in registry_scenarios(registry, "AST08")
    ]
    fixture = FixtureCase("AST08-V1", "AST08-S1", "AST08", True, None)
    with pytest.raises(UnregisteredScenarioFixtureError):
        run_category("AST08", coverage, [fixture], lambda sample: False)


def test_a_corpus_labeled_with_ids_the_detector_does_not_know_manufactures_a_hollow_zero():
    """The 0.0 the matrix warns about: `measured` status over an empty intersection.

    This was AST08's real state while its corpus was labeled `AST08-S1` and its
    detector answered to a different id. The corpus has been re-keyed to registry
    ids since, so the pairing below is synthetic -- but the routing rule it proves
    is the one that stopped that 0.0 being published, and it has to keep holding
    for the next category that gets there.
    """
    detector = load_detector("AST08")
    corpus = [({"manifest": {"description": ""}, "files": {}}, {"AST08-S1"})] * 3
    corpus += [({"manifest": {"description": ""}, "files": {}}, set())] * 3
    report = detector.f1_report(corpus)
    assert report["status"] == "measured"
    assert report["f1"] == 0.0
    # Every counter is zero because the labels and the detector's scenario set
    # intersect to nothing -- so the 0.0 measures an empty intersection, not poor
    # detection. The matrix must carry the rule that forbids publishing it.
    assert (report["tp"], report["fp"], report["fn"]) == (0, 0, 0)
    assert "must name the scenario it measures" in matrix_text("AST08")


# --- corpus facts the matrices assert in prose -----------------------------


def test_ast07_ships_no_detector_function_at_all():
    detector = load_detector("AST07")
    assert detector.DETECTORS == {}
    assert detector.STATIC_DETECTABLE == set()
    assert "`DETECTORS = {}` — zero detector functions" in matrix_text("AST07")


def test_ast08_full_coverage_entitlement_of_eight_is_the_manifest_figure(manifest):
    coverage = manifest["categories"]["AST08"]["registry_coverage"]
    assert coverage["cases_at_full_static_coverage"] == 8
    assert "| Entitlement at full registry coverage | 8 |" in matrix_text("AST08")


def test_ast08_corpus_is_one_distinct_pair_per_static_detectable_scenario(registry, manifest):
    """The replacement for a test that pinned a defect.

    It used to assert that AST08 shipped three byte-identical vulnerable files and
    three byte-identical clean ones -- six cases over a single frontmatter field
    that no detector read, carrying roughly one case of information and labeled
    against a local id (`AST08-S1`) that is not a whitepaper scenario at all. That
    corpus was replaced, so the claim it pinned is gone; the assertion is inverted
    rather than dropped, and now holds the corpus to the shape the entitlement
    formula assumes: one vulnerable/clean pair per static-detectable scenario, every
    package distinct, every case labeled with a registry id.
    """
    base = REPO_ROOT / "fixtures" / "AST08"
    static_ids = sorted(s["id"] for s in registry_scenarios(registry, "AST08") if s["tier"] == "static-detectable")
    cases = manifest["categories"]["AST08"]["cases"]

    by_scenario: dict[str, set[str]] = {}
    for case in cases:
        by_scenario.setdefault(case["scenario_id"], set()).add(case["label"])
    assert sorted(by_scenario) == static_ids, "every static-detectable scenario needs its own labeled pair"
    assert all(labels == {"vulnerable", "clean"} for labels in by_scenario.values())

    packages = sorted(p for p in base.iterdir() if p.is_dir())
    assert len(packages) == len(cases) == 2 * len(static_ids)
    digests = {
        package.name: sorted(
            (path.relative_to(package).as_posix(), path.read_bytes())
            for path in package.rglob("*")
            if path.is_file() and not path.is_symlink()
        )
        for package in packages
    }
    assert len({repr(files) for files in digests.values()}) == len(packages), (
        "two fixture packages are byte-identical; duplicates add count, not information"
    )
