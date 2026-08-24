---
artifact: adr
version: "1.1"
created: 2026-08-23
updated: 2026-08-24
status: accepted
---

# ADR-0005: The Ship Rule's Lower Bound Measures Judge Disagreement, Not Skill Quality

## Status

Accepted

**Date:** 2026-08-23
**Figures refreshed:** 2026-08-24, against the third judged run — the first scored with the
rubric's bands in the prompt. The decision below is unchanged; only the measurements are.
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
Eleven skills × three rounds × six providers were attempted; **177 judgments bind**, the other
21 having been refused as malformed by the justification contract the judge prompt now enforces.
The per-skill sigma across those 177 is **3.44 to 8.01**, still up to two and a half times the
figure the rule was tuned against.

### The spread is bias, not noise

Sigma is that wide because the judges disagree systematically. Against a pooled mean of
**108.7**:

| Judge | n | Mean | Bias vs pooled | Round means |
| --- | ---: | ---: | ---: | --- |
| `bedrock/qwen3-235b` | 32 | 117.3 | +8.7 | 117.7 / 117.1 / 117.2 |
| `anthropic-compatible/glm-5.2` | 23 | 108.7 | +0.0 | 108.7 / 108.3 / 109.7 |
| `claude-cli/sonnet` | 33 | 108.5 | -0.2 | 108.3 / 108.5 / 108.7 |
| `bedrock/nova-pro` | 30 | 108.0 | -0.7 | 107.5 / 108.4 / 108.4 |
| `bedrock/deepseek-v3.2` | 27 | 107.4 | -1.2 | 106.7 / 107.5 / 109 |
| `bedrock/gpt-oss-120b` | 32 | 101.9 | -6.8 | 102.6 / 101.8 / 101.2 |

Top to bottom that is a **15.4-point spread** — more than a grade band between the harshest and
the most generous reader of the same eleven files. The middle of the panel has closed up: four
of the six judges now sit within 1.2 points of the pooled mean. The spread survives because of
the two ends, `qwen3-235b` at +8.7 and `gpt-oss-120b` at -6.8, and a spread carried by two
judges is exactly as fatal to a sigma-based bound as a spread carried by six.

The right-hand column is what settles the diagnosis. Each judge scored the whole roster three
independent times, and no judge moved more than **2.3 points** between its own rounds — the
widest is `deepseek-v3.2` at 106.7 / 107.5 / 109, and `claude-cli/sonnet` moved 0.4 across the
entire roster. Every judge is precise. They are precise about different things. What sigma is
measuring across the pooled column is therefore mostly a constant per judge, and a constant per
judge carries no information about any skill.

### The statistical error

`mean − stdev` is a **spread** statistic. The gate applies it as a **confidence bound on the
mean** — "is this skill's true quality above the bar?". Those are different questions and they
have different denominators. The uncertainty of a mean shrinks with sample size:
`stdev / sqrt(n)`. The spread does not shrink at all. Pooling 15 judgments instead of 4 buys a
much better estimate of the mean and leaves `mean − stdev` exactly where it was.

Written out, `mean − stdev ≥ 105` is the same constraint as `mean ≥ 105 + stdev`. So the sigma a
panel happens to produce sets the mean the rule actually demands. At this panel's sigma the rule
demands a mean of **108.4 to 113.0** — 90.4% to 94.2% of the rubric — rather than the
108 (90.0%) it names as its target. Nobody chose a 90-94% bar. It arrived as a side effect of
adding judges. It is a milder distortion than the 92-99% the previous run implied, and it is the
same distortion: the bar still floats on panel composition rather than on the constant.

### The perverse incentive, stated plainly

Adding a judge to the panel makes the gate **harder** even when the skill is byte-identical.
A seventh judge with a novel calibration widens sigma, sigma raises the effective mean bar, and
the skill that passed yesterday fails today without a character changing. The rule as written
penalises panel diversity and rewards a narrow panel of like-minded judges — the exact opposite
of why `docs/skill-judge-dashboard.md` says the matrix is multi-provider: "a single judge's
idiosyncrasies become the rubric otherwise."

### The concrete case

`AST04` pooled a mean of **108.7** across 15 judgments — Grade A. It is BLOCKED twice over, and
only one of the two reasons is about `AST04`.

The reason that is about `AST04` is real: its `D3` Anti-Pattern Quality mean is 12.4 against a
floor of 13, and with the rubric's bands now in the prompt the judges can say why — three of
`gpt-oss-120b`'s reads place it in the rubric's own "8-11 specific anti-pattern" band rather than
above it. That is a finding about the file. No statistic retires it and none should.

The other reason is arithmetic:

```
108.7 - 6.24 = 102.5 < 105
```

Under the standard error of the mean the same 15 judgments give `108.7 − 6.24/√15 = 107.1`,
comfortably clear. Two skills isolate the effect with nothing else in the way: `AST01` (109.8)
and `AST08` (110.3) are Grade A with **every** dimension mean above its floor, and both are
blocked by the lower bound alone — by 0.6 and 0.4 points of a statistic that is not about them.
Under the standard error of the mean both clear it (108.5 and 108.8).

### What the rubric fix did to the panel

Runs 1 (`eval/scorecards-run1/`) and 2 (`eval/scorecards-run2/`) were scored by a prompt that
transmitted the eight dimension *names* and their maxima and **none of the rubric's score
bands**, and that forbade prose. Six judges each graded against a private scale invented from a
label. Run 3 — the corpus in `eval/scorecards/`, and the source of every figure above — is the
first scored with each dimension's band table quoted verbatim and a one-sentence justification
required per dimension.

The panel moved, and it moved the way the diagnosis predicted:

| Judge | Run 2 bias | Run 3 bias | Move |
| --- | ---: | ---: | ---: |
| `bedrock/qwen3-235b` | +10.8 | +8.7 | −2.1 |
| `anthropic-compatible/glm-5.2` | +0.7 | +0.0 | −0.7 |
| `claude-cli/sonnet` | −3.7 | −0.2 | +3.5 |
| `bedrock/nova-pro` | −5.7 | −0.7 | +5.0 |
| `bedrock/deepseek-v3.2` | +0.3 | −1.2 | −1.5 |
| `bedrock/gpt-oss-120b` | −2.4 | −6.8 | −4.4 |

- **Four of six judges now sit within 1.2 points of the pooled mean**, against two of six in
  run 2. The judges that had been reading a label are reading a scale.
- **Within-judge round-to-round spread fell from 4.0 points to 2.3.** The judges were already
  self-consistent; anchoring them did not cost that.
- **Median per-skill sigma fell from 6.43 to 5.65**, and the worst per-skill sigma fell from
  14.04 to 8.01. The 14.04 was run 2's `AST07`, where `nova-pro` returned 70 / 75 / 91 while the
  other five judges' fifteen judgments ran 101 to 120 — one judge, on one skill, carrying a whole
  grade band of the panel's sigma. Nothing that shaped survived the fix: `AST07`'s run-3 sigma is
  6.19, and `nova-pro`'s worst read of it is 99.
- **`bedrock/qwen3-235b` moved from NON-DISCRIMINATING to COARSE.** Under the unanchored prompt
  it returned exactly 120.0 on all eleven skills in all three rounds, drawn from three distinct
  values — 10, 15 and 20, precisely the three dimension maxima — and its across-skill sigma was
  0.00. Under the rubric-grounded prompt it returns 117.7 / 117.1 / 117.2, uses nine distinct
  dimension values, and ranks the skills. It is still coarse: 75% of its dimension scores are
  multiples of five and 75% sit at a dimension's maximum, which is what COARSE names. But a judge
  that had been returning a flat maximum began ranking, and **no judge on run 3's panel is
  flagged NON-DISCRIMINATING**. The prompt was the defect, and repairing it repaired the judge.
- **`gpt-oss-120b` got harsher, from -2.4 to -6.8, and that is the fix working too.** It is now
  the judge most willing to use the bottom of a band, and its low scores are checkable: it scored
  `AST02`'s `D3` at 4 with the reason "only generic warnings appear and there is no specific
  NEVER list", which is a claim a reader can settle by opening the file. A harsher number
  attached to a verifiable reason is better evidence than a kinder number attached to nothing.

Two things this does **not** license. First, run 3 is not run 3 of a series — it is a new
baseline. A pooled mean is a statement about the rubric *as read by these judges*, the read
changed, and differencing run 3 against run 2 skill-by-skill would be comparing two instruments.
The bias table above is a comparison of *judges*, which is exactly the quantity the instrument
change was meant to move, and is the only cross-run comparison this record makes. Second,
**runs 1 and 2 are retained as the evidence for the defect, not as measurements of skill
quality.** Their absolute means say what an unanchored judge produced. They are kept unedited
because deleting them would destroy the only proof that the two instruments differ.

And the finding stands. A better-calibrated panel did not repair the statistic: sigma is smaller,
so the implied mean bar fell from 110.4-119.0 to 108.4-113.0, and it is still above the 108 the
rule names, still set by the panel rather than by the constant, and still rising with every judge
added. Improving the instrument shrank the error. Only changing the rule removes it.

## Decision

**We record the flaw and leave the rule exactly as locked. No gate constant changes in this
record, and none changed in this run.**

Specifically:

1. **`ship_floor.py` is untouched.** `POOLED_TARGET` stays 108, `POOLED_LOWER_BOUND` stays 105,
   `FLOORS` stay as vendored, `MIN_ROUNDS` stays 4. Every verdict in `eval/scorecards/*.json`
   and every row on the dashboard is the locked rule's own output, unedited. This survived the
   prompt rebuild: rebuilding the instrument is not permission to move the bar.
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
     this repo does not yet have and which one run cannot produce — and which the prompt rebuild
     reset, since a baseline gathered under the unanchored prompt does not describe this judge.

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
   against run 1's scorecards, which say −5.4 and 17.9, and nothing on disk could tell a reader
   which was true. It is also why refreshing this document for run 3 was a mechanical exercise
   rather than a judgement call — fifteen tests failed the moment the corpus moved, each naming
   the figure that had gone stale. An ADR whose whole argument is arithmetic cannot have
   hand-typed arithmetic in it.

### Cross-repo implication

**A single-judge score and a pooled multi-judge score are not comparable, and neither is a
pooled score from a different panel.** The scale is not the rubric; the scale is the rubric *as
read by these specific judges*. Two consequences follow for anyone quoting a number from here or
bringing one in:

- A pooled mean is only meaningful next to its panel roster. Moving `AST04`'s 108.7 into a
  context judged by a different set of models compares two different instruments.
- `gpt-oss-120b` is a common solo judge, and on this panel it runs **6.8 points harsh**. A skill
  scored 101 by `gpt-oss-120b` alone and a skill scored 101 by this six-model panel are not the
  same skill, and the gap is more than half a grade band. On run 2's panel the same model ran
  2.4 points harsh, so the offset is a property of the panel *and the prompt*, not a constant of
  the model that can be looked up once. Any score imported from a single-judge harness must
  carry the judge's name and the prompt it read, or it is a number without units.

## Consequences

### Positive

- The gate keeps its integrity property. Nobody can say the bar moved once the results were in,
  because it demonstrably did not — across three runs and a rebuilt judge prompt — and that
  claim is checkable against the constants in `scripts/ship_floor.py` and the verdicts in the
  scorecards.
- The flaw is now a written, reproducible finding rather than folklore. `eval/calibration.py`
  regenerates every figure, so a reader who distrusts the argument can re-derive it in one
  command instead of trusting a paragraph.
- The `mean − stdev` clause is exposed as sensitive to panel composition, which is a property
  worth knowing before anyone adds a seventh judge and reads the resulting drop as a regression
  in the skills.
- The diagnosis is now falsifiable and was tested. It predicted that judges disagreeing about a
  scale they could not see would converge once they could, and they did: four of six inside 1.2
  points, median sigma down, and the panel's flat judge started ranking. Predictions that come
  true are the cheapest evidence an argument can carry.
- The cross-repo note stops the most likely misuse of these numbers: quoting a pooled mean
  beside a single-judge mean as if the two were on one scale.

### Negative

- **The repository ships 1 of 11 skills under its own gate**, and this record did not move the bar
  to get there. Three skills grade A on the mean and clear every one of the eight dimension
  floors (`advisory` 112.3, `AST08` 110.3, `AST01` 109.8). Exactly one, `advisory`, also clears
  the lower bound — 112.3 − 3.44 = 108.9 ≥ 105 — and holds the only SHIP verdict on the board.
  `AST01` and `AST08` miss it by 0.6 and 0.4 points with nothing else against them. Shipping one
  skill under a rule we can defend is worth more than shipping three under a rule we edited after
  reading the scores.
- The other eight are blocked first by a dimension floor, and `D3` Anti-Pattern Quality is the
  binding one in all eight (`AST07` also misses `D2`). That is not the lower bound's fault and
  this ADR does not excuse it. It is the clearest thing the rubric-grounded prompt bought:
  under the unanchored prompt `D3` looked fine, and the reasons the judges now attach name a
  specific absence in specific files. Anti-pattern sections added to the skill packages *after*
  this run are not measured by it; whether they move `D3` is a question only a fresh judged run
  can answer.
- Anyone reading the dashboard sees a wall of BLOCKED and may conclude the skills are uniformly
  weak. For two of them that is unsupported — Grade A, every dimension floor clear, blocked by
  the lower bound alone. This ADR is the only thing standing between that table and a wrong
  reading of it, which makes it load-bearing documentation rather than a footnote.
- Correcting the bound later means the corrected numbers cannot be compared to this run's
  numbers without care, since adoption requires a fresh run. This run becomes a historical
  measurement under a superseded rule rather than a baseline.
- Fixing the bound would not turn the board green, and it would be dishonest to imply it. It
  would take the board from one skill to three: `AST01` and `AST08` clear the standard error of
  the mean (108.5 and 108.8) and nothing else blocks them. The remaining eight stay blocked on
  `D3`, which is a real weakness in the artifacts and no statistic will retire it.

### Neutral

- `eval/calibration.py` is diagnostic and sits outside the gate path. Nothing imports it into a
  verdict. It prints both candidate bounds side by side — withholding the number the argument
  turns on would be its own dishonesty — but it issues no verdict, ranks no rule, and publishes
  no would-have-shipped list. Choosing between the two columns on the strength of that table is
  exactly what item 4 above forbids.
- The 3.3-sigma figure in `ship_floor.py`'s comment stays as vendored. It is an accurate record
  of the instrument that rule was calibrated against, and rewriting it to match this panel would
  destroy the evidence that the two differ.
- Per-judgment counts are no longer uniform across judges — 23 to 33 rather than a flat 33 —
  because the justification contract refuses a malformed judgment instead of averaging it in.
  Uneven `n` is the honest shape of a run that rejects bad rows; it means a per-provider bias is
  a slightly noisier estimate for the judges that lost the most rows, and it does not bias the
  pooled mean toward any skill, since rejections are spread across the roster.
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

Drop `qwen3-235b` and `gpt-oss-120b` and sigma collapses on its own, no rule change required.
Rejected as the incentive at its worst: it improves the reported numbers by narrowing the
evidence, and it selects judges for agreeing with each other rather than for reading well. On
this run it would be worse than that — `gpt-oss-120b` is the judge that most often cites a
specific absence in a specific file, so the panel would be cut back by discarding its best-
evidenced reader. It would also violate the roster doctrine this repo already holds — providers
are declared with a recorded reason, never dropped because of what they said.

### D — Report both bounds on the dashboard and let readers choose

Publish `mean − stdev` and `mean − stdev/sqrt(n)` side by side without designating either as the
gate. Rejected as a gate: a rule with two answers is not a rule, and "the reader decides" is how
the more flattering number becomes the quoted one. Retained as *diagnostics only* — both columns
are printed by `eval/calibration.py`, which gates nothing.

### E — Fix the judge prompt and call the statistic fixed

The rubric rebuild narrowed sigma materially, and it would be tempting to read the narrower
implied bar (108.4-113.0, down from 110.4-119.0) as the problem going away. Rejected as a
category error, and recorded here because it is the most attractive wrong conclusion available
from run 3. A better instrument makes the error smaller; it does not make `mean − stdev` a bound
on a mean. The implied bar is still above the target the rule names, still a function of who is
on the panel, and still rises when a judge is added. Improving measurement and correcting a
formula are different repairs and only one of them was made.

## References

- `scripts/ship_floor.py` — the locked rule, its constants, and the 3.3-sigma calibration comment
  this record measures against.
- `eval/calibration.py` — regenerates every figure quoted here from `eval/scorecards/*.json`.
- `tests/test_calibration.py` — fails if this document's figures drift from that script, or if a
  gate constant changes without a superseding record.
- `tests/test_judge_quality.py` — holds the judge-quality verdicts, including the run-2 → run-3
  move from NON-DISCRIMINATING to COARSE, against both recorded corpora.
- `eval/scorecards/*.json` — run 3: the 177 binding judgments of 198 attempted, one file per
  skill, each carrying its own `aggregate.judgments` array.
- `eval/scorecards-run1/`, `eval/scorecards-run2/` — the two runs scored without the rubric's
  bands, retained unedited as the evidence for the defect.
- `scripts/judge_harness.py` — the rebuilt prompt: the pinned rubric quoted verbatim, a
  justification required per dimension, and the artifact fenced as data.
- `docs/skill-judge-dashboard.md` — the published results table, the rubric, and the ship rule as
  a reader meets them.
- `docs/adr/0004-per-scenario-detectability-contract.md` — the companion decision on not letting
  a measurement's convenience choose its scope.
