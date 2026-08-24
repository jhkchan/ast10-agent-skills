"""detectors/scaffold.py — shared per-skill detector scaffolding.

Every ``skills/AST0X/scripts/detector.py`` module duplicated an identical
``Finding`` dataclass, ``STATIC_DETECTABLE`` derivation, ``run_all()``, and a
byte-identical ``f1_report()`` (code-review finding: reuse, HIGH). This
module is the single source of that scaffolding; each skill module now
imports it and exports only its own ``SCENARIO_TIERS`` + ``DETECTORS`` map
plus its own ``detect_*`` functions.

``f1_report``'s zero-denominator convention matches ``detectors/engine.py``'s
``run_category`` (0.0, not 1.0) rather than silently reporting a perfect F1
for a corpus where nothing was detected (code-review finding: correctness,
MEDIUM -- a category's own precision/recall must never default to "perfect"
just because tp+fp or tp+fn happened to be zero).

Also carries ``detect_invisible_unicode_smuggling``, the zero-width/bidi
control code point scan that was duplicated verbatim between AST04 and AST08
(code-review finding: reuse, MEDIUM) -- both skills now share the regex and
scan logic and supply only their own scenario id.

CHECK COVERAGE -- the symmetry axis (tier-doctrine integrity, HIGH)
-------------------------------------------------------------------
A module's ``SCENARIO_TIERS`` maps ``scenarios/registry.yaml``'s canonical
scenario ids to the tier the registry assigns them, and says nothing whatever
about any individual check. Whether a check is mechanical, and whether it
decides a named whitepaper scenario, are two further claims that belong to the
check and not to the tier table; collapsing any of the three is how the same
package-decidable predicate came to be read as scenario coverage inside a
detector module while
``scenarios/registry.yaml`` recorded it as an ``artifact_signal`` -- a proxy
that the registry's own ``defining_condition_rule`` says "is never counted as
coverage of the scenario".

Every module therefore also declares ``CHECK_COVERAGE``, using the SAME
vocabulary ``fixtures/manifest.yaml`` already uses for its labeled corpora:

  full                  the check decides the linked registry scenario's
                        defining condition; every linked scenario must be
                        tiered ``static-detectable`` by the registry.
  artifact-signal-only  the check computes an enabling precondition the
                        registry declares as some scenario's
                        ``artifact_signal``. Package-decidable, never
                        coverage. Linked scenarios must NOT be
                        static-detectable and must declare an
                        ``artifact_signal``.
  category-precondition the check derives from a category's preventive
                        mitigations and decides no named scenario at all;
                        ``registry_ids`` is empty and a ``derivation`` is
                        required.

``f1_scope`` folds those modes into the single label that must travel with any
published number, so an F1 computed over proxies can never be read as an F1
over scenarios. ``f1_report`` refuses to return a number without it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

VALID_CHECK_TIERS = frozenset({"static-detectable", "agent-judgable", "out-of-artifact"})
VALID_COVERS = frozenset({"full", "artifact-signal-only", "category-precondition"})

#: The scope label an F1 computed from a given set of `covers` modes may carry.
_SCOPE_BY_MODES = {
    frozenset(): "none",
    frozenset({"full"}): "scenario-level",
    frozenset({"artifact-signal-only"}): "artifact-signal-only",
    frozenset({"category-precondition"}): "category-precondition",
}


@dataclass
class Finding:
    scenario: str
    detected: bool
    evidence: str = ""


def static_detectable(scenario_tiers: dict[str, str]) -> set[str]:
    """The static-detectable subset of a module's SCENARIO_TIERS.

    ``SCENARIO_TIERS`` is keyed by ``scenarios/registry.yaml``'s canonical
    scenario ids, so what comes back is a set of SCENARIO ids -- the registry's
    static-detectable tier for that category, and nothing else.
    """
    return {s for s, tier in scenario_tiers.items() if tier == "static-detectable"}


def scenario_detectors(
    detectors: dict[str, Callable[[dict], Finding]],
    check_coverage: dict[str, dict],
) -> dict[str, Callable[[dict], Finding]]:
    """A module's checks re-keyed onto the registry scenarios they DECIDE.

    Two namespaces meet in ``f1_report`` and they are not the same one.
    ``SCENARIO_TIERS`` (and therefore ``STATIC_DETECTABLE``, the F1 denominator)
    is keyed by registry scenario id; ``DETECTORS`` is keyed by the module's own
    check ids, and the mapping between them is neither total nor one-to-one.
    ``AST06-S01``'s defining condition is a disjunction that two checks
    implement between them, and most checks in this repository decide no named
    scenario at all. Scoring raw check ids against a scenario-id denominator
    would score ``tp=0`` on a corpus a working detector labels perfectly,
    because ``"AST06-host-persistence-write"`` is not ``"AST06-S01"``.

    Only ``covers: full`` checks are folded in, and that is the tier doctrine
    rather than an implementation convenience: a proxy is never coverage of the
    scenario it proxies, so an ``artifact-signal-only`` or
    ``category-precondition`` check may not put a true positive in a scenario's
    column. A scenario several checks decide between them is detected when any
    one of them fires, and the firing check's own evidence travels with it.

    Modules whose checks already carry registry ids (AST08, AST10) get the
    identity mapping back, so passing the result to ``f1_report`` changes
    nothing for them.
    """
    by_scenario: dict[str, list[str]] = {}
    for check, entry in check_coverage.items():
        if entry.get("covers") != "full" or check not in detectors:
            continue
        for scenario_id in entry.get("registry_ids") or []:
            by_scenario.setdefault(scenario_id, []).append(check)

    def _decide(scenario_id: str, checks: tuple[str, ...]) -> Callable[[dict], Finding]:
        def run(pkg: dict) -> Finding:
            findings = [(check, detectors[check](pkg)) for check in checks]
            for check, finding in findings:
                if finding.detected:
                    return Finding(scenario_id, True, f"{check}: {finding.evidence}")
            return Finding(scenario_id, False, "; ".join(f"{c}: {f.evidence}" for c, f in findings))

        return run

    return {scenario_id: _decide(scenario_id, tuple(checks)) for scenario_id, checks in by_scenario.items()}


def f1_scope(check_coverage: dict[str, dict]) -> str:
    """The honest scope label for an F1 computed over these checks.

    Mirrors ``fixtures/manifest.yaml``'s per-category ``f1_scope`` exactly:
    a single mode names itself, a mixture is ``mixed-proxy``, and no checks
    at all is ``none``. A category whose every check is a proxy can still
    publish a number -- it just may never publish it as scenario coverage.
    """
    modes = frozenset(entry["covers"] for entry in check_coverage.values())
    return _SCOPE_BY_MODES.get(modes, "mixed-proxy")


def validate_check_coverage(check_coverage: dict[str, dict]) -> list[str]:
    """Structural violations in a module's CHECK_COVERAGE, one string each.

    Shape only -- the registry cross-check (does `full` link a scenario the
    registry actually tiers static-detectable? does `artifact-signal-only`
    link one that declares an ``artifact_signal``?) lives in
    ``tests/test_tier_doctrine_symmetry.py``, which is the only place both
    files are loaded at once.
    """
    violations: list[str] = []
    for check, entry in check_coverage.items():
        covers = entry.get("covers")
        if covers not in VALID_COVERS:
            violations.append(f"{check}: invalid covers {covers!r}")
            continue
        registry_ids = entry.get("registry_ids")
        if not isinstance(registry_ids, list):
            violations.append(f"{check}: registry_ids must be a list")
            continue
        if not str(entry.get("reason", "")).strip():
            violations.append(f"{check}: no written reason")
        if covers == "category-precondition":
            if registry_ids:
                violations.append(f"{check}: category-precondition must link no registry scenario")
            if not str(entry.get("derivation", "")).strip():
                violations.append(f"{check}: category-precondition must state a derivation")
        elif not registry_ids:
            violations.append(f"{check}: covers {covers!r} must link at least one registry scenario")
    return violations


def run_all(detectors: dict[str, Callable[[dict], Finding]], pkg: dict) -> list[Finding]:
    return [fn(pkg) for fn in detectors.values()]


def f1_report(
    static_detectable_scenarios: set[str],
    detectors: dict[str, Callable[[dict], Finding]],
    fixtures: list[tuple[dict, set[str]]] | None,
    scope: str = "none",
) -> dict:
    """Per-category F1 over the declared-detectable tier only (S-007, gate-4).

    ``fixtures`` is a list of (package, expected_detected_scenario_ids)
    pairs. A category whose declared-detectable tier is empty must never
    manufacture a number (S-003 / gate-4); it reports "declared-and-uncovered"
    instead.

    ``static_detectable_scenarios`` is the registry's static-detectable tier, so
    the ``detectors`` passed here must report findings in that same namespace --
    ``scenario_detectors(DETECTORS, CHECK_COVERAGE)`` is how a module whose
    checks carry their own slugs supplies them. Handing this the raw check map
    when the two namespaces differ scores every case a false negative.

    ``scope`` is the module's ``F1_SCOPE`` (see ``f1_scope``) and is returned
    alongside every number, so a proxy F1 cannot be quoted as coverage of a
    named scenario just because the caller dropped the label on the way out.
    """
    if not static_detectable_scenarios:
        return {"status": "declared-and-uncovered", "f1": None, "scope": "none"}

    tp = fp = fn = 0
    for pkg, expected in fixtures or []:
        expected = expected & static_detectable_scenarios
        detected = {f.scenario for f in run_all(detectors, pkg) if f.detected}
        tp += len(detected & expected)
        fp += len(detected - expected)
        fn += len(expected - detected)

    # Zero-denominator precision/recall report 0.0, matching
    # detectors/engine.py's run_category -- a corpus where nothing was
    # detected must never default to a "perfect" 1.0 score.
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "status": "measured",
        "scope": scope,
        "f1": f1,
        "precision": precision,
        "recall": recall,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


# --- shared AST04/AST08 detection: invisible-Unicode smuggling -------------
# Zero-width spaces/joiners and bidi control code points. Base rate matters
# here and it is high: a plain-text extraction of the whitepaper PDF made for
# this project carries 860 code points in this class, all of them typesetting
# artifacts rather than payloads. (Measured with this character class over
# that extraction; the whitepaper itself states no such count.) That is why
# every caller declares this scan a category precondition and never scenario
# coverage -- presence is a prompt to decode and re-scan, not a verdict.
# Explicit \uXXXX escapes on purpose: embedding the literal invisible glyphs
# in this file's own source would be exactly the smuggling risk this
# detector exists to catch, and would be silently unreadable in any diff.
INVISIBLE_UNICODE_RE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]")


def detect_invisible_unicode_smuggling(pkg: dict, scenario_id: str) -> Finding:
    """Scan a package's files (plus its manifest description) for invisible
    Unicode control code points. Shared by AST04 and AST08 -- each supplies
    only its own ``scenario_id`` so a code-point-range fix here can never
    leave one category's copy stale."""
    manifest_text = pkg.get("manifest", {}).get("description", "") or ""
    candidates = dict(pkg.get("files", {}))
    candidates["<manifest.description>"] = manifest_text
    for path, content in candidates.items():
        hits = INVISIBLE_UNICODE_RE.findall(content)
        if hits:
            codepoints = sorted({f"U+{ord(c):04X}" for c in hits})
            return Finding(
                scenario_id,
                True,
                f"{path}: {len(hits)} invisible code point(s) {codepoints}",
            )
    return Finding(scenario_id, False, "no invisible Unicode control code points found")


# --- shared permission-shape accessors -------------------------------------
#
# One skill package reaches the detectors through three different vocabularies
# and they are NOT interchangeable:
#
#   USF v1        `permissions.files.{read,write,deny_write}`, `permissions.shell`
#                 as a bare boolean, `permissions.network.allow` as a default-deny
#                 host list (schemas/usf-v1.schema.json).
#   detector      `permissions.{read,write,deny_write}`, `permissions.shell.allowed`,
#                 `permissions.network.policy` -- what `scripts/dogfood.py`'s
#                 `translate_permissions()` and `cli/lib/bridge.py` hand a detector.
#   frontmatter   bare booleans (`network: true`, `shell: true`) that SKILL.md
#                 files in the wild use and USF cannot express.
#
# Reading only one of the three is how `skills/AST03/coverage-matrix.md` came to
# record a check that "reports detected=True ... against a manifest that declares
# three deny_write entries": the module read `permissions.deny_write` and the
# manifest spelled it `permissions.files.deny_write`. These accessors read all
# three spellings so a check cannot be silently dead against a conformant
# manifest, and so a detector never has to guess which adapter ran upstream.

_GLOB_CHARS = "*?[]{}"


@dataclass(frozen=True)
class FileScopes:
    """A package's declared file scopes, whichever vocabulary declared them."""

    read: tuple[str, ...]
    write: tuple[str, ...]
    deny_write: tuple[str, ...]
    declares_deny_write: bool


def permissions(pkg: dict) -> dict:
    """The package's permissions block, or ``{}`` when it declares none."""
    manifest = pkg.get("manifest") or {}
    perms = manifest.get("permissions")
    return perms if isinstance(perms, dict) else {}


def _file_source(perms: dict) -> dict:
    files = perms.get("files")
    return files if isinstance(files, dict) else perms


def file_scopes(perms: dict) -> FileScopes:
    """Read/write/deny_write, from either the USF or the detector spelling.

    ``declares_deny_write`` is the *key's presence*, not its truthiness: USF
    requires the key precisely so that an author who grants nothing still has to
    state the floor, and ``deny_write: []`` is that statement. Treating an
    explicit empty floor as an absent one is what made the old check fire on
    every conformant manifest.
    """
    source = _file_source(perms)
    strings = lambda key: tuple(  # noqa: E731 - local, single-use
        entry for entry in (source.get(key) or []) if isinstance(entry, str)
    )
    return FileScopes(
        read=strings("read"),
        write=strings("write"),
        deny_write=strings("deny_write"),
        declares_deny_write="deny_write" in source,
    )


def shell_granted(perms: dict) -> bool:
    """True when the package declares shell execution, in any of the spellings.

    USF spells it ``shell: true``; the detector shape spells it
    ``shell: {"allowed": true}``; frontmatter in the wild spells it
    ``shell_exec: unrestricted``. The one value that must never read as a grant
    is an explicit closed declaration.
    """
    shell = perms.get("shell")
    if isinstance(shell, dict):
        return bool(shell.get("allowed"))
    if isinstance(shell, str):
        return shell.strip().lower() not in {"", "none", "false", "no", "off", "denied"}
    return bool(shell)


def network_allowlist(perms: dict) -> tuple[str, ...]:
    """The declared egress allowlist, or ``()`` when none is declared."""
    network = perms.get("network")
    if network is True:
        return ("*",)
    if not isinstance(network, dict):
        return ()
    return tuple(entry for entry in (network.get("allow") or []) if isinstance(entry, str))


def network_unbounded(perms: dict) -> bool:
    """True when egress is declared as *anything*, not as a bounded domain list.

    AST03's own preventive mitigation is the test: "adopt network allowlists
    scoped to specific domains, not a binary network: true/false". So a bare
    ``network: true``, a ``policy: allow-all``, and an allowlist entry carrying a
    glob all read as unbounded, while an enumerated host list -- including the
    empty list, which USF defines as no egress at all -- does not.
    """
    network = perms.get("network")
    if network is True:
        return True
    if not isinstance(network, dict):
        return False
    policy = str(network.get("policy") or "").strip().lower()
    if policy in {"allow-all", "allow_all", "any", "all", "*", "unrestricted"}:
        return True
    return any(any(ch in host for ch in _GLOB_CHARS) for host in network_allowlist(perms))
