"""AST10 -- Cross-Platform Reuse detector.

Interim scenario-tier declaration (T-3.3); superseded by T-1.3's registry and
T-3.1's authored `skills/AST10/coverage-matrix.md` once locked.

Both named scenarios require a cross-registry corpus outside a single skill
package, per plan.md's own stated reason:

- Cross-Registry Arbitrage: detecting the same (or subtly modified) skill
  republished across registries under different names/permissions needs a
  corpus spanning multiple registries to compare against; a single package
  in isolation has nothing to be "cross" with.
- Multi-Platform Campaign: detecting a coordinated reuse campaign across
  platforms needs cross-platform deployment telemetry that a static package
  snapshot does not carry.

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
    "AST10-cross-registry-arbitrage": "out-of-artifact",
    "AST10-multi-platform-campaign": "out-of-artifact",
}

STATIC_DETECTABLE: set[str] = static_detectable(SCENARIO_TIERS)

DETECTORS: dict[str, Callable[[dict], Finding]] = {}


def run_all(pkg: dict) -> list[Finding]:
    return _run_all(DETECTORS, pkg)


def f1_report(fixtures: list[tuple[dict, set[str]]] | None = None) -> dict:
    return _f1_report(STATIC_DETECTABLE, DETECTORS, fixtures)
