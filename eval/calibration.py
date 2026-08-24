#!/usr/bin/env python3
"""eval/calibration.py — measure the judge PANEL, not the skills.

Every other tool in `eval/` reads a scorecard to ask "how good is this skill?".
This one reads the same files to ask the prior question: **how much of the
recorded spread is the skill, and how much is the instrument?**

It computes two things from `eval/scorecards/*.json` and nothing else:

1. **Per-provider bias** — each judge's mean over every judgment it cast,
   against the pooled mean of the whole panel. A judge that scores every skill
   twelve points high is not adding information about any skill; it is adding a
   constant.
2. **Per-skill dispersion** — the sigma `scripts/ship_floor.py` divides by, next
   to the two candidate bounds: the locked `mean − σ` and the textbook standard
   error of the mean, `mean − σ/√n`.

Why this file exists rather than a paragraph of numbers in a document:
`docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md` argues that the
shipped lower bound is the wrong statistic, and an argument of that kind is only
worth as much as its arithmetic. Transcribed numbers rot silently — the first
draft of the dashboard's calibration note carried a `nova-pro` bias of −7.9 and
a 20.1-point spread against scorecards that say −5.4 and 17.9, and nothing on
disk could tell the reader which was true. Every figure the ADR quotes is
printed by this script, and `tests/test_calibration.py` fails if the two drift.

This script computes **diagnostics only**. It deliberately does not evaluate any
candidate replacement rule against the recorded data, and it changes no gate
constant: `ship_floor.POOLED_TARGET` and `ship_floor.POOLED_LOWER_BOUND` are
imported here purely so the report can state what is currently in force. A bar
retuned against the data it is about to judge is not a bar — see the ADR.

Usage::

    python3 eval/calibration.py                  # print the tables
    python3 eval/calibration.py --json           # same figures, machine-readable
    python3 eval/calibration.py --scorecards DIR # point at another corpus
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:  # allow `python3 eval/calibration.py`
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ship_floor import POOLED_LOWER_BOUND, POOLED_TARGET  # noqa: E402

SCORECARD_DIR = REPO_ROOT / "eval" / "scorecards"

#: The per-judgment sigma `scripts/ship_floor.py` records as its calibration
#: basis, quoted from that file's own comment. Not a threshold and not used in
#: any comparison here — it is printed so the report can show the gap between
#: the sigma the rule assumes and the sigma this panel produces.
CALIBRATION_SIGMA = 3.3

#: The rubric total. Used only to express a required mean as a percentage.
RUBRIC_MAX = 120


class ScorecardError(ValueError):
    """A file under the scorecard directory that cannot be read as a scorecard."""


@dataclass(frozen=True)
class Judgment:
    """One judge's total for one skill on one round."""

    skill: str
    provider: str
    round_index: int
    total: float


def load_judgments(directory: Path = SCORECARD_DIR) -> list[Judgment]:
    """Every individual judgment in every scorecard, flattened.

    ``round_index`` is derived by counting each provider's own occurrences
    within a skill rather than by slicing the list into fixed-size blocks: the
    runner happens to write judgments provider-cycling, but a scorecard with a
    provider missing from one round would make block-slicing attribute rounds to
    the wrong judge, and silently.
    """
    if not directory.is_dir():
        return []
    out: list[Judgment] = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ScorecardError(f"{path.name}: not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ScorecardError(f"{path.name}: scorecard must be a JSON object")
        skill = str(payload.get("skill") or path.stem)
        seen: dict[str, int] = defaultdict(int)
        for row in payload.get("judgments") or []:
            if not isinstance(row, dict):
                raise ScorecardError(f"{path.name}: judgment entries must be objects")
            provider = str(row.get("provider") or "<unnamed>")
            total = row.get("total")
            if not isinstance(total, (int, float)):
                raise ScorecardError(f"{path.name}: judgment from {provider!r} has no numeric total")
            out.append(Judgment(skill, provider, seen[provider], float(total)))
            seen[provider] += 1
    return out


def pooled_mean(judgments: list[Judgment]) -> float:
    """The mean over every judgment on the panel — the reference for bias.

    Pooled over judgments, not averaged over provider means. The two agree
    exactly when the design is balanced (every judge scores every skill the same
    number of times), which this repo's runs are; they diverge when it is not,
    and in that case the pooled mean is the honest description of what was
    actually measured.
    """
    if not judgments:
        raise ScorecardError("no judgments to pool — is eval/scorecards/ empty?")
    return statistics.fmean(j.total for j in judgments)


def provider_bias(judgments: list[Judgment]) -> list[dict[str, Any]]:
    """Per-judge mean, bias against the pooled mean, and round-to-round spread.

    The round spread is the load-bearing column. A judge whose three independent
    rounds land within a point or two of each other, yet sits ten points off the
    panel, is not noisy — it is calibrated differently, and pooling it with the
    others inflates sigma by a constant that has nothing to do with the skill.
    """
    reference = pooled_mean(judgments)
    by_provider: dict[str, list[Judgment]] = defaultdict(list)
    for j in judgments:
        by_provider[j.provider].append(j)

    rows = []
    for provider, rows_for_provider in by_provider.items():
        totals = [j.total for j in rows_for_provider]
        by_round: dict[int, list[float]] = defaultdict(list)
        for j in rows_for_provider:
            by_round[j.round_index].append(j.total)
        round_means = [round(statistics.fmean(by_round[r]), 1) for r in sorted(by_round)]
        rows.append(
            {
                "provider": provider,
                "n": len(totals),
                "mean": round(statistics.fmean(totals), 1),
                "bias": round(statistics.fmean(totals) - reference, 1),
                "round_means": round_means,
                "round_spread": round(max(round_means) - min(round_means), 1) if round_means else 0.0,
            }
        )
    return sorted(rows, key=lambda r: -r["mean"])


def skill_dispersion(judgments: list[Judgment]) -> list[dict[str, Any]]:
    """Per-skill mean, sigma, and the two candidate lower bounds side by side.

    ``lower_bound`` is what `ship_floor.aggregate_verdict` gates on today
    (``mean − σ``). ``sem_bound`` is ``mean − σ/√n``, the uncertainty of the
    mean itself. Both are printed; neither is applied. Deciding between them on
    the strength of this table is precisely the move the ADR forbids.
    """
    by_skill: dict[str, list[float]] = defaultdict(list)
    for j in judgments:
        by_skill[j.skill].append(j.total)

    rows = []
    for skill, totals in sorted(by_skill.items()):
        if len(totals) < 2:
            raise ScorecardError(f"{skill}: a sigma needs at least two judgments, got {len(totals)}")
        # Round mean and sigma FIRST, then derive the bounds from the rounded
        # pair. That is what `ship_floor.pooled_stats` does, for the reason its
        # docstring gives: the published numbers must be the numbers a reader
        # recomputing by hand lands on. Deriving from the unrounded values here
        # instead would put this table 0.1 away from the scorecards on two of
        # eleven skills, and a reader would have no way to know which was right.
        mean = round(statistics.fmean(totals), 1)
        sigma = round(statistics.stdev(totals), 2)
        rows.append(
            {
                "skill": skill,
                "n": len(totals),
                "mean": mean,
                "sigma": sigma,
                "lower_bound": round(mean - sigma, 1),
                "sem_bound": round(mean - sigma / math.sqrt(len(totals)), 1),
            }
        )
    return rows


def panel_summary(judgments: list[Judgment]) -> dict[str, Any]:
    """Panel-level figures: the spread, the sigma range, and the bar it implies.

    ``implied_mean_bar_*`` is arithmetic on the locked rule, not a proposal:
    ``mean − σ ≥ POOLED_LOWER_BOUND`` is the same constraint as
    ``mean ≥ POOLED_LOWER_BOUND + σ``, so the sigma a panel produces sets the
    mean the rule actually demands. Printing it makes visible that the effective
    bar moved when the panel widened, without anyone editing a constant.
    """
    biases = provider_bias(judgments)
    dispersion = skill_dispersion(judgments)
    sigmas = [row["sigma"] for row in dispersion]
    return {
        "n_judgments": len(judgments),
        "n_skills": len(dispersion),
        "n_providers": len(biases),
        "pooled_mean": round(pooled_mean(judgments), 1),
        "bias_spread": round(max(r["mean"] for r in biases) - min(r["mean"] for r in biases), 1),
        "max_round_spread": round(max(r["round_spread"] for r in biases), 1),
        "sigma_min": min(sigmas),
        "sigma_max": max(sigmas),
        "sigma_median": round(statistics.median(sigmas), 2),
        "calibration_sigma": CALIBRATION_SIGMA,
        "pooled_target": POOLED_TARGET,
        "pooled_lower_bound": POOLED_LOWER_BOUND,
        "implied_mean_bar_min": round(POOLED_LOWER_BOUND + min(sigmas), 1),
        "implied_mean_bar_max": round(POOLED_LOWER_BOUND + max(sigmas), 1),
        "target_pct": round(100 * POOLED_TARGET / RUBRIC_MAX, 1),
        "implied_pct_min": round(100 * (POOLED_LOWER_BOUND + min(sigmas)) / RUBRIC_MAX, 1),
        "implied_pct_max": round(100 * (POOLED_LOWER_BOUND + max(sigmas)) / RUBRIC_MAX, 1),
    }


def report(judgments: list[Judgment]) -> dict[str, Any]:
    """Everything the printed tables show, as plain data."""
    return {
        "summary": panel_summary(judgments),
        "providers": provider_bias(judgments),
        "skills": skill_dispersion(judgments),
    }


def format_report(data: dict[str, Any]) -> str:
    """The human-readable tables. Column widths fixed so output diffs cleanly."""
    s = data["summary"]
    lines: list[str] = []
    lines.append(
        f"Panel: {s['n_providers']} providers x {s['n_skills']} skills = "
        f"{s['n_judgments']} judgments, pooled mean {s['pooled_mean']}"
    )
    lines.append("")
    lines.append("Per-provider bias (mean over that judge's judgments, vs the pooled mean)")
    lines.append(f"  {'provider':<32} {'n':>4} {'mean':>7} {'bias':>7}  round means")
    for row in data["providers"]:
        rounds = " / ".join(f"{m:g}" for m in row["round_means"])
        lines.append(f"  {row['provider']:<32} {row['n']:>4} {row['mean']:>7.1f} {row['bias']:>+7.1f}  {rounds}")
    lines.append("")
    lines.append(
        f"  Between-judge spread: {s['bias_spread']} points. "
        f"Largest within-judge round-to-round spread: {s['max_round_spread']} points."
    )
    lines.append("")
    lines.append("Per-skill dispersion (sigma over pooled judgments; both bounds shown, neither applied)")
    lines.append(f"  {'skill':<12} {'n':>4} {'mean':>7} {'sigma':>7} {'mean-sigma':>11} {'mean-sigma/sqrt(n)':>20}")
    for row in data["skills"]:
        lines.append(
            f"  {row['skill']:<12} {row['n']:>4} {row['mean']:>7.1f} {row['sigma']:>7.2f} "
            f"{row['lower_bound']:>11.1f} {row['sem_bound']:>20.1f}"
        )
    lines.append("")
    lines.append(
        f"  ship_floor.py was calibrated at a per-judgment sigma of {s['calibration_sigma']}; "
        f"this panel produces {s['sigma_min']}-{s['sigma_max']} (median {s['sigma_median']})."
    )
    lines.append(
        f"  mean - sigma >= {s['pooled_lower_bound']} is the same constraint as "
        f"mean >= {s['pooled_lower_bound']} + sigma, so at this panel's sigma the locked rule "
        f"demands a mean of {s['implied_mean_bar_min']}-{s['implied_mean_bar_max']} "
        f"({s['implied_pct_min']}%-{s['implied_pct_max']}% of {RUBRIC_MAX}), "
        f"not the {s['pooled_target']} ({s['target_pct']}%) it names as the target."
    )
    lines.append("")
    lines.append("  Diagnostics only. No gate constant is read from this file and none is changed by it;")
    lines.append("  see docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eval/calibration.py",
        description="Per-provider bias and per-skill sigma over eval/scorecards/*.json.",
    )
    parser.add_argument("--scorecards", default=str(SCORECARD_DIR), help="scorecard directory to read")
    parser.add_argument("--json", action="store_true", help="emit the figures as JSON instead of tables")
    args = parser.parse_args(argv)

    judgments = load_judgments(Path(args.scorecards))
    if not judgments:
        print(f"{args.scorecards}: no judgments recorded — nothing to calibrate")
        return 0

    data = report(judgments)
    print(json.dumps(data, indent=2) if args.json else format_report(data))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
