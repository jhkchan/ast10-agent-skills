"""Tests for scripts/sign_usf.py — signing a USF manifest, and anchoring the key that signed it.

Four properties carry the weight here, and each is a test rather than a review habit:

1. **A private key cannot enter this repository.** `keygen` refuses a path that resolves
   inside the working tree -- checked after `os.path.realpath`, so `../` and a symlink
   are refused too, not just a matching string prefix, and both key-touching commands
   refuse to run in CI at all. That refusal is the control and it is pinned here;
   `.gitignore` is the backstop and `tests/test_signing_key_never_enters_the_repo.py` is
   the alarm that fires if a key arrives some other way. This repository audits other
   people's supply chains; leaking its own signing key would be the worst available
   outcome, so the refusal, the ignore rule and the scan are all pinned.

2. **A stale content_hash is not signable.** Each manifest signs its own `content_hash`,
   so signing one that no longer matches the package attests to bytes that are not
   there. The refusal is checked across the whole set BEFORE anything is written, which
   is why the "one stale skill leaves the others untouched" case has its own test.

3. **A signature and its anchor are one write.** `author.identity`,
   `author.signing_key` and `signature` are set together and all three are inside the
   signed payload. The tests pin that `sign` cannot be invoked without `--identity`, and
   that moving a signature to another identity breaks verification.

4. **The multibase encoding is right.** `publicKeyMultibase` is hand-rolled base58btc
   over the 0xed 0x01 multicodec prefix, so it is pinned to published vectors: the
   base58 vectors from the multibase test fixtures, and -- end to end -- the all-zero
   ed25519 seed, whose public key is published as
   `did:key:z6MkiTBz1ymuepAQ4HEHYSF1H8quG5GLVVQR3djdX3mDooWp`.

Nothing here touches the eleven shipped manifests. They are still explicitly unsigned
(`tests/test_usf.py::test_shipped_manifest_is_explicitly_unsigned` pins that), and every
test that signs works on a copy under `tmp_path`.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
from pathlib import Path

import pytest

from scripts.sign_usf import (
    BASE58BTC_ALPHABET,
    DEFAULT_KEY_PATH,
    MULTICODEC_ED25519_PUB,
    DidResolutionError,
    DidWeb,
    PublishedKey,
    SigningError,
    Target,
    assert_outside_repository,
    assertion_keys,
    base58btc_decode,
    base58btc_encode,
    did_document,
    generate_key,
    load_private_key,
    main,
    multibase_to_raw_public_key,
    parse_did_web,
    preflight,
    public_key_multibase,
    resolve_targets,
    sign_manifest,
)
from validators.usf import (
    SIGNATURE_STATE_SIGNED,
    SIGNATURE_STATE_UNSIGNED,
    load_manifest,
    signature_state,
    validate_manifest_file,
    verify_signature,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"

#: An ed25519 keypair anyone can re-derive: the seed is 32 zero bytes. Its public key and
#: the multibase form of that key are published in the did:key specification, which makes
#: this a vector with an origin outside this repository rather than a value produced by
#: the code under test.
ZERO_SEED = bytes(32)
ZERO_SEED_PUBLIC_HEX = "3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29"
ZERO_SEED_MULTIBASE = "z6MkiTBz1ymuepAQ4HEHYSF1H8quG5GLVVQR3djdX3mDooWp"

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _ed25519():
    return pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")


def _zero_key():
    return _ed25519().Ed25519PrivateKey.from_private_bytes(ZERO_SEED)


def _write_key(path: Path, private_key) -> Path:
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    os.chmod(path, 0o600)
    return path


def _skill_copy(tmp_path: Path, name: str = "AST01") -> Path:
    """A byte-identical copy of a shipped skill, so its content_hash still matches."""
    destination = tmp_path / "skills" / name
    shutil.copytree(SKILLS_DIR / name, destination)
    return destination


@pytest.fixture(autouse=True)
def _not_ci(monkeypatch):
    """These tests exercise the key-touching commands, which refuse to run in CI.

    The refusal itself has its own test; here it is cleared so the rest of the suite
    behaves the same on a laptop and on a runner.
    """
    for name in ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "BUILDKITE", "JENKINS_URL", "TF_BUILD"):
        monkeypatch.delenv(name, raising=False)


def _stub_resolution(monkeypatch, document: object, *, url_check: bool = True) -> None:
    """Serve ``document`` in place of the network, as the bytes a real fetch would return."""
    body = json.dumps(document).encode("utf-8")

    def fake_get(url: str, *, timeout: float):
        assert not url_check or url.startswith("https://")
        return url, body

    monkeypatch.setattr("scripts.sign_usf._http_get", fake_get)


def _stub_offline(monkeypatch, exc: Exception | None = None) -> None:
    def fake_get(url: str, *, timeout: float):
        raise exc or OSError("Name or service not known")

    monkeypatch.setattr("scripts.sign_usf._http_get", fake_get)


# --------------------------------------------------------------------------- #
# base58btc and multibase, against published vectors
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "encoded"),
    [
        (b"", ""),
        (b"\x00", "1"),
        # The multibase specification's own test fixtures, minus their 'z' prefix.
        (b"yes mani !", "7paNL19xttacUY"),
        (b"\x00yes mani !", "17paNL19xttacUY"),
        (b"\x00\x00yes mani !", "117paNL19xttacUY"),
        # The vector every base58 implementation is introduced with.
        (b"hello world", "StV1DL6CwTryKyV"),
    ],
)
def test_base58btc_matches_published_vectors(raw, encoded):
    assert base58btc_encode(raw) == encoded
    assert base58btc_decode(encoded) == raw


def test_base58btc_alphabet_omits_the_ambiguous_characters():
    assert len(BASE58BTC_ALPHABET) == 58
    assert len(set(BASE58BTC_ALPHABET)) == 58
    for character in "0OIl":
        assert character not in BASE58BTC_ALPHABET


def test_base58btc_round_trips_arbitrary_bytes():
    for length in range(0, 40):
        for _ in range(4):
            raw = os.urandom(length)
            assert base58btc_decode(base58btc_encode(raw)) == raw


def test_base58btc_decode_rejects_a_foreign_character():
    with pytest.raises(ValueError, match="base58btc"):
        base58btc_decode("StV1DL6CwTryKyV0")


def test_public_key_multibase_matches_the_published_did_key_vector():
    """End to end: zero seed -> ed25519 public key -> multicodec -> base58btc -> 'z'.

    The expected value is the identifier the did:key specification publishes for this
    key, so a wrong multicodec prefix, a wrong alphabet or a dropped 'z' all fail here.
    """
    private_key = _zero_key()
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    assert raw.hex() == ZERO_SEED_PUBLIC_HEX
    assert public_key_multibase(raw) == ZERO_SEED_MULTIBASE


def test_public_key_multibase_carries_the_ed25519_multicodec_prefix():
    encoded = public_key_multibase(bytes.fromhex(ZERO_SEED_PUBLIC_HEX))
    decoded = base58btc_decode(encoded[1:])
    assert encoded.startswith("z")
    assert decoded[:2] == MULTICODEC_ED25519_PUB == b"\xed\x01"
    assert decoded[2:].hex() == ZERO_SEED_PUBLIC_HEX
    assert len(encoded) == 48


def test_multibase_round_trips_random_keys():
    for _ in range(20):
        raw = os.urandom(32)
        encoded = public_key_multibase(raw)
        assert encoded.startswith("z6Mk"), encoded
        assert multibase_to_raw_public_key(encoded) == raw


def test_public_key_multibase_rejects_a_key_that_is_not_32_bytes():
    with pytest.raises(SigningError, match="32 bytes"):
        public_key_multibase(bytes(31))


@pytest.mark.parametrize(
    ("value", "match"),
    [
        ("6MkiTBz1ymuepAQ4HEHYSF1H8quG5GLVVQR3djdX3mDooWp", "base58btc"),
        ("f" + ZERO_SEED_PUBLIC_HEX, "base58btc"),
        # base58btc of a 32-byte key with no multicodec prefix at all.
        ("z" + base58btc_encode(bytes.fromhex(ZERO_SEED_PUBLIC_HEX)), "multicodec"),
        # The right prefix over the wrong number of key bytes.
        ("z" + base58btc_encode(MULTICODEC_ED25519_PUB + bytes(16)), "expected 32"),
    ],
)
def test_multibase_decode_refuses_anything_that_is_not_an_ed25519_key(value, match):
    with pytest.raises(ValueError, match=match):
        multibase_to_raw_public_key(value)


# --------------------------------------------------------------------------- #
# did:web parsing
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("identity", "url"),
    [
        ("did:web:example.com", "https://example.com/.well-known/did.json"),
        ("did:web:skills.example.com", "https://skills.example.com/.well-known/did.json"),
        # Path form: no .well-known component, per the did:web method specification.
        ("did:web:example.com:skills:ast10", "https://example.com/skills/ast10/did.json"),
        ("did:web:example.com%3A3000", "https://example.com:3000/.well-known/did.json"),
    ],
)
def test_did_web_resolves_to_the_right_https_url(identity, url):
    did = parse_did_web(identity)
    assert did.did == identity
    assert did.url == url


def test_did_web_path_form_is_flagged_as_such():
    assert parse_did_web("did:web:example.com:a:b").is_path_form is True
    assert parse_did_web("did:web:example.com").is_path_form is False


@pytest.mark.parametrize(
    "identity",
    [
        "",
        "   ",
        "example.com",
        "https://example.com",
        "did:key:z6MkiTBz1ymuepAQ4HEHYSF1H8quG5GLVVQR3djdX3mDooWp",
        "did:web:EXAMPLE.com",
        "did:web:",
        "did:web:example.com:",
        "did:web:example.com/path",
    ],
)
def test_did_web_refuses_anything_that_is_not_a_did_web_identifier(identity):
    with pytest.raises(SigningError):
        parse_did_web(identity)


# --------------------------------------------------------------------------- #
# DID document
# --------------------------------------------------------------------------- #


def test_did_document_publishes_the_key_under_assertion_method():
    did = parse_did_web("did:web:example.com")
    document = did_document(did, ZERO_SEED_PUBLIC_HEX)

    assert document["id"] == "did:web:example.com"
    assert "https://www.w3.org/ns/did/v1" in document["@context"]
    method = document["verificationMethod"][0]
    assert method["type"] == "Ed25519VerificationKey2020"
    assert method["controller"] == "did:web:example.com"
    assert method["publicKeyMultibase"] == ZERO_SEED_MULTIBASE
    assert method["id"] == f"did:web:example.com#{ZERO_SEED_MULTIBASE}"
    # A manifest signature is an assertion; `verify` accepts no other relationship.
    assert document["assertionMethod"] == [method["id"]]
    assert document["authentication"] == [method["id"]]


def test_did_document_round_trips_through_the_resolver():
    did = parse_did_web("did:web:example.com")
    keys = assertion_keys(did_document(did, ZERO_SEED_PUBLIC_HEX), did)
    assert [key.public_key for key in keys] == [f"ed25519:{ZERO_SEED_PUBLIC_HEX}"]
    assert keys[0].multibase == ZERO_SEED_MULTIBASE


def test_did_document_for_a_wrong_identifier_anchors_nothing():
    did = parse_did_web("did:web:example.com")
    document = did_document(parse_did_web("did:web:evil.example"), ZERO_SEED_PUBLIC_HEX)
    with pytest.raises(DidResolutionError, match="does not claim the identifier"):
        assertion_keys(document, did)


def test_a_key_published_only_for_authentication_is_not_accepted():
    did = parse_did_web("did:web:example.com")
    document = did_document(did, ZERO_SEED_PUBLIC_HEX)
    document.pop("assertionMethod")
    with pytest.raises(DidResolutionError, match="assertionMethod"):
        assertion_keys(document, did)


def test_a_verification_method_of_an_unsupported_type_is_not_accepted():
    did = parse_did_web("did:web:example.com")
    document = did_document(did, ZERO_SEED_PUBLIC_HEX)
    document["verificationMethod"][0]["type"] = "Ed25519VerificationKey2018"
    with pytest.raises(DidResolutionError, match="Ed25519VerificationKey2020"):
        assertion_keys(document, did)


def test_an_embedded_assertion_method_is_accepted():
    did = parse_did_web("did:web:example.com")
    document = did_document(did, ZERO_SEED_PUBLIC_HEX)
    document["assertionMethod"] = document.pop("verificationMethod")
    keys = assertion_keys(document, did)
    assert keys[0].public_key == f"ed25519:{ZERO_SEED_PUBLIC_HEX}"


def test_resolution_refuses_a_document_that_is_not_an_object():
    with pytest.raises(DidResolutionError):
        assertion_keys(["did:web:example.com"], parse_did_web("did:web:example.com"))


# --------------------------------------------------------------------------- #
# Key custody
# --------------------------------------------------------------------------- #


def test_the_default_key_path_is_outside_the_repository():
    assert assert_outside_repository(DEFAULT_KEY_PATH) == Path(os.path.expanduser(str(DEFAULT_KEY_PATH)))


@pytest.mark.parametrize(
    "relative",
    ["signing.pem", "skills/AST01/key.pem", "scripts/../ed25519.key", ".git/ast10.key"],
)
def test_a_key_path_inside_the_repository_is_refused(relative):
    with pytest.raises(SigningError, match="inside the repository"):
        assert_outside_repository(REPO_ROOT / relative)


def test_a_symlink_pointing_back_into_the_repository_is_refused(tmp_path):
    """The check resolves symlinks rather than comparing strings, which is the difference
    between a control and a speed bump."""
    link = tmp_path / "elsewhere"
    link.symlink_to(REPO_ROOT)
    with pytest.raises(SigningError, match="inside the repository"):
        assert_outside_repository(link / "signing.pem")


def test_dot_dot_cannot_smuggle_a_key_into_the_repository(tmp_path):
    escape = tmp_path / "keys" / ".." / ".." / ".." / "x.pem"
    # Not inside the repo, so this one is allowed -- the point is that the resolution
    # happens at all, which the repo-relative case above proves is enforced.
    assert assert_outside_repository(escape).name == "x.pem"


def test_keygen_writes_a_locked_down_key_outside_the_repository(tmp_path, capsys):
    target = tmp_path / "custody" / "ed25519.pem"
    assert main(["keygen", "--out", str(target)]) == 0

    assert target.is_file()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700
    assert b"PRIVATE KEY" in target.read_bytes()

    out = capsys.readouterr().out
    assert "ed25519:" in out
    # The next step is named, not left to be guessed.
    assert "did-doc" in out and "sign" in out and "verify" in out


def test_keygen_refuses_a_path_inside_the_repository(capsys):
    assert main(["keygen", "--out", str(REPO_ROOT / "signing.pem")]) == 1
    assert not (REPO_ROOT / "signing.pem").exists()
    assert "inside the repository" in capsys.readouterr().err


def test_keygen_refuses_to_silently_replace_an_existing_key(tmp_path, capsys):
    target = tmp_path / "ed25519.pem"
    assert main(["keygen", "--out", str(target)]) == 0
    original = target.read_bytes()

    assert main(["keygen", "--out", str(target)]) == 1
    assert target.read_bytes() == original
    assert "refusing to overwrite" in capsys.readouterr().err

    assert main(["keygen", "--out", str(target), "--force"]) == 0
    assert target.read_bytes() != original
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_keygen_can_encrypt_the_key_at_rest(tmp_path, monkeypatch):
    monkeypatch.setenv("AST10_SIGNING_PASSPHRASE", "correct horse battery staple")
    target = tmp_path / "ed25519.pem"
    assert main(["keygen", "--out", str(target), "--encrypt"]) == 0
    assert b"ENCRYPTED" in target.read_bytes()
    # And it loads again with the same passphrase, so an encrypted key is still usable.
    assert load_private_key(target) is not None


def test_an_encrypted_key_without_the_passphrase_is_not_silently_usable(tmp_path, monkeypatch):
    monkeypatch.setenv("AST10_SIGNING_PASSPHRASE", "correct horse battery staple")
    target = tmp_path / "ed25519.pem"
    assert main(["keygen", "--out", str(target), "--encrypt"]) == 0
    monkeypatch.delenv("AST10_SIGNING_PASSPHRASE")
    monkeypatch.setattr("getpass.getpass", lambda *a, **k: (_ for _ in ()).throw(EOFError()))
    with pytest.raises(SigningError, match="passphrase"):
        load_private_key(target)


def test_keygen_and_sign_refuse_to_run_in_ci(tmp_path, monkeypatch, capsys):
    """The key is local and used at release only. A key CI can reach is a key a workflow
    can exfiltrate."""
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    target = tmp_path / "ed25519.pem"
    assert main(["keygen", "--out", str(target)]) == 1
    assert not target.exists()
    error = capsys.readouterr().err
    assert "CI" in error and "GITHUB_ACTIONS" in error

    assert main(["sign", "--identity", "did:web:example.com", "--key", str(target)]) == 1
    assert "GITHUB_ACTIONS" in capsys.readouterr().err


def test_loading_a_key_from_inside_the_repository_is_refused():
    with pytest.raises(SigningError, match="inside the repository"):
        load_private_key(REPO_ROOT / "scripts" / "ed25519.pem")


def test_loading_a_missing_key_names_the_command_that_makes_one(tmp_path):
    with pytest.raises(SigningError, match="keygen"):
        load_private_key(tmp_path / "nope.pem")


def test_loading_a_key_of_the_wrong_algorithm_is_refused(tmp_path):
    rsa = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.rsa")
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

    target = tmp_path / "rsa.pem"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    target.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    with pytest.raises(SigningError, match="ed25519 only"):
        load_private_key(target)


def test_generate_key_returns_the_public_half_in_manifest_form(tmp_path):
    path, public_key = generate_key(tmp_path / "k.pem")
    assert path.is_file()
    assert public_key.startswith("ed25519:")
    assert len(public_key.split(":", 1)[1]) == 64


# --------------------------------------------------------------------------- #
# Targets and preflight
# --------------------------------------------------------------------------- #


def test_the_default_target_set_is_every_shipped_manifest():
    targets = resolve_targets([])
    assert len(targets) == len(list(SKILLS_DIR.glob("*/skill.usf.yaml")))
    assert all(target.path.name == "skill.usf.yaml" for target in targets)


def test_a_skill_directory_resolves_to_its_manifest(tmp_path):
    skill = _skill_copy(tmp_path)
    assert resolve_targets([str(skill)])[0].path == skill / "skill.usf.yaml"


def test_preflight_passes_on_an_untouched_copy_of_a_shipped_skill(tmp_path):
    assert preflight([Target(_skill_copy(tmp_path) / "skill.usf.yaml")]) == []


def test_preflight_refuses_a_stale_content_hash_and_names_the_fix(tmp_path):
    skill = _skill_copy(tmp_path)
    (skill / "SKILL.md").write_text((skill / "SKILL.md").read_text() + "\ndrift\n", encoding="utf-8")

    problems = preflight([Target(skill / "skill.usf.yaml")])
    assert len(problems) == 1, problems
    assert "content_hash is STALE" in problems[0]
    assert "AST01" in problems[0]
    assert "python3 validators/usf.py --update-content-hash" in problems[0]


def test_preflight_refuses_a_manifest_the_validator_rejects(tmp_path):
    skill = _skill_copy(tmp_path)
    manifest = skill / "skill.usf.yaml"
    manifest.write_text(manifest.read_text().replace("risk_tier: L0", "risk_tier: nonsense"), encoding="utf-8")
    problems = preflight([Target(manifest)])
    assert any("refusing to sign" in problem for problem in problems)


# --------------------------------------------------------------------------- #
# Signing
# --------------------------------------------------------------------------- #


def test_sign_writes_signature_and_anchor_in_one_operation(tmp_path):
    skill = _skill_copy(tmp_path)
    target = Target(skill / "skill.usf.yaml")
    did = parse_did_web("did:web:example.com")

    result = sign_manifest(target, private_key=_zero_key(), did=did)
    assert result.previous_state == SIGNATURE_STATE_UNSIGNED

    manifest = load_manifest(target.path)
    assert signature_state(manifest) == SIGNATURE_STATE_SIGNED
    assert manifest["author"]["identity"] == "did:web:example.com"
    assert manifest["author"]["signing_key"] == f"ed25519:{ZERO_SEED_PUBLIC_HEX}"
    assert verify_signature(manifest) is True
    assert validate_manifest_file(target.path).ok


def test_the_anchor_is_inside_the_signed_payload(tmp_path):
    """Swapping the identity under an existing signature must break verification.

    This is the property that makes "signature and anchor are one operation" true of the
    FILE and not only of the tool: there is no way to keep a valid signature while
    pointing it at a different publisher.
    """
    skill = _skill_copy(tmp_path)
    target = Target(skill / "skill.usf.yaml")
    sign_manifest(target, private_key=_zero_key(), did=parse_did_web("did:web:example.com"))

    text = target.path.read_text(encoding="utf-8")
    target.path.write_text(text.replace('identity: "did:web:example.com"', 'identity: "did:web:evil.example"'))
    assert verify_signature(load_manifest(target.path)) is False


def test_tampering_with_any_signed_field_breaks_the_signature(tmp_path):
    skill = _skill_copy(tmp_path)
    target = Target(skill / "skill.usf.yaml")
    sign_manifest(target, private_key=_zero_key(), did=parse_did_web("did:web:example.com"))

    text = target.path.read_text(encoding="utf-8")
    target.path.write_text(text.replace("risk_tier: L0", "risk_tier: L3"), encoding="utf-8")
    assert verify_signature(load_manifest(target.path)) is False


def test_signing_preserves_the_manifest_comments_that_are_still_true(tmp_path):
    skill = _skill_copy(tmp_path)
    target = Target(skill / "skill.usf.yaml")
    before = target.path.read_text(encoding="utf-8")
    sign_manifest(target, private_key=_zero_key(), did=parse_did_web("did:web:example.com"))
    after = target.path.read_text(encoding="utf-8")

    for comment in (
        "# Paths are relative to the skill package under review",
        "# No egress. Default-deny with an empty allowlist means no host is reachable.",
        "# sha256 over this skill's shipped surface as defined by scripts/content_hash.py",
    ):
        assert comment in before and comment in after

    # The two comments that would become FALSE are the two that are replaced.
    assert "deliberately absent" in before and "deliberately absent" not in after
    assert "unsigned placeholder" in before and "unsigned placeholder" not in after
    assert "https://example.com/.well-known/did.json" in after


def test_signing_is_idempotent(tmp_path):
    skill = _skill_copy(tmp_path)
    target = Target(skill / "skill.usf.yaml")
    did = parse_did_web("did:web:example.com")

    sign_manifest(target, private_key=_zero_key(), did=did)
    once = target.path.read_text(encoding="utf-8")
    sign_manifest(target, private_key=_zero_key(), did=did)
    twice = target.path.read_text(encoding="utf-8")

    assert once == twice
    assert once.count("identity:") == 1
    assert once.count("signing_key:") == 1


def test_resigning_with_a_new_key_replaces_the_anchor_rather_than_adding_one(tmp_path):
    skill = _skill_copy(tmp_path)
    target = Target(skill / "skill.usf.yaml")
    sign_manifest(target, private_key=_zero_key(), did=parse_did_web("did:web:example.com"))

    rotated = _ed25519().Ed25519PrivateKey.generate()
    result = sign_manifest(target, private_key=rotated, did=parse_did_web("did:web:other.example"))
    assert result.previous_state == SIGNATURE_STATE_SIGNED

    manifest = load_manifest(target.path)
    assert manifest["author"]["identity"] == "did:web:other.example"
    assert manifest["author"]["signing_key"] != f"ed25519:{ZERO_SEED_PUBLIC_HEX}"
    assert verify_signature(manifest) is True


def test_signing_does_not_change_the_content_hash(tmp_path):
    """skill.usf.yaml is outside the hashed surface, which is what stops the hash from
    depending on the field that carries it -- so signing cannot invalidate it."""
    skill = _skill_copy(tmp_path)
    target = Target(skill / "skill.usf.yaml")
    before = load_manifest(target.path)["content_hash"]
    sign_manifest(target, private_key=_zero_key(), did=parse_did_web("did:web:example.com"))
    assert load_manifest(target.path)["content_hash"] == before
    assert preflight([target]) == []


def test_dry_run_computes_a_signature_and_writes_nothing(tmp_path):
    skill = _skill_copy(tmp_path)
    target = Target(skill / "skill.usf.yaml")
    before = target.path.read_text(encoding="utf-8")

    result = sign_manifest(target, private_key=_zero_key(), did=parse_did_web("did:web:example.com"), dry_run=True)
    assert result.written is False
    assert result.signature.startswith("ed25519:")
    assert target.path.read_text(encoding="utf-8") == before


def test_sign_requires_an_identity():
    """There is no code path to a signature without an anchor, and argparse is where that
    starts: `sign` has no default identity to fall back to."""
    with pytest.raises(SystemExit) as excinfo:
        main(["sign"])
    assert excinfo.value.code == 2


def test_sign_refuses_the_whole_set_when_one_manifest_is_stale(tmp_path, capsys):
    first = _skill_copy(tmp_path, "AST01")
    second = _skill_copy(tmp_path, "AST02")
    (second / "SKILL.md").write_text((second / "SKILL.md").read_text() + "\ndrift\n", encoding="utf-8")
    key = _write_key(tmp_path / "keys" / "ed25519.pem", _zero_key())

    exit_code = main(
        [
            "sign",
            "--identity",
            "did:web:example.com",
            "--key",
            str(key),
            "--skip-anchor-check",
            str(first),
            str(second),
        ]
    )
    assert exit_code == 1

    error = capsys.readouterr().err
    assert "Nothing was written" in error
    assert "content_hash is STALE" in error
    assert "AST02" in error
    # The clean manifest is untouched: no half-signed set.
    assert signature_state(load_manifest(first / "skill.usf.yaml")) == SIGNATURE_STATE_UNSIGNED


def test_sign_confirms_the_anchor_publishes_the_key_before_writing(tmp_path, monkeypatch, capsys):
    skill = _skill_copy(tmp_path)
    key = _write_key(tmp_path / "keys" / "ed25519.pem", _zero_key())
    did = parse_did_web("did:web:example.com")
    _stub_resolution(monkeypatch, did_document(did, ZERO_SEED_PUBLIC_HEX))

    assert main(["sign", "--identity", did.did, "--key", str(key), str(skill)]) == 0
    assert "anchor confirmed" in capsys.readouterr().out
    assert verify_signature(load_manifest(skill / "skill.usf.yaml")) is True


def test_sign_refuses_when_the_anchor_publishes_a_different_key(tmp_path, monkeypatch, capsys):
    skill = _skill_copy(tmp_path)
    key = _write_key(tmp_path / "keys" / "ed25519.pem", _zero_key())
    did = parse_did_web("did:web:example.com")
    other = os.urandom(32).hex()
    _stub_resolution(monkeypatch, did_document(did, other))

    assert main(["sign", "--identity", did.did, "--key", str(key), str(skill)]) == 1
    assert "does not publish the key" in capsys.readouterr().err
    assert signature_state(load_manifest(skill / "skill.usf.yaml")) == SIGNATURE_STATE_UNSIGNED


def test_sign_reports_an_unreachable_anchor_as_unresolved_not_as_a_failure(tmp_path, monkeypatch, capsys):
    skill = _skill_copy(tmp_path)
    key = _write_key(tmp_path / "keys" / "ed25519.pem", _zero_key())
    _stub_offline(monkeypatch)

    assert main(["sign", "--identity", "did:web:example.com", "--key", str(key), str(skill)]) == 3
    assert "could not resolve" in capsys.readouterr().err
    assert signature_state(load_manifest(skill / "skill.usf.yaml")) == SIGNATURE_STATE_UNSIGNED


def test_skip_anchor_check_says_out_loud_what_it_is_skipping(tmp_path, capsys):
    skill = _skill_copy(tmp_path)
    key = _write_key(tmp_path / "keys" / "ed25519.pem", _zero_key())
    argv = ["sign", "--identity", "did:web:example.com", "--key", str(key), "--skip-anchor-check", str(skill)]
    assert main(argv) == 0
    assert "anchors to nothing" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Verifying
# --------------------------------------------------------------------------- #


def test_verify_says_an_unanchored_check_proves_only_internal_consistency(tmp_path, capsys):
    skill = _skill_copy(tmp_path)
    sign_manifest(Target(skill / "skill.usf.yaml"), private_key=_zero_key(), did=parse_did_web("did:web:example.com"))

    assert main(["verify", str(skill)]) == 0
    out = capsys.readouterr().out
    assert "internally consistent" in out
    assert "ONLY internal consistency" in out
    assert "re-sign it with its own key" in out


def test_verify_against_the_anchor_uses_the_published_key(tmp_path, monkeypatch, capsys):
    skill = _skill_copy(tmp_path)
    did = parse_did_web("did:web:example.com")
    sign_manifest(Target(skill / "skill.usf.yaml"), private_key=_zero_key(), did=did)
    _stub_resolution(monkeypatch, did_document(did, ZERO_SEED_PUBLIC_HEX))

    assert main(["verify", "--identity", did.did, str(skill)]) == 0
    out = capsys.readouterr().out
    assert "OK -- signed by did:web:example.com" in out
    assert '"who published this", never "is this safe"' in out
    assert "ONLY internal consistency" not in out


def test_verify_fails_when_the_anchor_does_not_publish_the_signing_key(tmp_path, monkeypatch, capsys):
    skill = _skill_copy(tmp_path)
    did = parse_did_web("did:web:example.com")
    sign_manifest(Target(skill / "skill.usf.yaml"), private_key=_zero_key(), did=did)
    _stub_resolution(monkeypatch, did_document(did, os.urandom(32).hex()))

    assert main(["verify", "--identity", did.did, str(skill)]) == 1
    assert "does not publish" in capsys.readouterr().out


def test_verify_fails_when_the_manifest_claims_a_different_identity(tmp_path, monkeypatch, capsys):
    skill = _skill_copy(tmp_path)
    sign_manifest(Target(skill / "skill.usf.yaml"), private_key=_zero_key(), did=parse_did_web("did:web:other.example"))
    did = parse_did_web("did:web:example.com")
    _stub_resolution(monkeypatch, did_document(did, ZERO_SEED_PUBLIC_HEX))

    assert main(["verify", "--identity", did.did, str(skill)]) == 1
    assert "claims identity" in capsys.readouterr().out


def test_verify_treats_an_unreachable_anchor_as_verified_nothing(tmp_path, monkeypatch, capsys):
    """The failure mode this exists to prevent: an offline verifier that prints OK."""
    skill = _skill_copy(tmp_path)
    sign_manifest(Target(skill / "skill.usf.yaml"), private_key=_zero_key(), did=parse_did_web("did:web:example.com"))
    _stub_offline(monkeypatch)

    assert main(["verify", "--identity", "did:web:example.com", str(skill)]) == 3
    captured = capsys.readouterr()
    assert "VERIFIED NOTHING" in captured.err
    assert "could not resolve" in captured.err
    assert "OK" not in captured.out


def test_verify_treats_a_plaintext_redirect_as_unresolved(tmp_path, monkeypatch, capsys):
    skill = _skill_copy(tmp_path)
    sign_manifest(Target(skill / "skill.usf.yaml"), private_key=_zero_key(), did=parse_did_web("did:web:example.com"))
    document = json.dumps(did_document(parse_did_web("did:web:example.com"), ZERO_SEED_PUBLIC_HEX)).encode()
    monkeypatch.setattr(
        "scripts.sign_usf._http_get",
        lambda url, *, timeout: ("http://example.com/.well-known/did.json", document),
    )

    assert main(["verify", "--identity", "did:web:example.com", str(skill)]) == 3
    assert "not HTTPS" in capsys.readouterr().err


def test_verify_treats_a_tampered_manifest_as_a_failure(tmp_path, capsys):
    skill = _skill_copy(tmp_path)
    manifest_path = skill / "skill.usf.yaml"
    sign_manifest(Target(manifest_path), private_key=_zero_key(), did=parse_did_web("did:web:example.com"))
    manifest_path.write_text(manifest_path.read_text().replace("risk_tier: L0", "risk_tier: L3"), encoding="utf-8")

    assert main(["verify", str(skill)]) == 1
    assert "does not verify" in capsys.readouterr().out


def test_verify_treats_a_malformed_signature_as_a_failure(tmp_path, capsys):
    skill = _skill_copy(tmp_path)
    manifest_path = skill / "skill.usf.yaml"
    manifest_path.write_text(
        manifest_path.read_text().replace('signature: "unsigned"', 'signature: "ed25519:not-hex"'), encoding="utf-8"
    )
    assert main(["verify", str(skill)]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_verify_treats_an_explicitly_unsigned_manifest_as_the_honest_current_state(capsys):
    """The eleven shipped manifests are unsigned. That must not read as a failure, or the
    tool pushes a maintainer toward exactly the unanchored key this repo refuses to ship."""
    assert main(["verify"]) == 0
    out = capsys.readouterr().out
    assert out.count("unsigned (explicit placeholder") == len(list(SKILLS_DIR.glob("*/skill.usf.yaml")))
    assert "FAIL" not in out


def test_verify_needs_no_key_material(monkeypatch, tmp_path):
    """`verify` is the half that can run in CI: it reads nothing secret. Pointing HOME at
    an empty directory proves it never reaches for the default key path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    assert main(["verify"]) == 0


# --------------------------------------------------------------------------- #
# The key must never enter this repository
# --------------------------------------------------------------------------- #
#
# The refusals are here -- keygen and sign declining a path inside the working tree, and
# both declining to run in CI at all. The SCAN that catches a key which arrived some other
# way lives in tests/test_signing_key_never_enters_the_repo.py, one implementation rather
# than a copy here that could drift from it, and it is the more thorough of the two: it
# looks at the working tree as well as at what git would commit, because an ignored key is
# not an absent one.


# --------------------------------------------------------------------------- #
# CLI shape
# --------------------------------------------------------------------------- #


def test_bare_invocation_prints_help_and_fails(capsys):
    assert main([]) == 2
    assert "keygen" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["keygen", "did-doc", "sign", "verify"])
def test_every_subcommand_has_help(command, capsys):
    with pytest.raises(SystemExit) as excinfo:
        main([command, "--help"])
    assert excinfo.value.code == 0
    assert command.split("-")[0] in capsys.readouterr().out


def test_did_doc_writes_a_publishable_document(tmp_path, capsys):
    out = tmp_path / "did.json"
    exit_code = main(
        [
            "did-doc",
            "--identity",
            "did:web:example.com",
            "--public-key",
            f"ed25519:{ZERO_SEED_PUBLIC_HEX}",
            "--output",
            str(out),
        ]
    )
    assert exit_code == 0

    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["verificationMethod"][0]["publicKeyMultibase"] == ZERO_SEED_MULTIBASE

    printed = capsys.readouterr().out
    assert "https://example.com/.well-known/did.json" in printed
    assert "control of example.com and its TLS" in printed


def test_did_doc_refuses_a_public_key_that_is_not_ed25519_hex(capsys):
    assert main(["did-doc", "--identity", "did:web:example.com", "--public-key", "ed25519:nope"]) == 1
    assert "ed25519:<64 hex>" in capsys.readouterr().err


def test_did_doc_emits_json_on_stdout_and_guidance_on_stderr(capsys):
    argv = ["did-doc", "--identity", "did:web:example.com", "--public-key", f"ed25519:{ZERO_SEED_PUBLIC_HEX}"]
    assert main(argv) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["id"] == "did:web:example.com"
    assert "Publish this document at" in captured.err


def test_published_key_reports_its_multibase_form():
    key = PublishedKey(method_id="did:web:example.com#x", public_key=f"ed25519:{ZERO_SEED_PUBLIC_HEX}")
    assert key.multibase == ZERO_SEED_MULTIBASE


def test_did_web_dataclass_is_frozen():
    did = parse_did_web("did:web:example.com")
    assert isinstance(did, DidWeb)
    with pytest.raises(Exception):
        did.did = "did:web:evil.example"
