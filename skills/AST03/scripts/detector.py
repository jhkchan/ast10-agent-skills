"""AST03 -- Over-Privileged Skills detector.

Anchors on the USF manifest's `permissions.deny_write`, `permissions.shell`,
and `permissions.network` fields (spec.md Behavior item 2). The canonical
example spec.md itself uses for this category is "overprivileged agent with
write access to production secrets" (S-002); both scenarios below are static
audits of exactly the manifest fields that grant that kind of write/exec/
network reach.

Interim scenario-tier declaration (T-3.3); superseded by T-1.3's registry and
T-3.1's authored `skills/AST03/coverage-matrix.md` once locked.

Package shape (see AST01/scripts/detector.py for the full contract):
    manifest.permissions = {
        "deny_write": [str, ...] | None,
        "shell": {"allowed": bool, "commands": [str, ...] | None},
        "network": {"policy": "deny-all" | "allow-list" | "allow-all", "allow": [str, ...]},
    }
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

SCENARIO_TIERS: dict[str, str] = {
    "AST03-unbounded-write-scope": "static-detectable",
    "AST03-shell-network-privilege-combo": "static-detectable",
    # Whether the *task* actually needs the privileges it was granted requires
    # reading intent against the skill's stated purpose -- semantic judgment.
    "AST03-task-scope-mismatch": "agent-judgable",
}

STATIC_DETECTABLE: set[str] = {
    s for s, tier in SCENARIO_TIERS.items() if tier == "static-detectable"
}


@dataclass
class Finding:
    scenario: str
    detected: bool
    evidence: str = ""


def _permissions(pkg: dict) -> dict:
    return pkg.get("manifest", {}).get("permissions") or {}


def detect_unbounded_write_scope(pkg: dict) -> Finding:
    """No `deny_write` list at all == unrestricted filesystem write."""
    deny_write = _permissions(pkg).get("deny_write")
    detected = not deny_write
    evidence = (
        "permissions.deny_write is unset or empty"
        if detected
        else f"deny_write covers {len(deny_write)} path(s)"
    )
    return Finding("AST03-unbounded-write-scope", detected, evidence)


def detect_shell_network_privilege_combo(pkg: dict) -> Finding:
    """Arbitrary shell exec *and* unrestricted outbound network is the
    exfiltration-capable combo the S-002 example names: write access plus a
    channel to move what was written."""
    perms = _permissions(pkg)
    shell_allowed = bool((perms.get("shell") or {}).get("allowed"))
    network_policy = (perms.get("network") or {}).get("policy")
    detected = shell_allowed and network_policy == "allow-all"
    evidence = f"shell.allowed={shell_allowed} network.policy={network_policy}"
    return Finding("AST03-shell-network-privilege-combo", detected, evidence)


DETECTORS: dict[str, Callable[[dict], Finding]] = {
    "AST03-unbounded-write-scope": detect_unbounded_write_scope,
    "AST03-shell-network-privilege-combo": detect_shell_network_privilege_combo,
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
