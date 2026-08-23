"""validators/tier_lock.py — S-011 tier-lock tripwire.

Binds a category's hand-labeled fixture corpus to the scenario tiering it
was labeled against: ``tier_lock_hash`` is a canonical sha256 over every
scenario's "id:tier" pair (both the detectable and out-of-artifact lists).
``check_tier_lock`` recomputes that hash and flags a mismatch as requiring
fixture re-labeling and a judge re-run, per spec.md S-011, rather than
silently republishing an F1 number the corpus was not labeled against.

Referenced (but previously missing) by scripts/content_hash.py's own
docstring: "a distinct tier-lock hash (T-1.5, validators/tier_lock.py), a
distinct mechanism for a distinct invariant (scenario tiering vs. judged
skill content)." Moved here from fixtures/test_manifest.py (code-review
finding: architecture, MEDIUM) so a production path -- not just a pytest
module -- can check the tier lock before a category's F1 row is published.
"""

from __future__ import annotations

import hashlib


def tier_lock_hash(scenarios: list[dict]) -> str:
    """Canonical content hash over a category's full scenario tiering.

    Deterministic across key order: built from sorted "id:tier" pairs so any
    change to which tier a scenario is classified under changes the hash
    (S-011's re-run tripwire).
    """
    canonical = "|".join(sorted(f"{s['id']}:{s['tier']}" for s in scenarios))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def check_tier_lock(scenarios: list[dict], locked_hash: str) -> tuple[bool, str | None]:
    """Return (ok, reason). ok=False means the corpus must be re-labeled and re-run (S-011)."""
    current = tier_lock_hash(scenarios)
    if current != locked_hash:
        changed = [s["id"] for s in scenarios]
        return False, (
            f"tier-lock mismatch: scenario tiering changed since fixtures were labeled "
            f"(affected candidates: {changed}); corpus requires re-labeling and a judge re-run"
        )
    return True, None


def check_manifest_tier_locks(manifest: dict) -> list[str]:
    """Check every category's tier lock in a loaded fixtures/manifest.yaml dict.

    Returns the list of violation reasons, one per category whose stored
    ``tier_lock_hash`` no longer matches its current ``detectable_scenarios``
    + ``out_of_artifact_scenarios`` tiering (empty when every category's
    labeled corpus is still valid). Intended to run before any category's F1
    row is published, per S-011 -- a production caller (an F1 runner, a
    release script) has a real path to this check now, not only the pytest
    module fixtures/test_manifest.py used to hold it in.
    """
    violations: list[str] = []
    for category, cat in manifest.get("categories", {}).items():
        scenarios = list(cat.get("detectable_scenarios", [])) + list(
            cat.get("out_of_artifact_scenarios", [])
        )
        ok, reason = check_tier_lock(scenarios, cat.get("tier_lock_hash", ""))
        if not ok:
            violations.append(f"{category}: {reason}")
    return violations
