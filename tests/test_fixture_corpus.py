"""Integrity of the labeled fixture corpus.

Sixteen fixture manifests state that "a fixture edit that forgets to regenerate is
caught by tests/test_fixture_corpus.py". This is that file. Without it the claim was
a dangling reference of exactly the kind the repo's own AST08 guidance calls out --
a named guard that does not exist.

A fixture whose content_hash has gone stale is worse than one with no hash: the
detectors that read the manifest would be reasoning about a package that is not the
package on disk, and a corpus that misrepresents itself cannot support an F1 claim.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from scripts.content_hash import content_sha256

REPO = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = REPO / "fixtures"


def _fixture_packages() -> list[pathlib.Path]:
    return sorted(p.parent for p in FIXTURES.glob("AST*/*/skill.usf.yaml"))


PACKAGES = _fixture_packages()


def test_the_corpus_is_not_empty():
    assert PACKAGES, "no fixture packages found — the corpus cannot have vanished"


@pytest.mark.parametrize("pkg", PACKAGES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_fixture_content_hash_matches_its_own_files(pkg: pathlib.Path):
    manifest = yaml.safe_load((pkg / "skill.usf.yaml").read_text(encoding="utf-8"))
    declared = (manifest or {}).get("content_hash")
    if not declared:
        pytest.skip(f"{pkg.name} declares no content_hash")
    actual = content_sha256(pkg)
    expected = declared.split(":", 1)[1] if ":" in declared else declared
    assert expected == actual, (
        f"{pkg.parent.name}/{pkg.name}: content_hash is stale.\n"
        f"  declared: {expected}\n  actual:   {actual}\n"
        f"Regenerate with: python3 -c \"from scripts.content_hash import content_sha256; "
        f"print(content_sha256('{pkg.relative_to(REPO)}'))\""
    )


@pytest.mark.parametrize("pkg", PACKAGES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_fixture_package_has_a_skill_md(pkg: pathlib.Path):
    assert (pkg / "SKILL.md").is_file(), f"{pkg} has a manifest but no SKILL.md"


@pytest.mark.parametrize("pkg", PACKAGES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_fixture_label_is_encoded_in_its_directory_name(pkg: pathlib.Path):
    """V-prefixed cases are vulnerable, C-prefixed are clean. The loader keys on this."""
    assert pkg.name[0] in {"V", "C"}, (
        f"{pkg.name} does not start with V (vulnerable) or C (clean); "
        "detectors/fixture_loader.py derives the ground-truth label from this prefix"
    )
