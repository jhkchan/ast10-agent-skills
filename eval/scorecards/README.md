# Scorecards

One JSON file per skill, written by a judge run and consumed by
`eval/generate_dashboard.py`. Empty until a judged run happens — see
[`../../docs/skill-judge-dashboard.md`](../../docs/skill-judge-dashboard.md) for the
file shape, the rubric, and the ship rule.

Only `*.json` files in this directory are read as scorecards; this README is ignored.

## These are run 3 — the first scorecards written under the rubric-grounded prompt

Every judgment in this directory was scored by the prompt `scripts/judge_harness.py` rebuilt
on 2026-08-23: the pinned rubric's own band tables quoted verbatim, and a one-sentence
justification required per dimension. So each judgment here carries a `justifications` block
alongside its `scores`, and a judgement that would not explain itself never entered the pool —
**177 of the 198 attempted judgments bind**, the other 21 having been refused as malformed and
recorded in the audit trail. That is why `n` varies by judge (23 to 33) instead of sitting at
a flat 33; an uneven `n` is the honest shape of a run that rejects bad rows rather than
averaging them in.

**The earlier runs are not comparable to these files.** `eval/scorecards-run1/` and
`eval/scorecards-run2/` were produced by a prompt that sent the eight dimension *names* and
their maxima, none of the rubric's scoring bands, and forbade any prose — which is why not one
of their judgments carries a reason for any score. They measure a different instrument, and
must not be pooled with, differenced against, or trended into anything here. Run 3 is a new
baseline, not the third point on a trend; the one comparison the break does support is
between *judges*, and it is in
[`../../docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md`](../../docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md).

Which corpus is which is checkable rather than remembered:
`tests/scripts/test_judge_harness.py` asserts that every judgment banked here satisfies the
justification contract and reproduces from its own recorded `raw_response`, and that the two
archived corpora are still *rejected* by today's parser for the stated reason. All three
directories are kept exactly as written. See the callout at the top of
[`../../docs/skill-judge-dashboard.md`](../../docs/skill-judge-dashboard.md).
