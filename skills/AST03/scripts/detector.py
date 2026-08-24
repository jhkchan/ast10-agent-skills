"""AST03 -- Over-Privileged Skills detector.

AST03's one static-detectable scenario in ``scenarios/registry.yaml`` is
**AST03-S03 Identity File Backdoors**: "a skill requesting write access to
SOUL.md and MEMORY.md installs persistent behavioural backdoors". The registry's
own reason states the mechanism -- "a declared write permission naming
``SOUL.md``, ``MEMORY.md``, or ``AGENTS.md`` ... is a pure structural check on
the manifest" -- and the whitepaper's preventive-mitigation list states the
control: "Flag skills requesting write access to agent identity files (SOUL.md,
MEMORY.md, AGENTS.md) for elevated review."

``detect_identity_file_write_grant`` is that check, and it is the only one in
this module that claims coverage of a named scenario. The other three say what
they are instead:

* ``detect_shell_network_privilege_combo`` and ``detect_wildcard_network_egress``
  compute ``artifact_signal``s the registry declares on AST03-S01 and AST06-S02.
  Package-decidable, never coverage (see ``CHECK_COVERAGE``).
* ``detect_unbounded_write_scope`` derives from AST03's first preventive
  mitigation -- "require skills to declare a permission manifest (files,
  network, shell, tools) - reject skills without one" -- and decides no named
  scenario at all.

TWO NAMESPACES, AND WHICH TABLE HOLDS WHICH
-------------------------------------------
``SCENARIO_TIERS`` is keyed by ``scenarios/registry.yaml``'s canonical scenario
ids and carries the tier the registry assigns each one, verbatim. It enumerates
ALL FIVE of AST03's named scenarios, including the three the registry rules
out-of-artifact, and it never disagrees with the registry: the registry decides
tier, this table mirrors it.

It used to be keyed by this module's own check slugs instead, and every one of
the four shipped checks was listed there as ``static-detectable``. Anything
reading the table for a tier count therefore read "AST03 decides four
scenarios" -- ``cli/bin/cli.js list`` printed exactly that -- when the registry
rules ONE AST03 scenario static-detectable. That is a coverage overclaim on the
repo's most-run command, and re-keying is the fix.

Nothing check-keyed was lost in the move, because the per-check table already
existed: ``CHECK_COVERAGE`` below is keyed by CHECK id and says, for each
shipped check, which registry scenarios it bears on and what it claims over
them (``full`` / ``artifact-signal-only`` / ``category-precondition``). The two
tables answer different questions and neither substitutes for the other.

One id had no code behind it and is gone from both tables:
``AST03-task-scope-mismatch``, the module's old slug for "the grant is broader
than the skill's stated function". It was declared ``agent-judgable`` and
implemented by nothing. What it recorded is now stated where it belongs and
more precisely -- ``SCENARIO_TIERS["AST03-S01"] == "agent-judgable"``, the
registry's own ruling on the scenario it stood in for -- and adding it to
``CHECK_COVERAGE`` would have been a claim that this module computes a
predicate it does not compute. ``skills/AST03/coverage-matrix.md`` records the
same disposition.

SHAPE
-----
Permission fields are read through ``detectors.scaffold``'s accessors, which
understand all three vocabularies one package reaches a detector in: USF v1
(``permissions.files.deny_write``, ``permissions.shell`` as a boolean,
``permissions.network.allow``), the flattened detector shape that
``scripts/dogfood.py::translate_permissions`` and ``cli/lib/bridge.py`` produce,
and the bare-boolean SKILL.md frontmatter shorthand. Reading only the flattened
spelling is what made the previous ``deny_write`` check report
``detected=True`` against this repository's own AST03 manifest, which declares
three ``deny_write`` entries -- a false positive on every conformant package,
recorded in ``skills/AST03/coverage-matrix.md`` and closed here.
"""

from __future__ import annotations

import fnmatch
from typing import Callable

from detectors.scaffold import (
    Finding,
    file_scopes,
    network_allowlist,
    network_unbounded,
    permissions,
    scenario_detectors,
    shell_granted,
    static_detectable,
)
from detectors.scaffold import f1_report as _f1_report
from detectors.scaffold import f1_scope as _f1_scope
from detectors.scaffold import run_all as _run_all

#: Agent identity files, verbatim from AST03's preventive mitigation. Kept in
#: sync with ``validators/usf.py::IDENTITY_FILES``, which the USF semantic pass
#: uses for the same three names; asserted equal in the module's tests so the
#: two lists cannot drift.
IDENTITY_FILES: tuple[str, ...] = ("SOUL.md", "MEMORY.md", "AGENTS.md")

_GLOB_CHARS = "*?[]"

#: Tiers keyed by ``scenarios/registry.yaml``'s canonical scenario ids, all five
#: of them, with the registry's tier for each. The registry is authoritative and
#: this map mirrors it; ``test_the_registry_is_the_authority_for_these_five_tiers``
#: in this directory's test module pins the two equal by construction, so a tier
#: cannot be invented, softened or omitted here.
SCENARIO_TIERS: dict[str, str] = {
    # Weather Assistant Data Exfiltration -- "far beyond what it needs" is a
    # purpose-versus-scope judgement; the same read scope is legitimate for a
    # credential-management skill.
    "AST03-S01": "agent-judgable",
    # Database Admin Wipe -- the defining event is an injected instruction
    # arriving at runtime in input the package does not contain.
    "AST03-S02": "out-of-artifact",
    # Identity File Backdoors -- the request IS the artifact: a declared write
    # permission naming SOUL.md / MEMORY.md / AGENTS.md.
    "AST03-S03": "static-detectable",
    # Logic-layer Injection of Privileged Actions (LPCI) -- payload and
    # permission-evaluation granularity both live outside the package.
    "AST03-S04": "out-of-artifact",
    # Low-Privilege Skill Invokes a High-Privilege Skill -- spans two packages
    # plus the host's inter-skill trust configuration.
    "AST03-S05": "out-of-artifact",
}

#: The registry's static-detectable tier for AST03: a set of SCENARIO ids, and
#: the F1 denominator. Deliberately NOT the set of shipped checks -- three of
#: the four checks below are mechanical and decide no named scenario, which is
#: what ``CHECK_COVERAGE`` records and what keeps them out of this set.
STATIC_DETECTABLE: set[str] = static_detectable(SCENARIO_TIERS)

# What each mechanical check actually COVERS, in fixtures/manifest.yaml's own
# vocabulary, keyed by CHECK id -- the id a Finding carries, the id
# fixtures/manifest.yaml's `detector_check` names, and the id
# config/dogfood_waivers.yml matches on. SCENARIO_TIERS above says what the
# registry rules about a scenario; this says which scenarios a shipped check
# bears on and what it claims over them. Both halves are needed, or a tier
# reads as a coverage claim it does not make.
CHECK_COVERAGE: dict[str, dict] = {
    "AST03-identity-file-write-grant": {
        "registry_ids": ["AST03-S03"],
        "covers": "full",
        "reason": (
            "AST03-S03 Identity File Backdoors is tiered static-detectable on exactly this "
            "predicate: a declared write permission naming SOUL.md, MEMORY.md or AGENTS.md "
            "that deny_write does not shadow. The check evaluates USF's most-specific-wins "
            "precedence (deny_write beats write) over the package's own manifest and reads "
            "nothing outside it, so it decides the scenario rather than proxying it."
        ),
    },
    "AST03-unbounded-write-scope": {
        "registry_ids": [],
        "covers": "category-precondition",
        "derivation": (
            "AST03's first preventive mitigation -- 'require skills to declare a permission "
            "manifest (files, network, shell, tools) - reject skills without one' -- not "
            "AST03-S03, whose defining condition names the identity-file paths that "
            "detect_identity_file_write_grant reads and this check does not."
        ),
        "reason": (
            "The check fires when no write floor is declared at all: no permissions block, "
            "or a files block with no deny_write key. It is deliberately blind to the "
            "CONTENT of a declared floor, so a manifest with deny_write: ['/etc/hosts'] "
            "passes it while SOUL.md stays writable -- that case is AST03-S03's and is "
            "decided by the identity-file check. An explicitly empty deny_write is a stated "
            "floor, not an absent one (schemas/usf-v1.schema.json requires the key for "
            "exactly that reason), so it does not fire."
        ),
    },
    "AST03-shell-network-privilege-combo": {
        "registry_ids": ["AST03-S01", "AST06-S02"],
        "covers": "artifact-signal-only",
        "reason": (
            "Shell execution together with unbounded egress is breadth, not mismatch. Its "
            "two conjuncts are exactly the artifact_signals the registry declares on "
            "AST03-S01 ('unrestricted shell ... alongside a narrow stated function') and "
            "AST06-S02 ('a manifest declaring network: true or policy: allow-all rather "
            "than a domain allowlist'). Both are package-decidable and neither is "
            "decidable-as-the-scenario: AST03-S01 turns on a purpose-versus-scope judgement "
            "and AST06-S02 on the host's sandbox and co-located services."
        ),
    },
    "AST03-wildcard-network-egress": {
        "registry_ids": ["AST06-S02"],
        "covers": "artifact-signal-only",
        "reason": (
            "An egress declaration that is a blanket rather than an enumerated domain list "
            "is verbatim AST06-S02's declared artifact_signal, and AST03's own mitigation "
            "asks for the same shape ('adopt network allowlists scoped to specific domains, "
            "not a binary network: true/false'). The registry tiers AST06-S02 "
            "out-of-artifact because the pivot depends on the host's sandbox and co-located "
            "services, so a blanket policy is a precondition and never the scenario."
        ),
    },
}

F1_SCOPE: str = _f1_scope(CHECK_COVERAGE)


# --------------------------------------------------------------------------- helpers


def _normalize(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    return normalized[2:] if normalized.startswith("./") else normalized


def _basename(path: str) -> str:
    return _normalize(path).rstrip("/").rsplit("/", 1)[-1]


def _write_entry_reaches(entry: str, identity_file: str) -> bool:
    """Does one declared ``write`` entry put ``identity_file`` in reach?

    Three shapes count, and nothing else does:

    * the entry names the file (``SOUL.md``, ``./SOUL.md``, ``memory/SOUL.md``) --
      the literal shape USF v1 permits, since it forbids globs in path lists;
    * a glob that matches the file at the package root (``*.md``, ``SOUL.*``);
    * a recursive grant rooted at the package or the home directory (``**``,
      ``./**``, ``~/**``), which reaches every path beneath it.

    A scoped recursive grant such as ``/secrets/**`` does NOT reach it. That
    distinction is the whole point: a broad write scope is a different finding
    (see ``detect_unbounded_write_scope``) from a write that names the agent's
    identity.
    """
    normalized = _normalize(entry)
    if not normalized:
        return False
    if _basename(normalized) == identity_file:
        return True
    if not any(ch in normalized for ch in _GLOB_CHARS):
        return False
    for candidate in (identity_file, f"./{identity_file}", f"~/{identity_file}", f"/{identity_file}"):
        if fnmatch.fnmatch(_normalize(candidate), normalized):
            return True
    if normalized.endswith("**"):
        return normalized[:-2].rstrip("/") in ("", ".", "~")
    return False


def _deny_shadows(deny_write: tuple[str, ...], identity_file: str) -> bool:
    """USF precedence: ``deny_write`` beats ``write``, bare filenames deny everywhere.

    Mirrors ``validators/usf.py::_write_allowed`` so a manifest the USF validator
    calls protected is not reported as exposed here.
    """
    for entry in deny_write:
        normalized = _normalize(entry)
        if _basename(normalized) == identity_file:
            return True
        if normalized.endswith("**") and normalized[:-2].rstrip("/") in ("", ".", "~"):
            return True
    return False


# ------------------------------------------------------------------------- checks


def detect_identity_file_write_grant(pkg: dict) -> Finding:
    """AST03-S03: a write grant reaching SOUL.md / MEMORY.md / AGENTS.md.

    The scenario is the *request*. A package that names an identity file in
    ``permissions.files.write`` and does not shadow it in ``deny_write`` has asked
    for the ability to rewrite the agent rather than its data -- which is why
    ``validators/usf.py::derive_risk_tier`` puts the same grant at L3,
    "destructive by definition".
    """
    perms = permissions(pkg)
    scopes = file_scopes(perms)
    granted: list[str] = []
    for identity_file in IDENTITY_FILES:
        reaching = [entry for entry in scopes.write if _write_entry_reaches(entry, identity_file)]
        if reaching and not _deny_shadows(scopes.deny_write, identity_file):
            granted.append(f"{identity_file} via write entry {reaching[0]!r}")
    if granted:
        return Finding(
            "AST03-identity-file-write-grant",
            True,
            "declared write reaches agent identity file(s): " + "; ".join(granted),
        )
    if not scopes.write:
        return Finding(
            "AST03-identity-file-write-grant",
            False,
            "no write scope declared, so no identity file is reachable",
        )
    return Finding(
        "AST03-identity-file-write-grant",
        False,
        f"{len(scopes.write)} write entr(y/ies) declared, none reaching {list(IDENTITY_FILES)} "
        f"(deny_write shadows {len(scopes.deny_write)} path(s))",
    )


def detect_unbounded_write_scope(pkg: dict) -> Finding:
    """No declared write floor at all -- the category precondition, not AST03-S03.

    ``deny_write: []`` is a stated floor and passes. A missing key, or a package
    with no permission manifest whatsoever, is what the mitigation rejects.
    """
    perms = permissions(pkg)
    if not perms:
        return Finding(
            "AST03-unbounded-write-scope",
            True,
            "no permissions block at all: the package declares no files/network/shell scope",
        )
    scopes = file_scopes(perms)
    if not scopes.declares_deny_write:
        return Finding(
            "AST03-unbounded-write-scope",
            True,
            "permissions declares no deny_write key: no write floor survives a port to a "
            "runtime whose default is write-everything",
        )
    return Finding(
        "AST03-unbounded-write-scope",
        False,
        f"write floor declared: deny_write lists {len(scopes.deny_write)} path(s)",
    )


def detect_shell_network_privilege_combo(pkg: dict) -> Finding:
    """Shell execution *and* unbounded egress: an execution primitive plus a channel.

    Proxy only. See ``CHECK_COVERAGE``: this is AST03-S01's and AST06-S02's
    declared ``artifact_signal``, never either scenario.
    """
    perms = permissions(pkg)
    shell = shell_granted(perms)
    unbounded = network_unbounded(perms)
    detected = shell and unbounded
    return Finding(
        "AST03-shell-network-privilege-combo",
        detected,
        f"shell_granted={shell} network_unbounded={unbounded} allowlist={list(network_allowlist(perms))}",
    )


def detect_wildcard_network_egress(pkg: dict) -> Finding:
    """Egress declared as a blanket rather than an enumerated domain allowlist.

    Proxy only: AST06-S02's declared ``artifact_signal``. An empty allowlist is
    no egress under USF default-deny and does not fire.
    """
    perms = permissions(pkg)
    unbounded = network_unbounded(perms)
    allowlist = list(network_allowlist(perms))
    network = perms.get("network")
    policy = network.get("policy") if isinstance(network, dict) else network
    if unbounded:
        return Finding(
            "AST03-wildcard-network-egress",
            True,
            f"egress is not a bounded domain allowlist: allow={allowlist} policy={policy!r}",
        )
    return Finding(
        "AST03-wildcard-network-egress",
        False,
        f"egress is a bounded allowlist of {len(allowlist)} host(s): {allowlist}",
    )


DETECTORS: dict[str, Callable[[dict], Finding]] = {
    "AST03-identity-file-write-grant": detect_identity_file_write_grant,
    "AST03-unbounded-write-scope": detect_unbounded_write_scope,
    "AST03-shell-network-privilege-combo": detect_shell_network_privilege_combo,
    "AST03-wildcard-network-egress": detect_wildcard_network_egress,
}


def run_all(pkg: dict) -> list[Finding]:
    return _run_all(DETECTORS, pkg)


def f1_report(fixtures: list[tuple[dict, set[str]]]) -> dict:
    """F1 over the registry's static-detectable tier, in registry ids.

    ``STATIC_DETECTABLE`` is a set of SCENARIO ids while ``DETECTORS`` is keyed
    by this module's check slugs, so the raw check map cannot be scored against
    it -- ``"AST03-identity-file-write-grant"`` is not ``"AST03-S03"`` and every
    case would come back a false negative. ``scenario_detectors`` folds the
    ``covers: full`` checks onto the scenarios they decide, which is also the
    tier doctrine: the two proxy checks and the category precondition never put
    a true positive in a scenario's column. ``fixtures`` therefore carries
    expected sets of registry scenario ids.
    """
    return _f1_report(
        STATIC_DETECTABLE,
        scenario_detectors(DETECTORS, CHECK_COVERAGE),
        fixtures,
        F1_SCOPE,
    )
