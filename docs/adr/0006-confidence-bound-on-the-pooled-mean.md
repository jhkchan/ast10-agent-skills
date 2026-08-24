---
artifact: adr
version: "1.0"
created: 2026-08-24
updated: 2026-08-24
status: accepted
supersedes: "0005, in part — Decision item 1's lower-bound constant and item 2's 'stated, not applied'. The DIAGNOSIS in 0005, its figures, item 3, item 4's procedure and item 5 all stand unchanged."
---

# ADR-0006: The Ship Rule's Second Clause Becomes a Confidence Bound on the Mean

## Status

Accepted

**ACCEPTED and IMPLEMENTED in `scripts/ship_floor.py`.** The constant below was written down
and this record accepted **before** any score was computed under it.

**Run 5 must be a fresh judged run.** The corpus in `eval/scorecards/` is run 4, scored under
the retired clause. Its verdicts stay exactly as issued and **no run-4 verdict may be re-issued,
re-gated or re-described as though this rule had produced it** — not in the dashboard, not in
the README, not in a changelog line. Adoption is complete only when run 5's scorecards are
written under the rule named below; until then the published board is a historical measurement
and every page showing it says so. `eval/scorecards-run{1,2,3}/` are likewise untouched.

**Date:** 2026-08-24
**Deciders:** Jacky Chan (Reviewer/Contributor, feature owner)

This is the superseding record that [ADR-0005](0005-judge-panel-calibration-and-the-lower-bound.md)
item 4 requires: *"a recorded decision superseding this one, naming the rule and its constants
before any score is computed under it."* ADR-0005's diagnosis is adopted here in full and is not
re-argued. What this record adds is the part ADR-0005 deliberately left open: **which constant,
against which reference level, and why.**

### Exactly what this supersedes in ADR-0005, and what it does not

| ADR-0005 | Status after this record |
| --- | --- |
| The **diagnosis** — `mean − stdev` is a spread statistic used as a confidence bound on a mean; the implied bar floats on panel composition; adding a judge makes the gate harder on an unedited file | **Stands, unchanged and not marked wrong.** It is the evidence this change rests on. Every figure in it stays regenerable by `eval/calibration.py`. |
| Decision **item 1** — "`ship_floor.py` is untouched … `POOLED_LOWER_BOUND` stays 105" | **Superseded.** `POOLED_LOWER_BOUND` is retired as a gate constant. `POOLED_TARGET`, `FLOORS` and `MIN_ROUNDS` are **not** superseded and do not move. |
| Decision **item 2** — "the correct bound is stated, not applied" | **Superseded.** It is applied, against the boundary derived below rather than against 105. |
| Decision **item 3** — trimmed judge vote, per-judge z-scoring | **Stands as open work.** Neither is adopted here. |
| Decision **item 4** — a superseding record first, then a fresh run | **Satisfied, not superseded.** This is the record; run 5 is the fresh run. The procedure it lays down remains binding on the next change. |
| Decision **item 5** — figures are generated, not transcribed | **Stands**, and applies to this record too. |
| Two sentences in 0005's Consequences — `AST09` "clears comfortably at 107.0", and fixing the bound "would take the board from nine skills to ten" | **True against the retired 105 threshold, false against the boundary this clause uses.** Corrected under "Consequence check" below. ADR-0005's own text is left exactly as written; the correction lives here and in the note at the top of that file. |

### The one and only change to the gate

`scripts/ship_floor.py` was byte-identical for the whole of this project until this record, and a
number of documents and tests said so. That claim is now a different, weaker, still-checkable
claim: **the gate was changed exactly once, by recorded decision, after the defect was
demonstrated and before a fresh run.** Every place asserting the stronger form has been updated
to the true one — not deleted, and not left overstating. The updated set is `scripts/ship_floor.py`
itself, `docs/skill-judge-dashboard.md`, `README.md`, `CONTRIBUTING.md`, `docs/architecture.md`,
`scripts/judge_harness.py`, `NOTICE`, `THIRD_PARTY_LICENSES.md`, `eval/calibration.py`,
`eval/scorecards/README.md`, and the tests that pin the constants
(`tests/test_calibration.py`, `tests/scripts/test_ship_floor.py`, `tests/test_docs.py`).

### Why this is not goalpost-moving, in arithmetic

The accusation this change has to answer is that a bar was lowered to let something through. It
has a numeric answer, and the numbers are stated here rather than buried in a consequence
section:

- **9 of 11 skills ALREADY SHIP under the locked rule** (run 4, `eval/scorecards/`). The board
  was not stuck. Eight skills were repaired against the reasons the judges gave and the repairs
  measured; the gate was doing its job.
- **On run-4 data the new clause touches exactly one skill: `AST09`.** Every dimension floor
  clear, Grade-A mean 108.2, blocked under the locked rule solely by `mean − σ = 103.4 < 105`.
  It is the only skill on the board whose clause-2 status the change reaches.
- **And `AST09` does not flip.** Measured against the boundary the corrected clause actually
  asks about, its bound is `108.2 − 1.18 = 107.0 < 108`. It moves from *blocked by a spread
  statistic* to *blocked by a confidence bound* — a change of reason, not of outcome.
- **So the count is 9 before and 9 after. Zero verdicts change. No pass was manufactured**, not
  even one. The full eleven-row table is under "Consequence check" below.

A change that fixes a proven determinism defect and alters no result is the only kind of gate
change that carries no suspicion whatsoever, and that is why it is made now rather than later:
the moment it starts buying something is the moment it can no longer be made cleanly.

## Context

### The evidence is a determinism failure, not a calibration complaint

The locked rule requires `mean >= POOLED_TARGET (108)` **and**
`mean - stdev >= POOLED_LOWER_BOUND (105)`. `mean - stdev` is a **spread** statistic used as a
**confidence bound on a mean**. ADR-0005 establishes that this is the wrong denominator. What
forces action now is the measured consequence, on a file nobody edited.

`AST08`'s `SKILL.md` is byte-identical between run 3 and run 4 — last touched in commit
`2cd49f1`, before run 3 was scored (`git diff --name-only 3e5919b bb593c8 -- skills/AST08/`
returns nothing). Every one of its eight dimension means clears its floor in **both** runs:

| Run | n | mean | sigma | `mean - sigma` | floors | locked verdict |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| 3 | 15 | 110.3 | 5.65 | **104.6** | all clear | **BLOCKED** |
| 4 | 18 | 110.8 | 4.67 | **106.1** | all clear | **SHIP** |

The verdict changed on an unchanged artifact, because the other judges happened to agree more
that day. **A gate that is not a function of the artifact is not a gate.** That, and not the
convenience of any particular skill, is what licenses the change.

Under a bound with `sqrt(n)` in the denominator `AST08` is SHIP in both runs. The same check run
across every skill whose `SKILL.md` was unedited between the two runs is in "Verdict stability"
below.

### Why the naive fix is worse than no fix

Swapping `stdev` for `stdev/sqrt(n)` while keeping the `105` threshold produces a **dead clause**.
At this panel's typical n (16) and sigma (4.7) the standard error is about **1.17**, so
`mean - 1.17 >= 105` is `mean >= 106.2` — already implied by the `mean >= 108` clause standing
beside it. It could never bind on any input the gate will ever see. A gate that keeps a clause
which cannot bind is decoration, and decoration in a gate is worse than an honest deletion,
because a reader takes it for a constraint.

So the reference level has to move with the denominator. The two are one decision, not two.

### What the second clause is FOR

- Clause 1, `mean >= 108`, asks: **is the point estimate Grade A?**
- Clause 2 must ask something clause 1 cannot. The only coherent second question is:
  **are we confident the TRUE mean is Grade A** — is the lower end of a confidence interval on
  the mean still at or above the grade boundary?

That fixes the reference level at the grade boundary the rule already names, **108**, not 105:

```
mean - CONFIDENCE_K * stdev / sqrt(n)  >=  POOLED_TARGET
```

`105` is not a boundary of anything in this rubric; it was a slack allowance under a spread
statistic and it has no meaning under a standard error. `107` or any other intermediate value
would be semi-dead — binding only when the standard error happens to exceed the gap — and
unprincipled. The grade boundary is the only defensible reference for a clause whose whole
question is "is the true mean Grade A".

### The panel's sampling structure, measured

Every figure below is computed from `eval/scorecards/*.json` (run 4: eleven skills, six judges,
2.73 rounds per judge on average).

| quantity | value |
| --- | --- |
| n per skill | 14 to 18; median **17**, mean 16.4 |
| per-skill sigma | 3.74 to 6.04; median **4.67**, mean 4.72 |
| within-judge variance component | 8.253 (sd 2.87), df 114 |
| between-judge variance component | 16.457 (sd 4.06), df 55 |
| total | 24.71 (sd 4.97) |
| intraclass correlation (ICC) | **0.666** |
| design effect, `1 + (m - 1) * ICC` | **2.15** (`sqrt` = 1.466) |
| effective sample size at n = 17 | **7.9** |

The last two rows matter and are stated up front because they are the strongest argument
*against* the rule this record adopts. The seventeen judgments behind a pooled mean are not
seventeen independent reads. They are six judges read roughly three times each, and the judges
carry large fixed offsets (`+6.7` to `-4.9`, ADR-0005) while barely moving between their own
rounds. The effective sample size is therefore close to the number of **judges**, not the number
of **judgments**, and `stdev/sqrt(n)` understates the true uncertainty of the mean by a factor of
about **1.47**.

## Decision

### The rule

```python
POOLED_TARGET = 108   # unchanged: the Grade-A boundary
CONFIDENCE_K  = 1.0   # NEW: standard errors of margin required on that same boundary
MIN_ROUNDS    = 4     # unchanged
FLOORS        = ...   # unchanged, as vendored
```

```python
sem      = round(stdev / sqrt(n), 2)          # NEW published statistic
ci_lower = round(mean - CONFIDENCE_K * sem, 1) # NEW published statistic

SHIP  <=>  every dimension mean >= its floor
       AND mean     >= POOLED_TARGET          # point estimate is Grade A
       AND ci_lower >= POOLED_TARGET          # true mean is confidently Grade A
```

`POOLED_LOWER_BOUND = 105` is **retired as a gate constant.** The descriptive statistic
`lower_bound = mean - stdev` **stays** in `pooled_stats()` and in every published scorecard: it
is the evidence ADR-0005's argument rests on and deleting it would destroy the record. It simply
stops deciding anything. Net constant count is unchanged — one retired, one added.

The name `POOLED_LOWER_BOUND` also stays **in the file, at 105, read by nothing in the gate**,
carrying a comment that says so. Deleting the symbol would take `eval/calibration.py`'s
implied-mean-bar diagnostic with it, and that diagnostic is how ADR-0005's central figures
(108.7–111.0 at this panel's sigma) are regenerated rather than transcribed. A record whose
arithmetic can no longer be re-derived is folklore. `tests/test_calibration.py` holds the retired
value against ADR-0005 and the live constants against this record, so the two cannot be confused.

`sem` is computed from the **rounded** `stdev` and `ci_lower` from the **rounded** `mean` and
`sem`, matching the existing convention that made `lower_bound` recomputable by hand from the
published figures. A reader with only `n`, `mean` and `stdev` in front of them must be able to
reproduce the verdict exactly; that property is worth more than a third decimal place.

### Why k = 1.0, derived rather than chosen

Four candidate values were priced before any verdict was computed. The effective mean bar is
`108 + k * sigma/sqrt(n)`.

| k | bar @ median (σ 4.67, n 17) | bar @ worst σ (6.04, n 17) | bar @ `MIN_ROUNDS` (σ 4.67, n 4) | nominal 1-sided, iid | actual, at deff 2.15 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| **1.0** | **109.13** | **109.46** | **110.34** | 84% | ~75% |
| 1.466 | 109.65 | 110.15 | 111.42 | 93% | 84% |
| 1.645 | 109.86 | 110.41 | 111.84 | 95% | ~87% |
| 2.0 | 110.26 | 110.93 | 112.68 | 97.7% | ~91% |

**1. No confidence label the rule cannot deliver.** Given ICC 0.666, a `k` chosen as a nominal
95% quantile delivers roughly 87% in fact. The label is the part a reader quotes, and a wrong
label is worse than none. `k = 1.0` is therefore adopted as **one standard error of margin** and
is deliberately **not** sold as a confidence level. Its operating characteristic is published in
points, not percent: at this panel it moves the effective bar from 108.0 to about **109.1**.

**2. No t-quantile.** At `df = n - 1 = 16`, `t(0.95) = 1.746` against `z = 1.645` — a 6%
correction. The *uncorrected* clustering error runs 47% in the same direction, and the honest df
under clustering is nearer `J - 1 = 5` than 16. Applying a t-correction on top of a larger
uncorrected bias would be precision theatre. Since no quantile is being claimed at all, the
question is moot by construction — and it is recorded here so that nobody has to re-derive why
it was skipped.

**3. The design-effect correction is stated, not absorbed.** `k = sqrt(deff) = 1.466` is a real
candidate with a real derivation: it would make the clause exactly one *true* standard error and
would let the 84% label be honest. It is rejected for three reasons. It fails the verdict-stability
test below with a 0.2-point margin, which by this repository's own doctrine
(ADR-0005: *"a threshold cleared by 0.38 is not a threshold cleared"*) is not clearance. It is
estimated from **this** panel's ICC and cluster size, so freezing it as a literal re-imports the
exact disease ADR-0005 diagnosed — a bar that floats on panel composition — only worse, because
it would float invisibly inside a constant instead of visibly inside a sigma. And the correct fix
for clustering is not a bigger `k` at all: it is a **cluster-aware denominator**, which needs
judge identity inside `aggregate.judgments` and is a larger change than the one authorised here.
See "Known gap" below.

**4. Verdict stability, the criterion the change exists to serve.** Declared before it was
computed: *a skill whose `SKILL.md` is byte-identical across two runs must receive the same
verdict.* Three skills qualify between run 3 and run 4 — `AST01`, `AST08` and `advisory` (the
eight others gained anti-pattern sections; `AST01` was edited only afterwards, in `bb593c8`).

| control | run | n | mean | σ | `mean-σ` (locked) | `sem` | `ci_lower` (k=1) | floors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `AST08` | 3 | 15 | 110.3 | 5.65 | 104.6 → **BLOCKED** | 1.46 | **108.8** → SHIP | all clear |
| `AST08` | 4 | 18 | 110.8 | 4.67 | 106.1 → **SHIP** | 1.10 | **109.7** → SHIP | all clear |
| `advisory` | 3 | 17 | 112.3 | 3.44 | 108.9 → SHIP | 0.83 | 111.5 → SHIP | all clear |
| `advisory` | 4 | 16 | 112.2 | 4.82 | 107.4 → SHIP | 1.21 | 111.0 → SHIP | all clear |
| `AST01` | 3 | 17 | 109.8 | 5.37 | 104.4 → BLOCKED | 1.30 | 108.5 → clears | all clear |
| `AST01` | 4 | 17 | 108.5 | 6.04 | 102.5 → BLOCKED | 1.46 | 107.0 → fails | **D3 12.2** |

- `AST08` is the clean case and it sets a hard cap. Its run-3 clause-2 value crosses 108 at
  `k = 1.577`; above that the new rule reproduces the very flip it exists to remove. Requiring
  the run-3 value to clear 108 by at least **0.5** — the distance the mean itself moved on this
  byte-identical file — caps `k` at **1.234**. `k = 1.0` clears by 0.84 (run 3) and 1.70 (run 4).
- `advisory` is stable under every candidate and carries no signal.
- **`AST01` is unstable and no choice of `k` repairs it.** Its `D3` dimension mean fell 13.1 to
  12.2 on an unedited file and dropped through the floor. The overall verdict therefore flips at
  run 4 for any `k` that lets clause 2 pass in run 3. At `k = 1.466` `AST01` happens to be
  BLOCKED in both runs — but by 0.1 points on the clause in run 3, which is co-blocking by luck,
  not stability, and it would mean tuning the pooled bound to mask noise located in a dimension
  floor. That is the wrong clause doing the wrong job, and it is refused. Under `k = 1.0` the
  instability stays visible, which is the correct outcome: **the margin problem belongs in its
  own record** (ADR-0005 already says so) and hiding it inside this constant would prevent that
  record from ever being written.

`k = 1.0` is the value that a plain reading of "one standard error" gives, that needs no estimate
of the panel's ICC to justify, that keeps the clause live (109.1, not 106.2), and that satisfies
the stability criterion with room to spare rather than by a rounding accident.

### MIN_ROUNDS stays 4

`MIN_ROUNDS` is **not** changed, and the reason is a property of the new rule rather than an
absence of thought.

The standard error shrinks with n, so the bar falls as evidence accumulates:

| n | 4 | 8 | 12 | 17 | 24 | 36 | 100 | → ∞ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bar at σ 4.67 | 110.34 | 109.65 | 109.35 | 109.13 | 108.95 | 108.78 | 108.47 | **108.00** |

**This is a feature, and it is bounded.** More evidence should earn more confidence — that is the
entire content of a confidence bound. What makes it safe is the limit: the bar is monotone
decreasing in n and **strictly bounded below by `POOLED_TARGET`**. Volume can therefore buy at
most the gap between today's bar and 108 — **1.13 points** at n 17 — and it can *never* buy a
pass for a skill whose true mean is below Grade A, because clause 1 is a hard wall at 108 that no
amount of sampling moves. Under the locked rule, by contrast, volume bought nothing at all; but
neither did evidence, which is precisely the defect.

Two further protections already hold and are unaffected: every judgment must be pooled and none
may be discarded (`_is_invalidated` requires an auditable reason), so added rounds move the mean
in both directions and cannot be aimed; and the run-4 corpus shows within-judge round-to-round
movement of ≤1.5 points on roster means, so adding rounds of the same judges barely moves the
mean at all. Buying a pass with volume costs a great deal of electricity for at most one point,
on a skill that is already Grade A.

Note also that the new rule is **harsher** than the old one at small n — 110.34 at `MIN_ROUNDS`
against a locked implied bar of 108.7-111.0 — so it removes rather than adds the pressure to
raise `MIN_ROUNDS`. It is left at 4.

### Known gap, flagged and not fixed here

`MIN_ROUNDS = 4` counts **judgments**, not **judges**. Four judgments from a single judge would
satisfy it, and that judge's fixed offset (up to ±6.7 points on this panel) would pass straight
into the pooled mean while its narrow within-judge sigma (2.87) produced a flatteringly small
standard error. The new rule does not create this hole and does not close it. The right fix is a
`MIN_JUDGES` constant, or better, a denominator built on the number of judges rather than the
number of judgments — both of which require `aggregate.judgments` to carry provider identity,
which it does not today. **This is named as future work and is deliberately not bundled into the
one authorised change.** In practice every run so far has used all six judges on every skill.

## Consequence check — computed AFTER the constant was chosen

**This is a consequence check, not an input to the choice, and not a re-gating.** The constant
above was written down first (the pre-registration, the stability table, and the k-comparison
table all precede this section in the order they were produced). Run 4's verdicts stand as issued
under the locked rule. Run 5 is what will be judged under the new one. Nothing in this table is
published as a verdict anywhere: it exists so that the cost of the change is on the record
**before** the run that will pay it.

Applying the adopted rule to the run-4 corpus **as a hypothetical**:

| skill | n | mean | σ | `sem` | `ci_lower` | floors | locked | adopted |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| AST01 | 17 | 108.5 | 6.04 | 1.46 | 107.0 | **D3 12.2** | BLOCKED | BLOCKED |
| AST02 | 15 | 112.3 | 4.62 | 1.19 | 111.1 | clear | SHIP | SHIP |
| AST03 | 18 | 110.7 | 4.33 | 1.02 | 109.7 | clear | SHIP | SHIP |
| AST04 | 17 | 112.6 | 3.74 | 0.91 | 111.7 | clear | SHIP | SHIP |
| AST05 | 14 | 111.2 | 4.06 | 1.09 | 110.1 | clear | SHIP | SHIP |
| AST06 | 15 | 111.3 | 4.04 | 1.04 | 110.3 | clear | SHIP | SHIP |
| AST07 | 17 | 110.3 | 5.22 | 1.27 | 109.0 | clear | SHIP | SHIP |
| AST08 | 18 | 110.8 | 4.67 | 1.10 | 109.7 | clear | SHIP | SHIP |
| AST09 | 17 | 108.2 | 4.85 | 1.18 | **107.0** | clear | BLOCKED | BLOCKED |
| AST10 | 16 | 113.2 | 5.55 | 1.39 | 111.8 | clear | SHIP | SHIP |
| advisory | 16 | 112.2 | 4.82 | 1.21 | 111.0 | clear | SHIP | SHIP |

**Nine of eleven under the locked rule. Nine of eleven under the adopted rule. Zero verdicts
change.** Verified by running the implemented gate over the committed corpus: the verdict column
is identical, and the single textual difference anywhere is `AST09`'s BLOCKED *reason*, which
under the new clause reads `confidence bound on the mean (mean - 1.0 * stdev/sqrt(n)) 107.0 <
target 108 — mean 108.2 is Grade A but not confidently so (n 17, stdev 4.85, sem 1.18)`. That
reason is **not** written back into any published run-4 surface; the dashboard keeps the reason
the locked rule gave and says which rule gave it.

This corrects an expectation carried into this record, and the correction is the single most
important sentence in it. ADR-0005 states that under the standard error of the mean `AST09`
*"clears comfortably at 107.0"* and that fixing the bound *"would take the board from nine skills
to ten."* **Both statements are true only against the retired `105` threshold.** Measured against
the grade boundary the corrected clause is actually asking about, `AST09`'s `107.0 < 108`: it is a
skill whose point estimate is Grade A by 0.2 points on a sigma of 4.85, which is exactly the
situation a confidence bound exists to refuse. `AST09` would pass only at `k <= 0.17`, and
lowering `k` to 0.17 to admit it is the precise corruption the pre-registration exists to prevent.
**The constant is not being revised.** ADR-0005's two sentences must be corrected when this record
is accepted, along with the dashboard rows that repeat them.

So the honest summary of what this change buys, on the data in hand: **nothing.** Nine skills
shipped before and nine ship after; one skill moves from "blocked by a spread statistic" to
"blocked by a confidence bound", which is a change of reason and not of outcome; and the gate
stops being able to flip a verdict on a file nobody edited. A change that fixes a proven
determinism defect and alters no result is the only kind of gate change that carries no suspicion
whatsoever, and this is the moment to make it.

## Alternatives Considered

### A — Drop the second clause entirely; gate on `mean >= 108` plus the per-dimension floors

A real option, and the strongest challenger. It removes the flawed statistic outright, needs no
new constant, and — on run-4 data — ships exactly the same nine skills plus `AST09`, i.e. ten.

**Rejected, on the same grounds ADR-0005 rejected it and one new one.** A mean of 108.2 drawn
from judgments with sigma 4.85 is weaker evidence than a mean of 108.2 with sigma 3.7, and a gate
that cannot say so has thrown away information it is holding. The run-4 corpus spans sigma 3.74 to
6.04, a factor of 1.6, so the distinction is measured rather than hypothetical. The per-dimension
floors do not cover the gap: they are means too, and they carry the identical error one level
down — `AST01`'s `D3` moving 13.1 → 12.2 on an unedited file is that error, visible.

The new ground is that this option is *more* attractive today than when ADR-0005 refused it,
because the corrected clause blocks a skill that dropping it would ship. **That is an argument
for keeping the clause, not against it.** A gate whose second clause is retained only while it
costs nothing is not a gate either.

### B — Keep `mean - stdev/sqrt(n) >= 105` (the naive swap)

Rejected as **decoration**. At n 16 and sigma 4.7 it reads `mean >= 106.2`, strictly implied by
the `mean >= 108` beside it, and there is no plausible (n, sigma) at this panel where it binds.
It would look like a two-clause gate to every future reader while being a one-clause gate in fact.
Removing the clause honestly (Alternative A) is better than keeping a clause that cannot fire.

### C — `k = sqrt(deff) = 1.466`, the design-effect correction

The most principled challenger and the one this record came closest to adopting. Priced in full
under "Why k = 1.0" above; rejected on the stability margin (0.2 points on the `AST08` control),
on panel-dependence (it freezes an ICC estimated from six judges over three rounds), and because
the correct treatment of clustering is a denominator change, not a multiplier — which is named as
future work rather than approximated by a constant. **The under-conservatism this leaves is
quantified and on the record above rather than papered over: at `k = 1.0` the clause delivers
about 0.68 design-corrected standard errors.**

### D — `k = 1.645` or `k = 2.0`, a nominal 95% or 97.7% bound

Rejected on measurement. At `k = 1.645` the `AST08` control returns `110.3 - 2.40 = 107.9` in run 3
and `110.8 - 1.81 = 109.0` in run 4 — **the new rule would flip the verdict of a byte-identical
file, which is the defect it was written to remove.** `k = 2.0` flips it further. A statistical
pedigree that reintroduces the fault being fixed is not a pedigree. Separately, both would attach
a confidence label the clustered design does not deliver (see the table).

### E — Cluster-aware denominator now: `mean - stdev/sqrt(n_eff)`, `n_eff` = judges

Statistically the best answer available and the direction this repository should eventually go.
Rejected **for this record only, on scope**. `aggregate.judgments` stores bare totals; the gate
never sees which judge produced which number. Making the gate cluster-aware means changing the
scorecard schema, the harness that writes it, and the fixtures that test it — several changes,
where exactly one is authorised. It is recorded under "Known gap" so the next record inherits the
reasoning rather than rediscovering it.

### F — Bootstrap or percentile confidence interval instead of a normal-theory bound

Rejected. With n ≈ 17 clustered inside six judges, an honest bootstrap is a *cluster* bootstrap,
which needs the same judge identity Alternative E needs. And a closed form a reader can recompute
by hand from the three published numbers (`n`, `mean`, `stdev`) is worth more to this gate than a
decimal place of accuracy, for the same reason `pooled_stats` rounds once and publishes what it
rounds.

### G — Cap sigma directly, e.g. `stdev <= 5`

Rejected without hesitation: it is the locked rule's defect in undisguised form. It penalises
panel diversity, rewards a narrow panel of like-minded judges, and gets strictly harder every
time a judge with a novel calibration is added — the same perverse incentive ADR-0005 names.

### H — Wait for more evidence before changing anything

Rejected. ADR-0005 declined to act because the data was already in hand and no threshold chosen
after seeing it could be distinguished from a convenient one. That objection is answered here in
the only way it can be: the constant is fixed **before** the run it will judge. Waiting longer
does not make the choice cleaner; it only leaves a gate that can flip on an unedited file in place
for another run.

## Consequences

### Positive

- The gate becomes a function of the artifact. On the one controlled natural experiment available
  — three skills byte-identical across two judged runs — the locked rule flips `AST08` and the
  adopted rule does not.
- The second clause asks a question the first cannot, against the boundary the rule already names.
  Two clauses, two distinct diagnoses: *"the point estimate is not Grade A"* and *"the point
  estimate is Grade A but not confidently so."*
- Evidence now counts for something. Pooling seventeen judgments instead of four earns a
  measurably lower bar (109.13 against 110.34), bounded below by 108, which is the behaviour a
  reader expects of a rule that calls itself a lower bound.
- The change buys nothing on the data in hand. Nine skills shipped under the locked rule and nine
  ship under the adopted one, so the accusation of goalpost-moving has an arithmetic answer
  rather than a rhetorical one.
- One constant retired, one added. The retired threshold's underlying statistic stays published
  and checkable, so ADR-0005's argument remains verifiable against future corpora.

### Negative

- **`scripts/ship_floor.py` is no longer byte-identical to the vendored upstream formula, and the
  two repositories now diverge.** `plan.md` names this exactly: *"If this formula is updated
  upstream, the two repos diverge and Step 05 measures an agreed-to metric in only one of them."*
  The divergence is now real, in this direction, by decision. `THIRD_PARTY_LICENSES.md`, `NOTICE`
  and the file's own docstring must record it, and any score quoted across the two repositories
  must name which rule produced it.
- **Every document and test asserting "the gate has never changed" is now false and has been
  rewritten to the true, weaker claim** — changed exactly once, by recorded decision, after the
  defect was demonstrated and before a fresh run, with a pointer to this record. Rewritten, not
  deleted: the integrity property being claimed is now a different one and it still has to be
  checkable. `tests/test_calibration.py` pins the live constants *and* asserts that this ADR
  documents each of them, so a constant and its justification cannot drift apart.
- **The published run-4 board can no longer be regenerated by the tool that wrote it.**
  `eval/generate_dashboard.py` calls the gate, and the gate is now a rule run 4 was not judged
  under, so regenerating would rewrite `AST09`'s stated reason into a clause that never saw it.
  The Results table is therefore **frozen** until run 5 replaces it, with a banner naming the rule
  that produced it. `tests/test_generate_dashboard.py` no longer asks whether the committed table
  is what today's generator would emit; it asserts the freeze is honest — every verdict in the
  table is still what the current gate computes, and the one row whose reason belongs to the
  retired clause is the one the ADR predicted. An unexplained regeneration fails that test.
- **The clause remains under-conservative by a measured factor.** At ICC 0.666 the naive
  `stdev/sqrt(n)` understates the standard error of the mean by about 1.47×, so `k = 1.0` delivers
  roughly 0.68 design-corrected standard errors. This is a known, quantified shortfall, chosen in
  preference to an estimated correction frozen into a constant, and it is the first thing a future
  record should revisit.
- **`MIN_ROUNDS` counts judgments, not judges**, so a four-judgment single-judge pool would satisfy
  the gate with that judge's full bias in the mean and a flatteringly narrow standard error. Not
  created by this change, not closed by it, flagged above.
- Run 4 becomes a historical measurement under a superseded rule. Its numbers cannot be differenced
  against run 5's verdicts without saying which rule issued each.
- Two of ADR-0005's sentences are now wrong and must be corrected: `AST09` does **not** clear
  "comfortably at 107.0" against the boundary this clause actually uses, and fixing the bound does
  **not** take the board from nine to ten. Both were written against the `105` threshold this
  record retires.

### Neutral

- `eval/calibration.py` already prints `mean - sigma/sqrt(n)` as a diagnostic column
  (`sem_bound`). It gates nothing and continues to gate nothing. Its `panel_summary()` **keeps**
  `POOLED_LOWER_BOUND` — the implied-mean-bar figures ADR-0005 quotes are arithmetic on the
  retired clause and must stay regenerable — and **gains** `CONFIDENCE_K`, so the report states
  the bar now in force beside the one the diagnosis was written against. `sem_bound` is rounded
  the way `pooled_stats()` rounds `ci_lower` (sem to two places first), so the diagnostic column
  and the gate cannot print numbers 0.1 apart. That alignment moves exactly one figure in the
  committed `eval/judge-quality.json` — `AST05`'s `sem_bound` in the *excluding-the-flagged-judge*
  diagnostic column, 109.3 → 109.2. It is a diagnostic, it gates nothing, no verdict or scorecard
  is touched, and the file is regenerated and re-derived by `tests/test_judge_quality.py`.
- The per-dimension floors are untouched. They are applied to dimension means and never divided by
  a sigma, so neither the old error nor the new correction reaches them — which is why `AST01`'s
  block is still a finding about `AST01`.
- The `3.3`-sigma calibration comment in `ship_floor.py` stays as vendored. It records the
  instrument the *original* rule was tuned against and rewriting it would destroy the evidence
  that the panels differ.
- **Adding `sem` and `ci_lower` to `pooled_stats()` would, taken naively, make every stored run-4
  aggregate fail the stats drift check**, since blocks written before this record cannot carry
  keys this record invents. That was the draft's expectation and it is wrong to leave standing,
  because its consequence is not "run 5 regenerates the corpus" — it is that until run 5 exists,
  every run-4 verdict renders as `BLOCKED — stored stats disagree with recompute`, which
  re-labels nine published SHIPs on a schema technicality. The Status section forbids exactly
  that. **Implemented instead:** `PRE_ADR0006_STATS` names the eight statistics a recorded
  aggregate must carry, absence of any one of them is refused, a stored value that *disagrees*
  with the recompute is refused whatever its key, and only the two keys this record adds are
  permitted to be absent — which dates a scorecard rather than excusing it. The refusal property
  the gate is built on ("a stored mean is a claim, not evidence") is unweakened: nothing that was
  checked before is unchecked now. Fixture scorecards in the test suite carry both new keys so
  the strict path is exercised, and `tests/scripts/test_ship_floor.py` pins both halves — a
  *present but wrong* `sem` or `ci_lower` must still BLOCK.

## References

- [`0005-judge-panel-calibration-and-the-lower-bound.md`](0005-judge-panel-calibration-and-the-lower-bound.md)
  — the diagnosis this record acts on, and the item-4 requirement it satisfies. Adopted in full;
  two of its numeric claims are corrected under Consequences.
- `scripts/ship_floor.py` — the rule to be changed, and the vendoring note that makes the
  divergence a recorded consequence rather than a surprise.
- `eval/calibration.py` — regenerates the panel figures above; already prints both candidate
  bounds side by side as diagnostics.
- `eval/scorecards/` (run 4) and `eval/scorecards-run3/` (run 3) — the two corpora scored under
  the same prompt, and therefore the only pair from which the byte-identical-control comparison
  can legitimately be made.
- `tests/test_calibration.py` — pins the gate constants and this repository's ADR figures; it is
  the test that must be updated to name this record rather than assert the constants never moved.
- `docs/adr/0004-per-scenario-detectability-contract.md` — the companion decision on not letting a
  measurement's convenience choose its scope.
