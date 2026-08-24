"""``SCENARIO_TIERS`` is a mirror of ``scenarios/registry.yaml``, in every module, always.

THE HOLE THIS CLOSES
--------------------
Every detector module defines a module-level dict named ``SCENARIO_TIERS``, and for a
long time the ten modules disagreed about what its KEYS were. AST01..AST06 keyed it by
their own CHECK ids -- private slugs like ``AST01-content-hash-missing`` -- while
AST07..AST10 keyed it by canonical registry scenario ids (``AST07-S01``). Both shapes
type-check, both import cleanly, and each module's own tests passed against whichever
shape it had chosen.

The divergence was invisible until something counted the table. ``cli/bin/cli.js``'s
``list`` does exactly that: it reads ``SCENARIO_TIERS`` out of each module and prints the
per-tier counts. Under check-keying, AST01 printed ``static-detectable x10`` -- ten
CHECKS wearing a SCENARIO tier label -- while ``scenarios/registry.yaml`` rules only
SEVEN AST01 scenarios static-detectable. A reader of the repository's most-run command
was told the category decides ten of the whitepaper's scenarios when it decides seven.
That is a coverage overclaim, and it was produced by nothing more exotic than two tables
sharing a name.

THE RULE, and it admits no per-module variation
-----------------------------------------------
``SCENARIO_TIERS`` maps CANONICAL REGISTRY SCENARIO IDS to the tier the registry assigns
them, and nothing else. It is a statement about the whitepaper's attack surface, not
about the code beneath it. Per-check metadata -- what a shipped check computes, and what
it may claim over a named scenario -- belongs in ``CHECK_COVERAGE``, which every module
already carries and which already speaks ``fixtures/manifest.yaml``'s vocabulary
(``full`` / ``artifact-signal-only`` / ``category-precondition``).

A tier is never invented here. Whatever ``scenarios/registry.yaml`` says for a scenario
id is what ``SCENARIO_TIERS`` must say; where the two ever differ, the module is wrong.

WHY THIS FILE EXISTS ALONGSIDE THE PER-CATEGORY TESTS
-----------------------------------------------------
``tests/test_coverage_matrix*.py`` already pin the registry equality for the categories
their authoring tasks covered, and ``tests/test_tier_doctrine_symmetry.py`` pins the
``covers``-vs-tier ruling. Neither is parameterized over all ten categories, which is
precisely how the split survived: a new category, or a category whose matrix test was
scoped to a sibling task, could re-acquire check-keying without reddening anything. This
module is deliberately uniform -- ten categories, same four questions, no exemptions --
so the divergence cannot come back in the one place nobody is looking.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "scenarios" / "registry.yaml"

CATEGORIES = [f"AST{i:02d}" for i in range(1, 11)]

#: The canonical id shape the registry uses, and the only key shape SCENARIO_TIERS may
#: carry. A check slug (``AST01-content-hash-missing``) fails it; so does a bare category
#: id, a title, or an id from a hand-invented numbering.
SCENARIO_ID_RE = re.compile(r"^AST\d{2}-S\d{2}$")

VALID_TIERS = {"static-detectable", "agent-judgable", "out-of-artifact"}


# --- loading ---------------------------------------------------------------


@pytest.fixture(scope="module")
def registry() -> dict:
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registry_scenarios(registry) -> dict[str, dict]:
    """Every registry scenario, by id. The authority for every assertion below."""
    return {scenario["id"]: scenario for scenario in registry["scenarios"]}


def _load_detector(category: str):
    path = REPO_ROOT / "skills" / category / "scripts" / "detector.py"
    spec = importlib.util.spec_from_file_location(f"registrykeyed_{category}", path)
    assert spec is not None and spec.loader is not None, f"{category}: no detector module at {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def modules() -> dict:
    return {category: _load_detector(category) for category in CATEGORIES}


def _registry_ids_for(registry_scenarios: dict[str, dict], category: str) -> set[str]:
    return {sid for sid, s in registry_scenarios.items() if s["category"] == category}


# --- 1. the keys are registry scenario ids, and this category's ------------


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_key_is_a_canonical_registry_scenario_id(category, modules):
    """The shape test, and the one that would have failed on the old check-keying.

    ``AST01-content-hash-missing`` is a perfectly good CHECK id and a category-prefixed
    string, so a prefix test alone would have passed it. Only the ``-S\\d\\d`` suffix
    separates the registry's namespace from a module's private slug dialect.
    """
    tiers = modules[category].SCENARIO_TIERS
    offenders = [key for key in tiers if not SCENARIO_ID_RE.match(key)]
    assert not offenders, (
        f"{category}: SCENARIO_TIERS is keyed by registry scenario ids (AST\\d\\d-S\\d\\d) and "
        f"nothing else, but carries {offenders}. Those look like CHECK ids -- per-check "
        f"metadata belongs in CHECK_COVERAGE, which already exists in this module. Keying "
        f"the tier table by checks is what made `node cli/bin/cli.js list` print a count of "
        f"checks under a scenario-tier label."
    )


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_key_belongs_to_this_category(category, modules, registry_scenarios):
    """A module speaks for its own category's scenarios and no one else's.

    Checked twice on purpose: against the id's own prefix, and against the registry's
    `category` field for that id. A borrowed scenario would silently double-count in
    `list`, which sums per-module tier counts across the ten modules.
    """
    tiers = modules[category].SCENARIO_TIERS
    misprefixed = [key for key in tiers if SCENARIO_ID_RE.match(key) and not key.startswith(f"{category}-")]
    assert not misprefixed, f"{category}: SCENARIO_TIERS carries another category's scenarios: {misprefixed}"
    # Keys the registry does not carry are a separate failure with its own test and its own
    # message; skip them here so this test reports a miscategorised scenario rather than a
    # KeyError that says nothing about which rule was broken.
    for key in tiers:
        scenario = registry_scenarios.get(key)
        if scenario is None:
            continue
        assert scenario["category"] == category, (
            f"{category}: SCENARIO_TIERS carries {key}, which scenarios/registry.yaml files "
            f"under {scenario['category']}"
        )


# --- 2. every key exists in the registry, at the registry's tier -----------


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_key_exists_in_the_registry(category, modules, registry_scenarios):
    """No invented scenarios. The whitepaper's enumeration is rank 1, the registry rank 2."""
    tiers = modules[category].SCENARIO_TIERS
    unknown = sorted(set(tiers) - set(registry_scenarios))
    assert not unknown, (
        f"{category}: SCENARIO_TIERS declares {unknown}, which scenarios/registry.yaml does "
        f"not contain. The registry enumerates the whitepaper's named scenarios; a module "
        f"may not add to it."
    )


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_tier_equals_the_registry_tier(category, modules, registry_scenarios):
    """The load-bearing one: the module mirrors, it does not rule.

    A module that tiers a scenario one notch more optimistically than the registry hands
    itself an F1 denominator the registry withholds -- ``STATIC_DETECTABLE`` derives
    straight from this table. Equality, not compatibility.
    """
    tiers = modules[category].SCENARIO_TIERS
    disagreements = {
        key: (declared, registry_scenarios[key]["tier"])
        for key, declared in tiers.items()
        if key in registry_scenarios and declared != registry_scenarios[key]["tier"]
    }
    detail = "; ".join(
        f"{key}: module says {declared}, registry says {expected}"
        for key, (declared, expected) in sorted(disagreements.items())
    )
    assert not disagreements, (
        f"{category}: SCENARIO_TIERS disagrees with scenarios/registry.yaml -- {detail}. "
        f"The registry is authoritative on tier; a module mirrors it and never invents one."
    )


@pytest.mark.parametrize("category", CATEGORIES)
def test_declared_tiers_are_from_the_registrys_own_vocabulary(category, modules, registry):
    tiers = modules[category].SCENARIO_TIERS
    assert VALID_TIERS == set(registry["tiers"]), "registry tier vocabulary moved; update this module"
    invalid = {key: tier for key, tier in tiers.items() if tier not in VALID_TIERS}
    assert not invalid, f"{category}: SCENARIO_TIERS uses tiers outside the registry's vocabulary: {invalid}"


# --- 3. completeness: no silent omissions ----------------------------------


@pytest.mark.parametrize("category", CATEGORIES)
def test_scenario_tiers_covers_the_category_completely(category, modules, registry_scenarios):
    """Equality with the registry's set, not containment in it.

    Omission is the quieter half of the same overclaim, and it is not hypothetical: AST07
    once listed two of its three scenarios and AST09 three of its seven, so a reader of
    the module concluded the category had a smaller attack surface than the whitepaper
    names. Where the missing scenarios are all out-of-artifact the published F1 does not
    move, which is exactly why nothing caught it.
    """
    declared = set(modules[category].SCENARIO_TIERS)
    expected = _registry_ids_for(registry_scenarios, category)
    missing = sorted(expected - declared)
    extra = sorted(declared - expected)
    assert declared == expected, (
        f"{category}: SCENARIO_TIERS must enumerate the category's registry scenarios exactly. "
        f"Missing {missing}; unexpected {extra}."
    )


@pytest.mark.parametrize("category", CATEGORIES)
def test_scenario_count_matches_the_registrys_own_header(category, modules, registry):
    """A third source for the same number, so a coordinated edit is still caught.

    ``scenarios/registry.yaml``'s ``categories`` block states each category's scenario
    count in its own header, independently of the entries below it. Dropping an entry and
    a module row together would satisfy the equality test above; it does not satisfy this.
    """
    stated = registry["categories"][category]["scenario_count"]
    assert len(modules[category].SCENARIO_TIERS) == stated, (
        f"{category}: SCENARIO_TIERS has {len(modules[category].SCENARIO_TIERS)} entries; "
        f"scenarios/registry.yaml's categories block states {stated}"
    )


@pytest.mark.parametrize("category", CATEGORIES)
def test_static_detectable_is_derived_from_the_table_not_asserted(category, modules):
    """``STATIC_DETECTABLE`` is the F1 denominator, so it must fall out of the mirror.

    If it were written by hand it could carry a scenario the registry does not tier
    static-detectable -- or a check id, which is how a denominator gets padded.
    """
    module = modules[category]
    assert module.STATIC_DETECTABLE == {
        sid for sid, tier in module.SCENARIO_TIERS.items() if tier == "static-detectable"
    }, f"{category}: STATIC_DETECTABLE is not the static-detectable slice of SCENARIO_TIERS"


# --- 4. CHECK_COVERAGE is the OTHER table, and stays that way --------------


@pytest.mark.parametrize("category", CATEGORIES)
def test_check_coverage_is_keyed_by_this_categorys_check_ids(category, modules):
    """Per-check metadata lives here, and every shipped check has an entry.

    ``DETECTORS`` is the map of checks that actually run. A check with no
    ``CHECK_COVERAGE`` row is a finding a reader cannot place: they see it fire and have
    no statement of whether it decides a named scenario, proxies one, or decides none.
    ``CHECK_COVERAGE`` may be the larger set -- AST05 and AST06 each document a check that
    is specified but does not ship -- but it may never be the smaller one.
    """
    module = modules[category]
    undocumented = sorted(set(module.DETECTORS) - set(module.CHECK_COVERAGE))
    assert not undocumented, (
        f"{category}: DETECTORS registers {undocumented} with no CHECK_COVERAGE entry, so "
        f"nothing states what those checks claim over a named scenario"
    )
    foreign = sorted(key for key in module.CHECK_COVERAGE if not key.startswith(f"{category}-"))
    assert not foreign, f"{category}: CHECK_COVERAGE is keyed by this category's check ids; found {foreign}"


@pytest.mark.parametrize("category", CATEGORIES)
def test_a_check_id_that_looks_like_a_scenario_id_covers_exactly_that_scenario(category, modules):
    """The anti-conflation rule, stated as the one collision that is safe.

    The two tables answer different questions, so sharing a key makes the key ambiguous:
    is ``AST08-S02`` the scenario the registry tiers, or the check this module runs? The
    honest split is disjoint namespaces, and eight of the ten modules have them -- their
    checks are slugs (``AST01-websocket-c2``).

    AST08 and AST10 do not, and the collision there is deliberate and harmless: each of
    those checks decides exactly one scenario, in full, and is named after it, so
    ``CHECK_COVERAGE["AST08-S02"]`` reads ``registry_ids: [AST08-S02], covers: full``. The
    key and the thing it covers are the same scenario; there is nothing to be wrong about.
    (It is still a namespace collision, and undoing it means renaming
    ``fixtures/manifest.yaml``'s ``detector_check`` values too -- recorded rather than
    done here.)

    What this test forbids is every other overlap, which is the conflation itself: a key
    that is a scenario id while covering a DIFFERENT scenario, or covering it only as a
    proxy. Under either of those, a reader who takes the key at face value reads a check
    id as a tier declaration -- the precise misreading that put ten checks under AST01's
    static-detectable label.
    """
    module = modules[category]
    collisions = set(module.CHECK_COVERAGE) & set(module.SCENARIO_TIERS)
    for check in sorted(collisions):
        entry = module.CHECK_COVERAGE[check]
        assert entry["covers"] == "full" and entry["registry_ids"] == [check], (
            f"{category}: CHECK_COVERAGE[{check!r}] shares its key with a SCENARIO_TIERS entry "
            f"but does not fully cover that same scenario (covers={entry['covers']!r}, "
            f"registry_ids={entry['registry_ids']!r}). Either give the check its own slug or "
            f"make the key the scenario it decides in full -- a scenario-shaped key that means "
            f"something else is how a check id gets read as a tier."
        )


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_scenario_a_check_claims_to_cover_exists_in_the_registry(category, modules, registry_scenarios):
    """``registry_ids`` links out to the authority, including across categories.

    Cross-category links are legitimate and present: AST01's content-hash check names
    AST05-S01 and AST07-S01 as the scenarios whose ``artifact_signal`` it computes. What
    is never legitimate is a link to an id the registry does not carry -- that is a
    coverage claim over a scenario nobody has enumerated.
    """
    for check, entry in modules[category].CHECK_COVERAGE.items():
        unknown = sorted(set(entry["registry_ids"]) - set(registry_scenarios))
        assert not unknown, (
            f"{category}: CHECK_COVERAGE[{check!r}] claims to bear on {unknown}, which "
            f"scenarios/registry.yaml does not contain"
        )


@pytest.mark.parametrize("category", CATEGORIES)
def test_check_coverage_never_carries_a_tier(category, modules):
    """The other direction of the same split: a check does not get to tier anything.

    A ``tier`` key inside a ``CHECK_COVERAGE`` entry would be a module ruling on
    detectability from the check's side -- the exact move the signal-symmetry review
    caught, where a predicate was static-detectable when it let a detector claim coverage
    and out-of-artifact when it would have obliged someone to build one.
    """
    for check, entry in modules[category].CHECK_COVERAGE.items():
        assert "tier" not in entry, (
            f"{category}: CHECK_COVERAGE[{check!r}] declares a tier. Tiers come from "
            f"scenarios/registry.yaml via SCENARIO_TIERS; a check declares only what it covers."
        )
