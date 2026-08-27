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
        assert (REPO_ROOT / uri).exists(), (
            f"{r['ruleId']} points at {uri!r}, which does not exist; GitHub resolves this "
            "against the repository root, so an unjoined package-relative path annotates "
            "the wrong file"
        )


def test_an_artifact_signal_only_detection_is_a_warning_not_an_error(sarif):
    """`artifact-signal-only` fires on a precondition a benign package can show."""
    for r in sarif["runs"][0]["results"]:
        if r["kind"] == "fail" and r["properties"]["covers"] != "full":
            assert r["level"] == "warning", f"{r['ruleId']} is not scenario coverage; it may not be an error"


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
