"""Tests for scripts/external_validation.py and the report it publishes.

``docs/external-validation.md`` publishes figures measured over 360 skill
packages that live in eight checkouts outside this repository. Those checkouts
cannot be vendored and cannot be in CI, so the usual guard — re-derive every
published figure from the artifact that produced it — is only half available
here. This file takes the half that is, and is explicit about the half that
is not.

**What is guarded.** Everything about the record that does not need the corpus:

* the 36-check roster, re-derived from the SHIPPED DETECTOR MODULES rather than
  from the record, so a check added, renamed, removed or reclassified fails the
  build instead of quietly invalidating a published table;
* the fixture-versus-wild declaration census on the FIXTURE side, recomputed
  live through the same loader ``eval/generate_f1_report.py`` scores through —
  the headline of the whole report is that comparison, and half of it is in this
  repository;
* every piece of arithmetic in the record, against the record's own rows;
* the hand-written prose, for the specific figures it states in words, because
  a generated table beside a stale sentence is still a stale document;
* the no-naming rule the corpora are published under.

**What is not, and cannot be.** A firing count going stale because a detector's
*logic* changed while its identity did not. Nothing short of re-running over the
corpus catches that. ``test_the_record_names_the_tree_it_was_measured_against``
is the consolation prize: the record must at least say what it was measured on.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from detectors.scaffold import VALID_COVERS  # noqa: E402
from scripts import external_validation as ev  # noqa: E402

RECORD_PATH = REPO_ROOT / "eval" / "external-validation.json"
REPORT_PATH = REPO_ROOT / "docs" / "external-validation.md"


@pytest.fixture(scope="module")
def record() -> dict:
    return json.loads(RECORD_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def report() -> str:
    return REPORT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def flat_report() -> str:
    """The report with every run of whitespace collapsed to one space.

    Mirrors ``tests/test_docs.py::_flat``: a prose assertion should match a
    sentence wherever the source file happened to wrap it, so reflowing a
    paragraph never breaks a test that is really about a number.
    """
    return " ".join(REPORT_PATH.read_text(encoding="utf-8").split())


# ---------------------------------------------------------------------------
# The generator agrees with the record
# ---------------------------------------------------------------------------


def test_the_report_is_in_sync_with_the_record():
    """`--check` is necessary but nowhere near sufficient; the rest of the file is why."""
    assert ev.main(["--check"]) == 0


def test_every_generated_region_is_marked_in_the_report(report):
    for region in ev.REGIONS:
        assert ev.begin(region) in report, f"missing BEGIN marker for {region}"
        assert ev.end(region) in report, f"missing END marker for {region}"


def test_rewriting_a_report_that_lost_a_marker_refuses_rather_than_guessing(record):
    """A silently-skipped region would publish a stale table under a fresh record."""
    mangled = REPORT_PATH.read_text(encoding="utf-8").replace(ev.begin("totals"), "")
    with pytest.raises(ev.ExternalValidationError, match="totals"):
        ev.rewrite(mangled, record)


# ---------------------------------------------------------------------------
# The record describes the detector suite this repository actually ships
# ---------------------------------------------------------------------------


def test_the_recorded_check_roster_is_the_one_the_detectors_ship_today(record):
    """The guard that matters most, and the one `--check` cannot provide.

    Re-derived from the modules, not from the record, so this fails on a check
    added, renamed, deleted, retiered or reclassified — any of which would leave
    the published before/after table describing a suite that no longer exists.
    """
    shipped = ev.shipped_checks()
    recorded = [{k: v for k, v in c.items() if k not in ("before", "after")} for c in record["checks"]]
    assert recorded == shipped, (
        "eval/external-validation.json describes a different detector suite than this tree ships — "
        "re-run the audit and `--record` it; the published counts are stale"
    )


def test_every_recorded_covers_value_is_one_the_scaffold_defines(record):
    for check in record["checks"]:
        assert check["covers"] in VALID_COVERS, f"{check['check']} claims an unknown coverage mode"


def test_the_recorded_check_count_matches_the_checks_each_package_saw(record):
    assert record["totals"]["checks_per_package"] == len(record["checks"])


# ---------------------------------------------------------------------------
# The fixture half of the headline comparison, recomputed live
# ---------------------------------------------------------------------------


def test_the_fixture_declaration_census_is_still_true_of_the_fixtures(record):
    """The report's headline is fixtures-declare versus the-wild-does-not.

    The wild half is a dated measurement over corpora that are not here. The
    fixture half is in this repository and is therefore recomputed rather than
    trusted: if someone adds a permissions block to a fixture, or adds a case,
    the published comparison changes and this fails.
    """
    assert record["fixture_declarations"] == ev.fixture_census()


def test_ast01s_corpus_cannot_exercise_the_branch_the_fix_repaired(record):
    """The structural claim the whole report rests on, asserted rather than narrated.

    `AST01-undeclared-egress` degenerated on packages declaring no
    `permissions.network`. Every AST01 fixture declares one, so no fixture can
    reach that branch — which is why F1 = 1.000 survived the fix unchanged, and
    why a fixture corpus could never have caught it.
    """
    ast01 = record["fixture_declarations"]["per_category"]["AST01"]
    assert ast01["declares_network"] == ast01["cases"] > 0
    assert record["wild_declarations"]["declares_network"] == 0


# ---------------------------------------------------------------------------
# The record's arithmetic, against its own rows
# ---------------------------------------------------------------------------


def test_the_corpora_sum_to_the_audited_total(record):
    by_label = record["totals"]["packages_by_label"]
    assert {c["label"]: c["packages"] for c in record["corpora"]} == by_label
    assert sum(by_label.values()) == record["totals"]["packages"]


def test_the_check_run_total_is_the_product_it_claims_to_be(record):
    totals = record["totals"]
    assert totals["check_runs"] == totals["checks_per_package"] * totals["packages"]


def test_the_firing_totals_are_the_sum_of_the_per_check_rows(record):
    totals = record["totals"]
    assert totals["firings_before"] == sum(c["before"] for c in record["checks"])
    assert totals["firings_after"] == sum(c["after"] for c in record["checks"])


def test_no_check_fired_more_often_than_there_are_packages(record):
    for check in record["checks"]:
        for column in ("before", "after"):
            assert 0 <= check[column] <= record["totals"]["packages"], f"{check['check']}.{column}"


def test_the_universal_checks_are_exactly_the_non_covering_ones(record):
    """The load-bearing claim of the report's central section.

    Three checks fired on every package, and the report's argument is that the
    detectability contract had already ruled all three non-covering, so none of
    them touched a published F1. If a `covers: full` check ever joins them, that
    argument is void and this fails.
    """
    packages = record["totals"]["packages"]
    universal = [c for c in record["checks"] if c["before"] == c["after"] == packages]
    assert len(universal) == 3, [c["check"] for c in universal]
    assert [c["covers"] for c in universal] == [
        "artifact-signal-only",
        "category-precondition",
        "artifact-signal-only",
    ]
    assert not any(c["covers"] == "full" for c in universal)


def test_the_record_names_the_tree_it_was_measured_against(record):
    """The counts cannot be re-derived in CI, so they must at least be dated."""
    run = record["run"]
    assert run["date"], "the record must say when it was measured"
    assert run["before_tree"] and run["after_tree"], "the record must say what it was measured on"


# ---------------------------------------------------------------------------
# The adjudications
# ---------------------------------------------------------------------------


def test_every_adjudication_names_a_shipped_check_and_agrees_on_its_coverage(record):
    rulings = {c["check"]: c["covers"] for c in record["checks"]}
    labels = {c["label"] for c in record["corpora"]}
    for adjudication in record["adjudications"]:
        check = adjudication["check"]
        assert check in rulings, f"{check} is adjudicated but not shipped"
        assert adjudication["covers"] == rulings[check], f"{check}: adjudication disagrees on coverage"
        assert adjudication["corpus"] in labels, f"{check}: unknown corpus {adjudication['corpus']}"


def test_the_adjudications_account_for_every_non_universal_firing(record):
    """No firing may go unexplained.

    Subtract the universal checks and every remaining firing, before and after,
    must appear in the adjudication table. A firing nobody wrote a verdict for
    is the failure mode this whole document exists to prevent.
    """
    packages = record["totals"]["packages"]
    for column in ("before", "after"):
        from_checks = sum(c[column] for c in record["checks"] if not (c["before"] == c["after"] == packages))
        from_adjudications = sum(a[column] for a in record["adjudications"])
        assert from_checks == from_adjudications, f"{column}: {from_checks} firings, {from_adjudications} adjudicated"


def test_only_a_covering_check_is_ever_called_a_false_positive(record):
    """A precondition firing convicts nothing, so it cannot be a false positive.

    Calling one that would import a claim the check never made — the exact
    confusion the audit renderer's `FINDING`/`signal`/`observed` vocabulary
    exists to prevent, and it would be embarrassing to reintroduce it in the
    document that reports the fix.
    """
    for adjudication in record["adjudications"]:
        if adjudication["verdict"].startswith("false positive"):
            assert adjudication["covers"] == "full", adjudication["check"]


def test_an_open_false_positive_is_still_firing_and_a_fixed_one_is_not(record):
    for adjudication in record["adjudications"]:
        verdict = adjudication["verdict"]
        if verdict.endswith("fixed"):
            assert adjudication["after"] == 0, f"{adjudication['check']} is called fixed but still fires"
        if verdict.endswith("OPEN"):
            assert adjudication["after"] > 0, f"{adjudication['check']} is called open but no longer fires"


# ---------------------------------------------------------------------------
# The prose, for the figures it states in words
# ---------------------------------------------------------------------------


def test_the_prose_states_the_same_figures_the_tables_do(record, flat_report):
    """A generated table beside a stale sentence is still a stale document."""
    totals = record["totals"]
    fixtures = record["fixture_declarations"]["total"]
    packages = totals["packages"]
    covering = [c for c in record["checks"] if c["covers"] == "full"]
    universal = [c for c in record["checks"] if c["before"] == c["after"] == packages]
    silent = [c for c in record["checks"] if c["before"] == c["after"] == 0]
    expected = [
        f"{fixtures['declares_permissions']} of the {fixtures['cases']} labeled fixture cases",
        f"0 of the {packages} real packages do",
        f"{len(silent)} of the {len(record['checks'])} checks never fired on any of the {packages} packages",
        f"{sum(c['before'] for c in universal):,} firings",
        f"{len(covering) * packages:,} covering-check runs",
        f"Only {record['totals']['packages_by_label']['A']} of the {packages} packages",
    ]
    missing = [phrase for phrase in expected if phrase not in flat_report]
    assert missing == [], f"the prose has drifted from the record: {missing}"


def test_the_report_says_what_it_does_not_establish(flat_report):
    """Non-negotiable, and the reason this document is publishable at all.

    The corpus contains no labelled positives, so the report may not be read as
    evidence of recall. It has to say so in those words, not imply it.
    """
    assert "The repository cannot claim it would catch a real malicious skill." in flat_report
    assert "no labelled real-world positives" in flat_report
    assert "presumed benign" in flat_report


# ---------------------------------------------------------------------------
# The no-naming rule
# ---------------------------------------------------------------------------

#: The one upstream this repository already cites by name — the vendored judge
#: rubric's origin, credited in NOTICE, THIRD_PARTY_LICENSES.md and the README
#: badge row. Every other corpus is published under an opaque label.
NAMEABLE_UPSTREAM = "https://github.com/softaworks/agent-toolkit"

GITHUB_URL_RE = re.compile(r"https://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+")
ABSOLUTE_LOCAL_PATH_RE = re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/")


@pytest.mark.parametrize("path", [RECORD_PATH, REPORT_PATH], ids=lambda p: p.name)
def test_the_committed_artifacts_name_no_corpus_but_the_one_already_credited(path):
    """The corpora are other people's repositories and are published by shape, not name.

    ``tests/test_docs.py::test_no_committed_file_names_a_sibling_repo`` already
    scans the whole tree against a fixed list of sibling repository names. This
    is the complement rather than a duplicate: stated as a POSITIVE property —
    exactly one repository slug may appear in these two files — it also catches a
    corpus this repository has never had a name for, which a blocklist cannot.
    """
    text = path.read_text(encoding="utf-8")
    unexpected = sorted(set(GITHUB_URL_RE.findall(text)) - {NAMEABLE_UPSTREAM})
    assert unexpected == [], f"{path.name} names a repository it may not: {unexpected}"


@pytest.mark.parametrize("path", [RECORD_PATH, REPORT_PATH], ids=lambda p: p.name)
def test_the_committed_artifacts_carry_no_local_absolute_path(path):
    """A home-directory path leaks both a machine layout and a checkout's name."""
    leaked = ABSOLUTE_LOCAL_PATH_RE.findall(path.read_text(encoding="utf-8"))
    assert leaked == [], f"{path.name} leaks a local path: {sorted(set(leaked))}"


def test_a_recorded_corpus_composition_accounts_for_all_of_its_packages(record):
    """Corpus D is 87 packages of four different kinds, and the report says which.

    A breakdown that stops summing to the corpus size is a breakdown someone
    edited without recounting — and the whole point of publishing it is that it
    is unflattering (17 of the 87 are in-repo test fixtures).
    """
    for corpus in record["corpora"]:
        composition = corpus.get("composition")
        if composition is None:
            continue
        assert sum(composition.values()) == corpus["packages"], f"corpus {corpus['label']} composition"


def test_the_hygiene_figures_cannot_exceed_the_corpus(record):
    hygiene = record["corpus_hygiene"]
    packages = record["totals"]["packages"]
    assert 0 < hygiene["distinct_skill_md_digests"] <= packages
    assert hygiene["exact_duplicate_packages"] == packages - hygiene["distinct_skill_md_digests"]


def test_the_prose_states_the_recorded_corpus_hygiene(record, flat_report):
    hygiene = record["corpus_hygiene"]
    packages = record["totals"]["packages"]
    composition = next(c["composition"] for c in record["corpora"] if c.get("composition"))
    expected = [
        f"({hygiene['distinct_skill_md_digests']} distinct `SKILL.md` digests among {packages} packages)",
        f"{hygiene['exact_duplicate_packages']} of the {packages} packages are byte-identical duplicates",
        f"{composition['in-repo test fixture']} in-repo test fixtures",
    ]
    missing = [phrase for phrase in expected if phrase not in flat_report]
    assert missing == [], f"the hygiene prose has drifted from the record: {missing}"


def test_the_corpora_are_identified_by_opaque_label(record):
    labels = [c["label"] for c in record["corpora"]]
    assert labels == sorted(labels), "corpus labels should read in order"
    assert all(re.fullmatch(r"[A-Z]", label) for label in labels), labels
    for corpus in record["corpora"]:
        assert corpus["independence"] and corpus["shape"], f"corpus {corpus['label']} is undescribed"
