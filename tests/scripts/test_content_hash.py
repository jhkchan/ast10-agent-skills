"""Tests for scripts.content_hash — spec.md gate-3 vendoring (T-2.2).

content_sha256() is the primitive scripts/ship_floor.py's binding_block()
uses to bind a judged block to "the current content" of a skill's shipped
surface (SKILL.md, references/*.md, scripts/*.py, evals/evals.json).
"""

from __future__ import annotations

from scripts.content_hash import content_sha256


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
