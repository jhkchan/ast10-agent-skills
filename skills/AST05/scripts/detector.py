"""AST05 -- Untrusted External Instructions detector.

Anchors on the USF manifest's `permissions.network` field (spec.md Behavior
item 2). A skill that can fetch and act on content from anywhere on the
network is a skill that can be steered by instructions the operator never
approved; both scenarios below audit exactly how wide that fetch surface is
declared to be.

Interim scenario-tier declaration (T-3.3); superseded by T-1.3's registry and
T-3.1's authored `skills/AST05/coverage-matrix.md` once locked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

SCENARIO_TIERS: dict[str, str] = {
    "AST05-unrestricted-network-fetch": "static-detectable",
    "AST05-wildcard-domain-allowlist": "static-detectable",
    # Whether a fetched instruction was actually *complied with* over the
    # skill's own stated task needs the transcript read with judgment.
    "AST05-injected-instruction-compliance": "agent-judgable",
}

STATIC_DETECTABLE: set[str] = {
    s for s, tier in SCENARIO_TIERS.items() if tier == "static-detectable"
}


@dataclass
class Finding:
    scenario: str
    detected: bool
    evidence: str = ""


def _network(pkg: dict) -> dict:
    permissions = pkg.get("manifest", {}).get("permissions") or {}
    return permissions.get("network") or {}


def detect_unrestricted_network_fetch(pkg: dict) -> Finding:
    """`network.policy == "allow-all"` means no domain is out of bounds."""
    policy = _network(pkg).get("policy")
    detected = policy == "allow-all"
    return Finding(
        "AST05-unrestricted-network-fetch", detected, f"network.policy={policy}"
    )


def _is_overly_broad_wildcard(entry: str) -> bool:
    if entry == "*":
        return True
    if entry.startswith("*."):
        suffix = entry[2:]
        return (
            suffix.count(".") < 1
        )  # e.g. "*.com" -- a bare TLD wildcard, not a scoped subdomain
    return False


def detect_wildcard_domain_allowlist(pkg: dict) -> Finding:
    """Declared as allow-list mode but the list itself is unrestricted in
    practice, e.g. `"*"` or a bare-TLD wildcard like `"*.com"` -- distinct
    from `unrestricted-network-fetch`, which flags `policy == "allow-all"`."""
    network = _network(pkg)
    if network.get("policy") != "allow-list":
        return Finding(
            "AST05-wildcard-domain-allowlist", False, "not in allow-list mode"
        )
    allow = network.get("allow", []) or []
    broad = [entry for entry in allow if _is_overly_broad_wildcard(entry)]
    detected = bool(broad)
    evidence = (
        f"overly broad allow-list entries: {broad}"
        if detected
        else f"allow-list scoped: {allow}"
    )
    return Finding("AST05-wildcard-domain-allowlist", detected, evidence)


DETECTORS: dict[str, Callable[[dict], Finding]] = {
    "AST05-unrestricted-network-fetch": detect_unrestricted_network_fetch,
    "AST05-wildcard-domain-allowlist": detect_wildcard_domain_allowlist,
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
