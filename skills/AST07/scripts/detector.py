"""AST07 -- Update Drift detector.

Scenario tiers are `scenarios/registry.yaml`'s, keyed by its canonical ids.
This table used to name only two scenarios under local slugs
(`AST07-rollback-attack`, `AST07-hot-reload-abuse`) and omitted AST07-S01
Malicious Update entirely, so a reader checking the module alone would have
concluded AST07 has two scenarios. It has three; the whitepaper's table of
contents and its body agree on that count.

All three require version/release history or host runtime state that lives
outside a single skill package snapshot:

- AST07-S01 Malicious Update: "update" is a relation between two versions and
  "compromised account" is registry-side state. A single package cannot show
  that it differs maliciously from a predecessor it does not contain.
- AST07-S02 Rollback Attack: detecting a downgrade to a known-vulnerable prior
  version requires the release timeline to compare against; a lone package
  snapshot has no "previous version" to be a rollback of.
- AST07-S03 Hot-Reload Abuse: detecting abuse of a live reload path requires
  the host's reload-event history; the package at rest is identical before and
  after the swap.

The absent-hash and unpinned-range preconditions the registry records as
AST07-S01's and AST07-S02's `artifact_signal` ARE decidable from the package
-- `skills/AST01/scripts/detector.py`'s `AST01-content-hash-missing` reads the
first of them -- and are never coverage of these scenarios. They therefore
change nothing here: this category's static-detectable tier stays empty.

Because that tier is empty, gate-4 requires `f1_report` to publish no F1 at
all rather than manufacture one: this module ships zero detector functions and
reports "declared-and-uncovered" (S-003).

ZERO DETECTORS IS THE RESULT, NOT A GAP
---------------------------------------
Re-verified against the finalised `scenarios/registry.yaml`: AST07 has three
named scenarios and the registry tiers all three `out-of-artifact`, so the
static-detectable tier is empty and there is no scenario here for a
deterministic rule to decide. An empty `DETECTORS` map in this module is
therefore a finished state, not an unimplemented one, and it is the only state
that stays honest: writing a check on the absent-hash or unpinned-range
preconditions and filing it under an AST07 scenario id is exactly the overclaim
the registry's `defining_condition_rule` forbids, and doing it to make a
coverage table look complete would be worse than the empty column.

The guard against this becoming stale is
`test_s001_detector_registry_matches_declared_detectable_tier` together with
`test_the_registry_is_the_authority_for_those_three_tiers`: the first pins
`DETECTORS` to the module's static-detectable set, the second pins the module's
tiers to the registry by equality. If the registry ever promotes an AST07
scenario, the pair fails and a detector is owed -- loudly, in the same change.
"""

from __future__ import annotations

from typing import Callable

from detectors.scaffold import Finding, static_detectable
from detectors.scaffold import f1_report as _f1_report
from detectors.scaffold import f1_scope as _f1_scope
from detectors.scaffold import run_all as _run_all

SCENARIO_TIERS: dict[str, str] = {
    "AST07-S01": "out-of-artifact",  # Malicious Update
    "AST07-S02": "out-of-artifact",  # Rollback Attack
    "AST07-S03": "out-of-artifact",  # Hot-Reload Abuse
}

STATIC_DETECTABLE: set[str] = static_detectable(SCENARIO_TIERS)

# No mechanical check ships for this category, so there is nothing whose coverage
# could be claimed. An empty CHECK_COVERAGE yields F1_SCOPE 'none', which is the
# label f1_report returns alongside its declared-and-uncovered status.
CHECK_COVERAGE: dict[str, dict] = {}

F1_SCOPE: str = _f1_scope(CHECK_COVERAGE)

DETECTORS: dict[str, Callable[[dict], Finding]] = {}


def run_all(pkg: dict) -> list[Finding]:
    return _run_all(DETECTORS, pkg)


def f1_report(fixtures: list[tuple[dict, set[str]]] | None = None) -> dict:
    return _f1_report(STATIC_DETECTABLE, DETECTORS, fixtures, F1_SCOPE)
