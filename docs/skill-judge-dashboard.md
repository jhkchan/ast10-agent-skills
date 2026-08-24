# Skill-Judge Scorecard Dashboard

Pooled eight-dimension judge results for the eleven skills in this repository, scored
against the pinned skill-judge rubric and gated by the ship rule in
`scripts/ship_floor.py`.

This repository is an independent community implementation. It is **not** an official
OWASP project and carries no OWASP endorsement — see [`../README.md`](../README.md) and
[`../NOTICE`](../NOTICE).

> ## Judged run recorded — run 2, 2026-08-23
>
> **11 skills x 3 rounds x 6 providers = 198 independent judgments**, the second such run.
> Run 1's scorecards are retained under `eval/scorecards-run1/` so the delta is auditable.
>
> **Nine of eleven skills now clear every one of the eight dimension floors and score Grade A
> on the pooled mean** (>= 108), against **zero** in run 1. Pooled mean rose from 107.5 to 109.2.
> The largest single move is `advisory`, rebuilt from 103.3 to **112.8** — from the weakest
> artifact in the repository to the strongest.
>
> **Two skills still fall short, and they differ in kind.** `AST07` (105.4) is a measurement
> artifact: five of six judges score it 107-120 and `nova-pro` alone returns 79, giving a sigma of
> 14.04, and a trimmed judge-mean that drops the highest and lowest judge lands at 108.5 — a pass.
> `AST09` (105.7) is a genuine gap: the judges broadly agree, and its trimmed judge-mean is 104.3.
> Both are the categories that ship no detector at all because every one of their scenarios is
> out-of-artifact, which is the honest limit of what a package-only skill can offer on D8.
>
> **Every skill remains BLOCKED under the locked ship rule**, because `mean - sigma >= 105` is
> equivalent to `mean >= 105 + sigma` and at this panel's sigma that demands 110.4-119.0 rather
> than the 108 the rule names. That defect is recorded in
> [ADR-0005](adr/0005-judge-panel-calibration-and-the-lower-bound.md) and deliberately **not**
> fixed here: a bar changed after seeing the run it is applied to is not a bar. Adoption requires
> a superseding record and a fresh run.
>
> Regenerate after a run with:
>
> ```bash
> python3 eval/run_judge_matrix.py --rounds 3   # writes eval/scorecards/*.json
> python3 eval/generate_dashboard.py            # rewrites the table below
> python3 eval/calibration.py                   # per-judge bias diagnostics
> ```

---

## Judge calibration (measured, diagnostics only)

Regenerate with `python3 eval/calibration.py`. Panel: 6 providers x 11 skills = 198 judgments, pooled mean of **109.2**.

| Judge | n | mean | bias | round means |
| --- | ---: | ---: | ---: | --- |
| `bedrock/qwen3-235b` | 33 | 120 | +10.8 | 120 / 120 / 120 |
| `anthropic-compatible/glm-5.2` | 33 | 109.9 | +0.7 | 110.1 / 110.3 / 109.5 |
| `bedrock/deepseek-v3.2` | 33 | 109.5 | +0.3 | 107.5 / 109.8 / 111.1 |
| `bedrock/gpt-oss-120b` | 33 | 106.8 | -2.4 | 106.8 / 107.5 / 106.2 |
| `claude-cli/sonnet` | 33 | 105.5 | -3.7 | 104.9 / 105.9 / 105.7 |
| `bedrock/nova-pro` | 33 | 103.5 | -5.7 | 103.6 / 101.4 / 105.4 |

A **16.5-point spread** separates the most generous judge from the harshest, while no judge's own
round-to-round means differ by more than **4 points** — so this is systematic calibration bias,
not measurement noise. Per-skill sigma runs **5.43 to 14.04** against the 3.3 `ship_floor.py` was calibrated on, which makes `mean - sigma >= 105` demand a mean of **110.4 to 119** (92% to 99.2% of 120) rather than the 108 (90%) it names.
These figures are diagnostics: no gate constant is read from them and none was changed. See
[ADR-0005](adr/0005-judge-panel-calibration-and-the-lower-bound.md).

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
| **D3** Anti-Pattern Quality | 15 | 13 | A specific NEVER list with the reasoning behind it. Generic warnings ("be careful", "consider edge cases") score in the 4–7 band. |
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
sigma of 4 is *within noise of failing badly*, and this rule refuses it.

### Anti-re-roll

**Every judgment must be recorded in `aggregate.judgments` and pooled. Rounds may be
added; a round may never be discarded.** That is the whole integrity mechanism, and it is
cheap to enforce because adding rounds barely moves a mean — one lucky draw of +6 moves a
mean of eight rounds by +0.75. Re-rolling for a better number is not worth the
electricity.

The single exception is an **invalidated** measurement — a defective instrument (a stale
rubric path, a truncated response), flagged and auditable in the record. Never a score
somebody merely dislikes.

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
**11 of 11 skills judged; 1 clears the ship rule.** Verdicts and grades below are recomputed from each scorecard's own `aggregate.judgments` by `ship_floor.aggregate_verdict`; stored verdicts are never copied. Unjudged skills keep their placeholder row rather than dropping out of the table.

| Skill | Rounds | Mean | Mean − σ | Lowest dim (floor) | Grade | Verdict |
| --- | ---: | ---: | ---: | --- | --- | --- |
| `AST01` | 18 | 109.8 | 103.8 | `D8` 13.3/13 | A | BLOCKED — lower bound (mean - stdev) 103.8 < 105 — mean 109.8 is within noise (sigma 6.02) of failing badly |
| `AST02` | 18 | 109.1 | 102.6 | `D8` 13.1/13 | A | BLOCKED — lower bound (mean - stdev) 102.6 < 105 — mean 109.1 is within noise (sigma 6.45) of failing badly |
| `AST03` | 18 | 108.7 | 101.3 | `D6` 13/13 | A | BLOCKED — lower bound (mean - stdev) 101.3 < 105 — mean 108.7 is within noise (sigma 7.44) of failing badly |
| `AST04` | 18 | 108.7 | 102.4 | `D6` 13.1/13 | A | BLOCKED — lower bound (mean - stdev) 102.4 < 105 — mean 108.7 is within noise (sigma 6.29) of failing badly |
| `AST05` | 18 | 110.7 | 104.3 | `D8` 13.3/13 | A | BLOCKED — lower bound (mean - stdev) 104.3 < 105 — mean 110.7 is within noise (sigma 6.36) of failing badly |
| `AST06` | 18 | 109.3 | 103.2 | `D8` 13.1/13 | A | BLOCKED — lower bound (mean - stdev) 103.2 < 105 — mean 109.3 is within noise (sigma 6.13) of failing badly |
| `AST07` | 18 | 105.4 | 91.4 | `D6` 12.2/13 ⚠ | B | BLOCKED — dimension means below floor: D6, D8 |
| `AST08` | 18 | 110.7 | 104.3 | `D6` 13.3/13 | A | BLOCKED — lower bound (mean - stdev) 104.3 < 105 — mean 110.7 is within noise (sigma 6.43) of failing badly |
| `AST09` | 18 | 105.7 | 97.7 | `D6` 12.3/13 ⚠ | B | BLOCKED — dimension means below floor: D6, D8 |
| `AST10` | 18 | 110.2 | 102.6 | `D6` 13.3/13 | A | BLOCKED — lower bound (mean - stdev) 102.6 < 105 — mean 110.2 is within noise (sigma 7.59) of failing badly |
| `advisory` | 18 | 112.8 | 107.4 | `D8` 13.8/13 | A | SHIP |
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
