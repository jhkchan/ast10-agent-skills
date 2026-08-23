"""AST08 -- Poor Scanning detector.

Most of what this category names is exactly the kind of natural-language
scenario spec.md's own rejected-design-C note calls out ("the only design
that can plausibly reach F1 >= 0.80 on natural-language scenarios AST08
exists to describe") -- i.e. agent-judgable, not static-detectable. One
scenario is a genuine exception: the invisible-Unicode control the T-3.3
extraction run surfaced is a concrete, static, format-independent smuggling
signal that a scanner missing it would be "poor scanning" by definition.
It is declared static-detectable here and shares its detection mechanism
with AST04's own instance of the same control (see
`skills/AST04/scripts/detector.py`) while remaining its own function, its
own fixtures, and its own file per this category's package scope.

Interim scenario-tier declaration (T-3.3); superseded by T-1.3's registry and
T-3.1's authored `skills/AST08/coverage-matrix.md` once locked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

SCENARIO_TIERS: dict[str, str] = {
    "AST08-invisible-unicode-smuggling": "static-detectable",
    # Whether a described bypass narrative actually evades a *specific*
    # scanner's ruleset is a claim about that scanner's behavior, not
    # anything this package's own content can settle statically.
    "AST08-scan-evasion-narrative": "agent-judgable",
}

STATIC_DETECTABLE: set[str] = {
    s for s, tier in SCENARIO_TIERS.items() if tier == "static-detectable"
}


@dataclass
class Finding:
    scenario: str
    detected: bool
    evidence: str = ""


# Zero-width spaces/joiners and bidi control code points -- the same class the
# whitepaper extraction stripped 860 instances of from the source PDF.
# Explicit \uXXXX escapes on purpose: embedding the literal invisible glyphs
# in this file's own source would be exactly the smuggling risk this
# detector exists to catch, and would be silently unreadable in any diff.
_INVISIBLE_UNICODE_RE = re.compile(
    "[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]"
)


def detect_invisible_unicode_smuggling(pkg: dict) -> Finding:
    manifest_text = pkg.get("manifest", {}).get("description", "") or ""
    candidates = dict(pkg.get("files", {}))
    candidates["<manifest.description>"] = manifest_text
    for path, content in candidates.items():
        hits = _INVISIBLE_UNICODE_RE.findall(content)
        if hits:
            codepoints = sorted({f"U+{ord(c):04X}" for c in hits})
            return Finding(
                "AST08-invisible-unicode-smuggling",
                True,
                f"{path}: {len(hits)} invisible code point(s) {codepoints}",
            )
    return Finding(
        "AST08-invisible-unicode-smuggling",
        False,
        "no invisible Unicode control code points found",
    )


DETECTORS: dict[str, Callable[[dict], Finding]] = {
    "AST08-invisible-unicode-smuggling": detect_invisible_unicode_smuggling,
}


def run_all(pkg: dict) -> list[Finding]:
    return [fn(pkg) for fn in DETECTORS.values()]


def f1_report(fixtures: list[tuple[dict, set[str]]]) -> dict:
    if not STATIC_DETECTABLE:
        return {"status": "declared-and-uncovered", "f1": None}

    tp = fp = fn = 0
    for pkg, expected in fixtures:
        expected = expected & STATIC_DETECTABLE
        detected = {f.scenario for f in run_all(pkg) if f.detected}
        tp += len(detected & expected)
        fp += len(detected - expected)
        fn += len(expected - detected)

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (
        (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    )
    return {
        "status": "measured",
        "f1": f1,
        "precision": precision,
        "recall": recall,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }
