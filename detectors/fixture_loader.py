"""detectors/fixture_loader.py — wire the labeled fixture corpus to the detectors.

Until this module existed, `fixtures/manifest.yaml` declared a hand-labeled
vulnerable/clean corpus and nothing in the repository ever fed one of those
files to a detector. Every category's `published_f1` therefore read
`pending-detector`, and each `coverage-matrix.md` recorded the same
"Reconciliation debt" item: *no loader maps `fixtures/<ID>/*/SKILL.md` onto the
`pkg` shape the detector consumes*. This is that loader.

**It does not add a third translator.** `tests/test_cli_bridge.py` pins the rule
that this repository has exactly ONE USF -> detector-shape translation
(`scripts/dogfood.py::translate_permissions`) because translating security
metadata between two vocabularies is the AST10 failure the repo is about. A
fixture directory is a candidate skill package, which is precisely what
`cli/lib/bridge.py` already knows how to read, so this module calls the bridge
rather than re-deriving the mapping.

**Scoring is per labeled check, never blended across them.** Each corpus check
in `fixtures/manifest.yaml` names the detector function it was labeled against
(`detector_check`), and each check is scored over its own vulnerable/clean pair
via `detectors/engine.py::run_category`. That is what makes the numbers
falsifiable: a check that fires on everything scores a false positive on its own
clean case rather than hiding inside a category-wide average. The per-check rows
are returned alongside the category total so a reader can see both.

A check whose corpus is a proxy (`covers: artifact-signal-only`) is reported
under its own scope label and never summed into a scenario-level figure — the
same rule `detectors/scaffold.py::f1_scope` applies to the module side.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no cover - import-path bootstrap
    sys.path.insert(0, str(REPO_ROOT))

from cli.lib import bridge  # noqa: E402
from detectors.engine import CoverageEntry, FixtureCase, Tier, run_category  # noqa: E402

MANIFEST_PATH = REPO_ROOT / "fixtures" / "manifest.yaml"


class FixtureCorpusError(RuntimeError):
    """The corpus cannot be run as declared."""


# --------------------------------------------------------------------------- load


def load_fixture_package(
    fixture_dir: Path,
    byte_views: Callable[[Path], dict] | None = None,
    surface_scoped: bool = False,
) -> dict:
    """One fixture directory as the ``{"manifest": ..., "files": ...}`` pkg dict.

    The manifest comes from `skill.usf.yaml` when the fixture ships one and from
    SKILL.md frontmatter otherwise, exactly as `cli/lib/bridge.py` resolves a
    candidate under audit; `files` is every text file in the directory, because a
    `manifest.json`, a `config.toml` or a bundled script is where AST04's findings
    live and none of those is part of the declared shipped surface.

    ``surface_scoped`` selects the DECLARED SHIPPED SURFACE instead
    (`scripts/content_hash.py`'s ``SURFACE_GLOBS``), and it is not an option --
    it is `cli/lib/bridge.py::SURFACE_SCOPED`'s rule, which this loader has to
    obey for the same reason the CLI does. AST01's two content-hash checks
    recompute that digest, and the scan view includes `skill.usf.yaml` (a
    ``.yaml`` file) while the hashed surface deliberately excludes it -- the
    field carrying the hash cannot be inside the hash. Feeding those checks the
    scan view reports a mismatch for every well-formed fixture: a false positive
    manufactured by the harness rather than by the package, which is exactly the
    thing this repository's F1 numbers must not be built on top of.

    ``byte_views`` is the escape hatch for a detector whose scenario is not
    decidable from decoded text at all. `cli/lib/bridge.py`'s scan view is text
    only -- it skips `__pycache__`, non-text suffixes and symlinks by design --
    and AST08's two host-hazard scenarios live in exactly what it skips: a
    `.pyc` header (`AST08-S08`), a zip central directory and a symlink target
    (`AST08-S07`). Rather than teach the bridge a second file-reading policy,
    the caller passes the *detector module's own* package loader (AST08 ships
    `load_package_dir`), and its `blobs`/`entries` views are attached here. The
    bridge-derived `manifest` still wins, so nothing about how a declaration is
    read changes: this adds views, it does not add a translator.
    """
    fixture_dir = Path(fixture_dir)
    if not fixture_dir.is_dir():
        raise FixtureCorpusError(f"no such fixture directory: {fixture_dir}")
    raw_manifest, source = bridge.read_manifest(fixture_dir)
    manifest, notes = bridge.adapt_manifest(raw_manifest)
    if surface_scoped:
        files, skipped = bridge.read_surface_files(fixture_dir), []
    else:
        files, skipped = bridge.read_scan_files(fixture_dir)
    extra: dict = {}
    if byte_views is not None:
        view = byte_views(fixture_dir)
        extra["blobs"] = view.get("blobs", {})
        extra["entries"] = view.get("entries", {})
        # The byte view decodes more files than the text-suffix allowlist does;
        # where both saw a file, the bridge's text wins so the two views can
        # never disagree about a file's contents.
        files = {**view.get("files", {}), **files}
    return {
        "name": fixture_dir.name,
        "manifest": manifest,
        "files": files,
        **extra,
        "manifest_source": source,
        "adapter_notes": notes,
        "skipped_files": skipped,
        "scope": "declared-surface" if surface_scoped else "all-files",
    }


@dataclass(frozen=True)
class LoadedCase:
    """One labeled fixture case, loaded and bound to the check it scores."""

    case_id: str
    scenario_id: str  # the corpus-local check id, e.g. "AST03-S1"
    detector_check: str  # the detector function id it was labeled against
    label: str  # "vulnerable" | "clean"
    path: str
    pkg: dict

    @property
    def is_vulnerable(self) -> bool:
        return self.label == "vulnerable"


def load_manifest(path: Path | str = MANIFEST_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def load_category_cases(
    category: str,
    manifest: dict | None = None,
    byte_views: Callable[[Path], dict] | None = None,
) -> list[LoadedCase]:
    """Every declared case for one category, loaded from disk.

    Raises rather than skipping when a case names a corpus check the manifest
    does not declare, or a check that declares no ``detector_check``: a case that
    quietly drops out of the run shrinks the denominator invisibly, which is the
    failure `detectors/engine.py` already refuses for an unregistered scenario id.

    ``byte_views`` defaults to the category detector's own ``load_package_dir``
    when it ships one, so a caller that loads the cases by hand sees exactly the
    packages :func:`run_corpus` scores. Pass it explicitly (or pass a loader that
    returns ``{}``) only to override that.
    """
    manifest = manifest or load_manifest()
    entry = (manifest.get("categories") or {}).get(category)
    if entry is None:
        raise FixtureCorpusError(f"{category} is not declared in fixtures/manifest.yaml")
    if byte_views is None:
        byte_views = byte_view_loader(category)

    checks = {s["id"]: s for s in entry.get("detectable_scenarios") or []}
    cases: list[LoadedCase] = []
    for case in entry.get("cases") or []:
        check = checks.get(case["scenario_id"])
        if check is None:
            raise FixtureCorpusError(
                f"{category} case {case['id']} names corpus check {case['scenario_id']!r}, "
                f"which the manifest does not declare"
            )
        detector_check = check.get("detector_check")
        if not detector_check:
            raise FixtureCorpusError(
                f"{category} corpus check {check['id']!r} declares no detector_check; "
                f"its cases cannot be scored against anything"
            )
        fixture_dir = (REPO_ROOT / case["path"]).parent
        cases.append(
            LoadedCase(
                case_id=case["id"],
                scenario_id=case["scenario_id"],
                detector_check=detector_check,
                label=case["label"],
                path=case["path"],
                pkg=load_fixture_package(fixture_dir, byte_views, category in bridge.SURFACE_SCOPED),
            )
        )
    return cases


def byte_view_loader(category: str) -> Callable[[Path], dict] | None:
    """The category detector's own package loader, when the module ships one.

    Only AST08 does today, and only because two of its scenarios are decided
    from bytes the text scan view cannot carry. Resolving it here -- rather than
    naming AST08 in a branch -- keeps the rule general: a detector that needs a
    view of its input beyond decoded text declares that view by shipping the
    loader that builds it.
    """
    return getattr(load_detector(category), "load_package_dir", None)


def load_detector(category: str):
    """Load ``skills/<category>/scripts/detector.py`` by path."""
    path = REPO_ROOT / "skills" / category / "scripts" / "detector.py"
    if not path.is_file():
        # `spec_from_file_location` happily returns a spec for a path that does
        # not exist and only fails at `exec_module`, with a bare
        # FileNotFoundError that says nothing about the corpus. Refuse here so
        # the caller gets the corpus error this module promises.
        raise FixtureCorpusError(f"cannot load {path}: no such detector module")
    spec = importlib.util.spec_from_file_location(f"_fixture_detector_{category}", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise FixtureCorpusError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------- run


@dataclass(frozen=True)
class CheckResult:
    """One corpus check's confusion matrix over its own labeled pair(s)."""

    corpus_check: str
    detector_check: str
    covers: str
    registry_ids: tuple[str, ...]
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    case_verdicts: tuple[tuple[str, bool, bool], ...]  # (case_id, predicted, is_vulnerable)

    @property
    def precision(self) -> float:
        denominator = self.true_positives + self.false_positives
        return self.true_positives / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positives + self.false_negatives
        return self.true_positives / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        total = self.precision + self.recall
        return 2 * self.precision * self.recall / total if total else 0.0

    @property
    def discriminates(self) -> bool:
        """True when the check separated vulnerable from clean on its own pair.

        The exact property the AST01 review found missing: "fires identically on
        all six of its own labeled fixtures — vulnerable and clean alike".
        """
        predicted = {verdict for _case, verdict, _label in self.case_verdicts}
        return self.false_positives == 0 and self.false_negatives == 0 and predicted == {True, False}


@dataclass(frozen=True)
class CategoryCorpusResult:
    category: str
    checks: tuple[CheckResult, ...]
    f1_scope: str

    @property
    def true_positives(self) -> int:
        return sum(c.true_positives for c in self.checks)

    @property
    def false_positives(self) -> int:
        return sum(c.false_positives for c in self.checks)

    @property
    def false_negatives(self) -> int:
        return sum(c.false_negatives for c in self.checks)

    @property
    def true_negatives(self) -> int:
        return sum(c.true_negatives for c in self.checks)

    def _scoped(self, covers: str) -> tuple[CheckResult, ...]:
        return tuple(c for c in self.checks if c.covers == covers)

    def f1(self, covers: str | None = None) -> float:
        checks = self.checks if covers is None else self._scoped(covers)
        tp = sum(c.true_positives for c in checks)
        fp = sum(c.false_positives for c in checks)
        fn = sum(c.false_negatives for c in checks)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        return 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    def cases(self, covers: str | None = None) -> int:
        checks = self.checks if covers is None else self._scoped(covers)
        return sum(len(c.case_verdicts) for c in checks)


def run_corpus(category: str, manifest: dict | None = None) -> CategoryCorpusResult:
    """Run one category's labeled corpus through its own detector, check by check."""
    manifest = manifest or load_manifest()
    entry = (manifest.get("categories") or {}).get(category) or {}
    module = load_detector(category)
    cases = load_category_cases(category, manifest, getattr(module, "load_package_dir", None))
    checks = {s["id"]: s for s in entry.get("detectable_scenarios") or []}

    results: list[CheckResult] = []
    for corpus_check_id, corpus_check in checks.items():
        bound = [c for c in cases if c.scenario_id == corpus_check_id]
        if not bound:
            continue
        detector_check = corpus_check["detector_check"]
        detector_fn: Callable[[dict], object] | None = module.DETECTORS.get(detector_check)
        if detector_fn is None:
            raise FixtureCorpusError(
                f"{category} corpus check {corpus_check_id!r} is labeled against detector "
                f"check {detector_check!r}, which skills/{category}/scripts/detector.py "
                f"does not implement"
            )

        coverage = [
            CoverageEntry(
                scenario_id=corpus_check_id,
                category=category,
                tier=Tier(corpus_check["tier"]),
                reason=corpus_check.get("reason", ""),
            )
        ]
        fixtures = [
            FixtureCase(
                case_id=c.case_id,
                scenario_id=c.scenario_id,
                category=category,
                is_vulnerable=c.is_vulnerable,
                sample=c.pkg,
            )
            for c in bound
        ]
        result = run_category(category, coverage, fixtures, lambda pkg, fn=detector_fn: bool(fn(pkg).detected))
        results.append(
            CheckResult(
                corpus_check=corpus_check_id,
                detector_check=detector_check,
                covers=corpus_check.get("covers", "full"),
                registry_ids=tuple(corpus_check.get("registry_ids") or []),
                true_positives=result.true_positives,
                false_positives=result.false_positives,
                false_negatives=result.false_negatives,
                true_negatives=result.true_negatives,
                case_verdicts=tuple((c.case_id, bool(detector_fn(c.pkg).detected), c.is_vulnerable) for c in bound),
            )
        )

    return CategoryCorpusResult(
        category=category,
        checks=tuple(results),
        f1_scope=str(entry.get("f1_scope") or "none"),
    )


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - operator CLI
    """``python3 detectors/fixture_loader.py AST03 AST04`` — print the corpus run."""
    import argparse

    parser = argparse.ArgumentParser(prog="detectors/fixture_loader.py")
    parser.add_argument("categories", nargs="*", default=[])
    args = parser.parse_args(argv)
    manifest = load_manifest()
    categories = args.categories or sorted(manifest.get("categories") or {})
    exit_code = 0
    for category in categories:
        entry = (manifest.get("categories") or {}).get(category) or {}
        if not (entry.get("detectable_scenarios") or []):
            print(f"{category}: declared-and-uncovered (empty detectable tier; no F1 by rule)")
            continue
        if not all(s.get("detector_check") for s in entry["detectable_scenarios"]):
            print(f"{category}: pending-detector (a labeled check names no detector_check)")
            continue
        result = run_corpus(category, manifest)
        print(f"{category}: f1_scope={result.f1_scope} cases={result.cases()} f1={result.f1():.3f}")
        for check in result.checks:
            flag = "OK " if check.discriminates else "!! "
            print(
                f"  {flag}{check.corpus_check} -> {check.detector_check} "
                f"[{check.covers}] tp={check.true_positives} fp={check.false_positives} "
                f"fn={check.false_negatives} tn={check.true_negatives} f1={check.f1:.3f}"
            )
            for case_id, predicted, vulnerable in check.case_verdicts:
                print(f"       {case_id}: predicted={predicted} labeled_vulnerable={vulnerable}")
            if not check.discriminates:
                exit_code = 1
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
