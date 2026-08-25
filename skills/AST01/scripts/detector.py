"""AST01 -- Malicious Skills detector.

Ten mechanical checks over one skill package's own bytes. Seven of them decide
a named AST01 scenario that ``scenarios/registry.yaml`` tiers
``static-detectable``; one decides AST08-S02, a scenario the whitepaper files
under another category but whose defining condition is a property of *this*
package's bundled scripts; and two are the pre-existing content-hash controls,
which decide no named scenario at all and say so in ``CHECK_COVERAGE``.

TWO TABLES, TWO NAMESPACES
--------------------------
``SCENARIO_TIERS`` mirrors ``scenarios/registry.yaml``: every one of AST01's
ELEVEN canonical scenario ids mapped to the tier the registry assigns it, and
nothing else. It describes the whitepaper's attack surface, not this file's
code, so it reads seven static-detectable, three agent-judgable and one
out-of-artifact however many checks happen to ship below. Keyed by check id --
which is how it used to be keyed -- ``node cli/bin/cli.js list`` printed
``AST01 [static-detectable x10]`` and told a reader this category decides ten
scenarios where the registry rules seven.

``CHECK_COVERAGE`` is the per-CHECK table: one entry per mechanical check,
keyed by check id, naming the registry scenarios the check bears on and what
it claims over them (``full`` / ``artifact-signal-only`` /
``category-precondition``). The two namespaces cannot be collapsed into one
the way AST08's and AST10's can, because three of the ten checks decide no
AST01 scenario at all: the two content-hash controls and the AST08-S02
obfuscation check. ``detectors/scaffold.py``'s ``scenario_detectors`` is the
join between them, and it is what ``f1_report`` scores over.

The old check-keyed table also carried one key that is neither a check nor a
scenario: ``AST01-obfuscated-payload-intent``, a local slug recording that
judging a decoded payload's *intent* -- malicious rather than merely unusual --
is semantic work no byte match does. No function ever computed it, so it is not
a check and has no ``CHECK_COVERAGE`` entry, and it is not a canonical registry
id, so it cannot stay in ``SCENARIO_TIERS``. Both halves of what it said
survive: ``detect_obfuscated_payload_exec`` decides only the mechanical half (a
decoded blob reaching an execution sink) and its ``CHECK_COVERAGE`` entry says
so, and AST01's genuinely judged surface is now stated outright and by name --
AST01-S01 Typosquatting, AST01-S03 Instruction Override, AST01-S04 ClickFix
Prompts -- instead of being represented by one invented slug.

WHAT EACH CHECK IS ANCHORED TO
------------------------------
Every rule below is the mechanism the whitepaper describes, not a keyword
grep. Each one is a *two-part* predicate -- a construct plus a contradiction
of the package's own declaration -- because that is what separates a
malicious skill from a skill that merely mentions the same words:

  AST01-S02  a remote-fetch-piped-to-a-shell command in the package's prose
             whose destination host the manifest's egress allowlist does not
             declare. An install line pointing at a declared host is the same
             syntax and is *not* this scenario.
  AST01-S05  a write to the agent identity file: a granted write scope under
             `deny_write`-wins evaluation, or a bundled script opening that
             path for write.
  AST01-S06  the same mechanism against the memory file.
  AST01-S08  a bundled script that reads an identity artifact AND carries an
             outbound send. Either half alone is not the scenario.
  AST01-S09  a WebSocket-scheme URL in a bundled script against a host the
             manifest's allowlist does not declare.
  AST01-S10  an egress call site in a bundled script whose hardcoded
             destination host the manifest does not declare -- the in-package
             diff between what the code does and what the manifest promises.
             A package that declares no egress policy at all has promised
             nothing to contradict, so it is a precondition (AST03's and
             AST06's) rather than this scenario; and a loopback destination
             is not egress at all, declared or not.
  AST01-S11  a concealment carrier (invisible control code points, or a
             base64 blob that decodes to text) inside the package's OUTPUT
             templates -- content the skill returns, not content it ships.
  AST08-S02  an encoded blob decoded and handed to an execution sink, with a
             bounded decode-then-rescan of the payload.

The two content-hash checks keep their prior meaning: an absent digest is the
enabling precondition `scenarios/registry.yaml` declares as the artifact_signal
of AST05-S01 and AST07-S01 and is never coverage of either; a declared digest
that contradicts the shipped bytes is a category precondition drawn from
AST02's signing mitigation. `CHECK_COVERAGE` records both non-claims.

MANIFEST SHAPES
---------------
One package reaches this module through three vocabularies (USF v1, the
flattened detector shape `scripts/dogfood.py` produces, and bare-boolean
SKILL.md frontmatter). Permission reads therefore go through
``detectors.scaffold``'s shared accessors and through ``validators.usf``'s own
`deny_write`-wins and default-deny evaluators rather than through a private
re-parse -- the "shape adapter" gap `skills/AST01/coverage-matrix.md` used to
record against the content-hash pair is closed the same way, by accepting the
USF `content_hash` string form alongside the mapping form.

A "skill package" is the dict shape this module operates on::

    {
      "manifest": {
          "permissions": {...},
          "content_hash": "sha256:<hex>" | {"algorithm": ..., "value": ...} | None,
      },
      "files": {"<relative/path>": "<text content>", ...},
    }
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from typing import Callable, NamedTuple

from detectors.scaffold import (
    INVISIBLE_UNICODE_RE,
    Finding,
    file_scopes,
    network_allowlist,
    network_unbounded,
    permissions,
    scenario_detectors,
    static_detectable,
)
from detectors.scaffold import f1_report as _f1_report
from detectors.scaffold import f1_scope as _f1_scope
from detectors.scaffold import run_all as _run_all
from validators.usf import network_egress_allowed, write_allowed

#: AST01's eleven canonical scenarios and the tier `scenarios/registry.yaml`
#: assigns each one, verbatim and complete -- including the three it judges and
#: the one it puts out of reach. Keyed by registry id, never by check id: this
#: table is a statement about the whitepaper's attack surface, not about the
#: code below it, and `tests/test_coverage_matrix_ast01_ast03.py` reads the
#: registry as the authority on every row.
SCENARIO_TIERS: dict[str, str] = {
    "AST01-S01": "agent-judgable",  # Typosquatting
    "AST01-S02": "static-detectable",  # Social Engineering Prerequisites
    "AST01-S03": "agent-judgable",  # Instruction Override
    "AST01-S04": "agent-judgable",  # ClickFix Prompts
    "AST01-S05": "static-detectable",  # SOUL.md Persistence
    "AST01-S06": "static-detectable",  # Memory Poisoning
    "AST01-S07": "out-of-artifact",  # Cognitive Degradation and Agent Drift
    "AST01-S08": "static-detectable",  # Identity Cloning and Impersonation
    "AST01-S09": "static-detectable",  # WebSocket Hijacking
    "AST01-S10": "static-detectable",  # Data Exfiltration
    "AST01-S11": "static-detectable",  # Hidden Prompt Injection in Skill Output
}

#: The seven AST01 scenarios the registry rules decidable from one package.
#: A set of SCENARIO ids -- see `SCORED_CHECKS` below for the F1 denominator,
#: which is a set of CHECK ids and is deliberately not the same set.
STATIC_DETECTABLE: set[str] = static_detectable(SCENARIO_TIERS)

# What each mechanical check actually COVERS, in fixtures/manifest.yaml's own
# vocabulary, keyed by CHECK id. `SCENARIO_TIERS` above says what the registry
# rules about a scenario; this says which scenarios a shipped check bears on
# and what it claims over them. Both halves are needed or a tier reads as a
# coverage claim it does not make.
CHECK_COVERAGE: dict[str, dict] = {
    "AST01-content-hash-missing": {
        "registry_ids": ["AST05-S01", "AST07-S01"],
        "covers": "artifact-signal-only",
        "reason": (
            "Absent content-hash pinning IS decidable by inspecting the package alone -- "
            "one field read -- and scenarios/registry.yaml declares exactly that predicate "
            "as the artifact_signal of AST05-S01 (Author Rug-Pull) and AST07-S01 (Malicious "
            "Update). It decides neither: a hash-pinned skill can still be maliciously "
            "updated once the operator accepts the new hash, and an unpinned one may never "
            "receive a malicious update at all. Package-decidable, never coverage."
        ),
    },
    "AST01-content-hash-mismatch": {
        "registry_ids": [],
        "covers": "category-precondition",
        "derivation": (
            "AST02's preventive mitigation 'have the signature cover a canonical digest of "
            "SKILL.md plus every declared resource file', not any named AST01 scenario."
        ),
        "reason": (
            "A declared digest that does not match the shipped bytes is a self-contained "
            "in-package contradiction -- both sides ship together and no off-artifact state "
            "is consulted. It maps to no named scenario in any category, so it is a category "
            "precondition rather than scenario coverage."
        ),
    },
    "AST01-social-engineering-prerequisites": {
        "registry_ids": ["AST01-S02"],
        "covers": "full",
        "reason": (
            "AST01-S02's defining condition is both halves in the package's own prose: an "
            "instruction to run a remote-fetch-piped-to-shell command, and the host it points "
            "at. The check decides exactly that pair, and clears an install line whose host "
            "the manifest's egress allowlist declares -- so it separates the scenario from "
            "the identical syntax used legitimately, rather than matching the syntax alone."
        ),
    },
    "AST01-soul-md-persistence": {
        "registry_ids": ["AST01-S05"],
        "covers": "full",
        "reason": (
            "AST01-S05 is a write to the agent identity file. The check decides two of the "
            "three structural facts the registry names -- a write scope that survives "
            "deny_write-wins evaluation, and a bundled script opening that path for write. "
            "The third disjunct the registry lists (an absent deny_write entry) is "
            "deliberately NOT treated as sufficient here and the reason is recorded in "
            "skills/AST01/coverage-matrix.md: it fires on every package that declares no "
            "permissions at all, which is AST06's missing-sandbox-declaration signal rather "
            "than a write to the identity file."
        ),
    },
    "AST01-memory-poisoning": {
        "registry_ids": ["AST01-S06"],
        "covers": "full",
        "reason": (
            "The same mechanism the registry gives AST01-S06 -- a declared write scope "
            "covering the memory file, or a bundled script writing to it -- against the "
            "memory path instead of the identity path. Kept as its own function rather than "
            "a parameterised alias so a future divergence between the two scenarios cannot "
            "be introduced silently in one shared branch."
        ),
    },
    "AST01-identity-clone-exfiltration": {
        "registry_ids": ["AST01-S08"],
        "covers": "full",
        "reason": (
            "AST01-S08 needs both halves and the registry says so: a read of a known "
            "identity-artifact path, and the outbound send that follows it. The check "
            "requires both in the same bundled script, so a skill that merely reads its own "
            "identity files and a skill that merely calls out to a declared host are each "
            "clear -- only the conjunction decides the scenario."
        ),
    },
    "AST01-websocket-c2": {
        "registry_ids": ["AST01-S09"],
        "covers": "full",
        "reason": (
            "A scheme-and-host match over the package's own source, which is the registry's "
            "own wording: a WebSocket-scheme URL opened by a bundled script against a host "
            "absent from the USF network allowlist. A declared relay host clears."
        ),
    },
    "AST01-undeclared-egress": {
        "registry_ids": ["AST01-S10"],
        "covers": "full",
        "reason": (
            "The in-package diff the registry names: an egress destination hardcoded in a "
            "bundled script and absent from the manifest's declared allowlist. Neither half "
            "alone fires -- a script with no egress call site and a script whose destinations "
            "the manifest declares are both clear. Because the scenario IS the diff, the check "
            "requires a declaration to diff against: a package with no permissions.network key "
            "has promised nothing, so nothing contradicts it, and convicting there would be "
            "convicting a named scenario on AST06's and AST03's precondition -- which this "
            "repository's own doctrine forbids a covers: full check from doing. Loopback "
            "destinations are excluded before the allowlist is read at all, because a packet "
            "that never leaves the machine is not egress whatever the manifest says."
        ),
    },
    "AST01-hidden-output-injection": {
        "registry_ids": ["AST01-S11"],
        "covers": "full",
        "reason": (
            "AST01-S11 is concealed instructions in the content the skill RETURNS, which is "
            "why the scan is scoped to the package's output templates -- fenced output blocks "
            "and template files -- rather than to the package's bytes at large. That scoping "
            "is exactly what keeps it distinct from AST04/AST08's shared invisible-Unicode "
            "carrier scan, which is declared a category-precondition there because it flags "
            "the carrier anywhere and decides no scenario."
        ),
    },
    "AST01-obfuscated-payload-exec": {
        "registry_ids": ["AST08-S02"],
        "covers": "full",
        "reason": (
            "AST08-S02 Obfuscated Instruction is tiered static-detectable on the encoded blob "
            "being in the package's bytes and decode-then-rescan being deterministic. This "
            "check performs that bounded decode and requires an execution sink, so it decides "
            "the scenario rather than flagging the presence of base64. The scenario is filed "
            "under AST08 by the whitepaper and the link is recorded here rather than "
            "reassigned: the artifact it is decided from is an AST01 skill package's own "
            "bundled script."
        ),
    },
}

F1_SCOPE: str = _f1_scope(CHECK_COVERAGE)


# --------------------------------------------------------------------------
# Shared package accessors
# --------------------------------------------------------------------------

_SCRIPT_SUFFIXES = (".py", ".sh", ".bash", ".zsh", ".js", ".mjs", ".ts", ".ps1", ".rb", ".pl")
_SHELL_SUFFIXES = (".sh", ".bash", ".zsh")
_MARKDOWN_SUFFIXES = (".md", ".markdown")
_TEMPLATE_SUFFIXES = (".tmpl", ".template", ".j2", ".mustache")


def _files_with_suffix(pkg: dict, *suffixes: str) -> dict[str, str]:
    files = pkg.get("files") or {}
    return {p: c for p, c in files.items() if isinstance(c, str) and p.lower().endswith(suffixes)}


def _declares_egress_policy(pkg: dict) -> bool:
    """Does the package state an egress policy AT ALL?

    Distinct from "is the allowlist empty", and the distinction is the whole
    point. USF v1 makes ``permissions.network.allow`` a required key precisely
    so that an author granting nothing still has to say so, and
    ``schemas/usf-v1.schema.json`` writes the reason on the sibling
    ``files`` block: "a declared-empty list and an absent list are the same
    thing to a permissive target runtime". They are not the same thing to a
    detector. ``allow: []`` is a promise of no egress, which a script calling
    out CONTRADICTS; an absent ``network`` key is no promise at all, which
    nothing can contradict.

    Presence of the key is the test, in any of the three vocabularies
    ``detectors/scaffold.py`` documents -- USF's ``network: {allow: [...]}``,
    the detector shape's ``network: {policy: ...}``, and frontmatter's bare
    ``network: true`` / ``network: false``. A frontmatter ``network: false`` is
    a declaration (of nothing) and is treated as one.
    """
    return "network" in permissions(pkg)


def _egress_declared(pkg: dict, host: str) -> bool:
    """Does the package's own manifest declare egress to ``host``?

    Default-deny evaluation is delegated to ``validators.usf`` so the detector
    and the validator cannot drift on what an allowlist means. The one thing
    added on top is the unbounded case: a manifest that declares egress to
    anything has not been contradicted by a script that calls out somewhere,
    and AST01-S10 is defined as the *contradiction*, so an unbounded
    declaration clears the host. (Unbounded egress is a real finding -- it is
    AST03's and AST06's, and their checks own it.)
    """
    perms = permissions(pkg)
    if network_unbounded(perms):
        return True
    return network_egress_allowed(pkg.get("manifest") or {}, host)


# --------------------------------------------------------------------------
# Where a hardcoded destination actually goes
# --------------------------------------------------------------------------
#
# An allowlist comparison presupposes that the destination is somewhere an
# allowlist could govern. Two classes of host literal are not, and reading
# either as "absent from the allowlist" is a category error rather than a
# tuning problem:
#
#   loopback     ``localhost``, ``127.0.0.0/8``, ``::1``, ``0.0.0.0``, and the
#                RFC 6761 s6.3 ``.localhost`` names, all of which the resolver
#                is REQUIRED to send back to the same machine. A packet that
#                never reaches a network cannot exfiltrate anything, so this
#                holds whether or not a manifest exists and whether or not the
#                allowlist happens to name the host. The observed false
#                positive was exactly this shape: a helper defaulting to
#                ``http://localhost:11434/api/chat``, Ollama's local API.
#   unqualified  a dotless, non-literal name -- ``ollama``, ``minio``, a
#                compose service name. Where it resolves is a property of the
#                RUNTIME's search domain, not of the package's bytes, so the
#                artifact does not decide it. Reported as undecided, which is
#                the same answer AST01-S02 already gives a ``curl $URL | sh``
#                with no literal host, and for the same reason.
#
# Everything else is a routable destination and goes to the allowlist.

_LOOPBACK = "loopback"
_UNQUALIFIED = "unqualified"
_ROUTABLE = "routable"

_IPV4_LITERAL_RE = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")
_IPV6_LOOPBACK_LITERALS = frozenset({"::1", "0:0:0:0:0:0:0:1"})


def _normalize_host(host: str) -> str:
    """A host literal reduced to the name an allowlist would be compared against.

    Strips a trailing port and root dot and lowercases. IPv6 needs two special
    cases, because ``host.split(":")[0]`` turns ``::1`` into the empty string:
    a bracketed host (``[::1]:8080``) is unwrapped first, and a bare literal is
    recognised by carrying more than one colon and left whole. No extractor in
    this module currently emits either form -- the URL host classes are
    ``[A-Za-z0-9._~-]+`` and match neither ``[`` nor ``:`` -- so both arms are
    defensive, and the IPv6 handling in ``_destination_class`` is reachable
    only through them.
    """
    host = host.strip().lower()
    if host.startswith("["):
        inside, _, _after = host[1:].partition("]")
        return inside.rstrip(".")
    if host.count(":") > 1:  # bare IPv6 literal, not host:port
        return host.rstrip(".")
    return host.split(":")[0].rstrip(".")


def _destination_class(host: str) -> str:
    """``loopback`` / ``unqualified`` / ``routable`` for one normalized host."""
    if host in _IPV6_LOOPBACK_LITERALS:
        return _LOOPBACK
    if host.startswith("::ffff:"):  # IPv4-mapped IPv6
        return _destination_class(host[len("::ffff:") :])
    if host == "localhost" or host == "localhost.localdomain" or host.endswith(".localhost"):
        return _LOOPBACK
    octets = _IPV4_LITERAL_RE.match(host)
    if octets:
        values = [int(part) for part in octets.groups()]
        if any(value > 255 for value in values):
            return _ROUTABLE  # not a valid literal; treat as a name, and names route
        # 127.0.0.0/8 is the whole loopback block, not just 127.0.0.1.
        # 0.0.0.0 is the unspecified address: as a *destination* every stack
        # sends it to this host.
        return _LOOPBACK if values[0] == 127 or values == [0, 0, 0, 0] else _ROUTABLE
    if "." not in host and ":" not in host:
        return _UNQUALIFIED
    return _ROUTABLE


class _Destinations(NamedTuple):
    """One script's hosts, split by what an allowlist can say about them.

    A ``NamedTuple`` and not a ``@dataclass`` on purpose, and the reason is a
    live one rather than a style preference. This module is loaded through
    ``importlib.util.spec_from_file_location`` by several callers and they do
    not agree on registration: ``detectors/fixture_loader.py`` and
    ``cli/lib/bridge.py`` assign ``sys.modules[spec.name]`` before
    ``exec_module``, ``scripts/dogfood.py`` does not. Under
    ``from __future__ import annotations``, ``@dataclass`` resolves its field
    annotations through ``sys.modules[cls.__module__].__dict__`` at
    class-creation time, so a dataclass here raises
    ``AttributeError: 'NoneType' object has no attribute '__dict__'`` inside
    dogfood -- which is how this was found. ``NamedTuple`` keeps its
    annotations as strings and does not look the module up. Fixing the loader
    instead would work; keeping the module loadable by every loader that
    already exists is the smaller claim.
    """

    undeclared: tuple[str, ...]  # routable AND absent from a declared allowlist
    loopback: tuple[str, ...]  # never left the machine; not egress at all
    unqualified: tuple[str, ...]  # not decidable from the package's own bytes


def _classify_hosts(pkg: dict, hosts) -> _Destinations:
    """Split host literals into the three answers an allowlist comparison has.

    Order matters: the destination class is settled BEFORE the allowlist is
    consulted, so a declared allowlist that omits ``localhost`` still does not
    make a loopback call exfiltration.
    """
    undeclared: list[str] = []
    loopback: list[str] = []
    unqualified: list[str] = []
    for raw in hosts:
        host = _normalize_host(raw)
        if not host:
            continue
        bucket = _destination_class(host)
        if bucket == _LOOPBACK:
            if host not in loopback:
                loopback.append(host)
        elif bucket == _UNQUALIFIED:
            if host not in unqualified:
                unqualified.append(host)
        elif host not in undeclared and not _egress_declared(pkg, host):
            undeclared.append(host)
    return _Destinations(tuple(undeclared), tuple(loopback), tuple(unqualified))


def _undeclared_hosts(pkg: dict, hosts) -> list[str]:
    """The routable destinations among ``hosts`` that no declaration covers."""
    return list(_classify_hosts(pkg, hosts).undeclared)


def _snippet(text: str, limit: int = 120) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


# --------------------------------------------------------------------------
# content_hash -- the two pre-existing, non-coverage checks
# --------------------------------------------------------------------------


def declared_content_hash(manifest: dict) -> str | None:
    """The declared digest as a bare hex string, from either spelling.

    USF v1 spells `content_hash` as the string ``sha256:<64 hex>``; the
    detector shape `scripts/dogfood.py` and `cli/lib/bridge.py` produce spells
    it ``{"algorithm": ..., "value": ...}``. Reading only the mapping form was
    the recorded reason the pair "does not run correctly against a real
    skill.usf.yaml"; both are read here so the gap cannot reopen.
    """
    declared = (manifest or {}).get("content_hash")
    if isinstance(declared, dict):
        value = declared.get("value")
        return value if isinstance(value, str) and value.strip() else None
    if isinstance(declared, str) and ":" in declared:
        _algorithm, _, value = declared.partition(":")
        return value.strip().lower() or None
    return None


def _package_digest(pkg: dict) -> str:
    """Deterministic sha256 over sorted (path, content) pairs.

    This is the "actual" side of the signed-content-hash comparison: the USF
    manifest declares an expected hash, and re-deriving it here the same way
    the signer must have is what makes a mismatch detectable rather than
    merely asserted. Framing matches scripts/content_hash.py's
    content_sha256 exactly -- sorted relative path, NUL, bytes, no trailing
    NUL after the content -- so a package hashed by this repo's own vendored
    hasher never spuriously reports content-hash-mismatch against a detector
    using different framing.
    """
    hasher = hashlib.sha256()
    files = pkg.get("files", {})
    for path in sorted(files):
        hasher.update(path.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(files[path].encode("utf-8"))
    return hasher.hexdigest()


def detect_content_hash_missing(pkg: dict) -> Finding:
    declared = declared_content_hash(pkg.get("manifest", {}))
    detected = not declared
    evidence = "manifest.content_hash.value is unset" if detected else "content_hash.value present"
    return Finding("AST01-content-hash-missing", detected, evidence)


def detect_content_hash_mismatch(pkg: dict) -> Finding:
    declared = declared_content_hash(pkg.get("manifest", {}))
    if not declared:
        # No hash to compare against -- that gap is content-hash-missing's job.
        return Finding("AST01-content-hash-mismatch", False, "no declared hash to compare")
    actual = _package_digest(pkg)
    detected = actual != declared
    evidence = f"declared={declared} actual={actual}" if detected else "hash matches package content"
    return Finding("AST01-content-hash-mismatch", detected, evidence)


# --------------------------------------------------------------------------
# AST01-S02 -- Social Engineering Prerequisites
# --------------------------------------------------------------------------
#
# The whitepaper's scenario is a SKILL.md "Prerequisites" section instructing
# the reader to copy-paste a terminal command that installs a "helper tool"
# from an attacker-controlled domain. The scan is therefore scoped to the
# package's PROSE (its markdown), which is where an instruction to a human
# lives; a bundled installer script is a different scenario and is decided by
# AST01-S10's egress check.
#
# Both halves must be present. A pipe-to-shell whose destination host the
# manifest declares is the same syntax used legitimately and does not decide
# the scenario; a command with no literal host (`curl $URL | sh`) leaves
# nothing to evaluate the allowlist against and is reported as undecided
# rather than guessed at.

_FETCH_PIPE_SHELL_RE = re.compile(
    r"(?:curl|wget)\b[^\n|]{0,400}\|\s{0,8}(?:sudo\s{1,8})?(?:/bin/)?(?:ba|z|k|a)?sh\b",
    re.IGNORECASE,
)
_POWERSHELL_FETCH_PIPE_RE = re.compile(
    r"(?:iwr|irm|invoke-webrequest|invoke-restmethod)\b[^\n|]{0,400}\|\s{0,8}(?:iex|invoke-expression)\b",
    re.IGNORECASE,
)
_PROCESS_SUBSTITUTION_RE = re.compile(
    r"\b(?:ba|z|k)?sh\b\s{0,8}<\(\s{0,8}(?:curl|wget)\b[^)\n]{0,400}\)",
    re.IGNORECASE,
)
_URL_HOST_RE = re.compile(r"https?://([A-Za-z0-9._~-]+(?::\d{1,5})?)", re.IGNORECASE)

_PIPE_TO_SHELL_FORMS = (
    (_FETCH_PIPE_SHELL_RE, "remote fetch piped to a shell"),
    (_POWERSHELL_FETCH_PIPE_RE, "remote fetch piped to Invoke-Expression"),
    (_PROCESS_SUBSTITUTION_RE, "shell reading a remote script through process substitution"),
)


def detect_social_engineering_prerequisites(pkg: dict) -> Finding:
    scenario = "AST01-social-engineering-prerequisites"
    undecided: list[str] = []
    for path, content in sorted(_files_with_suffix(pkg, *_MARKDOWN_SUFFIXES).items()):
        for regex, label in _PIPE_TO_SHELL_FORMS:
            for match in regex.finditer(content):
                command = match.group(0)
                hosts = _URL_HOST_RE.findall(command)
                if not hosts:
                    undecided.append(f"{path}: {label} with no literal host")
                    continue
                undeclared = _undeclared_hosts(pkg, hosts)
                if undeclared:
                    return Finding(
                        scenario,
                        True,
                        f"{path}: {label} to undeclared host(s) {undeclared}: {_snippet(command)}",
                    )
    if undecided:
        return Finding(
            scenario,
            False,
            f"undecided (no literal destination host to evaluate against the allowlist): {undecided[0]}",
        )
    return Finding(scenario, False, "no install instruction pipes a remote fetch into a shell")


# --------------------------------------------------------------------------
# AST01-S05 / AST01-S06 -- identity-file persistence and memory poisoning
# --------------------------------------------------------------------------

_IDENTITY_FILE = "SOUL.md"
_MEMORY_FILE = "MEMORY.md"


def _write_context_regexes(filename: str) -> tuple[tuple[re.Pattern[str], str], ...]:
    """Write-to-``filename`` patterns, each anchored on the filename itself.

    Anchoring matters: an unanchored "does this file mention a write verb"
    scan fires on any script that writes anything, and an unanchored "does
    this file name the identity path" scan fires on prose. Each pattern below
    requires the write construct and the path in one expression.
    """
    name = re.escape(filename)
    return (
        (
            re.compile(
                rf"open\s{{0,4}}\([^)\n]{{0,160}}?['\"][^'\"\n]{{0,200}}{name}['\"]\s{{0,4}},\s{{0,4}}['\"][wax]"
            ),
            "opened for write",
        ),
        (
            re.compile(
                rf"['\"][^'\"\n]{{0,200}}{name}['\"][^\n]{{0,160}}\.\s{{0,4}}(?:write_text|write_bytes|writelines)\s{{0,4}}\("
            ),
            "written through a pathlib write",
        ),
        (
            re.compile(
                rf"(?:appendFileSync|writeFileSync|createWriteStream|writeFile)\s{{0,4}}\(\s{{0,4}}['\"][^'\"\n]{{0,200}}{name}"
            ),
            "written through a filesystem write call",
        ),
        (
            re.compile(
                rf"(?:>>?|\btee\b(?:\s{{1,4}}-a)?|Add-Content|Set-Content|Out-File)\s{{0,4}}['\"]?[^\s;|&'\"\n]{{0,200}}{name}"
            ),
            "written through a shell redirect or append",
        ),
    )


_IDENTITY_WRITE_PATTERNS = {
    _IDENTITY_FILE: _write_context_regexes(_IDENTITY_FILE),
    _MEMORY_FILE: _write_context_regexes(_MEMORY_FILE),
}


def _identity_write_finding(pkg: dict, filename: str, scenario: str) -> Finding:
    manifest = pkg.get("manifest") or {}
    scopes = file_scopes(permissions(pkg))
    # deny_write-wins evaluation, delegated to validators/usf.py rather than
    # re-derived: a grant that survives the package's own deny list is the
    # declaration half of the scenario.
    usf_shaped = {
        "permissions": {
            "files": {
                "read": list(scopes.read),
                "write": list(scopes.write),
                "deny_write": list(scopes.deny_write),
            }
        }
    }
    if write_allowed(usf_shaped, filename):
        return Finding(
            scenario,
            True,
            f"manifest grants write to {filename} and no deny_write entry overrides it "
            f"(declared write scope {list(scopes.write)})",
        )

    for path, content in sorted(_files_with_suffix(pkg, *_SCRIPT_SUFFIXES).items()):
        for regex, label in _IDENTITY_WRITE_PATTERNS[filename]:
            match = regex.search(content)
            if match:
                return Finding(scenario, True, f"{path}: {filename} {label}: {_snippet(match.group(0))}")
    _ = manifest
    return Finding(scenario, False, f"no declared write scope and no bundled script writes to {filename}")


def detect_soul_md_persistence(pkg: dict) -> Finding:
    """AST01-S05: a backdoor instruction written into the agent identity file."""
    return _identity_write_finding(pkg, _IDENTITY_FILE, "AST01-soul-md-persistence")


def detect_memory_poisoning(pkg: dict) -> Finding:
    """AST01-S06: attacker context injected into the agent memory file."""
    return _identity_write_finding(pkg, _MEMORY_FILE, "AST01-memory-poisoning")


# --------------------------------------------------------------------------
# Egress call sites -- shared by AST01-S08 and AST01-S10
# --------------------------------------------------------------------------

_EGRESS_CALL_RE = re.compile(
    r"\b(?:"
    r"requests\.(?:post|put|patch|get|request)"
    r"|httpx\.(?:post|put|patch|get|stream)"
    r"|urllib\.request\.urlopen"
    r"|urlopen"
    r"|http\.client\.HTTPS?Connection"
    r"|aiohttp\.ClientSession"
    r"|socket\.create_connection"
    r"|websockets?\.(?:connect|create_connection)"
    r"|WebSocketApp"
    r"|axios\.(?:post|put|get)"
    r"|XMLHttpRequest"
    r"|Invoke-RestMethod"
    r"|Invoke-WebRequest"
    r")\s{0,4}\(",
    re.IGNORECASE,
)
_SHELL_EGRESS_RE = re.compile(r"\b(?:curl|wget|nc|ncat|netcat)\b\s{1,8}[^\n]{0,200}", re.IGNORECASE)
_QUOTED_HTTP_URL_RE = re.compile(
    r"['\"]\s{0,4}https?://([A-Za-z0-9._~-]+(?::\d{1,5})?)[^'\"\n]{0,300}['\"]",
    re.IGNORECASE,
)


def _egress_call_site(path: str, content: str) -> str | None:
    match = _EGRESS_CALL_RE.search(content)
    if match:
        return _snippet(match.group(0))
    if path.lower().endswith(_SHELL_SUFFIXES):
        shell_match = _SHELL_EGRESS_RE.search(content)
        if shell_match:
            return _snippet(shell_match.group(0))
    return None


# --------------------------------------------------------------------------
# AST01-S08 -- Identity Cloning and Impersonation
# --------------------------------------------------------------------------

_IDENTITY_ARTIFACT_LITERAL_RE = re.compile(
    r"['\"][^'\"\n]{0,200}(?:SOUL|MEMORY|AGENTS|PERSONA|IDENTITY)\.(?:md|json|ya?ml)['\"]",
    re.IGNORECASE,
)
_READ_CONTEXT_RE = re.compile(
    r"(?:\bopen\s{0,4}\("
    r"|read_text\s{0,4}\("
    r"|read_bytes\s{0,4}\("
    r"|readlines\s{0,4}\("
    r"|\.read\s{0,4}\("
    r"|readFileSync\s{0,4}\("
    r"|Get-Content\b"
    r"|\bcat\b)",
    re.IGNORECASE,
)
_WRITE_MODE_RE = re.compile(r"['\"][wax]\+?b?['\"]")


def detect_identity_clone_exfiltration(pkg: dict) -> Finding:
    """AST01-S08: an identity-artifact read plus an outbound send, same script."""
    scenario = "AST01-identity-clone-exfiltration"
    for path, content in sorted(_files_with_suffix(pkg, *_SCRIPT_SUFFIXES).items()):
        call_site = _egress_call_site(path, content)
        if not call_site:
            continue
        for line in content.splitlines():
            literal = _IDENTITY_ARTIFACT_LITERAL_RE.search(line)
            if not literal:
                continue
            if not _READ_CONTEXT_RE.search(line):
                continue
            if _WRITE_MODE_RE.search(line):
                continue  # a write is AST01-S05/S06, not a clone
            return Finding(
                scenario,
                True,
                f"{path}: reads identity artifact {literal.group(0)} and carries an outbound send ({call_site})",
            )
    return Finding(scenario, False, "no bundled script both reads an identity artifact and sends outbound")


# --------------------------------------------------------------------------
# AST01-S09 -- WebSocket Hijacking
# --------------------------------------------------------------------------

_WS_URL_LITERAL_RE = re.compile(
    r"['\"]\s{0,4}wss?://([A-Za-z0-9._~-]+(?::\d{1,5})?)[^'\"\n]{0,300}['\"]",
    re.IGNORECASE,
)


def detect_websocket_c2(pkg: dict) -> Finding:
    """AST01-S09: a WebSocket-scheme client against an undeclared host."""
    scenario = "AST01-websocket-c2"
    for path, content in sorted(_files_with_suffix(pkg, *_SCRIPT_SUFFIXES).items()):
        hosts = _WS_URL_LITERAL_RE.findall(content)
        if not hosts:
            continue
        undeclared = _undeclared_hosts(pkg, hosts)
        if undeclared:
            return Finding(
                scenario,
                True,
                f"{path}: WebSocket client to undeclared host(s) {undeclared}",
            )
    return Finding(scenario, False, "no bundled script opens a WebSocket to an undeclared host")


# --------------------------------------------------------------------------
# AST01-S10 -- Data Exfiltration
# --------------------------------------------------------------------------


def detect_undeclared_egress(pkg: dict) -> Finding:
    """AST01-S10: a hardcoded destination a bundled script sends to, that the
    manifest never declared. The in-package diff between code and manifest.

    Three things must hold before this fires, and the first two are the ones a
    manifest-carrying fixture corpus can never exercise:

    1. **There is a declaration to depart from.** "Undeclared egress"
       presupposes a declaration; a package with no ``permissions.network`` key
       has made no promise, so no script can contradict one. That absence is
       already a finding -- ``AST06-missing-sandbox-declaration`` and
       ``AST03-unbounded-write-scope`` state it as their preconditions -- and a
       ``covers: full`` check may not convict a named scenario on another
       category's precondition. Measured over 360 third-party skill packages,
       those two preconditions fired on 360; a check that degenerates to
       "makes a network call and declares nothing" convicts every real skill
       that calls anything.
    2. **The destination is somewhere an allowlist could govern.** Loopback is
       not egress and an unqualified name is not decidable from the artifact;
       ``_destination_class`` settles both before the allowlist is consulted.
    3. **The destination is absent from that declaration.** Unchanged, and the
       whole scenario: a manifest declaring ``status.example.com`` beside a
       script posting to ``collector.attacker-drop.example`` still convicts.

    The negatives are not interchangeable, and only the evidence string carries
    which one happened -- the same distinction AST01-S02 already draws between
    *undecided* and *clean*.
    """
    scenario = "AST01-undeclared-egress"
    declared_policy = _declares_egress_policy(pkg)
    unevaluated: list[str] = []
    undecided: list[str] = []
    local_only: list[str] = []
    for path, content in sorted(_files_with_suffix(pkg, *_SCRIPT_SUFFIXES).items()):
        call_site = _egress_call_site(path, content)
        if not call_site:
            continue
        hosts = _QUOTED_HTTP_URL_RE.findall(content)
        if path.lower().endswith(_SHELL_SUFFIXES):
            hosts = hosts + _URL_HOST_RE.findall(content)
        if not declared_policy:
            # Precondition, not this scenario. Still name what went unexamined:
            # a reviewer handed the boolean alone would read "no egress here".
            named = sorted({_normalize_host(host) for host in hosts if _normalize_host(host)})
            unevaluated.append(f"{path}: {call_site} to {named or 'no literal host'}")
            continue
        destinations = _classify_hosts(pkg, hosts)
        if destinations.undeclared:
            return Finding(
                scenario,
                True,
                f"{path}: egress call ({call_site}) to host(s) {list(destinations.undeclared)} absent from the "
                f"declared allowlist {list(network_allowlist(permissions(pkg)))}",
            )
        if destinations.unqualified:
            undecided.append(f"{path}: {call_site} to unqualified host(s) {list(destinations.unqualified)}")
        elif destinations.loopback:
            local_only.append(f"{path}: {call_site} to loopback host(s) {list(destinations.loopback)}")

    if unevaluated:
        more = f" (+{len(unevaluated) - 1} more)" if len(unevaluated) > 1 else ""
        return Finding(
            scenario,
            False,
            "precondition, not this scenario: the package declares no egress policy at all "
            "(permissions.network is absent, which is not the same as an allowlist declared empty), so "
            "there is no declaration for a destination to depart from. That absence is "
            "AST06-missing-sandbox-declaration's and AST03-unbounded-write-scope's finding. Left "
            f"unevaluated here: {unevaluated[0]}{more}",
        )
    if undecided:
        return Finding(
            scenario,
            False,
            "undecided (an unqualified host resolves through the runtime's search domain, which the "
            f"package's own bytes do not fix): {undecided[0]}",
        )
    if local_only:
        return Finding(
            scenario,
            False,
            f"not egress -- the destination never leaves the machine: {local_only[0]}",
        )
    if not declared_policy:
        # Nothing reached the precondition branch, so there was no egress call
        # site at all. Saying "covered by the declared allowlist" here would
        # credit a comparison against an allowlist that does not exist.
        return Finding(
            scenario,
            False,
            "no bundled script carries an egress call site; the package also declares no egress "
            "policy, so no allowlist comparison was available in any case",
        )
    return Finding(scenario, False, "every hardcoded egress destination is covered by the declared allowlist")


# --------------------------------------------------------------------------
# AST01-S11 -- Hidden Prompt Injection in Skill Output
# --------------------------------------------------------------------------
#
# Scoped to what the skill RETURNS. The carrier classes are the registry's:
# zero-width and bidirectional control characters, and base64 blobs that
# decode back to text. Scoping is the whole distinction from AST04/AST08's
# shared invisible-Unicode scan, which flags the carrier anywhere in the
# package and is declared a category-precondition there for that reason.

_OUTPUT_FENCE_RE = re.compile(
    r"^```[ \t]*(output|template|response|skill-output|agent-output)[^\n]*\n(.*?)^```",
    re.MULTILINE | re.DOTALL,
)
_B64_BLOB_RE = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")


def _output_regions(pkg: dict) -> list[tuple[str, str]]:
    regions: list[tuple[str, str]] = []
    for path, content in sorted(_files_with_suffix(pkg, *_MARKDOWN_SUFFIXES).items()):
        for match in _OUTPUT_FENCE_RE.finditer(content):
            regions.append((f"{path} (```{match.group(1)} block)", match.group(2)))
    for path, content in sorted(_files_with_suffix(pkg, *_TEMPLATE_SUFFIXES).items()):
        regions.append((path, content))
    for path, content in sorted((pkg.get("files") or {}).items()):
        if isinstance(content, str) and path.lower().startswith(("templates/", "output/")):
            regions.append((path, content))
    return regions


def _smuggled_text(blob: str) -> str | None:
    """Decode a base64 blob; return the text only when it decodes to text.

    Bounded: one decode pass, no recursion, and a blob that decodes to bytes
    rather than to readable text is not a smuggled instruction and is left
    alone.
    """
    padded = blob + "=" * (-len(blob) % 4)
    try:
        raw = base64.b64decode(padded, validate=True)
    except (binascii.Error, ValueError):
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if len(text) < 8:
        return None
    printable = sum(1 for ch in text if ch.isprintable() or ch in "\n\r\t")
    return text if printable / len(text) >= 0.9 else None


def detect_hidden_output_injection(pkg: dict) -> Finding:
    scenario = "AST01-hidden-output-injection"
    for label, region in _output_regions(pkg):
        hits = INVISIBLE_UNICODE_RE.findall(region)
        if hits:
            codepoints = sorted({f"U+{ord(c):04X}" for c in hits})
            return Finding(
                scenario,
                True,
                f"{label}: {len(hits)} invisible code point(s) {codepoints} concealed in returned content",
            )
        for blob in _B64_BLOB_RE.findall(region):
            decoded = _smuggled_text(blob)
            if decoded is not None:
                return Finding(
                    scenario,
                    True,
                    f"{label}: base64 blob in returned content decodes to text: {_snippet(decoded)}",
                )
    return Finding(scenario, False, "no concealed instruction carrier in the package's output templates")


# --------------------------------------------------------------------------
# AST08-S02 -- Obfuscated Instruction, decided from an AST01 package
# --------------------------------------------------------------------------

_EXEC_OF_DECODE_RE = re.compile(
    r"\b(?:eval|exec|os\.system|subprocess\.(?:run|call|Popen|check_output)|Function)\s{0,4}\("
    r"[^)\n]{0,120}?"
    r"(?:b64decode|b32decode|a85decode|atob|unhexlify|decodebytes|fromhex)\s{0,4}\(",
    re.IGNORECASE,
)
_ENCODED_LITERAL_RE = re.compile(r"['\"]([A-Za-z0-9+/]{16,}={0,2})['\"]")
_SHELL_DECODE_EXEC_RE = re.compile(
    r"base64\s{1,8}(?:--decode|-d)\b[^\n]{0,200}\|\s{0,8}(?:ba|z|k)?sh\b",
    re.IGNORECASE,
)
_DANGEROUS_DECODED_RE = re.compile(
    r"(?:\brm\s{1,4}-[rf]{1,2}\b|\bcurl\b|\bwget\b|/bin/(?:ba)?sh\b|\bnc\s{1,4}-e\b|\bchmod\s{1,4}\+x\b"
    r"|\bos\.system\b|\bsubprocess\b|\bimport\s{1,4}socket\b)",
    re.IGNORECASE,
)


def detect_obfuscated_payload_exec(pkg: dict) -> Finding:
    """AST08-S02: an encoded blob decoded and handed to an execution sink.

    The decode is performed, once, so the finding reports what the payload
    actually says rather than that the package contains base64. A decode call
    whose result is never executed -- the legitimate use -- does not fire.
    """
    scenario = "AST01-obfuscated-payload-exec"
    for path, content in sorted(_files_with_suffix(pkg, *_SCRIPT_SUFFIXES).items()):
        match = _EXEC_OF_DECODE_RE.search(content)
        if match:
            window = content[match.start() : match.start() + 400]
            literal = _ENCODED_LITERAL_RE.search(window)
            decoded = _smuggled_text(literal.group(1)) if literal else None
            if decoded is not None:
                verdict = "dangerous" if _DANGEROUS_DECODED_RE.search(decoded) else "opaque"
                return Finding(
                    scenario,
                    True,
                    f"{path}: encoded blob decoded into an execution sink; "
                    f"payload decodes ({verdict}) to: {_snippet(decoded)}",
                )
            return Finding(
                scenario,
                True,
                f"{path}: encoded blob decoded into an execution sink: {_snippet(match.group(0))}",
            )
        shell_match = _SHELL_DECODE_EXEC_RE.search(content)
        if shell_match:
            return Finding(
                scenario,
                True,
                f"{path}: base64-decoded stream piped into a shell: {_snippet(shell_match.group(0))}",
            )
    return Finding(scenario, False, "no encoded blob is decoded into an execution sink")


#: The ten mechanical checks, keyed by CHECK id. This is the namespace the CLI
#: reports a finding under and the one `fixtures/manifest.yaml` names in each
#: labeled case's `detector_check`; it is NOT the scenario namespace above.
DETECTORS: dict[str, Callable[[dict], Finding]] = {
    "AST01-content-hash-missing": detect_content_hash_missing,
    "AST01-content-hash-mismatch": detect_content_hash_mismatch,
    "AST01-social-engineering-prerequisites": detect_social_engineering_prerequisites,
    "AST01-soul-md-persistence": detect_soul_md_persistence,
    "AST01-memory-poisoning": detect_memory_poisoning,
    "AST01-identity-clone-exfiltration": detect_identity_clone_exfiltration,
    "AST01-websocket-c2": detect_websocket_c2,
    "AST01-undeclared-egress": detect_undeclared_egress,
    "AST01-hidden-output-injection": detect_hidden_output_injection,
    "AST01-obfuscated-payload-exec": detect_obfuscated_payload_exec,
}

#: The same checks re-keyed onto the registry scenarios they DECIDE, which is
#: the namespace `SCENARIO_TIERS` and `scenarios/registry.yaml` are in. Only
#: `covers: full` checks fold in, and that is the tier doctrine rather than a
#: convenience: a proxy is never coverage of the scenario it proxies, so the two
#: content-hash controls are absent here by ruling, not by oversight.
SCENARIO_DETECTORS: dict[str, Callable[[dict], Finding]] = scenario_detectors(DETECTORS, CHECK_COVERAGE)

#: The F1 denominator: every registry scenario a `covers: full` check here
#: decides. That is AST01's seven static-detectable scenarios plus AST08-S02 --
#: filed by the whitepaper under another category, decided here from an AST01
#: package's own bundled script, and published for exactly that reason as the
#: eighth labeled check in `fixtures/manifest.yaml`. Empty whenever the registry
#: tiers nothing in this category static-detectable, which is the gate-4 / S-003
#: guard `f1_report` reads: an empty detectable tier publishes no number at all
#: rather than manufacturing one.
SCORED_SCENARIOS: set[str] = set(SCENARIO_DETECTORS) if STATIC_DETECTABLE else set()


def run_all(pkg: dict) -> list[Finding]:
    return _run_all(DETECTORS, pkg)


def _scenario_labels(expected: set[str]) -> set[str]:
    """One fixture's expected labels, in the scenario namespace.

    `fixtures/manifest.yaml` labels every case with a registry `scenario_id` and
    records the CHECK it was measured against (`detector_check`), and
    `detectors/corpus.py` hands the scorer the check id. `SCORED_SCENARIOS` is a
    set of scenario ids, so a check-id label is resolved through
    `CHECK_COVERAGE` to the scenarios that check decides, and a label that is
    already a registry id passes through untouched. Only `covers: full` links
    resolve: a proxy label may not put a true positive in a scenario's column.
    """
    resolved: set[str] = set()
    for label in expected:
        entry = CHECK_COVERAGE.get(label)
        if entry is None:
            resolved.add(label)
        elif entry["covers"] == "full":
            resolved.update(entry["registry_ids"])
    return resolved


def f1_report(fixtures: list[tuple[dict, set[str]]] | None = None) -> dict:
    labeled = [(pkg, _scenario_labels(expected)) for pkg, expected in (fixtures or [])]
    return _f1_report(SCORED_SCENARIOS, SCENARIO_DETECTORS, labeled, F1_SCOPE)
