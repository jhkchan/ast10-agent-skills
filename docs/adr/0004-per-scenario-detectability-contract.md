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
**Deciders:** Jacky Chan (Reviewer/Contributor, feature owner)

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

## References

- `features/owasp-ast10-agent-skills/spec.md` — Gate 02 decision `gate-1` and the originating
  "Proposed ADRs" draft this record accepts.
- `features/owasp-ast10-agent-skills/plan.md` — T-1.1 (tier-lock ADR authoring), T-1.5 (tier-lock
  tripwire), T-3.1 (coverage-matrix authoring against this contract).
