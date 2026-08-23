"""AST07 -- Update Drift detector.

Interim scenario-tier declaration (T-3.3); superseded by T-1.3's registry and
T-3.1's authored `skills/AST07/coverage-matrix.md` once locked.

Both named scenarios require version/release history that lives outside a
single skill package snapshot, per plan.md's own stated reasons:

- Rollback Attack: detecting a downgrade to a known-vulnerable prior version
  requires the release history to compare against; a lone package snapshot
  has no "previous version" to be a rollback of.
- Hot-Reload Abuse: detecting abuse of a live reload path requires the
  update-event/release metadata (when a reload happened, from what source)
  that a static package artifact does not carry.

Because this category's declared-detectable tier is empty, gate-4 requires
`f1_report` to publish no F1 at all rather than manufacture one: this module
therefore ships zero detector functions and reports
"declared-and-uncovered" (S-003).
"""

from __future__ import annotations

from typing import Callable

from detectors.scaffold import Finding, static_detectable
from detectors.scaffold import f1_report as _f1_report
from detectors.scaffold import run_all as _run_all

SCENARIO_TIERS: dict[str, str] = {
    "AST07-rollback-attack": "out-of-artifact",
    "AST07-hot-reload-abuse": "out-of-artifact",
}

STATIC_DETECTABLE: set[str] = static_detectable(SCENARIO_TIERS)

DETECTORS: dict[str, Callable[[dict], Finding]] = {}


def run_all(pkg: dict) -> list[Finding]:
    return _run_all(DETECTORS, pkg)


def f1_report(fixtures: list[tuple[dict, set[str]]] | None = None) -> dict:
    return _f1_report(STATIC_DETECTABLE, DETECTORS, fixtures)
