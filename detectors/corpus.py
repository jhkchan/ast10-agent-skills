"""detectors/corpus.py -- the join between the labeled fixture corpus and the detectors.

`fixtures/manifest.yaml` labels every case with a check id and a path;
`skills/<ID>/scripts/detector.py` exposes `DETECTORS`, a map of check id to
function over a `{"manifest": ..., "files": ...}` package dict. Until this
module existed nothing connected the two: the cases were `SKILL.md` files on
disk, the detectors took a dict, and the two sides used different id
namespaces. Every category consequently published `pending-detector` -- a
corpus nothing consumed and a detector nothing measured.

This module is that connection, and it is deliberately small and explicit:

* **The package view.** ``load_case_package`` reads a case directory into the
  detector package shape. Every file in the directory is a package file
  except ``skill.usf.yaml``, which is the *manifest*, not package content --
  the same exclusion `scripts/content_hash.py` makes, and the reason a
  content hash can cover the package without covering the field that carries
  it.
* **The id map.** ``check_map`` reads each labeled check's ``detector_check``
  field from `fixtures/manifest.yaml`. The manifest is the authority on which
  fixture measures which check, so the mapping lives beside the labels rather
  than in a private table inside the detector module.
* **The expectation.** A `vulnerable` case expects exactly its own check to
  fire; a `clean` case expects nothing to fire *at all*. That second half is
  the strict one, and it is the point: a check that fires on a clean case is a
  false positive whether or not it is the check the case was written for. It
  is what the F1 the manifest publishes is computed against.

The corpus never contains a case bound to an out-of-artifact scenario (S-003),
which `fixtures/test_manifest.py` enforces on the manifest itself; this module
therefore does not need to re-police the tier, only to refuse a label it
cannot resolve to a shipped check.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "fixtures" / "manifest.yaml"

#: Files inside a case directory that are the package's *manifest*, not its
#: content. Excluded from the package `files` view for the same reason
#: `scripts/content_hash.py` excludes them from the hashed surface.
MANIFEST_FILENAMES = ("skill.usf.yaml",)


class CorpusError(RuntimeError):
    """A labeled corpus that cannot be resolved to the detectors it names."""


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def case_files(case_dir: Path) -> dict[str, str]:
    """Every package file in a case directory, keyed by relative posix path."""
    files: dict[str, str] = {}
    for path in sorted(case_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(case_dir).as_posix()
        if rel in MANIFEST_FILENAMES:
            continue
        files[rel] = path.read_text(encoding="utf-8")
    return files


def case_manifest(case_dir: Path) -> dict:
    """The case's USF manifest, or ``{}`` when the fixture ships none.

    A fixture with no manifest is a real shape -- a bare `SKILL.md` package --
    and the detectors must see the absence rather than a synthesised default.
    """
    for name in MANIFEST_FILENAMES:
        path = case_dir / name
        if path.is_file():
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    return {}


def load_case_package(case_dir: Path) -> dict:
    """One fixture case directory as a detector package dict."""
    if not case_dir.is_dir():
        raise CorpusError(f"no such fixture case directory: {case_dir}")
    return {"manifest": case_manifest(case_dir), "files": case_files(case_dir)}


def content_digest(case_dir: Path) -> str:
    """sha256 over the case's package files, in the detectors' own framing.

    Same construction as `scripts/content_hash.py::content_sha256` and
    `skills/AST01/scripts/detector.py::_package_digest`: sorted relative path,
    NUL, bytes. A fixture's declared `content_hash` is generated from this, so
    the two content-hash checks see a truthfully-hashed package and a fixture
    edit that forgets to regenerate is caught by
    `tests/test_fixture_corpus.py` rather than by a silent false positive.
    """
    digest = hashlib.sha256()
    for rel, content in sorted(case_files(case_dir).items()):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(content.encode("utf-8"))
    return digest.hexdigest()


def check_map(category: str, manifest: dict | None = None) -> dict[str, str]:
    """``{labeled check id: detector check id}`` for one category.

    Raises when a labeled check declares no ``detector_check``: an unmapped
    label is a corpus that measures nothing, which is exactly the state this
    module exists to end.
    """
    data = manifest or load_manifest()
    entry = data["categories"][category]
    mapping: dict[str, str] = {}
    for check in entry.get("detectable_scenarios") or []:
        detector_check = check.get("detector_check")
        if not detector_check:
            raise CorpusError(
                f"{category}/{check['id']} is a labeled detectable check with no "
                f"`detector_check`; the corpus would measure nothing"
            )
        mapping[check["id"]] = detector_check
    return mapping


def category_fixtures(
    category: str,
    manifest: dict | None = None,
    repo_root: Path = REPO_ROOT,
) -> list[tuple[dict, set[str]]]:
    """The `(package, expected_detected_check_ids)` pairs for one category.

    Vulnerable cases expect exactly the check they are labeled against; clean
    cases expect nothing at all, so any check firing on one is scored as a
    false positive.
    """
    data = manifest or load_manifest()
    mapping = check_map(category, data)
    entry = data["categories"][category]
    pairs: list[tuple[dict, set[str]]] = []
    for case in entry.get("cases") or []:
        case_dir = (repo_root / case["path"]).parent
        package = load_case_package(case_dir)
        if case["label"] == "vulnerable":
            expected = {mapping[case["scenario_id"]]}
        else:
            expected = set()
        pairs.append((package, expected))
    return pairs
