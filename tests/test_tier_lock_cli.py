"""The S-011 tripwire must guard the authority it names.

``scenarios/registry.yaml`` declares itself authoritative on tier. The CLI in
``validators/tier_lock.py`` used to hash only ``fixtures/manifest.yaml``'s own
embedded copy of the tiering, which meant the mutation the tripwire exists to
catch went straight past it: flipping AST01-S10's tier in the authoritative
registry left ``python3 validators/tier_lock.py fixtures/manifest.yaml``
printing "OK" and exiting 0.

These tests drive the real command with ``subprocess``, not the library
functions, because a tripwire that fires only when a test calls it directly is
one refactor away from firing nowhere -- the same reason the CLI exists at all.
Every mutation below is asserted to produce a NON-ZERO exit through the
production path.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "validators" / "tier_lock.py"
REGISTRY = REPO_ROOT / "scenarios" / "registry.yaml"
MANIFEST = REPO_ROOT / "fixtures" / "manifest.yaml"


def run_cli(manifest: pathlib.Path, registry: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), str(manifest), "--registry", str(registry)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=120,
    )


def flip_scenario_tier(source: str, scenario_id: str, new_tier: str) -> str:
    """Rewrite one scenario's `tier:` line in the registry text, leaving the rest byte-identical."""
    start = source.index(f"  - id: {scenario_id}\n")
    end = source.find("\n  - id: ", start)
    end = len(source) if end == -1 else end + 1
    block = source[start:end]
    for tier in ("static-detectable", "agent-judgable", "out-of-artifact"):
        needle = f"    tier: {tier}\n"
        if needle in block:
            assert tier != new_tier, f"{scenario_id} is already {new_tier}"
            return source[:start] + block.replace(needle, f"    tier: {new_tier}\n", 1) + source[end:]
    raise AssertionError(f"no tier line found for {scenario_id}")


def test_the_repository_as_shipped_passes_both_locks():
    result = run_cli(MANIFEST, REGISTRY)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_the_default_invocation_checks_the_registry_too():
    """No arguments at all still binds the corpus to the authority."""
    result = subprocess.run([sys.executable, str(CLI)], capture_output=True, text=True, cwd=REPO_ROOT, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "registry.yaml" in result.stdout


@pytest.mark.parametrize(
    ("scenario_id", "new_tier"),
    [
        # The exact mutation the review demonstrated slipping through.
        ("AST01-S10", "agent-judgable"),
        # And the reverse direction: promoting an out-of-artifact scenario is the
        # move that would let a padded corpus be published.
        ("AST07-S01", "static-detectable"),
        ("AST09-S03", "static-detectable"),
    ],
)
def test_mutating_the_authoritative_registry_exits_non_zero(tmp_path, scenario_id, new_tier):
    """Edit the AUTHORITY, leave the corpus untouched, and the CLI must fail.

    This is the whole point of the fix. The manifest copy is byte-identical to the
    shipped one, so its own `tier_lock_hash` values still recompute perfectly -- only
    the registry-derived lock can see this, and it must.
    """
    manifest_copy = tmp_path / "manifest.yaml"
    manifest_copy.write_text(MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")
    registry_copy = tmp_path / "registry.yaml"
    registry_copy.write_text(
        flip_scenario_tier(REGISTRY.read_text(encoding="utf-8"), scenario_id, new_tier),
        encoding="utf-8",
    )

    # Precondition: the mutation is real and nothing else moved.
    mutated = {s["id"]: s["tier"] for s in yaml.safe_load(registry_copy.read_text())["scenarios"]}
    shipped = {s["id"]: s["tier"] for s in yaml.safe_load(REGISTRY.read_text())["scenarios"]}
    assert mutated[scenario_id] == new_tier
    assert {k: v for k, v in mutated.items() if k != scenario_id} == {
        k: v for k, v in shipped.items() if k != scenario_id
    }

    result = run_cli(manifest_copy, registry_copy)
    assert result.returncode != 0, (
        "the tier-lock CLI accepted a mutated authoritative registry:\n" + result.stdout + result.stderr
    )
    assert "TIER-LOCK DRIFT" in result.stdout
    assert scenario_id[:5] in result.stdout  # the affected category is named
    assert "re-labeling" in result.stdout and "re-run" in result.stdout


def test_mutating_the_manifests_own_tiering_still_exits_non_zero(tmp_path):
    """The corpus-internal lock did not regress while the registry lock was added."""
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    manifest["categories"]["AST01"]["detectable_scenarios"][0]["tier"] = "agent-judgable"
    manifest_copy = tmp_path / "manifest.yaml"
    manifest_copy.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    result = run_cli(manifest_copy, REGISTRY)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "tier-lock mismatch" in result.stdout


def test_a_category_that_declares_no_registry_lock_exits_non_zero(tmp_path):
    """An unbound corpus is indistinguishable from one whose authority moved."""
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    del manifest["categories"]["AST04"]["registry_tier_lock"]
    manifest_copy = tmp_path / "manifest.yaml"
    manifest_copy.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    result = run_cli(manifest_copy, REGISTRY)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "no registry_tier_lock recorded" in result.stdout


def test_the_manifest_lock_and_the_registry_lock_are_different_hashes():
    """Two locks over two sources. If they were the same value one of them is redundant."""
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    same = [
        category
        for category, cat in manifest["categories"].items()
        if cat["tier_lock_hash"] == cat["registry_tier_lock"]
        and cat["detectable_scenarios"] + (cat.get("out_of_artifact_scenarios") or [])
        and len(cat["detectable_scenarios"] + (cat.get("out_of_artifact_scenarios") or []))
        != len([s for s in yaml.safe_load(REGISTRY.read_text())["scenarios"] if s["category"] == category])
    ]
    assert not same, (
        f"{same}: the corpus-internal and registry-derived locks collided over different "
        f"scenario sets, which means one of them is not hashing what it claims to"
    )


def test_every_coverage_matrix_that_quotes_a_registry_lock_quotes_the_right_one():
    """The matrices publish the same hash; a stale one there is a stale audit trail."""
    import re

    from validators.tier_lock import registry_tier_lock_hash

    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    checked = 0
    for category in [f"AST{i:02d}" for i in range(1, 11)]:
        path = REPO_ROOT / "skills" / category / "coverage-matrix.md"
        if not path.is_file():
            continue
        match = re.search(r"registry_tier_lock:\s*([0-9a-f]{64})", path.read_text(encoding="utf-8"))
        if not match:
            continue
        checked += 1
        assert match.group(1) == registry_tier_lock_hash(registry, category), (
            f"{path} quotes a stale registry_tier_lock"
        )
    assert checked, "no coverage matrix quotes a registry_tier_lock; the audit trail is inert"
