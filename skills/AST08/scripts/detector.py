"""AST08 -- Poor Scanning detector.

Most of what this category names is exactly the kind of natural-language
scenario spec.md's own rejected-design-C note calls out ("the only design
that can plausibly reach F1 >= 0.80 on natural-language scenarios AST08
exists to describe") -- i.e. agent-judgable, not static-detectable. One
scenario is a genuine exception: the invisible-Unicode control the T-3.3
extraction run surfaced is a concrete, static, format-independent smuggling
signal that a scanner missing it would be "poor scanning" by definition.
It is declared static-detectable here and shares its detection mechanism
with AST04's own instance of the same control (see
`skills/AST04/scripts/detector.py`) while remaining its own function, its
own fixtures, and its own file per this category's package scope.

Interim scenario-tier declaration (T-3.3); superseded by T-1.3's registry and
T-3.1's authored `skills/AST08/coverage-matrix.md` once locked.
"""

from __future__ import annotations

from typing import Callable

from detectors.scaffold import Finding
from detectors.scaffold import (
    detect_invisible_unicode_smuggling as _shared_invisible_unicode,
)
from detectors.scaffold import f1_report as _f1_report
from detectors.scaffold import run_all as _run_all
from detectors.scaffold import static_detectable

SCENARIO_TIERS: dict[str, str] = {
    "AST08-invisible-unicode-smuggling": "static-detectable",
    # Whether a described bypass narrative actually evades a *specific*
    # scanner's ruleset is a claim about that scanner's behavior, not
    # anything this package's own content can settle statically.
    "AST08-scan-evasion-narrative": "agent-judgable",
}

STATIC_DETECTABLE: set[str] = static_detectable(SCENARIO_TIERS)


# Detection logic (regex + scan) lives in detectors.scaffold, shared verbatim
# with AST04's own instance of the same control -- this module supplies only
# its own scenario id (code-review finding: reuse, MEDIUM -- the scan was
# previously duplicated verbatim in both modules).
def detect_invisible_unicode_smuggling(pkg: dict) -> Finding:
    return _shared_invisible_unicode(pkg, "AST08-invisible-unicode-smuggling")


DETECTORS: dict[str, Callable[[dict], Finding]] = {
    "AST08-invisible-unicode-smuggling": detect_invisible_unicode_smuggling,
}


def run_all(pkg: dict) -> list[Finding]:
    return _run_all(DETECTORS, pkg)


def f1_report(fixtures: list[tuple[dict, set[str]]]) -> dict:
    return _f1_report(STATIC_DETECTABLE, DETECTORS, fixtures)
