---
name: ast09-no-governance
description: "Detect and triage OWASP AST09 No Governance — no skill inventory, no approval workflow, orphaned skills after offboarding, regulated-data exposure with no audit trail, unreachable skills inside managed SaaS platforms, and bilateral-receipt audit logging (admission + outcome records). Use when designing or auditing a compliance-grade skill audit trail, when a skill lives inside a SaaS copilot the security team cannot scan, when distinguishing a signed-tamper-evident log from an operator-editable one, or when mapping an AST09 finding to EU AI Act Article 12 logging obligations."
---

# AST09 - No Governance

Pattern: Knowledge. The decision rule this category turns on: a log an operator
controls can be edited after the fact; a receipt an independent verifier can
cryptographically check cannot — "we have logging" and "we have compliance-grade
audit evidence" are different claims, and most AST09 mitigation lists conflate them.
Mechanism (receipt schema validation, inventory reconciliation) lives in `scripts/`;
frozen scenario tiers live in `coverage-matrix.md`.

## Why "we have logs" does not close this category

Cisco's State of AI Security 2026 reports 83% of organizations planning agentic AI
deployment against only 29% who feel ready to deploy it securely — the whitepaper
frames this gap as adoption outpacing governance, not as a logging-tooling gap
specifically. The sharper evidence is structural: skill installation requires no
enterprise logging hook, no CMDB entry, and no IAM integration by default — a
one-line `openclaw skill install` or a bare SKILL.md upload creates no artifact any
existing SAM tool recognizes. Adding a logging *feature* to one runtime does not
close AST09 fleet-wide; the absence is architectural, not a missing checkbox in one
product.

## Decision rules

1. **A signed admission receipt and a signed outcome receipt are two separate
   records joined by `attempt_id`, and both are mandatory.** The admission receipt
   (produced before execution: `agent_id`, `action_type`, `scope`, `policy_version`,
   `decision` of ALLOW/DENY/ESCALATE, signed) proves what was authorized; the outcome
   receipt (produced after: `terminal_state` of COMMITTED/FAILED, signed) proves what
   actually happened. Without `attempt_id` linking them, an auditor cannot confirm
   the admitted action and the executed action were the same action.
2. **A DENY decision still requires a signed admission receipt — the absence of an
   outcome receipt is not itself proof the action was blocked.** A DENY-with-no-outcome
   pattern is only trustworthy evidence of a correctly blocked action when the
   receipt pipeline itself is provably healthy; otherwise the same pattern is
   indistinguishable from telemetry loss, a crash, a queue failure, or tampering.
   Treat "no outcome receipt" as ambiguous, not as confirmation of a block, unless
   pipeline health is independently established.
3. **`policy_version` must be bound at decision time, in the signed record — not
   reconstructed afterward.** A policy change between admission and execution creates
   an unrecoverable audit gap if the version in effect at the moment of the ALLOW/DENY
   decision is not captured with that decision; recovering "which policy applied" from
   a separate change log after the fact cannot be verified independently.
4. **Discovery method must match where the skill actually lives.** Endpoint- or
   registry-based scanning finds skills the security team's tooling can reach; a
   skill deployed inside a managed SaaS copilot or agent platform, with endpoints and
   registries the security team does not administer, is invisible to that method by
   architecture, not by attacker concealment — the Unreachable Skill scenario. The
   required control is a *different* discovery method for this case: identity- and
   posture-based discovery from SaaS telemetry (OAuth grants, connected-app
   inventories, NHI activity, scope assignments), reconciled against the approved
   inventory so unmatched identities surface. Applying only endpoint scanning and
   reporting a clean result over-claims coverage for this scenario specifically.
5. **Scope/permission drift is itself a discovery signal, not just a change to log
   after the fact.** A new OAuth consent grant, a widened scope, or a fresh
   app-to-app connection should trigger inventory and revocation workflows the moment
   it is observed — treating drift as routine telemetry to review later misses the
   window where the drift itself was the actionable event.
6. **Revocation tied only to explicit incident response misses the routine case.**
   Orphaned Skill (a departed employee's still-active, still-credentialed skill) is
   not an incident — it is an unremarkable, high-frequency offboarding gap. The
   fix is a revocation process wired directly into the offboarding workflow, not an
   incident-response playbook that only triggers on detected compromise.
7. **Cross-execution linkage (`parent_action_ref`) is a proposed, not-yet-finalized
   extension — do not treat fan-in joins as solved.** Version 1 of the receipt model
   covers a single upstream parent per action cleanly; when a skill is admitted from
   more than one upstream outcome (a fan-in), the model does not yet guarantee a
   complete causal reconstruction. An implementation that cannot yet support fan-in
   must record that limitation explicitly rather than implying the reversibility walk
   covers every parent branch when it does not.

## Distinguishing AST09 from its neighbors

- **vs AST06 (Weak Isolation):** a shadow deployment that isolation-enforcement gaps
  enable is an AST06 technical control failure at one deployment; the fleet-level
  inability to *see* that deployment at all — no inventory entry, no approval record
  — is the AST09 finding. Both can be true of the same incident; fix the isolation
  default under AST06 and the inventory/discovery gap under AST09 separately.
- **vs AST07 (Update Drift):** AST07 is missing *version* control (an installed
  skill drifts from a known-good version). AST09 is missing *installation* control
  (the skill was never approved, inventoried, or reviewed in the first place, so
  there is no known-good baseline to drift from). A skill with no governance record
  at all cannot be meaningfully scored for update drift — there is no approved
  version of record to drift against.
- **vs AST03 (Over-Privileged Skills):** AST03 is a single skill's manifest being too
  broad for its function; AST09's "lack of permission review processes" finding is
  that no *process* exists to catch that condition at scale — the organizational
  absence, not the individual over-grant.

## Scope and out-of-artifact boundary

Orphaned Skill, Regulatory Exposure, and Unreachable Skill are, by the whitepaper's
own framing, properties of an *organization's process and identity data* (offboarding
records, compliance review logs, SaaS OAuth telemetry) maintained entirely outside any
single skill package — a static read of one SKILL.md carries none of that. This is
the strongest out-of-artifact case in the whole suite; the ADR that governs
per-scenario tiering names these three scenarios explicitly as the reason the F1
denominator must be narrowed to the declared-detectable tier rather than silently
inflated. The binding tier and written reason for each are fixed in
`coverage-matrix.md`, not decided in this file.

## References

Full attack-scenario catalog, the Bilateral Receipt Pattern audit-logging
specification, and EU AI Act Article 12 relevance are the whitepaper's own AST09
section (source: `ast09.md`). This file is the delta on top of it.
