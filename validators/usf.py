"""validators/usf.py -- Universal Skill Format (USF) v1.0 loader, validator, and JCS canonicalizer.

The USF manifest is proposed in the OWASP Agentic Skills Top 10 whitepaper under
AST10 (Cross-Platform Reuse) as "a cross-platform standard that mitigates AST10
and provides the metadata foundation required to address AST01 through AST09".
This module is the executable half of that proposal:

- ``schemas/usf-v1.schema.json`` constrains the manifest's SHAPE.
- this module constrains its SEMANTICS -- the rules a JSON Schema structurally
  cannot express.

Semantics enforced here, each anchored to the whitepaper's own text:

1. **Network evaluation is default-deny.** "only domains listed in network.allow
   are permitted egress, so deny: '*' is redundant with - not an override of -
   that default, kept only for explicit auditability." ``network_egress_allowed``
   consults ``allow`` alone; ``deny`` is checked only for the literal ``"*"`` and
   rejected otherwise, because any other value implies the author believes deny
   is an override list, which inverts the precedence rule.
2. **deny_write wins over write.** "deny_write always wins over write for any
   path it lists" -- ``write_allowed``.
3. **Explicit paths only, no wildcards** in ``permissions.files``.
4. **Identity files are protected by default.** "permissions.deny_write protects
   identity files (SOUL.md, MEMORY.md) by default - must be explicitly
   overridden." This module treats ``SOUL.md``, ``MEMORY.md`` and ``AGENTS.md``
   (the third file named in the whitepaper's own manifest example) as the
   identity set: each must appear in ``deny_write`` unless it is explicitly
   granted in ``write``.
5. **risk_tier is an untrusted author assertion** that "MUST be independently
   validated against the declared permission manifest". ``derive_risk_tier``
   computes a floor from the permissions and under-declaration is an error.
6. **Signing is over RFC 8785 (JCS) canonical JSON**, "excluding the 'signature'
   field and including 'content_hash'" -- ``signing_payload``.

Third-party runtime dependencies: ``PyYAML`` (MIT) for manifest loading and
``jsonschema`` (MIT) for the structural pass. Both sit inside the permissive
license family recorded in THIRD_PARTY_LICENSES.md. ``jsonschema`` is imported
defensively so the semantic half of this module stays usable without it.

Host-only matching, no wildcard subdomains, and explicit-path-only permissions
are the whitepaper's rules. Two additional strictness rules are this repo's own,
and are labelled as such in their error messages: a ``..`` segment is rejected in
permission paths (an explicit path that can escape its root is not explicit), and
``scan_status.scanner``/``result`` must agree about whether a scan happened.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from json import loads as _json_loads
from pathlib import Path
from typing import Any, Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "usf-v1.schema.json"

USF_VERSION = "1.0"

#: Explicit, auditable placeholder for "this package ships without a signature".
#: Recognised as a *state*, never as a malformed manifest.
SIGNATURE_UNSIGNED = "unsigned"

SIGNATURE_STATE_UNSIGNED = "unsigned"
SIGNATURE_STATE_SIGNED = "signed"
SIGNATURE_STATE_MALFORMED = "malformed"

#: Agent identity files. The whitepaper's format-design rationale names SOUL.md
#: and MEMORY.md; its own example manifest denies AGENTS.md alongside them with
#: the comment "Identity files require explicit grant".
IDENTITY_FILES: tuple[str, ...] = ("SOUL.md", "MEMORY.md", "AGENTS.md")

RISK_TIERS: tuple[str, ...] = ("L0", "L1", "L2", "L3")
_TIER_RANK = {tier: index for index, tier in enumerate(RISK_TIERS)}

#: Glob metacharacters. "Explicit paths only; no wildcards" (whitepaper, inline
#: comment on permissions.files.read).
_WILDCARD_CHARS = "*?[]{}"

_HOSTNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$")

#: Tools that can originate egress. Declaring one with an empty allowlist is not
#: an error under default-deny (the tool simply cannot reach anything) but it is
#: a declaration inconsistency worth surfacing.
_NETWORK_CAPABLE_TOOLS = frozenset({"web_fetch", "web_search", "fetch", "http_request", "http", "browser", "curl"})

#: IEEE-754 doubles represent every integer in [-2**53, 2**53] exactly. RFC 8785
#: serializes numbers as doubles, so anything outside that range cannot round-trip.
_MAX_EXACT_INT = 2**53


class UsfError(Exception):
    """Base class for USF loading/canonicalization failures."""


class UsfLoadError(UsfError):
    """The manifest could not be parsed into a JSON-compatible mapping."""


class CanonicalizationError(UsfError):
    """The value cannot be serialized under RFC 8785."""


class SchemaUnavailableError(UsfError):
    """``jsonschema`` is not importable, so the structural pass cannot run."""


# --------------------------------------------------------------------------- #
# RFC 8785 (JCS) canonicalization
# --------------------------------------------------------------------------- #
#
# Implemented directly rather than delegated to ``json.dumps``: ``json.dumps``
# sorts keys by Unicode code point, while RFC 8785 sorts by UTF-16 code unit, and
# its float repr is not the ECMAScript ``Number::toString`` the RFC mandates.
# Both differences are silent -- they produce a plausible-looking byte string that
# a verifier computing the real JCS form would reject.

_STRING_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def _escape_string(value: str) -> str:
    """RFC 8785 section 3.2.2.2 string serialization.

    Only ``"``, ``\\`` and the C0 controls are escaped; every other code point is
    emitted literally and carried by the UTF-8 encoding of the final output.
    """
    out = ['"']
    for char in value:
        escape = _STRING_ESCAPES.get(char)
        if escape is not None:
            out.append(escape)
        elif char < "\x20":
            out.append(f"\\u{ord(char):04x}")
        elif "\ud800" <= char <= "\udfff":
            raise CanonicalizationError("lone surrogate in string: not valid UTF-8, cannot be canonicalized")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _serialize_int(value: int) -> str:
    if abs(value) > _MAX_EXACT_INT:
        raise CanonicalizationError(
            f"integer {value} exceeds the IEEE-754 exact range +/-2**53; RFC 8785 "
            f"numbers are doubles and this value cannot round-trip"
        )
    return str(value)


def _es_number(value: float) -> str:
    """ECMAScript ``Number::toString`` for a finite float (RFC 8785 section 3.2.2.3).

    Derives the shortest round-tripping digit string ``s`` and its decimal
    exponent ``n`` from CPython's ``repr`` (also shortest round-tripping), then
    applies the ECMA-262 formatting rules verbatim.
    """
    if value != value or value in (float("inf"), float("-inf")):
        raise CanonicalizationError("NaN and Infinity have no RFC 8785 serialization")
    if value == 0:
        return "0"  # collapses -0.0, per ECMAScript
    if value < 0:
        return "-" + _es_number(-value)

    text = repr(value)
    if "e" in text:
        mantissa, _, exponent_text = text.partition("e")
        exponent = int(exponent_text)
    else:
        mantissa, exponent = text, 0
    int_part, _, frac_part = mantissa.partition(".")

    digits = int_part + frac_part
    point = len(int_part) + exponent
    stripped = digits.lstrip("0")
    point -= len(digits) - len(stripped)
    s = stripped.rstrip("0")
    if not s:  # pragma: no cover - unreachable: value == 0 handled above
        return "0"
    k = len(s)
    n = point

    if k <= n <= 21:
        return s + "0" * (n - k)
    if 0 < n <= 21:
        return s[:n] + "." + s[n:]
    if -6 < n <= 0:
        return "0." + "0" * (-n) + s
    exponent_sign = "+" if n - 1 >= 0 else "-"
    exponent_digits = str(abs(n - 1))
    if k == 1:
        return f"{s}e{exponent_sign}{exponent_digits}"
    return f"{s[0]}.{s[1:]}e{exponent_sign}{exponent_digits}"


def _utf16_sort_key(key: str) -> bytes:
    """Sort key reproducing RFC 8785's UTF-16 code-unit ordering.

    Comparing big-endian UTF-16 byte strings is equivalent to comparing the
    code-unit sequences numerically. This differs from Python's native code-point
    ordering for astral characters: U+1F600 encodes as the surrogate pair
    D83D DE00, so it sorts *before* U+FB00 under UTF-16 and *after* it under code
    points.
    """
    try:
        return key.encode("utf-16-be")
    except UnicodeEncodeError as exc:  # lone surrogate in a key
        raise CanonicalizationError(f"object key is not encodable: {key!r}") from exc


def _serialize(value: Any, out: list[str], stack: list[int]) -> None:
    if value is None:
        out.append("null")
        return
    if value is True:
        out.append("true")
        return
    if value is False:
        out.append("false")
        return
    if isinstance(value, int):  # bool already handled above
        out.append(_serialize_int(value))
        return
    if isinstance(value, float):
        out.append(_es_number(value))
        return
    if isinstance(value, str):
        out.append(_escape_string(value))
        return
    if isinstance(value, (list, tuple)):
        if id(value) in stack:
            raise CanonicalizationError("cyclic structure cannot be canonicalized")
        stack.append(id(value))
        out.append("[")
        for index, item in enumerate(value):
            if index:
                out.append(",")
            _serialize(item, out, stack)
        out.append("]")
        stack.pop()
        return
    if isinstance(value, dict):
        if id(value) in stack:
            raise CanonicalizationError("cyclic structure cannot be canonicalized")
        stack.append(id(value))
        for key in value:
            if not isinstance(key, str):
                raise CanonicalizationError(
                    f"object key {key!r} is not a string; RFC 8785 canonicalizes JSON, which has string keys only"
                )
        out.append("{")
        for index, key in enumerate(sorted(value, key=_utf16_sort_key)):
            if index:
                out.append(",")
            out.append(_escape_string(key))
            out.append(":")
            _serialize(value[key], out, stack)
        out.append("}")
        stack.pop()
        return
    raise CanonicalizationError(
        f"value of type {type(value).__name__} has no JSON representation; canonicalization refuses to guess one"
    )


def canonicalize(value: Any) -> bytes:
    """Return the RFC 8785 (JCS) canonical JSON serialization of ``value`` as UTF-8.

    Deterministic by construction: keys are sorted by UTF-16 code unit, there is
    no insignificant whitespace, numbers use ECMAScript ``Number::toString``, and
    the output is UTF-8. Two structurally equal inputs therefore produce
    byte-identical output regardless of key insertion order.
    """
    out: list[str] = []
    _serialize(value, out, [])
    return "".join(out).encode("utf-8")


def signing_payload(manifest: dict) -> bytes:
    """Bytes an ed25519 signature over a USF manifest is computed on.

    Per the whitepaper's ``signature`` comment: the RFC 8785 canonical JSON
    serialization of the manifest, "excluding the 'signature' field and including
    'content_hash'". Excluding ``content_hash`` here would break the chain that
    binds the signature to the package bytes, so its absence is a hard error
    rather than a silently smaller payload.
    """
    if not isinstance(manifest, dict):
        raise UsfError("manifest must be a mapping")
    if "content_hash" not in manifest:
        raise UsfError(
            "cannot build a signing payload: 'content_hash' is absent, and the "
            "signature must cover it (whitepaper: 'excluding the signature field "
            "and including content_hash')"
        )
    return canonicalize({k: v for k, v in manifest.items() if k != "signature"})


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


class _UsfYamlLoader(yaml.SafeLoader):
    """SafeLoader with the implicit timestamp resolver removed.

    ``yaml.safe_load`` turns an unquoted ``2026-02-15`` into a ``datetime.date``,
    which has no JSON representation and would make canonicalization -- and
    therefore signature verification -- fail on a manifest that looks fine. Dates
    stay strings here. (Using SafeLoader at all is the AST04 rule: ``UnsafeLoader``
    on a manifest is code execution.)
    """


_UsfYamlLoader.yaml_implicit_resolvers = {
    prefix: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for prefix, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def load_manifest(path: str | Path) -> dict:
    """Load a USF manifest from a ``.yaml``/``.yml``/``.json`` file.

    Raises ``UsfLoadError`` unless the document parses to a JSON-compatible
    mapping.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise UsfLoadError(f"cannot read manifest {path}: {exc}") from exc
    return loads_manifest(text, source=str(path), json_mode=path.suffix == ".json")


def loads_manifest(text: str, *, source: str = "<string>", json_mode: bool = False) -> dict:
    """Parse a USF manifest from text. YAML by default; JSON when ``json_mode``."""
    try:
        data = _json_loads(text) if json_mode else yaml.load(text, Loader=_UsfYamlLoader)
    except Exception as exc:  # noqa: BLE001 - both parsers raise their own types
        raise UsfLoadError(f"cannot parse manifest {source}: {exc}") from exc
    if not isinstance(data, dict):
        raise UsfLoadError(f"manifest {source} must be a mapping, got {type(data).__name__}")
    try:
        canonicalize(data)
    except CanonicalizationError as exc:
        raise UsfLoadError(
            f"manifest {source} contains a value with no JSON representation, so it "
            f"could never be canonically signed: {exc}"
        ) from exc
    return data


# --------------------------------------------------------------------------- #
# Structural pass (JSON Schema)
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def load_schema() -> dict:
    """Return the parsed ``schemas/usf-v1.schema.json``."""
    return _json_loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def schema_errors(manifest: dict) -> list[str]:
    """Structural errors from the JSON Schema pass, in document order."""
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - dependency is installed here
        raise SchemaUnavailableError(
            "jsonschema is required for the structural pass "
            "(`python3 -m pip install jsonschema`); the semantic checks in "
            "semantic_errors() run without it"
        ) from exc

    validator = jsonschema.Draft202012Validator(load_schema())
    messages: list[str] = []
    for error in sorted(validator.iter_errors(manifest), key=lambda e: list(e.absolute_path)):
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        messages.append(f"schema: {location}: {error.message}")
    return messages


# --------------------------------------------------------------------------- #
# Permission semantics
# --------------------------------------------------------------------------- #


def _as_list(value: Any) -> list:
    return list(value) if isinstance(value, (list, tuple)) else []


def _normalize_path(path: str) -> str:
    """Strip a single leading ``./`` so ``./SKILL.md`` and ``SKILL.md`` compare equal."""
    return path[2:] if path.startswith("./") else path


def _basename(path: str) -> str:
    return _normalize_path(path).rsplit("/", 1)[-1]


def path_errors(paths: Iterable[Any], location: str) -> list[str]:
    """Validate one ``permissions.files`` list: explicit paths only."""
    errors: list[str] = []
    for entry in paths:
        if not isinstance(entry, str) or not entry.strip():
            errors.append(f"{location}: entry {entry!r} is not a non-empty path string")
            continue
        found = [char for char in _WILDCARD_CHARS if char in entry]
        if found:
            errors.append(
                f"{location}: {entry!r} contains the glob metacharacter(s) "
                f"{''.join(found)!r}; USF v1.0 permits explicit paths only, no "
                f"wildcards -- a glob's effective scope depends on the host "
                f"filesystem, so it cannot be reviewed before install"
            )
        if ".." in _normalize_path(entry).split("/"):
            errors.append(
                f"{location}: {entry!r} contains a '..' segment; a path that can "
                f"escape its declared root is not an explicit path (repo strictness "
                f"rule, beyond the whitepaper text)"
            )
    return errors


def host_errors(hosts: Iterable[Any], location: str) -> list[str]:
    """Validate ``permissions.network.allow``: bare lowercase hostnames only.

    "allow/deny matching is host-only (no wildcard subdomains, scheme, or port
    matching) unless a future revision states otherwise."
    """
    errors: list[str] = []
    for entry in hosts:
        if not isinstance(entry, str) or not entry.strip():
            errors.append(f"{location}: entry {entry!r} is not a non-empty host string")
            continue
        if "*" in entry:
            errors.append(
                f"{location}: {entry!r} uses a wildcard; USF v1.0 matching is "
                f"host-only, so a wildcard subdomain would never match and reads as "
                f"broader access than is actually granted"
            )
            continue
        if "://" in entry:
            errors.append(
                f"{location}: {entry!r} includes a scheme; the allowlist holds bare hosts (scheme is not matched)"
            )
            continue
        if "/" in entry:
            errors.append(
                f"{location}: {entry!r} includes a path; the allowlist holds bare hosts (path is not matched)"
            )
            continue
        if ":" in entry:
            errors.append(
                f"{location}: {entry!r} includes a port; the allowlist holds bare hosts (port is not matched)"
            )
            continue
        if entry != entry.lower():
            errors.append(
                f"{location}: {entry!r} is not lowercase; hosts must be normalized so "
                f"matching is deterministic across runtimes"
            )
            continue
        if not _HOSTNAME_RE.match(entry):
            errors.append(f"{location}: {entry!r} is not a valid hostname")
    return errors


def network_egress_allowed(manifest: dict, host: str) -> bool:
    """Default-deny egress evaluation.

    Only hosts in ``permissions.network.allow`` are permitted. ``network.deny`` is
    deliberately not consulted: under default-deny it is redundant with, not an
    override of, the default, and is kept in the manifest purely for explicit
    auditability. Matching is exact and host-only -- ``api.example.com`` in the
    allowlist does not permit ``evil.api.example.com``.
    """
    network = manifest.get("permissions", {}).get("network", {}) or {}
    allow = {h.lower() for h in _as_list(network.get("allow")) if isinstance(h, str)}
    return host.strip().lower() in allow


def write_allowed(manifest: dict, path: str) -> bool:
    """Most-specific-wins write evaluation: ``deny_write`` beats ``write``.

    A bare-filename ``deny_write`` entry (``MEMORY.md``) denies that filename
    wherever it appears; an entry containing a separator denies exactly that path.
    Anything not in ``write`` is denied by default.
    """
    return _write_allowed(manifest.get("permissions", {}).get("files", {}) or {}, path)


def _write_allowed(files: dict, path: str) -> bool:
    target = _normalize_path(path)
    target_base = _basename(path)

    for entry in _as_list(files.get("deny_write")):
        if not isinstance(entry, str):
            continue
        normalized = _normalize_path(entry)
        if "/" in normalized:
            if normalized == target:
                return False
        elif normalized in (target, target_base):
            return False

    for entry in _as_list(files.get("write")):
        if isinstance(entry, str) and _normalize_path(entry) == target:
            return True
    return False


def _identity_state(files: dict, identity_file: str) -> tuple[bool, bool]:
    """Return ``(denied, granted)`` for one identity file."""
    denied = any(
        isinstance(entry, str) and _basename(entry) == identity_file for entry in _as_list(files.get("deny_write"))
    )
    granted = any(
        isinstance(entry, str) and _basename(entry) == identity_file for entry in _as_list(files.get("write"))
    )
    return denied, granted


def derive_risk_tier(permissions: dict) -> str:
    """Derive the minimum defensible ``risk_tier`` from a declared permission set.

    The whitepaper requires that ``risk_tier`` "MUST be independently validated
    against the declared permission manifest" and that "automated governance
    policies MUST be driven by permission-derived risk classification". This is
    that derivation. The ladder is calibrated against the whitepaper's own example
    manifest (one explicit config write + one allowlisted domain + ``shell:
    false`` is declared ``L1``):

    - ``L0`` -- reads only: no writes, no egress, no shell.
    - ``L1`` -- explicit non-identity writes and/or an allowlisted egress.
    - ``L2`` -- shell access.
    - ``L3`` -- shell access combined with write access, or a granted write to an
      agent identity file (``SOUL.md``/``MEMORY.md``/``AGENTS.md``), which is
      destructive by definition: it rewrites the agent rather than its data.

    Writes count only when they are *effective*. A ``write`` entry that
    ``deny_write`` fully shadows grants no capability, so it cannot raise the
    tier -- deriving otherwise would make the deny_write-wins rule apply in
    ``write_allowed`` but not here, and over-restrict a manifest that is merely
    redundant. The redundancy is surfaced as a warning by the semantic pass.
    """
    files = permissions.get("files", {}) or {}
    writes = [
        entry for entry in _as_list(files.get("write")) if isinstance(entry, str) and _write_allowed(files, entry)
    ]
    egress = [entry for entry in _as_list((permissions.get("network") or {}).get("allow"))]
    shell = bool(permissions.get("shell"))

    for identity_file in IDENTITY_FILES:
        denied, granted = _identity_state(files, identity_file)
        if granted and not denied:
            return "L3"
    if shell and writes:
        return "L3"
    if shell:
        return "L2"
    if writes or egress:
        return "L1"
    return "L0"


def signature_state(manifest: dict) -> str:
    """Classify the ``signature`` field as signed / unsigned / malformed.

    An explicit ``"unsigned"`` placeholder is a *state*, not a defect: it says the
    author declined to sign, which a consumer can act on. A missing or misshapen
    value is ``"malformed"`` -- indistinguishable from a signature stripped during
    a port, which is the AST10 failure this field exists to make visible.
    """
    value = manifest.get("signature")
    if value == SIGNATURE_UNSIGNED:
        return SIGNATURE_STATE_UNSIGNED
    if isinstance(value, str) and re.fullmatch(r"ed25519:[0-9a-f]{128}", value):
        return SIGNATURE_STATE_SIGNED
    return SIGNATURE_STATE_MALFORMED


def verify_signature(manifest: dict, *, public_key_hex: str | None = None) -> bool:
    """Verify the manifest's ed25519 signature over its JCS signing payload.

    ``public_key_hex`` defaults to ``author.signing_key``. Returns ``False`` for a
    bad signature; raises ``UsfError`` when there is nothing to verify (unsigned
    or malformed) or no key to verify against, so "unverifiable" can never be
    mistaken for "verified".
    """
    state = signature_state(manifest)
    if state != SIGNATURE_STATE_SIGNED:
        raise UsfError(f"manifest is not signed (signature_state={state!r})")

    key_text = public_key_hex or (manifest.get("author") or {}).get("signing_key")
    if not isinstance(key_text, str) or not key_text.startswith("ed25519:"):
        raise UsfError(
            "no ed25519 public key available: author.signing_key is absent or "
            "malformed, so the signature cannot be verified"
        )

    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:  # pragma: no cover - dependency is installed here
        raise UsfError(
            "ed25519 verification needs the `cryptography` package (`python3 -m pip install cryptography`)"
        ) from exc

    key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_text.split(":", 1)[1]))
    signature = bytes.fromhex(manifest["signature"].split(":", 1)[1])
    try:
        key.verify(signature, signing_payload(manifest))
    except InvalidSignature:
        return False
    return True


def _content_sha256(skill_dir: Path) -> str:
    """Import the vendored surface hasher, bootstrapping sys.path if run as a script."""
    try:
        from scripts.content_hash import content_sha256
    except ImportError:  # pragma: no cover - only when run outside the repo root
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from scripts.content_hash import content_sha256
    return content_sha256(skill_dir)


def compute_content_hash(skill_dir: str | Path) -> str:
    """``sha256:<hex>`` over a skill's shipped surface.

    The surface is ``scripts/content_hash.py``'s ``SURFACE_GLOBS`` (SKILL.md,
    references/*.md, scripts/*.py, evals/evals.json) -- one definition shared with
    ``scripts/ship_floor.py`` so the writer and every checker cannot drift. Note
    the honest divergence from the whitepaper's "hash of the complete skill
    package": ``skill.usf.yaml`` itself is outside that surface, which is what
    keeps the hash from depending on the field that carries it.
    """
    return "sha256:" + _content_sha256(Path(skill_dir))


# --------------------------------------------------------------------------- #
# Semantic pass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class UsfValidationResult:
    """Outcome of validating one manifest.

    ``errors`` block acceptance; ``warnings`` are declaration inconsistencies a
    reviewer should see but that do not make the manifest invalid.
    ``signature_state`` is reported separately because "unsigned" is a policy
    decision for the consumer, not a validation failure.
    """

    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    signature_state: str = SIGNATURE_STATE_MALFORMED
    derived_risk_tier: str | None = None
    schema_checked: bool = True
    metadata: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def semantic_errors(manifest: dict, *, skill_dir: Path | None = None) -> tuple[list[str], list[str]]:
    """Return ``(errors, warnings)`` for the semantics the schema cannot express.

    Assumes the manifest already passed the structural pass; callers that skip the
    schema get best-effort results on the fields that are present.
    """
    errors: list[str] = []
    warnings: list[str] = []

    permissions = manifest.get("permissions") or {}
    files = permissions.get("files") or {}
    network = permissions.get("network") or {}

    # 1. permissions.files -- explicit paths only.
    for key in ("read", "write", "deny_write"):
        errors.extend(path_errors(_as_list(files.get(key)), f"permissions.files.{key}"))

    # 2. Identity files must be denied unless explicitly granted.
    for identity_file in IDENTITY_FILES:
        denied, granted = _identity_state(files, identity_file)
        if denied and granted:
            warnings.append(
                f"permissions.files: {identity_file} appears in both write and "
                f"deny_write; deny_write wins, so the write grant is inert -- remove "
                f"one so the manifest states a single intent"
            )
        elif not denied and not granted:
            errors.append(
                f"permissions.files.deny_write: identity file {identity_file} is "
                f"neither denied nor explicitly granted in write; USF v1.0 protects "
                f"identity files by default and requires an explicit override"
            )

    # 3. Network -- default-deny precedence.
    errors.extend(host_errors(_as_list(network.get("allow")), "permissions.network.allow"))
    if "deny" in network:
        deny = network.get("deny")
        if deny != "*":
            errors.append(
                f"permissions.network.deny: {deny!r} is not a deny list. Evaluation "
                f"precedence is default-deny -- only hosts in network.allow get "
                f"egress -- so deny is redundant with that default and its only "
                f'auditable value is "*". Writing anything else asserts an override '
                f"semantics this format does not have"
            )
    else:
        warnings.append(
            "permissions.network.deny is absent. Egress is still default-deny, but "
            'the whitepaper keeps the explicit "*" for auditability: a reviewer '
            "cannot tell an intentional omission from metadata dropped in a port"
        )

    allow_hosts = _as_list(network.get("allow"))
    tools = {tool for tool in _as_list(permissions.get("tools")) if isinstance(tool, str)}
    network_tools = sorted(tools & _NETWORK_CAPABLE_TOOLS)
    if network_tools and not allow_hosts:
        warnings.append(
            f"permissions.tools declares network-capable tool(s) {network_tools} while "
            f"permissions.network.allow is empty; under default-deny they can reach "
            f"nothing, so either the allowlist or the tool declaration is wrong"
        )

    # 4. risk_tier is an untrusted author assertion.
    derived = derive_risk_tier(permissions)
    declared = manifest.get("risk_tier")
    if declared in _TIER_RANK:
        if _TIER_RANK[declared] < _TIER_RANK[derived]:
            errors.append(
                f"risk_tier: declared {declared} is below the {derived} floor derived "
                f"from the declared permissions. risk_tier is an untrusted author "
                f"assertion and MUST be validated against the permission manifest; "
                f"under-declaration is the AST04 risk_tier-spoofing shape"
            )
        elif _TIER_RANK[declared] > _TIER_RANK[derived]:
            warnings.append(
                f"risk_tier: declared {declared} is above the {derived} floor derived "
                f"from the declared permissions. Over-declaration is conservative and "
                f"allowed, but a policy engine keyed on risk_tier will over-restrict"
            )
    elif declared is not None:
        errors.append(
            f"risk_tier: {declared!r} is not one of {list(RISK_TIERS)} (L0=safe, L1=low, L2=elevated, L3=destructive)"
        )

    # 5. Signature / identity coherence.
    state = signature_state(manifest)
    author = manifest.get("author") or {}
    if state == SIGNATURE_STATE_MALFORMED:
        errors.append(
            f"signature: {manifest.get('signature')!r} is neither an "
            f"'ed25519:<128 hex>' signature nor the explicit \"unsigned\" placeholder. "
            f"An absent or misshapen signature is indistinguishable from one stripped "
            f"during a port (AST10 manifest stripping)"
        )
    if state == SIGNATURE_STATE_SIGNED and not author.get("signing_key"):
        errors.append(
            "author.signing_key: absent while signature is present; the signature "
            "covers the JCS canonical manifest but there is no key to verify it "
            "against, which is a false trust signal rather than an integrity control"
        )
    if not author.get("identity"):
        warnings.append(
            "author.identity: no decentralized identity anchor declared; a registry "
            "cannot bind this package to a publisher, so installation counts and "
            "author names remain unverifiable trust signals"
        )

    # 6. scan_status coherence.
    if "scan_status" not in manifest:
        warnings.append(
            "scan_status is absent; a consumer cannot distinguish 'never scanned' "
            "from 'scan metadata lost in a port'. Declare result: unscanned instead "
            "of omitting the field"
        )
    else:
        scan = manifest.get("scan_status") or {}
        result = scan.get("result")
        scanner = scan.get("scanner")
        if result == "unscanned" and scanner not in (None, "none"):
            errors.append(
                f"scan_status: result 'unscanned' names scanner {scanner!r}; an "
                f"unscanned package must declare scanner: none so the pair cannot "
                f"read as a completed scan (repo strictness rule)"
            )
        if result != "unscanned" and scanner == "none":
            errors.append(
                f"scan_status: scanner 'none' reports result {result!r}; a result "
                f"without a scanner is an unattributable claim (repo strictness rule)"
            )

    # 7. changelog must cover the declared version.
    version = manifest.get("version")
    changelog = _as_list(manifest.get("changelog"))
    if version and changelog:
        versions = {entry.get("version") for entry in changelog if isinstance(entry, dict)}
        if version not in versions:
            errors.append(
                f"changelog: no entry for the declared version {version!r} "
                f"(entries: {sorted(v for v in versions if v)}); an unlogged version "
                f"is the AST07 update-drift shape -- a release nobody can diff"
            )

    # 8. Bindings to the package on disk.
    if skill_dir is not None:
        skill_dir = Path(skill_dir)
        declared_hash = manifest.get("content_hash")
        if isinstance(declared_hash, str):
            actual = compute_content_hash(skill_dir)
            if declared_hash != actual:
                errors.append(
                    f"content_hash: manifest declares {declared_hash} but the package "
                    f"surface at {skill_dir} hashes to {actual}; the signature would "
                    f"cover a package that is not the one shipped"
                )
        skill_md = skill_dir / "SKILL.md"
        native_name = _skill_md_name(skill_md)
        if native_name is not None and manifest.get("name") != native_name:
            errors.append(
                f"name: USF manifest says {manifest.get('name')!r} but the "
                f"platform-native SKILL.md says {native_name!r}; two identities for "
                f"one package is exactly the normalization gap AST10 describes"
            )

    return errors, warnings


def _skill_md_name(path: Path) -> str | None:
    """Read the ``name`` from a SKILL.md YAML frontmatter block, or ``None``."""
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    try:
        frontmatter = yaml.load(text[4:end], Loader=_UsfYamlLoader)
    except yaml.YAMLError:
        return None
    if isinstance(frontmatter, dict):
        name = frontmatter.get("name")
        return name if isinstance(name, str) else None
    return None


def validate_manifest(
    manifest: dict,
    *,
    skill_dir: str | Path | None = None,
    check_schema: bool = True,
) -> UsfValidationResult:
    """Validate a loaded manifest structurally and semantically.

    When the structural pass fails, the semantic pass is skipped: its checks
    assume the shape the schema guarantees, and a cascade of type errors would
    bury the one real problem. ``signature_state`` is still reported.
    """
    state = signature_state(manifest)
    if check_schema:
        structural = schema_errors(manifest)
        if structural:
            return UsfValidationResult(
                errors=tuple(structural),
                warnings=(),
                signature_state=state,
                derived_risk_tier=None,
                schema_checked=True,
            )

    errors, warnings = semantic_errors(manifest, skill_dir=Path(skill_dir) if skill_dir is not None else None)
    return UsfValidationResult(
        errors=tuple(errors),
        warnings=tuple(warnings),
        signature_state=state,
        derived_risk_tier=derive_risk_tier(manifest.get("permissions") or {}),
        schema_checked=check_schema,
        metadata={"name": manifest.get("name"), "version": manifest.get("version")},
    )


def validate_manifest_file(
    path: str | Path, *, skill_dir: str | Path | None = None, check_schema: bool = True
) -> UsfValidationResult:
    """Load and validate a manifest file; ``skill_dir`` defaults to its parent."""
    path = Path(path)
    manifest = load_manifest(path)
    return validate_manifest(
        manifest,
        skill_dir=path.parent if skill_dir is None else skill_dir,
        check_schema=check_schema,
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

_CONTENT_HASH_LINE_RE = re.compile(r"^(?P<indent>\s*)content_hash:\s*.*$", re.MULTILINE)


def update_content_hash(path: str | Path) -> tuple[str, str]:
    """Rewrite a manifest's ``content_hash`` line in place; return ``(old, new)``.

    A targeted line rewrite rather than a YAML round-trip, because PyYAML would
    discard every comment in the file -- and the comments are where the manifest
    explains its own permission decisions.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    match = _CONTENT_HASH_LINE_RE.search(text)
    if match is None:
        raise UsfError(f"{path}: no top-level 'content_hash:' line to update")
    old = match.group(0).split(":", 1)[1].strip().strip("\"'")
    new = compute_content_hash(path.parent)
    if old == new:
        return old, new
    replacement = f'{match.group("indent")}content_hash: "{new}"'
    path.write_text(text[: match.start()] + replacement + text[match.end() :], encoding="utf-8")
    return old, new


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="validators/usf.py",
        description="Validate Universal Skill Format v1.0 manifests.",
    )
    parser.add_argument("paths", nargs="+", help="manifest files (skill.usf.yaml)")
    parser.add_argument(
        "--update-content-hash",
        action="store_true",
        help="recompute content_hash from the manifest's skill directory and rewrite it",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as failures",
    )
    args = parser.parse_args(argv)

    failed = False
    for raw_path in args.paths:
        path = Path(raw_path)
        if args.update_content_hash:
            old, new = update_content_hash(path)
            status = "unchanged" if old == new else f"{old} -> {new}"
            print(f"{path}: content_hash {status}")
        try:
            result = validate_manifest_file(path)
        except UsfError as exc:
            print(f"{path}: FAIL: {exc}")
            failed = True
            continue
        for message in result.errors:
            print(f"{path}: ERROR: {message}")
        for message in result.warnings:
            print(f"{path}: warn: {message}")
        verdict = "OK" if result.ok else "FAIL"
        print(
            f"{path}: {verdict} "
            f"(signature={result.signature_state}, "
            f"risk_tier floor={result.derived_risk_tier}, "
            f"{len(result.errors)} error(s), {len(result.warnings)} warning(s))"
        )
        if not result.ok or (args.strict and result.warnings):
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
