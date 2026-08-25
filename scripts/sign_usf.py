#!/usr/bin/env python3
"""scripts/sign_usf.py — sign the USF manifests, and anchor the key that signed them.

Every shipped `skill.usf.yaml` carries `signature: "unsigned"`, and `author.identity`
and `author.signing_key` are absent rather than empty. That is not an oversight to be
tidied away by generating a key: publishing a DID or a public key that anchors to
nothing manufactures exactly the false trust signal AST10 warns about, and this repo's
own AST01 skill states the rule it would break — *"A verified signature answers 'who
published this', never 'is this safe'."* A key with no anchor answers neither.

So this tool treats signing and anchoring as ONE operation. `sign` writes
`author.identity`, `author.signing_key` and `signature` in a single rewrite, and both
identity fields are INSIDE the signed payload (the payload is the whole manifest minus
`signature`), so a signature cannot be moved to a different publisher's identity, and an
identity cannot be swapped under an existing signature, without breaking verification.
There is no code path here that produces one without the other.

WHAT THIS BUYS AND WHAT IT DOES NOT
-----------------------------------
A `did:web` anchor is worth exactly as much as control of the domain and its TLS.
Whoever can serve `https://<domain>/.well-known/did.json` can publish a key of their own
and every signature made with it will verify. That is the honest ceiling of this
mechanism, it is printed by `did-doc` and by `verify`, and it is why `verify` without
`--identity` refuses to claim more than internal consistency: a rewriter who re-signs a
modified manifest with its own key passes that check trivially.

KEY CUSTODY
-----------
The private key lives outside this repository (default `~/.config/ast10-signing/`,
directory 0700, key 0600) and is used at release only.

* `keygen` REFUSES to write a key inside the working tree, checked against the git
  toplevel and git dir after `os.path.realpath`, so neither `../` nor a symlink can
  smuggle it in. `sign` applies the same check to `--key`.
* `keygen` and `sign` refuse to run when a CI environment variable is set. A signing key
  CI can reach is a signing key a workflow can exfiltrate. `verify` is the half that
  belongs in CI: it needs nothing secret.
* `.gitignore` covers the conventional key filenames as a backstop, and
  `tests/test_signing_key_never_enters_the_repo.py` fails if anything resembling a
  private key appears in `git ls-files` OR merely sits in the working tree -- ignored is
  not absent. The refusal above is the control; those two are the net.

`docs/signing.md` is the runbook: the four commands in order, the did:web publishing step,
what a verified signature does and does not prove, and key loss and rotation.

STALE HASHES ARE NOT SIGNABLE
-----------------------------
Each manifest signs its own `content_hash`, so signing a manifest whose hash no longer
matches the package would attest to bytes that are not there. `sign` recomputes every
target's hash BEFORE writing anything and refuses the whole run — naming the skill and
the regeneration command — if any one of them has drifted.

THE RELEASE RUN, IN ORDER
-------------------------
    python3 scripts/sign_usf.py keygen
    python3 scripts/sign_usf.py did-doc --identity did:web:example.com --output did.json
    # publish did.json at https://example.com/.well-known/did.json, then:
    python3 scripts/sign_usf.py sign   --identity did:web:example.com
    python3 scripts/sign_usf.py verify --identity did:web:example.com

Exit codes: 0 success; 1 a check failed or the tool refused; 2 usage (argparse);
3 the DID document could not be resolved, so nothing was verified — never confused with
a pass.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:  # pragma: no cover - import-path bootstrap
    sys.path.insert(0, str(REPO_ROOT))

from validators.usf import (  # noqa: E402
    SIGNATURE_STATE_MALFORMED,
    SIGNATURE_STATE_SIGNED,
    SIGNATURE_STATE_UNSIGNED,
    UsfError,
    compute_content_hash,
    load_manifest,
    signature_state,
    signing_payload,
    validate_manifest_file,
    verify_signature,
)

SKILLS_DIR = REPO_ROOT / "skills"
MANIFEST_NAME = "skill.usf.yaml"

#: Default private-key location. Outside the repository by construction, and the
#: `keygen` refusal below is what keeps it that way when someone passes `--out`.
DEFAULT_KEY_PATH = Path("~/.config/ast10-signing/ed25519.pem")

#: Environment variables that mean "this is not a maintainer's laptop".
CI_ENV_VARS = ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "BUILDKITE", "JENKINS_URL", "TF_BUILD")

#: multicodec `ed25519-pub`, varint-encoded: 0xed 0x01. The 0x01 is the varint
#: continuation byte, not padding -- dropping it yields a well-formed multibase string
#: that decodes to the wrong key type, which no verifier is obliged to notice.
MULTICODEC_ED25519_PUB = b"\xed\x01"

#: Bitcoin/IPFS base58 alphabet: no 0, O, I or l.
BASE58BTC_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

#: Verification-method types that carry an ed25519 key as `publicKeyMultibase`.
#: `Ed25519VerificationKey2018` is deliberately absent: it carries `publicKeyBase58`
#: with no multicodec prefix, so accepting it would mean guessing the key type.
ED25519_MULTIBASE_VM_TYPES = ("Ed25519VerificationKey2020", "Multikey")

_MAX_DID_DOCUMENT_BYTES = 1 << 20
_USER_AGENT = "owasp-ast10-agent-skills sign_usf.py"
_DEFAULT_TIMEOUT = 10.0

_EXIT_OK = 0
_EXIT_FAILED = 1
_EXIT_UNRESOLVED = 3

#: Set instead of a prompt when the key is encrypted and the release is scripted.
PASSPHRASE_ENV_VAR = "AST10_SIGNING_PASSPHRASE"


class SigningError(Exception):
    """A refusal or a failure the operator can act on. Printed without a traceback."""


class DidResolutionError(Exception):
    """The DID document could not be fetched or did not publish a usable key.

    Distinct from ``SigningError`` because "could not check" and "checked and failed"
    are different answers, and collapsing them is how an unreachable anchor turns into
    a pass.
    """


# --------------------------------------------------------------------------- #
# base58btc / multibase
# --------------------------------------------------------------------------- #


def base58btc_encode(data: bytes) -> str:
    """Base58 (Bitcoin alphabet) encoding of ``data``.

    Hand-rolled because the repository's dependency set is `pyyaml`, `jsonschema` and
    `cryptography` and none of them ships base58 -- adding a dependency to a supply-chain
    audit tool is not free. The algorithm is 20 lines and pinned to published test
    vectors in `tests/scripts/test_sign_usf.py`, including the leading-zero rule that a
    pure big-integer implementation silently gets wrong.
    """
    number = int.from_bytes(data, "big")
    digits: list[str] = []
    while number:
        number, remainder = divmod(number, 58)
        digits.append(BASE58BTC_ALPHABET[remainder])
    # Leading zero BYTES carry no value in the integer and must be re-added as '1's,
    # one per byte, or two distinct keys can encode to the same string.
    for byte in data:
        if byte:
            break
        digits.append(BASE58BTC_ALPHABET[0])
    return "".join(reversed(digits))


def base58btc_decode(text: str) -> bytes:
    """Inverse of :func:`base58btc_encode`. Raises ``ValueError`` on a foreign character."""
    number = 0
    for character in text:
        index = BASE58BTC_ALPHABET.find(character)
        if index < 0:
            raise ValueError(f"{character!r} is not a base58btc character")
        number = number * 58 + index
    body = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    leading_zeros = len(text) - len(text.lstrip(BASE58BTC_ALPHABET[0]))
    return b"\x00" * leading_zeros + body


def public_key_multibase(raw_public_key: bytes) -> str:
    """`publicKeyMultibase` for an ed25519 public key: 'z' + base58btc(0xed 0x01 || key)."""
    if len(raw_public_key) != 32:
        raise SigningError(f"an ed25519 public key is 32 bytes, got {len(raw_public_key)}")
    return "z" + base58btc_encode(MULTICODEC_ED25519_PUB + raw_public_key)


def multibase_to_raw_public_key(value: str) -> bytes:
    """Decode a `publicKeyMultibase` back to 32 raw ed25519 bytes.

    Rejects anything that is not base58btc ('z') or does not carry the ed25519-pub
    multicodec prefix, rather than returning bytes of an unknown key type.
    """
    if not isinstance(value, str) or not value.startswith("z"):
        raise ValueError(f"publicKeyMultibase {value!r} is not base58btc ('z'-prefixed)")
    decoded = base58btc_decode(value[1:])
    if decoded[:2] != MULTICODEC_ED25519_PUB:
        raise ValueError(f"publicKeyMultibase {value!r} does not carry the ed25519-pub multicodec prefix 0xed01")
    if len(decoded) != 34:
        raise ValueError(f"publicKeyMultibase {value!r} decodes to {len(decoded) - 2} key bytes, expected 32")
    return decoded[2:]


# --------------------------------------------------------------------------- #
# did:web
# --------------------------------------------------------------------------- #

# Lowercase, per the did:web method specification -- EXCEPT inside a percent-escape,
# whose hex digits are conventionally uppercase (`did:web:example.com%3A3000`).
_DID_WEB_RE = re.compile(r"^did:web:(?P<msi>(?:[a-z0-9._-]|%[0-9A-Fa-f]{2}|:)+)$")
_DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*(:[0-9]{1,5})?$")


@dataclass(frozen=True)
class DidWeb:
    """A parsed `did:web` identifier and the HTTPS URL it resolves to."""

    did: str
    domain: str
    path_segments: tuple[str, ...]
    url: str

    @property
    def is_path_form(self) -> bool:
        return bool(self.path_segments)


def parse_did_web(identity: str) -> DidWeb:
    """Parse `did:web:<domain>` or `did:web:<domain>:<path>:<segments>`.

    Both forms are implemented. `did:web:example.com` resolves to
    `https://example.com/.well-known/did.json`; `did:web:example.com:path:to` resolves to
    `https://example.com/path/to/did.json` (the `.well-known` segment is NOT inserted in
    the path form, per the did:web method specification). A port is carried as a
    percent-encoded colon, `did:web:example.com%3A3000`.
    """
    if not isinstance(identity, str) or not identity.strip():
        raise SigningError("--identity is required and must be a did:web identifier, e.g. did:web:example.com")
    identity = identity.strip()
    if not identity.startswith("did:web:"):
        raise SigningError(
            f"--identity {identity!r} is not a did:web identifier. This tool anchors to a domain you "
            f"control, which is the USF specification's own example form: did:web:example.com"
        )
    match = _DID_WEB_RE.match(identity)
    if not match:
        raise SigningError(
            f"--identity {identity!r} is not a well-formed did:web identifier. The method-specific "
            f"identifier is lowercase and may contain only [a-z0-9._%:-]"
        )
    parts = match.group("msi").split(":")
    domain = urllib.parse.unquote(parts[0])
    segments = tuple(parts[1:])
    if not _DOMAIN_RE.match(domain):
        raise SigningError(
            f"--identity {identity!r}: {domain!r} is not a hostname. did:web identifiers are lowercase "
            f"and a port is percent-encoded, e.g. did:web:example.com%3A3000"
        )
    if any(not segment for segment in segments):
        raise SigningError(f"--identity {identity!r} has an empty path segment")
    if segments:
        path = "/".join(urllib.parse.unquote(segment) for segment in segments)
        url = f"https://{domain}/{path}/did.json"
    else:
        url = f"https://{domain}/.well-known/did.json"
    return DidWeb(did=identity, domain=domain, path_segments=segments, url=url)


def did_document(did: DidWeb, public_key_hex: str) -> dict:
    """The DID document to publish for ``did`` and one ed25519 key.

    The verification method id uses the multibase key as its fragment (the `did:key`
    convention) rather than a positional `#key-1`: a rotation then publishes a NEW
    identifier instead of quietly redefining the old one, so an archived signature keeps
    naming the key that made it.
    """
    multibase = public_key_multibase(bytes.fromhex(public_key_hex))
    method_id = f"{did.did}#{multibase}"
    return {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/suites/ed25519-2020/v1",
        ],
        "id": did.did,
        "verificationMethod": [
            {
                "id": method_id,
                "type": "Ed25519VerificationKey2020",
                "controller": did.did,
                "publicKeyMultibase": multibase,
            }
        ],
        "authentication": [method_id],
        # The relationship that matters here: a manifest signature is an assertion, and
        # `verify` will not accept a key the document publishes under any other one.
        "assertionMethod": [method_id],
    }


@dataclass(frozen=True)
class PublishedKey:
    """One ed25519 key a DID document publishes under `assertionMethod`."""

    method_id: str
    public_key: str  # "ed25519:<64 hex>", the manifest's `author.signing_key` form

    @property
    def multibase(self) -> str:
        return public_key_multibase(bytes.fromhex(self.public_key.split(":", 1)[1]))


def _http_get(url: str, *, timeout: float) -> tuple[str, bytes]:
    """GET ``url``, returning ``(final_url, body)``. Split out so tests can stub the network."""
    request = urllib.request.Request(  # noqa: S310 - scheme is checked by the caller
        url,
        headers={"Accept": "application/did+json, application/json;q=0.9", "User-Agent": _USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        body = response.read(_MAX_DID_DOCUMENT_BYTES + 1)
        final_url = response.geturl()
    if len(body) > _MAX_DID_DOCUMENT_BYTES:
        raise DidResolutionError(f"{url} returned more than {_MAX_DID_DOCUMENT_BYTES} bytes; refusing to parse it")
    return final_url, body


def assertion_keys(document: object, did: DidWeb) -> list[PublishedKey]:
    """Every ed25519 key ``document`` publishes for `assertionMethod`, as USF key strings."""
    if not isinstance(document, dict):
        raise DidResolutionError(f"{did.url} did not return a JSON object")
    claimed = document.get("id")
    if claimed != did.did:
        raise DidResolutionError(
            f"{did.url} publishes a document for {claimed!r}, not for {did.did}. A DID document that "
            f"does not claim the identifier it was fetched for anchors nothing"
        )
    by_id: dict[str, dict] = {}
    for method in document.get("verificationMethod") or []:
        if isinstance(method, dict) and isinstance(method.get("id"), str):
            by_id[method["id"]] = method

    keys: list[PublishedKey] = []
    problems: list[str] = []
    for entry in document.get("assertionMethod") or []:
        method = by_id.get(entry) if isinstance(entry, str) else entry
        if not isinstance(method, dict):
            problems.append(f"assertionMethod {entry!r} does not resolve to a verification method")
            continue
        method_id = method.get("id") if isinstance(method.get("id"), str) else str(entry)
        if method.get("type") not in ED25519_MULTIBASE_VM_TYPES:
            expected = list(ED25519_MULTIBASE_VM_TYPES)
            problems.append(f"{method_id}: type {method.get('type')!r} is not one of {expected}")
            continue
        try:
            raw = multibase_to_raw_public_key(method.get("publicKeyMultibase"))
        except ValueError as exc:
            problems.append(f"{method_id}: {exc}")
            continue
        keys.append(PublishedKey(method_id=method_id, public_key=f"ed25519:{raw.hex()}"))

    if not keys:
        detail = "; ".join(problems) if problems else "the document lists no assertionMethod"
        raise DidResolutionError(
            f"{did.url} publishes no usable ed25519 assertionMethod key ({detail}). A signature is an "
            f"assertion, so a key published under any other relationship is not accepted here"
        )
    return keys


def resolve_did_web(did: DidWeb, *, timeout: float = _DEFAULT_TIMEOUT) -> list[PublishedKey]:
    """Fetch and parse ``did``'s DID document over HTTPS.

    Every failure mode raises ``DidResolutionError`` -- unreachable host, TLS failure,
    404, a redirect off HTTPS, malformed JSON, wrong `id`, no assertion key. None of them
    can be mistaken for a verified signature by a caller that handles the exception.
    """
    if not did.url.startswith("https://"):  # pragma: no cover - parse_did_web guarantees it
        raise DidResolutionError(f"{did.url} is not https")
    try:
        final_url, body = _http_get(did.url, timeout=timeout)
    except DidResolutionError:
        raise
    except urllib.error.HTTPError as exc:
        raise DidResolutionError(
            f"could not resolve {did.did}: {did.url} returned HTTP {exc.code} {exc.reason}"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - URLError, socket.timeout, ssl.SSLError, OSError
        raise DidResolutionError(f"could not resolve {did.did}: {did.url}: {exc}") from exc
    if not final_url.startswith("https://"):
        raise DidResolutionError(
            f"could not resolve {did.did}: {did.url} redirected to {final_url}, which is not HTTPS. "
            f"The anchor is the domain's TLS; a plaintext hop discards it"
        )
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DidResolutionError(f"could not resolve {did.did}: {did.url} is not valid JSON: {exc}") from exc
    return assertion_keys(document, did)


# --------------------------------------------------------------------------- #
# Key custody
# --------------------------------------------------------------------------- #


def _real(path: str | Path) -> Path:
    """`~` expanded, symlinks followed, `..` applied AFTER them -- not a lexical normalize."""
    return Path(os.path.realpath(os.path.expanduser(str(path))))


def protected_roots() -> tuple[Path, ...]:
    """Directories a private key may never be written into: the working tree and the git dir.

    Asks git rather than assuming, so a worktree's real `.git` directory (which lives
    under the main checkout, outside this tree) is covered too.
    """
    roots = {_real(REPO_ROOT)}
    for flag in ("--show-toplevel", "--git-dir", "--git-common-dir"):
        try:
            completed = subprocess.run(
                ["git", "rev-parse", flag],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=15,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        value = completed.stdout.strip()
        if not value:
            continue
        candidate = Path(value)
        roots.add(_real(candidate if candidate.is_absolute() else REPO_ROOT / candidate))
    return tuple(sorted(roots))


def assert_outside_repository(path: str | Path, *, what: str = "private key") -> Path:
    """Return the fully resolved ``path``, or refuse if it lands inside the repository."""
    target = _real(path)
    for root in protected_roots():
        if target == root or target.is_relative_to(root):
            raise SigningError(
                f"refusing to put the {what} at {target}\n"
                f"  that path is inside the repository ({root}).\n"
                f"  A signing key in the working tree is one `git add -A` from being published, and this "
                f"repository audits other people's supply chains.\n"
                f"  Keep it somewhere like {DEFAULT_KEY_PATH} instead."
            )
    return target


def refuse_in_ci(command: str) -> None:
    """Refuse a key-touching command when the environment says CI."""
    named = [name for name in CI_ENV_VARS if os.environ.get(name)]
    if named:
        raise SigningError(
            f"refusing to run `{command}` here: {', '.join(named)} is set, so this looks like CI.\n"
            f"  The signing key is held locally and used at release only. A key CI can reach is a key a "
            f"workflow can exfiltrate.\n"
            f"  `verify` is the half that belongs in CI -- it needs nothing secret."
        )


def _ed25519():
    """Import the ed25519 primitives with the same message validators/usf.py uses."""
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as exc:  # pragma: no cover - dependency is installed here
        raise SigningError(
            "ed25519 signing needs the `cryptography` package (`python3 -m pip install cryptography`)"
        ) from exc
    return ed25519


def raw_public_key(private_key) -> bytes:
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    return private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def public_key_field(private_key) -> str:
    """`ed25519:<64 hex>` -- the manifest's `author.signing_key` form."""
    return "ed25519:" + raw_public_key(private_key).hex()


def _passphrase(prompt: str, *, confirm: bool = False) -> bytes:
    """The key's passphrase, from ``AST10_SIGNING_PASSPHRASE`` or an interactive prompt.

    The environment variable exists for a scripted local release. It is not a way to put
    the key in CI -- there is no key in CI to unlock.
    """
    from_env = os.environ.get(PASSPHRASE_ENV_VAR)
    if from_env:
        return from_env.encode("utf-8")
    try:
        first = getpass.getpass(prompt)
        again = getpass.getpass("Repeat passphrase: ") if confirm else first
    except (EOFError, OSError) as exc:
        raise SigningError(
            f"no terminal to read a passphrase from. Set {PASSPHRASE_ENV_VAR} for a "
            f"non-interactive run, or run this from a terminal."
        ) from exc
    if first != again:
        raise SigningError("the two passphrases do not match; no key was written")
    if not first:
        raise SigningError("an empty passphrase is not encryption; re-run without --encrypt if that is the intent")
    return first.encode("utf-8")


def generate_key(out: str | Path, *, force: bool = False, encrypt: bool = False) -> tuple[Path, str]:
    """Write a new ed25519 private key outside the repository. Returns ``(path, public key)``."""
    from cryptography.hazmat.primitives.serialization import (
        BestAvailableEncryption,
        Encoding,
        NoEncryption,
        PrivateFormat,
    )

    ed25519 = _ed25519()
    target = assert_outside_repository(out, what="private key")

    parent = target.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(parent.stat().st_mode) & 0o077:
        print(f"warning: {parent} is readable beyond its owner; `chmod 700 {parent}`", file=sys.stderr)

    if encrypt:
        encryption = BestAvailableEncryption(_passphrase("Passphrase for the new key: ", confirm=True))
    else:
        encryption = NoEncryption()

    private_key = ed25519.Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, encryption)

    # O_EXCL is the no-silent-overwrite rule: replacing a signing key without meaning to
    # is how a project loses the ability to prove continuity with what it already shipped.
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if force else os.O_EXCL)
    try:
        handle = os.open(target, flags, 0o600)
    except FileExistsError as exc:
        raise SigningError(
            f"refusing to overwrite the existing key at {target}\n"
            f"  Silently replacing a signing key discards the continuity between what you already "
            f"published and what you publish next.\n"
            f"  Rotate deliberately: move the old key aside, or pass --force if you are certain."
        ) from exc
    with os.fdopen(handle, "wb") as file:
        file.write(pem)
    os.chmod(target, 0o600)
    return target, public_key_field(private_key)


def load_private_key(path: str | Path):
    """Load the ed25519 private key, refusing one that has been copied into the repository."""
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    target = assert_outside_repository(path, what="signing key")
    if not target.exists():
        raise SigningError(f"no signing key at {target}\n  Generate one first: python3 scripts/sign_usf.py keygen")
    mode = stat.S_IMODE(target.stat().st_mode)
    if mode & 0o077:
        print(
            f"warning: {target} is mode {mode:04o}; group/other can read your signing key. `chmod 600` it.",
            file=sys.stderr,
        )

    data = target.read_bytes()
    try:
        key = load_pem_private_key(data, password=None)
    except TypeError:
        key = load_pem_private_key(data, password=_passphrase(f"Passphrase for {target}: "))
    except ValueError as exc:
        raise SigningError(f"{target} is not a PEM private key this tool can read: {exc}") from exc

    ed25519 = _ed25519()
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise SigningError(f"{target} holds a {type(key).__name__}; USF signatures are ed25519 only")
    return key


# --------------------------------------------------------------------------- #
# Manifest rewriting
# --------------------------------------------------------------------------- #

_AUTHOR_HEADER_RE = re.compile(r"^author:\s*(#.*)?$")
_SIGNATURE_LINE_RE = re.compile(r"^signature:\s*\S.*$")

#: Phrases that mark the comment this repository ships EXPLAINING the unsigned state.
#: Both become false the moment a signature exists, and a manifest whose comments
#: contradict its fields is worse than one with no comments at all.
_STALE_AUTHOR_COMMENT = "deliberately absent"
_STALE_SIGNATURE_COMMENT = "unsigned placeholder"
_TOOL_MARKER = "scripts/sign_usf.py"


def _comment_runs(lines: list[str]) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, line in enumerate(lines):
        if line.strip().startswith("#"):
            start = index if start is None else start
        elif start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, len(lines)))
    return runs


def _drop_stale_comment(lines: list[str], marker: str) -> list[str]:
    for start, end in reversed(_comment_runs(lines)):
        if any(marker in line for line in lines[start:end]):
            lines = lines[:start] + lines[end:]
    return lines


def _anchor_comment(indent: str, did: DidWeb) -> list[str]:
    return [
        f"{indent}# `identity` and `signing_key` are written by scripts/sign_usf.py in the same",
        f"{indent}# operation as `signature` below, and both are INSIDE the signed payload. A",
        f"{indent}# signature whose key anchors to nothing is the false trust signal AST10 warns",
        f"{indent}# about, so the signer cannot produce one without the anchor, and neither field",
        f"{indent}# can be swapped for another publisher's without breaking the signature.",
        f"{indent}# The key is published at {did.url}; this",
        f"{indent}# anchor is worth exactly as much as control of that domain and its TLS. A",
        f'{indent}# verified signature answers "who published this", never "is this safe".',
    ]


def _signature_comment(did: DidWeb) -> list[str]:
    return [
        "# ed25519 over the RFC 8785 (JCS) canonical JSON serialization of this manifest",
        "# with `signature` removed and `content_hash` kept, so this one value covers both",
        "# the package bytes and the identity anchor above. Written and re-checked by",
        "# scripts/sign_usf.py; anyone can check it against the published key with:",
        f"#   python3 scripts/sign_usf.py verify --identity {did.did}",
    ]


def _block_indent(block: list[str], default: str = "  ") -> str:
    for line in block:
        if line.strip():
            return line[: len(line) - len(line.lstrip())]
    return default


def _set_author_anchor(lines: list[str], did: DidWeb, public_key: str) -> list[str]:
    for index, line in enumerate(lines):
        if _AUTHOR_HEADER_RE.match(line):
            start = index + 1
            break
    else:
        raise SigningError("this manifest has no top-level `author:` block to anchor the signature to")

    end = start
    while end < len(lines) and (not lines[end].strip() or lines[end][:1].isspace()):
        end += 1
    block = lines[start:end]
    trailing: list[str] = []
    while block and not block[-1].strip():
        trailing.insert(0, block.pop())

    indent = _block_indent(block)
    block = _drop_stale_comment(block, _STALE_AUTHOR_COMMENT)

    missing: dict[str, str] = {}
    for key, value in (("identity", did.did), ("signing_key", public_key)):
        pattern = re.compile(rf"^\s*{key}:\s*.*$")
        for offset, line in enumerate(block):
            if pattern.match(line):
                block[offset] = f'{indent}{key}: "{value}"'
                break
        else:
            missing[key] = value

    if missing:
        if not any(_TOOL_MARKER in line for line in block):
            block.extend(_anchor_comment(indent, did))
        block.extend(f'{indent}{key}: "{value}"' for key, value in missing.items())

    return lines[:start] + block + trailing + lines[end:]


def _set_signature(lines: list[str], signature: str, did: DidWeb) -> list[str]:
    for index, line in enumerate(lines):
        if _SIGNATURE_LINE_RE.match(line):
            break
    else:
        raise SigningError("this manifest has no top-level `signature:` line to write into")

    lines = list(lines)
    lines[index] = f'signature: "{signature}"'
    start = index
    while start > 0 and lines[start - 1].startswith("#"):
        start -= 1
    if any(_STALE_SIGNATURE_COMMENT in line for line in lines[start:index]):
        lines = lines[:start] + _signature_comment(did) + lines[index:]
    return lines


def rewrite_manifest_text(text: str, *, did: DidWeb, public_key: str, signature: str) -> str:
    """Set `author.identity`, `author.signing_key` and `signature` in one pass.

    A targeted line rewrite rather than a YAML round-trip, for the reason
    ``validators.usf.update_content_hash`` gives: PyYAML discards every comment, and the
    comments are where these manifests explain their own permission decisions. The
    caller re-reads the result and compares its canonical bytes against the bytes that
    were signed, so a rewrite that changed anything else cannot survive.
    """
    lines = text.split("\n")
    lines = _set_author_anchor(lines, did, public_key)
    lines = _set_signature(lines, signature, did)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Targets and preflight
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Target:
    path: Path

    @property
    def skill_dir(self) -> Path:
        return self.path.parent

    @property
    def label(self) -> str:
        try:
            return self.path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return str(self.path)


def resolve_targets(paths: list[str] | None) -> list[Target]:
    """Manifest paths to operate on; every shipped manifest when none are named."""
    if not paths:
        found = sorted(SKILLS_DIR.glob(f"*/{MANIFEST_NAME}"))
        if not found:
            raise SigningError(f"no manifests found under {SKILLS_DIR}")
        return [Target(path) for path in found]
    targets: list[Target] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            path = path / MANIFEST_NAME
        if not path.is_file():
            raise SigningError(f"{raw}: no such manifest")
        targets.append(Target(path))
    return targets


def preflight(targets: list[Target]) -> list[str]:
    """Everything that must hold before ANY manifest is written.

    Checked across the whole set first, so a stale hash on the eleventh skill cannot
    leave the first ten signed. The content-hash rule is the load-bearing one: each
    manifest signs its own `content_hash`, so signing a stale one attests to bytes that
    are not there.
    """
    problems: list[str] = []
    for target in targets:
        try:
            manifest = load_manifest(target.path)
        except UsfError as exc:
            problems.append(f"{target.label}: {exc}")
            continue

        declared = manifest.get("content_hash")
        actual = compute_content_hash(target.skill_dir)
        stale = declared != actual
        if stale:
            problems.append(
                f"{target.label}: content_hash is STALE -- the manifest says {declared!r} but "
                f"{target.skill_dir.name}/ hashes to {actual!r}. Signing it would attest to bytes that "
                f"are not there. Regenerate first:\n"
                f"    python3 validators/usf.py --update-content-hash {target.label}"
            )

        try:
            result = validate_manifest_file(target.path)
        except UsfError as exc:
            problems.append(f"{target.label}: {exc}")
            continue
        for error in result.errors:
            # The validator reports the same drift in its own words; saying it twice
            # buries the line that names the command to fix it.
            if stale and error.startswith("content_hash:"):
                continue
            problems.append(f"{target.label}: invalid, refusing to sign: {error}")
    return problems


# --------------------------------------------------------------------------- #
# Signing
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SignResult:
    target: Target
    previous_state: str
    signature: str
    written: bool


def sign_manifest(target: Target, *, private_key, did: DidWeb, dry_run: bool = False) -> SignResult:
    """Sign one manifest, writing identity and signature together, then verify the result.

    The post-write check is not decoration. It re-reads the file from disk and asserts
    that its canonical signing payload is byte-identical to the payload that was signed,
    which is what proves the YAML rewrite changed the three intended fields and nothing
    else. Any failure restores the original bytes.
    """
    original = target.path.read_text(encoding="utf-8")
    manifest = load_manifest(target.path)
    previous_state = signature_state(manifest)

    public_key = public_key_field(private_key)
    author = dict(manifest.get("author") or {})
    author["identity"] = did.did
    author["signing_key"] = public_key
    anchored = dict(manifest)
    anchored["author"] = author

    payload = signing_payload(anchored)
    signature = "ed25519:" + private_key.sign(payload).hex()
    updated = rewrite_manifest_text(original, did=did, public_key=public_key, signature=signature)

    if dry_run:
        return SignResult(target=target, previous_state=previous_state, signature=signature, written=False)

    target.path.write_text(updated, encoding="utf-8")
    try:
        _assert_written_manifest_is_sound(target, payload=payload, signature=signature, public_key=public_key)
    except Exception:
        target.path.write_text(original, encoding="utf-8")
        raise
    return SignResult(target=target, previous_state=previous_state, signature=signature, written=True)


def _assert_written_manifest_is_sound(target: Target, *, payload: bytes, signature: str, public_key: str) -> None:
    written = load_manifest(target.path)
    if written.get("signature") != signature:
        raise SigningError(f"{target.label}: the signature written to disk is not the one that was computed")
    if signing_payload(written) != payload:
        raise SigningError(
            f"{target.label}: the rewritten YAML does not canonicalize to the bytes that were signed, so "
            f"the rewrite changed something beyond identity/signing_key/signature. The original file has "
            f"been restored. This is a bug in scripts/sign_usf.py, not in your manifest."
        )
    author = written.get("author") or {}
    if author.get("signing_key") != public_key:
        raise SigningError(f"{target.label}: author.signing_key on disk is not the signing key")
    if verify_signature(written) is not True:
        raise SigningError(f"{target.label}: the manifest just written does not verify against its own key")
    if verify_signature(written, public_key_hex=public_key) is not True:
        raise SigningError(f"{target.label}: the manifest just written does not verify against the signing key")
    result = validate_manifest_file(target.path)
    if result.signature_state != SIGNATURE_STATE_SIGNED:
        raise SigningError(f"{target.label}: signature_state is {result.signature_state!r} after signing")
    if not result.ok:
        raise SigningError(f"{target.label}: invalid after signing: {'; '.join(result.errors)}")


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def cmd_keygen(args: argparse.Namespace) -> int:
    refuse_in_ci("keygen")
    path, public_key = generate_key(args.out, force=args.force, encrypt=args.encrypt)
    multibase = public_key_multibase(bytes.fromhex(public_key.split(":", 1)[1]))
    print("Wrote a new ed25519 signing key.\n")
    print(f"  private key   {path}   (0600, outside the repository)")
    print(f"  public key    {public_key}")
    print(f"  multibase     {multibase}   (Ed25519VerificationKey2020 publicKeyMultibase)")
    print()
    print("This is the only copy. Back it up somewhere that is neither this repository nor CI;")
    print("losing it means you cannot prove continuity with anything you have already signed.\n")
    print("Next, with YOUR.DOMAIN being a domain you control:")
    print("  1. python3 scripts/sign_usf.py did-doc --identity did:web:YOUR.DOMAIN --output did.json")
    print("  2. publish did.json at https://YOUR.DOMAIN/.well-known/did.json (HTTPS, no redirect off host)")
    print("  3. python3 scripts/sign_usf.py sign   --identity did:web:YOUR.DOMAIN")
    print("  4. python3 scripts/sign_usf.py verify --identity did:web:YOUR.DOMAIN")
    return _EXIT_OK


def _public_key_for_did_doc(args: argparse.Namespace) -> str:
    if args.public_key:
        value = args.public_key.strip()
        if not re.fullmatch(r"ed25519:[0-9a-f]{64}", value):
            raise SigningError(f"--public-key must be 'ed25519:<64 hex>', got {value!r}")
        return value
    return public_key_field(load_private_key(args.key))


def cmd_did_doc(args: argparse.Namespace) -> int:
    did = parse_did_web(args.identity)
    public_key = _public_key_for_did_doc(args)
    text = json.dumps(did_document(did, public_key.split(":", 1)[1]), indent=2) + "\n"

    guidance = sys.stderr
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        guidance = sys.stdout
        print(f"Wrote {args.output}\n")
    else:
        sys.stdout.write(text)

    print(f"Publish this document at:\n\n    {did.url}\n", file=guidance)
    if did.is_path_form:
        print(
            f"(path form: did:web:<domain>:<segments> resolves to https://{did.domain}/<segments>/did.json,\n"
            f"with no .well-known component -- that segment belongs to the bare-domain form only.)\n",
            file=guidance,
        )
    print(
        f"Serve it over HTTPS with a certificate valid for {did.domain}, as application/did+json\n"
        f"(application/json is accepted), with no authentication and no redirect to another host.\n",
        file=guidance,
    )
    print(
        f"What this anchor is worth: exactly as much as your control of {did.domain} and its TLS.\n"
        f"Anyone who can serve that path can publish a key of their own, and every signature made\n"
        f'with it will verify. A verified signature answers "who published this", never "is this safe".',
        file=guidance,
    )
    return _EXIT_OK


def cmd_sign(args: argparse.Namespace) -> int:
    refuse_in_ci("sign")
    did = parse_did_web(args.identity)
    targets = resolve_targets(args.paths)

    problems = preflight(targets)
    if problems:
        print("Refusing to sign. Nothing was written.\n", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return _EXIT_FAILED

    private_key = load_private_key(args.key)
    public_key = public_key_field(private_key)

    if args.skip_anchor_check:
        print(
            f"warning: --skip-anchor-check: not confirming that {did.url} publishes {public_key}.\n"
            f"         Publish the DID document before these manifests reach anyone, or the signature "
            f"anchors to nothing.",
            file=sys.stderr,
        )
    else:
        published = resolve_did_web(did, timeout=args.timeout)
        if public_key not in {key.public_key for key in published}:
            raise SigningError(
                f"{did.did} does not publish the key you are signing with.\n"
                f"  signing key   {public_key}\n"
                f"  published     {', '.join(key.public_key for key in published)}\n"
                f"  Publish the document from `did-doc` first, or pass --skip-anchor-check if you are "
                f"deliberately signing before publishing."
            )
        print(f"{did.url} publishes {public_key} -- anchor confirmed.\n")

    results = [sign_manifest(target, private_key=private_key, did=did, dry_run=args.dry_run) for target in targets]

    verb = "would sign" if args.dry_run else "signed"
    for result in results:
        print(f"{result.target.label}: {verb} ({result.previous_state} -> signed) {result.signature[:24]}...")
    print(f"\n{len(results)} manifest(s) {verb}, anchored to {did.did}.")
    if args.dry_run:
        print("--dry-run: nothing was written.")
    else:
        print("Each was re-read from disk and verified against the key that signed it.")
        print("Now check the whole set against the anchor:")
        print(f"    python3 scripts/sign_usf.py verify --identity {did.did}")
    return _EXIT_OK


_UNANCHORED_CAVEAT = (
    "NOTE: no --identity was given, so each signature was checked against the key the\n"
    "manifest itself carries. That proves ONLY internal consistency: the file has not\n"
    "been altered since whoever holds that key signed it. It does not say who that is --\n"
    "a rewriter can modify a manifest, re-sign it with its own key, and pass this exact\n"
    "check. Re-run with --identity did:web:<domain> to check against the key that domain\n"
    "publishes, which is the check that means something."
)


def cmd_verify(args: argparse.Namespace) -> int:
    targets = resolve_targets(args.paths)
    did = parse_did_web(args.identity) if args.identity else None

    published: list[PublishedKey] = []
    if did is not None:
        try:
            published = resolve_did_web(did, timeout=args.timeout)
        except DidResolutionError as exc:
            print(f"{exc}", file=sys.stderr)
            print(
                f"VERIFIED NOTHING. {len(targets)} manifest(s) were left unchecked because the anchor "
                f"could not be resolved. This is not a pass.",
                file=sys.stderr,
            )
            return _EXIT_UNRESOLVED
        print(f"{did.url} publishes {len(published)} assertion key(s):")
        for key in published:
            print(f"  {key.method_id}\n    {key.public_key}")
        print()

    failures = 0
    unsigned = 0
    verified = 0

    for target in targets:
        label = target.label
        try:
            manifest = load_manifest(target.path)
        except UsfError as exc:
            print(f"{label}: FAIL -- {exc}")
            failures += 1
            continue

        state = signature_state(manifest)
        if state == SIGNATURE_STATE_UNSIGNED:
            # Not a failure. An explicit "unsigned" is the honest declared state, and
            # treating it as one would push a maintainer toward an unanchored key.
            print(f"{label}: unsigned (explicit placeholder -- nothing to verify, and nothing claimed)")
            unsigned += 1
            continue
        if state == SIGNATURE_STATE_MALFORMED:
            print(
                f"{label}: FAIL -- signature is neither 'ed25519:<128 hex>' nor the explicit \"unsigned\" placeholder"
            )
            failures += 1
            continue

        author = manifest.get("author") or {}
        embedded = author.get("signing_key")
        # Which key the signature is actually checked against. Without an anchor there is
        # only the manifest's own claim; with one, it is the key the DOMAIN publishes, and
        # the manifest's claim has to match it first.
        against = embedded
        if did is not None:
            claimed = author.get("identity")
            if claimed != did.did:
                print(f"{label}: FAIL -- claims identity {claimed!r}, which is not {did.did}")
                failures += 1
                continue
            match = next((key for key in published if key.public_key == embedded), None)
            if match is None:
                print(f"{label}: FAIL -- signed with {embedded!r}, which {did.did} does not publish")
                failures += 1
                continue
            against = match.public_key

        try:
            ok = verify_signature(manifest, public_key_hex=against)
        except UsfError as exc:
            print(f"{label}: FAIL -- {exc}")
            failures += 1
            continue
        if not ok:
            print(f"{label}: FAIL -- signature does not verify over the manifest's JCS payload")
            failures += 1
            continue

        if did is not None:
            print(f"{label}: OK -- signed by {did.did}, key published at {did.url}")
        else:
            print(f"{label}: signature is internally consistent (key {embedded})")
        verified += 1

    print(f"\n{verified} verified, {unsigned} unsigned, {failures} failed, {len(targets)} manifest(s) checked.")
    if did is None and verified:
        print(f"\n{_UNANCHORED_CAVEAT}")
    if did is not None and verified:
        print(
            f"\nWhat this proves: {did.did} published the key, and the key signed these bytes. It answers\n"
            f'"who published this", never "is this safe" -- and it is worth exactly as much as that\n'
            f"domain's control of {did.url}."
        )
    return _EXIT_FAILED if failures else _EXIT_OK


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts/sign_usf.py",
        description=(
            "Sign USF manifests and anchor the signing key to a did:web identity. "
            "Signature and identity are always written together."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", metavar="{keygen,did-doc,sign,verify}")

    keygen = subparsers.add_parser("keygen", help="generate an ed25519 signing key OUTSIDE this repository")
    keygen.add_argument("--out", default=str(DEFAULT_KEY_PATH), help=f"key path (default: {DEFAULT_KEY_PATH})")
    keygen.add_argument("--force", action="store_true", help="replace an existing key (rotation; do this deliberately)")
    keygen.add_argument("--encrypt", action="store_true", help="encrypt the key with a passphrase")
    keygen.set_defaults(func=cmd_keygen)

    did_doc = subparsers.add_parser("did-doc", help="emit the DID document to publish for this key")
    did_doc.add_argument("--identity", required=True, help="did:web:<domain> you control")
    did_doc.add_argument("--key", default=str(DEFAULT_KEY_PATH), help=f"private key (default: {DEFAULT_KEY_PATH})")
    did_doc.add_argument("--public-key", help="ed25519:<64 hex> instead of reading the private key")
    did_doc.add_argument("--output", help="write the document here (default: stdout)")
    did_doc.set_defaults(func=cmd_did_doc)

    sign = subparsers.add_parser("sign", help="sign manifests and anchor them, in one write")
    sign.add_argument("--identity", required=True, help="did:web:<domain> that publishes the signing key")
    sign.add_argument("--key", default=str(DEFAULT_KEY_PATH), help=f"private key (default: {DEFAULT_KEY_PATH})")
    sign.add_argument("paths", nargs="*", help=f"manifests or skill directories (default: skills/*/{MANIFEST_NAME})")
    sign.add_argument("--dry-run", action="store_true", help="compute everything, write nothing")
    sign.add_argument(
        "--skip-anchor-check",
        action="store_true",
        help="do not confirm over HTTPS that the identity publishes this key before signing",
    )
    sign.add_argument("--timeout", type=float, default=_DEFAULT_TIMEOUT, help="HTTPS timeout in seconds")
    sign.set_defaults(func=cmd_sign)

    verify = subparsers.add_parser("verify", help="verify manifests, against the anchor when one is given")
    verify.add_argument("--identity", help="did:web:<domain> to resolve and verify against")
    verify.add_argument("paths", nargs="*", help=f"manifests or skill directories (default: skills/*/{MANIFEST_NAME})")
    verify.add_argument("--timeout", type=float, default=_DEFAULT_TIMEOUT, help="HTTPS timeout in seconds")
    verify.set_defaults(func=cmd_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help(sys.stderr)
        return 2
    try:
        return args.func(args)
    except DidResolutionError as exc:
        print(f"{exc}", file=sys.stderr)
        print("Nothing was verified and nothing was signed.", file=sys.stderr)
        return _EXIT_UNRESOLVED
    except (SigningError, UsfError) as exc:
        print(f"{exc}", file=sys.stderr)
        return _EXIT_FAILED


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
