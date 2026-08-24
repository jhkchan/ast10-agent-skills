# Scorecards — run 5 (live)

One JSON file per skill, written by a judge run and consumed by
`eval/generate_dashboard.py`. Empty until a judged run happens — see
[`../../docs/skill-judge-dashboard.md`](../../docs/skill-judge-dashboard.md) for the
file shape, the rubric, and the ship rule.

Only `*.json` files in this directory are read as scorecards; this README is ignored.

## These are run 5 — the first corpus judged under the confidence bound

Every judgment here was scored by the prompt `scripts/judge_harness.py` rebuilt on 2026-08-23:
the pinned rubric's own band tables quoted verbatim, and a one-sentence justification required
per dimension. So each judgment carries a `justifications` block alongside its `scores`, and a
judgement that would not explain itself never entered the pool — **188 of the 198 attempted
judgments bind**, the other 10 having been discarded at parse time. **Those ten were not recorded
when they were discarded** — the reasons and the raw responses are unrecoverable, and which skill,
judge and round each was is reconstructed in [`../run5-refusals.md`](../run5-refusals.md). Read
AST01's verdict with that file open: it lost the two judges that scored it lowest, and its
verdict does not survive refilling them at those judges' own means — see
[How fragile 11 of 11 is](../../docs/skill-judge-dashboard.md#how-fragile-11-of-11-is), which
also records that this board is 8 of 11 without one judge.
That is why `n` varies by judge (30 to 33) instead of sitting at a flat 33; an uneven `n` is the
honest shape of a run that rejects bad rows rather than averaging them in.

**These verdicts were issued by the rule in force**, and run 5 is the first corpus that rule ever
judged: `mean ≥ 108` AND `mean − 1.0 × stdev/√n ≥ 108` AND the per-dimension floors, adopted by
[`../../docs/adr/0006-confidence-bound-on-the-pooled-mean.md`](../../docs/adr/0006-confidence-bound-on-the-pooled-mean.md)
on 2026-08-24 — written down, and this repository's only gate change, **before** these scores
existed. These are also the first scorecards to carry that record's two published statistics,
`sem` and `ci_lower`, which is what dates them: the four archived runs do not have them, and
`scripts/ship_floor.py` treats their absence as a date rather than as a disagreement.

**All eleven skills clear the gate, and that number needs its caveats carried with it.** The panel
still spans 11.4 points on these same eleven files; the corpus, the fixtures and the judge prompt
are all written by this project, so a high pooled mean is internal consistency and not external
validation; `k = 1.0` is one standard error of margin and not a confidence level; and two skills
clear the second clause by under a point. "What 11 of 11 is, and what it is not" in
[`../../docs/skill-judge-dashboard.md`](../../docs/skill-judge-dashboard.md) is the long form.

**Runs 3 and 4 are the archives these files may be compared against, skill by skill.**
`eval/scorecards-run3/` and `eval/scorecards-run4/` were scored by this same prompt, with the same
panel and the same round count. Exactly one `SKILL.md` changed between run 4 and this run —
`AST01`, which gained an anti-pattern section — which is what makes the pair a controlled
measurement rather than two snapshots. The gate's second clause did change in between; that change
moves no verdict on the run-4 corpus, and `tests/test_generate_dashboard.py` re-derives it —
**but it moves `AST01`'s on this one.** Under the retired `mean − σ ≥ 105` clause `AST01` reads
`110.1 − 6.65 = 103.4` and stays BLOCKED, so the treated skill's `BLOCKED → SHIP` needs the new
clause as well as the edit. The `D3` half of that comparison (12.2 → 14.2 against a fixed floor of
13) is unaffected by either clause and is the part that is controlled.

**The first two runs are not comparable to these files.** `eval/scorecards-run1/` and
`eval/scorecards-run2/` were produced by a prompt that sent the eight dimension *names* and their
maxima, none of the rubric's scoring bands, and forbade any prose — which is why not one of their
judgments carries a reason for any score. They measure a different instrument, and must not be
pooled with, differenced against, or trended into anything here. The one comparison that break
does support is between *judges*, and it is in
[`../../docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md`](../../docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md).

Which corpus is which is checkable rather than remembered:
`tests/scripts/test_judge_harness.py` measures it from the judgments themselves — every judgment
banked in this directory and in the two post-rebuild archives must satisfy the justification
contract and reproduce from its own recorded `raw_response`, and the two pre-rebuild archives must
still be *rejected* by today's parser for the stated reason. All five directories are kept exactly
as written. See the callout at the top of
[`../../docs/skill-judge-dashboard.md`](../../docs/skill-judge-dashboard.md).
