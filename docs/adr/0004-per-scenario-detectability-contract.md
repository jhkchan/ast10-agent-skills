---
artifact: adr
version: "1.0"
created: 2026-08-21
status: accepted
---

# ADR-0004: Per-Scenario Detectability Contract Governs AST Detector Coverage and the F1 Denominator

## Status

Accepted

**Date:** 2026-08-21
**Deciders:** [Jacky Chan](https://github.com/jhkchan) (Reviewer/Contributor, feature owner)

## Context

Gate B requires the detector suite to reach F1 >= 0.80, reported per AST category, against a
hand-labeled fixture corpus. The source whitepaper names 58 attack scenarios across AST01-AST10,
but they are not uniformly observable inside a single skill package. AST07 Rollback Attack and
Hot-Reload Abuse require version history; AST09 Orphaned Skill, Regulatory Exposure and Undetected
Compromise are properties of an organization's process rather than of an artifact; AST10
Cross-Registry Arbitrage and Multi-Platform Campaign require a cross-registry corpus; AST02
Maintainer Account Takeover is registry-side. For these, any per-category F1 can only be produced
by authoring fixtures that the detector was written to match, which measures the fixture author
rather than the detector.

At the same time, Gate B's other half requires all ten skills to reach Grade A on a rubric whose
dominant dimension, D1 Knowledge Delta (floor 17/20), fell below floor in 9 of 14 skills in the
mature prior-art repo, where only 2 of 14 shipped under the identical pooled rule. Pushing detector
mechanism into SKILL.md to serve half 2 directly degrades half 1.

A decision is needed on how detector scope is bounded and what the published F1 is computed over,
and it must be made before the fixture corpus is labeled and the per-skill file layout is fixed —
reversing it afterward invalidates already-labeled fixtures.

## Decision

We will govern detector coverage with an explicit per-scenario detectability contract:

- Every one of the whitepaper's named attack scenarios is classified in a per-skill coverage
  matrix as `static-detectable`, `agent-judgable`, or `out-of-artifact`, each with a written
  reason (e.g., AST09 Orphaned Skill is classified `out-of-artifact` because it "requires version
  history and release metadata maintained outside the artifact").
- Detectors ship as skill-owned scripts anchored on the whitepaper's own Universal Skill Format
  (USF) manifest schema.
- SKILL.md carries knowledge and decision rules rather than mechanism; mechanism lives in
  `scripts/` and `references/`.
- The Gate B per-category F1 >= 0.80 bar is computed over the declared-detectable tier
  (`static-detectable` + `agent-judgable`) only. The `out-of-artifact` tier is published as a
  declared-and-uncovered row in the coverage matrix, never silently folded into or dropped from
  the denominator.

We choose this because it is the only way to satisfy Gate B's detection half with a number that is
not circular, and because it applies a doctrine this project has already adopted for the judge
matrix — unavailable providers are declared in config with a recorded reason and never silently
dropped — to scenarios instead of providers, rather than inventing a new exemption.

## Consequences

### Positive

- The published F1 measures detection rather than fixture authorship, and a reader can audit
  exactly which of the 58 scenarios the suite claims to cover and which it does not.
- The coverage matrix is itself high knowledge-delta content that serves D1 and D7 instead of
  competing with them.
- Keeping mechanism in `scripts/` and `references/` preserves the D5 progressive-disclosure ladder
  that a mechanism-heavy SKILL.md would break.
- Anchoring detectors on the whitepaper's published USF schema means validating a standard rather
  than house rules, which is cheaper to build and more citable given the credited-Reviewer
  attribution posture.
- The contract tells Step 03 precisely which scenarios justify paid LLM adjudication.

### Negative

- The published F1 denominator is narrower than a naive reading of Gate B implies, so the headline
  claim is weaker and open to the objection that the hard categories were excluded to make the
  bar. The coverage matrix and its written reasons are the only defense of that narrowing, and
  they must be reviewed and approved at Gate 02 before the fixture corpus is labeled.
- **Reversing a tier after Step 04 Build means re-labeling the entire affected category's fixture
  corpus and re-running the judge matrix** — the corpus is labeled against the tier in force at
  label time, so a scenario moved from `static-detectable` to `agent-judgable` (or vice versa)
  invalidates every fixture case labeled under the old tier for that scenario, and the category's
  F1 cannot be republished until the corpus is relabeled and the run repeated.
- The bet that judges read knowledge-in-SKILL.md/mechanism-in-scripts as discipline rather than as
  a thin body is unverified until pooled D5 comes back from Step 05; if it fails, mechanism has to
  migrate back into SKILL.md against this contract's grain.

### Neutral

- The tiering must be frozen and reviewed before fixture labeling begins for the affected category;
  labeling and tiering are therefore sequenced, not parallel, per category.

## Alternatives Considered

### A — Analyzer-first, thin-wrapper skills

Reproducible, fork-safe F1 runnable in CI. Rejected because thin wrappers are precisely the
rubric's Tool-not-Skill and Over-Engineered failure shapes, driving straight into D1 Knowledge
Delta, the dimension that fell below its 17/20 floor in 9 of 14 prior-art skills and blocked the
release.

### C — Ensemble adjudicated detection with LLM adjudicator

The only design that can plausibly reach F1 >= 0.80 on natural-language scenarios AST08 exists to
describe. Rejected because detection becomes non-deterministic and non-CI-runnable, and
per-category F1 costs at least four model rounds times ten categories times corpus in paid calls.

## Amendment — 2026-08-23 (T-3.1a): the count is 62, not 58

This record's Context and Consequences sections say the whitepaper names 58 attack scenarios. That
figure came from the document's table of contents. `scenarios/registry.yaml` extracts the scenarios
from the body of each category's "Attack Scenarios" section instead and finds **62**: four are body
sub-headings the table of contents omits — AST03 "Low-Privilege Skill Invokes a High-Privilege
Skill", AST05 "Malicious Instructions Embedded in Documents", AST05 "Denial-of-Service (DoS)
through Malicious Skills", and AST08 "Scanner Host Compromise and Resource Exhaustion".

Read every "58" above as 62. Nothing else in the decision changes: the tiering doctrine, the
tier-lock tripwire, and the never-pad rule all hold, and each of the four newly counted scenarios
is tiered in the registry like any other. The registry is now authoritative on tier;
`fixtures/manifest.yaml` links its labeled checks back to registry ids and is tested against them
in `tests/test_scenario_registry.py`.

Of the 62, the registry tiers 20 static-detectable, 8 agent-judgable, and 34 out-of-artifact — so
roughly two thirds of the whitepaper's named attack surface is not decidable from a single skill
package, which is a stronger version of the same claim this ADR was written to make.

## Amendment — 2026-08-23 (tier-doctrine integrity review): coverage is a second axis

An independent review found this contract's three-value tier vocabulary being used to
answer two different questions at once, and answering them differently depending on which
answer was convenient. The same predicate — content-hash absence, missing permission
metadata, a blanket network policy — was `static-detectable` inside the detector modules
that claimed it as coverage, and an `artifact_signal` in the registry entries where
counting it would have obliged someone to build a detector. In the reviewer's words: "When
it lets you claim a detector, it's static; when it would oblige you to build one, it's
out-of-artifact."

The contract is amended, not reversed. **A tier says whether a check is mechanical. It has
never said whether the check decides a named scenario, and it may not be read as saying
so.** Three changes make that explicit and testable:

1. `scenarios/registry.yaml` declares `artifact_signal_decidable` on every non-null
   `artifact_signal`, plus `artifact_signal_checks` naming any shipped check that computes
   that predicate. Out-of-artifact never meant "invisible in the package", and the registry
   now says which of the two it means, case by case.
2. Every `skills/<AST>/scripts/detector.py` declares `CHECK_COVERAGE` alongside
   `SCENARIO_TIERS`, in `fixtures/manifest.yaml`'s existing vocabulary — `full`,
   `artifact-signal-only`, `category-precondition` — and derives an `F1_SCOPE` that
   `f1_report` returns beside every number.
3. `tests/test_tier_doctrine_symmetry.py` enforces both directions: a check named as some
   scenario's `artifact_signal_check` must declare `artifact-signal-only`, and a check
   claiming `full` must link scenarios the registry independently tiers
   `static-detectable`.

**No scenario tier moved.** Each contested predicate was re-tested against the
defining-condition rule and each failed it for the reason it always did. What moved is the
detector-side claim, which is where the overclaim actually lived.

The honest consequence, pinned by a test: **no shipped module earns a `scenario-level` F1
today.** Every category's checks are proxies, category preconditions, or a mixture. The
coverage matrices said this in prose already; it is now machine-readable, and a detector
that genuinely decides a named scenario will fail that pin and force the matrix to be
updated in the same change.

Two consequences of the same review are recorded elsewhere and belong to this contract:

- **The tier-lock tripwire now guards the authority it names.** `validators/tier_lock.py`
  hashed only `fixtures/manifest.yaml`'s embedded copy of the tiering, so flipping a tier
  in the authoritative registry left the CLI printing "OK" and exiting 0. A second
  per-category lock, `registry_tier_lock`, is derived from `scenarios/registry.yaml` and
  checked by the same command; `tests/test_tier_lock_cli.py` drives the real CLI with a
  mutated registry and asserts a non-zero exit.
- **Twelve orphaned fixture files were deleted.** `fixtures/AST02/` and `fixtures/AST07/`
  held six labeled vulnerable/clean files each for categories with an empty labeled
  detectable tier and no publishable F1. AST07's encoded precisely the artifact_signals
  the registry declares for AST07-S01 and AST07-S02 — package-decidable, and therefore
  barred from counting as coverage by the defining-condition rule. Admitting them would
  have moved two `declared-and-uncovered` categories to `proxy-covered` on the strength of
  fixtures that decide none of their scenarios; leaving them was a labeled corpus no report
  could cite. `tests/test_coverage_matrix_ast01_ast03.py::test_no_category_ships_fixture_files_it_does_not_declare`
  stops the next set appearing.

## References

- `scenarios/registry.yaml` — the authoritative per-scenario registry this contract governs.
- `features/owasp-ast10-agent-skills/spec.md` — Gate 02 decision `gate-1` and the originating
  "Proposed ADRs" draft this record accepts.
- `features/owasp-ast10-agent-skills/plan.md` — T-1.1 (tier-lock ADR authoring), T-1.5 (tier-lock
  tripwire), T-3.1 (coverage-matrix authoring against this contract).
