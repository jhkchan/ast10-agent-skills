---
name: ast09-no-governance
description: "Detect and triage OWASP AST09 No Governance — no skill inventory, no approval workflow, orphaned skills after offboarding, regulated-data exposure with no audit trail, unreachable skills inside managed SaaS platforms, and bilateral-receipt audit logging (admission + outcome records). Use when designing or auditing a compliance-grade skill audit trail, when a skill lives inside a SaaS copilot the security team cannot scan, when distinguishing a signed-tamper-evident log from an operator-editable one, or when mapping an AST09 finding to EU AI Act Article 12 logging obligations."
---

# AST09 - No Governance

Pattern: Knowledge. The decision rule this category turns on: a log an operator
controls can be edited after the fact; a receipt an independent verifier can
cryptographically check cannot — "we have logging" and "we have compliance-grade
audit evidence" are different claims, and most AST09 mitigation lists conflate them.

**Fires on** the organization's control over skills rather than on a skill: no inventory,
no approval record, an offboarded installer's skill still credentialed, regulated data with
no audit trail, a skill inside a managed SaaS copilot the security team cannot scan, or an
audit-logging design that needs judging. **Decides** which of those claims a body of
evidence actually supports, and which population a coverage claim is entitled to cover.
**Decides nothing from the package**: all seven scenarios are out-of-artifact, `scripts/`
ships **no detector**, and that is the finished state rather than a gap — "This category
ships zero detectors" says why. Frozen scenario tiers live in `coverage-matrix.md`.

### Read only what the finding needs

| If the finding is… | Read |
| --- | --- |
| an audit-log or receipt design ("we log everything") | rules 1–3, then stop |
| "our skill scan came back clean" | rules 4–5 |
| a departed employee's skill still live | rule 6 |
| a multi-agent chain, or a fan-in join | rule 7 |
| "no detector ships — so what do I actually do?" | "The manual pass" |
| one skill's manifest granting too much | wrong skill → **AST03** |
| an installed skill drifted from its approved version | wrong skill → **AST07**, unless no approved version was ever recorded, in which case it is AST09 |
| isolation not enforced at one deployment | wrong skill → **AST06** for the control failure; the fleet's inability to see that deployment is still AST09 |

The last three rows are argued in "Distinguishing AST09 from its neighbors"; read it only
when a routing call is contested. **Do NOT open `coverage-matrix.md`** except for a binding
tier, an F1 question, or the off-artifact evidence for one named scenario — it is the only
file that carries per-scenario evidence, and this one deliberately does not reproduce it.
**Do NOT open `scripts/detector.py`** looking for a check: `DETECTORS` is `{}` by
construction, and the module says nothing "This category ships zero detectors" does not.

## Why "we have logs" does not close this category

The gap here is architectural, not a missing checkbox in one product, and the test for
that is simple: skill installation produces **no artifact any existing asset-management
tool recognizes**. No enterprise logging hook, no CMDB entry, no IAM integration, no
package receipt — a one-line install or a bare SKILL.md upload leaves the fleet's
existing inventory exactly as it was. That is why adding a logging feature to one
runtime does not move the category: the tool now records what it already knew about, and
the skills nobody knew about stay invisible.

Two consequences a reviewer should carry into any AST09 conversation. First, "we have
logging" and "we have compliance-grade audit evidence" are different claims: a log the
operator can edit after the fact answers neither *what was authorized* nor *what
happened*, only *what the operator is currently willing to say*. Second, coverage claims
in this category must name their discovery method, because each method is blind to a
different population — see decision rule 4.

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

## This category ships zero detectors, and that is the finding

All seven AST09 scenarios are tiered out-of-artifact — the only category in the suite
where that is true of every scenario — so the detector map is empty by construction and
this category publishes no F1 at all. The reason is one sentence, and it is worth
holding onto because it generalizes: **an approved copy and an unapproved copy of the
same skill are byte identical.** Approval, inventory, offboarding state, data
classification and install-count provenance are all facts held about the artifact by an
organization, never facts held *in* it.

That also disposes of the tempting workaround. One could write fixtures whose SKILL.md
prose says "this skill was never approved", detect the prose, and publish a number. The
number would measure a fixture-authoring convention, not a governance control, and it
would be indistinguishable in any report from a real detection rate. The registry
records no `artifact_signal` for any of the seven — unlike other categories, AST09 does
not even have an in-package proxy worth naming — so there is nothing here to promote
even accidentally. Report `declared-and-uncovered` and put the effort into the
off-artifact evidence each scenario actually needs; `coverage-matrix.md` names that
evidence per scenario.

## The manual pass, since nothing here runs

Two commands exist and neither returns a verdict. `node cli/bin/cli.js audit <pkg>` prints
`AST09  No Governance  no static detectors` and lists all seven scenarios as "declared
out-of-artifact, not decidable from one package"; `/ast:audit-ast09 <pkg> --evidence-plan`
emits the same seven with the evidence each needs. Read a clean run of either as *not asked*,
never as *asked and cleared* — a package that passes the other nine categories has said
nothing about this one. The review itself is four joins, and the package supplies the key
for exactly one of them: its content hash.

1. **Inventory row, keyed on that hash** — name, version, hash, install date, installer
   identity, last scan status. A missing row is not a blocked step — it is the AST09-S02
   finding, and it should be written down as one.
2. **Identity state for the installer, and for the credential the skill itself runs under.**
   An offboarding record sitting beside a live credential or an unrevoked non-human identity
   is AST09-S03 — and per rule 6 the fix belongs in the offboarding workflow, so record which
   workflow was supposed to carry it.
3. **Execution record over a real interval**, in the shape rules 1–3 require. If the records
   on offer are operator-editable, stop and say so at that grain: the finding is "no
   independently verifiable record", not "logging absent", and the two get different fixes.
4. **The discovery method itself, named in the finding.** Rule 4 makes this a claim about
   population, so a finding that does not say which method produced it cannot be scoped by
   whoever reads it next.

Steps 1–3 returning nothing is the ordinary first-pass outcome and is a result: report the
missing system by name. "Inconclusive" is the one write-up to refuse, because it reads in a
report exactly like a clean scan of a system that was never checked.

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
section (source: the OWASP Agentic Skills Top 10 publication, section AST09 (no local copy: the whitepaper is not redistributable here, so this points at the publication rather than at a file in this package)). This file is the delta on top of it.
