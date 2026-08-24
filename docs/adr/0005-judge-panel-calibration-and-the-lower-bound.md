---
artifact: adr
version: "1.0"
created: 2026-08-23
status: accepted
---

# ADR-0005: The Ship Rule's Lower Bound Measures Judge Disagreement, Not Skill Quality

## Status

Accepted

**Date:** 2026-08-23
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

The six-provider judged run of 2026-08-23 measured a different instrument. Eleven skills ×
three rounds × six providers = 198 judgments, and the per-skill sigma is **5.43 to 14.04**,
double to triple the figure the rule was tuned against.

### The spread is bias, not noise

Sigma is that wide because the judges disagree systematically. Measured over 33 judgments each,
against a pooled mean of **109.2**:

| Judge | n | Mean | Bias vs pooled | Round means |
| --- | ---: | ---: | ---: | --- |
| `bedrock/qwen3-235b` | 33 | 120 | +10.8 | 120 / 120 / 120 |
| `anthropic-compatible/glm-5.2` | 33 | 109.9 | +0.7 | 110.1 / 110.3 / 109.5 |
| `bedrock/deepseek-v3.2` | 33 | 109.5 | +0.3 | 107.5 / 109.8 / 111.1 |
| `bedrock/gpt-oss-120b` | 33 | 106.8 | -2.4 | 106.8 / 107.5 / 106.2 |
| `claude-cli/sonnet` | 33 | 105.5 | -3.7 | 104.9 / 105.9 / 105.7 |
| `bedrock/nova-pro` | 33 | 103.5 | -5.7 | 103.6 / 101.4 / 105.4 |

Top to bottom that is a **16.5-point spread** — one and a half grade bands between the harshest
and the most generous reader of the same eleven files.

The right-hand column is what settles the diagnosis. Each judge scored the whole roster three
independent times, and no judge moved more than **4.0 points** between its own rounds;
`qwen3-235b` returned 120 / 119.6 / 120. Every judge is precise. They are precise about
different things. What sigma is measuring across the pooled column is therefore mostly a
constant per judge, and a constant per judge carries no information about any skill.

### The statistical error

`mean − stdev` is a **spread** statistic. The gate applies it as a **confidence bound on the
mean** — "is this skill's true quality above the bar?". Those are different questions and they
have different denominators. The uncertainty of a mean shrinks with sample size:
`stdev / sqrt(n)`. The spread does not shrink at all. Pooling 18 judgments instead of 4 buys a
much better estimate of the mean and leaves `mean − stdev` exactly where it was.

Written out, `mean − stdev ≥ 105` is the same constraint as `mean ≥ 105 + stdev`. So the sigma a
panel happens to produce sets the mean the rule actually demands. At this panel's sigma the rule demands a mean of **110.4 to 119.0** — 92.0% to 99.2% of the rubric — rather than the 108 (90.0%) it names as its target. Nobody chose a 92-99% bar. It arrived
as a side effect of adding judges.

### The perverse incentive, stated plainly

Adding a judge to the panel makes the gate **harder** even when the skill is byte-identical.
A seventh judge with a novel calibration widens sigma, sigma raises the effective mean bar, and
the skill that passed yesterday fails today without a character changing. The rule as written
penalises panel diversity and rewards a narrow panel of like-minded judges — the exact opposite
of why `docs/skill-judge-dashboard.md` says the matrix is multi-provider: "a single judge's
idiosyncrasies become the rubric otherwise."

### The concrete case

`AST04` pooled a mean of **108.7** across 18 judgments — Grade A, and among the tightest
mean on the board, with every dimension mean clear of its floor. It is BLOCKED, and the recorded
reason is arithmetic:

```
108.7 - 6.29 = 102.4 < 105
```

It missed by half a point of a statistic that is not about `AST04`. Its sigma of 6.29 is the
*lowest* of the eleven — `AST04` is the skill the panel agreed on most — and the bound punished
it for the residual disagreement anyway. Under the standard error of the mean the same 18
judgments give `108.7 - 6.29/sqrt(18) = 109.6`, comfortably clear.

## Decision

**We record the flaw and leave the rule exactly as locked. No gate constant changes in this
record, and none changed in this run.**

Specifically:

1. **`ship_floor.py` is untouched.** `POOLED_TARGET` stays 108, `POOLED_LOWER_BOUND` stays 105,
   `FLOORS` stay as vendored, `MIN_ROUNDS` stays 4. Every verdict in `eval/scorecards/*.json`
   and every row on the dashboard is the locked rule's own output, unedited.
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
     `qwen3-235b` and `nova-pro` — the two furthest from centre — and makes the surviving sigma
     a statement about the middle of the panel rather than about its extremes.
   - **Per-judge z-scoring.** Standardise each judge against its own long-run mean and spread
     before pooling, so a judge contributes *where it ranked this skill relative to everything
     else it has scored*, and a constant offset cancels by construction. This is the more
     principled of the two and the more expensive: it needs a long-run baseline per judge, which
     this repo does not yet have and which one run cannot produce.

4. **Adopting any of them requires two things, in this order:** (a) a recorded decision
   superseding this one, naming the rule and its constants before any score is computed under
   it, and (b) a **fresh judged run** whose scorecards are written under the new rule. Neither
   is optional. **A bar changed after seeing the data it is applied to is not a bar** — it is a
   post-hoc description of the result, and every number downstream of it becomes uninterpretable
   because a reader cannot tell which came first, the threshold or the outcome. That is why this
   record fixes nothing today. The measurement in hand was taken under the locked rule and it
   stays reported under the locked rule.

5. **The numbers are generated, not transcribed.** `eval/calibration.py` computes the
   per-provider bias and per-skill sigma above from the scorecards; `tests/test_calibration.py`
   asserts this document's figures match its output. This is not ceremony: the first draft of
   the dashboard's calibration note carried a `nova-pro` bias of −7.9 and a 20.1-point spread
   against scorecards that say −5.4 and 17.9, and nothing on disk could tell a reader which was
   true. An ADR whose whole argument is arithmetic cannot have hand-typed arithmetic in it.

### Cross-repo implication

**A single-judge score and a pooled multi-judge score are not comparable, and neither is a
pooled score from a different panel.** The scale is not the rubric; the scale is the rubric *as
read by these specific judges*. Two consequences follow for anyone quoting a number from here or
bringing one in:

- A pooled mean is only meaningful next to its panel roster. Moving `AST04`'s 108.7 into a
  context judged by a different set of models compares two different instruments.
- `gpt-oss-120b` is a common solo judge, and on this panel it runs **5.2 points harsh**. A skill
  scored 103 by `gpt-oss-120b` alone and a skill scored 103 by this six-model panel are not the
  same skill, and the gap is roughly the width of a grade band. Any score imported from a
  single-judge harness must carry the judge's name, or it is a number without units.

## Consequences

### Positive

- The gate keeps its integrity property. Nobody can say the bar moved once the results were in,
  because it demonstrably did not, and that claim is checkable against the constants in
  `scripts/ship_floor.py` and the verdicts in the scorecards.
- The flaw is now a written, reproducible finding rather than folklore. `eval/calibration.py`
  regenerates every figure, so a reader who distrusts the argument can re-derive it in one
  command instead of trusting a paragraph.
- The `mean − stdev` clause is exposed as sensitive to panel composition, which is a property
  worth knowing before anyone adds a seventh judge and reads the resulting drop as a regression
  in the skills.
- The cross-repo note stops the most likely misuse of these numbers: quoting a pooled mean
  beside a single-judge mean as if the two were on one scale.

### Negative

- **The repository ships 1 of 11 skills under its own gate**, and this record did not move the bar
  to get there. As of the second judged run, nine of eleven skills grade A on the mean and clear
  every one of the eight dimension floors (`advisory` 112.8, `AST05` and `AST08` 110.7, `AST10`
  110.2, `AST01` 109.8, `AST06` 109.3, `AST02` 109.1, `AST03` and `AST04` 108.7). Exactly one,
  `advisory`, also clears the lower bound — 112.8 − 5.43 = 107.4 ≥ 105 — and is the first SHIP
  verdict this repository has recorded. The other eight are Grade A and BLOCKED on the lower bound
  alone. `AST07` 105.4 and `AST09` 105.7 remain genuinely below floor on D6 and D8. Shipping one
  skill under a rule we can defend is worth more than shipping nine under a rule we edited after
  reading the scores.
- Anyone reading the dashboard sees a wall of BLOCKED and may conclude the skills are weak. For
  eight of them it is unsupported — they are Grade A on the mean with every dimension floor clear,
  and blocked by the lower bound alone. This ADR is the only thing standing between that table and a wrong
  reading of it, which makes the ADR load-bearing documentation rather than a footnote.
- Correcting the bound later means the corrected numbers cannot be compared to this run's
  numbers without care, since adoption requires a fresh run. This run becomes a historical
  measurement under a superseded rule rather than a baseline.
- Fixing the bound would not turn the board green, and it would be dishonest to imply it. Seven
  of the eleven are blocked first by a dimension floor and one by the mean target itself; only
  three are blocked by the lower bound alone. D5 Progressive Disclosure, below floor in
  aggregate, is a real weakness in the artifacts and no statistic will retire it.

### Neutral

- `eval/calibration.py` is diagnostic and sits outside the gate path. Nothing imports it into a
  verdict. It prints both candidate bounds side by side — withholding the number the argument
  turns on would be its own dishonesty — but it issues no verdict, ranks no rule, and publishes
  no would-have-shipped list. Choosing between the two columns on the strength of that table is
  exactly what item 4 above forbids.
- The 3.3-sigma figure in `ship_floor.py`'s comment stays as vendored. It is an accurate record
  of the instrument that rule was calibrated against, and rewriting it to match this panel would
  destroy the evidence that the two differ.
- Per-dimension floors are unaffected by this analysis. They are applied to dimension means and
  never divided by a sigma, so the error described here does not reach them.

## Alternatives Considered

### A — Retune the constants now, against this run

Lower `POOLED_LOWER_BOUND`, or swap in `mean − stdev/sqrt(n)`, and re-issue the verdicts from the
scorecards already on disk. Cheapest possible fix and it produces shippable skills the same day.
Rejected outright. The data is in hand; any threshold chosen now is chosen knowing which skills
it passes, and a reader has no way to distinguish a principled correction from a convenient one.
The correction is right and it still has to wait for a fresh run, because the value of the gate
is entirely in the fact that it was set first.

### B — Drop the lower-bound clause and gate on the mean alone

Removes the flawed statistic instead of replacing it. Rejected because the clause is protecting
something real: a mean of 108 drawn from four wildly disagreeing judgments genuinely is weaker
evidence than a mean of 108 from four judgments that agree, and the gate should be able to say
so. The problem is the denominator, not the intent.

### C — Cut the panel back to judges that agree

Drop `qwen3-235b` and `nova-pro` and sigma collapses on its own, no rule change required.
Rejected as the incentive at its worst: it improves the reported numbers by narrowing the
evidence, and it selects judges for agreeing with each other rather than for reading well. It
would also violate the roster doctrine this repo already holds — providers are declared with a
recorded reason, never dropped because of what they said.

### D — Report both bounds on the dashboard and let readers choose

Publish `mean − stdev` and `mean − stdev/sqrt(n)` side by side without designating either as the
gate. Rejected as a gate: a rule with two answers is not a rule, and "the reader decides" is how
the more flattering number becomes the quoted one. Retained as *diagnostics only* — both columns
are printed by `eval/calibration.py`, which gates nothing.

## References

- `scripts/ship_floor.py` — the locked rule, its constants, and the 3.3-sigma calibration comment
  this record measures against.
- `eval/calibration.py` — regenerates every figure quoted here from `eval/scorecards/*.json`.
- `tests/test_calibration.py` — fails if this document's figures drift from that script, or if a
  gate constant changes without a superseding record.
- `eval/scorecards/*.json` — the 198 judgments, one file per skill, each carrying its own
  `aggregate.judgments` array.
- `docs/skill-judge-dashboard.md` — the published results table, the rubric, and the ship rule as
  a reader meets them.
- `docs/adr/0004-per-scenario-detectability-contract.md` — the companion decision on not letting
  a measurement's convenience choose its scope.
