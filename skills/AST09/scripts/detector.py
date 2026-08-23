"""AST09 -- No Governance detector.

THIS MODULE SHIPS NO DETECTOR FUNCTION, AND THAT IS THE FINDING
---------------------------------------------------------------
``DETECTORS`` is empty here by construction, not by omission. AST09 is the one
category in the whitepaper where every single named attack scenario is
out-of-artifact: ``scenarios/registry.yaml`` tiers all seven that way, so
``STATIC_DETECTABLE`` derives to the empty set and there is no scenario for a
deterministic rule to decide. ``tests/test_scenario_registry.py``'s
``test_ast09_has_no_static_detectable_scenario`` and this module's own tests
pin that in both directions: if the registry ever tiers an AST09 scenario
static-detectable, the tier lock trips and this file must grow a check.

Why all seven are out-of-artifact, in the whitepaper's own terms. AST09's
subject is the organisation, not the package: "Organizations deploying AI
agents lack the inventories, policies, review processes, and audit trails
needed to manage skills at enterprise scale." Every scenario's defining
condition is therefore a fact held outside the artifact --

  AST09-S01 Undetected Compromise    no alert fired: monitoring-pipeline state
  AST09-S02 Unapproved Malicious Skill  approval: the installer's workflow
  AST09-S03 Orphaned Skill           HR offboarding + IAM credential state
  AST09-S04 Regulatory Exposure      data classification + jurisdiction + logs
  AST09-S05 Unreachable Skill        "no host to scan and no local package
                                     manifest to read" -- no artifact exists
  AST09-S06 Cascading Agent Compromise  pipeline topology and checkpoints
  AST09-S07 Manipulated Trust Signals   registry-side stars and install counts

-- and an approved copy and an unapproved copy of the same skill are byte
identical. The registry records no ``artifact_signal`` for any of the seven
either: unlike AST10, AST09 does not even have an in-package proxy worth
naming. ``skills/AST09/coverage-matrix.md`` carries the full written reason
per scenario plus the off-artifact evidence that WOULD decide each one.

Because the declared-detectable tier is empty, gate-4 requires ``f1_report``
to publish no F1 at all rather than manufacture one from fixtures that encode
an organisational fact in prose and then detect the prose (spec.md S-003). It
returns ``declared-and-uncovered`` and the corpus stays at zero cases; that is
a measurement refusal, not an unfinished detector.
"""

from __future__ import annotations

from typing import Callable

from detectors.scaffold import Finding, static_detectable
from detectors.scaffold import f1_report as _f1_report
from detectors.scaffold import f1_scope as _f1_scope
from detectors.scaffold import run_all as _run_all

#: Keyed by ``scenarios/registry.yaml``'s canonical ids, and complete: all
#: seven scenarios the whitepaper's AST09 "Attack Scenarios" section names, not
#: the three an earlier interim declaration listed. The registry is
#: authoritative on tier and this map must agree with it, which
#: ``tests/test_coverage_matrix_ast09_ast10.py`` checks.
SCENARIO_TIERS: dict[str, str] = {
    "AST09-S01": "out-of-artifact",  # Undetected Compromise
    "AST09-S02": "out-of-artifact",  # Unapproved Malicious Skill
    "AST09-S03": "out-of-artifact",  # Orphaned Skill
    "AST09-S04": "out-of-artifact",  # Regulatory Exposure
    "AST09-S05": "out-of-artifact",  # Unreachable Skill
    "AST09-S06": "out-of-artifact",  # Cascading Agent Compromise
    "AST09-S07": "out-of-artifact",  # Manipulated Trust Signals
}

STATIC_DETECTABLE: set[str] = static_detectable(SCENARIO_TIERS)

# No mechanical check ships for this category, so there is nothing whose coverage
# could be claimed. An empty CHECK_COVERAGE yields F1_SCOPE 'none', which is the
# label f1_report returns alongside its declared-and-uncovered status.
CHECK_COVERAGE: dict[str, dict] = {}

F1_SCOPE: str = _f1_scope(CHECK_COVERAGE)

#: Empty on purpose. See the module docstring: zero static-detectable scenarios
#: means zero detector functions, and a category with an empty detectable tier
#: publishes no F1 rather than padding a corpus to manufacture one.
DETECTORS: dict[str, Callable[[dict], Finding]] = {}


def run_all(pkg: dict) -> list[Finding]:
    return _run_all(DETECTORS, pkg)


def f1_report(fixtures: list[tuple[dict, set[str]]] | None = None) -> dict:
    return _f1_report(STATIC_DETECTABLE, DETECTORS, fixtures, F1_SCOPE)
