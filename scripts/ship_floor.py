#!/usr/bin/env python3
"""scripts/ship_floor.py — the pooled Grade-A verdict rule (spec.md gate-2).

Vendored, standalone, from the upstream eval-harness repository (Apache-2.0) — spec.md
gate-3: "Inherited ship_floor.py rule, NOT the literal median ... Vendor a
standalone copy ... No live dependency on another repo." See
THIRD_PARTY_LICENSES.md and NOTICE for the pinned upstream commit and drift
policy: "If this formula is updated upstream, the two repos diverge and Step
05 measures an agreed-to metric in only one of them" (plan.md "Risky code
touchpoints").

The formula below — FLOORS, POOLED_TARGET, MIN_ROUNDS, AGG_METHOD, RUBRIC_SHA,
pooled_stats(), dim_means_of(), aggregate_verdict(), verdict_of(),
_is_invalidated(), binding_block() — was copied UNCHANGED from upstream: it is
"the exact formula locked at Gate B half 1" (spec.md gate-2) and must not drift
by so much as a comparison operator without a recorded decision. It has taken
exactly one such decision, described next; everything not named there is still
byte-identical to upstream.

THE GATE HAS BEEN CHANGED EXACTLY ONCE, and this is that change. On 2026-08-24
docs/adr/0006-confidence-bound-on-the-pooled-mean.md replaced the second clause
`mean - stdev >= POOLED_LOWER_BOUND (105)` with
`mean - CONFIDENCE_K * stdev/sqrt(n) >= POOLED_TARGET (108)`, adding CONFIDENCE_K
and the two published statistics `sem` and `ci_lower`. Nothing else moved: FLOORS,
POOLED_TARGET, MIN_ROUNDS, AGG_METHOD, RUBRIC_SHA, INDEPENDENT_METHODS, the
anti-re-roll pooling rule, dim_means_of(), verdict_of(), _is_invalidated(),
binding_block(), and the whole of pooled_stats()/aggregate_verdict() apart from
that clause, are as vendored. The change was made
because the retired clause was demonstrated to be NOT A FUNCTION OF THE ARTIFACT
— AST08's SKILL.md is byte-identical between run 3 and run 4 and the clause
flipped its verdict (run 3: 110.3 - 5.65 = 104.6, BLOCKED; run 4:
110.8 - 4.67 = 106.1, SHIP) — and it was recorded and its constant fixed BEFORE
the run it judges. Run 4 (eval/scorecards-run4/) was scored under the retired
clause and its published verdicts stay as issued; run 5 (eval/scorecards/) is the
first run judged here, and running this gate over the frozen run-4 bytes
reproduces all eleven of its verdicts.
THIS REPO AND UPSTREAM NOW DIVERGE IN THIS ONE CLAUSE, by decision: see
ADR-0006 "Consequences / Negative", THIRD_PARTY_LICENSES.md and NOTICE. Any
score quoted across the two repositories must name which rule produced it.

Dropped from upstream: the `A_MINUS`/`MANDATED` skill-name sets and the
delivery-floor check in `main()` are the upstream eval-harness repository's own roll-up
policy over ITS skill roster (skill names like
an upstream skill directory name) — not part of the formula, not
meaningful for this repo's AST01-AST10 + advisory roster, and this repo's
spec/plan define no equivalent "mandated area" concept. `main()` below is
this repo's own thin driver over the same aggregate_verdict() rule. Reads
OWASP_AST10_ROOT (default: this script's repo root) so tests can point it at
a fixture repo.
"""

from __future__ import annotations

import json
import math
import os
import pathlib
import re
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from content_hash import content_sha256  # noqa: E402

ITER_KEY = re.compile(r"^iter-(\d+)-(sim|live)$")
FLOORS = {"D1": 17, "D2": 13, "D3": 13, "D4": 13, "D5": 13, "D6": 13, "D7": 8, "D8": 13}
TARGETS = {"A": 108}

# --- the distribution rule --------------------------------------------------
# skill-judge scoring is NON-DETERMINISTIC. Three sweeps over byte-identical
# content produced binding means of 101.1, 105.1 and 108.6, and the pooled
# per-judgment sigma is 3.3 points. A single pair's min is therefore not a
# statistic: it is one draw from a distribution roughly two grade-boundaries
# wide, and which draw you got depends on when you ran it.
#
# SHIP is consequently defined on the POOLED DISTRIBUTION, not on any one
# judgment:
#     mean >= 108                            the POINT ESTIMATE is grade A
#     mean - 1.0 * stdev/sqrt(n) >= 108      and the TRUE MEAN is confidently grade A
# plus the per-dimension floors, applied to the DIMENSION MEANS.
#
# THE SECOND CLAUSE READ `mean - stdev >= 105` UNTIL 2026-08-24, and changing it
# is the only edit this file has taken since it was vendored. `mean - stdev` is a
# SPREAD statistic; the question the clause asks — "is this skill's true quality
# above the bar?" — is a question about a MEAN, whose uncertainty shrinks as
# `stdev/sqrt(n)`. Using the spread made the verdict a function of how much the
# panel happened to agree that day rather than of the artifact: AST08's SKILL.md
# is byte-identical between run 3 and run 4 and went BLOCKED (110.3 - 5.65 =
# 104.6) -> SHIP (110.8 - 4.67 = 106.1) on that clause alone. A gate that is not
# a function of the artifact is not a gate. ADR-0005 diagnosed it; ADR-0006
# named the replacement rule and its constant BEFORE the run they judge, which
# is the whole reason the change is not a retune. Full derivation, the k
# comparison, the verdict-stability controls and the alternatives considered are
# in docs/adr/0006-confidence-bound-on-the-pooled-mean.md.
#
# ANTI-RE-ROLL, preserved but by a different mechanism. The old rule took
# min(total) so that re-running the judge could never raise a score. Pooling
# keeps that property without pretending the minimum is the measurement:
# EVERY judgment must be recorded in `aggregate.judgments` and pooled. You may
# ADD rounds; you may never DISCARD one. That is what makes the number honest,
# and it is cheap to enforce because adding rounds barely moves a mean — one
# lucky +6 draw moves a mean of 8 by +0.75, where under min() a single unlucky
# draw moved the binding score by the full 6. Re-rolling for a better number
# is no longer worth the electricity. The one exception is an INVALIDATED
# measurement (see _is_invalidated): a defective instrument, flagged and
# auditable, never a score somebody merely dislikes.
# As vendored, and unchanged by ADR-0006: the grade-A boundary on the 120-point
# rubric (108/120 = 90.0%). It is now the reference level for BOTH clauses --
# clause 1 asks whether the point estimate reaches it, clause 2 whether the
# lower end of a confidence interval on the mean still does. ADR-0006 "What the
# second clause is FOR".
POOLED_TARGET = 108  # required pooled mean, and the bar clause 2 measures against
# NEW in ADR-0006: standard errors of margin the pooled mean must hold above
# POOLED_TARGET. Derived, not chosen (ADR-0006 "Why k = 1.0, derived rather than
# chosen"), on four grounds: (1) it is deliberately NOT sold as a confidence
# level -- this panel's ICC is 0.666 and its design effect 2.15, so a nominal
# 95% k would deliver ~87% and the label would be false; k = 1.0 is quoted in
# points instead, moving the effective bar from 108.0 to about 109.1 at this
# panel's median sigma 4.67 and n 17. (2) It keeps the clause LIVE: the naive
# swap `mean - stdev/sqrt(n) >= 105` reads `mean >= 106.2` here, strictly
# implied by clause 1, i.e. decoration. (3) It passes the pre-registered
# verdict-stability test with room to spare -- AST08's byte-identical run-3
# score clears by 0.84 and its run-4 score by 1.70, where k >= 1.577 would
# reintroduce the very flip this change removes. (4) It needs no estimate of the
# panel's ICC to justify, so the bar cannot float invisibly on panel
# composition, which is the disease ADR-0005 diagnosed.
CONFIDENCE_K = 1.0  # standard errors of margin required above POOLED_TARGET
# RETIRED as a gate constant by ADR-0006 and read by NOTHING in this module. It
# is kept, and kept at 105, because ADR-0005's diagnosis is arithmetic against
# this exact number and `eval/calibration.py` regenerates those figures from it;
# deleting it would make the record that justified the change unverifiable. The
# descriptive statistic it used to gate on, `lower_bound = mean - stdev`, is
# still computed and still published in every scorecard for the same reason. It
# simply stops deciding anything. ADR-0006 "The rule".
POOLED_LOWER_BOUND = 105  # historical: the retired mean - 1 sample stdev bar
# Unchanged by ADR-0006, and the reason is a property of the new rule rather
# than an absence of thought: the bar FALLS with n (110.34 at n=4, 109.13 at
# n=17, 108.47 at n=100) but is monotone and strictly bounded below by
# POOLED_TARGET, so volume can buy at most the ~1.1 points between today's bar
# and 108 and can never buy a pass for a skill whose true mean is below grade A.
# The new rule is also HARSHER than the retired one at small n, so it removes
# rather than adds the pressure to raise this. ADR-0006 "MIN_ROUNDS stays 4".
# Known gap, flagged there and deliberately not fixed here: this counts
# JUDGMENTS, not JUDGES.
MIN_ROUNDS = 4  # below this a sample stdev is not worth computing
AGG_METHOD = "multi-round-independent-pooled"
# Pins the skill-judge rubric version scores must be judged against (spec.md
# contract: "the pinned 8-dimension skill-judge rubric"). Same rubric,
# same SHA, as the upstream eval-harness repository's vendor/skill-judge/ — see
# THIRD_PARTY_LICENSES.md for the vendoring status of the rubric itself.
# RUBRIC_SHA is the upstream COMMIT id that last touched the rubric -- it is not a
# content hash and cannot be recomputed from the file. It exists to name the exact
# upstream revision. RUBRIC_CONTENT_SHA256 is the recomputable companion: it hashes
# the vendored bytes at vendor/skill-judge/SKILL.md, so the pin is checkable from
# inside this repo (tests/test_rubric_pin.py). See vendor/skill-judge/PROVENANCE.md.
RUBRIC_SHA = "3027f20f3181758385a1bb8c022d4041dfb4de84"
RUBRIC_CONTENT_SHA256 = "737ef3628f0e11353114c3bd05a1c9d0c448dbfec1ae85db839253cbe93198b6"
RUBRIC_PATH = pathlib.Path(__file__).resolve().parent.parent / "vendor" / "skill-judge" / "SKILL.md"
DIM_KEYS = tuple(FLOORS)

ROOT = pathlib.Path(os.environ.get("OWASP_AST10_ROOT", pathlib.Path(__file__).resolve().parent.parent))


# Methods whose scores may BIND. Every entry runs the judge in a context
# separate from the one that authored the skill. They are listed newest-first
# and each is strictly stronger than the one below it:
#   ...-pinned-rubric   two blind judges + the rubric pinned in vendor/ and
#                       confirmed read; judges must REFUSE rather than
#                       reconstruct it (added after a stale rubric path caused
#                       a measured -4.0 point systematic shift)
#   ...dual-judge-min   two blind judges, lower total binds
#   live-subagent...    one judge in a fresh context
# Anything absent — notably authoring-session self-scores, which measured
# +12.2 points of inflation — never binds.
#
# Kept HERE, not in the test, because both the gate and the test must agree;
# duplicating it is how the list silently drifts.
INDEPENDENT_METHODS = frozenset(
    {
        "live-subagent-skill-judge",
        "live-independent-dual-judge-min",
        "live-independent-dual-judge-min-pinned-rubric",
    }
)


def pooled_stats(totals: list[int]) -> dict:
    """Descriptive statistics over the pooled judgments, rounded as published.

    Rounded here, once, so that the numbers in scores.json, the dashboard, the
    README and the gate are literally the same numbers — a reader recomputing
    from `aggregate.judgments` must land on the stored values exactly, which is
    what makes the stored values checkable rather than merely asserted.

    `sem` and `ci_lower` are ADR-0006's two additions, and they follow the same
    convention for the same reason: `sem` is derived from the ROUNDED `stdev`
    and `ci_lower` from the ROUNDED `mean` and `sem`, so a reader holding only
    `n`, `mean` and `stdev` reproduces the gate's verdict exactly rather than
    approximately. `lower_bound` (`mean - stdev`) stays published although
    nothing gates on it any more: it is the statistic ADR-0005's argument rests
    on, and dropping it would destroy the evidence for the change.
    """
    if len(totals) < MIN_ROUNDS:
        raise ValueError(f"pooled stats need >= {MIN_ROUNDS} judgments, got {len(totals)}")
    n = len(totals)
    mean = round(statistics.fmean(totals), 1)
    stdev = round(statistics.stdev(totals), 2)
    sem = round(stdev / math.sqrt(n), 2)
    return {
        "n": n,
        "mean": mean,
        "median": round(statistics.median(totals), 1),
        "min": min(totals),
        "max": max(totals),
        "range": max(totals) - min(totals),
        "stdev": stdev,
        "lower_bound": round(mean - stdev, 1),
        "sem": sem,
        "ci_lower": round(mean - CONFIDENCE_K * sem, 1),
    }


#: The statistics every recorded aggregate MUST carry. This is `pooled_stats()`
#: minus ADR-0006's two additions, and the split is a dating mechanism, not a
#: softening: a scorecard written before 2026-08-24 cannot carry `sem`/`ci_lower`,
#: so reading their absence as "stored stats disagree with the recompute" would
#: turn every verdict in the four archived runs (`eval/scorecards-run{1,2,3,4}/`)
#: into a stats-drift BLOCK — re-labelling runs this rule never judged, which
#: ADR-0006's Status section forbids. Absence of these two is therefore tolerated; absence of anything in
#: this tuple is refused, and a stored value that DISAGREES with the recompute is
#: refused whatever its key.
PRE_ADR0006_STATS = ("n", "mean", "median", "min", "max", "range", "stdev", "lower_bound")


def dim_means_of(dimsets: list[dict]) -> dict:
    """Per-dimension means across every judgment that recorded a breakdown.

    May pool fewer judgments than the totals do: some historical rounds recorded
    only the binding judge's dimensions. `aggregate.dim_n` records how many.
    """
    return {d: round(statistics.fmean([ds[d] for ds in dimsets]), 1) for d in DIM_KEYS}


def aggregate_verdict(skill: str, agg: dict | None) -> tuple[str, str]:
    """SHIP on the pooled distribution. The single definition of SHIP.

    Recomputes every published number from `aggregate.judgments` first: a stored
    mean is a claim, not evidence, exactly as a stored `per_dim_floors_met` flag
    is not evidence. A stored statistic that disagrees with that recompute is
    BLOCKED, not a rounding note.

    Two clauses on the pooled totals, asking two different questions against the
    same boundary (ADR-0006):

        mean     >= POOLED_TARGET   is the point estimate Grade A?
        ci_lower >= POOLED_TARGET   is the TRUE mean confidently Grade A?

    where `ci_lower = mean - CONFIDENCE_K * stdev/sqrt(n)`. The second clause
    read `mean - stdev >= POOLED_LOWER_BOUND (105)` until 2026-08-24; that form
    could flip the verdict of a byte-identical file when the panel's dispersion
    moved, which is why it was replaced. Run 4's published verdicts were issued
    under the retired clause and are not re-issued here.
    """
    if not agg:
        return "BLOCKED", "no aggregate block — pool the independent rounds first"
    if agg.get("method") != AGG_METHOD:
        return "BLOCKED", f"method {agg.get('method')!r} is not {AGG_METHOD!r}"
    if agg.get("rubric_sha") != RUBRIC_SHA:
        return (
            "BLOCKED",
            f"rubric_sha {agg.get('rubric_sha')!r} != pinned {RUBRIC_SHA!r}",
        )

    totals = agg.get("judgments") or []
    if len(totals) < MIN_ROUNDS:
        return "BLOCKED", f"only {len(totals)} pooled judgments, need >= {MIN_ROUNDS}"
    stats = pooled_stats(totals)
    missing = [k for k in PRE_ADR0006_STATS if k not in agg]
    if missing:
        return (
            "BLOCKED",
            f"aggregate is missing required statistics: {missing}",
        )
    drift = [k for k, v in stats.items() if k in agg and agg[k] != v]
    if drift:
        return (
            "BLOCKED",
            f"stored stats disagree with recompute from judgments: {drift}",
        )

    dims = agg.get("dim_means", {})
    bad = [d for d, f in FLOORS.items() if dims.get(d, 0) < f]
    if bad:
        return "BLOCKED", f"dimension means below floor: {', '.join(bad)}"
    if stats["mean"] < POOLED_TARGET:
        return "BLOCKED", f"pooled mean {stats['mean']} < target {POOLED_TARGET}"
    if stats["ci_lower"] < POOLED_TARGET:
        return "BLOCKED", (
            f"confidence bound on the mean (mean - {CONFIDENCE_K} * stdev/sqrt(n)) "
            f"{stats['ci_lower']} < target {POOLED_TARGET} "
            f"— mean {stats['mean']} is Grade A but not confidently so "
            f"(n {stats['n']}, stdev {stats['stdev']}, sem {stats['sem']}); see ADR-0006"
        )
    return "SHIP", ""


def verdict_of(skill: str, blk: dict) -> tuple[str, str]:
    """Per-BLOCK recompute, retained for auditing single judgment rows.

    This is no longer the ship rule — aggregate_verdict() is. It stays because
    every historical block in scores.json carries a stored `verdict`, and a
    stored verdict that nothing recomputes is a self-assessment. main() still
    fails on any disagreement between the two.
    """
    tgt = TARGETS["A"]
    if blk.get("method") not in INDEPENDENT_METHODS:
        return (
            "BLOCKED",
            f"method {blk.get('method')!r} is not an independent judge pass",
        )
    dims = blk.get("dims", {})
    if blk.get("total") != sum(dims.values()):
        return "BLOCKED", "total != sum(dims)"
    bad = [d for d, f in FLOORS.items() if dims.get(d, 0) < f]
    if bad:
        return "BLOCKED", f"floors missed: {bad}"
    if blk["total"] < tgt:
        return "BLOCKED", f"total {blk['total']} < target {tgt}"
    return "SHIP", ""


def _is_invalidated(blk: dict) -> bool:
    """A block excluded from binding because its MEASUREMENT was defective.

    min(total) binds so that a re-roll can never raise a score. That rule is
    right, and it must not become a way to discard a score somebody dislikes —
    so exclusion requires an explicit `invalidated: true` PLUS a non-empty
    `invalidated_reason`, both recorded in scores.json and visible in the
    changelog and the dashboard. A merely low score is never excluded.
    """
    if not blk.get("invalidated"):
        return False
    if not str(blk.get("invalidated_reason", "")).strip():
        raise ValueError(
            "a block marked invalidated MUST carry a non-empty invalidated_reason "
            "— exclusion has to be auditable, not silent"
        )
    return True


def binding_block(skill: str, iters: dict, skills_dir: pathlib.Path | None = None) -> dict | None:
    """min(total) across live blocks at the CURRENT content hash. Not the last
    block, and never a lexicographic sort: iter-10 must outrank iter-9, and a
    re-roll must never raise a score.

    `skills_dir` defaults to ROOT / "skills"; callers that need to point at a
    fixture directory pass it explicitly instead of keeping a second copy of
    this function."""
    base = skills_dir if skills_dir is not None else ROOT / "skills"
    sha = content_sha256(base / skill)
    live = [
        (int(m.group(1)), b)
        for k, b in iters.items()
        if (m := ITER_KEY.match(k))
        and m.group(2) == "live"
        and b.get("content_sha256") == sha
        and not _is_invalidated(b)
    ]
    if not live:
        return None
    # .get(..., 0) — not blk["total"] — so a malformed live block (missing
    # "total") sorts as the minimum and surfaces as a verdict-mismatch FAIL
    # line in main(), rather than aborting the gate with a KeyError.
    return min(live, key=lambda t: (t[1].get("total", 0), t[0]))[1]


#: Where this repo's judged runs actually live, relative to ROOT. `scores.json`
#: is upstream's record shape and this repository has never written one; the
#: scorecards are. `main()` reads BOTH so that the command documented in the
#: README as "recompute every stored judge verdict" recomputes something.
SCORECARD_SUBDIR = ("eval", "scorecards")


def scorecard_dir() -> pathlib.Path:
    """The live scorecard directory, resolved against ROOT at call time.

    Resolved on each call rather than frozen at import, because ROOT is
    environment-driven (`OWASP_AST10_ROOT`) and tests repoint it at a fixture
    repo. A module-level constant would keep auditing the real corpus from
    inside a fixture, which is the opposite of what pointing ROOT somewhere else
    is for.
    """
    return ROOT.joinpath(*SCORECARD_SUBDIR)


def audit_scorecards(directory: pathlib.Path | None = None) -> tuple[list[str], list[str], int]:
    """Recompute every scorecard's stored aggregate verdict. Returns (failures, shipped, checked).

    A scorecard is exactly the shape `aggregate_verdict` reads, so nothing is
    translated on the way in: the stored `verdict` is a claim and the recompute
    from `aggregate.judgments` is the evidence, same as for a `scores.json`
    block. Files with no `aggregate` (a README, a hand-written note) are not
    scorecards and are skipped rather than failed.
    """
    base = directory if directory is not None else scorecard_dir()
    fail: list[str] = []
    shipped: list[str] = []
    checked = 0
    if not base.is_dir():
        return fail, shipped, checked
    for path in sorted(base.glob("*.json")):
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail.append(f"{path.name}: not valid JSON: {exc}")
            continue
        if not isinstance(card, dict) or not isinstance(card.get("aggregate"), dict):
            continue
        checked += 1
        skill = str(card.get("skill") or path.stem)
        verdict, why = aggregate_verdict(skill, card["aggregate"])
        stored = card.get("verdict")
        if stored is not None and stored != verdict:
            fail.append(f"{path.name}: stored verdict '{stored}' != recomputed '{verdict}' ({why or 'ok'})")
        if verdict == "SHIP":
            shipped.append(skill)
        else:
            print(f"note: {skill} does not ship — {why}")
    return fail, shipped, checked


def main() -> int:
    """Recompute every stored verdict this repository publishes, and fail on disagreement.

    Two records are read, and the command is only a no-op when neither exists:
    `scores.json` (upstream's per-iteration shape, which this repo does not
    write) and `eval/scorecards/*.json` (the judged runs it does). Reading only
    the first is how this command came to print "nothing scored yet" and exit 0
    beside a README line calling it a verification step — a check that checks
    nothing reports success, which is worse than no check. **An invocation that
    finds neither record now exits 1**, because "I could not verify anything" is
    not a pass.

    Unlike upstream, this carries no per-repo delivery-floor or mandated-area
    check — this repo's spec/plan define no such concept. What ships is
    exactly what aggregate_verdict() says ships; nothing else gates here.
    """
    scores_path = ROOT / "scores.json"
    fail: list[str] = []
    shipped: list[str] = []

    card_fail, card_shipped, card_checked = audit_scorecards()
    fail.extend(card_fail)
    shipped.extend(card_shipped)
    if card_checked:
        print(f"note: recomputed {card_checked} scorecard verdict(s) under {scorecard_dir()}")

    if not scores_path.is_file():
        if not card_checked:
            print(f"FAIL: neither {scores_path} nor a scorecard under {scorecard_dir()} exists — nothing was checked")
            return 1
        if fail:
            print("\n".join("FAIL: " + f for f in fail))
            return 1
        print(f"OK: {len(shipped)} skill(s) shipped.")
        return 0

    scores = json.loads(scores_path.read_text())

    for skill, iters in scores.items():
        # 1. Audit every stored per-block verdict against the per-block rule.
        #    These no longer decide shipping; they must still be internally
        #    honest, because the aggregate is pooled out of them.
        blk = binding_block(skill, iters)
        if blk is None:
            fail.append(f"{skill}: no live judge block matches the current content hash — re-judge")
        else:
            v, why = verdict_of(skill, blk)
            if blk.get("verdict") != v:
                fail.append(f"{skill}: stored verdict '{blk.get('verdict')}' != recomputed '{v}' ({why or 'ok'})")

        # 2. Ship on the pooled distribution.
        agg = iters.get("aggregate")
        av, awhy = aggregate_verdict(skill, agg)
        if agg is not None and agg.get("verdict") != av:
            fail.append(
                f"{skill}: stored aggregate verdict '{agg.get('verdict')}' != recomputed '{av}' ({awhy or 'ok'})"
            )
        if av == "SHIP":
            shipped.append(skill)
        else:
            print(f"note: {skill} does not ship — {awhy}")

    if fail:
        print("\n".join("FAIL: " + f for f in fail))
        return 1
    print(f"OK: {len(shipped)} skill(s) shipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
