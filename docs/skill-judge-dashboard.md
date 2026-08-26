# Skill-Judge Scorecard Dashboard

Pooled eight-dimension judge results for the eleven skills in this repository, scored
against the pinned skill-judge rubric and gated by the ship rule in
`scripts/ship_floor.py`.

This repository is an independent community implementation. It is **not** an official
OWASP project and carries no OWASP endorsement — see [`../README.md`](../README.md) and
[`../NOTICE`](../NOTICE).

> ## Which rule produced the table on this page
>
> **Every verdict published here is run 5's, issued under the rule in force:** `mean ≥ 108` AND
> `mean − 1.0 × stdev/√n ≥ 108` AND the per-dimension floors. Run 5 is the **first corpus judged
> under that second clause**, which [ADR-0006](adr/0006-confidence-bound-on-the-pooled-mean.md)
> adopted on 2026-08-24 in place of the retired `mean − stdev` clause, measured against
> `POOLED_LOWER_BOUND` (105) — a confidence bound on the mean instead of a spread statistic.
> **The gate has been changed exactly once, and that is the change.** The constant was written down and the record accepted *before* this run was scored,
> which is the whole of why this board is readable as a measurement.
>
> **Run 4 is archived at `eval/scorecards-run4/` exactly as issued**, gated by the retired clause.
> It is **not** re-gated and no run-4 verdict is restated here in the new clause's words. What is
> checkable — and checked by
> `tests/test_generate_dashboard.py::test_the_gate_change_moved_no_verdict_on_the_corpus_it_did_not_judge`
> — is that running today's gate over those frozen bytes reproduces all eleven run-4 verdicts.
> **The rule change moved no verdict when it was adopted.** That is what licenses reading the run-5
> board as a statement about the skills rather than about the rule.
>
> The rule now in force is published under [The ship rule](#the-ship-rule) below.

> ## Judged run recorded — run 5, 2026-08-24
>
> **Eleven of eleven skills clear the ship rule, and every dimension floor is clear on every
> skill.** 11 skills × 3 rounds × 6 providers were attempted; **188 judgments bind** and 10 were
> discarded, so `n` varies by judge (30 to 33) rather than sitting at a flat 33. **Those ten were
> discarded without being recorded**, and which they were is reconstructed after the fact in
> [`../eval/run5-refusals.md`](../eval/run5-refusals.md): AST01 lost the two judges that scored it
> lowest, and its verdict does not survive the most natural assumption about what they would have
> scored. Read the eleventh ship with that attached. Runs 1-4 are retained under `eval/scorecards-run1/`,
> `eval/scorecards-run2/`, `eval/scorecards-run3/` and `eval/scorecards-run4/`.
>
> **The same board is also 8 of 11 without one judge, and 10 of 11 if AST01's two lost judgments
> are refilled at the means of the judges that lost them.** Both figures are measured, not
> rhetorical, and both are in [How fragile 11 of 11 is](#how-fragile-11-of-11-is) — the next section,
> deliberately ahead of everything else on this page.
>
> **Two verdicts moved since run 4, and only one of them followed an edit.** `AST01` — the only
> `SKILL.md` touched between the two runs — gained the anti-pattern `NEVER` section the other eight
> skills received a run earlier, and went BLOCKED (`D3` 12.2) → SHIP (`D3` 14.2). `AST09` was
> **not edited** and moved BLOCKED → SHIP anyway, on a pooled mean that rose 108.2 → 111.1. Both are
> in [The controlled results](#the-controlled-results) below, and the second is the more instructive
> one.
>
> Regenerate after a run with:
>
> ```bash
> python3 eval/run_judge_matrix.py --rounds 3   # writes eval/scorecards/*.json
> python3 eval/generate_dashboard.py            # rewrites the table below
> python3 eval/calibration.py                   # per-judge bias, judge-quality diagnostics and the
>                                               # robustness block; also writes
>                                               # eval/judge-quality.json and eval/robustness.json
> ```

---

## How fragile 11 of 11 is

**Three statements about this board are true at the same time, and a reader needs all three.**

1. **As measured, it is 11 of 11.** Every verdict published on this page is that board, issued
   under the rule in force over the judgments that were actually recorded. Nothing below revises it.
2. **Without the panel's least discriminating judge, it is 8 of 11.** Drop `bedrock/qwen3-235b` —
   flagged **COARSE** below, returning the full 120 on 34% of its judgments against 16% in the run
   it was flagged NON-DISCRIMINATING on — and `AST01`, `AST07` and `AST08` all fall through the
   confidence bound.
3. **One of the eleven does not survive imputation of its own missing judgments.** `AST01` lost two
   of its eighteen attempts, and both were from the two judges that scored `AST01` lowest. Refill
   them at those judges' own observed means on `AST01` and it lands at `ci_lower` **107.6** —
   `BLOCKED`.

Every figure in this section is recomputed from `eval/scorecards/*.json` by
`python3 eval/calibration.py`, written to [`../eval/robustness.json`](../eval/robustness.json), and
re-derived at test time by `tests/test_robustness.py`, so the numbers on this page cannot drift from
the corpus. Both analyses re-run `ship_floor.aggregate_verdict` — the live gate, not a copy of it —
over a panel that was never recorded. **No judge is excluded from any published figure, no imputed
value is written into any scorecard, and no verdict is re-issued.** What is published here is the
margin around the board, which the count alone cannot show.

### Leave one judge out

Each row drops one judge's judgments entirely and re-runs the gate over what remains.

| Judge dropped | Judgments dropped | Board without it | Newly blocked (`ci_lower`) |
| --- | ---: | ---: | --- |
| `bedrock/qwen3-235b` | 32 | **8 of 11** | `AST01` 106.7 · `AST07` 107.7 · `AST08` 107.5 |
| `anthropic-compatible/glm-5.2` | 30 | 10 of 11 | `AST01` 107.2 |
| `claude-cli/sonnet` | 33 | 10 of 11 | `AST01` 107.7 |
| `bedrock/deepseek-v3.2` | 30 | 11 of 11 | — |
| `bedrock/gpt-oss-120b` | 33 | 11 of 11 | — |
| `bedrock/nova-pro` | 30 | 11 of 11 | — |

**`AST01` is blocked by three of the six single-judge exclusions.** It is not a skill that clears
the bar and happens to lose one prop; it clears the bar only on the panel as constituted. `AST07`
and `AST08` are blocked by one exclusion each, and both by the same one. Three of the eleven skills
— `AST01`, `AST07`, `AST08` — can be blocked by dropping a single judge; the other eight cannot.

**The judge the board leans on is the one this page flags.** `bedrock/qwen3-235b` is the most
generous reader on the panel by five points, 79% of its dimension scores sit at a dimension's
maximum, and on an unchanged rule it has come out NON-DISCRIMINATING in runs 2 and 4 and COARSE in
runs 3 and 5 — a verdict that keeps crossing a line it sits on. It is pooled into every published
figure, by the declare-and-record doctrine described under
[Judge quality](#judge-quality-is-each-judge-measuring-or-ranking-nothing-diagnostics-only), and
this table is the price of that decision stated in ships. Nothing here proposes dropping it:
excluding a judge from the binding pool is a human decision that needs its own ADR, and this is
the evidence such a record would have to weigh.

### Missing-data sensitivity

Six skills pooled fewer judgments than they attempted. Each row refills that skill's gap with the
**same provider's own observed mean on the same skill** — the least-assuming number available,
because it assumes only that a judge would have scored roughly what it scored on its other rounds
of that same file — and re-runs the gate.

| Skill | Pooled | Attempted | Mean → imputed | `ci_lower` → imputed | Verdict → imputed |
| --- | ---: | ---: | ---: | ---: | --- |
| `AST01` | 16 | 18 | 110.1 → 109.2 | 108.4 → **107.6** | SHIP → **BLOCKED** |
| `AST03` | 16 | 18 | 112.2 → 112.3 | 111.0 → 111.3 | SHIP → SHIP |
| `AST05` | 16 | 18 | 110.6 → 110.9 | 109.4 → 109.8 | SHIP → SHIP |
| `AST06` | 16 | 18 | 112.1 → 112.0 | 111.1 → 111.0 | SHIP → SHIP |
| `AST07` | 17 | 18 | 110.2 → 110.2 | 109.0 → 109.1 | SHIP → SHIP |
| `advisory` | 17 | 18 | 112.2 → 112.4 | 111.1 → 111.4 | SHIP → SHIP |

**Five of the six are insensitive to their gap. `AST01` is not**, because its gap is not a random
sample of its panel: `bedrock/deepseek-v3.2` averages 100.5 on `AST01` and `bedrock/nova-pro`
averages 104.5, against a pooled 110.1, and it is precisely those two judges' round-3 judgments
that never arrived. The eleventh ship therefore depends on two judgments nobody can produce — see
[`../eval/run5-refusals.md`](../eval/run5-refusals.md) for what survived of them and what did not.

**The imputation is load-bearing, and saying so is the point.** Refilling at the *pooled* mean
instead would leave every mean untouched and shrink every `sem`, turning a hole in the record into
free confidence; refilling at each judge's own mean assumes only within-judge consistency. Neither
assumption is knowable from what survived, which is the argument for recording refusals rather than
reasoning about them afterwards.

### Reading the three numbers together

`AST01` is the skill that the gate change bought (it does not clear the retired
`mean − σ ≥ 105` clause on this run — see [The ship rule](#the-ship-rule)), the skill three of six
single-judge exclusions block, and the skill whose own missing judgments flip it. Those are three
independent ways of asking whether one row is real, and it fails all three. **Eleven of eleven is
what was measured; it is not eleven results of equal strength**, and the eleventh is the weakest
row on the board by every check this repository knows how to run.

---

## What 11 of 11 is, and what it is not

A clean board is the easiest number on this page to over-read, so the five things it does not
mean are stated beside it rather than at the bottom.

1. **The corpus is self-authored.** The same project wrote the eleven skills, the fixtures, the
   scenario registry and the rubric-grounded judge prompt. A high pooled score is evidence of
   **internal consistency** — the artifacts say what this repository's own rubric asks for — and
   it is not external validation by anybody. No third party has scored these files.
2. **The panel still disagrees by most of a grade band.** Between the most generous judge and the
   harshest there is an **11.4-point spread** on the same eleven files, and it is systematic: no
   judge moves more than 2.3 points between its own rounds. A pooled mean is a statement about
   *the rubric as read by these six judges*, never about a skill in the abstract
   ([ADR-0005](adr/0005-judge-panel-calibration-and-the-lower-bound.md), "Cross-repo implication").
3. **`k = 1.0` is one standard error of margin and is deliberately not a confidence level.** The
   judgments behind a pooled mean are not independent draws: they are six judges read about three
   times each, and the judges carry large fixed offsets. Measured on run 4, the panel's
   intraclass correlation is **0.666** and its design effect **2.15**, so `stdev/√n` understates
   the true standard error of the mean by about **1.47×** and `k = 1.0` delivers roughly 0.68
   design-corrected standard errors. The clause is quoted in points — it moves the effective bar
   from 108.0 to about 109.2 at this panel — and never in percent. ADR-0006 records the shortfall
   as its first item of future work; run 5 does not close it.
4. **Two of the eleven clear the confidence bound by less than a point.** `AST01` ships at
   `ci_lower` 108.4 and `AST08` at 108.7, against a bar of 108. By this repository's own margin
   doctrine — *a threshold cleared by 0.38 is not a threshold cleared* — those two rows are inside
   the run-to-run movement of the instrument that produced them, and neither should be read as
   settled.
5. **A verdict moved on a file nobody edited, under the new clause as well as the old one.**
   `AST09` went BLOCKED → SHIP on a mean that rose 2.9 points while its `SKILL.md` stayed
   byte-identical. ADR-0006 removed the gate's dependence on *panel dispersion*; it did not, and
   could not, remove the run-to-run movement of the pooled mean itself. The board is a draw from a
   distribution, and this run drew well.

None of that makes 11 of 11 false. It makes it a measurement with units.

---

## The controlled results

Two runs in a row changed exactly one thing and left the instrument alone, which is the only
arrangement that supports a skill-by-skill reading. The pair is worth more than the ship count.

### Run 4 → run 5: one treated skill, ten controls

Between run 4 (`eval/scorecards-run4/`) and run 5 (`eval/scorecards/`) the judge prompt, the
pinned rubric, the panel roster and the round count were held fixed; the gate's second clause
changed by [ADR-0006](adr/0006-confidence-bound-on-the-pooled-mean.md). That change moves no
verdict on the run-4 corpus — **and it moves exactly one on run 5, `AST01`, which is the treated
row of this very table.** Read the `D3` column as the controlled measurement and the verdict
column with the caveat below it. **Exactly one `SKILL.md` was edited: `AST01`**, which
gained the anti-pattern `NEVER` section the eight treated skills received between runs 3 and 4.
Every other skill is byte-identical across the two runs.

| Skill | Edited | `D3` run 4 → run 5 | Mean run 4 → run 5 | Verdict run 4 → run 5 |
| --- | --- | ---: | ---: | --- |
| `AST01` | **yes** | 12.2 → 14.2 (+2.0) | 108.5 → 110.1 (+1.6) | BLOCKED (`D3`) → **SHIP** |
| `AST02` | no — control | 14.2 → 14.1 (−0.1) | 112.3 → 111.8 (−0.5) | SHIP → SHIP |
| `AST03` | no — control | 14.2 → 14.3 (+0.1) | 110.7 → 112.2 (+1.5) | SHIP → SHIP |
| `AST04` | no — control | 14.3 → 13.9 (−0.4) | 112.6 → 111.6 (−1.0) | SHIP → SHIP |
| `AST05` | no — control | 14.1 → 14.1 (0.0) | 111.2 → 110.6 (−0.6) | SHIP → SHIP |
| `AST06` | no — control | 14.3 → 14.3 (0.0) | 111.3 → 112.1 (+0.8) | SHIP → SHIP |
| `AST07` | no — control | 14.1 → 14.5 (+0.4) | 110.3 → 110.2 (−0.1) | SHIP → SHIP |
| `AST08` | no — control | 13.2 → 13.4 (+0.2) | 110.8 → 109.7 (−1.1) | SHIP → SHIP |
| `AST09` | no — control | 13.9 → 14.3 (+0.4) | 108.2 → 111.1 (**+2.9**) | BLOCKED (bound) → **SHIP** |
| `AST10` | no — control | 14.8 → 14.8 (0.0) | 113.2 → 112.4 (−0.8) | SHIP → SHIP |
| `advisory` | no — control | 14.0 → 13.9 (−0.1) | 112.2 → 112.2 (0.0) | SHIP → SHIP |

**The treated row's verdict flip is not purely a treatment effect, and the `D3` column is where
the controlled result lives.** `AST01`'s `SHIP` requires the clause ADR-0006 adopted: under the
retired `mean − σ ≥ 105` it reads `110.1 − 6.65 = 103.4` and this row is `BLOCKED (D3)` →
`BLOCKED (lower bound)` — a verdict that never changes. The `D3` movement is untouched by any of
that: `D3` is compared against a fixed floor of 13, which neither clause has ever altered, so
12.2 → 14.2 against ten controls holding still is the same measurement under either rule. Quote
the dimension, not the verdict, when quoting this experiment; "`AST01` was repaired and then
shipped" is two findings wearing one sentence, and only the first is controlled.

**On `D3` the treatment replicates; on the pooled mean it does not separate from noise.** `AST01`
rose +2.0 on `D3` and crossed the floor it had fallen through, while the ten controls moved between
−0.4 and +0.4 with a mean of +0.05 — the same contrast the eight-skill pass produced a run earlier,
now reproduced on a ninth skill with ten controls holding still. The pooled mean tells a weaker
story: `AST01` gained +1.6, and the untouched `AST09` gained **+2.9**. A treatment effect smaller
than the largest control movement is not a treatment effect you can read off the total, which is
exactly why the dimension the edit targets is the place to look.

**`AST09` is the row to be honest about.** It ships this run without a character changing, because
its pooled mean rose 2.9 points. That is not the defect ADR-0006 fixed — its `ci_lower` went 107.0
→ 110.0, and the movement is in the mean, not in the spread — but it is the same lesson one level
up: pooled judge scores are a distribution, and eleven skills read three times by six judges will
move a point or two in either direction for no reason attributable to the artifact. Ten unedited
files moved between −1.1 and +2.9 this run. Any single skill's mean should be read with that band
around it.

### Run 3 → run 4: the eight-skill anti-pattern pass (historical)

This is the earlier arm, recorded when run 4 was the live corpus and kept because it is the
evidence the `D3` treatment works. Between run 3 (`eval/scorecards-run3/`) and run 4
(`eval/scorecards-run4/`) the prompt, rubric, roster, round count and every gate constant were
fixed, and **eight skills — `AST02`-`AST07`, `AST09`, `AST10` — gained an explicit anti-pattern
`NEVER` section**, seven or eight prohibitions apiece, each grounded in something a reader can open
(a check id in that module's `CHECK_COVERAGE`, a scenario id and tier in `scenarios/registry.yaml`,
a coverage-matrix debt item, or a cited file line). `AST01`, `AST08` and `advisory` were
deliberately left untouched as controls.

| Skill | Anti-pattern section added | `D3` run 3 → run 4 | Mean run 3 → run 4 | Verdict run 3 → run 4 |
| --- | --- | ---: | ---: | --- |
| `AST02` | yes | 11.8 → 14.2 (+2.4) | 108.7 → 112.3 (+3.6) | BLOCKED (`D3`) → **SHIP** |
| `AST03` | yes | 12.2 → 14.2 (+2.0) | 107.9 → 110.7 (+2.8) | BLOCKED (`D3`) → **SHIP** |
| `AST04` | yes | 12.4 → 14.3 (+1.9) | 108.7 → 112.6 (+3.9) | BLOCKED (`D3`) → **SHIP** |
| `AST05` | yes | 12.9 → 14.1 (+1.2) | 107.9 → 111.2 (+3.3) | BLOCKED (`D3`) → **SHIP** |
| `AST06` | yes | 11.5 → 14.3 (+2.8) | 107.4 → 111.3 (+3.9) | BLOCKED (`D3`) → **SHIP** |
| `AST07` | yes | 12.1 → 14.1 (+2.0) | 106.6 → 110.3 (+3.7) | BLOCKED (`D2`, `D3`) → **SHIP** |
| `AST09` | yes | 12.3 → 13.9 (+1.6) | 107.4 → 108.2 (+0.8) | BLOCKED (`D3`) → BLOCKED (lower bound) |
| `AST10` | yes | 12.4 → 14.8 (+2.4) | 108.6 → 113.2 (+4.6) | BLOCKED (`D3`) → **SHIP** |
| `AST01` | **no — control** | 13.1 → 12.2 (−0.9) | 109.8 → 108.5 (−1.3) | BLOCKED (bound) → BLOCKED (`D3`) |
| `AST08` | **no — control** | 13.5 → 13.2 (−0.3) | 110.3 → 110.8 (+0.5) | BLOCKED (bound) → **SHIP** |
| `advisory` | **no — control** | 14.1 → 14.0 (−0.1) | 112.3 → 112.2 (−0.1) | SHIP → SHIP |

**Every treated skill improved. No control did.** All eight rose on `D3`, by +1.2 to +2.8, and all
eight crossed the floor of 13 they had been under. All three controls moved *down* on `D3` — −0.1,
−0.3 and −0.9 — which is what a null treatment looks like against run-to-run movement.

**A `D3` margin of 0.1 was treated as clearance, and it should not have been.** `AST01` was excluded
from that pass because it measured `D3` 13.1 against a floor of 13; it measured 12.2 in run 4 and
became the only skill on the board blocked by a floor. It was then treated, and run 5 is what that
repair measured. `AST08` was excluded on a margin of 0.5, fell to 13.2, and sits at 13.4 today — the
same finding, still open, one dimension away from a block.

Two things that pair of tables does **not** say. `AST08`'s run-3 → run-4 BLOCKED → SHIP was **not**
an improvement: its `SKILL.md` was byte-identical and its `D3` fell. It shipped because the panel's
sigma narrowed and lifted its `mean − sigma` from 104.6 to 106.1 — the lower-bound defect
[ADR-0005](adr/0005-judge-panel-calibration-and-the-lower-bound.md) describes, visible in the
flattering direction. **That row is the evidence that retired the clause**, and
[ADR-0006](adr/0006-confidence-bound-on-the-pooled-mean.md) replaced it on the strength of exactly
this comparison; under the confidence bound `AST08` is SHIP in both runs (108.8, then 109.7). And a
controlled result over eleven artifacts with one treatment arm is evidence, not proof: the pooled
mean rose across the board between runs 3 and 4, so only the treated-versus-control *contrast* is
attributable. The contrast is the finding. `D3` anti-patterns are load-bearing rather than
decorative, and this repository now has two runs of its own measurement saying so.

**The claim has to stop one step short of the one it is tempting to make, and `AST08` is why.**
`AST08` is the only skill on the board with **no consolidated anti-pattern section of any kind** —
the string `NEVER` does not appear in its `SKILL.md` — and it scores `D3` **13.4**, *above where
every one of the eight treated skills started* (11.5 to 12.9) and above two of them after
treatment. Its prohibitions are distributed through its decision rules and its per-check boundaries
instead of gathered under a heading, and the judges scored that. So the measurement supports the
narrow claim — **adding** a grounded anti-pattern section raised `D3` on nine skills that were at
or under the floor, reproducibly, against controls that did not move — and it does **not** support
"a consolidated `NEVER` section is what makes `D3` good", nor "a skill without one scores low".
`AST08` is the counterexample this repository ships, and it is one dimension away from a block for
reasons that have nothing to do with the section it does not have.

---

## Judge calibration (measured, diagnostics only)

Regenerate with `python3 eval/calibration.py`. Panel: 6 providers x 11 skills = 188 binding judgments, pooled mean of **111.3**.

| Judge | n | mean | bias | round means |
| --- | ---: | ---: | ---: | --- |
| `bedrock/qwen3-235b` | 32 | 117.7 | +6.5 | 117.7 / 117.3 / 118.2 |
| `anthropic-compatible/glm-5.2` | 30 | 112.6 | +1.3 | 112.1 / 113.3 / 112.3 |
| `bedrock/deepseek-v3.2` | 30 | 111.8 | +0.5 | 111 / 111.7 / 112.9 |
| `claude-cli/sonnet` | 33 | 110.4 | -0.9 | 110 / 110.6 / 110.5 |
| `bedrock/nova-pro` | 30 | 109.0 | -2.3 | 109.5 / 108.5 / 108.8 |
| `bedrock/gpt-oss-120b` | 33 | 106.3 | -4.9 | 107.2 / 106.9 / 104.9 |

An **11.4-point spread** separates the most generous judge from the harshest, while no judge's own
round-to-round means differ by more than **2.3 points** — so this is systematic calibration bias,
not measurement noise. The panel closed up over three runs and has now stopped: the spread was
16.5 in run 2, 15.4 in run 3, 11.6 in run 4 and 11.4 here. Four of the six judges sit within 2.3
points of the pooled mean and three of those within 1.3; what remains is carried by the two ends,
`bedrock/qwen3-235b` at +6.5 and `bedrock/gpt-oss-120b` at -4.9, neither of which moved
meaningfully since run 4 (+6.7 and -4.9 there).
Per-skill sigma runs **4.16 to 6.65** (median 4.75) against the 3.3 `ship_floor.py` was calibrated on, which would make the retired `mean - sigma >= 105` demand a mean of **109.2 to 111.7** (91.0% to 93.0% of 120) rather than the 108 (90.0%) it named.
That implied-bar arithmetic describes the clause **as it stood through run 4** and is why it was
retired; it is regenerated here rather than remembered, because it is the evidence
[ADR-0005](adr/0005-judge-panel-calibration-and-the-lower-bound.md) rests on. The rule now in force
asks `mean − 1.0 × stdev/√n ≥ 108`, whose bar at this panel's median sigma and n is **109.15** and
falls toward 108 as evidence accumulates. These figures are diagnostics: no gate constant is read
from them, and none was changed on the strength of them — the one change is recorded in
[ADR-0006](adr/0006-confidence-bound-on-the-pooled-mean.md), whose constant was fixed before the run
it judges.

## Judge quality: is each judge measuring, or ranking nothing? (diagnostics only)

Regenerate with `python3 eval/calibration.py`, which also writes the machine-readable
`eval/judge-quality.json`. Every figure below is derived from `eval/scorecards/*.json` and
re-derived at test time by `tests/test_judge_quality.py`.

The calibration table above asks whether a judge's number is in the *right place*. These four
signals ask the prior question — whether the number is a **measurement** at all.

| Judge | n | distinct values | across-skill σ | across-skill variance | multiples of 5 | at dimension max | full 120 | own-round spread | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `bedrock/qwen3-235b` | 32 | 9 | 1.22 | 1.48 | 79% | 79% | 34% | 3.36 | COARSE |
| `anthropic-compatible/glm-5.2` | 30 | 10 | 1.84 | 3.37 | 28% | 28% | 0% | 2.82 | DISCRIMINATING |
| `bedrock/deepseek-v3.2` | 30 | 14 | 4.22 | 17.78 | 40% | 40% | 3% | 7.27 | DISCRIMINATING |
| `bedrock/gpt-oss-120b` | 33 | 11 | 1.41 | 2.00 | 11% | 10% | 0% | 4.36 | DISCRIMINATING |
| `bedrock/nova-pro` | 30 | 9 | 2.32 | 5.37 | 15% | 15% | 3% | 6.55 | DISCRIMINATING |
| `claude-cli/sonnet` | 33 | 11 | 1.26 | 1.59 | 20% | 20% | 0% | 3.73 | DISCRIMINATING |

*distinct values* — how many different numbers the judge used across all of its dimension scores
(eight per judgment). *across-skill σ / variance* — the spread of its own per-skill mean totals;
near zero means it placed every skill in the same spot. *multiples of 5* — the share of its
dimension scores divisible by five. *at dimension max* / *full 120* — how often it returned the top
of a dimension, and the top of the rubric. *own-round spread* — the mean gap between its own rounds
on one skill, which is what separates a judge that is *noisy* from one that is *constant*.

**`bedrock/qwen3-235b` is COARSE on this panel and is not flagged, and the way it got there is the
clearest thing this table has ever shown.** Its verdict has now taken three different values across
four runs, on a rule that has not changed:

| Run | Prompt | distinct values | per-skill means | across-skill σ | Verdict |
| --- | --- | ---: | --- | ---: | --- |
| 2 | dimension names only | 3 | 120.0 on all eleven | 0.00 | NON-DISCRIMINATING |
| 3 | rubric bands quoted | 9 | 114.7 – 119.7 | 1.38 | COARSE |
| 4 | rubric bands quoted | 7 | 116.3 – 119.3 | 0.94 | NON-DISCRIMINATING |
| 5 | rubric bands quoted | 9 | 116.3 – 120.0 | 1.22 | COARSE |

Under the old prompt it returned the rubric total eleven times out of eleven, drawn from three
distinct values — 10, 15 and 20, precisely the three dimension maxima — and ranked nothing at all.
It has ranked ever since. Run 4 flagged it again for a different reason: its floor rose while its
ceiling did not, because the *skills* improved into the top of the scale it is willing to use, and
its per-skill means compressed into a 3.0-point band that fell under the `< 1.0` across-skill floor.
Run 5 puts it back over that floor at 1.22, on a slightly wider band of its own — 116.3 to 120.0
against 116.3 to 119.3.

**Read that as fragility, not as a repair.** Nothing in the judge's behaviour improved to earn it:
79% of its dimension scores still sit at a dimension's maximum, and it now returns the full 120 on
**34%** of its judgments against 16% in run 4 — more saturated than the run it was flagged on, not
less. Its ceiling has not moved in three runs while the roster underneath it has, so its verdict
will keep crossing a threshold it sits on, in both directions, for reasons that are about the
population rather than about the judge. It is the most generous reader on the panel, five points
clear of the next, and it is pooled into every figure on this page in every one of those states.
The compression mechanism is pinned against the frozen run-4 corpus by
`tests/test_judge_quality.py`, so it stays checked now that the live panel no longer reproduces it.

The thresholds are anchored to the rubric or to chance, never to this panel — a bar chosen after
seeing which judge it catches is a name for that judge, not a bar:

| Signal | Flag when | Why that number |
| --- | --- | --- |
| Distinct dimension values | < 4 | Every dimension in the pinned rubric defines exactly four score bands (D1: 0–5 / 6–10 / 11–15 / 16–20). A judge with fewer distinct values than one dimension has bands cannot express that dimension's scale even once. |
| Across-skill σ | < 1.0 points | Deliberately extreme: not "agrees too much" but "returned one number". This panel places its skills 109.7 to 112.4 apart and the grade bands are twelve points wide, so a judge whose per-skill means fit in a one-point window has resolved that span to a single verdict. On run 2 the flat judge measured 0.00; on run 3 the lowest was 1.38; on run 4 it was 0.94; on run 5 it is 1.22. |
| Multiples of 5 | ≥ 60% | A judge drawing uniformly at random would hit a multiple of five about **25%** of the time (5 of 21 values on D1, 4 of 16 on the six 15-point dimensions, 3 of 11 on D7). 60% is ~2.4× chance and unreachable by luck. Advisory only — it yields `COARSE`. |
| At dimension max / full 120 | ≥ 50% | The rubric's top bands are reserved language ("pure knowledge delta — every paragraph earns its tokens"). A judge awarding them to the majority of what it sees has merged the top band with everything under it. Advisory only — it yields `COARSE`. |

Only the first two decide `NON-DISCRIMINATING`, because that is what the verdict means: a judge that
returns one number ranks nothing, whatever its granularity. Granularity and saturation explain the
*mechanism* and are reported beside it. A judge can be coarse without being flat — a much milder
problem, and one the rule must not conflate with this one. `bedrock/qwen3-235b` is the worked
example of the distinction in every direction available: flat on run 2, coarse on run 3,
flat-by-compression on run 4, and coarse again on run 5 without ever going back to returning one
number.

### What excluding a flagged judge would do — shown, not applied

**No judge on this panel is flagged NON-DISCRIMINATING; there is nothing to exclude.** That is the
sentence `eval/calibration.py` prints for run 5, and it is published here rather than left to
inference: a page that simply stops showing an exclusion column looks identical to a page whose
filter ran silently. There is no *without* column this run because there is nobody to drop.

| Figure | Run 5, as published (every judge pooled) |
| --- | ---: |
| Judgments pooled | 188 |
| Pooled mean | 111.3 |
| Between-judge spread | 11.4 |
| Per-skill σ, median | 4.75 |
| Per-skill σ, range | 4.16–6.65 |

The one run where a column *was* printed is run 4, and it is the size of the effect a reader should
keep in mind: dropping `bedrock/qwen3-235b` there moved the pooled mean 111.0 → 109.5 and the
between-judge spread 11.6 → 6.0. Nothing was dropped then either. `eval/calibration.py` prints the
comparison and refuses to apply it: deciding whether a flagged judge stops binding is a **human
decision** and needs its own superseding record, written before the run it applies to. Run 3 is the
standing case for having kept this judge — it is the judge the prompt fix repaired, and a panel that
had dropped it in run 2 would never have measured that. The same verdicts, thresholds and deltas are
in `eval/judge-quality.json` for anything that needs to read them mechanically.

### Runs 1 and 2 were scored without the rubric's bands

Run 1 (`eval/scorecards-run1/`) and run 2 (`eval/scorecards-run2/`) were judged by the
pre-2026-08-23 prompt, which sent the eight dimension names and their maxima and **none of the
rubric bands**, and forbade prose. Their absolute values are **weaker evidence** than the figures on
this page: every mean and every grade in those two archives rests on six private scales invented
from eight labels, which is also the most likely explanation for a judge that could return the
maximum eleven times without contradiction. What survives from them is the *relative* picture — the
bias ordering, the between-judge spread, and their judge-quality verdicts, which turn on the shape
of a judge's output rather than on where the rubric would have put it. They are kept unedited as the
evidence for that defect. Run 3 (`eval/scorecards-run3/`) and run 4 (`eval/scorecards-run4/`) are
frozen for a different reason: both were scored by the same prompt as run 5, so they are the
*comparable* archives and the two halves of the controlled results above. This page's tables are
run 5 throughout, except where a row says otherwise.

## The rubric — 8 dimensions, 120 points

Pinned by SHA in `scripts/ship_floor.py` (`RUBRIC_SHA =
3027f20f3181758385a1bb8c022d4041dfb4de84`). A recorded scorecard whose `rubric_sha`
does not match that constant is `BLOCKED` before any arithmetic runs: a score against a
different rubric version is not a lower score, it is a different measurement.

`Floor` is the per-dimension minimum from `ship_floor.FLOORS`, applied to the **dimension
mean** across pooled judgments. One dimension below its floor blocks the skill no matter
how high the total is — the floors exist so a strong total cannot buy its way past a
structurally weak dimension.

| Dimension | Max | Floor | What it measures |
| --- | --- | --- | --- |
| **D1** Knowledge Delta | 20 | 17 | Expert-only knowledge minus what the model already knows. The core dimension, and the one this repo's own S-006 failure shape targets: a `SKILL.md` restating generic definitions scores ≤5 here and blocks on the floor alone. |
| **D2** Mindset + Appropriate Procedures | 15 | 13 | Whether the skill shapes *how* to think about the category, not just what to do — thinking frameworks plus domain-specific procedures. |
| **D3** Anti-Pattern Quality | 15 | 13 | A specific NEVER list with the reasoning behind it. Generic warnings ("be careful", "consider edge cases") score in the 4–7 band. **It bound eight of eleven skills in run 3, and the eight that were repaired against it are the controlled result above.** |
| **D4** Specification Compliance | 15 | 13 | Valid frontmatter and, above all, a description carrying WHAT, WHEN, and trigger keywords — the text a runtime routes on. |
| **D5** Progressive Disclosure | 15 | 13 | Layering: `SKILL.md` under the line budget, mechanism in `scripts/` and `references/`, explicit load triggers. Enforced mechanically too, by `tests/test_ast_skill_layout_lint.py`. |
| **D6** Freedom Calibration | 15 | 13 | Whether the prescriptiveness matches the task — rigid procedure for fragile operations, latitude for judgement calls. |
| **D7** Pattern Recognition | 10 | 8 | Whether the package applies a recognisable skill pattern coherently rather than improvising a structure. |
| **D8** Practical Usability | 15 | 13 | Whether a reader can actually act on it, including edge cases and error handling. |
| **Total** | **120** | — | |

### Grade bands

| Grade | Total | Meaning |
| --- | --- | --- |
| **A** | ≥ 108 | Grade-A bar. Necessary for ship, not sufficient — see the ship rule below. |
| **B** | 96 – 107 | Solid; below this repo's bar. |
| **C** | 84 – 95 | Usable with gaps. |
| **D** | 72 – 83 | Substantial rework needed. |
| **F** | < 72 | Does not function as a knowledge package. |

---

## The ship rule

Skill-judge scoring is **non-deterministic**. Repeated sweeps over byte-identical content
have produced binding means roughly two grade-boundaries apart, with a per-judgment sigma
around 3.3 points. A single judgment is therefore one draw from a distribution, not a
measurement — so ship is defined on the pooled distribution, never on any one round.

A skill ships when **all** of the following hold (`ship_floor.aggregate_verdict`). This is the
rule **in force now**, as changed by
[ADR-0006](adr/0006-confidence-bound-on-the-pooled-mean.md) on 2026-08-24, and it is the rule that
produced the Results table below — run 5 is the first corpus judged under it. The run-4 board in
`eval/scorecards-run4/` was issued under the retired clause and is not re-gated:

| Condition | Constant | Value |
| --- | --- | --- |
| Pooled mean over all recorded judgments | `POOLED_TARGET` | ≥ **108** |
| Confidence bound on that mean, `mean − k × stdev/√n` | `CONFIDENCE_K` = **1.0**, against `POOLED_TARGET` | ≥ **108** |
| Every dimension mean at or above its floor | `FLOORS` | D1 ≥ 17, D2 ≥ 13, D3 ≥ 13, D4 ≥ 13, D5 ≥ 13, D6 ≥ 13, D7 ≥ 8, D8 ≥ 13 |
| Pooled judgment count | `MIN_ROUNDS` | ≥ **4** |
| Aggregation method | `AGG_METHOD` | `multi-round-independent-pooled` |
| Rubric version | `RUBRIC_SHA` | `3027f20f3181758385a1bb8c022d4041dfb4de84` |

The second clause is the one that does the work, and it asks a question the first cannot:
*the point estimate is Grade A, but is the true mean confidently Grade A?* A mean of 110.1
drawn from judgments with a sigma of 6.65 is weaker evidence than the same 110.1 with a sigma
of 4.2, and the gate should be able to say so. At this panel's median sigma (4.75) and n (17)
the clause moves the effective bar from 108.0 to about **109.2**; the bar falls as evidence
accumulates but is bounded below by 108, so volume can never buy a pass for a skill whose true
mean is not Grade A. `k = 1.0` is **one standard error of margin and not a confidence level** —
the judgments inside a pooled mean are clustered in six judges, so the naive standard error is
understated by about 1.47× and no percentage may be attached to this clause. See
[What 11 of 11 is, and what it is not](#what-11-of-11-is-and-what-it-is-not).

**Until 2026-08-24 that clause read `mean − stdev ≥ POOLED_LOWER_BOUND (105)`, and that is the
gate's one and only change.** `mean − stdev` is a *spread* statistic being used as a confidence
bound on a *mean*: it does not shrink with sample size, and the mean it actually demanded floated
on how much the panel happened to agree.
[ADR-0005](adr/0005-judge-panel-calibration-and-the-lower-bound.md) diagnosed that and
deliberately left it in force; ADR-0006 replaced it after the defect was demonstrated on an
unedited file — `AST08`, byte-identical between runs 3 and 4, flipped BLOCKED → SHIP on that
clause alone — and with the new constant fixed **before** the run it judges. On the run-4 corpus
nine of eleven skills clear the gate under either rule and the change altered no verdict, which is
re-derived at test time rather than remembered.
`POOLED_LOWER_BOUND` is retired: `mean − σ` is still computed and still published in the column
below, and decides nothing. Had it still been in force, run 5's board would read ten of eleven:
`AST01` — the one skill that was actually repaired between the two runs, and whose `D3` rose 2.0
points because of it — is the single row it would have blocked, at `110.1 − 6.65 = 103.4 < 105`,
on the widest sigma in the panel. A clause that blocks the improvement and passes everything left
alone is the diagnosis in one line.

**And on this panel the confidence bound is the more permissive of the two clauses, not the
stricter one.** `mean − σ ≥ 105` and `mean − σ/√n ≥ 108` are the bars `mean ≥ 105 + σ` and
`mean ≥ 108 + σ/√n`, so the adopted clause demands more only where `σ < 3/(1 − 1/√n)` — about
**4.0** at `n = 16`, 3.96 at `n = 17`, 3.93 at `n = 18`. **Run 5's per-skill σ runs 4.16 to 6.65, so
at every one of its eleven `(n, σ)` pairs the adopted clause demands a lower mean than the retired
one**, by 0.12 points on `AST06` to 1.99 on `AST01`. Across all five recorded runs — 55 skill-runs
— the adopted clause has demanded a strictly higher mean on exactly **three**: `advisory` in run 3
(σ 3.44) and `AST04` and `AST05` in run 4 (σ 3.74, 4.06). `AST06` in run 4 (σ 4.04) is an exact
tie, both clauses demanding 109.04, and is counted apart from the three rather than with them. So
it is not a rule that only ever relaxes, but it has never been the harder rule on a corpus it
actually gated. ADR-0006's case is
that the retired clause was **not a function of the artifact**; it was never that the replacement
is stricter, and this page should not be read as claiming it is.

### Anti-re-roll

**Every judgment must be recorded in `aggregate.judgments` and pooled. Rounds may be
added; a round may never be discarded.** That is the whole integrity mechanism, and it is
cheap to enforce because adding rounds barely moves a mean — one lucky draw of +6 moves a
mean of eight rounds by +0.75. Re-rolling for a better number is not worth the
electricity.

The single exception is an **invalidated** measurement — a defective instrument (a stale
rubric path, a truncated response), flagged and auditable in the record. Never a score
somebody merely dislikes. A judgment refused as **malformed** by the justification
contract is the same exception applied at parse time, and it now leaves an audit-trail entry
naming the skill, the provider, the round, the parse error and an excerpt of the response
(`adapters.base.record_failure`, appended to `config/audit.yml`; the scorecard carries the
same entries under `refusals`).

**Run 5 predates that, and its ten discards left no entry at all.** The harness built its
audit trail in memory and the caller kept only the judgments, so the reasons and the raw
responses are gone; even the word "malformed" is an inference for those ten, because no
status was written. Which skill, judge and round each was IS recoverable, and is recorded in
[`../eval/run5-refusals.md`](../eval/run5-refusals.md) — 10 of 198, and `n` differs by judge
in the calibration table above because of them. `python3 scripts/refusal_ledger.py` fails if
any scorecard ever again shows a gap nothing accounts for.

Only judgments produced in a context separate from the one that authored the skill may
bind (`ship_floor.INDEPENDENT_METHODS`). Authoring-session self-scores measured **+12.2
points of inflation** and never bind.

`ship_floor.aggregate_verdict` recomputes every published statistic from
`aggregate.judgments` before comparing it to the stored value. A stored mean is a claim;
the judgments are the evidence. Any disagreement is `BLOCKED`, not a rounding note.

---

## Provider roster

The judge matrix is multi-provider on purpose: a single judge's idiosyncrasies become the
rubric otherwise. Availability was verified live from this build environment on
2026-08-21 (`features/ast10-agent-skills/build-notes.md`).

### Available — verified live

| Provider | Adapter | Model id | Notes |
| --- | --- | --- | --- |
| `bedrock/gpt-oss-120b` | `adapters/bedrock.py` | `openai.gpt-oss-120b-1:0` | Bedrock on-demand, `us-west-2`, `converse` API. |
| `bedrock/qwen3-235b` | `adapters/bedrock.py` | `qwen.qwen3-235b-a22b-2507-v1:0` | Bedrock on-demand, `us-west-2`. |
| `bedrock/deepseek-v3.2` | `adapters/bedrock.py` | `deepseek.v3.2` | Bedrock on-demand, `us-west-2`. |
| `bedrock/nova-pro` | `adapters/bedrock.py` | `us.amazon.nova-pro-v1:0` | The `us.` inference-profile prefix is **required**, not stylistic — the bare model id fails. |
| `claude-cli` | `adapters/claude_cli.py` | local `claude -p --model <id>` | The only working Claude-as-judge route from this environment, because the Bedrock Anthropic family is geo-blocked (below). |
| `anthropic-compatible/glm-5.2` | `adapters/anthropic_compatible.py` | `glm-5.2` | `POST https://api.z.ai/api/anthropic/v1/messages`, header `x-api-key: $ZAI_API_KEY`. |

### Unavailable — declared, never silently dropped

Per spec.md S-004, a provider that cannot run is recorded in
[`../config/audit.yml`](../config/audit.yml) with a written reason. It is never averaged
in as a zero and never dropped without a record: an unavailable provider that leaves no
trace is indistinguishable from one that was never tried, which is precisely the AST08
shape this repository is about. `adapters.base.AdapterStatus` refuses to construct an
unavailable status with an empty reason.

| Provider | Adapter | Model | Recorded reason |
| --- | --- | --- | --- |
| `bedrock-anthropic` | `bedrock` | `anthropic.*` | **Geo-blocked** from this environment — Bedrock `us-west-2` returns `ValidationException: not allowed from unsupported countries`. Verified 2026-08-21. Claude-as-judge coverage comes from `adapters/claude_cli.py` instead. |
| `openai-compatible-zai` | `openai-compatible` | `glm-5.2` | **Unfunded** — `POST https://api.z.ai/api/paas/v4` returns `Insufficient balance`. Verified 2026-08-21. GLM coverage comes from the Anthropic-compatible route (`api.z.ai/api/anthropic`) instead, so the model is in the pool and only this transport is not. |
| `openai-compatible-dashscope` | `openai-compatible` | `qwen3-max` | **No credential** — `DASHSCOPE_API_KEY` is unset in this environment, so the Alibaba DashScope route cannot be attempted at all. |

Mid-round failures are separate from roster-time unavailability: an adapter that raises
during a round is excluded from that round's pool with a timestamped audit entry
(`adapters.base.record_failure`, appended to `config/audit.yml`'s append-only
`runtime_entries`) rather than aborting the run.

---

## Results

> **Produced by the rule above, on the corpus below it.** Every row in this table is run 5's,
> gated by `mean ≥ 108` AND `mean − 1.0 × stdev/√n ≥ 108` AND the per-dimension floors — the rule
> [ADR-0006](adr/0006-confidence-bound-on-the-pooled-mean.md) put in force before this run was
> scored. The `Mean − σ` column is the **retired** statistic, published because ADR-0005's argument
> is arithmetic on it; it decides nothing, and `AST01` ships at 103.4 in that column.
>
> The table is regenerated, not typed: `python3 eval/generate_dashboard.py` rewrites it from
> `eval/scorecards/*.json`, recomputing every verdict and grade through `ship_floor.aggregate_verdict`
> rather than copying a stored one.
> `tests/test_generate_dashboard.py::test_the_committed_results_table_is_the_live_corpus_under_the_rule_in_force`
> fails if the committed table is not what the generator emits today, and re-derives every verdict
> here through the gate. The table was **frozen** for exactly one run — between ADR-0006 and run 5,
> while the published board was older than the rule in force — and
> `test_the_gate_change_moved_no_verdict_on_the_corpus_it_did_not_judge` is what carries that period's
> claim forward: today's gate over the frozen `eval/scorecards-run4/` bytes reproduces all eleven
> run-4 verdicts.

<!-- BEGIN:results -->
**11 of 11 skills judged; 11 clear the ship rule.** Verdicts and grades below are recomputed from each scorecard's own `aggregate.judgments` by `ship_floor.aggregate_verdict`; stored verdicts are never copied. Unjudged skills keep their placeholder row rather than dropping out of the table.

| Skill | Rounds | Mean | Mean − σ | Lowest dim (floor) | Grade | Verdict |
| --- | ---: | ---: | ---: | --- | --- | --- |
| `AST01` | 16 | 110.1 | 103.4 | `D2` 13.4/13 | A | SHIP |
| `AST02` | 18 | 111.8 | 107.4 | `D2` 13.5/13 | A | SHIP |
| `AST03` | 16 | 112.2 | 107.6 | `D6` 13.8/13 | A | SHIP |
| `AST04` | 18 | 111.6 | 106.4 | `D2` 13.6/13 | A | SHIP |
| `AST05` | 16 | 110.6 | 105.8 | `D2` 13.3/13 | A | SHIP |
| `AST06` | 16 | 112.1 | 107.9 | `D2` 13.5/13 | A | SHIP |
| `AST07` | 17 | 110.2 | 105.5 | `D1` 17.4/17 | A | SHIP |
| `AST08` | 18 | 109.7 | 105.4 | `D2` 13.4/13 | A | SHIP |
| `AST09` | 18 | 111.1 | 106.3 | `D2` 13.4/13 | A | SHIP |
| `AST10` | 18 | 112.4 | 107 | `D2` 13.6/13 | A | SHIP |
| `advisory` | 17 | 112.2 | 107.9 | `D2` 13.7/13 | A | SHIP |
<!-- END:results -->

The `advisory` skill is judged on **guidance relevance and reasoning quality** — whether
the AST it routes to and the remediation it returns make sense — not on detection. It
contributes to no category's F1 denominator (spec.md S-002).

---

## Recording a run

One JSON file per skill under `eval/scorecards/`, named after the skill. The `aggregate`
block is exactly the shape `ship_floor.aggregate_verdict` consumes, so the dashboard and
the gate read the same bytes and cannot drift apart:

```json
{
  "skill": "ast01-malicious-skills",
  "category": "AST01",
  "recorded_at": "2026-09-01T00:00:00+00:00",
  "providers": ["bedrock/gpt-oss-120b", "claude-cli", "anthropic-compatible/glm-5.2"],
  "aggregate": {
    "method": "multi-round-independent-pooled",
    "rubric_sha": "3027f20f3181758385a1bb8c022d4041dfb4de84",
    "judgments": [109, 111, 108, 112],
    "n": 4, "mean": 110.0, "median": 110.0,
    "min": 108, "max": 112, "range": 4,
    "stdev": 1.83, "lower_bound": 108.2,
    "sem": 0.92, "ci_lower": 109.1,
    "dim_means": {"D1": 18.0, "D2": 14.0, "D3": 14.0, "D4": 14.0,
                  "D5": 14.0, "D6": 14.0, "D7": 9.0, "D8": 13.0},
    "dim_n": 4
  }
}
```

`sem` and `ci_lower` are [ADR-0006](adr/0006-confidence-bound-on-the-pooled-mean.md)'s two
additions and are what the second clause is read from: `sem = stdev/√n` rounded to two places,
`ci_lower = mean − 1.0 × sem` rounded to one, both derived from the already-rounded `mean` and
`stdev` so a reader holding those three numbers reproduces the verdict exactly. Run 5 is the first
corpus written with them; the four archived runs predate them and do not carry them, so the gate
treats their absence as a date rather than a disagreement, and refuses any stored statistic — new
key or old — whose value disagrees with the recompute.

Then:

```bash
python3 eval/generate_dashboard.py    # rewrites the Results table above
python3 scripts/ship_floor.py         # recomputes every scorecard verdict, fails on drift
python3 eval/calibration.py           # bias, judge quality, and the robustness block
python3 scripts/refusal_ledger.py     # every discarded judgment must be on the record
```

The generator never copies a stored `verdict` or `grade`: it recomputes both from
`aggregate.judgments` through `ship_floor.aggregate_verdict`, and a scorecard whose stored
statistics disagree with the recompute is rendered `BLOCKED` with the reason shown.
