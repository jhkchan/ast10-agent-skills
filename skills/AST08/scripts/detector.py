"""AST08 -- Poor Scanning detector.

Scenario ids and tiers are `scenarios/registry.yaml`'s, verbatim. The registry
tiers four of AST08's eight named scenarios `static-detectable`, and this module
ships one function for each of them:

  AST08-S02  Obfuscated Instruction                        detect_obfuscated_instruction
  AST08-S04  Context-Dependent Malice                      detect_context_dependent_malice
  AST08-S07  Scanner Host Compromise and Resource Exhaustion
                                                           detect_scanner_host_hazard
  AST08-S08  Bytecode Cache Poisoning                      detect_bytecode_cache_poisoning

The other four are not this module's business and never will be:
`AST08-S01` Natural-Language Bypass and `AST08-S03` Scanner Impersonation are
agent-judgable (routed to the judge harness); `AST08-S05` Model-Dependent
Injection Resistance and `AST08-S06` Scanner-Target Evasion are out-of-artifact.
`skills/AST08/coverage-matrix.md` carries the written reason for each.

Each check is built from the mechanism the whitepaper's own AST08 section
describes, not from a keyword grep:

* **S02** implements the "Run every detection rule over the normalized view as
  well as the raw bytes ... Decode embedded encodings iteratively and re-scan
  each layer until no further decoding applies, under an explicit depth and size
  bound" mitigation. Carrier presence alone is never a finding -- the whitepaper
  is explicit that "Reporting the anomaly is not detecting the payload" -- so the
  check fires only when a *rule* matches a view the raw bytes hid: the normalized
  view, a decoded layer, or a zero-width run that decodes to text (the one
  carrier the whitepaper does allow to stand on its own, because no legitimate
  authoring path produces it).
* **S04** matches the logic-bomb control-flow shape the registry names: "an
  environment-keyed guard (hostname, username, date comparison, file-existence
  probe) wrapping a dangerous branch". It parses Python with `ast` rather than
  matching text, and deliberately excludes portability predicates
  (`platform.system`, `sys.platform`, `os.name`) from the guard class, because
  cross-platform branching around a subprocess call is the single most common
  benign shape that a naive version of this rule would convict -- exactly the
  over-flagging the category's own mitigations warn about.
* **S07** enforces the whitepaper's limits *before* parsing: file count, file
  size, padding runs, archive nesting depth, declared compression ratio, archive
  member count, member paths escaping the extraction root, symlinks escaping the
  scan root, and non-regular files. Nothing is decompressed: ratios come from the
  zip central directory, which is the only way to measure a decompression bomb
  without detonating it.
* **S08** compares source-to-bytecode provenance over the package's own
  contents, using only the 16-byte PEP 552 `.pyc` header. It never unmarshals a
  code object: `marshal` on hostile input is a scanner-host compromise
  (`AST08-S07`) waiting to happen, and this module is not going to demonstrate
  one category's failure while implementing another's.

INCOMPLETE IS NOT CLEAN
-----------------------
"Any limit or parser failure must produce an incomplete result (not a clean
verdict)." A `Finding` is binary, so this module encodes the third state in the
evidence string: any finding whose evidence begins with `INCOMPLETE:` is a
coverage event, not a demonstrated payload. Where the incompleteness is what
makes silent selection possible (a truncated `.pyc` header, an exhausted decode
bound) the finding is reported as detected; where the scan simply could not see
part of the package, the evidence records it beside a negative verdict rather
than claiming a clean one.

PACKAGE SHAPE
-------------
    {
      "manifest": {"description": "<text>"},
      "files":    {"<relative/path>": "<text>"},    # utf-8-decodable entries
      "blobs":    {"<relative/path>": b"<bytes>"},  # OPTIONAL, authoritative bytes
      "entries":  {"<relative/path>": {...}},       # OPTIONAL, non-file entries
    }

`files` is the shape every other detector in this repo consumes, so a package
built for them works here unchanged; `blobs` and `entries` are the extra views
`AST08-S07` and `AST08-S08` need (bytes for a `.pyc` header, a symlink's target,
a non-regular file's type) and are absent from a text-only package. Build all
three from a directory with `load_package_dir()`.
"""

from __future__ import annotations

import ast
import base64
import binascii
import importlib.util
import io
import os
import re
import stat
import struct
import unicodedata
import zipfile
from pathlib import Path
from typing import Callable

from detectors.scaffold import INVISIBLE_UNICODE_RE, Finding, static_detectable
from detectors.scaffold import (
    detect_invisible_unicode_smuggling as _shared_invisible_unicode,
)
from detectors.scaffold import f1_report as _f1_report
from detectors.scaffold import f1_scope as _f1_scope
from detectors.scaffold import run_all as _run_all

SCENARIO_TIERS: dict[str, str] = {
    "AST08-S01": "agent-judgable",  # Natural-Language Bypass
    "AST08-S02": "static-detectable",  # Obfuscated Instruction
    "AST08-S03": "agent-judgable",  # Scanner Impersonation
    "AST08-S04": "static-detectable",  # Context-Dependent Malice
    "AST08-S05": "out-of-artifact",  # Model-Dependent Injection Resistance
    "AST08-S06": "out-of-artifact",  # Scanner-Target Evasion
    "AST08-S07": "static-detectable",  # Scanner Host Compromise and Resource Exhaustion
    "AST08-S08": "static-detectable",  # Bytecode Cache Poisoning
}

STATIC_DETECTABLE: set[str] = static_detectable(SCENARIO_TIERS)

CHECK_COVERAGE: dict[str, dict] = {
    "AST08-S02": {
        "registry_ids": ["AST08-S02"],
        "covers": "full",
        "reason": (
            "Decides S02's defining condition -- a payload hidden in an encoding that the "
            "model decodes at runtime -- by decoding candidate encodings iteratively under "
            "an explicit depth and size bound and re-running the rule set over each decoded "
            "layer and over the normalized view, which is the whitepaper's own stated "
            "mitigation for this scenario. Carrier presence alone is never reported as the "
            "payload."
        ),
    },
    "AST08-S04": {
        "registry_ids": ["AST08-S04"],
        "covers": "full",
        "reason": (
            "Decides S04's defining condition -- a branch that activates only under specific "
            "runtime conditions -- by matching the control-flow shape the registry names: an "
            "environment-identity guard (hostname, username, date comparison, file-existence "
            "probe, env-var equality) wrapping a dangerous branch. The logic bomb ships with "
            "the package and the shape is decided from the parse tree, never by executing it."
        ),
    },
    "AST08-S07": {
        "registry_ids": ["AST08-S07"],
        "covers": "full",
        "reason": (
            "Decides S07's defining condition -- a package that attacks the scanner through "
            "recursive archives, decompression bombs, oversized inputs, symlink escapes or "
            "special files -- by measuring each named vector as a property of the files as "
            "they sit on disk and enforcing the limits before any parsing happens."
        ),
    },
    "AST08-S08": {
        "registry_ids": ["AST08-S08"],
        "covers": "full",
        "reason": (
            "Decides S08's defining condition -- bytecode the import machinery will select "
            "that does not correspond to the source a reviewer reads -- by comparing "
            "source-to-bytecode provenance across artifacts that both ship in the package: "
            "a sourceless .pyc, an unchecked hash-based .pyc, or a header whose recorded "
            "source hash or size contradicts the adjacent source."
        ),
    },
}

F1_SCOPE: str = _f1_scope(CHECK_COVERAGE)


# ---------------------------------------------------------------------------
# Shared views: normalization, and the rule set that is re-run over each view
# ---------------------------------------------------------------------------

#: Variation selectors and Unicode tag characters -- the two carrier classes the
#: whitepaper names beside zero-width and bidi controls ("variation selectors and
#: tag characters (U+E0000-U+E007F)"). Escapes, never literal glyphs: a file that
#: documents a smuggling class must not carry it.
_VARIATION_AND_TAG_RE = re.compile("[\ufe00-\ufe0f\U000e0000-\U000e01ef]")

#: The detection rules. Deliberately small and behavioural: these are re-run over
#: views the raw bytes hid, so their job is to recognise a payload once it is in
#: the clear, not to be a general-purpose scanner.
_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("remote-fetch-piped-to-shell", re.compile(r"\b(curl|wget)\b[^\n|]{0,200}\|\s*(ba|z|k)?sh\b", re.I)),
    (
        "shell-or-eval-execution",
        re.compile(
            r"\b(os\.system|os\.popen|subprocess\.(run|call|Popen|check_output)|"
            r"(ba|z|k)?sh\s+-c|eval\s*\(|exec\s*\()",
            re.I,
        ),
    ),
    (
        "credential-material-path",
        re.compile(
            r"(\.aws/credentials|\.ssh/id_[a-z0-9]+|/\.env\b|\.npmrc|\.docker/config\.json|\.kube/config)",
            re.I,
        ),
    ),
    ("egress-of-local-data", re.compile(r"\b(post|upload|send|exfiltrat\w*|beacon)\b[^\n]{0,80}https?://", re.I)),
    (
        "agent-directed-override",
        re.compile(
            r"(ignore\s+(all\s+)?(previous|prior|above)\s+instructions|"
            r"do\s+not\s+(tell|inform|mention|report)\s+(the\s+)?(user|operator)|"
            r"without\s+(telling|informing|notifying)\s+the\s+user)",
            re.I,
        ),
    ),
)

#: Decode bounds. Declared, not implicit: the whitepaper requires the bound to be
#: stated and its exhaustion recorded as an INCOMPLETE coverage event.
MAX_DECODE_DEPTH = 4
MAX_DECODE_BYTES = 1 << 20  # 1 MiB per decoded layer

_B64_RE = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")
_B64URL_RE = re.compile(r"[A-Za-z0-9_-]{24,}={0,2}")
_HEX_RE = re.compile(r"(?:[0-9a-fA-F]{2}){16,}")

#: Zero-width bit alphabet. U+200B/U+200C carry the bits; U+200D and U+FEFF are
#: tolerated as separators inside a run, which is how the published ASCII-smuggling
#: encoders lay a payload out.
_ZW_BITS = {"\u200b": "0", "\u200c": "1"}
_ZW_RUN_RE = re.compile("[\u200b-\u200d\ufeff]{16,}")


def normalized_view(text: str) -> str:
    """The whitepaper's normalized view: strip invisibles, then NFKC-fold.

    Two distinct operations, in the order the mitigation states them -- "NFKC
    folds compatibility variants ... and neither removes invisible characters. As
    a separate step, strip zero-width characters, bidirectional
    embedding/override/isolate controls, variation selectors and tag characters,
    then re-match."
    """
    stripped = INVISIBLE_UNICODE_RE.sub("", text)
    stripped = _VARIATION_AND_TAG_RE.sub("", stripped)
    return unicodedata.normalize("NFKC", stripped)


def rule_hits(text: str) -> dict[str, str]:
    """{rule name: matched excerpt} for every rule that matches ``text``."""
    hits: dict[str, str] = {}
    for name, pattern in _RULES:
        match = pattern.search(text)
        if match:
            hits[name] = match.group(0)[:120]
    return hits


def rule_counts(text: str) -> dict[str, int]:
    """{rule name: number of matches} -- the comparison unit for the normalized view.

    Counts, not booleans, and the difference matters. Comparing "does this rule
    match the normalized view / the raw bytes" per FILE lets one plainly written
    occurrence mask every obfuscated one in the same file: a payload smuggled
    through a zero-width split goes unreported because a decoy install line
    elsewhere in the document already matched the same rule against the raw
    bytes. Comparing per occurrence closes that, and closing it is the point --
    an adversary who reads this file must not find "add a decoy" in it.
    """
    return {name: len(pattern.findall(text)) for name, pattern in _RULES}


def _is_texty(data: bytes) -> str | None:
    """The decoded layer as text, or None when it is not plausibly text.

    A decoded blob that is not text is not an instruction. Screening on this is
    what keeps a base64-embedded PNG or public key from being reported as a
    hidden payload.
    """
    if not data:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    printable = sum(1 for ch in text if ch.isprintable() or ch in "\n\r\t")
    return text if printable >= 0.9 * len(text) else None


def _decode_candidates(text: str) -> tuple[list[tuple[str, str]], bool]:
    """Every decodable embedded encoding in ``text`` as (kind, decoded text).

    Returns the decoded layers plus a flag recording whether any candidate was
    refused for exceeding :data:`MAX_DECODE_BYTES` -- a size-bound event the
    caller must surface rather than swallow.
    """
    layers: list[tuple[str, str]] = []
    size_bounded = False
    seen: set[str] = set()

    def _take(kind: str, blob: str, decoder: Callable[[str], bytes]) -> None:
        nonlocal size_bounded
        if blob in seen:
            return
        seen.add(blob)
        if len(blob) > MAX_DECODE_BYTES:
            size_bounded = True
            return
        try:
            raw = decoder(blob)
        except (binascii.Error, ValueError):
            return
        if len(raw) > MAX_DECODE_BYTES:
            size_bounded = True
            return
        decoded = _is_texty(raw)
        if decoded is not None:
            layers.append((kind, decoded))

    for match in _B64_RE.finditer(text):
        blob = match.group(0)
        if len(blob) % 4 == 0:
            _take("base64", blob, lambda b: base64.b64decode(b, validate=True))
    for match in _B64URL_RE.finditer(text):
        blob = match.group(0)
        if len(blob) % 4 == 0 and ("-" in blob or "_" in blob):
            _take("base64url", blob, lambda b: base64.urlsafe_b64decode(b))
    for match in _HEX_RE.finditer(text):
        _take("hex", match.group(0), bytes.fromhex)
    return layers, size_bounded


def zero_width_payload(text: str) -> str | None:
    """Text decoded out of a zero-width run, if any.

    The one carrier the whitepaper permits as a finding in its own right:
    "scope that signal to constructs with no plausible authoring path, such as ...
    a zero-width run that decodes to text".
    """
    for match in _ZW_RUN_RE.finditer(text):
        bits = "".join(_ZW_BITS[ch] for ch in match.group(0) if ch in _ZW_BITS)
        if len(bits) < 16 or len(bits) % 8:
            continue
        raw = bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))
        decoded = _is_texty(raw)
        if decoded and decoded.strip():
            return decoded
    return None


# ---------------------------------------------------------------------------
# AST08-S02 -- Obfuscated Instruction
# ---------------------------------------------------------------------------


def detect_obfuscated_instruction(pkg: dict) -> Finding:
    """Decode-and-rescan, plus normalize-and-rescan, per AST08's own mitigation.

    Fires when a detection rule matches a view of the artifact that the raw bytes
    concealed:

    1. the normalized view, when the same rule does *not* match the raw bytes --
       the keyword-split-by-a-zero-width-character attack;
    2. any decoded layer of an embedded encoding, to :data:`MAX_DECODE_DEPTH`;
    3. a zero-width run that decodes to text;
    4. exhaustion of the decode depth or size bound, reported as INCOMPLETE
       because a bound that stopped the scan is not evidence of a clean artifact.

    It does **not** fire on the mere presence of an encoded blob. A base64 icon,
    a public key, or a checksum decodes to something that matches no rule, and
    that is the whole difference between reporting an anomaly and detecting a
    payload.
    """
    scenario = "AST08-S02"
    sources: dict[str, str] = dict(pkg.get("files") or {})
    description = (pkg.get("manifest") or {}).get("description") or ""
    if description:
        sources["<manifest.description>"] = description

    bounded: list[str] = []
    for path, raw in sorted(sources.items()):
        view = normalized_view(raw)
        raw_counts = rule_counts(raw)
        view_hits = rule_hits(view)
        revealed = sorted(
            name for name, count in rule_counts(view).items() if count > raw_counts.get(name, 0) and name in view_hits
        )
        if revealed:
            name = revealed[0]
            return Finding(
                scenario,
                True,
                f"{path}: rule {name!r} matches the normalized view "
                f"{rule_counts(view)[name]} time(s) against {raw_counts.get(name, 0)} in the raw bytes "
                f"(normalized excerpt: {view_hits[name]!r}) -- the payload was split or folded to evade a "
                f"byte-oriented rule",
            )

        payload = zero_width_payload(raw)
        if payload is not None:
            return Finding(
                scenario,
                True,
                f"{path}: zero-width run decodes to text {payload[:80]!r} -- a carrier with no plausible "
                f"authoring path",
            )

        layer_texts = [raw]
        for depth in range(1, MAX_DECODE_DEPTH + 1):
            next_layer: list[str] = []
            for text in layer_texts:
                decoded_layers, size_bounded = _decode_candidates(text)
                if size_bounded:
                    bounded.append(f"{path} (size bound at depth {depth})")
                for kind, decoded in decoded_layers:
                    hits = rule_hits(decoded)
                    if hits:
                        name, excerpt = sorted(hits.items())[0]
                        return Finding(
                            scenario,
                            True,
                            f"{path}: {kind} blob at decode depth {depth} decodes to a layer matching rule "
                            f"{name!r} (decoded excerpt: {excerpt!r}); reported against the raw artifact with "
                            f"the decoded view retained as evidence",
                        )
                    next_layer.append(decoded)
            if not next_layer:
                break
            layer_texts = next_layer
            if depth == MAX_DECODE_DEPTH:
                bounded.append(f"{path} (depth bound {MAX_DECODE_DEPTH} reached with a decodable layer remaining)")

    if bounded:
        return Finding(
            scenario,
            True,
            f"INCOMPLETE: decode bound exhausted in {sorted(set(bounded))} -- per AST08 a bound exhaustion or "
            f"decoder failure is an INCOMPLETE coverage event, never a clean result",
        )
    return Finding(
        scenario,
        False,
        f"no rule matched the raw bytes, the normalized view, or any decoded layer "
        f"(depth<={MAX_DECODE_DEPTH}) across {len(sources)} source(s)",
    )


# ---------------------------------------------------------------------------
# AST08-S04 -- Context-Dependent Malice
# ---------------------------------------------------------------------------

#: Guard predicates that key a branch to *which environment is running it*. This
#: is the registry's own list -- hostname, username, date comparison,
#: file-existence probe -- plus env-var equality and the sandbox/debugger probes
#: that serve the identical purpose.
_ENVIRONMENT_IDENTITY_CALLS = frozenset(
    {
        "os.getenv",
        "os.environ.get",
        "socket.gethostname",
        "socket.getfqdn",
        "platform.node",
        "platform.uname",
        "os.uname",
        "getpass.getuser",
        "os.getlogin",
        "os.getuid",
        "pwd.getpwuid",
        "datetime.now",
        "datetime.utcnow",
        "datetime.today",
        "date.today",
        "time.time",
        "os.path.exists",
        "os.path.isfile",
        "os.path.isdir",
        "path.exists",
        "path.is_file",
        "path.is_dir",
        "sys.gettrace",
    }
)

#: Deliberately NOT guard predicates. Branching on the operating system is how
#: portable code is written, and convicting it would make this rule fire on a
#: large fraction of legitimate skills -- the over-flagging AST08's own
#: false-positive mitigation warns about. A logic bomb keyed to the OS alone is
#: not context-dependent malice; it is a platform branch.
_PORTABILITY_CALLS = frozenset({"platform.system", "platform.machine", "sys.platform", "os.name"})

#: Dangerous branch bodies -- execution, egress, destruction, credential reads.
_DANGEROUS_CALLS = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "os.system",
        "os.popen",
        "os.execv",
        "os.execve",
        "os.remove",
        "os.unlink",
        "os.rmdir",
        "shutil.rmtree",
        "subprocess.run",
        "subprocess.call",
        "subprocess.Popen",
        "subprocess.check_call",
        "subprocess.check_output",
        "socket.create_connection",
        "urllib.request.urlopen",
        "request.urlopen",
        "requests.get",
        "requests.post",
        "requests.put",
        "httpx.post",
        "smtplib.SMTP",
        "ftplib.FTP",
    }
)


def _dotted_name(node: ast.AST) -> str | None:
    """`os.path.exists` for an Attribute/Name chain; None for anything else."""
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    elif isinstance(current, ast.Call):
        inner = _dotted_name(current.func)
        if inner is None:
            return None
        parts.append(inner.rsplit(".", 1)[-1].lower())
    else:
        return None
    return ".".join(reversed(parts))


def _called_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            dotted = _dotted_name(child.func)
            if dotted:
                names.add(dotted)
                names.add(dotted.rsplit(".", 1)[-1] if "." in dotted else dotted)
    return names


def _environment_guard(test: ast.AST) -> str | None:
    """The environment-identity predicate this branch is keyed to, if any."""
    for child in ast.walk(test):
        if isinstance(child, ast.Subscript):
            base = _dotted_name(child.value)
            if base in {"os.environ", "environ"}:
                return "os.environ[...]"
    for name in sorted(_called_names(test)):
        if name in _PORTABILITY_CALLS:
            # Branching on the operating system is how portable code is written.
            # Stated at the point of decision rather than left implicit in the
            # absence of these names from the identity set, and kept honest by
            # test_the_two_predicate_classes_are_disjoint.
            continue
        if name in _ENVIRONMENT_IDENTITY_CALLS:
            return name
        # `datetime.datetime.now()` / `Path(p).exists()` reach here as suffixes.
        tail = name.rsplit(".", 2)[-2:]
        if len(tail) == 2 and ".".join(tail) in _ENVIRONMENT_IDENTITY_CALLS:
            return ".".join(tail)
    return None


def _dangerous_in(nodes: list[ast.stmt]) -> str | None:
    for statement in nodes:
        for name in sorted(_called_names(statement)):
            if name in _DANGEROUS_CALLS:
                return name
    return None


def detect_context_dependent_malice(pkg: dict) -> Finding:
    """Match the logic-bomb shape: environment-identity guard over a dangerous branch.

    Parses each `.py` file in the package and looks for an `if`/`while` whose test
    reads *which environment is running* -- hostname, username, uid, an env var, a
    date comparison, a file-existence probe, a debugger probe -- and whose taken
    branch contains execution, egress, destruction, or a credential read. Neither
    half convicts alone: an unconditional `subprocess.run` is ordinary skill code
    and an OS-portability branch around a benign assignment is ordinary portable
    code. The conjunction is the scenario.

    Nothing is executed. Unparseable `.py` files are recorded in the evidence as
    an INCOMPLETE coverage event rather than counted as clean.
    """
    scenario = "AST08-S04"
    unparsed: list[str] = []
    for path, source in sorted((pkg.get("files") or {}).items()):
        if not path.endswith(".py"):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            unparsed.append(f"{path}:{exc.lineno}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While)):
                guard = _environment_guard(node.test)
                if guard is None:
                    continue
                dangerous = _dangerous_in(list(node.body) + list(node.orelse))
                if dangerous:
                    return Finding(
                        scenario,
                        True,
                        f"{path}:{node.lineno}: branch keyed to {guard} guards a call to {dangerous}() -- "
                        f"an environment-keyed guard wrapping a dangerous branch executes only where the "
                        f"attacker chooses, so a test environment sees the safe path",
                    )
            elif isinstance(node, ast.IfExp):
                guard = _environment_guard(node.test)
                if guard is None:
                    continue
                for branch in (node.body, node.orelse):
                    for name in sorted(_called_names(branch)):
                        if name in _DANGEROUS_CALLS:
                            return Finding(
                                scenario,
                                True,
                                f"{path}:{node.lineno}: conditional expression keyed to {guard} selects a call "
                                f"to {name}() -- the same environment-keyed guard, written as an expression",
                            )
    suffix = f"; INCOMPLETE: {unparsed} failed to parse and were not analysed" if unparsed else ""
    return Finding(scenario, False, f"no environment-keyed guard wraps a dangerous branch{suffix}")


# ---------------------------------------------------------------------------
# AST08-S07 -- Scanner Host Compromise and Resource Exhaustion
# ---------------------------------------------------------------------------

#: Declared scope bounds. The whitepaper requires every bound to be declared and
#: its exhaustion recorded, so they are module constants an auditor can read
#: rather than magic numbers buried in a branch.
MAX_PACKAGE_FILES = 500
MAX_FILE_BYTES = 2 << 20  # 2 MiB
MAX_PADDING_RUN = 1000  # consecutive whitespace characters before content
MAX_ARCHIVE_DEPTH = 1  # an archive inside an archive is the recursive-archive vector
MAX_ARCHIVE_MEMBERS = 1000
MAX_COMPRESSION_RATIO = 100  # declared uncompressed / compressed, per member

_ARCHIVE_SUFFIXES = (".zip", ".docx", ".xlsx", ".pptx", ".jar", ".whl", ".egg", ".odt", ".epub")
#: Local file header, end-of-central-directory, and spanned-archive signatures.
_ZIP_SIGNATURES = frozenset({b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"})
_PADDING_RUN_RE = re.compile(r"[\s]{%d,}" % MAX_PADDING_RUN)


def _archive_hazards(path: str, data: bytes) -> list[str]:
    """Hazards readable from a zip container's central directory, without extracting.

    Every measurement here comes from the headers: member count, declared
    uncompressed size, compressed size, member path, and whether a member is
    itself an archive. Nothing is decompressed, which is the only way to measure
    a decompression bomb without triggering it.
    """
    hazards: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
    except (zipfile.BadZipFile, OSError, EOFError) as exc:
        return [
            f"INCOMPLETE: {path}: archive header could not be parsed ({exc}); a parser failure is not a clean verdict"
        ]

    if len(infos) > MAX_ARCHIVE_MEMBERS:
        hazards.append(f"{path}: {len(infos)} archive members exceeds the declared limit of {MAX_ARCHIVE_MEMBERS}")
    for info in infos:
        name = info.filename
        normalized = name.replace("\\", "/")
        if normalized.startswith("/") or ".." in Path(normalized).parts:
            hazards.append(f"{path}: member {name!r} escapes the extraction root")
        if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            hazards.append(
                f"{path}: member {name!r} declares a compression ratio of "
                f"{info.file_size / info.compress_size:.0f}:1 "
                f"({info.file_size} bytes from {info.compress_size}), over the {MAX_COMPRESSION_RATIO}:1 limit"
            )
        if normalized.lower().endswith(_ARCHIVE_SUFFIXES):
            hazards.append(
                f"{path}: member {name!r} is itself an archive -- nesting depth exceeds "
                f"the declared limit of {MAX_ARCHIVE_DEPTH}"
            )
    return hazards


def detect_scanner_host_hazard(pkg: dict) -> Finding:
    """Enforce AST08's resource and traversal limits before anything is parsed.

    Measures, as properties of the files as they sit on disk: package file count,
    per-file size, leading/embedded padding runs (Trail of Bits' 100,000-newline
    truncation vector), archive member count, declared decompression ratio,
    archive nesting depth, archive members escaping the extraction root, symlinks
    resolving outside the scan root, and non-regular files. A package that trips
    none of them is within the declared scope; a package that trips one is
    attacking the scanner, and the limit fires before the parser it targets runs.
    """
    scenario = "AST08-S07"
    files = pkg.get("files") or {}
    blobs = pkg.get("blobs") or {}
    entries = pkg.get("entries") or {}
    hazards: list[str] = []

    paths = set(files) | set(blobs) | set(entries)
    if len(paths) > MAX_PACKAGE_FILES:
        hazards.append(f"package holds {len(paths)} entries, over the declared limit of {MAX_PACKAGE_FILES}")

    for path in sorted(paths):
        size = len(blobs[path]) if path in blobs else len(files.get(path, "").encode("utf-8"))
        declared = (entries.get(path) or {}).get("size")
        if isinstance(declared, int):
            size = max(size, declared)
        if size > MAX_FILE_BYTES:
            hazards.append(f"{path}: {size} bytes exceeds the declared per-file limit of {MAX_FILE_BYTES}")

    for path, text in sorted(files.items()):
        match = _PADDING_RUN_RE.search(text)
        if match:
            hazards.append(
                f"{path}: a run of {len(match.group(0))} whitespace characters at offset {match.start()} "
                f"exceeds the {MAX_PADDING_RUN}-character padding limit -- context padding forces a "
                f"length-bounded scanner to truncate before the payload"
            )

    for path, entry in sorted(entries.items()):
        kind = (entry or {}).get("type")
        if kind == "symlink" and entry.get("escapes_scan_root"):
            hazards.append(f"{path}: symlink to {entry.get('target')!r} resolves outside the scan root")
        elif kind not in (None, "file", "dir", "symlink"):
            hazards.append(f"{path}: non-regular file of type {kind!r} -- reading it can block or exhaust the scanner")

    for path, data in sorted(blobs.items()):
        # Suffix OR magic, and the magic is the full 4-byte local-file / central-directory
        # signature rather than the two bytes "PK": a prose file that happens to open with
        # "PKI notes" is not an archive, and reporting it INCOMPLETE would be the
        # over-flagging this category's own false-positive mitigation warns about.
        if path.lower().endswith(_ARCHIVE_SUFFIXES) or data[:4] in _ZIP_SIGNATURES:
            hazards.extend(_archive_hazards(path, data))

    if hazards:
        return Finding(scenario, True, f"{len(hazards)} hazard(s); first: {hazards[0]}")
    return Finding(
        scenario,
        False,
        f"within every declared bound: <={MAX_PACKAGE_FILES} entries, <={MAX_FILE_BYTES} bytes/file, "
        f"no padding run over {MAX_PADDING_RUN}, archive depth <={MAX_ARCHIVE_DEPTH}, ratio "
        f"<={MAX_COMPRESSION_RATIO}:1, no escaping symlink, no special file",
    )


# ---------------------------------------------------------------------------
# AST08-S08 -- Bytecode Cache Poisoning
# ---------------------------------------------------------------------------

_PYC_HEADER_BYTES = 16
_PYC_FLAG_HASH_BASED = 0b01
_PYC_FLAG_CHECK_SOURCE = 0b10


def _source_for_pyc(path: str) -> str:
    """The source file Python's import machinery pairs with this `.pyc`."""
    p = Path(path)
    if p.parent.name == "__pycache__":
        return (p.parent.parent / f"{p.name.split('.')[0]}.py").as_posix()
    return p.with_suffix(".py").as_posix()


def detect_bytecode_cache_poisoning(pkg: dict) -> Finding:
    """Compare source-to-bytecode provenance over artifacts that both ship here.

    Four decidable conditions, all read from the 16-byte PEP 552 header -- the
    code object is never unmarshalled, because handing `marshal` an attacker's
    bytes is the scanner-host compromise of `AST08-S07`:

    * a `.pyc` with no corresponding source in the package (sourceless bytecode:
      nothing a reviewer can read corresponds to what will execute);
    * an **unchecked** hash-based `.pyc`, whose header tells the runtime to select
      it *without* validating it against the adjacent source -- the poisoned-cache
      enabler in one flag bit;
    * a checked hash-based `.pyc` whose recorded source hash contradicts the
      adjacent source (verified only when the header's magic is this
      interpreter's, since the hash is keyed by magic);
    * a timestamp-based `.pyc` whose recorded source size contradicts the adjacent
      source's actual length.

    A truncated or malformed header is reported as INCOMPLETE-and-detected: a
    header the scanner cannot read is not a header the scanner has cleared.
    """
    scenario = "AST08-S08"
    blobs = dict(pkg.get("blobs") or {})
    for path, text in (pkg.get("files") or {}).items():
        blobs.setdefault(path, text.encode("utf-8", "surrogateescape"))

    incomplete: list[str] = []
    for path in sorted(blobs):
        if not path.endswith(".pyc"):
            continue
        data = blobs[path]
        if len(data) < _PYC_HEADER_BYTES:
            return Finding(
                scenario,
                True,
                f"INCOMPLETE: {path}: {len(data)}-byte .pyc is shorter than a {_PYC_HEADER_BYTES}-byte header; "
                f"a parser failure is not a clean verdict",
            )
        source_path = _source_for_pyc(path)
        source_bytes = blobs.get(source_path)
        if source_bytes is None:
            return Finding(
                scenario,
                True,
                f"{path}: sourceless bytecode -- no {source_path} ships in the package, so the import "
                f"machinery selects behaviour no reviewer can read",
            )

        magic = data[:4]
        flags = struct.unpack("<I", data[4:8])[0]
        if flags & _PYC_FLAG_HASH_BASED:
            if not flags & _PYC_FLAG_CHECK_SOURCE:
                return Finding(
                    scenario,
                    True,
                    f"{path}: unchecked hash-based .pyc (flags=0x{flags:x}) -- the header instructs the runtime "
                    f"to load it without validating it against {source_path}, so the bytecode and the source a "
                    f"reviewer reads need never agree",
                )
            if magic == importlib.util.MAGIC_NUMBER:
                expected = importlib.util.source_hash(source_bytes)
                if data[8:16] != expected:
                    return Finding(
                        scenario,
                        True,
                        f"{path}: hash-based .pyc records source hash {data[8:16].hex()} but {source_path} "
                        f"hashes to {expected.hex()} -- the bytecode was not produced from the shipped source",
                    )
            else:
                incomplete.append(f"{path} (foreign magic {magic.hex()}; hash not recomputable here)")
        else:
            declared_size = struct.unpack("<I", data[12:16])[0]
            if declared_size != len(source_bytes):
                return Finding(
                    scenario,
                    True,
                    f"{path}: timestamp-based .pyc records a {declared_size}-byte source but {source_path} is "
                    f"{len(source_bytes)} bytes -- the bytecode was compiled from different source",
                )
            incomplete.append(f"{path} (timestamp-based; only the recorded source size is comparable at rest)")

    suffix = f"; INCOMPLETE: {sorted(incomplete)}" if incomplete else ""
    return Finding(scenario, False, f"every shipped .pyc corresponds to shipped source{suffix}")


# ---------------------------------------------------------------------------
# Shared control, kept for the category's normalization pipeline
# ---------------------------------------------------------------------------


def detect_invisible_unicode_smuggling(pkg: dict) -> Finding:
    """The raw invisible-carrier scan, shared verbatim with AST04.

    Retained as a callable helper and NOT registered in :data:`DETECTORS`: on its
    own it reports a carrier, and AST08's own mitigation says to report a carrier
    as a finding in its own right "only where legitimate use does not explain it".
    A BOM is legitimate; a zero-width run that decodes to text is not. The scoped
    version of this signal lives inside `detect_obfuscated_instruction`, where the
    stripped view is re-matched and the zero-width run is decoded before anything
    is reported. The unscoped scan stays available for callers that want the raw
    carrier inventory -- and stays out of the F1 denominator, which is where
    counting it would have been an overclaim.
    """
    return _shared_invisible_unicode(pkg, "AST08-invisible-unicode-smuggling")


# ---------------------------------------------------------------------------
# Loading a package off disk
# ---------------------------------------------------------------------------

_SPECIAL_KINDS = (
    (stat.S_ISFIFO, "fifo"),
    (stat.S_ISSOCK, "socket"),
    (stat.S_ISCHR, "character-device"),
    (stat.S_ISBLK, "block-device"),
)


def _special_kind(mode: int) -> str:
    for predicate, name in _SPECIAL_KINDS:
        if predicate(mode):
            return name
    return "unknown"


def load_package_dir(root: str | os.PathLike[str]) -> dict:
    """Load a skill package directory into the package dict these checks consume.

    Symlinks are recorded and never followed -- following one is how a scanner
    walks out of its own scan root (`AST08-S07`). Every regular file contributes
    its exact bytes to ``blobs``; the utf-8-decodable ones additionally appear as
    text in ``files``, so a package loaded here is consumable by every other
    detector in this repo unchanged.
    """
    base = Path(root)
    resolved_root = base.resolve()
    files: dict[str, str] = {}
    blobs: dict[str, bytes] = {}
    entries: dict[str, dict] = {}

    def walk(directory: Path) -> None:
        for entry in sorted(os.scandir(directory), key=lambda e: e.name):
            rel = Path(entry.path).relative_to(base).as_posix()
            if entry.is_symlink():
                target = os.readlink(entry.path)
                destination = (Path(entry.path).parent / target).resolve()
                escapes = destination != resolved_root and resolved_root not in destination.parents
                entries[rel] = {"type": "symlink", "target": target, "escapes_scan_root": escapes}
                continue
            mode = entry.stat(follow_symlinks=False).st_mode
            if stat.S_ISDIR(mode):
                entries[rel] = {"type": "dir"}
                walk(Path(entry.path))
            elif stat.S_ISREG(mode):
                data = Path(entry.path).read_bytes()
                blobs[rel] = data
                entries[rel] = {"type": "file", "size": len(data)}
                try:
                    files[rel] = data.decode("utf-8")
                except UnicodeDecodeError:
                    pass
            else:
                entries[rel] = {"type": _special_kind(mode)}

    walk(base)
    description = ""
    skill_md = files.get("SKILL.md", "")
    match = re.search(r"^description:\s*(.+)$", skill_md, re.M)
    if match:
        description = match.group(1).strip().strip("\"'")
    return {
        "name": base.name,
        "manifest": {"description": description},
        "files": files,
        "blobs": blobs,
        "entries": entries,
    }


DETECTORS: dict[str, Callable[[dict], Finding]] = {
    "AST08-S02": detect_obfuscated_instruction,
    "AST08-S04": detect_context_dependent_malice,
    "AST08-S07": detect_scanner_host_hazard,
    "AST08-S08": detect_bytecode_cache_poisoning,
}


def run_all(pkg: dict) -> list[Finding]:
    return _run_all(DETECTORS, pkg)


def f1_report(fixtures: list[tuple[dict, set[str]]]) -> dict:
    return _f1_report(STATIC_DETECTABLE, DETECTORS, fixtures, F1_SCOPE)
