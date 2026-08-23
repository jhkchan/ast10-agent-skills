"""AST10 -- Cross-Platform Reuse detector.

Scenario tiers are keyed by the canonical ids in ``scenarios/registry.yaml``
(AST10-S01 ... AST10-S06), which is authoritative on tier, and the written
reasons are reproduced in ``skills/AST10/coverage-matrix.md``. Five of the six
named scenarios are out-of-artifact; exactly one -- AST10-S06 Silent Supply
Chain Injection -- is static-detectable, and this module implements it.

WHAT AST10-S06 SAYS, AND WHAT THAT MAKES CHECKABLE
--------------------------------------------------
The whitepaper's scenario text is: "Malicious payloads hidden inside encoded
script blocks or shared skill repositories execute at agent speed once
imported into a new ecosystem without structural validation." Its matching
preventive mitigation is: "Build platform-agnostic skill scanners that
evaluate the content layer independently of the runtime."

Those two sentences name a mechanism, not a keyword. The payload is not
visible in the package's source text -- that is the entire point of encoding
it -- so a scanner that greps the source finds nothing, and a scanner that
flags every base64 run flags every embedded icon, every ``content_hash``, and
every signature. The check that follows the whitepaper is therefore:

    decode the encoded blobs the package actually carries, and re-scan the
    DECODED bytes -- the content layer -- for payload behaviour.

``detect_encoded_payload_injection`` fires on either of two structural
conditions, and on nothing else:

C1  DECODE-AND-RESCAN. An encoded blob in the package (base64, hex, ``\\xNN``
    escapes, percent-encoding, and one further gzip/zlib/base64 layer beneath
    any of them) decodes to text that matches a payload-behaviour signature:
    interpreter invocation, destructive filesystem operations, credential
    harvesting, writes to the USF identity files, fetch-and-execute, outbound
    exfiltration, reverse shells, or a dynamic-execution sink. The source
    shows opaque bytes; only the decode makes the behaviour visible.

C2  DECODE-THEN-EXECUTE. An encoded literal is decoded and the decoded result
    reaches an execution sink -- on the same line, or through a single
    assignment (``payload = <decode call>`` ... ``exec`` of ``payload``). A
    package that hands an opaque literal straight to an interpreter has, by
    construction, no structural validation between import and execution, which
    is the condition AST10-S06 names. C2 fires even when C1 cannot read the
    payload (a second cipher layer, a remote key), so an unreadable payload is
    not a free pass.

WHAT IS DELIBERATELY NOT FLAGGED
--------------------------------
Encoding is not the finding; an unvalidated encoded *payload* is. A blob that
decodes to a PNG, to JSON configuration, or to nothing readable at all is not
reported, and the ``content_hash`` / ``signature`` / ``integrity`` hex fields
the Universal Skill Format itself mandates are excluded by field name --
flagging the manifest's own integrity metadata would make the scanner
unusable on exactly the conformant packages USF exists to produce. Three of
this category's six labeled fixtures are those cases, carrying real encoded
blobs and labeled clean.

The other five scenarios stay out-of-artifact and ship no check; each one's
defining condition needs a second manifest, a second registry, a second
platform's default-permission model, or a timeline. See the coverage matrix.
"""

from __future__ import annotations

import base64
import binascii
import gzip
import re
import zlib
from typing import Callable, Iterator, NamedTuple
from urllib.parse import unquote_to_bytes

from detectors.scaffold import Finding, static_detectable
from detectors.scaffold import f1_report as _f1_report
from detectors.scaffold import f1_scope as _f1_scope
from detectors.scaffold import run_all as _run_all

#: Tiers keyed by ``scenarios/registry.yaml``'s canonical scenario ids. The
#: registry is authoritative; this map must agree with it, and
#: ``tests/test_coverage_matrix_ast09_ast10.py`` checks that it does.
SCENARIO_TIERS: dict[str, str] = {
    # Loss is a relation between a source manifest and a ported target manifest
    # under the target platform's schema -- the whitepaper's own metadata loss
    # simulator takes two manifests as input.
    "AST10-S01": "out-of-artifact",
    # Needs a cross-registry corpus: the same skill's scan posture and install
    # counts on two or more registries.
    "AST10-S02": "out-of-artifact",
    # "Across four platforms simultaneously" is a corpus-and-timeline property.
    "AST10-S03": "out-of-artifact",
    # Absence of a permission block is not evidence of removal without the
    # pre-port manifest to diff against.
    "AST10-S04": "out-of-artifact",
    # The escalation belongs to the target platform's default-permission model,
    # not to the package, whose declarations are unchanged by the port.
    "AST10-S05": "out-of-artifact",
    # Silent Supply Chain Injection: an encoded script block is a byte pattern
    # in the package, and decode-then-rescan is deterministic.
    "AST10-S06": "static-detectable",
}

STATIC_DETECTABLE: set[str] = static_detectable(SCENARIO_TIERS)

CHECK_COVERAGE: dict[str, dict] = {
    "AST10-S06": {
        "registry_ids": ["AST10-S06"],
        "covers": "full",
        "reason": (
            "The check decides AST10-S06's defining condition rather than a precondition "
            "for it. The scenario is a payload hidden inside an encoded script block that "
            "executes once imported 'without structural validation'; the check performs "
            "exactly that structural validation -- it decodes the package's encoded blobs "
            "and evaluates the decoded content layer, and separately flags a decoded "
            "literal flowing into an execution sink. Both halves are deterministic over "
            "the package's own bytes, need no second manifest, no registry state and no "
            "runtime, and are precisely the whitepaper's own AST10 mitigation ('build "
            "platform-agnostic skill scanners that evaluate the content layer "
            "independently of the runtime')."
        ),
    },
}

F1_SCOPE: str = _f1_scope(CHECK_COVERAGE)


# ---------------------------------------------------------------------------
# Payload-behaviour signatures, applied to DECODED content only
# ---------------------------------------------------------------------------
#
# Each entry is (label, pattern). The label travels in the finding's evidence
# so a reviewer sees which behaviour was decoded, not merely that something
# was. These are matched against decoded bytes, never against package source:
# the whole premise of AST10-S06 is that the source is opaque.

DECODED_PAYLOAD_SIGNATURES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "interpreter-invocation",
        re.compile(
            r"/bin/(?:ba|z|k)?sh\b|\b(?:ba|z)?sh\s+-c\b|\bpython[0-9.]*\s+-c\b"
            r"|\bnode\s+-e\b|\bperl\s+-e\b|\bpowershell(?:\.exe)?\s+-",
            re.IGNORECASE,
        ),
    ),
    (
        "destructive-filesystem",
        re.compile(
            r"\brm\s+-[a-zA-Z]*[rf][a-zA-Z]*\b|\bshutil\.rmtree\b|\bos\.removedirs\b"
            r"|\bmkfs(?:\.[a-z0-9]+)?\b|\bdd\s+if=|\bdel\s+/[fs]\b|\bformat\s+[a-z]:",
            re.IGNORECASE,
        ),
    ),
    (
        "credential-harvest",
        re.compile(
            r"(?:~|\$HOME|/home/[^\s'\"]+|/root)/\.(?:ssh|aws|kube|docker|npmrc|netrc|gnupg)\b"
            r"|\.aws/credentials\b|\bid_(?:rsa|ed25519)\b|\.netrc\b|(?:^|[/\s'\"])\.env\b"
            r"|\bAWS_SECRET_ACCESS_KEY\b|\bGITHUB_TOKEN\b|\b(?:OPENAI|ANTHROPIC)_API_KEY\b",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        # The three identity files the Universal Skill Format's own
        # permissions.files.deny_write protects by default.
        "identity-file-write",
        re.compile(r"\b(?:SOUL|MEMORY|AGENTS)\.md\b"),
    ),
    (
        "remote-fetch-execute",
        re.compile(
            r"\b(?:curl|wget)\b[^\n|]{0,200}\|\s*(?:sudo\s+)?(?:ba|z)?sh\b"
            r"|\bInvoke-WebRequest\b[^\n]{0,200}\biex\b|\biex\s*\(\s*New-Object\b",
            re.IGNORECASE,
        ),
    ),
    (
        "outbound-exfiltration",
        re.compile(
            r"\b(?:curl|wget|requests\.(?:post|put|patch)|urllib\.request\.urlopen"
            r"|http\.client\.HTTPS?Connection|fetch)\b[^\n]{0,200}https?://",
            re.IGNORECASE,
        ),
    ),
    (
        "reverse-shell",
        re.compile(
            r"\bsocket\.socket\b|/dev/tcp/|\bnc\s+-[a-z]*e[a-z]*\s|\b(?:ba)?sh\s+-i\s*>&",
            re.IGNORECASE,
        ),
    ),
    (
        "dynamic-execution",
        re.compile(
            r"\b(?:eval|exec|execfile|os\.system|os\.popen"
            r"|subprocess\.(?:run|Popen|call|check_call|check_output)"
            r"|child_process\.(?:exec|execSync|spawn|spawnSync))\s*\(",
            re.IGNORECASE,
        ),
    ),
)


# ---------------------------------------------------------------------------
# Encoded-blob extraction
# ---------------------------------------------------------------------------

# A base64 run of at least 24 payload characters (18 decoded bytes), bounded so
# a longer alphanumeric token is not sliced into a spurious candidate.
_B64_RE = re.compile(
    r"(?<![A-Za-z0-9+/=])"
    r"((?:[A-Za-z0-9+/]{4}){6,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?)"
    r"(?![A-Za-z0-9+/=])"
)

# A bare hex run of at least 24 characters (12 bytes).
_HEX_RE = re.compile(r"(?<![0-9A-Za-z])((?:[0-9a-fA-F]{2}){12,})(?![0-9A-Za-z])")

# A run of >= 8 ``\xNN`` escapes, the classic in-source byte-string payload.
_HEX_ESCAPE_RE = re.compile(r"((?:\\x[0-9a-fA-F]{2}){8,})")

# A run of >= 8 percent-encoded octets.
_PERCENT_RE = re.compile(r"((?:%[0-9A-Fa-f]{2}){8,})")

# Hex-valued fields the Universal Skill Format itself mandates. A scanner that
# reports a conformant manifest's own integrity metadata as a hidden payload is
# unusable on the packages USF exists to produce, so the line is skipped for
# bare-hex candidates only -- an encoded blob smuggled into some OTHER field on
# the same line is still read.
_HEX_METADATA_FIELD_RE = re.compile(
    r"\b(?:content_hash|signature|signing_key|public_key|fingerprint|integrity|checksum"
    r"|digest|sha1|sha256|sha384|sha512|md5|blake2b|commit|revision|etag|uuid)\b",
    re.IGNORECASE,
)

_GZIP_MAGIC = b"\x1f\x8b"
_ZLIB_MAGICS = (b"\x78\x01", b"\x78\x5e", b"\x78\x9c", b"\x78\xda")

#: Guard rails so a hostile package cannot turn a scan into a decompression
#: bomb or a quadratic regex walk.
MAX_CANDIDATES_PER_FILE = 400
MAX_DECODED_BYTES = 256 * 1024
MAX_DECODE_DEPTH = 2


class DecodedBlob(NamedTuple):
    """One decoded encoded-blob candidate found in the package."""

    where: str
    layers: tuple[str, ...]
    text: str
    excerpt: str


def _printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(1 for ch in text if ch in "\t\r\n" or 0x20 <= ord(ch) < 0x7F or ord(ch) > 0xA0)
    return printable / len(text)


def _decompress(raw: bytes) -> tuple[bytes, str] | None:
    """One transparent compression layer beneath an encoding, or None."""
    try:
        if raw.startswith(_GZIP_MAGIC):
            return gzip.decompress(raw)[:MAX_DECODED_BYTES], "gzip"
        if any(raw.startswith(magic) for magic in _ZLIB_MAGICS):
            return zlib.decompress(raw)[:MAX_DECODED_BYTES], "zlib"
    except (OSError, EOFError, zlib.error):
        return None
    return None


def _as_text(raw: bytes) -> str | None:
    """Decoded bytes as text, or None when they are not text at all.

    A PNG, a signature, or a random digest decodes to bytes that are not UTF-8
    or not printable, and there is no content layer in them to evaluate. That
    is the gate that keeps an embedded icon from being a finding.
    """
    if not raw:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if _printable_ratio(text) < 0.9:
        return None
    return text


def _raw_candidates(where: str, text: str) -> Iterator[tuple[str, str, bytes]]:
    """(encoding, source_literal, raw_bytes) for every decodable blob in ``text``."""
    emitted = 0
    for match in _B64_RE.finditer(text):
        if emitted >= MAX_CANDIDATES_PER_FILE:
            return
        literal = match.group(1)
        try:
            raw = base64.b64decode(literal, validate=True)
        except (binascii.Error, ValueError):
            continue
        emitted += 1
        yield "base64", literal, raw[:MAX_DECODED_BYTES]

    def _line_of(position: int) -> str:
        start = text.rfind("\n", 0, position) + 1
        end = text.find("\n", position)
        return text[start : end if end != -1 else len(text)]

    # The field name may sit on the line beside the value (a YAML manifest read
    # as a file) or in the surface key itself (the same manifest already parsed
    # into the detector package dict, where the value arrives on its own).
    metadata_surface = bool(_HEX_METADATA_FIELD_RE.search(where))

    for match in _HEX_RE.finditer(text):
        if emitted >= MAX_CANDIDATES_PER_FILE:
            return
        if metadata_surface or _HEX_METADATA_FIELD_RE.search(_line_of(match.start())):
            continue
        try:
            raw = bytes.fromhex(match.group(1))
        except ValueError:
            continue
        emitted += 1
        yield "hex", match.group(1), raw[:MAX_DECODED_BYTES]

    for match in _HEX_ESCAPE_RE.finditer(text):
        if emitted >= MAX_CANDIDATES_PER_FILE:
            return
        try:
            raw = bytes.fromhex(match.group(1).replace("\\x", ""))
        except ValueError:
            continue
        emitted += 1
        yield "hex-escape", match.group(1), raw[:MAX_DECODED_BYTES]

    for match in _PERCENT_RE.finditer(text):
        if emitted >= MAX_CANDIDATES_PER_FILE:
            return
        raw = unquote_to_bytes(match.group(1))
        emitted += 1
        yield "percent", match.group(1), raw[:MAX_DECODED_BYTES]


def iter_decoded_blobs(where: str, text: str, _depth: int = 0) -> Iterator[DecodedBlob]:
    """Every encoded blob in ``text`` that decodes to readable content.

    Recurses one further level so a gzip-under-base64 archive, or a
    double-encoded literal, is read rather than dismissed as noise.
    """
    if _depth >= MAX_DECODE_DEPTH:
        return
    for encoding, literal, raw in _raw_candidates(where, text):
        layers: tuple[str, ...] = (encoding,)
        decompressed = _decompress(raw)
        if decompressed is not None:
            raw, algorithm = decompressed
            layers = (*layers, algorithm)
        decoded = _as_text(raw)
        if decoded is None:
            continue
        excerpt = literal[:40] + ("..." if len(literal) > 40 else "")
        yield DecodedBlob(where, layers, decoded, excerpt)
        yield from iter_decoded_blobs(where, decoded, _depth + 1)


def decoded_payload_hits(where: str, text: str) -> tuple[list[tuple[DecodedBlob, str]], int]:
    """C1: (hits, blobs_read) for one surface.

    ``blobs_read`` is returned alongside so a clean verdict can say how much
    encoded content was actually decoded and cleared, rather than implying the
    package carried none.
    """
    hits: list[tuple[DecodedBlob, str]] = []
    blobs_read = 0
    for blob in iter_decoded_blobs(where, text):
        blobs_read += 1
        labels = [label for label, pattern in DECODED_PAYLOAD_SIGNATURES if pattern.search(blob.text)]
        if labels:
            hits.append((blob, "+".join(labels)))
    return hits, blobs_read


# ---------------------------------------------------------------------------
# C2 -- decoded literal reaching an execution sink
# ---------------------------------------------------------------------------
#
# The token names below are written with a separating character class rather
# than glued to a literal "(" so that this module's own source does not read as
# a decode-then-execute construct when this repository dogfoods its detectors
# over its own skill packages.

_DECODE_CALL_RE = re.compile(
    r"\b(?:atob|b64decode|standard_b64decode|urlsafe_b64decode|b32decode|b16decode"
    r"|a85decode|unhexlify|fromhex|codecs\.decode|zlib\.decompress|gzip\.decompress"
    r"|lzma\.decompress|Buffer\.from)\s*\("
    r"|\bbase64\s+(?:-d|-D|--decode)\b"
    r"|\bopenssl\s+(?:base64|enc)\b[^\n]{0,40}\s-d\b"
    r"|\bxxd\s+-r\b|\bbase64\s+--decode\b",
    re.IGNORECASE,
)

_EXEC_SINK_RE = re.compile(
    r"\b(?:eval|exec|execfile|os\.system|os\.popen"
    r"|subprocess\.(?:run|Popen|call|check_call|check_output)"
    r"|child_process\.(?:exec|execSync|spawn|spawnSync)|vm\.runInNewContext"
    r"|pickle\.loads|marshal\.loads)\s*\("
    r"|\bnew\s+Function\s*\("
    r"|\|\s*(?:sudo\s+)?(?:ba|z)?sh\b|\|\s*python[0-9.]*\b"
    r"|\b(?:ba|z)?sh\s+-c\b|\bIEX\s*\(",
    re.IGNORECASE,
)

# `name = <expression containing a decode call>` -- the one-hop def-use edge
# that carries a decoded literal to a sink on a later line.
_DECODE_ASSIGN_RE = re.compile(r"^[ \t]*(?:const\s+|let\s+|var\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*(?::[^=]+)?=\s*(.+)$")


def decode_to_exec_hits(where: str, text: str) -> list[str]:
    """C2: an encoded literal decoded and handed to an execution sink."""
    hits: list[str] = []
    assigned: dict[str, int] = {}
    lines = text.splitlines()

    for number, line in enumerate(lines, start=1):
        decoded_here = _DECODE_CALL_RE.search(line)
        if decoded_here and _EXEC_SINK_RE.search(line):
            hits.append(f"{where}:{number}: decoded literal executed in place -- {line.strip()[:120]}")
            continue
        if not decoded_here:
            continue
        assignment = _DECODE_ASSIGN_RE.match(line)
        if assignment and _DECODE_CALL_RE.search(assignment.group(2)):
            assigned.setdefault(assignment.group(1), number)

    if assigned:
        name_re = {name: re.compile(rf"\b{re.escape(name)}\b") for name in assigned}
        for number, line in enumerate(lines, start=1):
            sink = _EXEC_SINK_RE.search(line)
            if not sink:
                continue
            for name, defined_at in assigned.items():
                if number == defined_at:
                    continue
                if name_re[name].search(line[sink.start() :]):
                    hits.append(
                        f"{where}:{number}: decoded value {name!r} (assigned at line "
                        f"{defined_at}) reaches an execution sink -- {line.strip()[:120]}"
                    )
    return hits


# ---------------------------------------------------------------------------
# Package view
# ---------------------------------------------------------------------------


def _scannable(pkg: dict) -> dict[str, str]:
    """Every text surface of the package, keyed by where it came from.

    Both halves matter: a SKILL.md-only skill ships its payload in a
    frontmatter field, which reaches the detectors as a manifest value rather
    than as a file, and a bundled script ships it in ``files``.
    """
    surfaces: dict[str, str] = {}
    for path, content in (pkg.get("files") or {}).items():
        if isinstance(content, str):
            surfaces[path] = content

    def _walk(node: object, trail: str) -> None:
        if isinstance(node, str):
            surfaces[f"<manifest.{trail}>" if trail else "<manifest>"] = node
        elif isinstance(node, dict):
            for key, value in node.items():
                _walk(value, f"{trail}.{key}" if trail else str(key))
        elif isinstance(node, (list, tuple)):
            for index, value in enumerate(node):
                _walk(value, f"{trail}[{index}]")

    _walk(pkg.get("manifest") or {}, "")
    return surfaces


def detect_encoded_payload_injection(pkg: dict) -> Finding:
    """AST10-S06 -- Silent Supply Chain Injection.

    Decodes the package's encoded blobs and evaluates the decoded content
    layer (C1), and flags a decoded literal reaching an execution sink (C2).
    Encoding alone is never the finding.
    """
    surfaces = _scannable(pkg)
    evidence: list[str] = []
    blobs_read = 0

    for where in sorted(surfaces):
        hits, read = decoded_payload_hits(where, surfaces[where])
        blobs_read += read
        for blob, label in hits:
            evidence.append(f"{where}: {'+'.join(blob.layers)} blob '{blob.excerpt}' decodes to {label} content layer")

    for where in sorted(surfaces):
        evidence.extend(decode_to_exec_hits(where, surfaces[where]))

    if evidence:
        return Finding("AST10-S06", True, "; ".join(evidence[:6]))

    return Finding(
        "AST10-S06",
        False,
        f"{len(surfaces)} surface(s) scanned, {blobs_read} decodable blob(s) read: no "
        f"payload behaviour in any decoded content layer and no decode-to-execution path",
    )


DETECTORS: dict[str, Callable[[dict], Finding]] = {
    "AST10-S06": detect_encoded_payload_injection,
}


def run_all(pkg: dict) -> list[Finding]:
    return _run_all(DETECTORS, pkg)


def f1_report(fixtures: list[tuple[dict, set[str]]] | None = None) -> dict:
    return _f1_report(STATIC_DETECTABLE, DETECTORS, fixtures, F1_SCOPE)
