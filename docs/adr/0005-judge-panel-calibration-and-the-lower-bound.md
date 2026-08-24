---
artifact: adr
version: "1.4"
created: 2026-08-23
updated: 2026-08-24
status: accepted
superseded_in_part_by: "0006 — the lower-bound clause only; the diagnosis below stands"
---

# ADR-0005: The Ship Rule's Lower Bound Measures Judge Disagreement, Not Skill Quality

> ## Superseded in part by [ADR-0006](0006-confidence-bound-on-the-pooled-mean.md)
>
> **What is superseded: the lower-bound clause, and nothing else.** On 2026-08-24
> [ADR-0006](0006-confidence-bound-on-the-pooled-mean.md) replaced
> `mean − stdev ≥ POOLED_LOWER_BOUND (105)` with
> `mean − 1.0 × stdev/√n ≥ POOLED_TARGET (108)` in `scripts/ship_floor.py`. That is the gate's
> first and only change. `POOLED_TARGET`, `FLOORS` and `MIN_ROUNDS` did not move; the anti-re-roll
> pooling rule did not move.
>
> **The diagnosis below is not superseded and is not wrong.** It is the record of how the defect
> was found, and ADR-0006 rests on it entirely. Decision item 4 — a superseding record naming the
> rule and its constants *before* any score is computed under it, then a fresh judged run — was
> not overruled either; it was **followed**, and it still binds the next change. What ADR-0006
> supersedes is item 1's "`POOLED_LOWER_BOUND` stays 105" and item 2's "stated, not applied".
>
> **Nothing below has been rewritten**, including two sentences that no longer hold against the
> boundary the new clause uses. Both were measured against the retired 105 threshold and are true
> of it: that `AST09` "clears comfortably at 107.0" under the standard error of the mean, and that
> fixing the bound "would take the board from nine skills to ten". Against the Grade-A boundary
> ADR-0006's clause actually asks about, `AST09`'s 107.0 is **below** 108 and still BLOCKED — the
> board stays at nine, and the change buys nothing. The correction is recorded in ADR-0006
> ("Consequence check") rather than applied here, because editing the argument after the fact
> would destroy the thing this file is for.
>
> **Every figure below still regenerates.** `eval/calibration.py` keeps the retired constant so
> the implied-mean-bar arithmetic can be re-derived, and `tests/test_calibration.py` still fails
> if this document and that script disagree.
>
> ### What has happened since, in one paragraph
>
> Run 5 — the first corpus judged under ADR-0006's clause — ships **11 of 11 skills**, and no skill
> on it is held by any lower bound. That is not this record being overtaken by events, and two
> measurements say so. First, the panel this record describes did most of its tightening before run
> 5 and then stopped: median per-skill sigma fell **6.43 → 5.65 → 4.67** across runs 2, 3 and 4 and
> came back up to **4.75** in run 5, while the between-judge spread went 16.5 → 15.4 → 11.6 → 11.4.
> The instrument is better than it was and it has not converged; an 11.4-point spread is still most
> of a grade band. Second, the defect this record found was **fixed**, by
> [ADR-0006](0006-confidence-bound-on-the-pooled-mean.md), with its constant recorded before the
> run it judges.
>
> **That fix changed no verdict on run 4, and it changed one on run 5.** Under the retired clause
> run 5 reads **10 of 11**: it would have blocked `AST01` at `110.1 − 6.65 = 103.4 < 105` — the one
> skill repaired between runs 4 and 5 — while passing all ten that nobody touched. Ten of run 5's
> eleven verdicts are attributable to the artifacts rather than to the rule; the eleventh is
> attributable to both, and an earlier version of this paragraph said otherwise. What run 5 retires
> is the *urgency* of the diagnosis, not the diagnosis: a clause that blocks the one repaired skill
> and passes everything left alone is the defect in one line, and `AST08`'s flip on a byte-identical
> file remains the demonstration. It is also not a tightening — on this panel ADR-0006's clause
> demands a **lower** mean than the retired one at every `(n, σ)` run 5 produced.

## Status

Accepted

**Date:** 2026-08-23
**Figures refreshed:** 2026-08-24, against the fifth judged run — the third scored with the
rubric's bands in the prompt, and the first judged under the clause ADR-0006 put in place of the
one this record diagnoses. The decision below is unchanged; the panel figures are new, and the
worked example is deliberately **not** new — it is run-4 evidence, labelled as such, because a
clause that no longer runs cannot produce a fresh instance of itself.
**Deciders:** Jacky Chan (Reviewer/Contributor, feature owner)

Every figure quoted below is printed by `python3 eval/calibration.py`, which derives it from
`eval/scorecards/*.json` and nothing else. `tests/test_calibration.py` fails if this document
and that script disagree.

## Context

`scripts/ship_floor.py` decides what ships. A skill clears the gate when its pooled mean is at
least `POOLED_TARGET` (108), its pooled `mean − stdev` is at least `POOLED_LOWER_BOUND` (105),
and every dimension mean clears its floor. The second clause is the one the file describes as
doing the work: "a mean of 108 sitting on a sigma of 4 is *within noise of failing badly*, and
this rule refuses it."

That clause was calibrated against a stated instrument. The comment block above it records the
basis: repeated sweeps over byte-identical content produced binding means of 101.1, 105.1 and
108.6, and "the pooled per-judgment sigma is 3.3 points". At sigma 3.3 the pair of constants is
coherent — it asks for a Grade-A mean and refuses one perched on a wobble.

The six-provider judged run recorded in `eval/scorecards/` measured a different instrument.
Eleven skills × three rounds × six providers were attempted; **188 judgments bind**, the other
10 having been discarded at parse time — and recorded nowhere, so even "malformed" is an
inference rather than a reading (`eval/run5-refusals.md` reconstructs which skill, judge and
round each was, and states what cannot be recovered).
The per-skill sigma across those 188 is **4.16 to 6.65**, still up to twice the figure the rule
was tuned against — and the *widest* it has been since the prompt rebuild, on the run with the
best board.

### The spread is bias, not noise

Sigma is that wide because the judges disagree systematically. Against a pooled mean of
**111.3**:

| Judge | n | Mean | Bias vs pooled | Round means |
| --- | ---: | ---: | ---: | --- |
| `bedrock/qwen3-235b` | 32 | 117.7 | +6.5 | 117.7 / 117.3 / 118.2 |
| `anthropic-compatible/glm-5.2` | 30 | 112.6 | +1.3 | 112.1 / 113.3 / 112.3 |
| `bedrock/deepseek-v3.2` | 30 | 111.8 | +0.5 | 111 / 111.7 / 112.9 |
| `claude-cli/sonnet` | 33 | 110.4 | -0.9 | 110 / 110.6 / 110.5 |
| `bedrock/nova-pro` | 30 | 109.0 | -2.3 | 109.5 / 108.5 / 108.8 |
| `bedrock/gpt-oss-120b` | 33 | 106.3 | -4.9 | 107.2 / 106.9 / 104.9 |

Top to bottom that is an **11.4-point spread** — still most of a grade band between the harshest
and the most generous reader of the same eleven files, and barely narrower than the 11.6 of the
run before it. Four of the six judges sit within 2.3 points of the pooled mean, three of them
within 1.3. The spread survives because of the two ends, `qwen3-235b` at +6.5 and `gpt-oss-120b`
at -4.9, and a spread carried by two judges is exactly as fatal to a sigma-based bound as a spread
carried by six.

The right-hand column is what settles the diagnosis. Each judge scored the whole roster three
independent times, and no judge moved more than **2.3 points** between its own rounds — the
widest is `gpt-oss-120b` at 107.2 / 106.9 / 104.9, and `sonnet` moved 0.6 across the entire
roster. Every judge is precise. They are precise about different things. What sigma is
measuring across the pooled column is therefore mostly a constant per judge, and a constant per
judge carries no information about any skill.

### The statistical error

`mean − stdev` is a **spread** statistic. The gate applies it as a **confidence bound on the
mean** — "is this skill's true quality above the bar?". Those are different questions and they
have different denominators. The uncertainty of a mean shrinks with sample size:
`stdev / sqrt(n)`. The spread does not shrink at all. Pooling 17 judgments instead of 4 buys a
much better estimate of the mean and leaves `mean − stdev` exactly where it was.

Written out, `mean − stdev ≥ 105` is the same constraint as `mean ≥ 105 + stdev`. So the sigma a
panel happens to produce sets the mean the rule actually demands. At this panel's sigma the rule
would demand a mean of **109.2 to 111.7** — 91.0% to 93.0% of the rubric — rather than the
108 (90.0%) it names as its target. Nobody chose a 91.0-93.0% bar. It arrived as a side effect
of adding judges. It is a *wider* distortion than the 90.6-92.5% the previous run implied, on a
run whose skills scored better — which is the argument in miniature: the implied bar moved up
while the artifacts improved, because it is not a function of them.

### The perverse incentive, stated plainly

Adding a judge to the panel makes the gate **harder** even when the skill is byte-identical.
A seventh judge with a novel calibration widens sigma, sigma raises the effective mean bar, and
the skill that passed yesterday fails today without a character changing. The rule as written
penalises panel diversity and rewards a narrow panel of like-minded judges — the exact opposite
of why `docs/skill-judge-dashboard.md` says the matrix is multi-provider: "a single judge's
idiosyncrasies become the rubric otherwise."

### The concrete case — run-4 evidence, and the last instance the clause will ever produce

**Read this section as history, and check it against `eval/scorecards-run4/`.** It is measured on
run 4, the last corpus judged under the retired clause, and it is deliberately not refreshed
against run 5. It cannot be: the clause was retired before run 5 was scored, so no skill judged
from here on can be "blocked by the lower bound" and a search of the live corpus returns zero
instances of the thing this record is about. The evidence for a retired rule is the run it was
last applied to, kept frozen — deleting it because the board has since gone green would erase why
this record exists. `tests/test_calibration.py` derives the corpus the same way, by finding the
newest run whose scorecards predate ADR-0006's two published statistics, so the example cannot
silently drift onto a corpus that never saw the clause.

Version 1.1 of this record used `AST04` as the worked example. `AST04` shipped in run 4 — 112.6,
every floor clear, `mean − stdev` 108.9 — so it could no longer carry the argument, and run 4
produced a cleaner instance than any run before it.

`AST09` pooled a mean of **108.2** across 17 judgments — Grade A — with **every one of the eight
dimension means above its floor**: D1 17.8, D2 13.1, D3 13.9, D4 14.6, D5 13.1, D6 13.4, D7 8.6,
D8 13.7. There was no finding about the file left in its verdict. It was BLOCKED, and the whole of
the reason is arithmetic:

```
108.2 - 4.85 = 103.4 < 105
```

Under the standard error of the mean the same 17 judgments give `108.2 − 4.85/√17 = 107.0`,
comfortably clear of 105. `AST09` was the only skill on run 4's board blocked by the lower bound,
and nothing else was against it: no dimension below floor, no shortfall on the mean, no rubric
mismatch, 17 pooled judgments against a `MIN_ROUNDS` of 4. It is the defect this record describes
with every confounder removed.

Two things happened to that skill afterwards, and both are worth having next to the arithmetic.
ADR-0006 measured 107.0 against the boundary its clause actually asks about — the Grade-A 108, not
the retired 105 — and found `AST09` still BLOCKED, so the correction changed the reason and not
the outcome. Then run 5 scored the same byte-identical `SKILL.md` at a mean of 111.1 and it
shipped. Nobody edited it. The clause that blocked it is gone, but the thing that moved it is the
pooled mean itself, and no confidence bound removes that.

The same clause moved a verdict in the other direction on the same run, which is worth recording
because it is the less obvious half. `AST08` was BLOCKED in run 3 by the lower bound alone
(110.3 − 5.65 = 104.6) and SHIPs in run 4 at 110.8 − 4.67 = 106.1. `AST08`'s `SKILL.md` is
byte-identical across the two runs and its `D3` mean *fell*, 13.5 to 13.2. What changed was the
panel's dispersion. A rule that can flip a verdict on a file nobody edited is not measuring the
file. **This row, not `AST09`, is what licensed ADR-0006**, and it is the reason the retired rule
cannot be called sound merely because run 5 has nothing held by it.

### The controlled result: `D3` anti-patterns are load-bearing

Between run 3 and run 4 the judge prompt, the rubric pin, the panel roster and every gate
constant were held fixed. Exactly one thing changed: eight skills — `AST02`-`AST07`, `AST09`,
`AST10` — gained an explicit, grounded anti-pattern `NEVER` section. `AST01`, `AST08` and
`advisory` were deliberately left untouched because they had already cleared the `D3` floor in
run 3.

That makes run 3 → run 4 the first comparison this repository can legitimately make
skill-by-skill, and the result is unambiguous: all eight treated skills rose on `D3` and on the
pooled mean, all eight crossed the `D3` floor, seven went BLOCKED → SHIP; all three untouched
controls *fell* on `D3`, and `AST01` fell through the floor it had cleared by 0.1 points.

Run 4 → run 5 is the second arm and it repeats the same design with the ratio inverted: **one
treated skill and ten controls.** `AST01` was the only `SKILL.md` edited, it received the same
anti-pattern treatment, and its `D3` rose 12.2 → 14.2 while the ten untouched skills moved between
−0.4 and +0.4 with a mean of +0.05. The treatment replicates on the dimension it targets. It does
**not** replicate on the total: `AST01` gained 1.6 points of pooled mean, and the untouched
`AST09` gained 2.9. A treated effect smaller than the largest control movement is not readable off
a total, which is a caution about every pooled mean in this document and not only about that one.
Both tables are in [`../skill-judge-dashboard.md`](../skill-judge-dashboard.md), "The controlled
results", along with what treating a 0.1-point margin as clearance cost. They are worth more than
the headline ship count, and they are the reason this record now has to argue in two directions at
once.

**What the two arms license, stated at the width the evidence supports.** They say that *adding* a
grounded anti-pattern section raises `D3` on a skill that is at or under the floor, reproducibly,
against controls that do not move. They do **not** say that a consolidated `NEVER` section is what
makes a `D3` score good. `AST08` is the counterexample and it is on this board: it has **no**
anti-pattern section at all — the string `NEVER` does not occur in its `SKILL.md`, its
prohibitions are distributed through its decision rules instead — and it scores `D3` 13.4 in run 5,
above the 11.5-to-12.9 band every one of the eight treated skills started from. The treatment works
where it was applied; the heading is not the mechanism, and this record should not be read as
claiming it is.

### What the two instrument changes did to the panel

Runs 1 (`eval/scorecards-run1/`) and 2 (`eval/scorecards-run2/`) were scored by a prompt that
transmitted the eight dimension *names* and their maxima and **none of the rubric's score
bands**, and that forbade prose. Six judges each graded against a private scale invented from a
label. Run 3 (`eval/scorecards-run3/`) was the first scored with each dimension's band table
quoted verbatim and a one-sentence justification required per dimension. Runs 4
(`eval/scorecards-run4/`) and 5 — the corpus in `eval/scorecards/`, and the source of every panel
figure above — were scored by that same prompt, so they are measurements of the skills and not of
the instrument.

| Judge | Run 2 bias | Run 3 bias | Run 4 bias | Run 5 bias |
| --- | ---: | ---: | ---: | ---: |
| `bedrock/qwen3-235b` | +10.8 | +8.7 | +6.7 | +6.5 |
| `anthropic-compatible/glm-5.2` | +0.7 | +0.0 | +1.2 | +1.3 |
| `claude-cli/sonnet` | −3.7 | −0.2 | −0.5 | −0.9 |
| `bedrock/nova-pro` | −5.7 | −0.7 | −1.0 | −2.3 |
| `bedrock/deepseek-v3.2` | +0.3 | −1.2 | −1.8 | +0.5 |
| `bedrock/gpt-oss-120b` | −2.4 | −6.8 | −4.9 | −4.9 |

- **Median per-skill sigma fell 6.43 → 5.65 → 4.67 and then rose to 4.75**, and the worst
  per-skill sigma went 14.04 → 8.01 → 6.04 → 6.65. Giving the judges the rubric tightened
  agreement; giving them a concrete anti-pattern list to point at tightened it again; run 5 gave
  back a little of the second gain. Two runs of tightening and one of drift is a panel that has
  improved and has not converged, and only the middle change was a change to the instrument —
  which is why only the artifact changes license a skill-by-skill reading.
- **Between-judge spread fell 16.5 → 15.4 → 11.6 → 11.4**, and the largest within-judge
  round-to-round spread went 4.0 → 2.3 → 1.5 → 2.3. The judges were always self-consistent; they
  are closer to each other than they were and they have stopped getting closer.
- **`bedrock/qwen3-235b` has now returned three different verdicts on an unchanged rule, and none
  of them is a relapse.** Under the unanchored prompt it returned exactly 120.0 on all eleven
  skills, from three distinct values, for an across-skill sigma of 0.00 — NON-DISCRIMINATING.
  Under the rubric-grounded prompt it ranked: run 3 placed the roster across 114.7-119.7, an
  across-skill sigma of 1.38, COARSE. Run 4 flagged it again at 0.94, not because the judge got
  worse but because the *skills* moved up into a ceiling it does not move: it puts most of its
  dimension scores at a dimension's maximum, so it has almost no room above a rising roster. Run 5
  puts it back over the floor at 1.22 and COARSE, for the mirror-image reason — the roster spread
  out again beneath it, and it now returns the full 120 on 34% of its judgments against 16% in
  run 4. A judge whose verdict oscillates across a threshold it sits on is a judge at the edge of
  what it can resolve, which is the same lesson `AST01` teaches below: a threshold cleared by 0.38
  is not a threshold cleared. It is pooled into every figure here in all three states.
- **`gpt-oss-120b` remains the panel's most checkable reader.** It is the harshest judge at
  -4.9, the furthest from saturation (10% of its dimension scores at a dimension maximum, none
  at the rubric total), and it uses twelve distinct dimension values. A harsher number attached
  to a verifiable reason is better evidence than a kinder number attached to nothing.

Two things this does **not** license. First, **runs 1 and 2 are retained as the evidence for the
prompt defect, not as measurements of skill quality.** Their absolute means say what an
unanchored judge produced. They are kept unedited because deleting them would destroy the only
proof that the two instruments differ, and no figure on this page may be differenced against
them. Second, run 4's improvement is attributable to the treatment only for the eight skills
that received it. The three controls are what make that a finding rather than a story, and one
of them moved the wrong way.

And the finding stands. Better artifacts did not repair the statistic any more than a better
panel did: the implied mean bar went 108.4-113.0 → 108.7-111.0 → 109.2-111.7 across the last three
runs, so it *rose* on the run with the best board. It is still above the 108 the rule names, still
set by the panel rather than by the constant, and still rising with every judge added. Improving
the measurement shrank the error for two runs and then gave some back. Only changing the rule
removes it, and that is what ADR-0006 did.

## Decision

**We record the flaw and leave the rule exactly as locked. No gate constant changes in this
record, and none changed in this run.**

Specifically:

1. **`ship_floor.py` is untouched.** `POOLED_TARGET` stays 108, `POOLED_LOWER_BOUND` stays 105,
   `FLOORS` stay as vendored, `MIN_ROUNDS` stays 4. Every verdict in `eval/scorecards/*.json`
   and every row on the dashboard is the locked rule's own output, unedited. This survived the
   prompt rebuild and it survived the run that finally produced a shippable board: neither
   rebuilding the instrument nor improving the artifacts is permission to move the bar.
   `tests/test_calibration.py` pins those constants to the values this record names, so a future
   change to them fails a test that names this document.

2. **The correct bound is stated, not applied.** For the question the gate is actually asking —
   *is the true mean above the bar?* — the bound is `mean − stdev/sqrt(n)`, the standard error
   of the mean, not `mean − stdev`. That is the fix. It is written down here so that whoever
   adopts it inherits the reasoning rather than re-deriving it.

3. **Two alternatives are worth evaluating alongside it**, because the SEM fix corrects the
   denominator without touching the bias that inflated the numerator:
   - **Trimmed judge vote.** Reduce each judge to one vote per skill (its own mean over rounds),
     then drop the highest and lowest judge before pooling. On this panel that discards
     `qwen3-235b` and `gpt-oss-120b` — the two furthest from centre — and makes the surviving
     sigma a statement about the middle of the panel rather than about its extremes. Note that
     the pair it discards changed between runs; a rule whose membership moves with the prompt
     needs that property recorded before it is adopted, not discovered after.
   - **Per-judge z-scoring.** Standardise each judge against its own long-run mean and spread
     before pooling, so a judge contributes *where it ranked this skill relative to everything
     else it has scored*, and a constant offset cancels by construction. This is the more
     principled of the two and the more expensive: it needs a long-run baseline per judge, which
     this repo does not yet have — two runs under the current prompt is not a baseline, and a
     baseline gathered under the unanchored prompt does not describe this judge at all.

4. **Adopting any of them requires two things, in this order:** (a) a recorded decision
   superseding this one, naming the rule and its constants before any score is computed under
   it, and (b) a **fresh judged run** whose scorecards are written under the new rule. Neither
   is optional. **A bar changed after seeing the data it is applied to is not a bar** — it is a
   post-hoc description of the result, and every number downstream of it becomes uninterpretable
   because a reader cannot tell which came first, the threshold or the outcome. That is why this
   record fixes nothing today, and why it fixed nothing on the run where the fix would have cost
   the most. The measurement in hand was taken under the locked rule and it stays reported under
   the locked rule.

5. **The numbers are generated, not transcribed.** `eval/calibration.py` computes the
   per-provider bias and per-skill sigma above from the scorecards; `tests/test_calibration.py`
   asserts this document's figures match its output. This is not ceremony: the first draft of
   the dashboard's calibration note carried a `nova-pro` bias of −7.9 and a 20.1-point spread
   against run 1's scorecards, which say −5.4 and 17.9, and nothing on disk could tell a reader
   which was true. It is also why refreshing this document for run 4, and again for run 5, was a
   mechanical exercise rather than a judgement call — a fistful of tests failed the moment each
   corpus moved, every one naming the figure that had gone stale. Run 4 broke the assertion that
   had pinned `AST04` as the worked example; run 5 broke the assertion itself, because a retired
   clause cannot produce a fresh instance, and the fix was to point the derivation at the last
   corpus judged under that clause rather than to delete the argument. An ADR whose whole argument
   is arithmetic cannot have hand-typed arithmetic in it.

### Cross-repo implication

**A single-judge score and a pooled multi-judge score are not comparable, and neither is a
pooled score from a different panel.** The scale is not the rubric; the scale is the rubric *as
read by these specific judges*. Two consequences follow for anyone quoting a number from here or
bringing one in:

- A pooled mean is only meaningful next to its panel roster. Moving `AST09`'s 108.2 into a
  context judged by a different set of models compares two different instruments.
- `gpt-oss-120b` is a common solo judge, and on this panel it runs **4.9 points harsh**. A skill
  scored 106 by `gpt-oss-120b` alone and a skill scored 106 by this six-model panel are not the
  same skill. On run 3's panel the same model ran 6.8 points harsh and on run 2's 2.4, so the
  offset is a property of the panel *and* the prompt *and* the population being scored, not a
  constant of the model that can be looked up once. Any score imported from a single-judge
  harness must carry the judge's name and the prompt it read, or it is a number without units.

## Consequences

### Positive

- The gate keeps its integrity property, and run 4 is the run that proved it was worth keeping.
  Nobody can say the bar moved once the results were in, because it demonstrably did not —
  across four runs, a rebuilt judge prompt, and a board that went from one shippable skill to
  nine — and that claim is checkable against the constants in `scripts/ship_floor.py` and the
  verdicts in the scorecards. The skills were changed to meet the bar. The bar was not changed
  to meet the skills. The one change the gate has ever taken, ADR-0006, was written before the run
  it judges and moved no verdict on the corpus in hand when it was adopted.
- **The repository now ships 11 of 11 skills, and the count is the least interesting thing about
  it.** Nine of those eleven cleared under the rule this record declined to retune; the tenth,
  `AST01`, was repaired against the reasons the judges gave and its `D3` rose 2.0 points; the
  eleventh, `AST09`, was not edited at all and rose 2.9 points of pooled mean between two runs.
  The honest reading is that the bar was demanding and that a pooled mean is still a distribution.
- The flaw is now a written, reproducible finding rather than folklore. `eval/calibration.py`
  regenerates every figure, so a reader who distrusts the argument can re-derive it in one
  command instead of trusting a paragraph.
- The `mean − stdev` clause is exposed as sensitive to panel composition, which is a property
  worth knowing before anyone adds a seventh judge and reads the resulting drop as a regression
  in the skills.
- The diagnosis is now falsifiable and has been tested twice. It predicted that judges
  disagreeing about a scale they could not see would converge once they could, and they did. It
  then predicted that the clause would keep issuing verdicts that track panel dispersion rather
  than the artifact, and `AST08` — byte-identical, `D3` down, BLOCKED → SHIP — is that
  prediction landing. Predictions that come true are the cheapest evidence an argument can
  carry.
- The cross-repo note stops the most likely misuse of these numbers: quoting a pooled mean
  beside a single-judge mean as if the two were on one scale.

### Negative

- **The lower bound is no longer blocking almost everything, and that weakens the urgency of
  this record even though it does not touch its correctness.** Version 1.1 was written against a
  board where one skill shipped and two Grade-A skills were held out by this clause alone. Nine
  of eleven cleared the locked rule in run 4 with no constant changed, so the clause could no
  longer be described as the thing standing between this repository and a shippable result. It was
  a latent defect in a gate that was passing, which is a materially weaker case for fixing it than
  the one this ADR opened with, and pretending otherwise would be the same dishonesty in the
  opposite direction. **Run 5 weakens it further and does not repair it.** Nothing on that board
  is held by any bound — but the retired clause would have blocked `AST01`, the single skill that
  was actually repaired, at `110.1 − 6.65 = 103.4`, on the widest sigma in the panel. A defect that
  costs nothing on the run you happen to be looking at is still a defect, and `AST08`'s run-3 →
  run-4 flip on an unedited file remains the demonstration. Nothing about run 5 makes the retired
  rule sound retrospectively.
- **What still holds is the single clean instance the earlier version never had.** `AST09` has a
  Grade-A mean of 108.2, every one of the eight dimension floors clear, 17 pooled judgments, and
  is BLOCKED solely because `108.2 − 4.85 = 103.4 < 105`. Under the standard error of the mean it
  clears comfortably at 107.0. In run 3 this defect was entangled — the skills it blocked also
  had real `D3` findings against them, so a reader could reasonably suspect the statistic of
  being a proxy for a genuine weakness. It is not entangled now. One skill, one reason, and the
  reason is not about the skill.
- **A dimension floor cleared by 0.1 points was treated as cleared, and it should not have
  been.** `AST01` held `D3` 13.1 against a floor of 13 in run 3 and was excluded from the
  anti-pattern pass on that basis. It measured 12.2 in run 4 and became the only skill on that
  board blocked by a floor; it was then treated, and run 5 measures it at 14.2. `AST08` was
  excluded on a 0.5-point margin, fell to 13.2, and sits at 13.4 — still the same finding, still
  without the consequence. The margin problem has not gone away either: run 5 ships two skills
  whose confidence bound clears 108 by less than a point. Judge scores are a distribution; a
  margin inside the run-to-run movement of that distribution is noise wearing a verdict's clothes.
  The remedy is a decision about margins, and it belongs in its own record
  rather than here.
- Anyone reading the dashboard now sees a fully green board and may conclude the gate is easy.
  It is not, and the archived runs are the proof: the same first clause and the same floors,
  unmodified, blocked ten of eleven skills in run 3 and two of eleven in run 4. The board is green
  because the artifacts changed — and because run 5 drew well on a panel that still spans 11.4
  points. Two of the eleven clear the confidence bound by under a point.
- Correcting the bound later means the corrected numbers cannot be compared to this run's
  numbers without care, since adoption requires a fresh run. This run becomes a historical
  measurement under a superseded rule rather than a baseline.
- Fixing the bound today would take the board from nine skills to ten — `AST09` and nothing
  else. `AST01` stays blocked on `D3`, which is a real weakness in the artifact and no statistic
  will retire it. Shipping nine skills under a rule we can defend is worth more than shipping ten
  under a rule we edited after reading the scores.

### Neutral

- `eval/calibration.py` is diagnostic and sits outside the gate path. Nothing imports it into a
  verdict. It prints both candidate bounds side by side — withholding the number the argument
  turns on would be its own dishonesty — but it issues no verdict, ranks no rule, and publishes
  no would-have-shipped list. Choosing between the two columns on the strength of that table is
  exactly what item 4 above forbids.
- The 3.3-sigma figure in `ship_floor.py`'s comment stays as vendored. It is an accurate record
  of the instrument that rule was calibrated against, and rewriting it to match this panel would
  destroy the evidence that the two differ.
- Per-judgment counts are not uniform across judges — 30 to 33 rather than a flat 33 — because a
  judgment that will not bind is discarded instead of averaged in. Uneven `n` is the honest shape
  of a run that rejects bad rows, and it makes a per-provider bias a slightly noisier estimate for
  the judges that lost the most rows. **It is not neutral per skill, and an earlier draft of this
  bullet said it was.** The ten discards are spread across four judges but they land on six skills,
  and on `AST01` the two that landed are the two judges that scored `AST01` lowest
  (`bedrock/deepseek-v3.2` 100.5 and `bedrock/nova-pro` 104.5 against a pooled 110.1). Substituting
  each missing attempt with that judge's own observed mean on that skill moves `AST01` to mean
  109.2, `ci_lower` 107.6 — below the bar. Nothing is imputed into any published figure and no
  verdict is re-issued; the arithmetic is recorded in `eval/run5-refusals.md` because a reader of
  11 of 11 is entitled to it.
- Per-dimension floors are unaffected by this analysis. They are applied to dimension means and
  never divided by a sigma, so the error described here does not reach them — which is why
  `AST01`'s block is a finding about `AST01` and this record does not excuse it.

## Alternatives Considered

### A — Retune the constants now, against this run

Lower `POOLED_LOWER_BOUND`, or swap in `mean − stdev/sqrt(n)`, and re-issue the verdicts from the
scorecards already on disk. Cheapest possible fix and it produces one more shippable skill the
same day. Rejected outright, and the rejection is cheaper to make now than it was in version 1.1,
which is precisely why it has to be made on the same grounds rather than on the new ones. The
data is in hand; any threshold chosen now is chosen knowing which skills it passes, and a reader
has no way to distinguish a principled correction from a convenient one. The correction is right
and it still has to wait for a fresh run, because the value of the gate is entirely in the fact
that it was set first.

### B — Drop the lower-bound clause and gate on the mean alone

Removes the flawed statistic instead of replacing it. Rejected because the clause is protecting
something real: a mean of 108 drawn from four wildly disagreeing judgments genuinely is weaker
evidence than a mean of 108 from four judgments that agree, and the gate should be able to say
so. The problem is the denominator, not the intent.

### C — Cut the panel back to judges that agree

Drop `qwen3-235b` and `gpt-oss-120b` and sigma collapses on its own, no rule change required.
Rejected as the incentive at its worst: it improves the reported numbers by narrowing the
evidence, and it selects judges for agreeing with each other rather than for reading well. On
this run it would be worse than that — `gpt-oss-120b` is the judge furthest from saturation and
the one that most often cites a specific absence in a specific file, so the panel would be cut
back by discarding its best-evidenced reader. It would also violate the roster doctrine this
repo already holds — providers are declared with a recorded reason, never dropped because of
what they said. `qwen3-235b` is flagged NON-DISCRIMINATING on this run and is still pooled into
every published figure for exactly that reason.

### D — Report both bounds on the dashboard and let readers choose

Publish `mean − stdev` and `mean − stdev/sqrt(n)` side by side without designating either as the
gate. Rejected as a gate: a rule with two answers is not a rule, and "the reader decides" is how
the more flattering number becomes the quoted one. Retained as *diagnostics only* — both columns
are printed by `eval/calibration.py`, which gates nothing.

### E — Read the green board as the problem going away

Nine of eleven skills cleared the locked rule in run 4 and eleven of eleven clear the corrected
one in run 5, and it would be tempting to close this record as overtaken by events. Rejected as a
category error, and recorded here because it is the most attractive wrong conclusion available
from either board — the same shape as version 1.1's temptation to read a narrower sigma as a
repaired statistic. A gate that currently passes is not a correct gate. `mean − stdev` was still
not a bound on a mean, the implied bar it produced is *higher* on run 5 than on run 4, it still
rises when a judge is added, and it still flipped `AST08`'s verdict on a file nobody edited. That
last item is the demonstration, and a green board does not retire it. A latent defect is a weaker
reason to act, which this record says plainly under Consequences; it is not a reason to stop
describing it. ADR-0006 acted on it anyway, before a run rather than after one.

## References

- `scripts/ship_floor.py` — the locked rule, its constants, and the 3.3-sigma calibration comment
  this record measures against.
- `eval/calibration.py` — regenerates every figure quoted here from `eval/scorecards/*.json`.
- `tests/test_calibration.py` — fails if this document's figures drift from that script, or if a
  gate constant changes without a superseding record. Its worked-example assertion derives both
  the corpus and the skill: the newest run whose scorecards predate ADR-0006's statistics, and
  whichever skill that run blocked on the lower bound alone. So this record cannot go on quoting a
  skill that has since shipped, and cannot quietly re-point its historical arithmetic at a corpus
  the retired clause never judged.
- `tests/test_judge_quality.py` — holds the judge-quality verdicts against every recorded corpus,
  including run 2's flat judge, run 3's repaired one, run 4's re-flag and run 5's COARSE.
- `eval/scorecards/*.json` — run 5: the 188 binding judgments of 198 attempted, one file per
  skill, each carrying its own `aggregate.judgments` array. Source of every panel figure here.
- `eval/run5-refusals.md` — the other 10: which skill, judge and round each was, what was lost
  with them, and what the gap can and cannot do to a published verdict.
- `eval/scorecards-run4/` — run 4, frozen. The last corpus judged under the retired clause, and
  therefore the evidence for the worked example above.
- `eval/scorecards-run3/` — run 3, frozen. Scored by the same prompt as runs 4 and 5, so the three
  are comparable skill-by-skill; those comparisons are the controlled results above.
- `eval/scorecards-run1/`, `eval/scorecards-run2/` — the two runs scored without the rubric's
  bands, retained unedited as the evidence for the prompt defect.
- `scripts/judge_harness.py` — the prompt: the pinned rubric quoted verbatim, a justification
  required per dimension, and the artifact fenced as data.
- `docs/skill-judge-dashboard.md` — the published results table, the controlled result, the
  rubric, and the ship rule as a reader meets them.
- `docs/adr/0004-per-scenario-detectability-contract.md` — the companion decision on not letting
  a measurement's convenience choose its scope.
