# Scorecards — run 4 (archived)

One JSON file per skill, as written by the run-4 judge sweep. **Frozen.** Nothing writes here,
and nothing in this directory may be edited.

Only `*.json` files in this directory are read as scorecards; this README is ignored.

## These are run 4 — the last corpus judged under the retired clause

Every judgment here was scored by the prompt `scripts/judge_harness.py` rebuilt on 2026-08-23:
the pinned rubric's own band tables quoted verbatim, and a one-sentence justification required
per dimension. So each judgment carries a `justifications` block alongside its `scores`, and a
judgement that would not explain itself never entered the pool — **180 of the 198 attempted
judgments bind**, the other 18 having been discarded at parse time and **recorded nowhere** — the
harness of the day kept its audit trail in memory, so the reasons and the raw responses are gone.
Which skill, judge and round each was is reconstructed in
[`../run5-refusals.md`](../run5-refusals.md), which covers this archive too; the skill-by-skill
comparison with run 5 does not have the same panel behind both sides. That is why `n` varies by
judge (26 to 32) instead of sitting at a flat 33.

**Every verdict recorded here was issued under `mean ≥ 108` AND `mean − stdev ≥ 105` AND the
per-dimension floors.** That second clause was retired on 2026-08-24 by
[`../../docs/adr/0006-confidence-bound-on-the-pooled-mean.md`](../../docs/adr/0006-confidence-bound-on-the-pooled-mean.md),
which replaced it with `mean − 1.0 × stdev/√n ≥ 108` — the gate's first and only change, made
because the retired clause was measured flipping the verdict of a byte-identical file. **These
scorecards are not re-gated and must not be.** Run 5, in `eval/scorecards/`, is the first corpus
judged under the new clause. These files were also written before that clause's two published
statistics (`sem`, `ci_lower`) existed and so do not carry them, which is why
`scripts/ship_floor.py` treats the absence of those two keys as a date rather than as a
disagreement — a stored statistic that *disagrees* with the recompute is still refused.

**This is the corpus two records argue from, which is why it is kept exactly as it is.** Running
today's gate over these bytes reproduces all eleven verdicts as issued — nine SHIP, `AST01` on its
`D3` floor, `AST09` on the bound — and that is the arithmetic behind ADR-0006's "zero verdicts
change";
`tests/test_generate_dashboard.py::test_the_gate_change_moved_no_verdict_on_the_corpus_it_did_not_judge`
re-derives it. It is also the last run in which any skill could be blocked by the retired clause
alone, so `AST09`'s `108.2 − 4.85 = 103.4 < 105` is the worked example in
[`../../docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md`](../../docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md)
and `tests/test_calibration.py` finds it here rather than in whichever corpus is live. And it is
the corpus on which `bedrock/qwen3-235b` came out NON-DISCRIMINATING by *compression* — still
ranking, still using nine distinct values, but with its per-skill means squeezed under the
across-skill floor as the roster rose into the ceiling it never leaves. Run 5 does not reproduce
that flag, so `tests/test_judge_quality.py` pins the mechanism against these bytes.

**Runs 3 and 5 are the corpora these files may be compared against, skill by skill.**
`eval/scorecards-run3/` and `eval/scorecards/` were scored by this same prompt, with the same
panel and the same round count. Eight `SKILL.md` files changed between run 3 and this run, and one
(`AST01`) between this run and run 5 — see "The controlled results" in
[`../../docs/skill-judge-dashboard.md`](../../docs/skill-judge-dashboard.md).

**The first two runs are not comparable to these files.** `eval/scorecards-run1/` and
`eval/scorecards-run2/` were produced by a prompt that sent the eight dimension *names* and their
maxima, none of the rubric's scoring bands, and forbade any prose — which is why not one of their
judgments carries a reason for any score. They measure a different instrument, and must not be
pooled with, differenced against, or trended into anything here. The one comparison that break
does support is between *judges*, and it is in
[`../../docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md`](../../docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md).

Which corpus is which is checkable rather than remembered:
`tests/scripts/test_judge_harness.py` measures it from the judgments themselves.
