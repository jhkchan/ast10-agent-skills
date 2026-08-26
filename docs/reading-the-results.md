# Reading the results

How to read the roster and the F1 column without over-reading them, the four misreadings that
come up most, and how the ship gate reached its current form.

## Measured results

Two independent measurements, and collapsing them is the mistake this table exists to
prevent. **F1** is what the *detector* was measured at over the labeled fixture corpus.
**Judged** is what an independent judge panel scored the *knowledge package* — the `SKILL.md`
— against the skill-judge rubric. A category with no detector at all can still be a strong
skill, and a perfect F1 does not clear the judge gate. Per-judge scores and bias diagnostics
are in [`docs/skill-judge-dashboard.md`](skill-judge-dashboard.md); the rubric behind
that column is third-party work, [credited in
full below](#what-11-of-11-is-and-what-it-is-not).

| Skill | F1 (measured) | Judged (run 5) |
| --- | --- | --- |
| `ast01-malicious-skills` | `scenario-level 1.00 (n=16)` | **SHIP** 110.1 |
| `ast02-supply-chain-compromise` | `scenario-level 1.00 (n=6)` | **SHIP** 111.8 |
| `ast03-over-privileged-skills` | `scenario-level 1.00 (n=2)` + `artifact-signal-only 1.00 (n=4)` | **SHIP** 112.2 |
| `ast04-insecure-metadata` | `scenario-level 1.00 (n=10)` | **SHIP** 111.6 |
| `ast05-untrusted-external-instructions` | `artifact-signal-only 1.00 (n=6)` | **SHIP** 110.6 |
| `ast06-weak-isolation` | `scenario-level 1.00 (n=4)` + `artifact-signal-only 1.00 (n=2)` | **SHIP** 112.1 |
| `ast07-update-drift` | `declared-and-uncovered` | **SHIP** 110.2 |
| `ast08-poor-scanning` | `scenario-level 1.00 (n=8)` | **SHIP** 109.7 |
| `ast09-no-governance` | `declared-and-uncovered` | **SHIP** 111.1 |
| `ast10-cross-platform-reuse` | `scenario-level 1.00 (n=6)` | **SHIP** 112.4 |
| `advisory` | not scored — judged on guidance quality | **SHIP** 112.2 |

Every F1 above is printed in one shape, `scope value (n)`, because a number quoted without
its scope is the overclaim the labels exist to block; the manifest's own string for each one,
parenthetical and all, is in that skill's block below. Every verdict and pooled mean is
recomputed by `scripts/ship_floor.py` from `eval/scorecards/<AST>.json` rather than copied
from a stored field.

**Eleven of the eleven skills clear the ship rule**: pooled mean ≥ 108, the confidence bound
`mean − 1.0 × σ/√n` ≥ 108, and all eight dimension means above their floors, over 16 to 18
pooled judgments from six independent judges. **The same board is 8 of 11 without the panel's
least discriminating judge, and one of the eleven does not survive imputation of its own
missing judgments** — both measured, both in [How fragile 11 of 11
is](skill-judge-dashboard.md#how-fragile-11-of-11-is). Read that number with them and
with [What 11 of 11 is, and what it is not](#what-11-of-11-is-and-what-it-is-not) below — it
is four paragraphs and it is not decoration.

## Reading the columns

Each category carries three independent states: what the **detector** does, what its **F1** was
measured over, and how the *knowledge package* scored against the judge panel. They do not track
each other. A category with no detector at all can still be a strong skill, and a category with a
perfect F1 can still be blocked by the judge gate.

**Detector state** is re-derived on every test run from `scenarios/registry.yaml` (which scenarios
one package's own bytes can decide) and `fixtures/manifest.yaml` (which of those carry a shipped
check and a labeled fixture pair), so the column cannot describe a check that does not exist.

| State | What it means |
| --- | --- |
| **`implemented`** | Every decidable scenario in the category has a shipped check and a labeled fixture pair. Nothing decidable is unbuilt. |
| **`coverage-debt`** | A scenario is decidable and no shipped check decides it. **No category is in this state today** — it exists so that regressing into it shows up here rather than only inside a matrix. |
| **`declared-and-uncovered`** | Nothing in the category is statically decidable. No check ships, and no F1 is published at any corpus size. |

**F1 scope** records what each number was measured over, written as `scope value (n)` and derived
from `fixtures/manifest.yaml`.

| Scope | What it means |
| --- | --- |
| **`scenario-level`** | Decides a named whitepaper scenario's defining condition. |
| **`artifact-signal-only`** | Decides an enabling *precondition* a benign package can also exhibit — an unbounded retry loop, an unpinned reference, an absent permissions block. It is **not** coverage of any named scenario and may never be quoted as one. AST05 publishes only this. |
| two scopes joined by `+` | A mixed category, scored separately per scope so the proxy half cannot ride on the scenario half. |
| **`declared-and-uncovered`** | No number, at any corpus size. An empty detectable tier is reported as empty rather than filled with fixtures written to separate perfectly. |

## Common misreadings

**Shipped checks and measured checks are different counts, on purpose.** AST01 ships ten checks and
publishes an F1 over eight: its two `content_hash` checks decide a *precondition* rather than a
named scenario, so they run on every audit and enter no denominator. AST03 (4 shipped / 3 labeled),
AST04 (6 / 5), AST05 (5 / 3) and AST06 (5 / 3) have the same shape. A check that runs and is never
scored is not a hidden number — its `CHECK_COVERAGE` entry says outright that firing it proves
nothing about a whitepaper scenario.

**AST07 and AST09 publish nothing, and that is the registry talking, not a backlog.** Neither has a
single statically-detectable scenario in the whitepaper's own enumeration — every one is temporal or
organisational — so no corpus size would give them a denominator.

**AST05 ships five checks and still covers no scenario.** Its detectable tier is empty, like AST07's
and AST09's, yet it publishes a number, because its checks decide real preconditions over a real
corpus. What keeps that from being a padded F1 is the scope label: `artifact-signal-only` is not
comparable with a `scenario-level` number and cannot be quoted as AST05 coverage.

**A 1.00 is a discrimination claim about one hand-built corpus.** AST10's single detectable scenario
(AST10-S06, Silent Supply Chain Injection) is measured over six labeled cases whose three *clean*
packages each carry a real encoded blob — one of them the same gzip-under-base64 shape as the
vulnerable case — so a check that fired on "contains an encoded blob" would score 0.67, not 1.00.
Read [`skills/AST10/coverage-matrix.md`](../skills/AST10/coverage-matrix.md) before quoting the number.
The same caveat applies to every 1.00 in the column.

## How the ship gate was set

The gate has changed exactly once, and run 5 is the first corpus judged under the change. After run
4 was published, [ADR-0006](adr/0006-confidence-bound-on-the-pooled-mean.md) retired the
`mean - σ ≥ 105` clause and replaced it with `mean - 1.0 × σ/√n ≥ 108` — a confidence bound on the
mean rather than a spread statistic — because the retired clause was shown not to be a function of
the artifact: `AST08`'s `SKILL.md` is byte-identical between runs 3 and 4, and that clause alone
flipped its verdict. The replacement constant was recorded *before* the run it judged.

**On run 5 the change bought a ship.** Under the retired clause run 5 is **10 of 11**: `AST01`
clears the mean (110.1 ≥ 108) and misses `mean - σ` at 103.4, against 105. Under the clause in
force it is 11 of 11. No constant moved to produce that — but "the new rule costs nothing" is a
claim about run 4, not run 5. On run 4 it was true: nine of eleven shipped under either rule and no
verdict changed, which `tests/test_generate_dashboard.py` re-derives through today's gate against
the frozen `eval/scorecards-run4/`.

**Nor is the confidence bound reliably the stricter rule.** It demands a higher mean only where σ is
small, and run 5's per-skill σ never is — at all eleven `(n, σ)` pairs the adopted clause sets a
*lower* bar than the retired one. Across all five recorded runs, 55 skill-runs, it has demanded a
strictly higher mean on exactly three, with one exact tie (`AST06` in run 4). ADR-0006 replaced a
clause that was not a function of the artifact; it did not replace it with a uniformly stricter one,
and on the corpus it now gates it is the more permissive of the two.

`AST01` is the row where all of this lands at once: the skill the gate change buys, the skill three
of six single-judge exclusions block, and the skill whose two missing judgments flip it when they
are refilled at the means of the judges that lost them. See
[How fragile 11 of 11 is](skill-judge-dashboard.md#how-fragile-11-of-11-is).

---

---

[< Back to the README](../README.md)
