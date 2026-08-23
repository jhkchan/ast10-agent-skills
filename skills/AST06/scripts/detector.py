"""AST06 -- Weak Isolation detector.

Anchors on the USF manifest's `permissions.shell` field, plus the presence
of a `permissions` block at all (spec.md Behavior item 2). A skill with
arbitrary shell exec, or one that declares no isolation posture whatsoever,
is running with weaker sandbox boundaries than the manifest schema exists to
constrain.

Interim scenario-tier declaration (T-3.3); superseded by T-1.3's registry and
T-3.1's authored `skills/AST06/coverage-matrix.md` once locked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

SCENARIO_TIERS: dict[str, str] = {
    "AST06-unrestricted-shell-exec": "static-detectable",
    "AST06-missing-sandbox-declaration": "static-detectable",
    # Whether data actually crossed between co-installed skills at runtime is
    # an execution-trace property, not something the manifest alone shows.
    "AST06-cross-skill-data-leak": "agent-judgable",
}

STATIC_DETECTABLE: set[str] = {
    s for s, tier in SCENARIO_TIERS.items() if tier == "static-detectable"
}


@dataclass
class Finding:
    scenario: str
    detected: bool
    evidence: str = ""


def detect_unrestricted_shell_exec(pkg: dict) -> Finding:
    """Shell allowed with no `commands` allow-list == run anything."""
    permissions = pkg.get("manifest", {}).get("permissions") or {}
    shell = permissions.get("shell") or {}
    allowed = bool(shell.get("allowed"))
    commands = shell.get("commands") or []
    detected = allowed and not commands
    evidence = (
        "shell.allowed with no commands allow-list"
        if detected
        else f"shell.allowed={allowed} commands={commands}"
    )
    return Finding("AST06-unrestricted-shell-exec", detected, evidence)


def detect_missing_sandbox_declaration(pkg: dict) -> Finding:
    """No `permissions` block at all -- no isolation posture is declared,
    distinct from a broad-but-present one (unrestricted-shell-exec)."""
    permissions = pkg.get("manifest", {}).get("permissions")
    detected = not permissions
    evidence = (
        "manifest.permissions is unset or empty"
        if detected
        else "permissions block present"
    )
    return Finding("AST06-missing-sandbox-declaration", detected, evidence)


DETECTORS: dict[str, Callable[[dict], Finding]] = {
    "AST06-unrestricted-shell-exec": detect_unrestricted_shell_exec,
    "AST06-missing-sandbox-declaration": detect_missing_sandbox_declaration,
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
