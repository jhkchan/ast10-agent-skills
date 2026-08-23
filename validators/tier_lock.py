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

TWO LOCKS, AND WHY THE CLI NEEDS BOTH
-------------------------------------
``scenarios/registry.yaml`` declares itself authoritative on tier
("THIS FILE IS AUTHORITATIVE ON TIER"), but this module's CLI used to hash
only ``fixtures/manifest.yaml``'s OWN embedded entries. A tier-doctrine
review demonstrated the consequence: flipping AST01-S10 in the authoritative
registry left ``python3 validators/tier_lock.py fixtures/manifest.yaml``
printing "OK" and exiting 0. The tripwire did not guard its stated
authority.

There are now two locks and the CLI checks both:

``tier_lock_hash`` / ``check_manifest_tier_locks``
    corpus-internal. Binds a category's labeled fixtures to the tiering
    recorded beside them in the manifest. Catches an edit to the manifest.

``registry_tier_lock_hash`` / ``check_registry_tier_locks``
    corpus-to-authority. Binds each category's ``registry_tier_lock`` field
    to a hash over ``scenarios/registry.yaml``'s own scenarios for that
    category. Catches an edit to the registry -- the mutation the tripwire
    exists to catch, and the one it previously missed. The per-category
    ``coverage-matrix.md`` files quote the same hash.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "fixtures" / "manifest.yaml"
DEFAULT_REGISTRY = REPO_ROOT / "scenarios" / "registry.yaml"


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
        scenarios = list(cat.get("detectable_scenarios", [])) + list(cat.get("out_of_artifact_scenarios", []))
        ok, reason = check_tier_lock(scenarios, cat.get("tier_lock_hash", ""))
        if not ok:
            violations.append(f"{category}: {reason}")
    return violations


def registry_tier_lock_hash(registry: dict, category: str) -> str:
    """Canonical hash over the AUTHORITATIVE tiering of one category.

    Same construction as ``tier_lock_hash``, but computed from
    ``scenarios/registry.yaml``'s own scenarios rather than from whatever the
    corpus happens to have copied beside its labels. This is the hash the
    per-category ``coverage-matrix.md`` files quote as ``registry_tier_lock``.
    """
    return tier_lock_hash([s for s in registry.get("scenarios", []) if s.get("category") == category])


def check_registry_tier_locks(manifest: dict, registry: dict) -> list[str]:
    """Check every category's ``registry_tier_lock`` against the registry itself.

    Returns one violation string per category whose stored hash no longer
    matches a fresh recompute over ``scenarios/registry.yaml``. A category
    that declares no ``registry_tier_lock`` at all is itself a violation: an
    unbound corpus is indistinguishable from one whose authority silently
    moved, which is exactly the failure this check exists to make loud.
    """
    violations: list[str] = []
    for category, cat in manifest.get("categories", {}).items():
        stored = cat.get("registry_tier_lock")
        current = registry_tier_lock_hash(registry, category)
        if not stored:
            violations.append(
                f"{category}: no registry_tier_lock recorded; the corpus is not bound to "
                f"scenarios/registry.yaml (expected {current})"
            )
        elif stored != current:
            violations.append(
                f"registry tier-lock mismatch: scenarios/registry.yaml's tiering for "
                f"{category} changed since the corpus was labeled against it "
                f"(stored {stored}, current {current}); corpus requires re-labeling and a "
                f"judge re-run"
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    """CLI drift check, so CI runs the same S-011 tripwire the tests do.

    Checks BOTH locks. The registry-derived one is the load-bearing half: the
    registry declares itself authoritative on tier, so a tripwire that hashed
    only the manifest's own copy of the tiering could not see the mutation it
    exists to catch.
    """
    import argparse

    import yaml

    parser = argparse.ArgumentParser(
        prog="validators/tier_lock.py",
        description=(
            "Check every category's tier locks (S-011): its stored tier_lock_hash against "
            "the manifest's own scenario tiering, AND its registry_tier_lock against the "
            "authoritative scenarios/registry.yaml."
        ),
    )
    parser.add_argument(
        "manifest",
        nargs="?",
        default=str(DEFAULT_MANIFEST),
        help="fixtures/manifest.yaml (default: this repo's)",
    )
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY),
        help="scenarios/registry.yaml — authoritative on tier (default: this repo's)",
    )
    args = parser.parse_args(argv)

    path = Path(args.manifest)
    with path.open(encoding="utf-8") as fh:
        manifest = yaml.safe_load(fh) or {}

    registry_path = Path(args.registry)
    with registry_path.open(encoding="utf-8") as fh:
        registry = yaml.safe_load(fh) or {}

    violations = check_manifest_tier_locks(manifest)
    violations += check_registry_tier_locks(manifest, registry)
    categories = manifest.get("categories", {})
    if violations:
        for violation in violations:
            print(f"{path}: TIER-LOCK DRIFT: {violation}")
        print(
            f"{path}: FAIL — {len(violations)} tier-lock violation(s) across "
            f"{len(categories)} categories; the affected corpora must be re-labeled and "
            "re-judged before their F1 is republished"
        )
        return 1
    print(f"{path}: OK — {len(categories)} category tier-lock(s) intact against {registry_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
