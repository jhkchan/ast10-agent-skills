"""T-3.1b — the AST01-AST03 coverage matrices, audited against their own sources.

`skills/<ID>/coverage-matrix.md` is the artifact `docs/adr/0004` makes the defence of the
narrowed F1 denominator, and the one deliverable in this repository that no downstream
automation can repair. These tests hold it to the sources it claims to summarise, so a
matrix cannot drift into a comfortable summary of a tiering that is no longer in force:

  * The scenario table exhausts the category. Every scenario `scenarios/registry.yaml`
    names appears exactly once, with the registry's tier and the whitepaper's verbatim
    title. A dropped row, an invented row, or a silently re-tiered row fails.
  * The "Declared and uncovered" section lists exactly the out-of-artifact scenarios —
    not a subset, not a superset — and states, for each, evidence that would decide it.
    S-003's requirement is that the tier is *published*, not merely excluded.
  * The corpus-entitlement figures are recomputed, not transcribed: the gate-4 formula
    `max(6, 2 x detectable)` against the registry, the labeled-check count from
    `fixtures/manifest.yaml`, and the actual file count from disk.
  * A category whose labeled detectable tier is empty says in writing that it publishes
    no F1 (gate-4, S-003) rather than leaving a reader to infer it.
  * Each matrix records a tier-lock hash over the registry tiering it was authored
    against (S-011), so a reclassification invalidates the matrix as loudly as it
    invalidates the fixture labels.

Scope: the three categories T-3.1b owns. Sibling tasks author AST04-AST10; extend
``AUTHORED_CATEGORIES`` as those land rather than globbing, so an unwritten matrix reads
as "not yet authored" instead of failing this module.
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

from validators.tier_lock import tier_lock_hash

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "scenarios" / "registry.yaml"
MANIFEST_PATH = REPO_ROOT / "fixtures" / "manifest.yaml"

AUTHORED_CATEGORIES = ["AST01", "AST02", "AST03"]

MIN_FLOOR = 6  # gate-4, locked
VALID_TIERS = {"static-detectable", "agent-judgable", "out-of-artifact"}

SCENARIO_ID_RE = re.compile(r"^AST\d{2}-S\d{2}$")
# Split on unescaped pipes only: a table cell may legitimately contain `curl\|bash`.
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")


# --------------------------------------------------------------------------- sources


@pytest.fixture(scope="module")
def registry() -> dict:
    with REGISTRY_PATH.open() as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="module")
def manifest() -> dict:
    with MANIFEST_PATH.open() as fh:
        return yaml.safe_load(fh)


def _registry_scenarios(registry: dict, category: str) -> list[dict]:
    return [s for s in registry["scenarios"] if s["category"] == category]


def _matrix_path(category: str) -> pathlib.Path:
    return REPO_ROOT / "skills" / category / "coverage-matrix.md"


def _matrix_text(category: str) -> str:
    path = _matrix_path(category)
    assert path.is_file(), f"{path} does not exist"
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- parsing


def _section(text: str, heading_prefix: str) -> str:
    """The body of the first `## ` section whose heading starts with the prefix."""
    lines = text.split("\n")
    start = None
    for i, line in enumerate(lines):
        if line.startswith("## ") and line[3:].startswith(heading_prefix):
            start = i + 1
            break
    assert start is not None, f"no '## {heading_prefix}...' section found"
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end])


def _clean(cell: str) -> str:
    return cell.replace("\\|", "|").strip().strip("*").strip("`").strip()


def _table_rows(section: str) -> list[list[str]]:
    """Data rows of the first markdown pipe table in a section, header/rule dropped."""
    rows: list[list[str]] = []
    for line in section.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("|"):
            if rows:
                break  # table ended
            continue
        cells = [_clean(c) for c in CELL_SPLIT_RE.split(stripped)[1:-1]]
        if all(set(c) <= {"-", ":"} and c for c in cells):
            continue  # the |---|---| separator rule
        rows.append(cells)
    assert rows, "no markdown table rows found in section"
    return rows[1:]  # drop the header row


def _scenario_rows(category: str) -> list[list[str]]:
    return _table_rows(_section(_matrix_text(category), "Scenario tiering"))


def _quantity(category: str, key_fragment: str) -> int:
    """An integer from the Corpus-entitlement table, keyed by a fragment of column 1."""
    rows = _table_rows(_section(_matrix_text(category), "Corpus entitlement"))
    matches = [r for r in rows if key_fragment.lower() in r[0].lower()]
    assert len(matches) == 1, (
        f"{category}: expected exactly one corpus-entitlement row matching {key_fragment!r}, found {len(matches)}"
    )
    return int(_clean(matches[0][1]))


# ------------------------------------------------------------------- existence / shape


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_matrix_exists_for_every_authored_category(category):
    assert _matrix_path(category).is_file()


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_matrix_carries_the_non_endorsement_disclaimer(category):
    """The repo name says OWASP; NOTICE says it is not an OWASP project. Every
    reader-facing artifact has to say so too, not only NOTICE."""
    text = re.sub(r"\s+", " ", _matrix_text(category).lower())
    assert "**not** an official owasp project" in text
    assert "no owasp endorsement" in text


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_matrix_is_referenced_by_its_skill_md(category):
    """Each SKILL.md defers its tiering to this file; the promise must resolve."""
    skill_md = (REPO_ROOT / "skills" / category / "SKILL.md").read_text(encoding="utf-8")
    assert "coverage-matrix.md" in skill_md
    assert _matrix_path(category).is_file()


# ------------------------------------------------------------------- the tiering table


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_scenario_table_exhausts_the_registry(category, registry):
    expected = {s["id"] for s in _registry_scenarios(registry, category)}
    listed = [r[0] for r in _scenario_rows(category)]
    assert all(SCENARIO_ID_RE.match(i) for i in listed), listed
    assert len(listed) == len(set(listed)), f"{category}: duplicate scenario row"
    assert set(listed) == expected, f"{category}: matrix rows {sorted(set(listed))} != registry {sorted(expected)}"


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_scenario_rows_carry_the_registry_tier(category, registry):
    tiers = {s["id"]: s["tier"] for s in _registry_scenarios(registry, category)}
    for row in _scenario_rows(category):
        scenario_id, tier = row[0], row[2]
        assert tier in VALID_TIERS, f"{scenario_id}: unknown tier {tier!r}"
        assert tier == tiers[scenario_id], f"{scenario_id}: matrix says {tier!r}, registry says {tiers[scenario_id]!r}"


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_scenario_rows_carry_the_verbatim_whitepaper_title(category, registry):
    titles = {s["id"]: s["title"] for s in _registry_scenarios(registry, category)}
    for row in _scenario_rows(category):
        assert row[1] == titles[row[0]], f"{row[0]}: matrix title {row[1]!r} != whitepaper title {titles[row[0]]!r}"


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_every_scenario_row_states_a_written_reason(category):
    """The tier is worthless to a reviewer without the reason for it (ADR-0004)."""
    for row in _scenario_rows(category):
        assert len(row) == 5, f"{row[0]}: expected 5 columns, got {len(row)}"
        assert len(row[4]) >= 80, f"{row[0]}: tier reason is too thin to audit"


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_non_detectable_rows_claim_no_detector_coverage(category, registry):
    """A row the registry does not tier static-detectable must not advertise a
    detector check in column 4 as though the scenario were decided."""
    tiers = {s["id"]: s["tier"] for s in _registry_scenarios(registry, category)}
    for row in _scenario_rows(category):
        if tiers[row[0]] == "static-detectable":
            continue
        checks = row[3]
        assert checks.startswith("—"), f"{row[0]} is {tiers[row[0]]} but its detector column claims {checks!r}"


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_tally_line_matches_the_registry_counts(category, registry):
    scenarios = _registry_scenarios(registry, category)
    counts = {t: sum(1 for s in scenarios if s["tier"] == t) for t in VALID_TIERS}
    text = _matrix_text(category)
    match = re.search(
        r"Tally:\s*\*\*(\d+) static-detectable, (\d+) agent-judgable, "
        r"(\d+) out-of-artifact\*\*",
        text,
    )
    assert match, f"{category}: no machine-checkable Tally line"
    assert [int(g) for g in match.groups()] == [
        counts["static-detectable"],
        counts["agent-judgable"],
        counts["out-of-artifact"],
    ]


# ------------------------------------------------------------- declared and uncovered


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_declared_and_uncovered_lists_exactly_the_out_of_artifact_tier(category, registry):
    expected = {s["id"] for s in _registry_scenarios(registry, category) if s["tier"] == "out-of-artifact"}
    rows = _table_rows(_section(_matrix_text(category), "Declared and uncovered"))
    listed = {r[0] for r in rows}
    assert listed == expected, (
        f"{category}: declared-and-uncovered lists {sorted(listed)}, "
        f"registry out-of-artifact tier is {sorted(expected)}"
    )


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_each_uncovered_scenario_names_the_evidence_that_would_decide_it(category):
    """S-003 publishes the tier; a reviewer still has to be told what would close it."""
    rows = _table_rows(_section(_matrix_text(category), "Declared and uncovered"))
    for row in rows:
        assert len(row) == 4, f"{row[0]}: expected 4 columns, got {len(row)}"
        assert len(row[2]) >= 120, f"{row[0]}: 'why one package cannot decide it' is thin"
        assert len(row[3]) >= 120, f"{row[0]}: 'evidence that would decide it' is thin"


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_no_out_of_artifact_scenario_is_claimed_as_detector_coverage(category, registry):
    out_of_artifact = {s["id"] for s in _registry_scenarios(registry, category) if s["tier"] == "out-of-artifact"}
    for row in _scenario_rows(category):
        if row[0] in out_of_artifact:
            assert row[3] == "—", f"{row[0]}: out-of-artifact rows carry no detector"


# ------------------------------------------------------------------- F1 denominator


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_matrix_states_an_f1_denominator(category):
    section = _section(_matrix_text(category), f"F1 denominator for {category}")
    assert "declared-detectable tier" in section
    assert "static-detectable" in section
    assert "out-of-artifact" in section


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_empty_labeled_detectable_tier_says_it_publishes_no_f1(category, manifest):
    """gate-4 / S-003: never padded, and never left for the reader to infer."""
    cat = manifest["categories"][category]
    section = _section(_matrix_text(category), f"F1 denominator for {category}")
    if cat["detectable_scenarios"]:
        return
    assert cat["cases"] == [] and cat["published_f1"] is None  # manifest agrees
    assert "publishes no F1" in section
    assert "declared-and-uncovered" in section
    assert "honesty choice" in _matrix_text(category).lower() or ("deliberate" in section)


# --------------------------------------------------------------- corpus accounting


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_registry_static_detectable_count_is_transcribed_correctly(category, registry):
    actual = sum(1 for s in _registry_scenarios(registry, category) if s["tier"] == "static-detectable")
    assert _quantity(category, "Registry static-detectable scenarios") == actual


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_entitlement_at_full_registry_coverage_follows_the_locked_formula(category, registry):
    detectable = sum(1 for s in _registry_scenarios(registry, category) if s["tier"] == "static-detectable")
    assert _quantity(category, "Entitlement at full registry coverage") == max(MIN_FLOOR, 2 * detectable)


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_labeled_check_count_matches_the_fixture_manifest(category, manifest):
    assert _quantity(category, "Labeled detectable checks") == len(
        manifest["categories"][category]["detectable_scenarios"]
    )


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_entitlement_at_present_labeling_follows_the_locked_formula(category, manifest):
    """`max(6, 2 x n)` when the category labels anything; 0 when it labels nothing —
    the never-pad rule means an empty detectable tier is not owed the floor."""
    labeled = len(manifest["categories"][category]["detectable_scenarios"])
    expected = max(MIN_FLOOR, 2 * labeled) if labeled else 0
    assert _quantity(category, "Entitlement at present labeling") == expected


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_actual_fixture_count_matches_what_is_on_disk(category):
    on_disk = sorted(p for p in (REPO_ROOT / "fixtures" / category).iterdir() if p.is_dir())
    assert _quantity(category, "Actual fixture count") == len(on_disk)


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_matrix_records_a_disk_versus_manifest_discrepancy_when_one_exists(category, manifest):
    """AST02 ships six delisted fixture directories the manifest declares as zero
    cases. A matrix that quietly reported one number or the other would hide the
    orphaned corpus; it has to show both and say so."""
    on_disk = len([p for p in (REPO_ROOT / "fixtures" / category).iterdir() if p.is_dir()])
    declared = len(manifest["categories"][category]["cases"])
    if on_disk == declared:
        return
    text = _matrix_text(category)
    assert "orphan" in text.lower()
    assert _quantity(category, "Declared cases") == declared


# ------------------------------------------------------------------------ tier lock


@pytest.mark.parametrize("category", AUTHORED_CATEGORIES)
def test_recorded_tier_lock_recomputes_from_the_registry(category, registry):
    """S-011 for the matrix itself: reclassify a scenario and this hash stops
    matching, which is the signal to re-label the corpus and re-run the judges."""
    text = _matrix_text(category)
    match = re.search(r"registry_tier_lock:\s*([0-9a-f]{64})", text)
    assert match, f"{category}: matrix records no registry_tier_lock hash"
    assert match.group(1) == tier_lock_hash(_registry_scenarios(registry, category))


def test_each_category_locks_a_distinct_tiering():
    """A copy-pasted hash across matrices would defeat the tripwire silently."""
    hashes = {
        c: re.search(r"registry_tier_lock:\s*([0-9a-f]{64})", _matrix_text(c)).group(1) for c in AUTHORED_CATEGORIES
    }
    assert len(set(hashes.values())) == len(hashes), hashes
