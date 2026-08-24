#!/usr/bin/env python3
"""eval/generate_dashboard.py — rewrite the Results table in the judge dashboard.

Reads every scorecard under ``eval/scorecards/`` and regenerates the block
between the ``<!-- BEGIN:results -->`` / ``<!-- END:results -->`` markers in
``docs/skill-judge-dashboard.md``. Nothing else in the document is touched, so
the rubric, the ship rule and the provider roster stay hand-authored.

Two invariants make the generated table trustworthy:

1. **Nothing stored is believed.** The verdict and the grade are recomputed from
   ``aggregate.judgments`` via ``ship_floor.aggregate_verdict`` — the same
   function the ship gate calls. A scorecard whose stored ``mean``/``stdev``
   disagree with the recompute renders as ``BLOCKED`` with the reason shown,
   rather than rendering the stored numbers.
2. **An empty corpus renders as empty.** With no scorecards on disk the block
   is rewritten to the explicit "no judged run recorded yet" state with
   placeholder rows for every skill — never to a table that looks like a
   result. Publishing zeros, or omitting the table, would both read as a
   measurement that did not happen.

**Do not run this against a corpus scored under a superseded rule.** It calls the
live gate, so pointing it at `eval/scorecards/` (run 4, judged under the clause
`docs/adr/0006-confidence-bound-on-the-pooled-mean.md` retired on 2026-08-24)
would restate a published verdict in the words of a rule that never issued it —
which that record forbids in as many words. The committed Results table is
therefore frozen until run 5 replaces it; `--check` will report it out of date
and that report is expected, not a defect.
``tests/test_generate_dashboard.py::test_the_committed_results_table_is_run_4_under_the_rule_that_produced_it``
is what guards the table instead, by re-deriving every published verdict through
the current gate and failing if one has moved.

Usage::

    python3 eval/generate_dashboard.py            # rewrite in place
    python3 eval/generate_dashboard.py --check    # exit 1 if it would change
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:  # allow `python3 eval/generate_dashboard.py`
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ship_floor import (  # noqa: E402
    DIM_KEYS,
    FLOORS,
    aggregate_verdict,
)

SCORECARD_DIR = REPO_ROOT / "eval" / "scorecards"
DASHBOARD = REPO_ROOT / "docs" / "skill-judge-dashboard.md"

BEGIN = "<!-- BEGIN:results -->"
END = "<!-- END:results -->"

#: Rendered when no scorecard exists for a skill. Kept in sync with the
#: repository's own roster so a skill that is never judged still appears.
PLACEHOLDER_SKILLS: tuple[str, ...] = (
    "ast01-malicious-skills",
    "ast02-supply-chain-compromise",
    "ast03-over-privileged-skills",
    "ast04-insecure-metadata",
    "ast05-untrusted-external-instructions",
    "ast06-weak-isolation",
    "ast07-update-drift",
    "ast08-poor-scanning",
    "ast09-no-governance",
    "ast10-cross-platform-reuse",
    "advisory",
)

TABLE_HEADER = (
    "| Skill | Rounds | Mean | Mean − σ | Lowest dim (floor) | Grade | Verdict |\n"
    "| --- | ---: | ---: | ---: | --- | --- | --- |"
)

EMPTY_PREAMBLE = (
    "**No judged run recorded yet.** `eval/scorecards/` contains no scorecard files. "
    "Every row\nbelow is a placeholder showing the shape of a recorded result — not a "
    "measurement, not a\ngrade, and not a claim that any skill has been evaluated."
)


class ScorecardError(ValueError):
    """A scorecard file that cannot be read as a scorecard at all."""


def grade_of(mean: float) -> str:
    """Percentage-band grade over the 120-point rubric total."""
    if mean >= 108:
        return "A"
    if mean >= 96:
        return "B"
    if mean >= 84:
        return "C"
    if mean >= 72:
        return "D"
    return "F"


def load_scorecards(directory: Path = SCORECARD_DIR) -> list[dict[str, Any]]:
    """Every ``*.json`` in ``directory``, sorted by filename for stable output."""
    if not directory.is_dir():
        return []
    cards = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ScorecardError(f"{path.name}: not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ScorecardError(f"{path.name}: scorecard must be a JSON object")
        payload.setdefault("skill", path.stem)
        cards.append(payload)
    return cards


def _lowest_dimension(dim_means: dict[str, Any]) -> str:
    """The dimension furthest below (or closest to) its floor, as `D<n> x/floor`.

    Ranked by margin against the floor rather than by raw score, because a D7
    of 9 and a D1 of 9 are not comparable: one clears its floor of 8 and the
    other misses its floor of 17 by eight points.
    """
    present = [(d, dim_means[d]) for d in DIM_KEYS if isinstance(dim_means.get(d), (int, float))]
    if not present:
        return "—"
    dim, value = min(present, key=lambda pair: pair[1] - FLOORS[pair[0]])
    flag = "" if value >= FLOORS[dim] else " ⚠"
    return f"`{dim}` {value:g}/{FLOORS[dim]}{flag}"


def render_row(card: dict[str, Any]) -> str:
    skill = str(card.get("skill", "?"))
    aggregate = card.get("aggregate")
    verdict, why = aggregate_verdict(skill, aggregate if isinstance(aggregate, dict) else None)
    if not isinstance(aggregate, dict):
        aggregate = {}

    judgments = aggregate.get("judgments") or []
    rounds = len(judgments) or "—"

    # Recompute rather than read: a stored mean is a claim, the judgments are
    # the evidence. Where the two disagree the verdict is already BLOCKED and
    # the recomputed numbers are what the reader should see.
    if len(judgments) >= 2:
        mean = round(statistics.fmean(judgments), 1)
        stdev = round(statistics.stdev(judgments), 2)
        lower = round(mean - stdev, 1)
        mean_cell, lower_cell, grade = f"{mean:g}", f"{lower:g}", grade_of(mean)
    else:
        mean_cell = lower_cell = grade = "—"

    lowest = _lowest_dimension(aggregate.get("dim_means") or {})
    verdict_cell = verdict if verdict == "SHIP" else f"{verdict} — {why}" if why else verdict
    return f"| `{skill}` | {rounds} | {mean_cell} | {lower_cell} | {lowest} | {grade} | {verdict_cell} |"


def render_block(cards: list[dict[str, Any]]) -> str:
    """The full text that belongs between the BEGIN/END markers."""
    if not cards:
        rows = "\n".join(f"| `{skill}` | — | — | — | — | — | NOT YET JUDGED |" for skill in PLACEHOLDER_SKILLS)
        return f"{EMPTY_PREAMBLE}\n\n{TABLE_HEADER}\n{rows}"

    judged = {str(c.get("skill")) for c in cards}
    missing = [s for s in PLACEHOLDER_SKILLS if s not in judged]
    judged_rows = [render_row(card) for card in cards]
    rows = judged_rows + [f"| `{s}` | — | — | — | — | — | NOT YET JUDGED |" for s in missing]

    shipped = sum(1 for row in judged_rows if row.endswith("| SHIP |"))
    verb = "clears" if shipped == 1 else "clear"
    preamble = (
        f"**{len(cards)} of {len(PLACEHOLDER_SKILLS)} skills judged; {shipped} {verb} "
        "the ship rule.** Verdicts and grades below are recomputed from each scorecard's own "
        "`aggregate.judgments` by `ship_floor.aggregate_verdict`; stored verdicts are "
        "never copied. Unjudged skills keep their placeholder row rather than dropping "
        "out of the table."
    )
    return f"{preamble}\n\n{TABLE_HEADER}\n" + "\n".join(rows)


def rewrite(text: str, block: str) -> str:
    """Replace the marked region of ``text`` with ``block``."""
    start = text.find(BEGIN)
    end = text.find(END)
    if start == -1 or end == -1 or end < start:
        raise ScorecardError(
            f"dashboard is missing the {BEGIN} / {END} markers — refusing to guess where the results table belongs"
        )
    return text[: start + len(BEGIN)] + "\n" + block + "\n" + text[end:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eval/generate_dashboard.py",
        description="Rewrite the Results table in docs/skill-judge-dashboard.md.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the dashboard is out of date; write nothing",
    )
    parser.add_argument("--dashboard", default=str(DASHBOARD), help="path to the dashboard markdown")
    parser.add_argument("--scorecards", default=str(SCORECARD_DIR), help="path to the scorecard directory")
    args = parser.parse_args(argv)

    dashboard = Path(args.dashboard)
    cards = load_scorecards(Path(args.scorecards))
    current = dashboard.read_text(encoding="utf-8")
    updated = rewrite(current, render_block(cards))

    if args.check:
        if updated != current:
            print(f"{dashboard}: out of date — run eval/generate_dashboard.py")
            return 1
        print(f"{dashboard}: up to date ({len(cards)} scorecard(s))")
        return 0

    if updated != current:
        dashboard.write_text(updated, encoding="utf-8")
        print(f"{dashboard}: rewritten from {len(cards)} scorecard(s)")
    else:
        print(f"{dashboard}: unchanged ({len(cards)} scorecard(s))")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
