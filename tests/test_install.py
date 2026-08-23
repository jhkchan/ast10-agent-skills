"""Contract tests for `cli/ast10.py install`.

This is the command README Method 1 and Method 3 both hand a reader, and it was
the only user-facing verb in the repository with no test of its own:
`tests/test_cli.py` skips its whole module when `node` is absent, and the two
Python-CLI assertions it does make are cross-checks of the Node front end's
numbers, not of installation. So the one command that writes to a directory
outside the repository was exercised by nothing.

Four properties are asserted, and the third is the one with teeth:

1. The destination directory is named after the frontmatter `name`, not the
   `ASTnn` directory -- that name is the identifier a runtime matches an
   invocation against, so getting it wrong installs an unreachable skill.
2. `--dry-run` writes nothing, and `--all` resolves to all eleven packages.
3. **No local build residue is installed.** Running the suite leaves
   `__pycache__/` (and, in at least one package, `.pytest_cache/`) inside a
   skill directory. A plain `copytree` puts that into the user's skills
   directory: bytes nobody authored, nobody reviewed, and no `content_hash`
   covers. For a repository whose subject is what is actually inside a skill
   you install, shipping unexamined files is the failure it documents.
4. An existing destination is skipped unless `--force` is passed, so an install
   cannot silently overwrite a package a user edited.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "ast10.py"

#: Anything matching these must never appear under an installed package.
RESIDUE_NAMES = ("__pycache__", ".pytest_cache", ".ruff_cache", ".DS_Store")
RESIDUE_SUFFIXES = (".pyc", ".pyo")


def run_install(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), "install", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def installed_paths(target: Path) -> list[Path]:
    return sorted(p for p in target.rglob("*"))


def test_install_dry_run_writes_nothing(tmp_path):
    result = run_install("--all", "--target", str(tmp_path), "--dry-run")
    assert result.returncode == 0, result.stderr
    assert not installed_paths(tmp_path), "--dry-run created files"
    assert "nothing written" in result.stdout
    # One `plan` line per skill the repo ships.
    assert len(re.findall(r"^plan\s", result.stdout, re.MULTILINE)) == 11


def test_install_names_the_destination_after_the_frontmatter_name(tmp_path):
    result = run_install("--skill", "AST03", "--target", str(tmp_path))
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "ast03-over-privileged-skills" / "SKILL.md").is_file()
    assert not (tmp_path / "AST03").exists(), "installed under the directory name, not the skill name"


def test_install_all_writes_every_package(tmp_path):
    result = run_install("--all", "--target", str(tmp_path))
    assert result.returncode == 0, result.stderr
    installed = sorted(p.name for p in tmp_path.iterdir() if p.is_dir())
    assert len(installed) == 11, installed
    for name in installed:
        assert (tmp_path / name / "SKILL.md").is_file(), f"{name} installed without a SKILL.md"


def test_install_ships_no_local_build_residue(tmp_path):
    """The teeth. Seed a cache directory into the source package first, so the
    test fails on a `copytree` with no ignore list rather than passing because
    the working tree happened to be clean."""
    seeded = REPO_ROOT / "skills" / "AST03" / "scripts" / "__pycache__"
    seeded.mkdir(parents=True, exist_ok=True)
    marker = seeded / "detector.cpython-999.pyc"
    marker.write_bytes(b"\x00seeded-by-test")
    try:
        result = run_install("--all", "--target", str(tmp_path))
        assert result.returncode == 0, result.stderr
        offenders = [
            p.relative_to(tmp_path).as_posix()
            for p in installed_paths(tmp_path)
            if p.name in RESIDUE_NAMES or p.suffix in RESIDUE_SUFFIXES
        ]
        assert not offenders, f"install copied local build residue into the target: {offenders}"
    finally:
        marker.unlink(missing_ok=True)
        if seeded.is_dir() and not any(seeded.iterdir()):
            seeded.rmdir()


def test_install_skips_an_existing_destination_without_force(tmp_path):
    assert run_install("--skill", "AST03", "--target", str(tmp_path)).returncode == 0
    sentinel = tmp_path / "ast03-over-privileged-skills" / "SKILL.md"
    sentinel.write_text("locally edited", encoding="utf-8")

    again = run_install("--skill", "AST03", "--target", str(tmp_path))
    assert again.returncode == 0, again.stderr
    assert "skip" in again.stdout
    assert sentinel.read_text(encoding="utf-8") == "locally edited", "install overwrote an existing package"

    forced = run_install("--skill", "AST03", "--target", str(tmp_path), "--force")
    assert forced.returncode == 0, forced.stderr
    assert sentinel.read_text(encoding="utf-8") != "locally edited", "--force did not replace the package"


def test_install_rejects_an_unknown_skill(tmp_path):
    result = run_install("--skill", "AST99", "--target", str(tmp_path))
    assert result.returncode != 0
    assert "unknown skill" in (result.stdout + result.stderr).lower()
    assert not installed_paths(tmp_path)


@pytest.mark.parametrize("selector", ["AST03", "ast03-over-privileged-skills", "advisory"])
def test_install_accepts_both_the_directory_id_and_the_frontmatter_name(tmp_path, selector):
    result = run_install("--skill", selector, "--target", str(tmp_path), "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "1 skill(s) planned" in result.stdout
