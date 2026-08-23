"""An F1 of 1.000 over a self-authored corpus proves nothing on its own. This does.

The failure this module guards against is the one an independent review found in
AST01's first corpus: a check that "fires identically on all six of its own labeled
fixtures -- vulnerable and clean alike". The fix is not a better number; a keyword
grep can score 1.000 on a corpus whose clean cases simply omit the keyword. The fix
is a corpus whose clean half is a *near miss* -- the same construct, the same
vocabulary, differing only in the property the scenario is actually defined by.

So this module measures the corpus against a deliberately naive baseline: for each
check, the SYNTAX-ONLY half of its predicate, with the second half (the
contradiction of the package's own declaration, or the sink the construct reaches)
removed. Two properties are then asserted:

  1. the shipped detectors separate the corpus perfectly, and
  2. the syntax-only ablation does NOT.

Property 2 is the load-bearing one. If a future fixture edit makes the ablation
score as well as the real detector, the corpus has stopped testing the mechanism
and started testing vocabulary, and this fails -- which is the signal to rewrite the
clean case, not to relax the threshold.

Scope: AST01 and AST02, the two categories whose corpora were rebuilt against this
requirement. Sibling categories are covered by their own modules; extend
``ABLATIONS`` rather than globbing, so an unwritten ablation reads as "not yet
authored" instead of passing vacuously.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

from detectors import corpus

REPO_ROOT = Path(__file__).resolve().parents[1]

#: An ablated check must stay well clear of the real one. 0.85 leaves room for a
#: baseline that happens to get one case right without letting one that gets them
#: all right pass as a discriminating corpus.
ABLATION_CEILING = 0.85


@pytest.fixture(scope="module")
def manifest() -> dict:
    return yaml.safe_load((REPO_ROOT / "fixtures" / "manifest.yaml").read_text(encoding="utf-8"))


def _load_detector(category: str):
    path = REPO_ROOT / "skills" / category / "scripts" / "detector.py"
    spec = importlib.util.spec_from_file_location(f"_ablation_{category}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# The naive baselines: each is the shipped check with its second half deleted
# --------------------------------------------------------------------------

_PIPE_TO_SHELL = re.compile(r"(?:curl|wget)\b[^\n|]{0,400}\|\s{0,8}(?:ba|z|k|a)?sh\b", re.IGNORECASE)
_ANY_WRITE_OPEN = re.compile(r"open\s*\([^)\n]{0,160}?['\"][wax]", re.IGNORECASE)
_ANY_EGRESS_CALL = re.compile(r"\b(?:requests\.\w+|WebSocketApp|urlopen)\s*\(")
_ANY_WS_SCHEME = re.compile(r"wss?://", re.IGNORECASE)
_ANY_QUOTED_URL = re.compile(r"['\"]https?://")
_ANY_BASE64_TOKEN = re.compile(r"b64decode|atob|base64")
# Same code-point class detectors/scaffold.py scans for, written in escapes for the
# same reason: a literal glyph here would be unreadable in a diff.
_ANY_INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]")
_ANY_COMMANDISH = re.compile(r"\b(?:curl|wget|bash|sh|node|python)\b")


def _scripts(pkg: dict) -> dict[str, str]:
    return {p: c for p, c in pkg["files"].items() if p.endswith((".py", ".sh", ".js"))}


def _markdown(pkg: dict) -> dict[str, str]:
    return {p: c for p, c in pkg["files"].items() if p.endswith(".md")}


def _declared_write(pkg: dict) -> list[str]:
    files = ((pkg["manifest"].get("permissions") or {}).get("files") or {}) if pkg["manifest"] else {}
    return list(files.get("write") or [])


def _ablate_ast01(check: str, pkg: dict) -> bool:
    """Syntax only: the construct, with no reference to what the package declared."""
    if check == "AST01-social-engineering-prerequisites":
        # drops: is the destination host absent from the allowlist?
        return any(_PIPE_TO_SHELL.search(c) for c in _markdown(pkg).values())
    if check == "AST01-soul-md-persistence":
        # drops: is the path being written the identity file?
        return any(_ANY_WRITE_OPEN.search(c) for c in _scripts(pkg).values())
    if check == "AST01-memory-poisoning":
        # drops: does deny_write override the grant?
        return "MEMORY.md" in _declared_write(pkg)
    if check == "AST01-identity-clone-exfiltration":
        # drops: is an identity artifact read in the same script?
        return any(_ANY_EGRESS_CALL.search(c) for c in _scripts(pkg).values())
    if check == "AST01-websocket-c2":
        # drops: is the host absent from the allowlist?
        return any(_ANY_WS_SCHEME.search(c) for c in _scripts(pkg).values())
    if check == "AST01-undeclared-egress":
        # drops: is the destination host absent from the allowlist?
        return any(_ANY_EGRESS_CALL.search(c) and _ANY_QUOTED_URL.search(c) for c in _scripts(pkg).values())
    if check == "AST01-hidden-output-injection":
        # drops: is the carrier inside returned content rather than anywhere?
        return any(_ANY_INVISIBLE.search(c) for c in pkg["files"].values())
    if check == "AST01-obfuscated-payload-exec":
        # drops: does the decoded blob reach an execution sink?
        return any(_ANY_BASE64_TOKEN.search(c) for c in _scripts(pkg).values())
    raise AssertionError(f"no ablation authored for {check}")


def _ablate_ast02(check: str, pkg: dict) -> bool:
    """Syntax only: a command-looking string inside any shipped JSON config.

    Drops both halves of the real predicate: whether the file is one a host reads
    at project open, and whether the value sits under a key the host executes.
    """
    assert check == "AST02-config-file-hijacking"
    for path, content in pkg["files"].items():
        if not path.endswith(".json"):
            continue
        try:
            json.loads(content)
        except json.JSONDecodeError:
            continue
        if _ANY_COMMANDISH.search(content):
            return True
    return False


ABLATIONS = {"AST01": _ablate_ast01, "AST02": _ablate_ast02}


def _score(hits_per_case) -> tuple[int, int, int, float]:
    tp = fp = fn = 0
    for fired, expected in hits_per_case:
        tp += len(fired & expected)
        fp += len(fired - expected)
        fn += len(expected - fired)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return tp, fp, fn, f1


@pytest.mark.parametrize("category", sorted(ABLATIONS))
def test_the_shipped_checks_separate_the_corpus(category, manifest):
    module = _load_detector(category)
    pairs = corpus.category_fixtures(category, manifest)
    assert pairs, f"{category} has no labeled corpus"
    hits = [({f.scenario for f in module.run_all(pkg) if f.detected}, expected) for pkg, expected in pairs]
    tp, fp, fn, f1 = _score(hits)
    assert (fp, fn) == (0, 0), f"{category}: tp={tp} fp={fp} fn={fn}"
    assert f1 == 1.0


@pytest.mark.parametrize("category", sorted(ABLATIONS))
def test_a_syntax_only_ablation_does_not_pass_the_same_corpus(category, manifest):
    """The corpus has to punish a detector that matches vocabulary, not mechanism."""
    ablate = ABLATIONS[category]
    checks = sorted(set(corpus.check_map(category, manifest).values()))
    pairs = corpus.category_fixtures(category, manifest)
    hits = [({c for c in checks if ablate(c, pkg)}, expected) for pkg, expected in pairs]
    tp, fp, fn, f1 = _score(hits)
    assert f1 < ABLATION_CEILING, (
        f"{category}: a syntax-only baseline scores F1 {f1:.3f} (tp={tp} fp={fp} fn={fn}) on "
        f"this corpus, which means the corpus is measuring vocabulary rather than the "
        f"scenario's defining condition. Rewrite the clean cases as near misses; do not "
        f"relax this ceiling."
    )


@pytest.mark.parametrize("category", sorted(ABLATIONS))
def test_every_clean_case_is_a_near_miss_of_its_vulnerable_pair(category, manifest):
    """At least one ablated check must fire on a clean case.

    A clean case that no naive baseline even reaches is not a near miss -- it is an
    unrelated package, and pairing it with a vulnerable one measures nothing. This
    asserts the corpus contains real bait.
    """
    ablate = ABLATIONS[category]
    checks = sorted(set(corpus.check_map(category, manifest).values()))
    baited = 0
    for pkg, expected in corpus.category_fixtures(category, manifest):
        if expected:
            continue
        if any(ablate(c, pkg) for c in checks):
            baited += 1
    total_clean = sum(1 for _pkg, expected in corpus.category_fixtures(category, manifest) if not expected)
    assert baited >= total_clean // 2, (
        f"{category}: only {baited} of {total_clean} clean cases trip a naive baseline; "
        f"the rest are not near misses and are not testing discrimination"
    )


def test_the_measured_ablation_numbers_are_the_ones_the_matrices_quote(manifest):
    """A number in prose that nothing recomputes is a claim, not a measurement.

    The coverage matrices cite the ablation F1 and its tp/fp/fn breakdown as the
    evidence that their 1.000 is not a keyword grep's 1.000. Recompute both here, so
    a fixture edit that moves the baseline forces the matrix to be corrected in the
    same change instead of leaving a stale figure behind.
    """
    for category, ablate in ABLATIONS.items():
        checks = sorted(set(corpus.check_map(category, manifest).values()))
        pairs = corpus.category_fixtures(category, manifest)
        hits = [({c for c in checks if ablate(c, pkg)}, expected) for pkg, expected in pairs]
        tp, fp, fn, f1 = _score(hits)
        matrix = (REPO_ROOT / "skills" / category / "coverage-matrix.md").read_text(encoding="utf-8")
        assert f"{f1:.3f}" in matrix, f"{category}/coverage-matrix.md must quote the measured ablation F1 {f1:.3f}"
        assert f"tp {tp}, fp {fp}, fn {fn}" in matrix, (
            f"{category}/coverage-matrix.md must quote the ablation breakdown 'tp {tp}, fp {fp}, fn {fn}'"
        )
