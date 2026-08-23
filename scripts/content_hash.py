"""Shared sha256 helper for a skill's shipped surface.

Vendored, standalone, from the upstream eval-harness repository (Apache-2.0) — spec.md
gate-3: "Vendor a standalone copy of ship_floor.py, content_hash.py,
eval_counts.py into scripts/ ... No live dependency on another repo." See
THIRD_PARTY_LICENSES.md and NOTICE for the pinned upstream commit and drift
policy. Do not hand-edit the hashing algorithm without updating both.

Used by scripts/ship_floor.py (recomputes content_sha256 from disk to bind a
judged block to the current skill surface) and by whatever writes the judged
block at score time (scripts/judge_harness.py, T-2.3). One definition so the
writer and every checker cannot drift.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# Relative-to-skill-dir glob patterns that make up a skill's shipped surface,
# sorted by relative path before hashing. Vendored as-is from upstream; this
# repo's skills additionally ship a coverage-matrix.md (spec.md "Behavior" #3)
# which is NOT part of this surface — it is covered by its own tier-lock hash
# (T-1.5, validators/tier_lock.py), a distinct mechanism for a distinct
# invariant (scenario tiering vs. judged skill content).
SURFACE_GLOBS = ("SKILL.md", "references/*.md", "scripts/*.py", "evals/evals.json")

# Which of those patterns actually match a file in THIS repository, stated
# rather than implied. An independent review found the docs describing the
# hashed surface as if it contained `references/*.md` and `evals/evals.json`
# when no skill here ships either, so every skill's content_hash is in fact a
# digest over `SKILL.md` plus `scripts/*.py` and nothing else.
#
# The two unpopulated patterns are kept rather than deleted, for one reason:
# the day a skill adds a `references/notes.md` or an `evals/evals.json`, that
# file must enter the hash without anybody remembering to edit this tuple. A
# surface definition that silently stops covering a shipped file is the AST10
# metadata-loss shape. Removing the patterns would be hash-neutral today and a
# trap tomorrow.
#
# `tests/scripts/test_content_hash.py::test_unpopulated_surface_globs_are_still_unpopulated`
# fails the moment that changes, so the prose above cannot go stale quietly,
# and `tests/test_docs.py` asserts the published docs say the same thing.
POPULATED_SURFACE_GLOBS = ("SKILL.md", "scripts/*.py")
UNPOPULATED_SURFACE_GLOBS = ("references/*.md", "evals/evals.json")


def _surface_files(skill_dir: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in SURFACE_GLOBS:
        files.extend(p for p in skill_dir.glob(pattern) if p.is_file())
    return sorted(files, key=lambda p: p.relative_to(skill_dir).as_posix())


def content_sha256(skill_dir: Path) -> str:
    """sha256 over a skill's shipped surface, hashed as path\\0bytes concatenation.

    Sorted by relative path so the hash is independent of filesystem iteration
    order. A missing skill directory or an empty surface still hashes
    deterministically (to the hash of zero files).
    """
    digest = hashlib.sha256()
    for f in _surface_files(skill_dir):
        rel = f.relative_to(skill_dir).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(f.read_bytes())
    return digest.hexdigest()
