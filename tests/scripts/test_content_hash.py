"""Tests for scripts.content_hash — spec.md gate-3 vendoring (T-2.2).

content_sha256() is the primitive scripts/ship_floor.py's binding_block()
uses to bind a judged block to "the current content" of a skill's shipped
surface, defined by SURFACE_GLOBS as
(SKILL.md, references/*.md, scripts/*.py, evals/evals.json).

One of those four patterns matches nothing in this repository today
(references/*.md), so every shipped skill's content_hash is a digest over
SKILL.md plus scripts/*.py plus evals/evals.json. The tmp_path tests below
exercise the full glob set on purpose — the hasher must keep working for a
surface this repo does not currently populate — and
test_unpopulated_surface_globs_are_still_unpopulated pins the claim about the
real skills/ tree so the published docs cannot go stale unnoticed.

evals/evals.json crossed from the unpopulated half to the populated one when
the with/without eval cases were authored, and every skill's content_hash was
re-stamped in that same change. That crossing is the event these partition
tests exist to make loud, and it is the reason the tuples are values rather
than prose.
"""

from __future__ import annotations

from pathlib import Path

from scripts.content_hash import (
    POPULATED_SURFACE_GLOBS,
    SURFACE_GLOBS,
    UNPOPULATED_SURFACE_GLOBS,
    content_sha256,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"


def _write_skill(root, name: str, skill_md: str = "# hello\n") -> None:
    d = root / name
    (d / "references").mkdir(parents=True)
    (d / "scripts").mkdir(parents=True)
    (d / "SKILL.md").write_text(skill_md)
    (d / "references" / "notes.md").write_text("ref notes")
    (d / "scripts" / "detector.py").write_text("print('detect')")


def test_same_content_hashes_identically(tmp_path):
    _write_skill(tmp_path, "AST01")
    _write_skill(tmp_path, "AST01-copy")

    assert content_sha256(tmp_path / "AST01") == content_sha256(tmp_path / "AST01-copy")


def test_changing_a_surface_file_changes_the_hash(tmp_path):
    _write_skill(tmp_path, "AST01")
    before = content_sha256(tmp_path / "AST01")

    (tmp_path / "AST01" / "SKILL.md").write_text("# hello, edited\n")

    assert content_sha256(tmp_path / "AST01") != before


def test_hash_is_independent_of_filesystem_creation_order(tmp_path):
    a = tmp_path / "order-a"
    (a / "references").mkdir(parents=True)
    (a / "scripts").mkdir(parents=True)
    (a / "SKILL.md").write_text("body")
    (a / "scripts" / "z.py").write_text("z")
    (a / "references" / "notes.md").write_text("notes")

    b = tmp_path / "order-b"
    (b / "references").mkdir(parents=True)
    (b / "scripts").mkdir(parents=True)
    (b / "references" / "notes.md").write_text("notes")
    (b / "scripts" / "z.py").write_text("z")
    (b / "SKILL.md").write_text("body")

    assert content_sha256(a) == content_sha256(b)


def test_file_outside_surface_globs_does_not_affect_hash(tmp_path):
    _write_skill(tmp_path, "AST01")
    before = content_sha256(tmp_path / "AST01")

    # coverage-matrix.md is a real shipped artifact (spec.md "Behavior" #3)
    # but is NOT part of this hash's surface — it is covered by the separate
    # tier-lock hash (T-1.5), not by content_sha256.
    (tmp_path / "AST01" / "coverage-matrix.md").write_text("| scenario | tier | reason |")

    assert content_sha256(tmp_path / "AST01") == before


def test_missing_skill_dir_hashes_deterministically_to_empty_surface(tmp_path):
    missing = tmp_path / "does-not-exist"

    assert content_sha256(missing) == content_sha256(tmp_path / "also-missing")


# ---------------------------------------------------------------------------
# What the surface definition covers in THIS repo, asserted rather than implied
# ---------------------------------------------------------------------------


def test_the_two_glob_partitions_reconstruct_the_surface_definition():
    """POPULATED + UNPOPULATED must be exactly SURFACE_GLOBS, no drift."""
    assert set(POPULATED_SURFACE_GLOBS) | set(UNPOPULATED_SURFACE_GLOBS) == set(SURFACE_GLOBS)
    assert not set(POPULATED_SURFACE_GLOBS) & set(UNPOPULATED_SURFACE_GLOBS)


def test_populated_surface_globs_really_do_match_a_file_in_every_skill():
    """The half of the definition the docs say is load-bearing must be."""
    skill_dirs = sorted(d for d in SKILLS_DIR.iterdir() if (d / "SKILL.md").is_file())
    assert len(skill_dirs) == 11, "expected ten AST categories plus advisory"
    for skill in skill_dirs:
        for pattern in POPULATED_SURFACE_GLOBS:
            assert list(skill.glob(pattern)), f"{skill.name}: no file matches surface glob {pattern!r}"


def test_unpopulated_surface_globs_are_still_unpopulated():
    """Guards a documented claim, not an implementation detail.

    README.md, docs/architecture.md and every skill.usf.yaml state that
    `references/*.md` contributes nothing to any shipped content_hash because
    no skill ships one. The day one does, that prose is wrong — and a reader
    who believed it would mis-recompute the hash. Fail here rather than let the
    docs drift. `evals/evals.json` was in this half until every skill authored
    one; that is what moving a pattern to POPULATED_SURFACE_GLOBS looks like.
    """
    matched: list[str] = []
    for skill in sorted(d for d in SKILLS_DIR.iterdir() if (d / "SKILL.md").is_file()):
        for pattern in UNPOPULATED_SURFACE_GLOBS:
            matched += [str(p.relative_to(SKILLS_DIR)) for p in skill.glob(pattern) if p.is_file()]
    assert not matched, (
        "a skill now ships a surface file the docs say no skill ships: "
        f"{matched}. Update scripts/content_hash.py's partition, README.md, "
        "docs/architecture.md and the skill.usf.yaml comments together, then "
        "re-stamp every content_hash."
    )


def test_shipped_content_hash_is_reproducible_from_the_populated_globs_alone():
    """The docs' arithmetic claim: SKILL.md + scripts/*.py IS the whole digest."""
    import hashlib

    for skill in sorted(d for d in SKILLS_DIR.iterdir() if (d / "SKILL.md").is_file()):
        files: list[Path] = []
        for pattern in POPULATED_SURFACE_GLOBS:
            files += [p for p in skill.glob(pattern) if p.is_file()]
        digest = hashlib.sha256()
        for f in sorted(files, key=lambda p: p.relative_to(skill).as_posix()):
            digest.update(f.relative_to(skill).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(f.read_bytes())
        assert digest.hexdigest() == content_sha256(skill), skill.name
