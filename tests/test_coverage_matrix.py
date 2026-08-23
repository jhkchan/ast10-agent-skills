"""T-3.1b — the authored per-category coverage matrices are audit artifacts, so they are
tested like one.

`skills/<ID>/coverage-matrix.md` is the file each `SKILL.md` points at when it says the
scenario tiering "is fixed in `coverage-matrix.md`". It is prose, but every claim in it
is checkable, and an audit artifact that drifts from the thing it audits is worse than
none at all. These tests hold the matrices to four sources at once:

  * `scenarios/registry.yaml` — authoritative on tier. The matrix must enumerate exactly
    the category's scenarios, with the whitepaper's verbatim titles and the registry's
    tiers. No scenario may be dropped, renamed, re-tiered, or invented.
  * `fixtures/manifest.yaml` — authoritative on the corpus. The matrix's corpus-size
    claim and every fixture path it lists must be the real ones, and its `tier_lock_hash`
    must be the hash the corpus was labeled against (S-011).
  * `skills/<ID>/scripts/detector.py` — the matrix's "what the detector actually checks"
    column is a claim about running code. Every scenario id the module declares must be
    accounted for in the matrix, so a new check cannot be added without saying whether it
    covers a named scenario or is a category precondition.
  * The detectors' observed behaviour. Several cells record gaps found by running the
    detectors (dead checks against `schemas/usf-v1.schema.json`, a crash on a conformant
    manifest, a corpus not wired to any loader). Those are pinned below: when a gap is
    fixed, the pin fails and forces the matrix to be corrected in the same change.

Scope: the three categories authored by T-3.1b. Other categories' matrices are covered by
their own authoring task; this module deliberately does not assert on files it did not
write, so a sibling task's in-progress file cannot redden this suite.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "scenarios" / "registry.yaml"
MANIFEST_PATH = REPO_ROOT / "fixtures" / "manifest.yaml"

# Authored by T-3.1b. See the module docstring on why this is not all ten.
AUTHORED = ["AST04", "AST05", "AST06"]

VALID_TIERS = {"static-detectable", "agent-judgable", "out-of-artifact"}
NO_CHECK = "`—`"  # the matrix legend's marker for "no deterministic check is possible"

_ROW_RE = re.compile(r"^\|\s*`(AST\d{2}-S\d{2})`\s*\|")
_SUBHEAD_RE = re.compile(r"^###\s+`(AST\d{2}-S\d{2})`")


# --- loading ---------------------------------------------------------------


@pytest.fixture(scope="module")
def registry() -> dict:
    return yaml.safe_load(REGISTRY_PATH.read_text())


@pytest.fixture(scope="module")
def by_id(registry) -> dict[str, dict]:
    return {s["id"]: s for s in registry["scenarios"]}


@pytest.fixture(scope="module")
def manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text())


def matrix_path(category: str) -> pathlib.Path:
    return REPO_ROOT / "skills" / category / "coverage-matrix.md"


def _split_frontmatter(text: str) -> tuple[dict, str]:
    assert text.startswith("---\n"), "coverage-matrix.md must open with YAML frontmatter"
    end = text.find("\n---\n", 4)
    assert end != -1, "coverage-matrix.md frontmatter is not closed"
    fm = yaml.safe_load(text[4:end])
    assert isinstance(fm, dict)
    return fm, text[end + len("\n---\n") :]


@pytest.fixture(scope="module")
def matrices() -> dict[str, tuple[dict, str]]:
    out = {}
    for category in AUTHORED:
        path = matrix_path(category)
        assert path.is_file(), f"{path} does not exist"
        out[category] = _split_frontmatter(path.read_text(encoding="utf-8"))
    return out


def _rows(body: str) -> dict[str, list[str]]:
    """Scenario-table rows keyed by scenario id, as stripped cell lists."""
    rows: dict[str, list[str]] = {}
    for line in body.splitlines():
        match = _ROW_RE.match(line)
        if not match:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        assert match.group(1) not in rows, f"duplicate table row for {match.group(1)}"
        rows[match.group(1)] = cells
    return rows


def _section(body: str, heading: str) -> str:
    """The text under a `## heading`, up to the next `## `."""
    start = body.find(f"\n## {heading}")
    assert start != -1, f"missing section '## {heading}'"
    rest = body[start + 1 :]
    nxt = rest.find("\n## ", 1)
    return rest if nxt == -1 else rest[:nxt]


def _category_scenarios(by_id: dict, category: str) -> dict[str, dict]:
    return {i: s for i, s in by_id.items() if s["category"] == category}


def _load_detector(category: str):
    spec = importlib.util.spec_from_file_location(
        f"_covmatrix_det_{category}",
        REPO_ROOT / "skills" / category / "scripts" / "detector.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- the file exists and says what it is -----------------------------------


@pytest.mark.parametrize("category", AUTHORED)
def test_skill_md_promise_is_kept(category, matrices):
    """SKILL.md points at coverage-matrix.md; the file must exist and name the category."""
    skill_md = (REPO_ROOT / "skills" / category / "SKILL.md").read_text(encoding="utf-8")
    assert "coverage-matrix.md" in skill_md, f"{category}/SKILL.md no longer references coverage-matrix.md"
    fm, body = matrices[category]
    assert fm["artifact"] == "coverage-matrix"
    assert fm["category"] == category
    assert body.lstrip().startswith(f"# {category} — ")


@pytest.mark.parametrize("category", AUTHORED)
def test_frontmatter_tier_counts_match_the_registry(category, matrices, by_id):
    fm, _ = matrices[category]
    scenarios = _category_scenarios(by_id, category)
    counts = {tier: sum(1 for s in scenarios.values() if s["tier"] == tier) for tier in VALID_TIERS}
    assert fm["registry_scenarios"] == len(scenarios)
    assert fm["static_detectable"] == counts["static-detectable"]
    assert fm["agent_judgable"] == counts["agent-judgable"]
    assert fm["out_of_artifact"] == counts["out-of-artifact"]


@pytest.mark.parametrize("category", AUTHORED)
def test_frontmatter_tier_lock_hash_is_the_corpus_lock(category, matrices, manifest):
    """S-011: the matrix is bound to the tiering the fixtures were labeled against."""
    fm, _ = matrices[category]
    assert fm["tier_lock_hash"] == manifest["categories"][category]["tier_lock_hash"]


# --- the scenario table exhausts the registry ------------------------------


@pytest.mark.parametrize("category", AUTHORED)
def test_table_enumerates_exactly_the_registry_scenarios(category, matrices, by_id):
    _, body = matrices[category]
    rows = _rows(_section(body, "Scenario table"))
    expected = set(_category_scenarios(by_id, category))
    assert set(rows) == expected, (
        f"{category} table scenario set differs from the registry: "
        f"missing={sorted(expected - set(rows))} extra={sorted(set(rows) - expected)}"
    )


@pytest.mark.parametrize("category", AUTHORED)
def test_every_row_carries_the_verbatim_whitepaper_title(category, matrices, by_id):
    _, body = matrices[category]
    for scenario_id, cells in _rows(_section(body, "Scenario table")).items():
        assert cells[1] == by_id[scenario_id]["title"], (
            f"{scenario_id} title {cells[1]!r} != whitepaper title {by_id[scenario_id]['title']!r}"
        )


@pytest.mark.parametrize("category", AUTHORED)
def test_every_row_carries_the_registry_tier(category, matrices, by_id):
    _, body = matrices[category]
    for scenario_id, cells in _rows(_section(body, "Scenario table")).items():
        assert cells[2] == by_id[scenario_id]["tier"], (
            f"{scenario_id} tier {cells[2]!r} != registry tier {by_id[scenario_id]['tier']!r} — the registry wins"
        )


@pytest.mark.parametrize("category", AUTHORED)
def test_every_row_states_a_detector_answer_and_a_written_reason(category, matrices):
    _, body = matrices[category]
    for scenario_id, cells in _rows(_section(body, "Scenario table")).items():
        assert len(cells) == 5, f"{scenario_id} row does not have 5 columns: {cells}"
        assert cells[3].strip(), f"{scenario_id} has an empty detector column"
        assert len(cells[4].strip()) >= 40, f"{scenario_id} reason is too thin to audit: {cells[4]!r}"


@pytest.mark.parametrize("category", AUTHORED)
def test_undecidable_rows_claim_no_check_and_decidable_rows_do_not_hide_behind_one(category, matrices, by_id):
    """The legend's core invariant.

    A scenario the package cannot decide must show the `—` marker, never a check. A
    scenario the registry tiers static-detectable must never show `—`: if no check
    exists, that is coverage debt and must be written as such, not disguised as
    undetectability.
    """
    _, body = matrices[category]
    for scenario_id, cells in _rows(_section(body, "Scenario table")).items():
        tier = by_id[scenario_id]["tier"]
        if tier == "static-detectable":
            assert cells[3] != NO_CHECK, f"{scenario_id} is static-detectable but the matrix marks it undecidable"
        else:
            assert cells[3] == NO_CHECK, (
                f"{scenario_id} is {tier} but the matrix claims a deterministic check: {cells[3]!r}"
            )


# --- declared and uncovered ------------------------------------------------


@pytest.mark.parametrize("category", AUTHORED)
def test_declared_and_uncovered_lists_every_out_of_artifact_scenario(category, matrices, by_id):
    _, body = matrices[category]
    section = _section(body, "Declared and uncovered")
    documented = {m.group(1) for m in (_SUBHEAD_RE.match(ln) for ln in section.splitlines()) if m}
    expected = {i for i, s in _category_scenarios(by_id, category).items() if s["tier"] == "out-of-artifact"}
    assert documented == expected, (
        f"{category} declared-and-uncovered set differs from the registry's "
        f"out-of-artifact tier: missing={sorted(expected - documented)} "
        f"extra={sorted(documented - expected)}"
    )


@pytest.mark.parametrize("category", AUTHORED)
def test_each_uncovered_scenario_states_the_evidence_that_would_decide_it(category, matrices, by_id):
    """An uncovered row is only auditable if it says what would close it."""
    _, body = matrices[category]
    section = _section(body, "Declared and uncovered")
    blocks = re.split(r"^###\s+", section, flags=re.MULTILINE)
    seen = 0
    for block in blocks:
        match = re.match(r"`(AST\d{2}-S\d{2})`", block)
        if not match:
            continue
        seen += 1
        assert "Why one package cannot decide it" in block, (
            f"{match.group(1)} does not say why it is undecidable from one package"
        )
        assert "Evidence that would decide it" in block, (
            f"{match.group(1)} does not name the evidence that would decide it"
        )
    assert seen == sum(1 for s in _category_scenarios(by_id, category).values() if s["tier"] == "out-of-artifact")


@pytest.mark.parametrize("category", AUTHORED)
def test_scenarios_with_an_artifact_signal_name_it_as_a_proxy(category, matrices, by_id):
    """A partial proxy must be visible as one, never quietly upgraded to coverage."""
    _, body = matrices[category]
    section = _section(body, "Declared and uncovered")
    blocks = {
        m.group(1): block
        for block in re.split(r"^###\s+", section, flags=re.MULTILINE)
        if (m := re.match(r"`(AST\d{2}-S\d{2})`", block))
    }
    for scenario_id, scenario in _category_scenarios(by_id, category).items():
        if scenario["tier"] != "out-of-artifact":
            continue
        block = blocks[scenario_id]
        if str(scenario.get("artifact_signal") or "").strip():
            assert "Enabling precondition the package shows" in block, (
                f"{scenario_id} declares an artifact_signal the matrix does not record"
            )
        else:
            assert "Enabling precondition the package shows" not in block, (
                f"{scenario_id} declares no artifact_signal, so the matrix must not claim one"
            )


# --- the F1 denominator statement ------------------------------------------


@pytest.mark.parametrize("category", AUTHORED)
def test_f1_statement_matches_whether_the_detectable_tier_is_empty(category, matrices, by_id):
    """gate-4 / S-003: an empty detectable tier publishes no F1 and says so."""
    _, body = matrices[category]
    section = _section(body, "F1 denominator statement")
    static = [i for i, s in _category_scenarios(by_id, category).items() if s["tier"] == "static-detectable"]
    if static:
        assert "does publish an F1" in section, (
            f"{category} has a non-empty detectable tier but the matrix does not say it publishes an F1"
        )
        for scenario_id in static:
            assert scenario_id in section, f"{category}'s F1 denominator statement omits {scenario_id}"
    else:
        assert "publishes no F1" in section, (
            f"{category}'s detectable tier is empty; the matrix must state that it publishes no F1"
        )
        assert "honesty choice" in section, (
            f"{category} must state that publishing no F1 is deliberate, not an omission"
        )


@pytest.mark.parametrize("category", AUTHORED)
def test_agent_judgable_scenarios_are_excluded_from_the_denominator_in_writing(category, matrices, by_id):
    _, body = matrices[category]
    section = _section(body, "F1 denominator statement")
    for scenario_id, scenario in _category_scenarios(by_id, category).items():
        if scenario["tier"] != "agent-judgable":
            continue
        assert scenario_id in section, f"{category}'s F1 statement does not account for agent-judgable {scenario_id}"
    assert "judge" in section.lower() or not any(
        s["tier"] == "agent-judgable" for s in _category_scenarios(by_id, category).values()
    )


# --- corpus entitlement -----------------------------------------------------


@pytest.mark.parametrize("category", AUTHORED)
def test_corpus_entitlement_formula_and_result_are_stated_correctly(category, matrices, by_id):
    """max(6, 2 * detectable), computed off the registry's static tier."""
    _, body = matrices[category]
    section = _section(body, "Corpus entitlement and actual count")
    static = sum(1 for s in _category_scenarios(by_id, category).values() if s["tier"] == "static-detectable")
    formula = f"max(6, 2 × {static})"
    assert formula in section, f"{category} does not state the entitlement {formula}"
    line = next(ln for ln in section.splitlines() if formula in ln)
    if static:
        assert f"**{max(6, 2 * static)}**" in line, (
            f"{category} states {formula} but not its value {max(6, 2 * static)}"
        )
    else:
        assert "none" in line.lower(), f"{category} has an empty detectable tier; the entitlement is not a number"


@pytest.mark.parametrize("category", AUTHORED)
def test_stated_fixture_count_is_the_real_one(category, matrices, manifest):
    _, body = matrices[category]
    section = _section(body, "Corpus entitlement and actual count")
    on_disk = sorted(p for p in (REPO_ROOT / "fixtures" / category).iterdir() if p.is_dir())
    cases = manifest["categories"][category]["cases"]
    assert len(on_disk) == len(cases), f"{category}: {len(on_disk)} fixture dirs on disk vs {len(cases)} manifest cases"
    assert f"actually present under `fixtures/{category}/` | **{len(cases)}**" in section, (
        f"{category} does not state its real fixture count of {len(cases)}"
    )


@pytest.mark.parametrize("category", AUTHORED)
def test_every_manifest_case_path_is_listed_in_the_matrix(category, matrices, manifest):
    """A reviewer must be able to walk from the matrix to the actual files."""
    _, body = matrices[category]
    for case in manifest["categories"][category]["cases"]:
        assert case["path"] in body, f"{category} matrix does not list fixture path {case['path']}"
        assert (REPO_ROOT / case["path"]).is_file()


# --- the detector column is a claim about running code ---------------------


@pytest.mark.parametrize("category", AUTHORED)
def test_every_declared_detector_scenario_id_is_accounted_for(category, matrices):
    """A check cannot be added to the module without the matrix saying what it covers."""
    _, body = matrices[category]
    module = _load_detector(category)
    for scenario_id in module.SCENARIO_TIERS:
        assert f"`{scenario_id}`" in body, (
            f"{category}/scripts/detector.py declares {scenario_id} but the coverage matrix does not account for it"
        )


@pytest.mark.parametrize("category", AUTHORED)
def test_implemented_detectors_are_a_subset_of_the_declared_ids(category):
    module = _load_detector(category)
    assert set(module.DETECTORS) <= set(module.SCENARIO_TIERS)
    assert module.STATIC_DETECTABLE == {s for s, t in module.SCENARIO_TIERS.items() if t == "static-detectable"}


# --- pinned gaps: the matrices record these, so a fix must update them -----
#
# Each test below asserts observed detector behaviour that a "Reconciliation debt"
# item in the corresponding coverage-matrix.md describes. When the defect is fixed,
# the test fails — which is the point: the audit artifact must be corrected in the
# same change, not left claiming a gap that no longer exists.


def _usf_conformant_permissions() -> dict:
    """A permissions block valid under schemas/usf-v1.schema.json.

    `shell` is a boolean and `network` carries only `allow`/`deny` — the schema sets
    `additionalProperties: false` on both.
    """
    return {
        "files": {"read": ["."], "write": [], "deny_write": []},
        "network": {"allow": ["example.com"], "deny": "*"},
        "shell": True,
    }


def test_ast05_network_checks_are_dead_against_a_conformant_usf_manifest():
    """Pinned: skills/AST05/coverage-matrix.md, Reconciliation debt item 2.

    Both AST05 checks gate on `permissions.network.policy`, which USF v1 does not
    define, so neither can fire on a conformant manifest.
    """
    module = _load_detector("AST05")
    pkg = {"manifest": {"permissions": _usf_conformant_permissions()}, "files": {}}
    findings = module.run_all(pkg)
    assert findings, "AST05 declares no runnable checks at all"
    assert not any(f.detected for f in findings), (
        "an AST05 check now fires on a USF-conformant manifest — update "
        "skills/AST05/coverage-matrix.md, which records both as dead"
    )


def test_ast06_shell_check_crashes_on_a_conformant_usf_manifest():
    """Pinned: skills/AST06/coverage-matrix.md, Reconciliation debt item 1.

    USF v1 declares `permissions.shell` a boolean; the detector calls `.get("allowed")`
    on it.
    """
    module = _load_detector("AST06")
    pkg = {"manifest": {"permissions": _usf_conformant_permissions()}, "files": {}}
    with pytest.raises(AttributeError):
        module.detect_unrestricted_shell_exec(pkg)


def test_ast04_toml_check_cannot_see_a_duplicate_table_override():
    """Pinned: skills/AST04/coverage-matrix.md, AST04-S07 row.

    `tomllib` raises on a redefined table, and the detector swallows the decode error,
    so the duplicate-`[permissions]` shape the fixture encodes is skipped, not flagged.
    """
    module = _load_detector("AST04")
    duplicate_table = "[permissions]\nwrite = false\n\n[permissions]\nwrite = true\n"
    pkg = {"manifest": {}, "files": {"config.toml": duplicate_table}}
    assert not module.detect_toml_injection(pkg).detected, (
        "the TOML check now sees duplicate-table overrides — update skills/AST04/coverage-matrix.md's AST04-S07 row"
    )


@pytest.mark.parametrize("category", AUTHORED)
def test_no_fixture_loader_wires_the_corpus_to_the_detectors(category, manifest):
    """Pinned: every matrix's "Publication status" paragraph and its
    `published_f1: pending-detector`.

    Read the fixture bytes straight into the `pkg` shape the detectors consume and the
    result carries no discriminative signal: for AST04 and AST05 nothing fires at all,
    and for AST06 `missing-sandbox-declaration` fires uniformly on vulnerable and clean
    alike because the constructed package has no manifest. That is a wiring gap, and
    `pending-detector` is the honest report until it closes.
    """
    assert manifest["categories"][category]["published_f1"] == "pending-detector"
    module = _load_detector(category)
    verdicts: dict[str, set[bool]] = {}
    for case in manifest["categories"][category]["cases"]:
        text = (REPO_ROOT / case["path"]).read_text(encoding="utf-8")
        pkg = {"manifest": {}, "files": {"SKILL.md": text}}
        for finding in module.run_all(pkg):
            verdicts.setdefault(finding.scenario, set()).add(finding.detected)
    assert verdicts, f"{category} has no runnable checks"
    for scenario, seen in verdicts.items():
        assert seen != {True, False}, (
            f"{scenario} now discriminates across the fixture corpus — the corpus is "
            f"wired; update {category}/coverage-matrix.md and publish a real F1"
        )
