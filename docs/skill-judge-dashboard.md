# Skill-Judge Scorecard Dashboard

Pooled eight-dimension judge results for the eleven skills in this repository, scored
against the pinned skill-judge rubric and gated by the ship rule in
`scripts/ship_floor.py`.

This repository is an independent community implementation. It is **not** an official
OWASP project and carries no OWASP endorsement — see [`../README.md`](../README.md) and
[`../NOTICE`](../NOTICE).

> ## Judged run recorded — run 4, 2026-08-24
>
> **Nine of eleven skills clear the ship rule, and no gate constant moved to get there.**
> 11 skills x 3 rounds x 6 providers were attempted; **180 judgments bind** and 18 were
> refused as malformed by the justification contract, so `n` varies by judge (26 to 32)
> instead of sitting at a flat 33. Runs 1, 2 and 3 are retained under
> `eval/scorecards-run1/`, `eval/scorecards-run2/` and `eval/scorecards-run3/`.
>
> **Run 4 *is* comparable to run 3, and that is the point of it.** The judge prompt, the
> rubric pin, the panel roster and every gate constant were held fixed across the two runs;
> the only thing that changed was eight `SKILL.md` files. That makes this the first
> skill-by-skill comparison the repository can legitimately make — see
> [The controlled result](#the-controlled-result-what-changed-between-run-3-and-run-4)
> below, which is worth more than the ship count above it. Runs 1 and 2 remain off-limits
> for differencing: the prompt was rebuilt between run 2 and run 3 (callout below), so those
> two are a different instrument reading the same files.
>
> **Two skills do not ship, for two different reasons.** `AST01` is BLOCKED on a dimension
> floor — `D3` Anti-Pattern Quality 12.2 against a floor of 13 — and it is the only skill on
> the board blocked by a floor. `AST09` is BLOCKED by the lower bound alone: a Grade-A mean
> of 108.2, all eight dimension means above their floors, and `108.2 - 4.85 = 103.4 < 105`.
> That clause is [ADR-0005](adr/0005-judge-panel-calibration-and-the-lower-bound.md)'s
> subject, and `AST09` is now the single clean instance of the defect it describes: one
> skill, one reason, and the reason is not about the skill. The defect is recorded and
> deliberately **not** fixed here — a bar changed after seeing the run it is applied to is
> not a bar.
>
> **`bedrock/qwen3-235b` is flagged NON-DISCRIMINATING again, and it is still pooled.** It
> ranked the roster in run 3 and was recorded as COARSE. In run 4 it still ranks, but the
> skills moved up into its ceiling while its ceiling did not, so its across-skill sigma fell
> from 1.38 to 0.94 and crossed the 1.0 floor. Full signals and the size of the effect are
> in [Judge quality](#judge-quality-is-each-judge-measuring-or-ranking-nothing-diagnostics-only).
>
> Regenerate after a run with:
>
> ```bash
> python3 eval/run_judge_matrix.py --rounds 3   # writes eval/scorecards/*.json
> python3 eval/generate_dashboard.py            # rewrites the table below
> python3 eval/calibration.py                   # per-judge bias + judge-quality diagnostics;
>                                              # also writes eval/judge-quality.json
> ```

> ## Instrument change — the judge prompt was rebuilt on 2026-08-23
>
> **Runs 3 and 4 were scored under the rebuilt prompt. Runs 1 and 2 are not comparable to
> either, and neither is anything measured before 2026-08-23.** The break is recorded here
> rather than corrected in place, because the archived runs are the audit trail of what the
> old instrument produced and deleting them would destroy the evidence that the two differ.
>
> What changed, in `scripts/judge_harness.py`:
>
> 1. **The judge now receives the rubric.** The old prompt sent the eight dimension *names* and
>    their maxima — "D1 Knowledge Delta 20, D2 Mindset + Appropriate Procedures 15, …" — and no
>    scoring bands at all. The band tables live in the pinned rubric and were never transmitted,
>    so six judges each scored against a private scale invented from a label. The prompt is now
>    built by reading the pinned rubric off disk and quoting every dimension's own band table,
>    red flags and worked examples verbatim; it refuses to build at all if those bytes do not
>    hash to the pinned `RUBRIC_CONTENT_SHA256`.
> 2. **The judge must justify every score.** The old prompt ended "and nothing else", and
>    measurably **0% of run 2's 198 judgments contain any prose**. The response contract is
>    now `{"D1": {"score": <int>, "why": "<one sentence citing something specific in the skill>"},
>    …}`. A judgement whose `why` is missing, empty, or repeated across dimensions is recorded as
>    **malformed** and excluded from the pool with an audit-trail entry — the same treatment a
>    provider that crashed already gets. A judge that will not explain itself does not bind a score.
>    In run 4 that rejected 18 of 198 attempted judgments.
> 3. **The artifact is fenced as data.** The skill was previously delimited by a bare `---`, which
>    is exactly what every scored skill's own YAML frontmatter opens with. It now sits between
>    markers Markdown cannot produce, declared in words to be the thing under evaluation rather
>    than a source of instructions.
>
> **What the rebuild did to the panel, measured.** A pooled mean is a statement about *the rubric
> as read by these judges* (ADR-0005, "Cross-repo implication"), and the read changed between
> run 2 and run 3 — which is why run 3 was a new baseline rather than the third point on a trend.
> The judges themselves are comparable across the break, and they moved: four of six came inside
> 1.2 points of the pooled mean against two of six in run 2, the largest within-judge
> round-to-round spread fell from 4.0 points to 2.3, median per-skill sigma fell from 6.43 to
> 5.65, and `bedrock/qwen3-235b` — which returned exactly 120.0 on all eleven skills from three
> distinct values under the old prompt — began to vary and to rank. See
> [ADR-0005](adr/0005-judge-panel-calibration-and-the-lower-bound.md), "What the two instrument
> changes did to the panel".
>
> **No gate constant moved.** `FLOORS`, `POOLED_TARGET` (108), `POOLED_LOWER_BOUND` (105),
> `MIN_ROUNDS` and the rubric pin are exactly as vendored. Rebuilding the instrument is not
> permission to move the bar, and neither is a run that would have shipped more skills without
> it. ADR-0005's claim that the bar was never retuned still holds across all four runs.
> Held by `tests/scripts/test_judge_harness.py` and `tests/test_calibration.py`.

---

## The controlled result: what changed between run 3 and run 4

This is the most useful thing on the page, and it is not the ship count.

Between run 3 (`eval/scorecards-run3/`) and run 4 (`eval/scorecards/`) the judge prompt, the
pinned rubric, the panel roster, the round count and every gate constant were held fixed.
**Exactly one thing changed: eight skills — `AST02`-`AST07`, `AST09`, `AST10` — gained an
explicit anti-pattern `NEVER` section**, seven or eight prohibitions apiece, each grounded in
something a reader can open (a check id in that module's `CHECK_COVERAGE`, a scenario id and
tier in `scenarios/registry.yaml`, a coverage-matrix debt item, or a cited file line).

`AST01`, `AST08` and `advisory` were **deliberately left untouched**, because all three had
already cleared the `D3` floor in run 3. They are the untreated controls, and they are what
turns this from an anecdote into a result.

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

**Every treated skill improved. No control did.** All eight treated skills rose on `D3`, by
+1.2 to +2.8 points, and all eight crossed the floor of 13 they had been under. All eight rose
on the pooled mean. Seven went BLOCKED → SHIP outright; the eighth, `AST09`, cleared every
dimension floor and is held only by the lower bound. All three controls moved *down* on `D3` —
−0.1, −0.3 and −0.9 — which is what a null treatment looks like against run-to-run movement.

**A `D3` margin of 0.1 was treated as clearance, and it should not have been.** `AST01` was
excluded from the anti-pattern pass because it measured `D3` 13.1 against a floor of 13. It
measures 12.2 now and is the only skill on the board blocked by a floor. `AST08` was excluded
on a margin of 0.5 and has fallen to 13.2 — a margin of 0.2 — which is the same finding one
run behind. Judge scores are a distribution, not a reading: a margin narrower than the
distribution's own run-to-run movement is noise wearing a verdict's clothes, and treating it as
clearance is how the untreated control became the only floor failure on the board.

Two things this table does **not** say. `AST08`'s BLOCKED → SHIP is **not** an improvement: its
`SKILL.md` is byte-identical across the two runs and its `D3` fell. It shipped because the
panel's sigma narrowed and lifted its `mean − sigma` from 104.6 to 106.1 — the lower-bound
defect [ADR-0005](adr/0005-judge-panel-calibration-and-the-lower-bound.md) describes, visible in
the flattering direction for once. And a controlled result over eleven artifacts with one
treatment arm is evidence, not proof: the pooled mean rose across the board, so some of every
skill's movement is panel-level and only the treated-versus-control *contrast* is attributable.
The contrast is the finding. `D3` anti-patterns are load-bearing rather than decorative, and
this repository now has its own measurement saying so.

---

## Judge calibration (measured, diagnostics only)

Regenerate with `python3 eval/calibration.py`. Panel: 6 providers x 11 skills = 180 binding judgments, pooled mean of **111.0**.

| Judge | n | mean | bias | round means |
| --- | ---: | ---: | ---: | --- |
| `bedrock/qwen3-235b` | 32 | 117.7 | +6.7 | 118.2 / 117.1 / 117.9 |
| `anthropic-compatible/glm-5.2` | 29 | 112.1 | +1.2 | 112.3 / 112.4 / 111.6 |
| `claude-cli/sonnet` | 32 | 110.4 | -0.5 | 110.6 / 110.7 / 109.9 |
| `bedrock/nova-pro` | 29 | 110.0 | -1.0 | 110.3 / 110.4 / 108.9 |
| `bedrock/deepseek-v3.2` | 26 | 109.2 | -1.8 | 109.3 / 109.6 / 108.5 |
| `bedrock/gpt-oss-120b` | 32 | 106.1 | -4.9 | 106.1 / 106 / 106.3 |

An **11.6-point spread** separates the most generous judge from the harshest, while no judge's own
round-to-round means differ by more than **1.5 points** — so this is systematic calibration bias,
not measurement noise. The panel has kept closing up: the spread was 16.5 in run 2 and 15.4 in
run 3, four of the six judges now sit within 1.8 points of the pooled mean, and what remains is
carried by the two ends, `bedrock/qwen3-235b` at +6.7 and `bedrock/gpt-oss-120b` at -4.9.
Per-skill sigma runs **3.74 to 6.04** (median 4.67) against the 3.3 `ship_floor.py` was calibrated on, which makes `mean - sigma >= 105` demand a mean of **108.7 to 111.0** (90.6% to 92.5% of 120) rather than the 108 (90.0%) it names.
These figures are diagnostics: no gate constant is read from them and none was changed. See
[ADR-0005](adr/0005-judge-panel-calibration-and-the-lower-bound.md).

## Judge quality: is each judge measuring, or ranking nothing? (diagnostics only)

Regenerate with `python3 eval/calibration.py`, which also writes the machine-readable
`eval/judge-quality.json`. Every figure below is derived from `eval/scorecards/*.json` and
re-derived at test time by `tests/test_judge_quality.py`.

The calibration table above asks whether a judge's number is in the *right place*. These four
signals ask the prior question — whether the number is a **measurement** at all.

| Judge | n | distinct values | across-skill σ | across-skill variance | multiples of 5 | at dimension max | full 120 | own-round spread | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `bedrock/qwen3-235b` | 32 | 7 | 0.94 | 0.88 | 77% | 77% | 16% | 2.36 | NON-DISCRIMINATING |
| `anthropic-compatible/glm-5.2` | 29 | 8 | 1.23 | 1.51 | 24% | 24% | 0% | 2.36 | DISCRIMINATING |
| `bedrock/deepseek-v3.2` | 26 | 13 | 3.11 | 9.68 | 29% | 28% | 4% | 4.82 | DISCRIMINATING |
| `bedrock/gpt-oss-120b` | 32 | 12 | 2.19 | 4.80 | 10% | 10% | 0% | 4.64 | DISCRIMINATING |
| `bedrock/nova-pro` | 29 | 10 | 3.70 | 13.68 | 26% | 26% | 14% | 6.64 | DISCRIMINATING |
| `claude-cli/sonnet` | 32 | 10 | 1.17 | 1.37 | 20% | 20% | 0% | 3.91 | DISCRIMINATING |

*distinct values* — how many different numbers the judge used across all of its dimension scores
(eight per judgment). *across-skill σ / variance* — the spread of its own per-skill mean totals;
near zero means it placed every skill in the same spot. *multiples of 5* — the share of its
dimension scores divisible by five. *at dimension max* / *full 120* — how often it returned the top
of a dimension, and the top of the rubric. *own-round spread* — the mean gap between its own rounds
on one skill, which is what separates a judge that is *noisy* from one that is *constant*.

**`bedrock/qwen3-235b` is flagged NON-DISCRIMINATING on this panel, and the reason is not a
relapse.** Its history across the four runs is the clearest thing this table has ever shown:

| Run | Prompt | distinct values | per-skill means | across-skill σ | Verdict |
| --- | --- | ---: | --- | ---: | --- |
| 2 | dimension names only | 3 | 120.0 on all eleven | 0.00 | NON-DISCRIMINATING |
| 3 | rubric bands quoted | 9 | 114.7 – 119.7 | 1.38 | COARSE |
| 4 | rubric bands quoted | 7 | 116.3 – 119.3 | 0.94 | NON-DISCRIMINATING |

Under the old prompt it returned the rubric total eleven times out of eleven, drawn from three
distinct values — 10, 15 and 20, precisely the three dimension maxima — and ranked nothing at all.
It has ranked ever since. What moved between run 3 and run 4 is not the judge: its floor rose from
114.7 to 116.3 while its ceiling stayed put at roughly 119, because the *skills* improved into the
top of the scale it is willing to use. 77% of its dimension scores sit at a dimension's maximum,
so it has very little room above the roster and its per-skill means compressed into a 3.0-point
band. The `< 1.0` across-skill floor then fires. That is a true statement about what this judge can
resolve on this population — a judge that saturates cannot rank a roster once the roster reaches
its ceiling — and it is why the flag is reported rather than explained away. It also repeats the
lesson `AST01` teaches above: 1.38 against a floor of 1.0 was a margin of 0.38, and a margin that
narrow is not clearance.

The thresholds are anchored to the rubric or to chance, never to this panel — a bar chosen after
seeing which judge it catches is a name for that judge, not a bar:

| Signal | Flag when | Why that number |
| --- | --- | --- |
| Distinct dimension values | < 4 | Every dimension in the pinned rubric defines exactly four score bands (D1: 0–5 / 6–10 / 11–15 / 16–20). A judge with fewer distinct values than one dimension has bands cannot express that dimension's scale even once. |
| Across-skill σ | < 1.0 points | Deliberately extreme: not "agrees too much" but "returned one number". This panel places its skills 108.2 to 113.2 apart and the grade bands are twelve points wide, so a judge whose per-skill means fit in a one-point window has resolved that span to a single verdict. On run 2 the flat judge measured 0.00; on run 3 the lowest was 1.38; on run 4 it is 0.94. |
| Multiples of 5 | ≥ 60% | A judge drawing uniformly at random would hit a multiple of five about **25%** of the time (5 of 21 values on D1, 4 of 16 on the six 15-point dimensions, 3 of 11 on D7). 60% is ~2.4× chance and unreachable by luck. Advisory only — it yields `COARSE`. |
| At dimension max / full 120 | ≥ 50% | The rubric's top bands are reserved language ("pure knowledge delta — every paragraph earns its tokens"). A judge awarding them to the majority of what it sees has merged the top band with everything under it. Advisory only — it yields `COARSE`. |

Only the first two decide `NON-DISCRIMINATING`, because that is what the verdict means: a judge that
returns one number ranks nothing, whatever its granularity. Granularity and saturation explain the
*mechanism* and are reported beside it. A judge can be coarse without being flat — a much milder
problem, and one the rule must not conflate with this one. `bedrock/qwen3-235b` is the worked
example of the distinction in every direction available: flat on run 2, merely coarse on run 3, and
flat-by-compression on run 4 without ever going back to returning one number.

### What excluding a flagged judge would do — shown, not applied

`bedrock/qwen3-235b` was **not excluded** from anything. Every number everywhere else on this page,
in `eval/scorecards/*.json`, and in
[ADR-0005](adr/0005-judge-panel-calibration-and-the-lower-bound.md) is the *with* column below.
Both columns are published so a reader sees the size of the effect instead of being handed a
pre-filtered number.

| Figure | With `bedrock/qwen3-235b` | Without | Δ |
| --- | ---: | ---: | ---: |
| Judgments pooled | 180 | 148 | −32 |
| Pooled mean | 111.0 | 109.5 | −1.50 |
| Between-judge spread | 11.6 | 6.0 | −5.60 |
| Per-skill σ, median | 4.67 | 3.30 | −1.37 |
| Per-skill σ, range | 3.74–6.04 | 3.19–5.70 | — |

`eval/calibration.py` prints this table and refuses to apply it. Deciding whether a flagged judge
stops binding is a **human decision** and needs its own superseding record, written before the run
it applies to. Run 3 is the standing case for having kept this judge: it is the judge the prompt
fix repaired, and a panel that had dropped it in run 2 would never have measured that. The same
verdicts, thresholds and deltas are in `eval/judge-quality.json` for anything that needs to read
them mechanically.

### Runs 1 and 2 were scored without the rubric's bands

Run 1 (`eval/scorecards-run1/`) and run 2 (`eval/scorecards-run2/`) were judged by the
pre-2026-08-23 prompt, which sent the eight dimension names and their maxima and **none of the
rubric bands**, and forbade prose. Their absolute values are **weaker evidence** than the figures
on this page: every mean and every grade in those two archives rests on six private scales
invented from eight labels, which is also the most likely explanation for a judge that could return
the maximum eleven times without contradiction. What survives from them is the *relative* picture —
the bias ordering, the between-judge spread, and their judge-quality verdicts, which turn on the
shape of a judge's output rather than on where the rubric would have put it. They are kept unedited
as the evidence for that defect. Run 3 (`eval/scorecards-run3/`) is frozen for a different reason:
it was scored by the same prompt as run 4, so it is the *comparable* archive and the other half of
the controlled result above. This page's tables are run 4 throughout.

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

A skill ships when **all** of the following hold (`ship_floor.aggregate_verdict`):

| Condition | Constant | Value |
| --- | --- | --- |
| Pooled mean over all recorded judgments | `POOLED_TARGET` | ≥ **108** |
| Pooled mean minus one sample standard deviation | `POOLED_LOWER_BOUND` | ≥ **105** |
| Every dimension mean at or above its floor | `FLOORS` | D1 ≥ 17, D2 ≥ 13, D3 ≥ 13, D4 ≥ 13, D5 ≥ 13, D6 ≥ 13, D7 ≥ 8, D8 ≥ 13 |
| Pooled judgment count | `MIN_ROUNDS` | ≥ **4** |
| Aggregation method | `AGG_METHOD` | `multi-round-independent-pooled` |
| Rubric version | `RUBRIC_SHA` | `3027f20f3181758385a1bb8c022d4041dfb4de84` |

The mean-minus-sigma clause is the one that does the work: a mean of 108 sitting on a
sigma of 4 is *within noise of failing badly*, and this rule refuses it. It is also the
clause [ADR-0005](adr/0005-judge-panel-calibration-and-the-lower-bound.md) shows to be
measuring judge disagreement rather than skill quality — recorded, and left in force. Nine
of eleven skills clear this rule as written, on constants nobody has touched since they
were vendored.

### Anti-re-roll

**Every judgment must be recorded in `aggregate.judgments` and pooled. Rounds may be
added; a round may never be discarded.** That is the whole integrity mechanism, and it is
cheap to enforce because adding rounds barely moves a mean — one lucky draw of +6 moves a
mean of eight rounds by +0.75. Re-rolling for a better number is not worth the
electricity.

The single exception is an **invalidated** measurement — a defective instrument (a stale
rubric path, a truncated response), flagged and auditable in the record. Never a score
somebody merely dislikes. A judgment refused as **malformed** by the justification
contract is the same exception applied at parse time, and it leaves an audit-trail entry
naming the provider and the round: 18 of run 4's 198 attempted judgments were refused this
way, which is why `n` differs by judge in the calibration table above.

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
2026-08-21 (`features/owasp-ast10-agent-skills/build-notes.md`).

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

<!-- BEGIN:results -->
**11 of 11 skills judged; 9 clear the ship rule.** Verdicts and grades below are recomputed from each scorecard's own `aggregate.judgments` by `ship_floor.aggregate_verdict`; stored verdicts are never copied. Unjudged skills keep their placeholder row rather than dropping out of the table.

| Skill | Rounds | Mean | Mean − σ | Lowest dim (floor) | Grade | Verdict |
| --- | ---: | ---: | ---: | --- | --- | --- |
| `AST01` | 17 | 108.5 | 102.5 | `D3` 12.2/13 ⚠ | A | BLOCKED — dimension means below floor: D3 |
| `AST02` | 15 | 112.3 | 107.7 | `D2` 13.4/13 | A | SHIP |
| `AST03` | 18 | 110.7 | 106.4 | `D2` 13.4/13 | A | SHIP |
| `AST04` | 17 | 112.6 | 108.9 | `D6` 13.8/13 | A | SHIP |
| `AST05` | 14 | 111.2 | 107.1 | `D2` 13.7/13 | A | SHIP |
| `AST06` | 15 | 111.3 | 107.3 | `D2` 13.5/13 | A | SHIP |
| `AST07` | 17 | 110.3 | 105.1 | `D5` 13.5/13 | A | SHIP |
| `AST08` | 18 | 110.8 | 106.1 | `D3` 13.2/13 | A | SHIP |
| `AST09` | 17 | 108.2 | 103.4 | `D2` 13.1/13 | A | BLOCKED — lower bound (mean - stdev) 103.4 < 105 — mean 108.2 is within noise (sigma 4.85) of failing badly |
| `AST10` | 16 | 113.2 | 107.7 | `D5` 13.8/13 | A | SHIP |
| `advisory` | 16 | 112.2 | 107.4 | `D2` 13.8/13 | A | SHIP |
| `ast01-malicious-skills` | — | — | — | — | — | NOT YET JUDGED |
| `ast02-supply-chain-compromise` | — | — | — | — | — | NOT YET JUDGED |
| `ast03-over-privileged-skills` | — | — | — | — | — | NOT YET JUDGED |
| `ast04-insecure-metadata` | — | — | — | — | — | NOT YET JUDGED |
| `ast05-untrusted-external-instructions` | — | — | — | — | — | NOT YET JUDGED |
| `ast06-weak-isolation` | — | — | — | — | — | NOT YET JUDGED |
| `ast07-update-drift` | — | — | — | — | — | NOT YET JUDGED |
| `ast08-poor-scanning` | — | — | — | — | — | NOT YET JUDGED |
| `ast09-no-governance` | — | — | — | — | — | NOT YET JUDGED |
| `ast10-cross-platform-reuse` | — | — | — | — | — | NOT YET JUDGED |
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
    "dim_means": {"D1": 18.0, "D2": 14.0, "D3": 14.0, "D4": 14.0,
                  "D5": 14.0, "D6": 14.0, "D7": 9.0, "D8": 13.0},
    "dim_n": 4
  }
}
```

Then:

```bash
python3 eval/generate_dashboard.py    # rewrites the Results table above
python3 scripts/ship_floor.py         # recomputes every stored verdict, fails on drift
```

The generator never copies a stored `verdict` or `grade`: it recomputes both from
`aggregate.judgments` through `ship_floor.aggregate_verdict`, and a scorecard whose stored
statistics disagree with the recompute is rendered `BLOCKED` with the reason shown.
