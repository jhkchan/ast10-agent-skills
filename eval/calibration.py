#!/usr/bin/env python3
"""eval/calibration.py — measure the judge PANEL, not the skills.

Every other tool in `eval/` reads a scorecard to ask "how good is this skill?".
This one reads the same files to ask the prior question: **how much of the
recorded spread is the skill, and how much is the instrument?**

It computes three things from `eval/scorecards/*.json` and nothing else:

1. **Per-provider bias** — each judge's mean over every judgment it cast,
   against the pooled mean of the whole panel. A judge that scores every skill
   twelve points high is not adding information about any skill; it is adding a
   constant.
2. **Per-skill dispersion** — the sigma `scripts/ship_floor.py` divides by, next
   to the two candidate bounds: the locked `mean − σ` and the textbook standard
   error of the mean, `mean − σ/√n`.
3. **Per-provider judge quality** — whether a judge is *measuring* at all.
   Bias is a judge scoring the wrong number; this is a judge emitting a
   placeholder. Four signals, each with a written-down threshold:
   discrimination (distinct values used, and variance of its scores across
   skills), granularity (how much of its output is rounded to multiples of
   five), saturation (how often it returns a dimension's maximum, or the full
   120), and self-consistency (its round-to-round spread on one skill). A judge
   that fails discrimination is printed as **NON-DISCRIMINATING**.

A flagged judge is **not** dropped from any pooled figure here. The standing
doctrine in this repository is declare-and-record: the report prints the pooled
numbers with *and* without the flagged judges side by side so a reader sees the
size of the effect, `eval/judge-quality.json` carries the same verdicts in
machine-readable form, and whether a judge stops binding is a human decision
that needs its own ADR. A tool that quietly filtered the panel would be making
that decision and leaving no record — which is the failure shape this whole
repository is about.

Why this file exists rather than a paragraph of numbers in a document:
`docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md` argues that the
shipped lower bound is the wrong statistic, and an argument of that kind is only
worth as much as its arithmetic. Transcribed numbers rot silently — the first
draft of the dashboard's calibration note carried a `nova-pro` bias of −7.9 and
a 20.1-point spread against scorecards that say −5.4 and 17.9, and nothing on
disk could tell the reader which was true. Every figure the ADR quotes is
printed by this script, and `tests/test_calibration.py` fails if the two drift.

This script computes **diagnostics only**. It evaluates no candidate rule against
the recorded data and it changes no gate constant. Three constants are imported
purely so the report can state what bar applies and what bar used to:
`ship_floor.POOLED_TARGET` and `ship_floor.CONFIDENCE_K` are the rule in force
after `docs/adr/0006-confidence-bound-on-the-pooled-mean.md`, and
`ship_floor.POOLED_LOWER_BOUND` is the constant that rule retired — kept here
because ADR-0005's implied-mean-bar figures are arithmetic on it, and a record
whose arithmetic can no longer be re-derived is folklore. A bar retuned against
the data it is about to judge is not a bar; ADR-0006 is the one change the gate
has taken and its constant was fixed before the run it judges — see both ADRs.

Usage::

    python3 eval/calibration.py                  # print the tables
    python3 eval/calibration.py --json           # same figures, machine-readable
    python3 eval/calibration.py --scorecards DIR # point at another corpus
    python3 eval/calibration.py --no-emit        # skip rewriting eval/judge-quality.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:  # allow `python3 eval/calibration.py`
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ship_floor import CONFIDENCE_K, POOLED_LOWER_BOUND, POOLED_TARGET  # noqa: E402

SCORECARD_DIR = REPO_ROOT / "eval" / "scorecards"

#: Where the machine-readable judge-quality verdicts are written. Committed, so
#: a reviewer reading a diff sees a judge's verdict change without running
#: anything, and `tests/test_judge_quality.py` fails if the file drifts from
#: what the recorded scorecards produce.
JUDGE_QUALITY_PATH = REPO_ROOT / "eval" / "judge-quality.json"

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
    """One judge's total for one skill on one round, and its dimension scores.

    ``scores`` is optional and defaults to empty. The bias and dispersion tables
    need only ``total``, and a corpus that records nothing else (a hand-written
    fixture, an older scorecard) must still calibrate; the judge-quality
    diagnostics report their dimension-level signals as ``None`` for such a
    provider rather than inventing them. ``compare=False`` keeps the mapping out
    of the generated ``__eq__``/``__hash__``, so a frozen record stays hashable.
    """

    skill: str
    provider: str
    round_index: int
    total: float
    scores: dict[str, float] = field(default_factory=dict, compare=False)


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
            out.append(Judgment(skill, provider, seen[provider], float(total), _dimension_scores(path, provider, row)))
            seen[provider] += 1
    return out


def _dimension_scores(path: Path, provider: str, row: dict[str, Any]) -> dict[str, float]:
    """The judgment's per-dimension scores, or ``{}`` when it recorded none.

    A present-but-malformed ``scores`` block is an error rather than an empty
    dict: silently reading it as "this judge recorded no dimensions" would make
    a corrupt scorecard look exactly like an old one, and the judge-quality
    verdicts below turn on that distinction.
    """
    raw = row.get("scores")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ScorecardError(f"{path.name}: judgment from {provider!r} has a non-object 'scores'")
    scores: dict[str, float] = {}
    for dimension, value in raw.items():
        if not isinstance(value, (int, float)):
            raise ScorecardError(f"{path.name}: {provider!r} scored {dimension} as {value!r}, which is not a number")
        scores[str(dimension)] = float(value)
    return scores


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


def _round_means(rows_for_provider: list[Judgment]) -> list[float]:
    """One judge's mean per round, in round order, rounded to a tenth."""
    by_round: dict[int, list[float]] = defaultdict(list)
    for j in rows_for_provider:
        by_round[j.round_index].append(j.total)
    return [round(statistics.fmean(by_round[r]), 1) for r in sorted(by_round)]


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
        round_means = _round_means(rows_for_provider)
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

    ``sem_bound`` is ``mean − σ/√n``, the uncertainty of the mean itself, and
    since ADR-0006 it is the shape `ship_floor.aggregate_verdict` gates on — as
    ``ci_lower``, measured against ``POOLED_TARGET`` rather than against the
    retired 105. ``lower_bound`` (``mean − σ``) is what the gate used through run
    4 and is kept because ADR-0005's whole argument is arithmetic on it. Both are
    printed; neither is applied here. This table gates nothing, and choosing
    between the two columns on the strength of it — rather than in a record
    written before the run it judges — is precisely the move ADR-0005 forbids and
    ADR-0006 avoided.
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
                # Rounded exactly as `ship_floor.pooled_stats` rounds `ci_lower`:
                # sem to two places first, then the subtraction. Deriving from
                # the unrounded sem instead puts this column 0.1 away from the
                # gate on AST10's run-3 figures, and a diagnostic that disagrees
                # with the rule it is diagnosing is worse than no diagnostic.
                "sem_bound": round(mean - CONFIDENCE_K * round(sigma / math.sqrt(len(totals)), 2), 1),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Judge quality: is this judge measuring, or emitting a placeholder?
# ---------------------------------------------------------------------------
#
# Bias asks whether a judge's number is in the right place. These signals ask
# the prior question — whether the number is a measurement at all. The panel
# recorded in eval/scorecards-run2/ contains a judge (`bedrock/qwen3-235b`) that
# returned exactly 120.0 on all eleven skills, from three distinct values, every
# one of them a multiple of five and every one of them a dimension's maximum. No
# bias figure can express that: its bias of +10.8 reads as "lenient", when what
# it actually did was decline to rank anything. Averaging it with five judges
# that did rank things adds a constant to every skill and widens every sigma,
# and the sigma is what the ship rule subtracts.
#
# That judge is no longer flat. Run 3 (eval/scorecards/) sent the rubric's own
# bands and it now varies and ranks, coming out COARSE rather than
# NON-DISCRIMINATING. The rule below is unchanged and still fires on the run-2
# corpus, which is what keeps "nobody is flagged" readable as a repair rather
# than as a relaxed threshold. Every "Measured:" line in this section is that
# run-2 panel — the evidence available when each threshold was written, kept as
# a record of the margin rather than refreshed into a moving target.
#
# Every threshold below is stated as a constant with its derivation, for two
# reasons. A threshold chosen after seeing which judge it catches is not a
# threshold, it is a name for that judge — so each is anchored to the rubric or
# to chance, and the measured panel values are recorded next to it as evidence
# of the margin rather than as the source of the number. And a future run has a
# different panel: the rule has to be readable by someone deciding whether it
# still applies.

#: A judge must use at least this many distinct dimension values across its
#: whole run. Derived from the rubric, not from the data: every dimension in
#: `vendor/skill-judge/SKILL.md` defines exactly FOUR score bands (D1's are
#: 0-5 / 6-10 / 11-15 / 16-20). A judge emitting fewer distinct values than a
#: single dimension has bands cannot express that dimension's scale even once,
#: let alone eight of them over eleven skills. Measured: qwen3-235b 3, sonnet 8,
#: nova-pro 11, gpt-oss 12, deepseek 13.
MIN_DISTINCT_DIMENSION_VALUES = 4

#: A judge's per-skill mean totals must vary by at least this much (population
#: standard deviation, in points) across the skills it judged. Deliberately
#: extreme — this is not "this judge agrees too much with itself", it is "this
#: judge returned one number". For scale: the run-2 panel places its skills
#: 105.4 to 112.8 apart, the grade bands in the dashboard are twelve points
#: wide, and the ship rule turns on three-point differences. A judge whose every
#: per-skill mean fits inside a one-point window has resolved that whole span to
#: a single verdict. Measured: qwen3-235b 0.00, sonnet 2.23, glm 2.30, gpt-oss
#: 2.41, deepseek 5.46, nova-pro 8.61 — nothing sits near the line, which is the
#: point. The lowest anyone has measured under the rubric-grounded prompt is
#: 1.38, still clear of the floor and no longer the same judge's zero.
#: The floor is written down now so that a FUTURE flat judge is caught by a rule
#: that predates it.
DISCRIMINATION_SD_FLOOR = 1.0

#: Discrimination needs at least this many skills to be a question. One skill
#: judged three times says nothing about ranking, and a variance of zero over a
#: single skill is not evidence of anything.
MIN_SKILLS_FOR_DISCRIMINATION = 2

#: Flag a judge whose dimension scores are multiples of five this often. A judge
#: drawing uniformly at random from each dimension's range would hit a multiple
#: of five about 25% of the time (5 of 21 values on D1, 4 of 16 on the six
#: 15-point dimensions, 3 of 11 on D7 — see `multiple_of_five_chance_rate`), so
#: 0.60 is roughly 2.4x chance and cannot be reached by accident. Rounding to
#: fives on a 15-point scale collapses it to four usable values: that is a
#: placeholder, not a measurement. Measured: qwen3-235b 100%, deepseek 36%,
#: nova-pro 23%, gpt-oss 9%, glm 6%, sonnet 0%.
GRANULARITY_CEILING = 0.60

#: Flag a judge that returns a dimension's maximum on this share of its
#: dimension scores. The rubric's top bands are written as reserved language
#: ("Pure knowledge delta — every paragraph earns its tokens", "Masterful
#: application"), so a judge awarding them to the majority of what it sees has
#: merged the top band with everything below it and can no longer say "better
#: than most". Half is the point at which the ceiling becomes the mode.
#: Measured: qwen3-235b 100%, deepseek 35%, nova-pro 11%, gpt-oss 8%, glm 6%,
#: sonnet 0%.
SATURATION_DIM_MAX_CEILING = 0.50

#: Same argument one level up: the share of whole judgments that come back at
#: the rubric total. A perfect 120 is the rubric's strongest available claim;
#: returning it more than half the time makes it the default.
#: Measured: qwen3-235b 100%, deepseek 21%, nova-pro 6%, everyone else 0%.
SATURATION_FULL_TOTAL_CEILING = 0.50

#: The verdicts, worst first. NON-DISCRIMINATING is the one with consequences:
#: it says the judge's output carries no information about which skill is
#: better, so pooling it moves every mean and every sigma for no gain in
#: knowledge. COARSE is advisory — the judge does rank skills, but reports the
#: ranking on a scale coarser than the rubric's. Neither verdict excludes
#: anybody from anything here; see this module's docstring.
VERDICT_NON_DISCRIMINATING = "NON-DISCRIMINATING"
VERDICT_COARSE = "COARSE"
VERDICT_DISCRIMINATING = "DISCRIMINATING"
VERDICT_INSUFFICIENT_DATA = "INSUFFICIENT-DATA"

#: The pinned rubric's per-dimension maxima, as vendored. Saturation is "how
#: often did this judge return the top of the scale", so it has to know where
#: the top is; the authority is the rubric the judges were actually sent, read
#: through `scripts.judge_harness.load_rubric`, and this table is the fallback
#: when that read is unavailable. It is a fallback and not the source precisely
#: so that the two can be compared — `tests/test_judge_quality.py` asserts they
#: agree, which is what stops this copy rotting silently.
FALLBACK_DIMENSION_MAXIMA: dict[str, int] = {
    "D1": 20,
    "D2": 15,
    "D3": 15,
    "D4": 15,
    "D5": 15,
    "D6": 15,
    "D7": 10,
    "D8": 15,
}


def dimension_maxima() -> dict[str, int]:
    """Per-dimension maxima from the pinned rubric, falling back to the vendored table.

    The fallback is not laziness about the pin. Enforcing
    `RUBRIC_CONTENT_SHA256` is `scripts/judge_harness.py`'s job, at the moment a
    prompt is built and a live score is produced. This script reads a corpus
    that was scored months ago: refusing to describe a recorded run because
    today's rubric bytes moved would destroy exactly the audit trail it exists
    to read, and would make the tool fail hardest at the moment it is most
    needed — the moment the instrument changed.
    """
    try:
        from scripts.judge_harness import load_rubric

        return dict(load_rubric().maxima)
    except Exception:  # rubric missing, re-vendored, or pin moved: see docstring
        return dict(FALLBACK_DIMENSION_MAXIMA)


def multiple_of_five_chance_rate(maxima: Mapping[str, int]) -> float:
    """Share of multiples of five a judge picking uniformly at random would emit.

    Computed rather than asserted so that the justification for
    `GRANULARITY_CEILING` survives a re-weighted rubric: if a future rubric
    scores every dimension out of 10, chance rises and this number says so.
    """
    if not maxima:
        return 0.0
    return statistics.fmean(len(range(0, m + 1, 5)) / (m + 1) for m in maxima.values())


def _fraction(hits: int, total: int) -> float | None:
    return None if total == 0 else round(hits / total, 3)


def provider_quality(judgments: list[Judgment], maxima: Mapping[str, int] | None = None) -> list[dict[str, Any]]:
    """One diagnostic row per judge: the four signals, the verdict, and its reasons.

    Dimension-level signals are ``None`` for a judge whose scorecards recorded
    only totals — absent, not zero. A zero would read as "this judge never
    rounded to five", which is a claim the data does not support.
    """
    maxima = dict(maxima) if maxima is not None else dimension_maxima()
    rubric_total = sum(maxima.values()) or RUBRIC_MAX

    by_provider: dict[str, list[Judgment]] = defaultdict(list)
    for j in judgments:
        by_provider[j.provider].append(j)

    rows = []
    for provider, rows_for_provider in by_provider.items():
        by_skill: dict[str, list[float]] = defaultdict(list)
        for j in rows_for_provider:
            by_skill[j.skill].append(j.total)

        # Discrimination. Population sigma, not sample: these eleven skills are
        # the population being ranked, not a draw from some larger set of
        # skills, and the question is whether this judge separated the things in
        # front of it.
        skill_means = [statistics.fmean(totals) for totals in by_skill.values()]
        enough_skills = len(skill_means) >= MIN_SKILLS_FOR_DISCRIMINATION
        across_sd = round(statistics.pstdev(skill_means), 2) if enough_skills else None
        across_var = round(statistics.pvariance(skill_means), 2) if enough_skills else None

        dim_scores = [(d, v) for j in rows_for_provider for d, v in j.scores.items()]
        values = sorted({v for _, v in dim_scores})
        gradeable = [(d, v) for d, v in dim_scores if d in maxima]

        # Self-consistency: the same judge, the same skill, a fresh round.
        within = [max(totals) - min(totals) for totals in by_skill.values()]
        within_sds = [statistics.stdev(totals) for totals in by_skill.values() if len(totals) > 1]
        round_means = _round_means(rows_for_provider)

        row: dict[str, Any] = {
            "provider": provider,
            "n_judgments": len(rows_for_provider),
            "n_skills": len(by_skill),
            "n_dimension_scores": len(dim_scores),
            "discrimination": {
                "distinct_dimension_values": len(values) if dim_scores else None,
                "dimension_values": values,
                "across_skill_sd": across_sd,
                "across_skill_variance": across_var,
                "skill_mean_min": round(min(skill_means), 1),
                "skill_mean_max": round(max(skill_means), 1),
                "skill_mean_range": round(max(skill_means) - min(skill_means), 1),
            },
            "granularity": {
                "multiple_of_five_rate": _fraction(sum(1 for _, v in dim_scores if v % 5 == 0), len(dim_scores)),
                "chance_rate": round(multiple_of_five_chance_rate(maxima), 3),
            },
            "saturation": {
                "dimension_max_rate": _fraction(sum(1 for d, v in gradeable if v >= maxima[d]), len(gradeable)),
                "full_total_rate": _fraction(
                    sum(1 for j in rows_for_provider if j.total >= rubric_total), len(rows_for_provider)
                ),
                "rubric_total": rubric_total,
            },
            "self_consistency": {
                "round_means": round_means,
                "round_spread": round(max(round_means) - min(round_means), 1) if round_means else 0.0,
                "same_skill_spread_mean": round(statistics.fmean(within), 2) if within else 0.0,
                "same_skill_spread_max": round(max(within), 1) if within else 0.0,
                "within_skill_sd": round(statistics.fmean(within_sds), 2) if within_sds else None,
            },
        }
        row["verdict"], row["reasons"] = _verdict(row)
        rows.append(row)

    # Worst first: a reader scanning the table should hit the judges that need a
    # decision before the ones that do not.
    order = {
        VERDICT_NON_DISCRIMINATING: 0,
        VERDICT_COARSE: 1,
        VERDICT_INSUFFICIENT_DATA: 2,
        VERDICT_DISCRIMINATING: 3,
    }
    return sorted(rows, key=lambda r: (order.get(r["verdict"], 9), r["provider"]))


def _verdict(row: dict[str, Any]) -> tuple[str, list[str]]:
    """Apply the thresholds above to one provider's signals.

    Discrimination alone decides NON-DISCRIMINATING, because that is what the
    verdict *means*: a judge that returns one number is ranking nothing whatever
    its granularity. Granularity and saturation are reported alongside because
    they explain the mechanism — and because a judge can be coarse without being
    flat, which is a different and much milder problem.
    """
    disc, gran, sat = row["discrimination"], row["granularity"], row["saturation"]
    reasons: list[str] = []

    if row["n_skills"] < MIN_SKILLS_FOR_DISCRIMINATION:
        return VERDICT_INSUFFICIENT_DATA, [
            f"judged {row['n_skills']} skill(s); discrimination needs at least "
            f"{MIN_SKILLS_FOR_DISCRIMINATION} to be a question"
        ]

    across_sd, distinct = disc["across_skill_sd"], disc["distinct_dimension_values"]
    flat = across_sd is not None and across_sd < DISCRIMINATION_SD_FLOOR
    few_values = distinct is not None and distinct < MIN_DISTINCT_DIMENSION_VALUES
    coarse = (gran["multiple_of_five_rate"] or 0.0) >= GRANULARITY_CEILING
    ceilinged = (sat["dimension_max_rate"] or 0.0) >= SATURATION_DIM_MAX_CEILING
    perfect = (sat["full_total_rate"] or 0.0) >= SATURATION_FULL_TOTAL_CEILING

    if flat:
        reasons.append(
            f"across-skill sd {across_sd} < {DISCRIMINATION_SD_FLOOR}: its {row['n_skills']} per-skill means "
            f"span {disc['skill_mean_range']} points ({disc['skill_mean_min']}-{disc['skill_mean_max']})"
        )
    if few_values:
        reasons.append(
            f"used {distinct} distinct dimension value(s) across {row['n_dimension_scores']} scores "
            f"({', '.join(f'{v:g}' for v in disc['dimension_values'])}); the rubric gives every single "
            f"dimension {MIN_DISTINCT_DIMENSION_VALUES} bands"
        )
    if coarse:
        reasons.append(
            f"{gran['multiple_of_five_rate']:.0%} of its dimension scores are multiples of 5 "
            f"(chance is {gran['chance_rate']:.0%})"
        )
    if ceilinged:
        reasons.append(f"{sat['dimension_max_rate']:.0%} of its dimension scores are that dimension's maximum")
    if perfect:
        reasons.append(f"{sat['full_total_rate']:.0%} of its judgments came back at the full {sat['rubric_total']}")

    if flat or few_values:
        return VERDICT_NON_DISCRIMINATING, reasons
    if coarse or ceilinged or perfect:
        return VERDICT_COARSE, reasons
    return VERDICT_DISCRIMINATING, []


def flagged_providers(quality_rows: list[dict[str, Any]]) -> list[str]:
    """The judges whose output carries no ranking information. Not an exclusion list."""
    return sorted(r["provider"] for r in quality_rows if r["verdict"] == VERDICT_NON_DISCRIMINATING)


def _pool_figures(judgments: list[Judgment]) -> dict[str, Any] | None:
    """The pooled headline numbers for a set of judgments, or None if it cannot support them.

    Returns None rather than raising when a skill is left with a single
    judgment: "excluding this judge would leave AST07 with one score" is a
    finding about the exclusion, and the report says so in words.
    """
    if len(judgments) < 2:
        return None
    try:
        dispersion = skill_dispersion(judgments)
    except ScorecardError:
        return None
    sigmas = [row["sigma"] for row in dispersion]
    provider_means = [row["mean"] for row in provider_bias(judgments)]
    return {
        "n_judgments": len(judgments),
        "providers": sorted({j.provider for j in judgments}),
        "pooled_mean": round(pooled_mean(judgments), 1),
        "bias_spread": round(max(provider_means) - min(provider_means), 1),
        "sigma_min": min(sigmas),
        "sigma_max": max(sigmas),
        "sigma_median": round(statistics.median(sigmas), 2),
        "implied_mean_bar_min": round(POOLED_LOWER_BOUND + min(sigmas), 1),
        "implied_mean_bar_max": round(POOLED_LOWER_BOUND + max(sigmas), 1),
        "skills": dispersion,
    }


def exclusion_effect(judgments: list[Judgment], flagged: list[str]) -> dict[str, Any]:
    """Pooled figures with and without the flagged judges, and the delta between them.

    Both columns are published on purpose. Printing only the filtered number
    would hand the reader a panel that quietly differs from the one every
    scorecard, the dashboard and ADR-0005 describe; printing only the unfiltered
    one would hide that a single judge moves the pooled mean by two points and
    the median sigma by a point and a half. The delta is the evidence a human
    needs in order to decide — in an ADR, not here — whether that judge should
    keep binding.
    """
    flagged_set = set(flagged)
    kept = [j for j in judgments if j.provider not in flagged_set]
    with_flagged = _pool_figures(judgments)
    without_flagged = _pool_figures(kept) if flagged_set else None

    out: dict[str, Any] = {
        "flagged": sorted(flagged_set),
        "with_flagged": with_flagged,
        "without_flagged": without_flagged,
        "delta": None,
        "note": (
            "Diagnostics. Every figure elsewhere in this report, in eval/scorecards/*.json, in the "
            "dashboard and in ADR-0005 is the with-flagged column: no judge has been excluded from "
            "anything. Excluding one is a human decision and needs its own ADR."
        ),
    }
    if not flagged_set:
        out["note"] = "No judge on this panel is flagged NON-DISCRIMINATING; there is nothing to exclude."
        return out
    if without_flagged is None:
        out["note"] = (
            f"Excluding {', '.join(sorted(flagged_set))} would leave too few judgments per skill to "
            "compute a sigma, so the without-flagged column cannot be shown. That is itself a finding: "
            "the flagged judge is carrying part of the panel's coverage."
        )
        return out
    if with_flagged is not None:
        out["delta"] = {
            key: round(without_flagged[key] - with_flagged[key], 2)
            for key in ("n_judgments", "pooled_mean", "bias_spread", "sigma_min", "sigma_max", "sigma_median")
        }
    return out


def judge_quality(judgments: list[Judgment], maxima: Mapping[str, int] | None = None) -> dict[str, Any]:
    """The whole judge-quality report: thresholds, per-provider rows, and the exclusion delta."""
    rows = provider_quality(judgments, maxima)
    flagged = flagged_providers(rows)
    return {
        "thresholds": {
            "min_distinct_dimension_values": MIN_DISTINCT_DIMENSION_VALUES,
            "discrimination_sd_floor": DISCRIMINATION_SD_FLOOR,
            "min_skills_for_discrimination": MIN_SKILLS_FOR_DISCRIMINATION,
            "granularity_ceiling": GRANULARITY_CEILING,
            "saturation_dim_max_ceiling": SATURATION_DIM_MAX_CEILING,
            "saturation_full_total_ceiling": SATURATION_FULL_TOTAL_CEILING,
            # Not a threshold: the baseline `granularity_ceiling` is justified
            # against. Recorded here so the file explains its own numbers.
            "multiple_of_five_chance_rate": round(
                multiple_of_five_chance_rate(dict(maxima) if maxima is not None else dimension_maxima()), 3
            ),
        },
        "verdicts": [
            VERDICT_NON_DISCRIMINATING,
            VERDICT_COARSE,
            VERDICT_DISCRIMINATING,
            VERDICT_INSUFFICIENT_DATA,
        ],
        "providers": rows,
        "flagged": flagged,
        "exclusion": exclusion_effect(judgments, flagged),
    }


def panel_summary(judgments: list[Judgment]) -> dict[str, Any]:
    """Panel-level figures: the spread, the sigma range, and the bar it implies.

    ``implied_mean_bar_*`` is arithmetic on the RETIRED clause, not a proposal:
    ``mean − σ ≥ POOLED_LOWER_BOUND`` is the same constraint as
    ``mean ≥ POOLED_LOWER_BOUND + σ``, so the sigma a panel produces set the
    mean that clause actually demanded. It is still computed because ADR-0005's
    figures are that arithmetic and must stay regenerable; it is what ADR-0006
    retired, and printing it makes visible that the effective bar moved when the
    panel widened, without anyone editing a constant.

    ``sem_bar_median`` is the same statement about the clause now in force:
    ``mean − CONFIDENCE_K × σ/√n ≥ POOLED_TARGET`` is ``mean ≥ POOLED_TARGET +
    k·σ/√n``, so at this panel's median σ and n the rule demands that mean. It
    falls as n rises and is bounded below by ``POOLED_TARGET``, which is the
    difference between a confidence bound and a spread.
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
        "confidence_k": CONFIDENCE_K,
        # Median sigma over median n, which is the figure ADR-0006 quotes
        # (109.13 at sigma 4.67, n 17) — not the median of the per-skill sems,
        # which is a different statistic and would put the tool 0.05 away from
        # the record it is meant to make checkable.
        "sem_bar_median": round(
            POOLED_TARGET
            + CONFIDENCE_K * statistics.median(sigmas) / math.sqrt(statistics.median([row["n"] for row in dispersion])),
            2,
        ),
        "pooled_lower_bound": POOLED_LOWER_BOUND,
        "implied_mean_bar_min": round(POOLED_LOWER_BOUND + min(sigmas), 1),
        "implied_mean_bar_max": round(POOLED_LOWER_BOUND + max(sigmas), 1),
        "target_pct": round(100 * POOLED_TARGET / RUBRIC_MAX, 1),
        "implied_pct_min": round(100 * (POOLED_LOWER_BOUND + min(sigmas)) / RUBRIC_MAX, 1),
        "implied_pct_max": round(100 * (POOLED_LOWER_BOUND + max(sigmas)) / RUBRIC_MAX, 1),
    }


def report(judgments: list[Judgment]) -> dict[str, Any]:
    """Everything the printed tables show, as plain data.

    ``summary``, ``providers`` and ``skills`` describe the panel exactly as
    recorded — flagged judges included. ``judge_quality`` is the only place a
    filtered figure appears, and it appears beside its unfiltered twin.
    """
    return {
        "summary": panel_summary(judgments),
        "providers": provider_bias(judgments),
        "skills": skill_dispersion(judgments),
        "judge_quality": judge_quality(judgments),
    }


def judge_quality_document(data: dict[str, Any], source: Path) -> dict[str, Any]:
    """`eval/judge-quality.json`: the verdicts, machine-readable and diffable.

    Carries no timestamp on purpose. The file is committed and regenerated from
    the recorded scorecards, so a wall-clock field would make every run a diff
    and hide the one change that matters — a judge's verdict moving.
    """
    try:
        where = str(source.resolve().relative_to(REPO_ROOT))
    except ValueError:
        where = str(source)
    return {
        "generated_by": "eval/calibration.py",
        "source": where,
        "n_judgments": data["summary"]["n_judgments"],
        "n_skills": data["summary"]["n_skills"],
        "n_providers": data["summary"]["n_providers"],
        "doctrine": (
            "Declare and record. A NON-DISCRIMINATING verdict flags a judge whose output carries no "
            "ranking information; it does NOT remove that judge from any pooled figure, and nothing in "
            "this repository reads this file as an exclusion list. Excluding a judge from the binding "
            "pool is a human decision and needs its own ADR."
        ),
        **data["judge_quality"],
    }


def _format_judge_quality(quality: dict[str, Any]) -> list[str]:
    """The judge-quality table, the reasons behind each verdict, and the exclusion delta."""
    lines: list[str] = []
    lines.append("Judge quality (is this judge measuring, or emitting a placeholder?)")
    lines.append(
        f"  {'provider':<32} {'n':>4} {'dist':>5} {'acr-sd':>7} {'acr-var':>8} "
        f"{'mult5':>6} {'dim-max':>8} {'full':>6} {'self':>6}  verdict"
    )
    for row in quality["providers"]:
        disc, gran, sat, cons = row["discrimination"], row["granularity"], row["saturation"], row["self_consistency"]

        def pct(value: float | None) -> str:
            return "   n/a" if value is None else f"{value:>5.0%}"

        def num(value: float | None, width: int) -> str:
            return "n/a".rjust(width) if value is None else f"{value:>{width}.2f}"

        lines.append(
            f"  {row['provider']:<32} {row['n_judgments']:>4} "
            f"{(disc['distinct_dimension_values'] if disc['distinct_dimension_values'] is not None else 'n/a'):>5} "
            f"{num(disc['across_skill_sd'], 7)} {num(disc['across_skill_variance'], 8)} "
            f"{pct(gran['multiple_of_five_rate']):>6} {pct(sat['dimension_max_rate']):>8} "
            f"{pct(sat['full_total_rate']):>6} {cons['same_skill_spread_mean']:>6.2f}  {row['verdict']}"
        )
    t = quality["thresholds"]
    lines.append("")
    lines.append(
        f"  dist = distinct dimension values used (flag < {t['min_distinct_dimension_values']}, "
        "the number of bands the rubric gives every single dimension); "
        f"acr-sd / acr-var = spread of this judge's per-skill mean totals (flag < "
        f"{t['discrimination_sd_floor']});"
    )
    lines.append(
        f"  mult5 = share of its dimension scores that are multiples of 5 (flag >= "
        f"{t['granularity_ceiling']:.0%}, against ~{t['multiple_of_five_chance_rate']:.0%} by chance); "
        f"dim-max = share at that dimension's maximum (flag >= {t['saturation_dim_max_ceiling']:.0%}); "
        f"full = share of judgments at the rubric total (flag >= {t['saturation_full_total_ceiling']:.0%});"
    )
    lines.append("  self = mean spread between this judge's own rounds on one skill (low is good on its own,")
    lines.append("  and is what turns a low acr-sd from 'noisy' into 'constant').")
    for row in quality["providers"]:
        if row["reasons"]:
            lines.append("")
            lines.append(f"  {row['provider']} -> {row['verdict']}")
            for reason in row["reasons"]:
                lines.append(f"    - {reason}")
    return lines


def _format_exclusion(exclusion: dict[str, Any]) -> list[str]:
    """The with/without table. Never a replacement for the with-flagged figures."""
    lines: list[str] = []
    lines.append("Pooled figures WITH and WITHOUT the flagged judge(s) — shown, not applied")
    with_f, without_f, delta = exclusion["with_flagged"], exclusion["without_flagged"], exclusion["delta"]
    if with_f is None:
        lines.append("  (not enough judgments to pool)")
        return lines
    if without_f is None or delta is None:
        lines.append(f"  {exclusion['note']}")
        return lines
    labels = [
        ("judgments pooled", "n_judgments", "{:.0f}"),
        ("pooled mean", "pooled_mean", "{:.1f}"),
        ("between-judge spread", "bias_spread", "{:.1f}"),
        ("per-skill sigma, min", "sigma_min", "{:.2f}"),
        ("per-skill sigma, max", "sigma_max", "{:.2f}"),
        ("per-skill sigma, median", "sigma_median", "{:.2f}"),
    ]
    lines.append(f"  {'figure':<26} {'with':>10} {'without':>10} {'delta':>10}")
    for label, key, fmt in labels:
        lines.append(
            f"  {label:<26} {fmt.format(with_f[key]):>10} {fmt.format(without_f[key]):>10} {delta[key]:>+10.2f}"
        )
    lines.append("")
    lines.append(f"  {'skill':<12} {'mean with':>10} {'mean w/o':>10} {'sigma with':>11} {'sigma w/o':>10}")
    without_by_skill = {row["skill"]: row for row in without_f["skills"]}
    for row in with_f["skills"]:
        other = without_by_skill.get(row["skill"])
        if other is None:
            continue
        lines.append(
            f"  {row['skill']:<12} {row['mean']:>10.1f} {other['mean']:>10.1f} "
            f"{row['sigma']:>11.2f} {other['sigma']:>10.2f}"
        )
    lines.append("")
    lines.append(f"  {exclusion['note']}")
    return lines


def format_report(data: dict[str, Any]) -> str:
    """The human-readable tables. Column widths fixed so output diffs cleanly."""
    s = data["summary"]
    quality = data["judge_quality"]
    lines: list[str] = []
    if quality["flagged"]:
        # First thing on the page. A verdict a reader has to scroll to find is a
        # verdict the next person quoting the pooled mean will not have read.
        lines.append("!! " + "=" * 74)
        lines.append(f"!! {VERDICT_NON_DISCRIMINATING} JUDGE(S) ON THIS PANEL: {', '.join(quality['flagged'])}")
        lines.append("!! Still pooled into every figure below, and into every recorded scorecard.")
        lines.append("!! See the judge-quality table for why, and eval/judge-quality.json for the data.")
        lines.append("!! " + "=" * 74)
        lines.append("")
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
    lines.append(
        f"  That clause was RETIRED on 2026-08-24 (ADR-0006). The rule in force is "
        f"mean - {s['confidence_k']} * sigma/sqrt(n) >= {s['pooled_target']}, which at this "
        f"panel's median sigma and n demands a mean of {s['sem_bar_median']} and falls toward "
        f"{s['pooled_target']} as judgments accumulate. Run 4 was judged under the retired "
        f"clause and is not re-gated."
    )
    lines.append("")
    lines.extend(_format_judge_quality(quality))
    lines.append("")
    lines.extend(_format_exclusion(quality["exclusion"]))
    lines.append("")
    lines.append("  Diagnostics only. No gate constant is read from this file and none is changed by it;")
    lines.append("  no judge is excluded by it. The gate has been changed exactly once, by a record")
    lines.append("  written before the run it judges. See")
    lines.append("  docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md (the diagnosis) and")
    lines.append("  docs/adr/0006-confidence-bound-on-the-pooled-mean.md (the change).")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eval/calibration.py",
        description="Per-provider bias and per-skill sigma over eval/scorecards/*.json.",
    )
    parser.add_argument("--scorecards", default=str(SCORECARD_DIR), help="scorecard directory to read")
    parser.add_argument("--json", action="store_true", help="emit the figures as JSON instead of tables")
    parser.add_argument(
        "--judge-quality-out",
        default=None,
        help=f"where to write the machine-readable judge-quality verdicts (default: {JUDGE_QUALITY_PATH.name})",
    )
    parser.add_argument("--no-emit", action="store_true", help="print only; do not write the judge-quality file")
    args = parser.parse_args(argv)

    source = Path(args.scorecards)
    judgments = load_judgments(source)
    if not judgments:
        print(f"{args.scorecards}: no judgments recorded — nothing to calibrate")
        return 0

    data = report(judgments)
    print(json.dumps(data, indent=2) if args.json else format_report(data))

    # Written by default, but only for the corpus the committed file is *about*.
    # A `--scorecards some/other/dir` run must never overwrite the recorded
    # panel's verdicts with a foreign corpus's; an explicit --judge-quality-out
    # is the way to ask for that on purpose.
    destination = Path(args.judge_quality_out) if args.judge_quality_out else JUDGE_QUALITY_PATH
    default_corpus = source.resolve() == SCORECARD_DIR.resolve()
    if not args.no_emit and (args.judge_quality_out or default_corpus):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(judge_quality_document(data, source), indent=2) + "\n",
            encoding="utf-8",
        )
        if not args.json:
            print(f"\n  Judge-quality verdicts written to {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
