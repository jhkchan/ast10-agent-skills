"""detectors/scaffold.py — shared per-skill detector scaffolding.

Every ``skills/AST0X/scripts/detector.py`` module duplicated an identical
``Finding`` dataclass, ``STATIC_DETECTABLE`` derivation, ``run_all()``, and a
byte-identical ``f1_report()`` (code-review finding: reuse, HIGH). This
module is the single source of that scaffolding; each skill module now
imports it and exports only its own ``SCENARIO_TIERS`` + ``DETECTORS`` map
plus its own ``detect_*`` functions.

``f1_report``'s zero-denominator convention matches ``detectors/engine.py``'s
``run_category`` (0.0, not 1.0) rather than silently reporting a perfect F1
for a corpus where nothing was detected (code-review finding: correctness,
MEDIUM -- a category's own precision/recall must never default to "perfect"
just because tp+fp or tp+fn happened to be zero).

Also carries ``detect_invisible_unicode_smuggling``, the zero-width/bidi
control code point scan that was duplicated verbatim between AST04 and AST08
(code-review finding: reuse, MEDIUM) -- both skills now share the regex and
scan logic and supply only their own scenario id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass
class Finding:
    scenario: str
    detected: bool
    evidence: str = ""


def static_detectable(scenario_tiers: dict[str, str]) -> set[str]:
    """The static-detectable subset of a module's SCENARIO_TIERS."""
    return {s for s, tier in scenario_tiers.items() if tier == "static-detectable"}


def run_all(detectors: dict[str, Callable[[dict], Finding]], pkg: dict) -> list[Finding]:
    return [fn(pkg) for fn in detectors.values()]


def f1_report(
    static_detectable_scenarios: set[str],
    detectors: dict[str, Callable[[dict], Finding]],
    fixtures: list[tuple[dict, set[str]]] | None,
) -> dict:
    """Per-category F1 over the declared-detectable tier only (S-007, gate-4).

    ``fixtures`` is a list of (package, expected_detected_scenario_ids)
    pairs. A category whose declared-detectable tier is empty must never
    manufacture a number (S-003 / gate-4); it reports "declared-and-uncovered"
    instead.
    """
    if not static_detectable_scenarios:
        return {"status": "declared-and-uncovered", "f1": None}

    tp = fp = fn = 0
    for pkg, expected in fixtures or []:
        expected = expected & static_detectable_scenarios
        detected = {f.scenario for f in run_all(detectors, pkg) if f.detected}
        tp += len(detected & expected)
        fp += len(detected - expected)
        fn += len(expected - detected)

    # Zero-denominator precision/recall report 0.0, matching
    # detectors/engine.py's run_category -- a corpus where nothing was
    # detected must never default to a "perfect" 1.0 score.
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "status": "measured",
        "f1": f1,
        "precision": precision,
        "recall": recall,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


# --- shared AST04/AST08 detection: invisible-Unicode smuggling -------------
# Zero-width spaces/joiners and bidi control code points -- the same class the
# whitepaper extraction stripped 860 instances of from the source PDF.
# Explicit \uXXXX escapes on purpose: embedding the literal invisible glyphs
# in this file's own source would be exactly the smuggling risk this
# detector exists to catch, and would be silently unreadable in any diff.
INVISIBLE_UNICODE_RE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]")


def detect_invisible_unicode_smuggling(pkg: dict, scenario_id: str) -> Finding:
    """Scan a package's files (plus its manifest description) for invisible
    Unicode control code points. Shared by AST04 and AST08 -- each supplies
    only its own ``scenario_id`` so a code-point-range fix here can never
    leave one category's copy stale."""
    manifest_text = pkg.get("manifest", {}).get("description", "") or ""
    candidates = dict(pkg.get("files", {}))
    candidates["<manifest.description>"] = manifest_text
    for path, content in candidates.items():
        hits = INVISIBLE_UNICODE_RE.findall(content)
        if hits:
            codepoints = sorted({f"U+{ord(c):04X}" for c in hits})
            return Finding(
                scenario_id,
                True,
                f"{path}: {len(hits)} invisible code point(s) {codepoints}",
            )
    return Finding(scenario_id, False, "no invisible Unicode control code points found")
