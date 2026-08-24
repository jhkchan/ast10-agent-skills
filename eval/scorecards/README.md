# Scorecards

One JSON file per skill, written by a judge run and consumed by
`eval/generate_dashboard.py`. Empty until a judged run happens — see
[`../../docs/skill-judge-dashboard.md`](../../docs/skill-judge-dashboard.md) for the
file shape, the rubric, and the ship rule.

Only `*.json` files in this directory are read as scorecards; this README is ignored.

## These are run 4 — the current corpus, and the second scored under the rubric-grounded prompt

Every judgment in this directory was scored by the prompt `scripts/judge_harness.py` rebuilt
on 2026-08-23: the pinned rubric's own band tables quoted verbatim, and a one-sentence
justification required per dimension. So each judgment here carries a `justifications` block
alongside its `scores`, and a judgement that would not explain itself never entered the pool —
**180 of the 198 attempted judgments bind**, the other 18 having been refused as malformed and
recorded in the audit trail. That is why `n` varies by judge (26 to 32) instead of sitting at
a flat 33; an uneven `n` is the honest shape of a run that rejects bad rows rather than
averaging them in.

**Run 3 is the one archive these files may be compared against, skill by skill.**
`eval/scorecards-run3/` was scored by this same prompt, with the same panel, the same round
count and the same gate constants. The only thing that changed between the two runs is eight
`SKILL.md` files, which is what makes the pair a controlled measurement rather than two
snapshots — see "The controlled result" in
[`../../docs/skill-judge-dashboard.md`](../../docs/skill-judge-dashboard.md).

**The first two runs are not comparable to these files.** `eval/scorecards-run1/` and
`eval/scorecards-run2/` were produced by a prompt that sent the eight dimension *names* and
their maxima, none of the rubric's scoring bands, and forbade any prose — which is why not one
of their judgments carries a reason for any score. They measure a different instrument, and
must not be pooled with, differenced against, or trended into anything here. The one comparison
that break does support is between *judges*, and it is in
[`../../docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md`](../../docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md).

Which corpus is which is checkable rather than remembered:
`tests/scripts/test_judge_harness.py` measures it from the judgments themselves — every
judgment banked in this directory and in `eval/scorecards-run3/` must satisfy the
justification contract and reproduce from its own recorded `raw_response`, and the two
pre-rebuild archives must still be *rejected* by today's parser for the stated reason. All
four directories are kept exactly as written. See the callout at the top of
[`../../docs/skill-judge-dashboard.md`](../../docs/skill-judge-dashboard.md).
