"""`detectors/fixture_loader.py` is the wire between the labeled corpus and the
detectors, so its failure modes are the ones that could silently shrink an F1
denominator again.

The loader itself is exercised end-to-end by `skills/AST03/scripts/test_ast03_detector.py`
and `skills/AST04/scripts/test_ast04_detector.py`, which run their real corpora
through their real detectors. What this module covers is the part those cannot:
what happens when the corpus declaration and the code disagree. Every one of
those cases must RAISE. A loader that skipped a mislabeled case would report a
clean F1 over a denominator quietly missing a fixture, which is the exact shape
`detectors/engine.py` already refuses for an unregistered scenario id.
"""

from __future__ import annotations

import pathlib

import pytest

from detectors.fixture_loader import (
    FixtureCorpusError,
    load_category_cases,
    load_detector,
    load_fixture_package,
    load_manifest,
    run_corpus,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


# --- loading one fixture directory ------------------------------------------


def test_a_fixture_directory_loads_as_a_package_not_as_one_file():
    """The wiring gap that blocked publication: a fixture read as
    `{"files": {"SKILL.md": <bytes>}}` shows a detector none of the payload files
    the scenario actually lives in."""
    pkg = load_fixture_package(REPO_ROOT / "fixtures" / "AST04" / "V1-yaml-frontmatter-injection")
    assert pkg["manifest_source"] == "SKILL.md frontmatter"
    assert set(pkg["files"]) >= {"SKILL.md", "metadata.yaml", "scripts/loader.py"}
    assert pkg["manifest"]["permissions"]["deny_write"] == ["SOUL.md", "MEMORY.md", "AGENTS.md"]


def test_the_loader_translates_permissions_into_the_detector_shape():
    """It delegates to the repo's one USF translator rather than carrying a copy."""
    pkg = load_fixture_package(REPO_ROOT / "fixtures" / "AST03" / "V3-undeclared-shell-exec")
    permissions = pkg["manifest"]["permissions"]
    assert permissions["shell"] == {"allowed": True, "commands": []}
    assert permissions["network"]["allow"] == ["*"]
    assert any("deny_write" in note for note in pkg["adapter_notes"])


def test_a_missing_fixture_directory_raises():
    with pytest.raises(FixtureCorpusError, match="no such fixture directory"):
        load_fixture_package(REPO_ROOT / "fixtures" / "AST04" / "does-not-exist")


# --- corpus declaration guard rails -----------------------------------------


def test_an_unknown_category_raises_rather_than_returning_nothing():
    with pytest.raises(FixtureCorpusError, match="not declared"):
        load_category_cases("AST99")


def test_a_case_naming_an_undeclared_corpus_check_raises():
    """A silent drop here is a denominator one case smaller than the manifest says."""
    manifest = load_manifest()
    manifest["categories"]["AST04"]["cases"][0]["scenario_id"] = "AST04-S-typo"
    with pytest.raises(FixtureCorpusError, match="does not declare"):
        load_category_cases("AST04", manifest)


def test_a_corpus_check_with_no_detector_check_raises():
    manifest = load_manifest()
    del manifest["categories"]["AST04"]["detectable_scenarios"][0]["detector_check"]
    with pytest.raises(FixtureCorpusError, match="declares no detector_check"):
        load_category_cases("AST04", manifest)


def test_a_corpus_check_bound_to_an_unimplemented_detector_raises():
    manifest = load_manifest()
    manifest["categories"]["AST04"]["detectable_scenarios"][0]["detector_check"] = "AST04-not-a-real-check"
    with pytest.raises(FixtureCorpusError, match="does not implement"):
        run_corpus("AST04", manifest)


# --- the scoring contract ---------------------------------------------------


@pytest.mark.parametrize("category", ["AST03", "AST04"])
def test_every_case_the_manifest_declares_is_scored(category):
    """No case may fall out of the run: the count in equals the count scored."""
    manifest = load_manifest()
    declared = len(manifest["categories"][category]["cases"])
    assert run_corpus(category).cases() == declared == len(load_category_cases(category, manifest))


def test_proxy_and_scenario_level_figures_are_computed_separately():
    """A mixed corpus must be able to report its halves apart, or the proxy cases
    inflate a number labeled as scenario coverage."""
    result = run_corpus("AST03")
    assert result.cases("full") + result.cases("artifact-signal-only") == result.cases()
    assert result.cases("full") == 2
    assert result.cases("artifact-signal-only") == 4


def test_a_check_that_fired_on_everything_would_not_be_reported_as_discriminating():
    """The AST01 failure shape, asserted against the reporting logic itself.

    `discriminates` is what the detector tests key on, so it has to be false for a
    check that returns one verdict for its whole pair — not merely for one with a
    poor F1.
    """
    from detectors.fixture_loader import CheckResult

    always_fires = CheckResult(
        corpus_check="X",
        detector_check="x-check",
        covers="full",
        registry_ids=("X-S01",),
        true_positives=1,
        false_positives=1,
        false_negatives=0,
        true_negatives=0,
        case_verdicts=(("V1", True, True), ("C2", True, False)),
    )
    assert always_fires.discriminates is False
    assert always_fires.f1 == pytest.approx(2 / 3)  # the coin flip the review named

    separates = CheckResult(
        corpus_check="X",
        detector_check="x-check",
        covers="full",
        registry_ids=("X-S01",),
        true_positives=1,
        false_positives=0,
        false_negatives=0,
        true_negatives=1,
        case_verdicts=(("V1", True, True), ("C2", False, False)),
    )
    assert separates.discriminates is True
    assert separates.f1 == 1.0


# --- a published number must be a measured number ---------------------------
#
# The gap these three tests close: `fixtures/manifest.yaml` published
# `"scenario-level 1.00 (4 scenario checks, n=8)"` for AST08 while all four of
# its labeled checks carried no `detector_check` at all. Nothing ran, so the
# number was a claim, not a measurement -- and the bookkeeping test in
# `tests/test_coverage_matrix.py` did not catch it, because that test only asks
# whether the published string is the literal `"pending-detector"`.

MANIFEST = load_manifest()

#: Every category whose corpus declares at least one labeled detectable check.
#: Derived from the manifest rather than listed, so a category that gains or
#: loses a corpus is picked up without editing this file.
CATEGORIES_WITH_A_CORPUS = sorted(
    name for name, entry in (MANIFEST.get("categories") or {}).items() if (entry.get("detectable_scenarios") or [])
)


def test_the_corpus_roster_is_not_empty():
    """A parametrize list derived from data must be checked for emptiness, or
    every test below it passes vacuously the day the derivation breaks."""
    assert len(CATEGORIES_WITH_A_CORPUS) >= 8, CATEGORIES_WITH_A_CORPUS


@pytest.mark.parametrize("category", CATEGORIES_WITH_A_CORPUS)
def test_every_labeled_check_names_a_detector_its_module_implements(category):
    """An unwired label is a corpus that measures nothing."""
    entry = MANIFEST["categories"][category]
    module = load_detector(category)
    for check in entry["detectable_scenarios"]:
        detector_check = check.get("detector_check")
        assert detector_check, (
            f"{category}/{check['id']} is a labeled detectable check with no `detector_check`; "
            f"its fixtures are scored against nothing and any F1 published for "
            f"{category} is unmeasured"
        )
        assert detector_check in module.DETECTORS, (
            f"{category}/{check['id']} names detector check {detector_check!r}, which "
            f"skills/{category}/scripts/detector.py does not register"
        )


@pytest.mark.parametrize("category", CATEGORIES_WITH_A_CORPUS)
def test_a_published_f1_is_backed_by_a_run_that_scores_every_declared_case(category):
    """The number in `published_f1` must come from a corpus that actually ran.

    Asserted as a property of the run, not of the string: the corpus executes,
    and the count of cases it scored equals the count the manifest declares. A
    category whose checks were never wired raises out of `run_corpus` here
    instead of publishing a figure nothing computed.
    """
    entry = MANIFEST["categories"][category]
    published = entry.get("published_f1")
    assert published not in (None, "pending-detector"), (
        f"{category} declares a labeled corpus; publishing {published!r} hides it"
    )
    result = run_corpus(category)
    assert result.cases() == len(entry["cases"]), (
        f"{category} declares {len(entry['cases'])} case(s) but the run scored {result.cases()}"
    )


def test_the_shared_loader_and_a_category_local_corpus_agree_on_the_same_number():
    """AST08 was measured twice by two paths that had never been compared.

    `skills/AST08/scripts/test_ast08_detector.py` builds its own corpus with the
    module's `load_package_dir` and scores it with `detector.f1_report`; the
    shared pipeline scores each check over its own labeled pair. Those are
    genuinely different denominators — the category-local path evaluates every
    check against all eight packages (TN=7 per check), the shared one against
    its own pair (TN=1) — so agreeing on TP/FP/FN is a real cross-check rather
    than a tautology, and disagreeing would mean one of the two published
    numbers came from a corpus the other does not recognise.
    """
    local = load_detector("AST08")
    entry = MANIFEST["categories"]["AST08"]
    check_of = {s["id"]: s["detector_check"] for s in entry["detectable_scenarios"]}

    # Labels come from the manifest, never from what the detector happened to
    # do: an expectation derived from the output would make any agreement
    # tautological, which is the failure this whole file exists to prevent.
    fixtures = []
    for case in entry["cases"]:
        directory = (REPO_ROOT / case["path"]).parent
        expected = {check_of[case["scenario_id"]]} if case["label"] == "vulnerable" else set()
        fixtures.append((local.load_package_dir(directory), expected))
    assert len(fixtures) == 8
    local_report = local.f1_report(fixtures)

    shared = run_corpus("AST08")
    assert (shared.true_positives, shared.false_positives, shared.false_negatives) == (
        local_report["tp"],
        local_report["fp"],
        local_report["fn"],
    )
    assert shared.f1() == local_report["f1"] == 1.0
    assert shared.f1_scope == local_report["scope"] == "scenario-level"


def test_ast08_corpus_is_wired_and_every_check_discriminates():
    """The positive counterpart of the AST08 gap, in the shape AST04/05/06 use.

    Two of AST08's four scenarios are decided from bytes the text scan view
    cannot carry -- a `.pyc` header under `__pycache__` (`AST08-S08`) and a zip
    central directory plus a symlink target (`AST08-S07`) -- so this also pins
    that the byte views reach the detector. Without them `AST08-S08` returns
    "every shipped .pyc corresponds to shipped source" for its vulnerable case
    and the check silently scores a false negative.
    """
    entry = MANIFEST["categories"]["AST08"]
    result = run_corpus("AST08")
    assert result.cases() == len(entry["cases"]) == 8
    assert {c.corpus_check for c in result.checks} == {"AST08-S02", "AST08-S04", "AST08-S07", "AST08-S08"}
    for check in result.checks:
        verdicts = {predicted for _case, predicted, _label in check.case_verdicts}
        assert verdicts == {True, False}, f"{check.detector_check} does not discriminate: {check}"
        assert check.false_positives == 0 and check.false_negatives == 0, check
    assert result.f1() == 1.0

    module = load_detector("AST08")
    for case in load_category_cases("AST08"):
        if case.is_vulnerable:
            continue
        fired = [f.scenario for f in module.run_all(case.pkg) if f.detected]
        assert fired == [], f"{case.case_id} is labeled clean but fired {fired}"


def test_the_byte_views_are_what_ast08_s08_needs_and_the_text_view_alone_is_not():
    """Pins the reason `byte_views` exists, from both sides.

    If a future change makes the bridge's text view carry `__pycache__`, the
    second half of this test fails and the escape hatch can be retired
    deliberately rather than kept out of habit.
    """
    fixture = REPO_ROOT / "fixtures" / "AST08" / "V4-bytecode-cache-poisoning"
    module = load_detector("AST08")

    text_only = load_fixture_package(fixture, byte_views=None)
    assert "blobs" not in text_only
    assert not module.DETECTORS["AST08-S08"](text_only).detected

    with_bytes = load_fixture_package(fixture, byte_views=module.load_package_dir)
    assert any(name.endswith(".pyc") for name in with_bytes["blobs"])
    assert module.DETECTORS["AST08-S08"](with_bytes).detected


def test_the_byte_view_never_overwrites_a_file_the_bridge_already_read():
    """Two views of the same file must not be able to disagree."""
    fixture = REPO_ROOT / "fixtures" / "AST08" / "V1-obfuscated-instruction"
    module = load_detector("AST08")
    merged = load_fixture_package(fixture, byte_views=module.load_package_dir)
    bridged = load_fixture_package(fixture, byte_views=None)
    for name, text in bridged["files"].items():
        assert merged["files"][name] == text
