"""AST01 -- Malicious Skills detector.

Anchors on the Universal Skill Format (USF) manifest's signed content-hash
field (spec.md Behavior item 2: "deny_write rules, network policy, shell
permissions, signed content hash"). A malicious/tampered skill package is
static-detectable at the artifact boundary precisely where the manifest's
declared hash and the package's actual content diverge, or where no hash was
declared to verify against at all.

Interim scenario-tier declaration (T-3.3). T-1.3's 58-scenario registry and
T-3.1's authored `skills/AST01/coverage-matrix.md` supersede this table once
locked; until then this is the working, per-scenario tier this detector is
built and tested against, scoped only to what T-3.3 can build without those
not-yet-landed artifacts.

A "skill package" is the minimal dict shape this module operates on:
    {
      "manifest": {
          "permissions": {...},                       # see AST03/05/06
          "content_hash": {"algorithm": "sha256", "value": "<hex>"} | None,
      },
      "files": {"<relative/path>": "<text content>", ...},
    }
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable

SCENARIO_TIERS: dict[str, str] = {
    "AST01-content-hash-missing": "static-detectable",
    "AST01-content-hash-mismatch": "static-detectable",
    # Judging whether a payload is *intentionally* malicious (vs. merely
    # unusual) needs semantic judgment a static pattern cannot supply.
    "AST01-obfuscated-payload-intent": "agent-judgable",
}

STATIC_DETECTABLE: set[str] = {
    s for s, tier in SCENARIO_TIERS.items() if tier == "static-detectable"
}


@dataclass
class Finding:
    scenario: str
    detected: bool
    evidence: str = ""


def _package_digest(pkg: dict) -> str:
    """Deterministic sha256 over sorted (path, content) pairs.

    This is the "actual" side of the signed-content-hash comparison: the USF
    manifest declares an expected hash, and re-deriving it here the same way
    the signer must have is what makes a mismatch detectable rather than
    merely asserted.
    """
    hasher = hashlib.sha256()
    files = pkg.get("files", {})
    for path in sorted(files):
        hasher.update(path.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(files[path].encode("utf-8"))
        hasher.update(b"\x00")
    return hasher.hexdigest()


def detect_content_hash_missing(pkg: dict) -> Finding:
    declared = (pkg.get("manifest", {}).get("content_hash") or {}).get("value")
    detected = not declared
    evidence = (
        "manifest.content_hash.value is unset"
        if detected
        else "content_hash.value present"
    )
    return Finding("AST01-content-hash-missing", detected, evidence)


def detect_content_hash_mismatch(pkg: dict) -> Finding:
    manifest = pkg.get("manifest", {})
    declared = (manifest.get("content_hash") or {}).get("value")
    if not declared:
        # No hash to compare against -- that gap is content-hash-missing's job.
        return Finding(
            "AST01-content-hash-mismatch", False, "no declared hash to compare"
        )
    actual = _package_digest(pkg)
    detected = actual != declared
    evidence = (
        f"declared={declared} actual={actual}"
        if detected
        else "hash matches package content"
    )
    return Finding("AST01-content-hash-mismatch", detected, evidence)


DETECTORS: dict[str, Callable[[dict], Finding]] = {
    "AST01-content-hash-missing": detect_content_hash_missing,
    "AST01-content-hash-mismatch": detect_content_hash_mismatch,
}


def run_all(pkg: dict) -> list[Finding]:
    return [fn(pkg) for fn in DETECTORS.values()]


def f1_report(fixtures: list[tuple[dict, set[str]]]) -> dict:
    """Per-category F1 over the declared-detectable tier only (S-007, gate-4).

    `fixtures` is a list of (package, expected_detected_scenario_ids) pairs.
    A category whose declared-detectable tier is empty must never manufacture
    a number (S-003 / gate-4); it reports "declared-and-uncovered" instead.
    """
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
