"""End-to-end tests for `cli/bin/cli.js`, the zero-dependency Node CLI.

Every test shells out to the real binary and asserts on what an operator
actually sees. Two kinds of assertion matter here:

  * SHAPE -- each subcommand exits 0 and prints the sections it promises.
  * AGREEMENT -- the CLI reads `scenarios/registry.yaml`,
    `fixtures/manifest.yaml` and `config/audit.yml` with narrow line scanners
    instead of a YAML library, because it ships with no runtime dependencies.
    The tests below re-derive the same numbers with PyYAML and fail on any
    disagreement, so that shortcut can never drift into wrong output.

Skipped, not failed, when Node is absent: the Python side of this repo must
stay testable on a machine with no JavaScript runtime.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "bin" / "cli.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed; the Node CLI cannot be exercised")

TIERS = ("static-detectable", "agent-judgable", "out-of-artifact")
AST_IDS = tuple(f"AST{n:02d}" for n in range(1, 11))


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Invoke the CLI the way a user would, pinned to this interpreter.

    AST10_PYTHON keeps `route` and `audit` on the interpreter running the test
    suite, so the bridge always has the same PyYAML the tests do.
    """
    env = dict(os.environ)
    env["AST10_PYTHON"] = sys.executable
    return subprocess.run(
        [NODE, str(CLI), *args],
        cwd=str(cwd or REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def run_json(*args: str) -> object:
    result = run_cli(*args, "--json")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def load_detector_tiers(category: str) -> dict[str, str]:
    """A category's declared tiers, straight from the module the CLI parses."""
    path = REPO_ROOT / "skills" / category / "scripts" / "detector.py"
    spec = importlib.util.spec_from_file_location(f"tiercheck_{category}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return dict(module.SCENARIO_TIERS)


# ---------------------------------------------------------------------------
# packaging
# ---------------------------------------------------------------------------


def test_package_json_exposes_the_bin_and_declares_no_runtime_dependencies():
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["bin"]["ast10-skills"] == "cli/bin/cli.js"
    assert (REPO_ROOT / package["bin"]["ast10-skills"]).is_file()
    assert package["type"] == "module"
    assert package.get("dependencies", {}) == {}
    # The repo name contains "owasp"; the package metadata has to carry the
    # non-endorsement disclaimer wherever the name travels.
    assert "NOT an OWASP project" in package["description"]


def test_cli_is_executable_without_installing_anything():
    assert run_cli("help").returncode == 0


# ---------------------------------------------------------------------------
# help
# ---------------------------------------------------------------------------


def test_help_lists_every_subcommand_and_the_non_endorsement_disclaimer():
    result = run_cli("help")
    assert result.returncode == 0
    for command in ("list", "route", "audit", "coverage", "status"):
        assert command in result.stdout
    assert "NOT an OWASP project" in result.stdout


def test_unknown_command_exits_non_zero():
    assert run_cli("frobnicate").returncode != 0


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_prints_all_eleven_skills_with_ast_id_and_description():
    result = run_cli("list")
    assert result.returncode == 0
    assert "11 skills" in result.stdout
    for ast_id in AST_IDS:
        assert ast_id in result.stdout
    assert "advisory" in result.stdout


def test_list_json_carries_one_line_descriptions_from_the_frontmatter():
    rows = run_json("list")
    assert len(rows) == 11
    by_id = {row["id"]: row for row in rows}
    assert set(by_id) == {*AST_IDS, "advisory"}
    for row in rows:
        assert row["description"], row["id"]
        assert "\n" not in row["description"]
        frontmatter_name = yaml.safe_load(
            (REPO_ROOT / "skills" / row["id"] / "SKILL.md").read_text(encoding="utf-8").split("---\n")[1]
        )["name"]
        assert row["name"] == frontmatter_name


@pytest.mark.parametrize("tier", TIERS)
def test_list_tier_filter_matches_what_the_detector_modules_declare(tier):
    """`--tier` claims to filter by what a skill can decide. The authority for
    that claim is each detector module's own SCENARIO_TIERS table -- so the
    filter's output must equal what importing those modules says."""
    expected = {category for category in AST_IDS if tier in load_detector_tiers(category).values()}
    rows = run_json("list", "--tier", tier)
    assert {row["id"] for row in rows} == expected
    for row in rows:
        assert row["tier_counts"][tier] > 0


def test_list_tier_filter_excludes_the_advisory_router_from_every_tier():
    # The advisory skill decides no scenario; it routes. Listing it under a
    # detectability tier would be a coverage claim it does not make.
    for tier in TIERS:
        assert all(row["id"] != "advisory" for row in run_json("list", "--tier", tier))


def test_list_rejects_an_unknown_tier():
    result = run_cli("list", "--tier", "mostly-detectable")
    assert result.returncode != 0
    assert "static-detectable" in result.stderr


# ---------------------------------------------------------------------------
# route
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("finding", "ast_id", "branch"),
    [
        ("the published skill contained a hidden payload", "AST01", 1),
        ("a typosquatted package reached the registry unsigned", "AST02", 2),
        ("the manifest metadata has a deceptive description", "AST04", 3),
        ("the scanner missed an obfuscated instruction", "AST08", 4),
    ],
)
def test_route_follows_the_whitepaper_decision_tree_ordering(finding, ast_id, branch):
    payload = run_json("route", finding)
    assert payload["ast_id"] == ast_id
    assert payload["branch"] == branch
    assert payload["matched_phrase"] in finding.lower()


def test_route_prints_the_matched_rule_so_the_routing_is_auditable():
    result = run_cli("route", "the scanner missed an obfuscated instruction")
    assert result.returncode == 0
    assert "AST08" in result.stdout
    assert "decision-tree branch 4" in result.stdout
    assert "Matched phrase:" in result.stdout
    assert "skills/advisory/scripts/triage.py" in result.stdout


def test_route_labels_an_extended_rule_as_such_not_as_a_numbered_branch():
    # AST03/05/06/07/09/10 are not among the four branches the whitepaper's
    # tree numbers. Printing a branch number for them would overstate what the
    # source document says.
    result = run_cli("route", "skills execute with full host file system access, no sandbox")
    assert result.returncode == 0
    assert "AST06" in result.stdout
    assert "extended rule" in result.stdout
    assert "decision-tree branch" not in result.stdout
    assert result.stdout.count("extended rule —") == 1


def test_route_records_overlap_as_contributing_not_as_a_second_primary():
    result = run_cli(
        "route",
        "a malicious skill with a hidden payload also evaded the scanner's natural-language detection",
    )
    assert result.returncode == 0
    assert "Primary category: AST01" in result.stdout
    assert "Contributing control failures" in result.stdout
    assert "AST08" in result.stdout


def test_route_escalates_instead_of_guessing_when_nothing_matches():
    result = run_cli("route", "the office printer is out of toner")
    assert result.returncode == 0
    assert "no decision-tree branch matched" in result.stdout
    assert "manual triage" in result.stdout


def test_route_needs_a_finding():
    assert run_cli("route").returncode != 0


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


def test_audit_groups_findings_by_category_over_every_ast():
    result = run_cli("audit", "fixtures/AST01/V1-obfuscated-payload")
    assert result.returncode == 0, result.stderr
    for ast_id in AST_IDS:
        assert ast_id in result.stdout
    assert "Summary:" in result.stdout
    assert "no static detectors" in result.stdout


def test_audit_json_reports_every_check_and_names_the_undetectable_categories():
    payload = run_json("audit", "fixtures/AST01/V1-obfuscated-payload")
    assert [c["category"] for c in payload["categories"]] == list(AST_IDS)
    assert payload["totals"]["checks_run"] > 0
    assert payload["totals"]["categories_without_detectors"] == 4
    ast01 = next(c for c in payload["categories"] if c["category"] == "AST01")
    scenarios = {f["scenario"]: f for f in ast01["findings"]}
    assert scenarios["AST01-content-hash-missing"]["detected"] is True
    # Every finding carries its tier, so a reader can tell a static check from
    # a judged one without leaving the output.
    for entry in payload["categories"]:
        for finding in entry["findings"]:
            assert finding["tier"] in TIERS


def test_audit_prints_the_manifest_adapter_trail(tmp_path):
    payload = run_json("audit", str(REPO_ROOT / "skills" / "AST01"))
    assert payload["manifest_source"] == "skill.usf.yaml"
    assert any("deny_write" in note for note in payload["adapter_notes"])


def test_audit_fail_on_detect_exits_one_only_when_something_fired(tmp_path):
    package = tmp_path / "clean"
    package.mkdir()
    (package / "SKILL.md").write_text("---\nname: clean\n---\n\n# clean\n", encoding="utf-8")
    digest = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys;sys.path.insert(0,sys.argv[1]);"
            "from pathlib import Path;from scripts.content_hash import content_sha256;"
            "print(content_sha256(Path(sys.argv[2])))",
            str(REPO_ROOT),
            str(package),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    (package / "skill.usf.yaml").write_text(
        yaml.safe_dump(
            {
                "content_hash": f"sha256:{digest}",
                "permissions": {
                    "files": {"read": [], "write": [], "deny_write": ["SOUL.md"]},
                    "network": {"allow": []},
                    "shell": False,
                },
            }
        ),
        encoding="utf-8",
    )
    clean = run_cli("audit", str(package), "--fail-on-detect")
    assert clean.returncode == 0, clean.stdout

    vulnerable = run_cli("audit", "fixtures/AST01/V1-obfuscated-payload", "--fail-on-detect")
    assert vulnerable.returncode == 1


def test_audit_reports_a_missing_package_instead_of_crashing():
    result = run_cli("audit", "does/not/exist")
    assert result.returncode == 2
    assert "no such skill package" in result.stderr


# ---------------------------------------------------------------------------
# coverage
# ---------------------------------------------------------------------------


def test_coverage_prints_per_category_tier_counts_and_the_no_f1_reasons():
    result = run_cli("coverage")
    assert result.returncode == 0
    for ast_id in AST_IDS:
        assert ast_id in result.stdout
    assert "declared-and-uncovered" in result.stdout
    assert "pending-detector" in result.stdout


def test_coverage_numbers_agree_with_the_registry_read_through_pyyaml():
    """The CLI scans scenarios/registry.yaml with a line matcher because it has
    no YAML dependency. This is the guard that the shortcut stays correct."""
    registry = yaml.safe_load((REPO_ROOT / "scenarios" / "registry.yaml").read_text())
    expected: dict[str, dict[str, int]] = {}
    for scenario in registry["scenarios"]:
        bucket = expected.setdefault(scenario["category"], {t: 0 for t in TIERS})
        bucket[scenario["tier"]] += 1

    payload = run_json("coverage")
    rows = {row["category"]: row for row in payload["categories"]}
    for category, counts in expected.items():
        row = rows[category]
        assert row["static_detectable"] == counts["static-detectable"], category
        assert row["agent_judgable"] == counts["agent-judgable"], category
        assert row["out_of_artifact"] == counts["out-of-artifact"], category
        assert row["scenarios"] == sum(counts.values()), category
    assert payload["totals"]["scenarios"] == len(registry["scenarios"])


def test_coverage_f1_state_agrees_with_the_fixture_manifest():
    manifest = yaml.safe_load((REPO_ROOT / "fixtures" / "manifest.yaml").read_text())
    categories = manifest["categories"]
    payload = run_json("coverage")
    rows = {row["category"]: row for row in payload["categories"]}
    for category, entry in categories.items():
        row = rows[category]
        assert row["fixture_cases"] == len(entry.get("cases") or []), category
        assert row["labeled_detectable_checks"] == len(entry.get("detectable_scenarios") or []), category
        assert row["status"] == entry["status"], category
        published = entry.get("published_f1")
        if published is None:
            # Empty detectable tier: no F1 at all, and the corpus is never
            # padded to manufacture one.
            assert row["publishes_f1"] is False
            assert row["no_f1_reason"] == "empty-detectable-tier"
        elif published == "pending-detector":
            assert row["publishes_f1"] is False
            assert row["no_f1_reason"] == "no-detector-consumes-corpus"
        else:
            assert row["publishes_f1"] is True


def test_coverage_distinguishes_the_two_reasons_a_category_publishes_no_f1():
    payload = run_json("coverage")
    reasons = {row["category"]: row["no_f1_reason"] for row in payload["categories"]}
    assert reasons["AST02"] == "empty-detectable-tier"
    assert reasons["AST01"] == "no-detector-consumes-corpus"
    assert len(payload["categories_without_f1"]) == sum(1 for row in payload["categories"] if not row["publishes_f1"])


def test_the_node_cli_and_the_python_cli_report_the_same_numbers():
    """Two entry points, one set of manifests.

    `cli/ast10.py status` and `cli/bin/cli.js coverage` answer the same
    question in two languages. Whichever a reader runs, the per-category
    tiers, corpus size and F1 state must be identical -- a CLI that disagrees
    with its sibling is the stale-declaration shape this repo is about.
    """
    python_cli = REPO_ROOT / "cli" / "ast10.py"
    if not python_cli.is_file():  # pragma: no cover - the sibling CLI is optional
        pytest.skip("cli/ast10.py is not present")
    result = subprocess.run(
        [sys.executable, str(python_cli), "status", "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    python_rows = {row["category"]: row for row in json.loads(result.stdout)}
    node_rows = {row["category"]: row for row in run_json("coverage")["categories"]}
    assert set(python_rows) == set(node_rows)
    for category, expected in python_rows.items():
        actual = node_rows[category]
        assert actual["static_detectable"] == expected["registry_static_detectable"]
        assert actual["agent_judgable"] == expected["registry_agent_judgable"]
        assert actual["out_of_artifact"] == expected["registry_out_of_artifact"]
        assert actual["fixture_cases"] == expected["cases"]
        assert actual["labeled_detectable_checks"] == expected["labeled_detectable"]
        assert actual["status"] == expected["status"]
        assert actual["f1"] == expected["f1"]


def test_both_clis_route_a_finding_through_the_same_decision_tree():
    python_cli = REPO_ROOT / "cli" / "ast10.py"
    if not python_cli.is_file():  # pragma: no cover - the sibling CLI is optional
        pytest.skip("cli/ast10.py is not present")
    finding = "the scanner missed an obfuscated instruction"
    result = subprocess.run(
        [sys.executable, str(python_cli), "route", finding],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ast_id"] == run_json("route", finding)["ast_id"]


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status_reports_skills_commands_fixtures_and_scorecards():
    result = run_cli("status")
    assert result.returncode == 0
    for label in ("Skills", "Commands", "Fixtures", "Scorecards", "Judge providers"):
        assert label in result.stdout


def test_status_counts_match_the_repository_on_disk():
    payload = run_json("status")
    assert payload["skills"]["total"] == 11
    assert payload["skills"]["detectors"] == 10
    assert payload["skills"]["with_detector_module"] == len(
        [p for p in (REPO_ROOT / "skills").glob("*/scripts/detector.py")]
    )
    on_disk = sum(
        1
        for category in (REPO_ROOT / "fixtures").glob("AST*")
        for case in category.iterdir()
        if case.is_dir() and not case.name.startswith((".", "__"))
    )
    assert payload["fixtures"]["case_directories"] == on_disk


def test_status_counts_namespaced_slash_commands():
    """`Commands` must count `commands/<namespace>/*.md`, not just the top level.

    Slash commands are addressed through their directory namespace --
    `commands/ast/audit-ast01.md` is `/ast:audit-ast01` -- so every command this
    repo ships lives one level down. A top-level-only scan reported 0 for a
    repository shipping 14, which reads as "no command surface" rather than as a
    counting bug. Re-derived from disk here so the CLI cannot drift from it.
    """
    on_disk = sorted(
        p.relative_to(REPO_ROOT).as_posix()
        for root in (REPO_ROOT / "commands", REPO_ROOT / ".claude-plugin" / "commands")
        if root.is_dir()
        for p in root.rglob("*.md")
        if not any(part.startswith(".") or part == "__pycache__" for part in p.relative_to(root).parts)
    )
    assert on_disk, "no command files on disk — this test would be vacuous"
    payload = run_json("status")
    assert payload["commands"]["total"] == len(on_disk)

    result = run_cli("status")
    assert result.returncode == 0
    assert re.search(rf"^Commands\s+{len(on_disk)}\b", result.stdout, re.MULTILINE), (
        f"human-readable status must print the same command count as --json ({len(on_disk)})"
    )


def test_status_flags_fixture_directories_no_f1_denominator_can_see():
    manifest = yaml.safe_load((REPO_ROOT / "fixtures" / "manifest.yaml").read_text())
    payload = run_json("status")
    reported = {row["category"]: row for row in payload["fixtures"]["unlabeled"]}
    for category, entry in manifest["categories"].items():
        directory = REPO_ROOT / "fixtures" / category
        on_disk = (
            len([p for p in directory.iterdir() if p.is_dir() and not p.name.startswith((".", "__"))])
            if directory.is_dir()
            else 0
        )
        labeled = len(entry.get("cases") or [])
        if on_disk and on_disk != labeled:
            assert reported[category]["on_disk"] == on_disk
            assert reported[category]["labeled"] == labeled
        else:
            assert category not in reported


def test_status_declares_every_unavailable_provider_with_its_recorded_reason():
    audit = yaml.safe_load((REPO_ROOT / "config" / "audit.yml").read_text())
    declared = {
        name: entry for name, entry in (audit.get("providers") or {}).items() if entry.get("status") == "unavailable"
    }
    payload = run_json("status")
    reported = {p["name"]: p for p in payload["providers"]["declared_unavailable"]}
    assert set(reported) == set(declared)
    for name, entry in declared.items():
        assert reported[name]["status"] == "unavailable"
        # The reason is the whole point of declare-or-skip: it must survive
        # into the CLI output rather than being reduced to a boolean.
        assert reported[name]["reason"].split()[0] in entry["reason"]
    assert payload["providers"]["runtime_audit_entries"] == len(audit.get("runtime_entries") or [])


def test_status_lists_every_live_adapter_model_from_the_adapter_modules():
    bedrock = (REPO_ROOT / "adapters" / "bedrock.py").read_text(encoding="utf-8")
    payload = run_json("status")
    names = {a["name"] for a in payload["providers"]["live"]}
    for model in ("gpt-oss-120b", "qwen3-235b", "deepseek-v3.2", "nova-pro"):
        assert f"bedrock/{model}" in names
        assert model in bedrock
    assert any(name.startswith("claude-cli/") for name in names)
    assert any(name.startswith("anthropic-compatible/") for name in names)
    for adapter in payload["providers"]["live"]:
        assert isinstance(adapter["configured"], bool)
        assert adapter["detail"]
