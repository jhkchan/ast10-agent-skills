"""AST02 -- Supply Chain Compromise detector.

Interim scenario-tier declaration (T-3.3); superseded by T-1.3's registry and
T-3.1's authored `skills/AST02/coverage-matrix.md` once locked.

Maintainer Account Takeover is registry-side: the signal lives in the
registry's own auth/session logs (who published this version, from what
account, with what credential), not in anything the skill package itself
ships. A package artifact carries no observable difference between a
legitimate maintainer's release and a hijacked account's release of the
same content, so this scenario is out-of-artifact per plan.md's own stated
reason (see `docs/adr/0004-per-scenario-detectability-contract.md`,
authored by T-4.3).

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
    "AST02-maintainer-account-takeover": "out-of-artifact",
}

STATIC_DETECTABLE: set[str] = static_detectable(SCENARIO_TIERS)

DETECTORS: dict[str, Callable[[dict], Finding]] = {}


def run_all(pkg: dict) -> list[Finding]:
    return _run_all(DETECTORS, pkg)


def f1_report(fixtures: list[tuple[dict, set[str]]] | None = None) -> dict:
    """Empty declared-detectable tier -> never manufacture an F1 (S-003, gate-4)."""
    return _f1_report(STATIC_DETECTABLE, DETECTORS, fixtures)
