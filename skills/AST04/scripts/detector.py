"""AST04 -- Insecure Metadata detector.

Anchors on the USF manifest's file tree (spec.md Behavior item 2): a skill
package's `.yaml`/`.yml`, `.json`, and `.toml` metadata/config files are
parsed defensively and checked for three distinct, format-specific injection
signals -- never one shared "looks like config injection" code path (S-005).
A fourth, format-independent scenario covers the invisible-Unicode control
the T-3.3 extraction run surfaced directly: 860 zero-width/bidi code points
were stripped from the source PDF itself, which is a live smuggling vector
shared with AST08 (see `skills/AST08/scripts/detector.py`).

Interim scenario-tier declaration (T-3.3); superseded by T-1.3's registry and
T-3.1's authored `skills/AST04/coverage-matrix.md` once locked.

Security note: this detector NEVER calls `yaml.load()`/`UnsafeLoader` on
attacker-controlled content -- that would execute the very injection this
module exists to catch. Detection is raw-text source scanning only.

Detection choice for YAML follows `skills/AST04/SKILL.md`'s own decision
rule: PyYAML has been `FullLoader`-safe by default since 5.1, so a detector
that only greps skill data for a literal `!!python/object` tag misses the
more common finding -- the *loader choice* in the skill's own source. This
module therefore scans the package's `.py` files for unsafe YAML
deserialization API usage (`yaml.unsafe_load`, `Loader=yaml.UnsafeLoader`,
or a bare `yaml.load()` call with no explicit `Loader=yaml.SafeLoader`)
rather than scanning `.yaml` file content for tag strings.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from typing import Callable

SCENARIO_TIERS: dict[str, str] = {
    "AST04-yaml-injection": "static-detectable",
    "AST04-json-injection": "static-detectable",
    "AST04-toml-injection": "static-detectable",
    "AST04-invisible-unicode-smuggling": "static-detectable",
}

STATIC_DETECTABLE: set[str] = {
    s for s, tier in SCENARIO_TIERS.items() if tier == "static-detectable"
}


@dataclass
class Finding:
    scenario: str
    detected: bool
    evidence: str = ""


def _files_with_suffix(pkg: dict, *suffixes: str) -> dict[str, str]:
    files = pkg.get("files", {})
    return {p: c for p, c in files.items() if p.lower().endswith(suffixes)}


# --- AST04-yaml-injection: unsafe YAML deserialization API usage -----------

_YAML_UNSAFE_LOAD_CALL_RE = re.compile(r"yaml\.unsafe_load\s*\(")
_YAML_UNSAFE_LOADER_CLASS_RE = re.compile(r"Loader\s*=\s*yaml\.UnsafeLoader")
_YAML_LOAD_CALL_RE = re.compile(r"yaml\.load\s*\(")
_YAML_LOAD_CALL_WINDOW = 200  # chars scanned after `yaml.load(` for a Loader= kwarg


def detect_yaml_injection(pkg: dict) -> Finding:
    for path, content in _files_with_suffix(pkg, ".py").items():
        if _YAML_UNSAFE_LOAD_CALL_RE.search(content):
            return Finding(
                "AST04-yaml-injection", True, f"{path}: yaml.unsafe_load() call"
            )
        if _YAML_UNSAFE_LOADER_CLASS_RE.search(content):
            return Finding(
                "AST04-yaml-injection", True, f"{path}: Loader=yaml.UnsafeLoader"
            )
        for match in _YAML_LOAD_CALL_RE.finditer(content):
            window = content[match.start() : match.start() + _YAML_LOAD_CALL_WINDOW]
            if "SafeLoader" not in window:
                return Finding(
                    "AST04-yaml-injection",
                    True,
                    f"{path}: yaml.load() with no explicit Loader=yaml.SafeLoader",
                )
    return Finding(
        "AST04-yaml-injection", False, "no unsafe YAML deserialization API usage found"
    )


# --- AST04-json-injection: prototype-pollution key names --------------------

_DANGEROUS_JSON_KEYS = {"__proto__", "constructor", "prototype"}


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


def detect_json_injection(pkg: dict) -> Finding:
    for path, content in _files_with_suffix(pkg, ".json").items():
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            continue  # malformed JSON is not this detector's job
        bad_key = _scan_json_keys(data)
        if bad_key:
            return Finding(
                "AST04-json-injection",
                True,
                f"{path}: prototype-pollution key {bad_key!r}",
            )
    return Finding("AST04-json-injection", False, "no prototype-pollution keys found")


# --- AST04-toml-injection: unexpected top-level table beyond the known set --

_EXPECTED_TOML_TOP_LEVEL_KEYS = {
    "name",
    "description",
    "version",
    "settings",
    "permissions",
    "metadata",
}


def detect_toml_injection(pkg: dict) -> Finding:
    for path, content in _files_with_suffix(pkg, ".toml").items():
        try:
            data = tomllib.loads(content)
        except tomllib.TOMLDecodeError:
            continue  # malformed TOML is not this detector's job
        unexpected = set(data.keys()) - _EXPECTED_TOML_TOP_LEVEL_KEYS
        if unexpected:
            return Finding(
                "AST04-toml-injection",
                True,
                f"{path}: unexpected top-level key(s) {sorted(unexpected)}",
            )
    return Finding(
        "AST04-toml-injection", False, "no unexpected top-level TOML keys found"
    )


# --- AST04-invisible-unicode-smuggling --------------------------------------
# Zero-width spaces/joiners and bidi control code points -- the same class the
# whitepaper extraction stripped 860 instances of from the source PDF.
# Explicit \uXXXX escapes on purpose: embedding the literal invisible glyphs
# in this file's own source would be exactly the smuggling risk this
# detector exists to catch, and would be silently unreadable in any diff.
_INVISIBLE_UNICODE_RE = re.compile(
    "[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]"
)


def detect_invisible_unicode_smuggling(pkg: dict) -> Finding:
    manifest_text = pkg.get("manifest", {}).get("description", "") or ""
    candidates = dict(pkg.get("files", {}))
    candidates["<manifest.description>"] = manifest_text
    for path, content in candidates.items():
        hits = _INVISIBLE_UNICODE_RE.findall(content)
        if hits:
            codepoints = sorted({f"U+{ord(c):04X}" for c in hits})
            return Finding(
                "AST04-invisible-unicode-smuggling",
                True,
                f"{path}: {len(hits)} invisible code point(s) {codepoints}",
            )
    return Finding(
        "AST04-invisible-unicode-smuggling",
        False,
        "no invisible Unicode control code points found",
    )


DETECTORS: dict[str, Callable[[dict], Finding]] = {
    "AST04-yaml-injection": detect_yaml_injection,
    "AST04-json-injection": detect_json_injection,
    "AST04-toml-injection": detect_toml_injection,
    "AST04-invisible-unicode-smuggling": detect_invisible_unicode_smuggling,
}


def run_all(pkg: dict) -> list[Finding]:
    return [fn(pkg) for fn in DETECTORS.values()]


def f1_report(fixtures: list[tuple[dict, set[str]]]) -> dict:
    if not STATIC_DETECTABLE:
        return {"status": "declared-and-uncovered", "f1": None}

    tp = fp = fn = 0
    for pkg, expected in fixtures:
        expected = expected & STATIC_DETECTABLE
        detected = {f.scenario for f in run_all(pkg) if f.detected}
        tp += len(detected & expected)
        fp += len(detected - expected)
        fn += len(expected - detected)

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (
        (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    )
    return {
        "status": "measured",
        "f1": f1,
        "precision": precision,
        "recall": recall,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }
