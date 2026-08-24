# With/without skill evals — the workspace

**Two smoke iterations are recorded, each covering one case of the authored 33.** They are
here to prove the machinery end to end, not to characterise the skills:

| Iteration | Case | Path taken | Δ pass_rate |
| --- | --- | --- | --- |
| `iteration-1` | `AST01-case-2` | `eval/skill_evals.py` — run and grade inline, one command | 1.00 vs 0.80 = **+0.20** |
| `iteration-2` | `AST01-case-3` | `eval/skill_evals.py --no-grade`, then `eval/skill_eval_grade.py grade` + `aggregate` + `review` | 1.00 vs 0.20 = **+0.80** |

One case is not a result about a skill. The published page,
[`docs/skill-eval-report.md`](../../docs/skill-eval-report.md), prints each iteration's
coverage against the whole corpus for exactly that reason.

`python3 eval/skill_evals.py` writes the next unused integer — a prior iteration is never
overwritten, because a corpus you can overwrite is a corpus you cannot measure change
against. `--iteration N` resumes into an existing one.

## What this surface answers, and what the other two answer

This repository publishes three independent kinds of evidence. They use different units and
are never averaged together.

| Surface | The question it answers | Where |
| --- | --- | --- |
| **Judge scores** | Is the *text* of a `SKILL.md` well written against the vendored 8-dimension rubric? No prompt is ever executed. Unit: a total out of 120. | `eval/scorecards*/`, [`docs/skill-judge-dashboard.md`](../../docs/skill-judge-dashboard.md) |
| **Detector F1** | Do the shipped Python check scripts separate this repository's own labelled vulnerable/clean fixtures? Real output measurement — of the scripts, not of an agent. Unit: precision/recall/F1 per category. | `fixtures/`, [`docs/f1-report.md`](../../docs/f1-report.md) |
| **With/without evals** | Does an agent *holding* a skill behave better than the same agent holding nothing? Unit: the fraction of a case's hand-authored assertions a graded response satisfied, and the **delta** between the two arms. | this directory, written by [`eval/skill_evals.py`](../skill_evals.py) |

A `pass_rate` here is not an F1 and not a judge total. Nothing in this directory feeds the
ship gate (`scripts/ship_floor.py`), and no number here moves a grade or a verdict on either
of the other two surfaces.

## Layout

Per the convention at <https://agentskills.io/skill-creation/evaluating-skills>:

```
iteration-N/
  <eval-slug>/                     e.g. AST01-case-1
    with_skill/
      outputs/response.md          what the model answered — a text answer is a file
      timing.json                  {"total_tokens": int|null, "duration_ms": int, ...}
      grading.json                 {"assertion_results": [...], "summary": {...}}
      prompt.txt                   (local addition) the exact bytes sent to the agent
      run.json                     (local addition) which arm, which agent model, which inputs
      error.json                   (local addition) written INSTEAD of grading.json on failure
    without_skill/                 the identical prompt and files, minus the skill block
  benchmark.json                   {"run_summary": {with_skill, without_skill, delta}}
  feedback.json                    {"<eval-slug>": "<human note or empty string>"}
```

`prompt.txt`, `run.json` and `error.json` are this repository's three additions to the
convention's file set. `run.json` names the arm and the agent model that produced the run, so
the rule that the agent and the grader must be different models can still be checked by a
process that arrives later — `timing.json`'s two contract fields have no room for it.
`prompt.txt` is what makes "the two arms differ in exactly one respect" auditable after
the run rather than only asserted before it — diff the two and the only difference is the
installed-skill block. `error.json` applies the refusal-ledger doctrine
(`scripts/refusal_ledger.py`) to this surface: a failed run records its stage, its provider
and a redacted excerpt of whatever came back, and is then excluded from `benchmark.json` with
that reason printed in the `excluded` block — never silently dropped, never scored as a zero.

## Reading a benchmark.json honestly

* **`run_summary.delta` is the deliverable.** A skill that grades well on the rubric and does
  not beat its own absence here has not been shown to work.
* **A case counts only when both arms completed.** `counts.cases_excluded` and `excluded`
  say what did not make it and why; a delta computed over two different case sets is not a
  delta.
* **`models` names the agent under test and the grader, and they are always different
  models.** The runner exits rather than let one model grade its own output.
* **`limitations` travels inside the file.** One agent model is one point of evidence, not a
  population.

Every figure is regenerable from the directories beside it:
`python3 eval/skill_evals.py --iteration N --benchmark-only` rebuilds `benchmark.json` from
disk without calling a model, and `tests/test_skill_evals.py` re-derives every published mean
from the per-case rows in the same file.

## The second pass: independent grading and the assertion review

[`eval/skill_evals.py`](../skill_evals.py) runs the agents and grades what they produced in
one pass. [`eval/skill_eval_grade.py`](../skill_eval_grade.py) is a **second, independent
layer over the same workspace**. It never calls an agent: it reads the run directories that
are already here, so a whole iteration can be re-graded by a different grader for the price
of the grading alone, and "did the delta depend on who graded it?" becomes an answerable
question rather than a caveat.

```
python3 eval/skill_eval_grade.py grade --grader bedrock/deepseek-v3.2 --regrade
python3 eval/skill_eval_grade.py review        # writes assertion-review.json
python3 eval/skill_eval_grade.py --check review
```

It adds one file to the layout above:

```
iteration-N/
  assertion-review.json            every assertion, classified across the two arms
```

**It will not overwrite a `benchmark.json` that `eval/skill_evals.py` wrote.** Two
aggregators writing one path under two shapes turns a published delta into a function of
which module ran last; `aggregate` refuses and names the owner unless `--force` says
otherwise.

### Reading assertion-review.json

Aggregate statistics hide patterns, and a mean is the easiest place for a broken assertion to
hide. Every assertion lands in exactly one bucket, with the grader's own evidence from both
arms beside it:

| Bucket | What it tells you |
| --- | --- |
| `passed_with_failed_without` | **The headline.** The skill demonstrably added value here — this is the evidence it works, and it belongs at the top of any report. |
| `failed_with_passed_without` | **Regressions.** The agent holding nothing did better. Not one of the three buckets the guidance names; recorded because an assertion the skill makes worse must not be invisible. |
| `passed_in_both` | Tells you nothing about the skill. Candidates for removal or for being made harder — each one costs two runs and discriminates nothing. |
| `failed_in_both` | A broken assertion, or a case too hard for both arms. Read these before believing any pass rate. |
| `mixed_across_repeats` | The same assertion disagreed with itself across repeats. This is the harness's noise floor and it bounds how small a delta is readable. |
| `incomplete` | Graded in one arm only. |

### Two safeguards worth knowing about before reading a number

**Grading is blind, and the claim is narrow.** The grader is told only an opaque token; the
prompt for one arm and the prompt for the other are byte-identical apart from that token, arm
words are scrubbed out of the output text as well as out of the labels, and a prompt that
still names an arm raises instead of being sent. What blinding cannot remove is stated rather
than claimed away: an agent holding a skill writes like one, and a sufficiently attentive
grader may still infer the arm from the answer's own shape.

**A PASS must quote the output.** "The output is correct" is not evidence. Every PASS is
checked for a span that actually occurs in the graded answer — a quotation, or a `file:line`
that resolves. One that has none is re-asked with a corrective instruction and, if it still
has none, flipped to FAIL and recorded as `evidence_rejected`, with the grader's original
verdict preserved beside it so the flip is auditable. For an assertion about something the
answer must *not* do, the grader is required to quote the passage where it would have
appeared and say what is there instead.

Assertions a script can settle — a file exists, a file parses as JSON, a literal is absent —
are settled by a script rather than a model, and every result records which mechanism decided
it. As authored today none of this repository's 162 assertions is mechanical; they are all
semantic claims about a response, and
`tests/test_skill_eval_grade.py::test_no_authored_assertion_is_script_decidable_today` records
that count so the day one becomes mechanical is loud rather than quiet.
