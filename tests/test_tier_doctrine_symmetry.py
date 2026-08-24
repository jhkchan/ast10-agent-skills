"""The same predicate must get the same ruling in the registry and in the detectors.

An independent tier-doctrine review found one signal classified two ways depending
on which way it cut. Content-hash absence and missing-permission metadata were
``static-detectable`` inside the detector modules that claimed them as coverage, and
``artifact_signal``-only in the ``scenarios/registry.yaml`` entries where counting
them would have enlarged an F1 denominator: "When it lets you claim a detector, it's
static; when it would oblige you to build one, it's out-of-artifact."

The ruling, and what this module enforces:

  * Package-decidability and scenario coverage are two questions. Almost every
    ``artifact_signal`` in the registry IS decidable from the package alone -- that is
    what makes it a signal -- so each one now states ``artifact_signal_decidable``
    outright instead of hiding behind its scenario's tier.
  * A check that computes exactly such a signal is named in the scenario's
    ``artifact_signal_checks``, and MUST declare ``covers: artifact-signal-only`` in
    its module's ``CHECK_COVERAGE``. It may never be published as coverage of the
    scenario. That is the load-bearing test here: ``test_a_signal_the_registry_names_is
    _never_claimed_as_scenario_coverage``.
  * The converse holds too. A check claiming ``covers: full`` must link registry
    scenarios the registry independently tiers ``static-detectable``. A detector cannot
    grant itself a detectability the registry withholds.
  * And the number that comes out carries the label: ``f1_report`` returns the module's
    ``F1_SCOPE`` next to every F1, so a proxy F1 cannot be quoted as scenario coverage
    by a caller who dropped the qualifier.

The vocabulary is deliberately the one ``fixtures/manifest.yaml`` already uses for its
labeled corpora (``full`` / ``artifact-signal-only`` / ``category-precondition``), so
the corpus, the registry and the detectors are readable against each other rather than
each carrying a private dialect.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest
import yaml

from detectors.scaffold import VALID_CHECK_TIERS, VALID_COVERS, f1_scope, validate_check_coverage

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "scenarios" / "registry.yaml"

CATEGORIES = [f"AST{i:02d}" for i in range(1, 11)]
DECIDABILITY = {"package-decidable", "partly-package-decidable", "not-package-decidable"}


@pytest.fixture(scope="module")
def registry() -> dict:
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def by_id(registry) -> dict[str, dict]:
    return {s["id"]: s for s in registry["scenarios"]}


def _load_detector(category: str):
    path = REPO_ROOT / "skills" / category / "scripts" / "detector.py"
    spec = importlib.util.spec_from_file_location(f"symmetry_{category}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def modules() -> dict:
    return {category: _load_detector(category) for category in CATEGORIES}


def _all_checks(modules: dict):
    for category, module in modules.items():
        for check, entry in module.CHECK_COVERAGE.items():
            yield category, check, entry


# --- registry side: a signal must say whether the package can decide it ----


def test_every_artifact_signal_states_whether_it_is_package_decidable(registry):
    """The dodge this closes: reading `out-of-artifact` as `invisible in the package`.

    It never meant that. It means the package cannot decide the scenario's DEFINING
    condition. An artifact_signal that does not say which of the two it is leaves room
    for exactly the asymmetry the review found.
    """
    for scenario in registry["scenarios"]:
        if not scenario.get("artifact_signal"):
            assert "artifact_signal_decidable" not in scenario, (
                f"{scenario['id']} declares no artifact_signal but rules on its decidability"
            )
            continue
        decidable = scenario.get("artifact_signal_decidable")
        assert decidable in DECIDABILITY, (
            f"{scenario['id']} declares an artifact_signal but its "
            f"artifact_signal_decidable is {decidable!r}, not one of {sorted(DECIDABILITY)}"
        )
        assert isinstance(scenario.get("artifact_signal_checks"), list), (
            f"{scenario['id']} must declare artifact_signal_checks (possibly empty)"
        )


def test_most_artifact_signals_are_package_decidable_and_the_registry_admits_it(registry):
    """A sanity floor on the ruling itself, not a restatement of the data.

    If the registry ever drifted back to calling its signals undecidable wholesale,
    the double standard would be available again. The signals are preconditions the
    package shows; the overwhelming majority must be readable from it.
    """
    signals = [s for s in registry["scenarios"] if s.get("artifact_signal")]
    assert signals
    decidable = [s for s in signals if s["artifact_signal_decidable"] == "package-decidable"]
    assert len(decidable) >= len(signals) * 2 // 3, (
        "most artifact_signals should be package-decidable; if they are not, the tier "
        "is being used to avoid building detectors rather than to describe the evidence"
    )


def test_no_static_detectable_scenario_names_an_artifact_signal_check(registry):
    """A decided scenario has no proxy to name; a check on it would be `covers: full`."""
    for scenario in registry["scenarios"]:
        if scenario["tier"] == "static-detectable":
            assert not scenario.get("artifact_signal_checks"), scenario["id"]


# --- detector side: every mechanical check declares what it does NOT claim -


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_module_declares_check_coverage_and_an_f1_scope(modules, category):
    module = modules[category]
    assert isinstance(module.CHECK_COVERAGE, dict)
    assert module.F1_SCOPE == f1_scope(module.CHECK_COVERAGE)


@pytest.mark.parametrize("category", CATEGORIES)
def test_check_coverage_is_structurally_valid(modules, category):
    violations = validate_check_coverage(modules[category].CHECK_COVERAGE)
    assert violations == [], f"{category}: {violations}"


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_scored_check_declares_its_coverage(modules, category):
    """Nothing enters the F1 denominator without saying what it measures.

    `STATIC_DETECTABLE` is the denominator. Whatever reaches it must be named by
    a CHECK_COVERAGE entry -- as that entry's key, for a module whose checks are
    keyed by registry scenario id, or in its `registry_ids`, for a module whose
    checks carry their own slugs. Either way the denominator element has a
    written coverage claim beside it; reaching it with none is the unqualified
    claim-by-default the review objected to.
    """
    module = modules[category]
    declared = set(module.CHECK_COVERAGE)
    for entry in module.CHECK_COVERAGE.values():
        declared.update(entry.get("registry_ids") or [])
    undeclared = sorted(module.STATIC_DETECTABLE - declared)
    assert not undeclared, f"{category}: {undeclared} are in the F1 denominator but declare no CHECK_COVERAGE entry"


@pytest.mark.parametrize("category", CATEGORIES)
def test_check_coverage_only_describes_checks_the_module_declares(modules, category):
    """The two tables are two namespaces, and each has to stay inside its own.

    `SCENARIO_TIERS` is keyed by `scenarios/registry.yaml`'s canonical scenario
    ids; `CHECK_COVERAGE` is keyed by the module's own CHECK ids. This used to
    assert `CHECK_COVERAGE <= SCENARIO_TIERS`, which only held while the tier
    table was keyed by check slugs -- the very conflation that let a module
    report its check count as a scenario count. What survives the split is the
    load-bearing half: a module describes only its OWN checks, and every check
    it actually ships declares what it covers.
    """
    module = modules[category]
    foreign = sorted(c for c in module.CHECK_COVERAGE if not c.startswith(f"{category}-"))
    assert not foreign, f"{category}: CHECK_COVERAGE describes {foreign}, which are not this module's checks"
    undeclared = sorted(set(module.DETECTORS) - set(module.CHECK_COVERAGE))
    assert not undeclared, f"{category}: {undeclared} ship as checks but declare no CHECK_COVERAGE entry"
    for tier in module.SCENARIO_TIERS.values():
        assert tier in VALID_CHECK_TIERS


# --- the two directions of the symmetry ------------------------------------


def test_a_signal_the_registry_names_is_never_claimed_as_scenario_coverage(registry, modules):
    """THE finding, mechanised.

    If `scenarios/registry.yaml` says a predicate is some scenario's artifact_signal,
    the module that computes that predicate says `artifact-signal-only`. It cannot say
    `full`, and it cannot silently omit a ruling. Flip either file alone and this fails.
    """
    coverage_by_check = {check: (category, entry) for category, check, entry in _all_checks(modules)}
    named_any = False
    for scenario in registry["scenarios"]:
        for check in scenario.get("artifact_signal_checks") or []:
            named_any = True
            assert check in coverage_by_check, (
                f"{scenario['id']} names artifact_signal_check {check!r}, which no detector "
                f"module declares in CHECK_COVERAGE"
            )
            category, entry = coverage_by_check[check]
            assert entry["covers"] == "artifact-signal-only", (
                f"{check} (skills/{category}) computes {scenario['id']}'s artifact_signal but "
                f"claims covers: {entry['covers']!r} -- a signal the registry calls a proxy "
                f"cannot be a detector's coverage claim"
            )
            assert scenario["id"] in entry["registry_ids"], (
                f"{check} is named on {scenario['id']} but does not link it back"
            )
    assert named_any, "no artifact_signal_checks are wired at all; the symmetry test is inert"


def test_the_three_signals_the_review_named_are_wired_in_both_directions(registry, modules):
    """Regression pin on the exact predicates the review caught.

    Content-hash absence, missing permission metadata, and blanket network policy.
    Each is package-decidable, each is a named artifact_signal, and each is declared
    non-coverage by the module that computes it.
    """
    expected = {
        "AST07-S01": "AST01-content-hash-missing",
        "AST05-S01": "AST01-content-hash-missing",
        "AST10-S04": "AST06-missing-sandbox-declaration",
        "AST06-S02": "AST05-unrestricted-network-fetch",
    }
    by_id = {s["id"]: s for s in registry["scenarios"]}
    for scenario_id, check in expected.items():
        scenario = by_id[scenario_id]
        assert scenario["tier"] == "out-of-artifact", scenario_id
        assert scenario["artifact_signal_decidable"] == "package-decidable", (
            f"{scenario_id}'s signal is one field read; the registry must say so"
        )
        assert check in scenario["artifact_signal_checks"], scenario_id


def test_covers_full_links_only_scenarios_the_registry_tiers_static_detectable(by_id, modules):
    """The other direction: a detector cannot grant itself detectability."""
    for category, check, entry in _all_checks(modules):
        if entry["covers"] != "full":
            continue
        for rid in entry["registry_ids"]:
            assert rid in by_id, f"{category}/{check} links unknown registry id {rid}"
            assert by_id[rid]["tier"] == "static-detectable", (
                f"{category}/{check} claims covers: full over {rid}, which the registry "
                f"tiers {by_id[rid]['tier']!r} -- the registry wins"
            )


def test_artifact_signal_only_checks_proxy_a_scenario_that_declares_a_signal(by_id, modules):
    """And a proxy must name a real proxy target that is genuinely not decided."""
    for category, check, entry in _all_checks(modules):
        if entry["covers"] != "artifact-signal-only":
            continue
        for rid in entry["registry_ids"]:
            assert rid in by_id, f"{category}/{check} links unknown registry id {rid}"
            scenario = by_id[rid]
            assert scenario["tier"] != "static-detectable", (
                f"{category}/{check} proxies {rid}, which the registry already tiers "
                f"static-detectable -- it should be covers: full"
            )
            assert str(scenario.get("artifact_signal") or "").strip(), (
                f"{category}/{check} proxies {rid}, which declares no artifact_signal"
            )


def test_every_declared_covers_mode_is_one_of_the_manifests_three(modules):
    """One vocabulary across the corpus, the registry and the detectors."""
    for _category, _check, entry in _all_checks(modules):
        assert entry["covers"] in VALID_COVERS


# --- the label has to travel with the number -------------------------------


@pytest.mark.parametrize("category", CATEGORIES)
def test_f1_report_never_returns_a_number_without_a_scope(modules, category):
    module = modules[category]
    report = module.f1_report([])
    assert "scope" in report, f"{category}: f1_report dropped the scope label"
    if report["f1"] is None:
        assert report["scope"] == "none"
    else:
        assert report["scope"] == module.F1_SCOPE


def test_a_scenario_level_f1_is_earned_check_by_check(by_id, modules):
    """What a `scenario-level` scope has to be backed by, now that categories earn one.

    This replaces an earlier pin that asserted NO shipped module could claim
    `scenario-level` -- true while every category's checks were proxies or category
    preconditions, and false as soon as a detector was written that decides a named
    scenario's defining condition. That earlier test said in its own docstring that its
    failure was the signal to write this one, so the guard is re-expressed rather than
    dropped: the claim is no longer forbidden, it is itemised.

    A module claiming `scenario-level` must have every one of its checks declared
    `covers: full`, each linking at least one registry scenario, and the registry must
    independently tier every one of those scenarios `static-detectable`. A module cannot
    reach the label by mislabelling a proxy, and cannot reach it with no checks at all.
    """
    claimed = {category: module for category, module in modules.items() if module.F1_SCOPE == "scenario-level"}
    assert claimed, (
        "no module claims scenario-level, so this test is inert. If every category's "
        "checks really are proxies again, say so in the matrices and delete this test "
        "deliberately rather than letting it pass vacuously."
    )
    for category, module in claimed.items():
        assert module.CHECK_COVERAGE, f"{category} claims scenario-level with no declared checks"
        for check, entry in module.CHECK_COVERAGE.items():
            assert entry["covers"] == "full", (
                f"{category}/{check} is {entry['covers']!r} inside a scenario-level module"
            )
            assert entry["registry_ids"], f"{category}/{check} claims covers: full but links no scenario"
            for rid in entry["registry_ids"]:
                assert by_id[rid]["tier"] == "static-detectable", (
                    f"{category}/{check} claims scenario-level coverage of {rid}, which the "
                    f"registry tiers {by_id[rid]['tier']!r}"
                )


def test_ast10s_scenario_level_claim_is_written_down_where_a_reader_will_find_it(modules):
    """AST10 is the worked example of the rule above, so its paperwork is pinned.

    The whole reason the earlier blanket ban existed was that a scenario-level number is
    the strongest claim this repo can make. Where one is made, the category's coverage
    matrix has to carry the number, its scope, and the corpus it was measured on -- not
    just the module's `F1_SCOPE` constant.
    """
    assert modules["AST10"].F1_SCOPE == "scenario-level"
    matrix = (REPO_ROOT / "skills" / "AST10" / "coverage-matrix.md").read_text(encoding="utf-8")
    assert "scenario-level" in matrix
    assert "1.00" in matrix
    assert "6 labeled cases" in matrix
