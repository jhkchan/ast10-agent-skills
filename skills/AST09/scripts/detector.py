"""AST09 -- No Governance detector.

Interim scenario-tier declaration (T-3.3); superseded by T-1.3's registry and
T-3.1's authored `skills/AST09/coverage-matrix.md` once locked.

All three named scenarios are properties of an organization's process, not
of a skill package artifact, per spec.md S-003 and plan.md's own stated
reasons:

- Orphaned Skill: "an agent receives no updates for 6+ months but the skill
  is still in active use" (spec.md S-003) -- requires version history and
  release metadata maintained outside the artifact.
- Regulatory Exposure: requires compliance/audit records outside the
  artifact; a package snapshot carries no regulatory-scope metadata.
- Undetected Compromise: requires runtime monitoring/incident history
  outside the artifact; a package snapshot cannot show what happened after
  it was installed.

Because this category's declared-detectable tier is empty, gate-4 requires
`f1_report` to publish no F1 at all rather than manufacture one: this module
therefore ships zero detector functions and reports
"declared-and-uncovered" (S-003).
"""

from __future__ import annotations

from typing import Callable

from detectors.scaffold import Finding
from detectors.scaffold import f1_report as _f1_report
from detectors.scaffold import run_all as _run_all
from detectors.scaffold import static_detectable

SCENARIO_TIERS: dict[str, str] = {
    "AST09-orphaned-skill": "out-of-artifact",
    "AST09-regulatory-exposure": "out-of-artifact",
    "AST09-undetected-compromise": "out-of-artifact",
}

STATIC_DETECTABLE: set[str] = static_detectable(SCENARIO_TIERS)

DETECTORS: dict[str, Callable[[dict], Finding]] = {}


def run_all(pkg: dict) -> list[Finding]:
    return _run_all(DETECTORS, pkg)


def f1_report(fixtures: list[tuple[dict, set[str]]] | None = None) -> dict:
    return _f1_report(STATIC_DETECTABLE, DETECTORS, fixtures)
