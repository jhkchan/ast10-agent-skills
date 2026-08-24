---
artifact: adr
version: "1.2"
created: 2026-08-23
updated: 2026-08-24
status: accepted
---

# ADR-0005: The Ship Rule's Lower Bound Measures Judge Disagreement, Not Skill Quality

## Status

Accepted

**Date:** 2026-08-23
**Figures refreshed:** 2026-08-24, against the fourth judged run — the second scored with the
rubric's bands in the prompt, and the first in which the skills rather than the instrument
were the thing that changed. The decision below is unchanged; the measurements are new, and
the argument has moved in both directions since version 1.1. Both moves are stated.
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
Eleven skills × three rounds × six providers were attempted; **180 judgments bind**, the other
18 having been refused as malformed by the justification contract the judge prompt enforces.
The per-skill sigma across those 180 is **3.74 to 6.04**, still up to nearly twice the figure
the rule was tuned against.

### The spread is bias, not noise

Sigma is that wide because the judges disagree systematically. Against a pooled mean of
**111.0**:

| Judge | n | Mean | Bias vs pooled | Round means |
| --- | ---: | ---: | ---: | --- |
| `bedrock/qwen3-235b` | 32 | 117.7 | +6.7 | 118.2 / 117.1 / 117.9 |
| `anthropic-compatible/glm-5.2` | 29 | 112.1 | +1.2 | 112.3 / 112.4 / 111.6 |
| `claude-cli/sonnet` | 32 | 110.4 | -0.5 | 110.6 / 110.7 / 109.9 |
| `bedrock/nova-pro` | 29 | 110.0 | -1.0 | 110.3 / 110.4 / 108.9 |
| `bedrock/deepseek-v3.2` | 26 | 109.2 | -1.8 | 109.3 / 109.6 / 108.5 |
| `bedrock/gpt-oss-120b` | 32 | 106.1 | -4.9 | 106.1 / 106 / 106.3 |

Top to bottom that is an **11.6-point spread** — still most of a grade band between the harshest
and the most generous reader of the same eleven files, and narrower than the 15.4 of the run
before it. Four of the six judges sit within 1.8 points of the pooled mean. The spread survives
because of the two ends, `qwen3-235b` at +6.7 and `gpt-oss-120b` at -4.9, and a spread carried
by two judges is exactly as fatal to a sigma-based bound as a spread carried by six.

The right-hand column is what settles the diagnosis. Each judge scored the whole roster three
independent times, and no judge moved more than **1.5 points** between its own rounds — the
widest is `nova-pro` at 110.3 / 110.4 / 108.9, and `gpt-oss-120b` moved 0.3 across the entire
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
demands a mean of **108.7 to 111.0** — 90.6% to 92.5% of the rubric — rather than the
108 (90.0%) it names as its target. Nobody chose a 90.6-92.5% bar. It arrived as a side effect
of adding judges. It is a milder distortion than the 90.4-94.2% the previous run implied, and
it is the same distortion: the bar still floats on panel composition rather than on the
constant.

### The perverse incentive, stated plainly

Adding a judge to the panel makes the gate **harder** even when the skill is byte-identical.
A seventh judge with a novel calibration widens sigma, sigma raises the effective mean bar, and
the skill that passed yesterday fails today without a character changing. The rule as written
penalises panel diversity and rewards a narrow panel of like-minded judges — the exact opposite
of why `docs/skill-judge-dashboard.md` says the matrix is multi-provider: "a single judge's
idiosyncrasies become the rubric otherwise."

### The concrete case

Version 1.1 of this record used `AST04` as the worked example. `AST04` now ships — 112.6, every
floor clear, `mean − stdev` 108.9 — so it can no longer carry the argument, and the argument
does not need it to. Run 4 produced a cleaner instance than any run before it.

`AST09` pooled a mean of **108.2** across 17 judgments — Grade A — with **every one of the eight
dimension means above its floor**: D1 17.8, D2 13.1, D3 13.9, D4 14.6, D5 13.1, D6 13.4, D7 8.6,
D8 13.7. There is no finding about the file left in its verdict. It is BLOCKED, and the whole of
the reason is arithmetic:

```
108.2 - 4.85 = 103.4 < 105
```

Under the standard error of the mean the same 17 judgments give `108.2 − 4.85/√17 = 107.0`,
comfortably clear. `AST09` is now the only skill on the board blocked by the lower bound, and
nothing else is against it: no dimension below floor, no shortfall on the mean, no rubric
mismatch, 17 pooled judgments against a `MIN_ROUNDS` of 4. It is the defect this record
describes with every confounder removed.

The same clause moved a verdict in the other direction on the same run, which is worth recording
because it is the less obvious half. `AST08` was BLOCKED in run 3 by the lower bound alone
(110.3 − 5.65 = 104.6) and SHIPs in run 4 at 110.8 − 4.67 = 106.1. `AST08`'s `SKILL.md` is
byte-identical across the two runs and its `D3` mean *fell*, 13.5 to 13.2. What changed was the
panel's dispersion. A rule that can flip a verdict on a file nobody edited is not measuring the
file.

### The controlled result: `D3` anti-patterns are load-bearing

Between run 3 and run 4 the judge prompt, the rubric pin, the panel roster and every gate
constant were held fixed. Exactly one thing changed: eight skills — `AST02`-`AST07`, `AST09`,
`AST10` — gained an explicit, grounded anti-pattern `NEVER` section. `AST01`, `AST08` and
`advisory` were deliberately left untouched because they had already cleared the `D3` floor in
run 3.

That makes run 3 → run 4 the first comparison this repository can legitimately make
skill-by-skill, and the result is unambiguous: all eight treated skills rose on `D3` and on the
pooled mean, all eight crossed the `D3` floor, seven went BLOCKED → SHIP; all three untouched
controls *fell* on `D3`, and `AST01` fell through the floor it had cleared by 0.1 points. The
full table, and what it says about treating a 0.1-point margin as clearance, is in
[`../skill-judge-dashboard.md`](../skill-judge-dashboard.md), "The controlled result". It is
worth more than the headline ship count, and it is the reason this record now has to argue in
two directions at once.

### What the two instrument changes did to the panel

Runs 1 (`eval/scorecards-run1/`) and 2 (`eval/scorecards-run2/`) were scored by a prompt that
transmitted the eight dimension *names* and their maxima and **none of the rubric's score
bands**, and that forbade prose. Six judges each graded against a private scale invented from a
label. Run 3 (`eval/scorecards-run3/`) was the first scored with each dimension's band table
quoted verbatim and a one-sentence justification required per dimension. Run 4 — the corpus in
`eval/scorecards/`, and the source of every figure above — was scored by that same prompt, so
it is a measurement of the skills and not of the instrument.

| Judge | Run 2 bias | Run 3 bias | Run 4 bias |
| --- | ---: | ---: | ---: |
| `bedrock/qwen3-235b` | +10.8 | +8.7 | +6.7 |
| `anthropic-compatible/glm-5.2` | +0.7 | +0.0 | +1.2 |
| `claude-cli/sonnet` | −3.7 | −0.2 | −0.5 |
| `bedrock/nova-pro` | −5.7 | −0.7 | −1.0 |
| `bedrock/deepseek-v3.2` | +0.3 | −1.2 | −1.8 |
| `bedrock/gpt-oss-120b` | −2.4 | −6.8 | −4.9 |

- **Median per-skill sigma fell 6.43 → 5.65 → 4.67** across the three measured states, and the
  worst per-skill sigma fell 14.04 → 8.01 → 6.04. Giving the judges the rubric tightened
  agreement; giving them a concrete anti-pattern list to point at tightened it again. Only the
  first of those two was a change to the instrument, which is why only the second licenses a
  skill-by-skill reading.
- **Between-judge spread fell 16.5 → 15.4 → 11.6**, and the largest within-judge
  round-to-round spread fell 4.0 → 2.3 → 1.5. The judges were always self-consistent; they are
  now also closer to each other.
- **`bedrock/qwen3-235b` is flagged NON-DISCRIMINATING again, and it is not a relapse.** Under
  the unanchored prompt it returned exactly 120.0 on all eleven skills, from three distinct
  values, for an across-skill sigma of 0.00. Under the rubric-grounded prompt it ranked: run 3
  placed the roster across 114.7-119.7, an across-skill sigma of 1.38, and it came out COARSE.
  In run 4 it still ranks — 116.3 to 119.3, seven distinct dimension values — but the *skills*
  moved up into its ceiling while its ceiling did not move, so its across-skill sigma fell to
  0.94 and crossed the 1.0 floor. The judge did not get worse. The population it was ranking got
  tighter at the top of the scale it is willing to use. That is a real limitation of a judge
  which puts 77% of its dimension scores at a dimension's maximum, it is now on the record, and
  it is a second instance of the same lesson `AST01` teaches below: a threshold cleared by 0.38
  is not a threshold cleared.
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
panel did: sigma is smaller, so the implied mean bar fell from 108.4-113.0 to 108.7-111.0, and
it is still above the 108 the rule names, still set by the panel rather than by the constant,
and still rising with every judge added. Improving the measurement shrank the error. Only
changing the rule removes it.

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
   which was true. It is also why refreshing this document for run 4 was a mechanical exercise
   rather than a judgement call — eleven tests failed the moment the corpus moved, each naming
   the figure that had gone stale, including the one that had pinned `AST04` as the worked
   example and could no longer be satisfied by a true sentence. An ADR whose whole argument is
   arithmetic cannot have hand-typed arithmetic in it.

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

- The gate keeps its integrity property, and run 4 is the run that proves it was worth keeping.
  Nobody can say the bar moved once the results were in, because it demonstrably did not —
  across four runs, a rebuilt judge prompt, and a board that went from one shippable skill to
  nine — and that claim is checkable against the constants in `scripts/ship_floor.py` and the
  verdicts in the scorecards. The skills were changed to meet the bar. The bar was not changed
  to meet the skills.
- **The repository now ships 9 of 11 skills under the rule this record declined to retune.** The
  honest reading of that is that the bar was demanding, not that it was wrong to hold: eight
  skills were repaired against the reasons the judges gave, and the repairs measured.
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
  of eleven now clear the locked rule with no constant changed, so the clause can no longer be
  described as the thing standing between this repository and a shippable result. It is a
  latent defect in a gate that is currently passing, which is a materially weaker case for
  fixing it than the one this ADR opened with, and pretending otherwise would be the same
  dishonesty in the opposite direction.
- **What still holds is the single clean instance the earlier version never had.** `AST09` has a
  Grade-A mean of 108.2, every one of the eight dimension floors clear, 17 pooled judgments, and
  is BLOCKED solely because `108.2 − 4.85 = 103.4 < 105`. Under the standard error of the mean it
  clears comfortably at 107.0. In run 3 this defect was entangled — the skills it blocked also
  had real `D3` findings against them, so a reader could reasonably suspect the statistic of
  being a proxy for a genuine weakness. It is not entangled now. One skill, one reason, and the
  reason is not about the skill.
- **A dimension floor cleared by 0.1 points was treated as cleared, and it should not have
  been.** `AST01` held `D3` 13.1 against a floor of 13 in run 3 and was excluded from the
  anti-pattern pass on that basis. It measured 12.2 in run 4 and is the only skill on the board
  blocked by a floor. `AST08` was excluded on a 0.5-point margin and fell to 13.2 — a 0.2-point
  margin — which is the same finding without the consequence yet. Judge scores are a
  distribution; a margin inside the run-to-run movement of that distribution is noise wearing a
  verdict's clothes. The remedy is a decision about margins, and it belongs in its own record
  rather than here.
- Anyone reading the dashboard now sees a mostly-green board and may conclude the gate is easy.
  It is not, and the archived runs are the proof: the same rule, unmodified, blocked ten of
  eleven skills two runs ago. The board is green because the artifacts changed.
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
- Per-judgment counts are not uniform across judges — 26 to 32 rather than a flat 33 — because
  the justification contract refuses a malformed judgment instead of averaging it in. Uneven `n`
  is the honest shape of a run that rejects bad rows; it means a per-provider bias is a slightly
  noisier estimate for the judges that lost the most rows, and it does not bias the pooled mean
  toward any skill, since rejections are spread across the roster.
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

Nine of eleven skills now clear the locked rule, and it would be tempting to close this record as
overtaken by events. Rejected as a category error, and recorded here because it is the most
attractive wrong conclusion available from run 4 — the same shape as version 1.1's temptation to
read a narrower sigma as a repaired statistic. A gate that currently passes is not a correct
gate. `mean − stdev` is still not a bound on a mean, the implied bar is still above the target
the rule names, it still rises when a judge is added, and it still flipped `AST08`'s verdict on a
file nobody edited. A latent defect is a weaker reason to act, which this record says plainly
under Consequences; it is not a reason to stop describing it.

## References

- `scripts/ship_floor.py` — the locked rule, its constants, and the 3.3-sigma calibration comment
  this record measures against.
- `eval/calibration.py` — regenerates every figure quoted here from `eval/scorecards/*.json`.
- `tests/test_calibration.py` — fails if this document's figures drift from that script, or if a
  gate constant changes without a superseding record. Its worked-example assertion derives which
  skill the example must be from the verdicts, so this record cannot go on quoting a skill that
  has since shipped.
- `tests/test_judge_quality.py` — holds the judge-quality verdicts against every recorded corpus,
  including run 2's flat judge, run 3's repaired one, and run 4's re-flag.
- `eval/scorecards/*.json` — run 4: the 180 binding judgments of 198 attempted, one file per
  skill, each carrying its own `aggregate.judgments` array.
- `eval/scorecards-run3/` — run 3, frozen. Scored by the same prompt as run 4, so the two are
  comparable skill-by-skill; that comparison is the controlled result above.
- `eval/scorecards-run1/`, `eval/scorecards-run2/` — the two runs scored without the rubric's
  bands, retained unedited as the evidence for the prompt defect.
- `scripts/judge_harness.py` — the prompt: the pinned rubric quoted verbatim, a justification
  required per dimension, and the artifact fenced as data.
- `docs/skill-judge-dashboard.md` — the published results table, the controlled result, the
  rubric, and the ship rule as a reader meets them.
- `docs/adr/0004-per-scenario-detectability-contract.md` — the companion decision on not letting
  a measurement's convenience choose its scope.
