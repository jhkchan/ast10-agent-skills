"""Shared eval-count floor and negative-eval heuristic.

Vendored, standalone, from the upstream eval-harness repository (Apache-2.0) — spec.md
gate-3. See THIRD_PARTY_LICENSES.md and NOTICE for the pinned upstream commit
and drift policy.

`MIN_EVALS`, `MIN_NEGATIVE_EVALS` and `is_negative_eval()` are the generic
heuristic, unchanged from upstream. `EVAL_COUNTS` is repo-specific — upstream
keys it by the upstream eval-harness repository's own skill directory names, which do not
exist here. It starts empty and is populated by T-3.x as this repo's ten AST
skills (`AST01`.."AST10") plus the advisory skill are authored, keyed by skill
DIRECTORY name (== frontmatter `name`), mirroring upstream's contract exactly.
"""

from __future__ import annotations

import re

MIN_EVALS = 7  # nothing ships below this
MIN_NEGATIVE_EVALS = 2

# Populated per-skill by T-3.x once skills/<name>/evals/evals.json exists.
EVAL_COUNTS: dict[str, int] = {}

_NEGATIVE_EXPECTED_RE = re.compile(r"^no\b[\s—-]", re.IGNORECASE)


def is_negative_eval(e: dict) -> bool:
    """An eval is negative — "a prompt where the correct answer is 'no'" — if
    it is explicitly tagged `"negative": true`, its `name` carries a
    `negative-` marker, or its `expected_output` opens with a refusal
    ("No —")."""
    if e.get("negative") is True:
        return True
    name = str(e.get("name", ""))
    if name.startswith("negative-") or "-negative-" in name:
        return True
    return bool(_NEGATIVE_EXPECTED_RE.match(str(e.get("expected_output", "")).strip()))
