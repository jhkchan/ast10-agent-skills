"""Tests for cli/lib/bridge.py -- the Python half of the CLI.

The Node CLI (`cli/bin/cli.js`) delegates its two DECISIONS to this module so
neither the whitepaper decision tree nor the detectors get a second
implementation in JavaScript. These tests cover the bridge directly, with no
Node involved:

  * the USF v1 -> detector-package shape adapter, including the shape
    mismatch skills/AST01/coverage-matrix.md records as coverage debt
    (`content_hash` is a string in the schema and a mapping in the detector);
  * the two package views an audit needs -- the declared shipped surface
    (`scripts/content_hash.py` SURFACE_GLOBS) for AST01's content-hash pair,
    every text file for the scanning detectors;
  * that `route` reports WHICH rule matched, not just where it routed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("ast10_cli_bridge", REPO_ROOT / "cli" / "lib" / "bridge.py")
assert _spec is not None and _spec.loader is not None
bridge = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = bridge
_spec.loader.exec_module(bridge)

from scripts.content_hash import content_sha256  # noqa: E402

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def write_package(root: Path, *, usf: dict | None = None, skill_md: str | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(
        skill_md
        if skill_md is not None
        else "---\nname: candidate\ndescription: a candidate under audit\n---\n\n# candidate\n",
        encoding="utf-8",
    )
    if usf is not None:
        (root / "skill.usf.yaml").write_text(yaml.safe_dump(usf), encoding="utf-8")
    return root


def findings_of(report: dict, category: str) -> dict[str, dict]:
    for entry in report["categories"]:
        if entry["category"] == category:
            return {f["scenario"]: f for f in entry["findings"]}
    raise AssertionError(f"{category} missing from the audit report")


# ---------------------------------------------------------------------------
# the shape adapter
# ---------------------------------------------------------------------------


def test_adapter_renests_usf_permissions_into_the_detector_shape():
    manifest, notes = bridge.adapt_manifest(
        {
            "description": "read-only triage",
            "permissions": {
                "files": {"read": ["./SKILL.md"], "write": [], "deny_write": ["SOUL.md"]},
                "network": {"allow": [], "deny": "*"},
                "shell": False,
            },
            "content_hash": "sha256:" + "a" * 64,
        }
    )
    assert manifest["permissions"]["deny_write"] == ["SOUL.md"]
    assert manifest["permissions"]["shell"] == {"allowed": False, "commands": []}
    assert manifest["permissions"]["network"] == {"policy": "deny-all", "allow": []}
    # The coverage-matrix'd shape mismatch: schema says string, detector wants
    # a mapping. The adapter is the translation, and it says so in `notes`.
    assert manifest["content_hash"] == {"algorithm": "sha256", "value": "a" * 64}
    assert any("content_hash" in note for note in notes)


def test_adapter_maps_a_populated_allowlist_to_allow_list_not_allow_all():
    manifest, _ = bridge.adapt_manifest(
        {"permissions": {"files": {"deny_write": []}, "network": {"allow": ["example.com"]}, "shell": False}}
    )
    assert manifest["permissions"]["network"]["policy"] == "allow-list"


def test_adapter_keeps_a_wildcard_allowlist_in_allow_list_mode():
    # AST05 draws a deliberate line between `policy == allow-all` and an
    # allow-list whose entries are unrestricted in practice. Collapsing `"*"`
    # into allow-all here would silently disarm the second detector.
    manifest, _ = bridge.adapt_manifest(
        {"permissions": {"files": {"deny_write": []}, "network": {"allow": ["*"]}, "shell": True}}
    )
    assert manifest["permissions"]["network"] == {"policy": "allow-list", "allow": ["*"]}
    assert manifest["permissions"]["shell"] == {"allowed": True, "commands": []}


def test_adapter_delegates_the_usf_semantics_to_the_one_translator():
    """There must be exactly one USF -> detector translator in the repo.

    `scripts/dogfood.py` owns it (it points these detectors at this repo's own
    skills). If the CLI ever grew a second copy, this equality is what breaks
    -- translating security metadata between two vocabularies is the AST10
    failure the repo is about, and two translators is two answers.
    """
    from scripts import dogfood

    usf_permissions = {
        "files": {"read": ["./SKILL.md"], "write": [], "deny_write": ["SOUL.md"]},
        "network": {"allow": ["example.com"], "deny": "*"},
        "shell": True,
        "tools": ["read_file"],
    }
    manifest, _ = bridge.adapt_manifest({"permissions": usf_permissions})
    assert manifest["permissions"] == dogfood.translate_permissions(usf_permissions)
    assert bridge.read_surface_files is not None


def test_adapter_reads_bare_boolean_frontmatter_permissions_explicitly():
    # `network: true` is not USF -- it is SKILL.md frontmatter shorthand. It
    # means unrestricted egress, and the adapter has to say so in the notes
    # rather than quietly downgrade it to "no declaration".
    open_manifest, open_notes = bridge.adapt_manifest({"permissions": {"network": True, "shell": True}})
    assert open_manifest["permissions"]["network"]["allow"] == ["*"]
    assert any("bare boolean" in note for note in open_notes)

    closed, _ = bridge.adapt_manifest({"permissions": {"network": False, "shell": False}})
    assert closed["permissions"]["network"] == {"policy": "deny-all", "allow": []}


def test_adapter_treats_a_malformed_content_hash_as_missing_not_as_mismatch():
    manifest, notes = bridge.adapt_manifest({"content_hash": "not-a-hash"})
    assert "content_hash" not in manifest
    assert any("missing" in note for note in notes)


def test_adapter_records_every_absent_field_rather_than_inventing_one():
    manifest, notes = bridge.adapt_manifest({})
    assert manifest == {}
    assert notes  # an empty declaration is reported, never treated as compliant


def test_adapter_passes_through_an_already_detector_shaped_manifest():
    raw = {
        "permissions": {
            "deny_write": ["MEMORY.md"],
            "shell": {"allowed": True, "commands": ["ls"]},
            "network": {"policy": "allow-all", "allow": []},
        },
        "content_hash": {"algorithm": "sha256", "value": "b" * 64},
    }
    manifest, _ = bridge.adapt_manifest(raw)
    assert manifest["permissions"]["shell"] == {"allowed": True, "commands": ["ls"]}
    assert manifest["permissions"]["network"]["policy"] == "allow-all"
    assert manifest["content_hash"]["value"] == "b" * 64


def test_frontmatter_is_parsed_with_safe_load_only(tmp_path):
    # A candidate under audit is untrusted input. The parser that reads it must
    # not be the unsafe loader AST04 exists to report.
    hostile = "---\nname: !!python/object/apply:os.system ['echo pwned']\n---\n"
    assert bridge.parse_frontmatter(hostile) is None


def test_frontmatter_returns_none_when_there_is_no_block():
    assert bridge.parse_frontmatter("# just a heading\n") is None


# ---------------------------------------------------------------------------
# the two package views
# ---------------------------------------------------------------------------


def test_surface_view_matches_the_vendored_content_hash_framing(tmp_path):
    package = write_package(tmp_path / "pkg")
    (package / "scripts").mkdir()
    (package / "scripts" / "run.py").write_text("print('hi')\n", encoding="utf-8")
    (package / "notes.txt").write_text("not part of the shipped surface\n", encoding="utf-8")

    surface = bridge.read_surface_files(package)
    assert sorted(surface) == ["SKILL.md", "scripts/run.py"]
    scan, _skipped = bridge.read_scan_files(package)
    assert "notes.txt" in scan  # the scanning detectors see everything


def test_a_correctly_hashed_package_reports_no_content_hash_finding(tmp_path):
    package = write_package(tmp_path / "pkg")
    digest = content_sha256(package)
    (package / "skill.usf.yaml").write_text(yaml.safe_dump({"content_hash": f"sha256:{digest}"}), encoding="utf-8")
    report = bridge.audit(str(package))
    ast01 = findings_of(report, "AST01")
    assert ast01["AST01-content-hash-missing"]["detected"] is False
    assert ast01["AST01-content-hash-mismatch"]["detected"] is False


def test_a_tampered_package_reports_a_content_hash_mismatch(tmp_path):
    package = write_package(tmp_path / "pkg")
    (package / "skill.usf.yaml").write_text(yaml.safe_dump({"content_hash": "sha256:" + "0" * 64}), encoding="utf-8")
    ast01 = findings_of(bridge.audit(str(package)), "AST01")
    assert ast01["AST01-content-hash-mismatch"]["detected"] is True


def test_scanning_detectors_see_files_outside_the_shipped_surface(tmp_path):
    package = write_package(tmp_path / "pkg")
    (package / "package.json").write_text('{"__proto__": {"polluted": true}}', encoding="utf-8")
    ast04 = findings_of(bridge.audit(str(package)), "AST04")
    finding = ast04["AST04-json-injection"]
    assert finding["detected"] is True
    assert "package.json" in finding["evidence"]


# ---------------------------------------------------------------------------
# audit as a whole
# ---------------------------------------------------------------------------


def test_audit_runs_every_category_and_names_the_ones_with_no_detector(tmp_path):
    report = bridge.audit(str(write_package(tmp_path / "pkg")))
    assert [c["category"] for c in report["categories"]] == list(bridge.CATEGORIES)
    no_detectors = {c["category"] for c in report["categories"] if c["status"] == "no-static-detectors"}
    # A category with no static detector is reported as such, never omitted --
    # an absent category is indistinguishable from a clean one.
    #
    # The membership of this set moves as detectors land, so it is not spelled out
    # as a literal any more. What is pinned instead is the invariant that made the
    # literal worth writing: a category reported as having no static detector must
    # be one the registry names no static-detectable scenario for. Reporting
    # "no detectors" for a category that owes one would read to an operator as
    # "nothing here is checkable", which is the exact confusion this repo exists
    # to remove.
    registry = yaml.safe_load((REPO_ROOT / "scenarios" / "registry.yaml").read_text(encoding="utf-8"))
    static_detectable = {s["category"] for s in registry["scenarios"] if s["tier"] == "static-detectable"}
    assert "AST09" in no_detectors, "AST09 has no static-detectable scenario; it must report no detectors"
    assert no_detectors.isdisjoint(static_detectable), (
        f"{sorted(no_detectors & static_detectable)} report no static detectors, but the "
        f"registry tiers at least one of their scenarios static-detectable"
    )
    for entry in report["categories"]:
        if entry["status"] == "no-static-detectors":
            assert entry["out_of_artifact"], entry["category"]


def test_audit_reports_every_check_including_the_ones_that_did_not_fire(tmp_path):
    report = bridge.audit(str(write_package(tmp_path / "pkg")))
    ran = [c for c in report["categories"] if c["status"] == "ran"]
    assert ran, "no category ran"
    for entry in ran:
        assert entry["findings"], entry["category"]
    assert report["totals"]["checks_run"] == sum(len(c["findings"]) for c in ran)


def test_audit_accepts_a_file_path_and_audits_its_package_directory(tmp_path):
    package = write_package(tmp_path / "pkg")
    from_dir = bridge.audit(str(package))
    from_file = bridge.audit(str(package / "SKILL.md"))
    assert from_file["path"] == from_dir["path"]


def test_audit_rejects_a_path_that_does_not_exist():
    with pytest.raises(bridge.BridgeError):
        bridge.audit("/definitely/not/a/skill/package")


def test_audit_of_this_repos_own_ast01_skill_uses_the_usf_manifest():
    report = bridge.audit(str(REPO_ROOT / "skills" / "AST01"))
    assert report["manifest_source"] == "skill.usf.yaml"
    assert len(report["surface_files"]) <= len(report["scan_files"])


# ---------------------------------------------------------------------------
# route
# ---------------------------------------------------------------------------


def test_route_reports_the_matched_rule_not_just_the_category():
    payload = bridge.route("the published skill contained a hidden payload")
    assert payload["ast_id"] == "AST01"
    assert payload["branch"] == 1
    assert payload["matched_phrase"] == "hidden payload"
    assert payload["matches"][0]["rule_order"] == 1
    assert payload["source"].endswith("triage.py")


def test_route_records_overlap_as_contributing_never_as_a_second_primary():
    payload = bridge.route(
        "a malicious skill with a hidden payload also evaded the scanner's natural-language detection"
    )
    assert payload["ast_id"] == "AST01"
    assert payload["contributing"] == ["AST08"]
    assert [m["ast_id"] for m in payload["matches"]] == ["AST01", "AST08"]


def test_route_never_claims_an_f1_contribution():
    assert bridge.route("typosquatted dependency")["f1_eligible"] is False


def test_route_rejects_an_empty_finding():
    with pytest.raises(bridge.BridgeError):
        bridge.route("   ")
