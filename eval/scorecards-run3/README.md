# Scorecards — run 3 (archived)

One JSON file per skill, as written by the run-3 judge sweep. **Frozen.** Nothing writes here,
and nothing in this directory may be edited: it is half of a controlled measurement, and the
half that already happened.

Only `*.json` files in this directory are read as scorecards; this README is ignored.

## These are run 3 — the first scorecards written under the rubric-grounded prompt

Every judgment in this directory was scored by the prompt `scripts/judge_harness.py` rebuilt
on 2026-08-23: the pinned rubric's own band tables quoted verbatim, and a one-sentence
justification required per dimension. So each judgment here carries a `justifications` block
alongside its `scores`, and a judgement that would not explain itself never entered the pool —
**177 of the 198 attempted judgments bind**, the other 21 having been discarded at parse time
and **recorded nowhere** — the harness of the day kept its audit trail in memory, so the reasons
and the raw responses are gone. Which skill, judge and round each was is reconstructed in
[`../run5-refusals.md`](../run5-refusals.md), which covers this archive too. That is why `n`
varies by judge (23 to 33) instead of sitting at a flat 33.

## Why this archive is kept, and what it is for

Unlike `eval/scorecards-run1/` and `eval/scorecards-run2/`, this run **is** comparable to the
runs that followed it. It and `eval/scorecards-run4/` were scored by the same prompt, the same
six-provider panel, the same three rounds and the same gate constants. Between those two exactly
one thing changed: eight skills — `AST02`-`AST07`, `AST09`, `AST10` — gained an explicit
anti-pattern `NEVER` section, while `AST01`, `AST08` and `advisory` were deliberately left
untouched as controls.

That makes this directory the baseline arm of the first controlled experiment this repository
ran. Deleting it, or rescoring it, would destroy the comparison rather than update it. The result
is written up as "The controlled results" in
[`../../docs/skill-judge-dashboard.md`](../../docs/skill-judge-dashboard.md), beside the second
arm — run 4 to run 5, where `AST01` was the one treated skill and ten were controls. The live
corpus in `eval/scorecards/` is run 5; it is comparable to this one too, but nine `SKILL.md` files
separate them, so run 4 is the archive to difference against.

This is also the corpus on which `bedrock/qwen3-235b` came out COARSE rather than
NON-DISCRIMINATING — the measurement that records what the prompt rebuild repaired.
`tests/test_judge_quality.py` pins that verdict here, against these bytes, precisely so a later
run cannot un-make it. It has since been flagged again on run 4 and cleared again on run 5, on a
rule that has not changed; each of those states is pinned to the directory that measured it.

**The first two runs are not comparable to these files.** `eval/scorecards-run1/` and
`eval/scorecards-run2/` were produced by a prompt that sent the eight dimension *names* and
their maxima, none of the rubric's scoring bands, and forbade any prose — which is why not one
of their judgments carries a reason for any score. They measure a different instrument, and
must not be pooled with, differenced against, or trended into anything here. The one comparison
that break does support is between *judges*, and it is in
[`../../docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md`](../../docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md).

Which corpus is which is checkable rather than remembered:
`tests/scripts/test_judge_harness.py` measures it from the judgments themselves — every
judgment banked here must satisfy the justification contract and reproduce from its own
recorded `raw_response`, exactly as the live corpus must.
