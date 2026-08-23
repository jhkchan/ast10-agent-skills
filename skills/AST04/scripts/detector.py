"""AST04 -- Insecure Metadata detector.

`scenarios/registry.yaml` tiers five of AST04's seven named scenarios
static-detectable, and this module now implements one check per scenario:

======================  =====================================================
Registry scenario       Check
======================  =====================================================
AST04-S02 Permission     ``detect_permission_understating`` -- an egress call
Understating             site in a bundled script whose destination host the
                         manifest's ``permissions.network.allow`` does not
                         permit.
AST04-S03 Risk Tier      ``detect_risk_tier_spoofing`` -- the declared
Spoofing                 ``risk_tier`` against the floor
                         ``validators/usf.py::derive_risk_tier`` computes from
                         the declared permission set.
AST04-S04 YAML Code      ``detect_yaml_injection`` -- the dangerous tag in
Execution                shipped YAML (or a SKILL.md frontmatter block) and the
                         unsafe-loader opt-in in bundled Python.
AST04-S06 JSON           ``detect_json_injection`` -- a prototype-pollution key
Prototype Pollution      in a shipped JSON file, with any in-package recursive
                         merge reported as corroborating evidence.
AST04-S07 TOML / Config  ``detect_toml_injection`` -- a redefined table
Injection                (precedence violation) or a top-level key outside the
                         schema allowlist.
======================  =====================================================

``detect_invisible_unicode_smuggling`` is the sixth check and maps to no named
AST04 scenario: it derives from the category's preventive-mitigation list
("flag suspicious patterns ... specifically ASCII smuggling, base64 payloads,
and zero-width characters invisible to human reviewers") and is declared
``category-precondition``. AST04-S01 (Brand Impersonation) is agent-judgable and
AST04-S05 (Staged Loader) out-of-artifact; neither has a check, by tier.

SECURITY NOTE
-------------
This module NEVER calls ``yaml.load()``/``UnsafeLoader`` on scanned content --
that would execute the very injection it exists to catch. YAML detection is raw
text scanning; JSON and TOML are parsed with ``json``/``tomllib``, which have no
code-execution construct.
"""

from __future__ import annotations

import json
import re
import tomllib
from typing import Callable

from detectors.scaffold import (
    Finding,
    file_scopes,
    network_allowlist,
    permissions,
    shell_granted,
    static_detectable,
)
from detectors.scaffold import (
    detect_invisible_unicode_smuggling as _shared_invisible_unicode,
)
from detectors.scaffold import f1_report as _f1_report
from detectors.scaffold import f1_scope as _f1_scope
from detectors.scaffold import run_all as _run_all
from validators.usf import RISK_TIERS, derive_risk_tier

SCENARIO_TIERS: dict[str, str] = {
    "AST04-permission-understating": "static-detectable",
    "AST04-risk-tier-spoofing": "static-detectable",
    "AST04-yaml-injection": "static-detectable",
    "AST04-json-injection": "static-detectable",
    "AST04-toml-injection": "static-detectable",
    "AST04-invisible-unicode-smuggling": "static-detectable",
}

STATIC_DETECTABLE: set[str] = static_detectable(SCENARIO_TIERS)

CHECK_COVERAGE: dict[str, dict] = {
    "AST04-permission-understating": {
        "registry_ids": ["AST04-S02"],
        "covers": "full",
        "reason": (
            "AST04-S02 is tiered static-detectable because 'both sides of the contradiction "
            "ship together: the declared permission in the manifest and the egress call site "
            "in the bundled script'. This check reads both sides -- the destination host of "
            "each egress call site in the package's own scripts, against "
            "permissions.network.allow evaluated default-deny and host-exact, the same rule "
            "validators/usf.py::network_egress_allowed applies."
        ),
    },
    "AST04-risk-tier-spoofing": {
        "registry_ids": ["AST04-S03"],
        "covers": "full",
        "reason": (
            "The whitepaper's own mitigation states the check: 'cross-reference risk_tier "
            "declarations against the permission manifest scope'. Both operands are fields "
            "of the same manifest, and the derivation is this repository's canonical one "
            "(validators/usf.py::derive_risk_tier), not a second ladder invented here. "
            "Under-declaration -- declared strictly below the derived floor -- is the "
            "scenario; declaring a tier ABOVE the floor is conservative and does not fire."
        ),
    },
    "AST04-yaml-injection": {
        "registry_ids": ["AST04-S04"],
        "covers": "full",
        "reason": (
            "AST04-S04 is tiered static-detectable on 'the dangerous tag ... a literal byte "
            "sequence in the frontmatter, and the loader opt-in ... a call site in the "
            "bundled code'. The check implements BOTH halves: a raw-text tag scan over "
            "shipped YAML and over SKILL.md frontmatter blocks, and an unsafe-deserialization "
            "API scan over bundled Python. Either half firing is the finding, because a "
            "package can ship the payload for a host loader it does not bundle."
        ),
    },
    "AST04-json-injection": {
        "registry_ids": ["AST04-S06"],
        "covers": "full",
        "reason": (
            "The package-side half of AST04-S06 is the polluting key in the shipped JSON, and "
            "that is what this check decides. The whitepaper places the exploiting merge in "
            "'Node.js runtimes that perform the merge' -- which may be the host, not the "
            "package -- so requiring an in-package merge site would MISS the common shape "
            "(a skill that ships only the poisoned manifest.json). An in-package recursive "
            "merge is therefore reported as corroborating evidence, not as a precondition."
        ),
    },
    "AST04-toml-injection": {
        "registry_ids": ["AST04-S07"],
        "covers": "full",
        "reason": (
            "AST04-S07's risk is 'unvalidated key overrides ... when precedence rules aren't "
            "enforced'. The check decides both shapes from the shipped config's literal "
            "structure: a redefined single-bracket table (the precedence violation, found by "
            "text scan BEFORE tomllib is asked to parse, because tomllib raises on a "
            "redefinition and the raise used to swallow the finding), and a top-level key "
            "outside the schema allowlist."
        ),
    },
    "AST04-invisible-unicode-smuggling": {
        "registry_ids": [],
        "covers": "category-precondition",
        "derivation": (
            "AST04's preventive-mitigation list ('flag suspicious patterns ... specifically "
            "ASCII smuggling, base64 payloads, and zero-width characters invisible to human "
            "reviewers'), not any of AST04's seven named scenarios."
        ),
        "reason": (
            "The scan flags a carrier class and stops. It is specifically NOT AST08-S02 "
            "Obfuscated Instruction, which needs bounded decode-then-rescan the shipped "
            "function performs none of; and it is not AST01-S11, which turns on concealed "
            "instructions in returned content rather than on code-point presence. "
            "Package-decidable, and coverage of no named scenario in any category."
        ),
    },
}

F1_SCOPE: str = _f1_scope(CHECK_COVERAGE)


def _files_with_suffix(pkg: dict, *suffixes: str) -> dict[str, str]:
    files = pkg.get("files", {})
    return {p: c for p, c in files.items() if p.lower().endswith(suffixes)}


# --- AST04-S04: YAML code execution ----------------------------------------
#
# Two halves, per the registry reason. The payload half is a dangerous tag in
# shipped YAML; the loader half is an unsafe deserialization API in bundled
# Python. Neither half is ever parsed -- the tag scan is raw text, because
# calling the unsafe loader to find out whether a package contains an unsafe
# loader payload is the injection itself.

_DANGEROUS_YAML_TAG_RE = re.compile(r"!!(?:python|ruby)/[A-Za-z_][A-Za-z0-9_.]*(?:/[A-Za-z_][A-Za-z0-9_.]*)*")
_YAML_UNSAFE_LOAD_CALL_RE = re.compile(r"yaml\.unsafe_load\s*\(")
_YAML_UNSAFE_LOADER_CLASS_RE = re.compile(r"Loader\s*=\s*yaml\.UnsafeLoader")
_YAML_LOAD_CALL_RE = re.compile(r"yaml\.load\s*\(")
_YAML_LOAD_CALL_WINDOW = 200  # chars scanned after `yaml.load(` for a Loader= kwarg


def frontmatter_block(text: str) -> str:
    """The YAML frontmatter of a Markdown file, or ``""`` when there is none.

    Scanning only the frontmatter of a `.md` file, never its body, is deliberate:
    AST04-S04's payload lives in the frontmatter the loader deserializes, while a
    body that *discusses* `!!python/object` -- as this repository's own
    `skills/AST04/SKILL.md` does -- is documentation, not a payload.
    """
    if not text.startswith("---"):
        return ""
    start = text.find("\n", 3)
    if start == -1:
        return ""
    end = text.find("\n---", start)
    return text[start + 1 : end] if end != -1 else ""


def detect_yaml_injection(pkg: dict) -> Finding:
    for path, content in sorted(_files_with_suffix(pkg, ".yaml", ".yml").items()):
        match = _DANGEROUS_YAML_TAG_RE.search(content)
        if match:
            return Finding(
                "AST04-yaml-injection",
                True,
                f"{path}: code-executing YAML tag {match.group(0)!r}",
            )
    for path, content in sorted(_files_with_suffix(pkg, ".md").items()):
        match = _DANGEROUS_YAML_TAG_RE.search(frontmatter_block(content))
        if match:
            return Finding(
                "AST04-yaml-injection",
                True,
                f"{path}: code-executing YAML tag {match.group(0)!r} in frontmatter",
            )
    for path, content in sorted(_files_with_suffix(pkg, ".py").items()):
        if _YAML_UNSAFE_LOAD_CALL_RE.search(content):
            return Finding("AST04-yaml-injection", True, f"{path}: yaml.unsafe_load() call")
        if _YAML_UNSAFE_LOADER_CLASS_RE.search(content):
            return Finding("AST04-yaml-injection", True, f"{path}: Loader=yaml.UnsafeLoader")
        for match in _YAML_LOAD_CALL_RE.finditer(content):
            window = content[match.start() : match.start() + _YAML_LOAD_CALL_WINDOW]
            if "SafeLoader" not in window:
                return Finding(
                    "AST04-yaml-injection",
                    True,
                    f"{path}: yaml.load() with no explicit Loader=yaml.SafeLoader",
                )
    return Finding(
        "AST04-yaml-injection",
        False,
        "no code-executing YAML tag and no unsafe YAML deserialization API usage found",
    )


# --- AST04-S06: JSON prototype pollution ------------------------------------

_DANGEROUS_JSON_KEYS = {"__proto__", "constructor", "prototype"}

#: A recursive merge that writes an attacker-controlled key straight onto a
#: target object -- the exploitation half the whitepaper describes. Reported as
#: corroboration; see CHECK_COVERAGE for why it is not required.
_RECURSIVE_MERGE_LOOP_RE = re.compile(r"for\s*\(\s*(?:const|let|var)?\s*\w+\s+in\s+\w+\s*\)")
_RECURSIVE_MERGE_ASSIGN_RE = re.compile(r"\w+\s*\[\s*\w+\s*\]\s*=")


def _scan_json_keys(node) -> str | None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _DANGEROUS_JSON_KEYS:
                return key
            found = _scan_json_keys(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _scan_json_keys(item)
            if found:
                return found
    return None


def _unsafe_merge_sites(pkg: dict) -> list[str]:
    sites = []
    for path, content in sorted(_files_with_suffix(pkg, ".js", ".mjs", ".cjs", ".ts").items()):
        if _RECURSIVE_MERGE_LOOP_RE.search(content) and _RECURSIVE_MERGE_ASSIGN_RE.search(content):
            sites.append(path)
    return sites


def detect_json_injection(pkg: dict) -> Finding:
    for path, content in sorted(_files_with_suffix(pkg, ".json").items()):
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            continue  # malformed JSON is not this detector's job
        bad_key = _scan_json_keys(data)
        if bad_key:
            merges = _unsafe_merge_sites(pkg)
            corroboration = (
                f"; unsafe recursive merge in {merges}" if merges else "; no in-package merge site (host may merge)"
            )
            return Finding(
                "AST04-json-injection",
                True,
                f"{path}: prototype-pollution key {bad_key!r}{corroboration}",
            )
    return Finding("AST04-json-injection", False, "no prototype-pollution keys found")


# --- AST04-S07: TOML / config injection -------------------------------------

_EXPECTED_TOML_TOP_LEVEL_KEYS = {
    "name",
    "description",
    "version",
    "settings",
    "permissions",
    "metadata",
}
#: Single-bracket table headers only. `[[array_of_tables]]` legitimately repeats;
#: a repeated `[table]` is the precedence violation AST04-S07 names.
_TOML_TABLE_HEADER_RE = re.compile(r"^[ \t]*\[([^\[\]\n]+)\][ \t]*$", re.MULTILINE)


def _redefined_tables(content: str) -> list[str]:
    seen: list[str] = []
    duplicates: list[str] = []
    for match in _TOML_TABLE_HEADER_RE.finditer(content):
        name = match.group(1).strip()
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.append(name)
    return duplicates


def detect_toml_injection(pkg: dict) -> Finding:
    for path, content in sorted(_files_with_suffix(pkg, ".toml").items()):
        # Precedence first: tomllib RAISES on a redefined table, so asking it to
        # parse before this scan is what previously swallowed the finding.
        duplicates = _redefined_tables(content)
        if duplicates:
            return Finding(
                "AST04-toml-injection",
                True,
                f"{path}: table(s) {duplicates} redefined; a later definition overrides the "
                f"declared one with no precedence rule enforced",
            )
        try:
            data = tomllib.loads(content)
        except tomllib.TOMLDecodeError:
            continue  # malformed for some other reason is not this detector's job
        unexpected = set(data.keys()) - _EXPECTED_TOML_TOP_LEVEL_KEYS
        if unexpected:
            return Finding(
                "AST04-toml-injection",
                True,
                f"{path}: unexpected top-level key(s) {sorted(unexpected)}",
            )
    return Finding(
        "AST04-toml-injection",
        False,
        "no redefined tables and no unexpected top-level TOML keys found",
    )


# --- AST04-S02: permission understating -------------------------------------
#
# "Declare network: false in metadata while the underlying script calls curl to
# an external endpoint." Both operands ship together, which is why the registry
# tiers it static-detectable: the declared allowlist is a manifest field and the
# destination host is a literal in the bundled script.

_CODE_SUFFIXES = (".py", ".sh", ".bash", ".zsh", ".js", ".mjs", ".cjs", ".ts", ".rb", ".ps1", ".pl")
_EGRESS_PRIMITIVE_RE = re.compile(
    r"\b(?:curl|wget|Invoke-WebRequest|iwr|requests\.(?:get|post|put|patch|delete|request)"
    r"|urlopen|httpx\.(?:get|post|put|request)|axios(?:\.\w+)?|fetch|Net::HTTP|HTTPSConnection|HTTPConnection)\b"
)
_URL_RE = re.compile(r"https?://([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)(?::\d+)?")


def _egress_call_sites(pkg: dict) -> list[tuple[str, int, str, str]]:
    """``(path, line_number, host, line)`` for every egress call site with a literal host.

    A host is only reported when an egress primitive and an absolute URL appear on
    the same line, which keeps prose and identifier names (``detect_unrestricted_
    network_fetch``) out of the result: the finding has to name a destination the
    manifest can be checked against.
    """
    sites: list[tuple[str, int, str, str]] = []
    for path, content in sorted(_files_with_suffix(pkg, *_CODE_SUFFIXES).items()):
        for number, line in enumerate(content.splitlines(), start=1):
            if not _EGRESS_PRIMITIVE_RE.search(line):
                continue
            for match in _URL_RE.finditer(line):
                sites.append((path, number, match.group(1).lower(), line.strip()))
    return sites


def detect_permission_understating(pkg: dict) -> Finding:
    perms = permissions(pkg)
    allowlist = {host.lower() for host in network_allowlist(perms)}
    sites = _egress_call_sites(pkg)
    if not sites:
        return Finding(
            "AST04-permission-understating",
            False,
            f"no egress call site with a literal destination in the bundled code "
            f"(declared allowlist: {sorted(allowlist)})",
        )
    if "*" in allowlist:
        return Finding(
            "AST04-permission-understating",
            False,
            "the manifest declares unrestricted egress, so the bundled egress is declared, "
            "not understated (breadth is AST03's finding, not AST04-S02's)",
        )
    # Default-deny, host-exact -- validators/usf.py::network_egress_allowed's rule.
    undeclared = [site for site in sites if site[2] not in allowlist]
    if undeclared:
        path, number, host, line = undeclared[0]
        return Finding(
            "AST04-permission-understating",
            True,
            f"{path}:{number} reaches {host!r}, which permissions.network.allow "
            f"({sorted(allowlist)}) does not permit: {line[:120]}",
        )
    return Finding(
        "AST04-permission-understating",
        False,
        f"all {len(sites)} egress call site(s) reach hosts the manifest declares: {sorted(allowlist)}",
    )


# --- AST04-S03: risk tier spoofing ------------------------------------------

_TIER_RANK = {tier: index for index, tier in enumerate(RISK_TIERS)}


def _usf_shaped_permissions(perms: dict) -> dict:
    """Re-nest whatever permission vocabulary arrived into the USF shape.

    ``validators/usf.py::derive_risk_tier`` is the repository's one permission ->
    risk-tier ladder and it is specified over USF. Rebuilding its input here,
    rather than reimplementing the ladder, is what keeps the detector's answer and
    the validator's answer the same answer.
    """
    scopes = file_scopes(perms)
    return {
        "files": {
            "read": list(scopes.read),
            "write": list(scopes.write),
            "deny_write": list(scopes.deny_write),
        },
        "network": {"allow": list(network_allowlist(perms))},
        "shell": shell_granted(perms),
    }


def detect_risk_tier_spoofing(pkg: dict) -> Finding:
    declared = (pkg.get("manifest") or {}).get("risk_tier")
    if not isinstance(declared, str) or declared not in _TIER_RANK:
        return Finding(
            "AST04-risk-tier-spoofing",
            False,
            f"no valid risk_tier declared ({declared!r}); there is no self-classification to "
            f"contradict (an absent tier is AST04-S01/metadata-completeness, not spoofing)",
        )
    perms = permissions(pkg)
    if not perms:
        return Finding(
            "AST04-risk-tier-spoofing",
            False,
            f"risk_tier {declared!r} declared with no permission manifest to cross-reference",
        )
    derived = derive_risk_tier(_usf_shaped_permissions(perms))
    if _TIER_RANK[declared] < _TIER_RANK[derived]:
        return Finding(
            "AST04-risk-tier-spoofing",
            True,
            f"declared risk_tier {declared} is below the {derived} floor derived from the "
            f"declared permission scope (validators/usf.py::derive_risk_tier)",
        )
    return Finding(
        "AST04-risk-tier-spoofing",
        False,
        f"declared risk_tier {declared} is at or above the derived floor {derived}",
    )


# --- AST04-invisible-unicode-smuggling --------------------------------------
# Detection logic (regex + scan) lives in detectors.scaffold, shared verbatim
# with AST08's own instance of the same control -- this module supplies only
# its own scenario id (code-review finding: reuse, MEDIUM -- the scan was
# previously duplicated verbatim in both modules).
def detect_invisible_unicode_smuggling(pkg: dict) -> Finding:
    return _shared_invisible_unicode(pkg, "AST04-invisible-unicode-smuggling")


DETECTORS: dict[str, Callable[[dict], Finding]] = {
    "AST04-permission-understating": detect_permission_understating,
    "AST04-risk-tier-spoofing": detect_risk_tier_spoofing,
    "AST04-yaml-injection": detect_yaml_injection,
    "AST04-json-injection": detect_json_injection,
    "AST04-toml-injection": detect_toml_injection,
    "AST04-invisible-unicode-smuggling": detect_invisible_unicode_smuggling,
}


def run_all(pkg: dict) -> list[Finding]:
    return _run_all(DETECTORS, pkg)


def f1_report(fixtures: list[tuple[dict, set[str]]]) -> dict:
    return _f1_report(STATIC_DETECTABLE, DETECTORS, fixtures, F1_SCOPE)
