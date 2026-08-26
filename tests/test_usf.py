"""Tests for the Universal Skill Format (USF) v1.0 schema and validator (T-1.x).

Structure mirrors the two-layer split the deliverable is built on:

- ``schemas/usf-v1.schema.json`` owns SHAPE. The schema-valid / schema-invalid
  cases below pin exactly which malformations it catches.
- ``validators/usf.py`` owns SEMANTICS -- default-deny network precedence,
  deny_write-wins-over-write, no wildcards in permissions.files, identity-file
  protection, permission-derived risk_tier, and RFC 8785 canonicalization.

The last section asserts the eleven shipped manifests validate clean and stay
bound to the packages they describe.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from validators.usf import (
    IDENTITY_FILES,
    RISK_TIERS,
    SIGNATURE_STATE_MALFORMED,
    SIGNATURE_STATE_SIGNED,
    SIGNATURE_STATE_UNSIGNED,
    SIGNATURE_UNSIGNED,
    CanonicalizationError,
    UsfLoadError,
    canonicalize,
    compute_content_hash,
    derive_risk_tier,
    load_manifest,
    load_schema,
    loads_manifest,
    network_egress_allowed,
    schema_errors,
    semantic_errors,
    signature_state,
    signing_payload,
    update_content_hash,
    validate_manifest,
    validate_manifest_file,
    verify_signature,
    write_allowed,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"

#: The did:web identity every shipped manifest anchors to. Pinned here rather than read
#: back out of the manifests, because a test that derives the expected value from the file
#: under test cannot notice the file changing. The key that identity publishes, and the
#: agreement between the two, are checked offline in
#: ``tests/test_signing_anchor.py``.
SHIPPED_IDENTITY = "did:web:jhkchan.github.io"

SHIPPED_SKILLS = [
    "AST01",
    "AST02",
    "AST03",
    "AST04",
    "AST05",
    "AST06",
    "AST07",
    "AST08",
    "AST09",
    "AST10",
    "advisory",
]


def minimal_manifest(**overrides) -> dict:
    """A schema-valid, semantically-clean L0 manifest to mutate per-test."""
    manifest = {
        "name": "example-skill",
        "version": "1.0.0",
        "platforms": ["claude"],
        "description": "Safe example skill - concise, honest statement of function",
        "author": {"name": "Author Name"},
        "permissions": {
            "files": {
                "read": ["~/.config/app.json"],
                "write": [],
                "deny_write": list(IDENTITY_FILES),
            },
            "network": {"allow": [], "deny": "*"},
            "shell": False,
            "tools": ["read_file"],
        },
        "risk_tier": "L0",
        "scan_status": {
            "scanner": "none",
            "last_scanned": None,
            "result": "unscanned",
        },
        "signature": SIGNATURE_UNSIGNED,
        "content_hash": "sha256:" + "ab" * 32,
        "changelog": [{"version": "1.0.0", "date": "2026-02-01", "notes": "Initial release"}],
    }
    manifest.update(overrides)
    return manifest


def whitepaper_manifest() -> dict:
    """The whitepaper's own example manifest, transcribed field for field.

    This is the calibration case: whatever else the validator does, it must
    accept the format's reference example, and must derive the L1 tier the
    whitepaper assigns to exactly this permission set.
    """
    return {
        "name": "example-skill",
        "version": "1.0.0",
        "platforms": ["openclaw", "claude", "cursor", "vscode"],
        "description": "Safe example skill - concise, honest statement of function",
        "author": {
            "name": "Author Name",
            "identity": "did:web:example.com",
            "signing_key": "ed25519:" + "0a" * 32,
        },
        "permissions": {
            "files": {
                "read": ["~/.config/app.json"],
                "write": ["~/.config/app.json"],
                "deny_write": ["SOUL.md", "MEMORY.md", "AGENTS.md"],
            },
            "network": {"allow": ["api.example.com"], "deny": "*"},
            "shell": False,
            "tools": ["web_fetch", "read_file"],
        },
        "requires": {"binaries": ["jq", "curl"], "min_runtime_version": "2026.1.0"},
        "risk_tier": "L1",
        "scan_status": {
            "scanner": "snyk-agent-scan@1.4.0",
            "last_scanned": "2026-02-15",
            "result": "pass",
        },
        "signature": SIGNATURE_UNSIGNED,
        "content_hash": "sha256:" + "cd" * 32,
        "changelog": [{"version": "1.0.0", "date": "2026-02-01", "notes": "Initial release"}],
    }


# --------------------------------------------------------------------------- #
# Schema: shape
# --------------------------------------------------------------------------- #


def test_schema_is_a_valid_draft_2020_12_document():
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.Draft202012Validator.check_schema(load_schema())


def test_minimal_manifest_is_schema_valid():
    assert schema_errors(minimal_manifest()) == []


def test_whitepaper_example_manifest_is_schema_valid():
    assert schema_errors(whitepaper_manifest()) == []


def test_whitepaper_example_manifest_passes_semantic_validation():
    result = validate_manifest(whitepaper_manifest())
    assert result.ok, result.errors
    # The whitepaper assigns L1 to exactly this permission set.
    assert result.derived_risk_tier == "L1"


def _mutate(path: list[str], value):
    manifest = minimal_manifest()
    target = manifest
    for key in path[:-1]:
        target = target[key]
    if value is _DELETE:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return manifest


class _Delete:
    def __repr__(self):  # pragma: no cover - debug aid only
        return "<delete>"


_DELETE = _Delete()


SCHEMA_INVALID_CASES = [
    # required keys
    (["name"], _DELETE, "name"),
    (["version"], _DELETE, "version"),
    (["platforms"], _DELETE, "platforms"),
    (["permissions"], _DELETE, "permissions"),
    (["risk_tier"], _DELETE, "risk_tier"),
    (["signature"], _DELETE, "signature"),
    (["content_hash"], _DELETE, "content_hash"),
    (["changelog"], _DELETE, "changelog"),
    (["permissions", "files"], _DELETE, "files"),
    (["permissions", "shell"], _DELETE, "shell"),
    (["permissions", "files", "deny_write"], _DELETE, "deny_write"),
    (["permissions", "network", "allow"], _DELETE, "allow"),
    (["author", "name"], _DELETE, "name"),
    # enumerations
    (["risk_tier"], "L4", "L4"),
    (["risk_tier"], "low", "low"),
    # `platforms` is an OPEN list of runtime slugs, not a closed enumeration: the
    # whitepaper shows `platforms: [openclaw, claude, cursor, vscode]` as an example
    # array and defines no membership rule, so an unknown-but-well-formed slug like
    # "telepathy" is CONFORMANT and is not asserted against here. What the schema
    # still rejects is a malformed slug, which is what these three pin.
    (["platforms"], ["Claude"], "Claude"),
    (["platforms"], ["not a slug"], "not a slug"),
    (["platforms"], [""], "''"),
    (["platforms"], [], "[]"),
    (["scan_status", "result"], "maybe", "maybe"),
    # syntax
    (["version"], "1.0", "1.0"),
    (["version"], "v1.0.0", "v1.0.0"),
    (["content_hash"], "deadbeef", "deadbeef"),
    (["content_hash"], "sha256:XYZ", "sha256:XYZ"),
    (["content_hash"], "md5:" + "ab" * 16, "md5:"),
    (["signature"], "ed25519:nothex", "nothex"),
    (["signature"], "", "''"),
    (["signature"], "signed", "signed"),
    (["author", "signing_key"], "ed25519:short", "short"),
    (["author", "identity"], "example.com", "example.com"),
    (["name"], "Example-Skill", "Example-Skill"),
    # types
    (["permissions", "shell"], "false", "false"),
    (["permissions", "files", "read"], "~/.config/app.json", "~/.config/app.json"),
    (["description"], 42, "42"),
    # unknown keys are rejected: a typo'd `deny_writes` silently dropping
    # identity-file protection is the AST10/AST04 manifest failure itself.
    (["permissions", "files", "deny_writes"], ["SOUL.md"], "deny_writes"),
    (["totally_unknown"], "x", "totally_unknown"),
    # changelog entries are fully specified or absent
    (["changelog"], [{"version": "1.0.0", "date": "2026-02-01"}], "notes"),
    (["changelog"], [], "[]"),
    (
        ["changelog"],
        [{"version": "1.0.0", "date": "1 Feb 2026", "notes": "x"}],
        "1 Feb 2026",
    ),
]


@pytest.mark.parametrize(
    "path,value,needle",
    SCHEMA_INVALID_CASES,
    ids=[f"{'.'.join(p)}={n}" for p, _, n in SCHEMA_INVALID_CASES],
)
def test_schema_rejects_malformed_manifest(path, value, needle):
    errors = schema_errors(_mutate(path, value))
    assert errors, f"schema accepted {'.'.join(path)}={value!r}"
    assert any(needle in error for error in errors), errors


def test_schema_allows_vendor_extension_namespace():
    manifest = minimal_manifest()
    manifest["x-acme-review-ticket"] = "SEC-1234"
    assert schema_errors(manifest) == []


def test_scan_status_pass_requires_a_scan_date():
    manifest = minimal_manifest()
    manifest["scan_status"] = {
        "scanner": "snyk-agent-scan@1.4.0",
        "last_scanned": None,
        "result": "pass",
    }
    errors = schema_errors(manifest)
    assert errors and any("last_scanned" in error or "null" in error for error in errors)


def test_scan_status_unscanned_must_not_carry_a_scan_date():
    manifest = minimal_manifest()
    manifest["scan_status"] = {
        "scanner": "none",
        "last_scanned": "2026-02-15",
        "result": "unscanned",
    }
    errors = schema_errors(manifest)
    assert errors and any("last_scanned" in error for error in errors)


def test_scan_status_is_optional_but_its_absence_warns():
    manifest = minimal_manifest()
    del manifest["scan_status"]
    result = validate_manifest(manifest)
    assert result.ok, result.errors
    assert any("scan_status is absent" in warning for warning in result.warnings)


@pytest.mark.parametrize(
    "scan_status",
    [
        {
            "scanner": "snyk-agent-scan@1.4.0",
            "last_scanned": None,
            "result": "unscanned",
        },
        {"scanner": "none", "last_scanned": "2026-02-15", "result": "pass"},
    ],
)
def test_scan_status_scanner_and_result_must_agree(scan_status):
    manifest = minimal_manifest()
    manifest["scan_status"] = scan_status
    errors, _ = semantic_errors(manifest)
    assert any("scan_status" in error for error in errors), errors


# --------------------------------------------------------------------------- #
# Semantics: network default-deny precedence
# --------------------------------------------------------------------------- #


def test_only_allowlisted_hosts_get_egress_despite_deny_star():
    manifest = minimal_manifest()
    manifest["permissions"]["network"] = {"allow": ["api.example.com"], "deny": "*"}
    manifest["risk_tier"] = "L1"

    assert network_egress_allowed(manifest, "api.example.com") is True
    assert network_egress_allowed(manifest, "evil.example.com") is False


def test_deny_star_is_redundant_not_an_override():
    """Removing `deny: "*"` must not widen egress: the default is already deny."""
    with_deny = minimal_manifest()
    with_deny["permissions"]["network"] = {"allow": ["api.example.com"], "deny": "*"}
    without_deny = copy.deepcopy(with_deny)
    del without_deny["permissions"]["network"]["deny"]

    for host in ("api.example.com", "evil.example.com", "other.test"):
        assert network_egress_allowed(with_deny, host) == network_egress_allowed(without_deny, host)


def test_empty_allowlist_permits_nothing():
    manifest = minimal_manifest()
    assert manifest["permissions"]["network"]["allow"] == []
    assert network_egress_allowed(manifest, "api.example.com") is False
    assert network_egress_allowed(manifest, "localhost") is False


def test_allowlist_matching_is_host_only_no_wildcard_subdomains():
    manifest = minimal_manifest()
    manifest["permissions"]["network"]["allow"] = ["example.com"]
    manifest["risk_tier"] = "L1"

    assert network_egress_allowed(manifest, "example.com") is True
    assert network_egress_allowed(manifest, "api.example.com") is False
    assert network_egress_allowed(manifest, "EXAMPLE.COM") is True  # case-normalized


def test_deny_that_is_not_star_is_rejected_as_an_override_list():
    manifest = minimal_manifest()
    manifest["permissions"]["network"] = {
        "allow": ["api.example.com"],
        "deny": "internal.example.com",
    }
    manifest["risk_tier"] = "L1"

    errors, _ = semantic_errors(manifest)
    assert any("permissions.network.deny" in error for error in errors), errors
    assert any("default-deny" in error for error in errors), errors


def test_absent_deny_is_only_an_auditability_warning():
    manifest = minimal_manifest()
    del manifest["permissions"]["network"]["deny"]
    result = validate_manifest(manifest)
    assert result.ok, result.errors
    assert any("network.deny is absent" in warning for warning in result.warnings)


@pytest.mark.parametrize(
    "host,needle",
    [
        ("*.example.com", "wildcard"),
        ("https://api.example.com", "scheme"),
        ("api.example.com/v1", "path"),
        ("api.example.com:443", "port"),
        ("API.example.com", "lowercase"),
        ("not a host", "not a valid hostname"),
    ],
)
def test_network_allow_entries_must_be_bare_lowercase_hosts(host, needle):
    manifest = minimal_manifest()
    manifest["permissions"]["network"]["allow"] = [host]
    manifest["risk_tier"] = "L1"

    errors, _ = semantic_errors(manifest)
    assert any(needle in error for error in errors), errors


def test_network_capable_tool_with_empty_allowlist_warns():
    manifest = minimal_manifest()
    manifest["permissions"]["tools"] = ["read_file", "web_fetch"]
    result = validate_manifest(manifest)
    assert result.ok, result.errors
    assert any("web_fetch" in warning for warning in result.warnings)


# --------------------------------------------------------------------------- #
# Semantics: permissions.files -- explicit paths only
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("list_name", ["read", "write", "deny_write"])
@pytest.mark.parametrize(
    "path",
    ["~/.config/*.json", "src/**/*.py", "logs/?.txt", "conf/[abc].yaml", "a{b,c}.md"],
)
def test_wildcard_paths_are_rejected_in_every_files_list(list_name, path):
    manifest = minimal_manifest()
    manifest["permissions"]["files"][list_name] = [path]
    if list_name == "deny_write":
        manifest["permissions"]["files"]["deny_write"] = [path, *IDENTITY_FILES]
    if list_name == "write":
        manifest["risk_tier"] = "L1"

    errors, _ = semantic_errors(manifest)
    assert any(f"permissions.files.{list_name}" in error and "wildcard" in error for error in errors), errors


def test_traversal_segments_are_rejected():
    manifest = minimal_manifest()
    manifest["permissions"]["files"]["read"] = ["./config/../../etc/passwd"]
    errors, _ = semantic_errors(manifest)
    assert any("'..' segment" in error for error in errors), errors


def test_explicit_paths_are_accepted():
    manifest = minimal_manifest()
    manifest["permissions"]["files"]["read"] = [
        "~/.config/app.json",
        "./SKILL.md",
        "./.claude/settings.json",
        "/etc/hosts",
    ]
    result = validate_manifest(manifest)
    assert result.ok, result.errors


# --------------------------------------------------------------------------- #
# Semantics: deny_write wins, identity files protected
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("identity_file", IDENTITY_FILES)
def test_identity_file_missing_from_deny_write_is_an_error(identity_file):
    manifest = minimal_manifest()
    manifest["permissions"]["files"]["deny_write"] = [f for f in IDENTITY_FILES if f != identity_file]
    errors, _ = semantic_errors(manifest)
    assert any(identity_file in error and "deny_write" in error for error in errors), errors


@pytest.mark.parametrize("identity_file", IDENTITY_FILES)
def test_identity_file_may_be_explicitly_granted_in_write(identity_file):
    manifest = minimal_manifest()
    manifest["permissions"]["files"]["deny_write"] = [f for f in IDENTITY_FILES if f != identity_file]
    manifest["permissions"]["files"]["write"] = [identity_file]
    manifest["risk_tier"] = "L3"  # a granted identity write is destructive

    result = validate_manifest(manifest)
    assert result.ok, result.errors
    assert write_allowed(manifest, identity_file) is True


def test_identity_file_in_both_lists_is_denied_and_warns():
    manifest = minimal_manifest()
    manifest["permissions"]["files"]["write"] = ["MEMORY.md"]
    result = validate_manifest(manifest)

    assert result.ok, result.errors
    assert any("MEMORY.md" in warning and "deny_write wins" in warning for warning in result.warnings)
    assert write_allowed(manifest, "MEMORY.md") is False
    # ... and the shadowed grant is inert, so it does not inflate the derived tier.
    assert result.derived_risk_tier == "L0"


def test_deny_write_beats_write_for_the_same_path():
    manifest = minimal_manifest()
    manifest["permissions"]["files"]["write"] = ["./notes/output.md"]
    manifest["permissions"]["files"]["deny_write"] = [
        *IDENTITY_FILES,
        "./notes/output.md",
    ]
    assert write_allowed(manifest, "./notes/output.md") is False
    assert write_allowed(manifest, "notes/output.md") is False


def test_bare_filename_deny_write_protects_the_file_in_any_directory():
    manifest = minimal_manifest()
    manifest["permissions"]["files"]["write"] = ["./nested/dir/MEMORY.md"]
    manifest["risk_tier"] = "L1"
    assert write_allowed(manifest, "./nested/dir/MEMORY.md") is False


def test_unlisted_paths_are_denied_by_default():
    manifest = minimal_manifest()
    manifest["permissions"]["files"]["write"] = ["./allowed.md"]
    assert write_allowed(manifest, "./allowed.md") is True
    assert write_allowed(manifest, "./anything-else.md") is False


# --------------------------------------------------------------------------- #
# Semantics: risk_tier is an untrusted author assertion
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "permissions,expected",
    [
        (
            {
                "files": {
                    "read": ["./a.md"],
                    "write": [],
                    "deny_write": list(IDENTITY_FILES),
                },
                "network": {"allow": [], "deny": "*"},
                "shell": False,
            },
            "L0",
        ),
        (
            {
                "files": {
                    "read": [],
                    "write": ["./a.md"],
                    "deny_write": list(IDENTITY_FILES),
                },
                "network": {"allow": [], "deny": "*"},
                "shell": False,
            },
            "L1",
        ),
        (
            {
                "files": {"read": [], "write": [], "deny_write": list(IDENTITY_FILES)},
                "network": {"allow": ["api.example.com"], "deny": "*"},
                "shell": False,
            },
            "L1",
        ),
        (
            {
                "files": {"read": [], "write": [], "deny_write": list(IDENTITY_FILES)},
                "network": {"allow": [], "deny": "*"},
                "shell": True,
            },
            "L2",
        ),
        (
            {
                "files": {
                    "read": [],
                    "write": ["./a.md"],
                    "deny_write": list(IDENTITY_FILES),
                },
                "network": {"allow": [], "deny": "*"},
                "shell": True,
            },
            "L3",
        ),
        (
            {
                "files": {
                    "read": [],
                    "write": ["SOUL.md"],
                    "deny_write": ["MEMORY.md", "AGENTS.md"],
                },
                "network": {"allow": [], "deny": "*"},
                "shell": False,
            },
            "L3",
        ),
        (
            # A write entry that deny_write fully shadows grants nothing, so it
            # cannot raise the tier.
            {
                "files": {
                    "read": [],
                    "write": ["./out.md"],
                    "deny_write": [*IDENTITY_FILES, "./out.md"],
                },
                "network": {"allow": [], "deny": "*"},
                "shell": False,
            },
            "L0",
        ),
    ],
    ids=[
        "read-only",
        "write",
        "egress",
        "shell",
        "shell+write",
        "identity-grant",
        "shadowed-write",
    ],
)
def test_risk_tier_is_derived_from_the_declared_permission_set(permissions, expected):
    assert derive_risk_tier(permissions) == expected


def test_under_declared_risk_tier_is_an_error():
    manifest = minimal_manifest()
    manifest["permissions"]["shell"] = True
    manifest["risk_tier"] = "L0"  # spoofed: shell access is at least L2

    errors, _ = semantic_errors(manifest)
    assert any("risk_tier" in error and "L2 floor" in error for error in errors), errors


def test_over_declared_risk_tier_is_only_a_warning():
    manifest = minimal_manifest(risk_tier="L3")
    result = validate_manifest(manifest)
    assert result.ok, result.errors
    assert any("above the L0 floor" in warning for warning in result.warnings)


def test_every_risk_tier_letter_is_known():
    assert RISK_TIERS == ("L0", "L1", "L2", "L3")


# --------------------------------------------------------------------------- #
# Semantics: signature state and identity
# --------------------------------------------------------------------------- #


def test_unsigned_placeholder_is_a_state_not_an_error():
    manifest = minimal_manifest()
    result = validate_manifest(manifest)
    assert result.signature_state == SIGNATURE_STATE_UNSIGNED
    assert result.ok, result.errors
    assert not any("signature" in error for error in result.errors)


@pytest.mark.parametrize(
    "value",
    [None, "", "ed25519:", "ed25519:zz", "unsigned-for-now", "sha256:" + "ab" * 32],
)
def test_malformed_signature_is_reported_as_malformed(value):
    manifest = minimal_manifest()
    manifest["signature"] = value
    assert signature_state(manifest) == SIGNATURE_STATE_MALFORMED
    errors, _ = semantic_errors(manifest)
    assert any("signature" in error for error in errors), errors


def test_signed_manifest_without_a_public_key_is_an_error():
    manifest = minimal_manifest()
    manifest["signature"] = "ed25519:" + "ab" * 64
    assert signature_state(manifest) == SIGNATURE_STATE_SIGNED

    errors, _ = semantic_errors(manifest)
    assert any("author.signing_key" in error for error in errors), errors


def test_missing_identity_anchor_warns():
    result = validate_manifest(minimal_manifest())
    assert any("author.identity" in warning for warning in result.warnings)


def test_declared_version_must_appear_in_the_changelog():
    manifest = minimal_manifest(version="1.1.0")
    errors, _ = semantic_errors(manifest)
    assert any("changelog" in error and "1.1.0" in error for error in errors), errors


# --------------------------------------------------------------------------- #
# RFC 8785 (JCS) canonicalization
# --------------------------------------------------------------------------- #


def test_jcs_is_deterministic_across_key_insertion_order():
    a = {"z": 1, "a": {"y": 2, "b": [3, {"d": 4, "c": 5}]}}
    b = {"a": {"b": [3, {"c": 5, "d": 4}], "y": 2}, "z": 1}
    assert canonicalize(a) == canonicalize(b)
    assert canonicalize(a) == b'{"a":{"b":[3,{"c":5,"d":4}],"y":2},"z":1}'


def test_jcs_of_a_manifest_is_stable_across_reserialization():
    manifest = minimal_manifest()
    once = canonicalize(manifest)
    twice = canonicalize(json.loads(once.decode("utf-8")))
    assert once == twice


def test_jcs_has_no_insignificant_whitespace():
    blob = canonicalize({"a": [1, 2], "b": {"c": 3}}).decode("utf-8")
    assert blob == '{"a":[1,2],"b":{"c":3}}'
    assert " " not in blob


def test_jcs_output_is_utf8_bytes_with_literal_non_ascii():
    blob = canonicalize({"k": "café ☺"})
    assert isinstance(blob, bytes)
    assert blob == '{"k":"café ☺"}'.encode("utf-8")


def test_jcs_sorts_keys_by_utf16_code_unit_not_code_point():
    """U+1F600 is D83D DE00 in UTF-16, so it sorts before U+FB00 -- the opposite
    of Python's native code-point ordering. A canonicalizer that leaned on
    ``sorted()`` or ``json.dumps(sort_keys=True)`` would emit the other order and
    produce a signature no conforming verifier could reproduce."""
    payload = {"\U0001f600": 1, "ﬀ": 2}
    assert sorted(payload) == ["ﬀ", "\U0001f600"]  # code-point order
    assert canonicalize(payload) == '{"\U0001f600":1,"ﬀ":2}'.encode("utf-8")


def test_jcs_escapes_only_what_rfc8785_requires():
    value = 'quote" back\\ bs\b ff\f nl\n cr\r tab\t ctl\x01 keep-é'
    assert canonicalize({"s": value}) == (
        b'{"s":"quote\\" back\\\\ bs\\b ff\\f nl\\n cr\\r tab\\t ctl\\u0001 keep-' + "é".encode("utf-8") + b'"}'
    )


@pytest.mark.parametrize(
    "value,expected",
    [
        (0.0, b"0"),
        (-0.0, b"0"),
        (1.0, b"1"),
        (1.5, b"1.5"),
        (-1.5, b"-1.5"),
        (123.456, b"123.456"),
        (1e16, b"10000000000000000"),
        (1e20, b"100000000000000000000"),
        (1e21, b"1e+21"),
        (1e23, b"1e+23"),
        (1e-6, b"0.000001"),
        (1e-7, b"1e-7"),
        (5e-324, b"5e-324"),
        (1.7976931348623157e308, b"1.7976931348623157e+308"),
        (2.2250738585072014e-308, b"2.2250738585072014e-308"),
    ],
)
def test_jcs_numbers_use_ecmascript_number_to_string(value, expected):
    assert canonicalize(value) == expected


def test_jcs_integers_are_exact_and_bounded_by_the_double_range():
    assert canonicalize(2**53) == b"9007199254740992"
    assert canonicalize(-(2**53)) == b"-9007199254740992"
    with pytest.raises(CanonicalizationError, match=r"2\*\*53"):
        canonicalize(2**53 + 1)


def test_jcs_booleans_are_not_treated_as_integers():
    assert canonicalize({"a": True, "b": False, "c": 1, "d": 0}) == (b'{"a":true,"b":false,"c":1,"d":0}')


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_jcs_rejects_non_finite_numbers(value):
    with pytest.raises(CanonicalizationError):
        canonicalize(value)


def test_jcs_rejects_values_with_no_json_representation():
    with pytest.raises(CanonicalizationError):
        canonicalize({"d": {1, 2}})
    with pytest.raises(CanonicalizationError):
        canonicalize({1: "int key"})


def test_jcs_rejects_cycles():
    cyclic: list = []
    cyclic.append(cyclic)
    with pytest.raises(CanonicalizationError, match="cyclic"):
        canonicalize(cyclic)


# --------------------------------------------------------------------------- #
# Signing payload
# --------------------------------------------------------------------------- #


def test_signing_payload_excludes_signature_and_includes_content_hash():
    manifest = minimal_manifest()
    payload = signing_payload(manifest)
    assert b'"signature"' not in payload
    assert b'"content_hash":"sha256:' in payload


def test_signing_payload_is_independent_of_the_signature_value():
    unsigned = minimal_manifest()
    signed = minimal_manifest()
    signed["signature"] = "ed25519:" + "ab" * 64
    assert signing_payload(unsigned) == signing_payload(signed)


def test_signing_payload_changes_when_content_hash_changes():
    a = minimal_manifest()
    b = minimal_manifest(content_hash="sha256:" + "cd" * 32)
    assert signing_payload(a) != signing_payload(b)


def test_signing_payload_requires_content_hash():
    manifest = minimal_manifest()
    del manifest["content_hash"]
    with pytest.raises(Exception, match="content_hash"):
        signing_payload(manifest)


def test_signature_round_trips_over_the_jcs_payload():
    ed25519 = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes_raw()

    manifest = minimal_manifest()
    manifest["author"]["signing_key"] = "ed25519:" + public_bytes.hex()
    manifest["signature"] = "ed25519:" + private_key.sign(signing_payload(manifest)).hex()

    assert signature_state(manifest) == SIGNATURE_STATE_SIGNED
    assert verify_signature(manifest) is True

    # Key insertion order must not matter: the signature is over canonical bytes.
    reordered = dict(reversed(list(manifest.items())))
    assert verify_signature(reordered) is True

    # Any change to a covered field invalidates it.
    tampered = copy.deepcopy(manifest)
    tampered["permissions"]["shell"] = True
    assert verify_signature(tampered) is False


def test_verify_signature_refuses_to_pass_an_unsigned_manifest():
    with pytest.raises(Exception, match="not signed"):
        verify_signature(minimal_manifest())


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def test_loader_keeps_dates_as_strings_so_canonicalization_stays_possible():
    manifest = loads_manifest("name: x\nscan_status:\n  scanner: s\n  last_scanned: 2026-02-15\n  result: pass\n")
    assert manifest["scan_status"]["last_scanned"] == "2026-02-15"
    canonicalize(manifest)  # must not raise


def test_loader_rejects_a_non_mapping_document():
    with pytest.raises(UsfLoadError, match="must be a mapping"):
        loads_manifest("- a\n- b\n")


def test_loader_rejects_python_object_tags():
    with pytest.raises(UsfLoadError):
        loads_manifest("!!python/object/apply:os.system ['echo pwned']\n")


def test_load_manifest_reads_from_disk(tmp_path):
    path = tmp_path / "skill.usf.yaml"
    path.write_text('name: x\nversion: "1.0.0"\n', encoding="utf-8")
    assert load_manifest(path)["name"] == "x"


# --------------------------------------------------------------------------- #
# Binding to the package on disk
# --------------------------------------------------------------------------- #


def _fake_skill(tmp_path, name: str = "example-skill"):
    skill_dir = tmp_path / "example"
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\ndescription: d\n---\n\nbody\n", encoding="utf-8")
    (skill_dir / "scripts" / "detector.py").write_text("x = 1\n", encoding="utf-8")
    return skill_dir


def test_content_hash_mismatch_is_an_error(tmp_path):
    skill_dir = _fake_skill(tmp_path)
    manifest = minimal_manifest()
    errors, _ = semantic_errors(manifest, skill_dir=skill_dir)
    assert any("content_hash" in error for error in errors), errors

    manifest["content_hash"] = compute_content_hash(skill_dir)
    errors, _ = semantic_errors(manifest, skill_dir=skill_dir)
    assert not any("content_hash" in error for error in errors), errors


def test_manifest_name_must_match_the_platform_native_skill_md(tmp_path):
    skill_dir = _fake_skill(tmp_path, name="some-other-name")
    manifest = minimal_manifest(content_hash=compute_content_hash(skill_dir))
    errors, _ = semantic_errors(manifest, skill_dir=skill_dir)
    assert any("SKILL.md says" in error for error in errors), errors


def test_update_content_hash_rewrites_only_that_line(tmp_path):
    skill_dir = _fake_skill(tmp_path)
    manifest_path = skill_dir / "skill.usf.yaml"
    manifest_path.write_text(
        "# a comment worth keeping\n"
        "name: example-skill\n"
        "# content_hash.py defines the surface\n"
        'content_hash: "sha256:' + "00" * 32 + '"\n',
        encoding="utf-8",
    )
    old, new = update_content_hash(manifest_path)

    assert old == "sha256:" + "00" * 32
    assert new == compute_content_hash(skill_dir)
    text = manifest_path.read_text(encoding="utf-8")
    assert "# a comment worth keeping" in text
    assert "# content_hash.py defines the surface" in text
    assert f'content_hash: "{new}"' in text

    # Idempotent.
    assert update_content_hash(manifest_path) == (new, new)


# --------------------------------------------------------------------------- #
# The eleven shipped manifests
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("skill", SHIPPED_SKILLS)
def test_shipped_manifest_exists(skill):
    assert (SKILLS_DIR / skill / "skill.usf.yaml").is_file()


def test_every_skill_directory_ships_a_manifest():
    on_disk = sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir())
    assert on_disk == sorted(SHIPPED_SKILLS)


@pytest.mark.parametrize("skill", SHIPPED_SKILLS)
def test_shipped_manifest_validates(skill):
    result = validate_manifest_file(SKILLS_DIR / skill / "skill.usf.yaml")
    assert result.ok, result.errors


@pytest.mark.parametrize("skill", SHIPPED_SKILLS)
def test_shipped_manifest_content_hash_matches_the_package_on_disk(skill):
    skill_dir = SKILLS_DIR / skill
    manifest = load_manifest(skill_dir / "skill.usf.yaml")
    assert manifest["content_hash"] == compute_content_hash(skill_dir), (
        f"{skill}: content_hash is stale. Regenerate with "
        f"`python3 validators/usf.py --update-content-hash skills/{skill}/skill.usf.yaml`"
    )


@pytest.mark.parametrize("skill", SHIPPED_SKILLS)
def test_shipped_manifest_is_signed_and_anchored(skill):
    """The eleven are signed, and this is the assertion that keeps saying so.

    It replaces ``test_shipped_manifest_is_explicitly_unsigned``, which pinned the
    unsigned placeholder so that signing this repository could not happen by accident.
    That test's premise is now false, and the successor is a SUPERSET of what it
    guaranteed: it still fixes the exact signature state, and it additionally requires a
    real ``ed25519:<128 hex>`` value, both anchor fields, and a signature that actually
    verifies over this manifest's own RFC 8785 payload. "Signed" as a bare string would
    be weaker than the unsigned pin it replaces -- `signature: "ed25519:" + "00" * 64`
    would satisfy it -- so nothing here settles for the shape alone.

    What it still does not claim: that any of this makes the skill safe. That is
    ``author.identity``'s own comment in every manifest, and this repository's AST01
    rule -- a verified signature answers "who published this", never "is this safe".
    """
    path = SKILLS_DIR / skill / "skill.usf.yaml"
    result = validate_manifest_file(path)
    assert result.signature_state == SIGNATURE_STATE_SIGNED
    assert result.ok, result.errors

    manifest = load_manifest(path)
    assert re.fullmatch(r"ed25519:[0-9a-f]{128}", manifest["signature"]), manifest["signature"]

    author = manifest["author"]
    assert author.get("identity") == SHIPPED_IDENTITY
    assert re.fullmatch(r"ed25519:[0-9a-f]{64}", author.get("signing_key") or ""), author.get("signing_key")

    # Over its own JCS payload, against the key the manifest carries -- and again against
    # that key passed in explicitly, so a verifier that ignored its argument is caught.
    assert verify_signature(manifest) is True
    assert verify_signature(manifest, public_key_hex=author["signing_key"]) is True


@pytest.mark.parametrize("skill", SHIPPED_SKILLS)
def test_shipped_signature_does_not_survive_a_change_to_the_package_it_covers(skill):
    """The other half of the claim above: the signature is bound to THESE bytes.

    A signature that verified over a manifest it no longer describes would be the false
    trust signal AST10 is about, so the binding is asserted rather than assumed. The
    manifest on disk is never touched; the tampering happens on the loaded dict.
    """
    manifest = load_manifest(SKILLS_DIR / skill / "skill.usf.yaml")

    tampered = copy.deepcopy(manifest)
    tampered["permissions"]["shell"] = True
    assert verify_signature(tampered) is False

    # The content_hash is inside the signed payload, so a swapped package fails too.
    restamped = copy.deepcopy(manifest)
    restamped["content_hash"] = "sha256:" + "00" * 32
    assert verify_signature(restamped) is False

    # And the anchor is inside it: the signature cannot be moved to another publisher.
    moved = copy.deepcopy(manifest)
    moved["author"]["identity"] = "did:web:evil.example"
    assert verify_signature(moved) is False


@pytest.mark.parametrize("skill", SHIPPED_SKILLS)
def test_shipped_manifest_requests_no_shell_and_no_network(skill):
    """These are read-only detectors. An honest manifest asks for nothing more."""
    manifest = load_manifest(SKILLS_DIR / skill / "skill.usf.yaml")
    permissions = manifest["permissions"]
    assert permissions["shell"] is False
    assert permissions["network"]["allow"] == []
    assert permissions["files"]["write"] == []
    assert network_egress_allowed(manifest, "api.anthropic.com") is False


@pytest.mark.parametrize("skill", SHIPPED_SKILLS)
def test_shipped_manifest_denies_writes_to_every_identity_file(skill):
    manifest = load_manifest(SKILLS_DIR / skill / "skill.usf.yaml")
    for identity_file in IDENTITY_FILES:
        assert identity_file in manifest["permissions"]["files"]["deny_write"]
        assert write_allowed(manifest, identity_file) is False


@pytest.mark.parametrize("skill", SHIPPED_SKILLS)
def test_shipped_manifest_risk_tier_matches_its_derived_floor(skill):
    manifest = load_manifest(SKILLS_DIR / skill / "skill.usf.yaml")
    assert manifest["risk_tier"] == derive_risk_tier(manifest["permissions"]) == "L0"


@pytest.mark.parametrize("skill", SHIPPED_SKILLS)
def test_shipped_manifest_name_matches_its_skill_md(skill):
    skill_dir = SKILLS_DIR / skill
    manifest = load_manifest(skill_dir / "skill.usf.yaml")
    frontmatter_name = None
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    for line in text.splitlines()[1:]:
        if line.startswith("---"):
            break
        if line.startswith("name:"):
            frontmatter_name = line.split(":", 1)[1].strip()
            break
    assert manifest["name"] == frontmatter_name


@pytest.mark.parametrize("skill", SHIPPED_SKILLS)
def test_shipped_manifest_canonicalizes_deterministically(skill):
    path = SKILLS_DIR / skill / "skill.usf.yaml"
    assert canonicalize(load_manifest(path)) == canonicalize(load_manifest(path))


def test_shipped_manifests_are_distinguishable_by_content_hash():
    hashes = {skill: load_manifest(SKILLS_DIR / skill / "skill.usf.yaml")["content_hash"] for skill in SHIPPED_SKILLS}
    assert len(set(hashes.values())) == len(hashes), hashes
