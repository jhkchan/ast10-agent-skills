"""`audit --sarif` must emit valid SARIF 2.1.0, and must not lose the contract.

The reason this format matters to this repository is narrow. A scanner that
emits only its detections teaches a reader that silence means safety, and the
whole point of the per-scenario decidability contract is that silence is
usually an unasked question. SARIF has vocabulary for that -- `kind` -- so the
conversion is only correct if the `agent-judgable` and `out-of-artifact` tiers
survive it. These tests fail if they are flattened away.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "bin" / "cli.js"
FIXTURE = "fixtures/AST01/V1-obfuscated-payload-exec"
REGISTRY = REPO_ROOT / "scenarios" / "registry.yaml"

#: SARIF's closed set for `result.kind`, and the subset this tool emits.
EMITTED_KINDS = {"fail", "pass", "open", "notApplicable"}


@pytest.fixture(scope="module")
def sarif() -> dict:
    node = subprocess.run(["node", "--version"], capture_output=True, text=True, check=False)
    if node.returncode != 0:
        pytest.skip("node is not available")
    result = subprocess.run(
        ["node", str(CLI), "audit", FIXTURE, "--sarif"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_it_is_sarif_2_1_0(sarif):
    assert sarif["version"] == "2.1.0"
    assert sarif["$schema"].endswith("sarif-schema-2.1.0.json")
    assert len(sarif["runs"]) == 1


def test_the_driver_names_itself_as_not_an_owasp_project(sarif):
    """SARIF travels into dashboards that show the tool name and nothing else."""
    driver = sarif["runs"][0]["tool"]["driver"]
    assert driver["name"] == "ast10-agent-skills"
    assert "NOT an OWASP project" in driver["organization"]
    assert "owasp" not in driver["name"].lower(), "the tool NAME must not carry the OWASP word mark"


def test_the_version_is_the_published_one(sarif):
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert sarif["runs"][0]["tool"]["driver"]["version"] == package["version"]


def test_every_result_kind_is_one_this_tool_declares(sarif):
    kinds = {r["kind"] for r in sarif["runs"][0]["results"]}
    assert kinds <= EMITTED_KINDS, f"unexpected SARIF kind(s): {sorted(kinds - EMITTED_KINDS)}"


def test_the_undecided_tiers_survive_the_conversion(sarif):
    """The point of the format conversion, as a test.

    `agent-judgable` becomes `open` and `out-of-artifact` becomes
    `notApplicable`. Counting them against the registry means a scenario that
    stops being reported fails here rather than quietly becoming a clean run.
    """
    scenarios = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["scenarios"]
    expected_open = sum(1 for s in scenarios if s["tier"] == "agent-judgable")
    expected_na = sum(1 for s in scenarios if s["tier"] == "out-of-artifact")

    results = sarif["runs"][0]["results"]
    assert sum(1 for r in results if r["kind"] == "open") == expected_open
    assert sum(1 for r in results if r["kind"] == "notApplicable") == expected_na

    # The static-detectable tier was previously unguarded: 42 of the 62 scenarios
    # were counted and the 20 that checks actually decide were not. Every shipped
    # check must appear as exactly one pass-or-fail row.
    decided = [r for r in results if r["kind"] in {"pass", "fail"}]
    ids = [r["ruleId"] for r in decided]
    assert len(ids) == len(set(ids)), "a check produced more than one decided row"
    assert decided, "no check reported a decided result"


def test_a_cleared_check_is_reported_as_pass_not_omitted(sarif):
    """Omitting cleared checks is how a report implies more coverage than it has."""
    results = sarif["runs"][0]["results"]
    assert any(r["kind"] == "pass" for r in results), "no check reported as pass"
    for r in results:
        if r["kind"] == "pass":
            assert r["level"] == "none"


def test_a_detection_carries_a_level_and_a_real_file_location(sarif):
    detections = [r for r in sarif["runs"][0]["results"] if r["kind"] == "fail"]
    assert detections, "the vulnerable fixture produced no detection"
    for r in detections:
        assert r["level"] in {"error", "warning"}
        uri = r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        assert (REPO_ROOT / uri).is_file(), f"{r['ruleId']} points at {uri!r}, which is not a file"


def test_no_detection_anywhere_in_the_corpus_cites_a_file_that_does_not_exist():
    """The single-fixture check above was fixture-lucky and missed a real defect.

    AST01's vulnerable fixture happens to produce evidence beginning with a real
    path, so asserting on it alone passed while `sarifLocation` was reading any
    dotted token as a filename -- `manifest.content_hash.value:` became an
    artifact. Measured over the whole corpus that was 60 of 138 detections
    pointing at nothing. GitHub cannot annotate a file it cannot resolve, and
    codeql-action refuses to fingerprint one, so this sweeps every fixture.
    """
    if subprocess.run(["node", "--version"], capture_output=True, check=False).returncode != 0:
        pytest.skip("node is not available")
    packages = [d for d in sorted(REPO_ROOT.glob("fixtures/AST*/*")) if (d / "SKILL.md").is_file()]
    assert packages, "no fixture packages found"
    dangling: list[str] = []
    detections = 0
    for pkg in packages:
        rel = pkg.relative_to(REPO_ROOT).as_posix()
        out = subprocess.run(
            ["node", str(CLI), "audit", rel, "--sarif"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if not out.stdout.strip():
            continue
        for result in json.loads(out.stdout)["runs"][0]["results"]:
            if result["kind"] != "fail":
                continue
            detections += 1
            uri = result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
            if not (REPO_ROOT / uri).is_file():
                dangling.append(f"{rel}: {result['ruleId']} -> {uri}")
    assert detections, "the corpus produced no detections at all"
    assert not dangling, f"{len(dangling)} of {detections} detections cite a non-file:\n  " + "\n  ".join(dangling[:5])


def test_an_artifact_signal_only_detection_is_a_warning_not_an_error():
    """`artifact-signal-only` fires on a precondition a benign package can show.

    Asserted over a package that actually produces such a row: on the AST01
    fixture this inspected zero results and passed vacuously.
    """
    if subprocess.run(["node", "--version"], capture_output=True, check=False).returncode != 0:
        pytest.skip("node is not available")
    seen = 0
    for pkg in sorted(REPO_ROOT.glob("fixtures/AST*/*")):
        if not (pkg / "SKILL.md").is_file():
            continue
        out = subprocess.run(
            ["node", str(CLI), "audit", pkg.relative_to(REPO_ROOT).as_posix(), "--sarif"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if not out.stdout.strip():
            continue
        for r in json.loads(out.stdout)["runs"][0]["results"]:
            if r["kind"] == "fail" and r["properties"]["covers"] != "full":
                seen += 1
                assert r["level"] == "warning", (
                    f"{r['ruleId']} covers {r['properties']['covers']}, which is not scenario "
                    "coverage, so it may not be reported at error level"
                )
    assert seen, "no artifact-signal-only detection anywhere in the corpus; this test proved nothing"


def test_every_result_resolves_to_a_declared_rule(sarif):
    run = sarif["runs"][0]
    declared = {rule["id"] for rule in run["tool"]["driver"]["rules"]}
    used = {r["ruleId"] for r in run["results"]}
    assert used <= declared, f"results cite undeclared rules: {sorted(used - declared)}"


def test_it_validates_against_the_published_sarif_schema(sarif):
    """Offline: the schema ships nowhere, so this runs only when it is cached."""
    schema = Path("/tmp/sarif-schema.json")
    if not schema.is_file():
        pytest.skip("SARIF schema not cached locally")
    jsonschema = pytest.importorskip("jsonschema")
    errors = list(jsonschema.Draft7Validator(json.loads(schema.read_text())).iter_errors(sarif))
    assert not errors, [f"{list(e.path)}: {e.message}" for e in errors[:3]]


def test_the_readme_documents_the_flag():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "--sarif" in readme, "README must document the --sarif flag"


def test_conformance_invariants_that_do_not_need_the_published_schema(sarif):
    """The schema test skips whenever the schema is not cached, which is always
    in CI, so the invariants a consumer actually depends on are asserted here
    unconditionally rather than resting on a test that does not run."""
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["informationUri"].startswith("https://")
    assert run["automationDetails"]["id"].endswith("/"), (
        "a trailing slash makes the whole string the analysis CATEGORY with an empty run id; "
        "without it GitHub splits the last segment off as a run id"
    )
    for r in run["results"]:
        assert r["kind"] in EMITTED_KINDS
        # SARIF: when kind is not "fail", level must be "none".
        if r["kind"] != "fail":
            assert r["level"] == "none", f"{r['ruleId']} is kind={r['kind']} at level={r['level']}"
        assert r["message"]["text"].strip(), f"{r['ruleId']} has an empty message"
        assert r["locations"], f"{r['ruleId']} has no location"
        uri = r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        assert uri and not uri.startswith("/"), f"{r['ruleId']} uri {uri!r} is not repository-relative"
        assert ".." not in uri, f"{r['ruleId']} uri {uri!r} escapes the tree"


def test_attacker_controlled_evidence_cannot_carry_control_characters(sarif):
    """Evidence is read out of a hostile package and lands in a document humans
    render. C0 controls, ANSI escapes and bidi overrides are stripped, and the
    text is bounded so one crafted file cannot inflate the report."""
    for r in sarif["runs"][0]["results"]:
        text = r["message"]["text"]
        assert not any(ord(c) < 32 and c not in "\t\n" for c in text), f"{r['ruleId']} carries a control character"
        assert not any("\u202a" <= c <= "\u202e" or "\u2066" <= c <= "\u2069" for c in text), (
            f"{r['ruleId']} carries a bidirectional override"
        )
        assert len(text) <= 1100, f"{r['ruleId']} message is {len(text)} chars; it should be bounded"
