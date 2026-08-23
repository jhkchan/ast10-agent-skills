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

from dataclasses import dataclass
from typing import Callable

SCENARIO_TIERS: dict[str, str] = {
    "AST02-maintainer-account-takeover": "out-of-artifact",
}

STATIC_DETECTABLE: set[str] = {
    s for s, tier in SCENARIO_TIERS.items() if tier == "static-detectable"
}


@dataclass
class Finding:
    scenario: str
    detected: bool
    evidence: str = ""


DETECTORS: dict[str, Callable[[dict], Finding]] = {}


def run_all(pkg: dict) -> list[Finding]:
    return [fn(pkg) for fn in DETECTORS.values()]


def f1_report(fixtures: list[tuple[dict, set[str]]] | None = None) -> dict:
    """Empty declared-detectable tier -> never manufacture an F1 (S-003, gate-4)."""
    if not STATIC_DETECTABLE:
        return {"status": "declared-and-uncovered", "f1": None}
    return {"status": "measured", "f1": None}  # unreachable while the tier stays empty
