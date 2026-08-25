"""No private key may exist in this checkout — as a test, not as a habit.

This repository audits other people's supply chains. Leaking its own signing key would
be the most embarrassing possible outcome, so the rule is pinned here rather than left to
review. `scripts/sign_usf.py` keygen REFUSING to write a key inside the working tree is
the *control*; `.gitignore` is the *backstop*; this file is the *alarm* that fires when
both have been bypassed — a key copied in by hand, restored from a backup, dropped by
another tool, or force-added past the ignore rules.

TWO LENSES, AND WHY BOTH
------------------------
`test_no_private_key_material_can_be_committed` scans what git would put in a commit:
tracked files plus untracked-and-not-ignored ones. That is the leak in its published
form, and it is the worse failure of the two.

`test_no_private_key_is_sitting_in_the_working_tree` scans the tree itself, ignored files
included — because `.gitignore` keeps a key out of `git add -A`, not out of `git add -f`,
not out of a release tarball, not out of `zip -r`, and not out of whatever backs this
directory up. A key that git cannot see is still a key on the disk, and
`test_a_planted_key_is_invisible_to_git_and_still_caught` demonstrates exactly that gap
by planting one and watching the first lens miss it.

THE ONE SHAPE THAT CANNOT BE DECIDED FROM TEXT ALONE
----------------------------------------------------
An ed25519 private seed and an ed25519 public key are both 32 bytes, so `ed25519:<64 hex>`
is the *same string shape* for the secret and for the thing you publish. Nothing can tell
them apart by inspection. The rule here is therefore contextual: a 64-hex value is allowed
only on a line that names the field as public (`signing_key:`, `publicKey`, `--public-key`),
which is where `sign_usf.py` writes the public half, and is flagged anywhere else. That is
a real limit and it is named rather than papered over. The 128-hex `signature:` value is
not a key at all and is deliberately not matched.

`test_a_signed_manifest_does_not_trip_the_scan` is the other half of that rule: if signing
the roster made this file fail, the tool would be unusable and the maintainer's first move
would be to weaken the scan.
"""

from __future__ import annotations

import base64
import os
import re
import subprocess
from pathlib import Path

import pytest

from scripts.sign_usf import DEFAULT_KEY_PATH

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Directories a walk must not descend into: caches, virtualenvs and vendored installs.
#: A `.venv` full of `cacert.pem` files would otherwise fail this file on every laptop
#: that has one, which is how a real alarm gets muted.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".tox",
        ".eggs",
        ".omc",
        ".idea",
        "htmlcov",
        "dist",
        "build",
    }
)

#: Filename shapes that mean "this is probably a private key".
KEY_SUFFIXES = (".pem", ".key", ".p8", ".pkcs8", ".pkcs12", ".ppk", ".pfx", ".p12", ".jks", ".keystore", ".der")

#: OpenSSH's default private-key names. Matched on the stem so `id_ed25519.bak` is caught.
KEY_STEMS = ("id_rsa", "id_ed25519", "id_ecdsa", "id_dsa")

#: Assembled from fragments on purpose: written out as literals, THIS file would become
#: the first thing its own scan reports.
_PEM_KINDS = ("", "RSA ", "DSA ", "EC ", "OPENSSH ", "ENCRYPTED ", "PGP ")
PEM_MARKERS = tuple(f"-----BEGIN {kind}PRIVATE KEY" for kind in _PEM_KINDS)

#: The magic that opens the body of every OpenSSH v1 private key, base64-encoded exactly
#: as the armor carries it. Derived rather than typed, and it catches a key whose header
#: line was stripped or renamed.
OPENSSH_BODY_MAGIC = base64.b64encode(b"openssh-key-v1\x00").decode("ascii").rstrip("=")

#: PuTTY's format keeps its secret under a `Private-Lines:` header inside this file type.
#: Split for the same reason as the PEM markers above.
PUTTY_MARKER = "PuTTY-" + "User-Key-File"

CONTENT_MARKERS = (*PEM_MARKERS, OPENSSH_BODY_MAGIC, PUTTY_MARKER)

#: Exactly 64 hex, and not one more: the 128-hex form is a `signature:`, not a key.
ED25519_HEX_RE = re.compile(r"ed25519:([0-9a-fA-F]{64})(?![0-9a-fA-F])")

#: Field names that declare the 64-hex value beside them to be the PUBLIC half.
PUBLIC_KEY_CONTEXTS = ("signing_key", "public_key", "publicKey", "--public-key", "publicKeyHex")


# --------------------------------------------------------------------------- #
# The scan
# --------------------------------------------------------------------------- #


def key_shaped(path: Path) -> list[str]:
    """Every reason ``path`` looks like private key material. Empty means clean."""
    reasons: list[str] = []

    if path.suffix.lower() in KEY_SUFFIXES:
        reasons.append(f"filename ends in {path.suffix.lower()!r}")
    if path.stem in KEY_STEMS:
        reasons.append(f"named like an OpenSSH private key ({path.stem})")
    # Only the part of the path BELOW the repository is examined for the tool's own key
    # directory: a checkout that happened to live under a directory of that name would
    # otherwise report every file it contains, and an alarm that fires on everything is
    # one that gets switched off.
    inside = path.relative_to(REPO_ROOT).parts if path.is_relative_to(REPO_ROOT) else (path.name,)
    if path.name == DEFAULT_KEY_PATH.name or DEFAULT_KEY_PATH.parent.name in inside:
        reasons.append(f"matches sign_usf.py's own key location ({DEFAULT_KEY_PATH})")

    if not path.is_file() or path.is_symlink():
        return reasons

    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return reasons  # binary or unreadable: no text shape to match

    for marker in CONTENT_MARKERS:
        if marker in text:
            reasons.append(f"contains {marker!r}")

    for number, line in enumerate(text.splitlines(), 1):
        if not ED25519_HEX_RE.search(line):
            continue
        if any(context in line for context in PUBLIC_KEY_CONTEXTS):
            continue  # a declared public key, which is the half that is meant to be published
        reasons.append(f"line {number} carries a bare ed25519:<64 hex> value, the shape of a private seed")

    return sorted(set(reasons))


def offenders(paths: list[Path]) -> list[str]:
    found: list[str] = []
    for path in paths:
        reasons = key_shaped(path)
        if reasons:
            found.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {'; '.join(reasons)}")
    return sorted(found)


def files_git_would_commit() -> list[Path]:
    """Tracked plus untracked-and-not-ignored: everything a `git add -A` would stage."""
    try:
        completed = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - only outside a checkout
        pytest.skip("not a git checkout, so `git ls-files` cannot be scanned")
    paths = [REPO_ROOT / name for name in completed.stdout.split("\0") if name]
    return [path for path in paths if path.is_file()]


def working_tree_files() -> list[Path]:
    """Every file on disk under the repository, ignored ones included.

    `os.walk` with the directory list pruned in place, and symlinks not followed: a walk
    that followed them could leave the tree it is supposed to be scanning.
    """
    found: list[Path] = []
    for directory, subdirectories, names in os.walk(REPO_ROOT, followlinks=False):
        subdirectories[:] = [name for name in subdirectories if name not in SKIP_DIRS]
        for name in names:
            found.append(Path(directory) / name)
    return found


# --------------------------------------------------------------------------- #
# Both lenses must actually be looking at something
# --------------------------------------------------------------------------- #


def test_both_lenses_see_this_repository():
    """Guards the two scans below from passing because they found nothing to scan."""
    committed = files_git_would_commit()
    tree = working_tree_files()
    assert len(committed) > 50, f"expected the repo listing, found {len(committed)} file(s)"
    assert len(tree) > 50, f"expected the repo tree, found {len(tree)} file(s)"
    assert REPO_ROOT / "README.md" in committed
    assert REPO_ROOT / "README.md" in tree


# --------------------------------------------------------------------------- #
# The two that matter
# --------------------------------------------------------------------------- #


def test_no_private_key_material_can_be_committed():
    """The leak in its published form: a key in a commit is a key on the internet."""
    found = offenders(files_git_would_commit())
    assert not found, (
        "private key material is staged for, or already in, this repository:\n  "
        + "\n  ".join(found)
        + "\n\nA key must never be in the working tree at all. Generate one with "
        "`python3 scripts/sign_usf.py keygen`, which refuses to write inside the repository, "
        "and treat the key above as compromised: rotate it (docs/signing.md)."
    )


def test_no_private_key_is_sitting_in_the_working_tree():
    """`.gitignore` keeps a key out of a commit. It does not keep it off the disk, out of
    `git add -f`, or out of a release tarball built from this directory."""
    found = offenders(working_tree_files())
    assert not found, (
        "private key material is present in this working tree:\n  "
        + "\n  ".join(found)
        + "\n\nIt is ignored, not absent. Move it outside the repository — see docs/signing.md."
    )


# --------------------------------------------------------------------------- #
# The scan is proven to fire, shape by shape
# --------------------------------------------------------------------------- #

#: One synthetic sample per shape the scan claims to catch. Every one is assembled at
#: runtime so this file's own bytes carry none of them.
FAKE_KEYS = {
    "pkcs8-pem": ("secret.txt", f"{PEM_MARKERS[0]}-----\nMC4CAQAwBQYDK2VwBCIEIA==\n-----END PRIVATE KEY-----\n"),
    "rsa-pem": ("notes.md", f"{PEM_MARKERS[1]}-----\nMIIEowIBAAKCAQEA\n"),
    "openssh-pem": ("deploy_token", f"{PEM_MARKERS[4]}-----\n"),
    "openssh-headerless": ("blob.txt", f"{OPENSSH_BODY_MAGIC}AAAABG5vbmUAAAAEbm9uZQAAAAAAAAAB\n"),
    "putty": ("release.txt", f"{PUTTY_MARKER}-2: ssh-ed25519\nPrivate-Lines: 1\n"),
    "raw-seed": ("scratch.md", "seed = " + "ed25519:" + "ab" * 32 + "\n"),
    "by-filename": (DEFAULT_KEY_PATH.name, "this file's NAME is the whole finding\n"),
    "openssh-filename": ("id_ed25519", "so is this one\n"),
    "der-suffix": ("release.der", "binary keys have names too\n"),
}


@pytest.mark.parametrize("shape", sorted(FAKE_KEYS))
def test_every_shape_the_scan_claims_to_catch_is_caught(shape, tmp_path):
    """A scan nobody has watched fire is a scan nobody knows the shape of."""
    name, body = FAKE_KEYS[shape]
    planted = tmp_path / name
    planted.write_text(body, encoding="utf-8")
    assert key_shaped(planted), f"the scan does not catch a {shape} private key"


def test_a_planted_key_is_invisible_to_git_and_still_caught():
    """Why there are two lenses, demonstrated rather than asserted.

    `ed25519.pem` is covered by `.gitignore`, so the commit lens cannot see it — which is
    correct (it cannot be committed) and insufficient (it is still on the disk). The tree
    lens is what closes that gap, and this is the test that proves the gap is real.

    The plant is removed in a `finally`. If a run is killed between the two, the file that
    survives is this fake and the next run fails on the tree lens naming it, which is the
    right failure: a file of that name in this directory is a finding no matter who wrote it.
    """
    planted = REPO_ROOT / DEFAULT_KEY_PATH.name
    assert not planted.exists(), f"{planted} already exists — refusing to overwrite it"

    planted.write_text(f"{PEM_MARKERS[0]}-----\nnot a real key\n-----END PRIVATE KEY-----\n", encoding="utf-8")
    try:
        assert key_shaped(planted), "the planted key is not recognised as one"
        assert any(DEFAULT_KEY_PATH.name in entry for entry in offenders(working_tree_files())), (
            "the working-tree scan missed a private key sitting in the repository root"
        )
        assert not any(DEFAULT_KEY_PATH.name in entry for entry in offenders(files_git_would_commit())), (
            "the planted key reached the commit lens, so `.gitignore` no longer covers it — "
            "fix the ignore rule; the tree lens catching it is not a substitute"
        )
    finally:
        planted.unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# …and is proven NOT to fire on the thing this repository is about to publish
# --------------------------------------------------------------------------- #


def test_a_signed_manifest_does_not_trip_the_scan(tmp_path):
    """Signing the roster writes a PUBLIC key and a 128-hex signature into every manifest.

    If that made this file fail, the first thing a maintainer would do is weaken the scan.
    """
    manifest = tmp_path / "skill.usf.yaml"
    manifest.write_text(
        "author:\n"
        '  identity: "did:web:example.com"\n'
        '  signing_key: "' + "ed25519:" + "cd" * 32 + '"\n'
        'signature: "' + "ed25519:" + "ef" * 64 + '"\n',
        encoding="utf-8",
    )
    assert not key_shaped(manifest)


def test_the_shipped_manifests_are_clean_today():
    """The eleven are unsigned, and nothing about them is key-shaped either way."""
    assert not offenders(sorted((REPO_ROOT / "skills").glob("*/skill.usf.yaml")))


# --------------------------------------------------------------------------- #
# The backstop the scan is the alarm for
# --------------------------------------------------------------------------- #


def check_ignored(name: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", name],
        cwd=REPO_ROOT,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if result.returncode == 128:  # pragma: no cover - only outside a checkout
        pytest.skip("not a git checkout, so `git check-ignore` cannot be run")
    return result.returncode == 0


@pytest.mark.parametrize("suffix", KEY_SUFFIXES)
def test_gitignore_covers_every_key_filename_suffix_the_scan_catches(suffix):
    """A backstop, not the control — `keygen` refusing to write inside the tree is the
    control. This is what catches a key that arrived some other way.

    Parametrized over the scan's own suffix list so the ignore rules and the alarm cannot
    drift apart: widening one without the other fails here.
    """
    assert check_ignored(f"release{suffix}"), f".gitignore does not cover *{suffix}"


@pytest.mark.parametrize("stem", KEY_STEMS)
def test_gitignore_covers_every_openssh_key_name_the_scan_catches(stem):
    assert check_ignored(stem), f".gitignore does not cover {stem!r}"
    assert check_ignored(f"docs/{stem}.bak"), f".gitignore does not cover a renamed copy of {stem!r}"


@pytest.mark.parametrize("name", ["keys/release.pem", "eval/scratch/signing.key"])
def test_the_ignore_rules_are_not_anchored_to_the_repository_root(name):
    """A key does not have to arrive at the top level to be a key."""
    assert check_ignored(name), f".gitignore does not cover {name!r}"


def test_gitignore_covers_the_tools_own_default_key_directory():
    """Derived from `sign_usf.py` rather than retyped, so moving the default moves this."""
    directory = DEFAULT_KEY_PATH.parent.name
    assert check_ignored(f"{directory}/{DEFAULT_KEY_PATH.name}")
    assert check_ignored(f"{directory}/anything-at-all")
