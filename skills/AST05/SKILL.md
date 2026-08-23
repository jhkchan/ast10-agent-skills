---
name: ast05-untrusted-external-instructions
description: "Detect and triage OWASP AST05 Untrusted External Instructions — skills that fetch external documentation (URLs, runbooks, schemas) and follow it as instruction rather than treat it as data, including Author Rug-Pull, Reviewer Bait-and-Switch, transitive reference chaining, and relay-node amplification in multi-skill chains. Use when a skill's referenced content has no hash pin, when a reviewed skill's external dependency could have changed since review, when triaging a skill-chain injection that no single node's review caught, or when deciding whether a finding belongs here versus AST01 or AST02."
---

# AST05 - Untrusted External Instructions

Pattern: Knowledge. The category exists because textual external references have none
of the tooling that code dependencies already have — no hash-pin field, no lockfile
for prose, and signing the skill package says nothing about what a URL returns at
runtime. Mechanism (content-hash pinning checks, reference-chain auditing) lives in
`scripts/`; frozen scenario tiers live in `coverage-matrix.md`.

## Why review-time inspection cannot close this category

Anthropic's own Agent Skills security guidance states plainly that "even trustworthy
Skills can be compromised if their external dependencies change over time" — this is
the platform vendor documenting, not hypothesizing, both the injection and the
rug-pull variants of AST05. The structural reason review cannot close it: the skill
*package* can be reviewed, signed, and hash-pinned; the *referenced* content cannot,
because nothing in the skill format pins a document's hash the way a lockfile pins a
dependency's. A skill that passed review yesterday and points at a URL the author
still controls can be silently rewritten today with no version bump, no re-signature,
and no visible diff to the skill itself.

## Decision rules

1. **A hash pin without a re-verify-on-every-load step is a snapshot, not a
   control.** Record a content hash for referenced material at review time, then
   re-check it *immediately before model ingestion* on every subsequent load —
   refusing content that is unpinned or has drifted. A pin checked only once, at
   install, degrades to the exact "reviewed skill is never the skill that runs"
   failure this category exists to prevent.
2. **A redirect to an unreviewed resource is a verification failure, not a
   pass-through.** Treat a missing reference the same way — log the resolved source,
   version, and content digest at the moment of failure so the specific drift is
   auditable, not just "content unavailable."
3. **Bait-and-switch defeats review by keying on the *reviewer*, not the content.** A
   URL can serve clean documentation to reviewers, scanners, and crawlers (by IP,
   user-agent, or timing) while serving malicious instructions to a live agent run.
   The decision consequence: a scan result is evidence about what the scanner's
   fetch saw, not evidence about what any given agent's fetch will see — a passing
   scan is not proof of a clean live path.
4. **Reference-following must be complete or explicitly bounded — a partial audit is
   a false negative generator.** Transitive Reference Chaining means an attacker
   needs to control only one link buried deep in a chain the agent follows, past
   where a shallow review stopped. If reference auditing has a depth limit, that
   limit is itself a declared scope boundary that must be recorded, not a silent
   truncation.
5. **A skill chain's injection resistance is the minimum over its nodes, and it does
   not compose across hops.** When one skill's output feeds the next (intake → triage
   → an action-taking skill), each node re-parses upstream output with its own
   instruction-vs-data boundary and its own backbone model. Some nodes neutralize an
   injected payload; others pass it on. The attacker needs exactly one weak relay.
   The consequence for review: certifying every endpoint of a chain does not certify
   the chain — the minimum-resistance node, not the average, sets the chain's actual
   exposure, and that node can differ per model swap even with the skill definitions
   held fixed.
6. **Prefer inlining a snapshot over fetching live, and treat "must stay current" as
   a distribution problem, not a fetch problem.** Snapshotting external documentation
   into the signed skill package at publish time makes it reviewable and pinnable
   like any other package content. When content genuinely needs to stay current,
   route updates through a controlled, auto-updating marketplace channel with its own
   review and provenance — not by pointing a skill at an arbitrary, unmanaged URL.

## Distinguishing AST05 from its neighbors

- **vs AST01:** if the payload sits in the shipped SKILL.md, it's AST01. If a
  malicious author places the identical payload in content the skill merely
  *references*, keeping the shipped skill body clean, that's AST05 specifically
  because the skill passes install-time review — there is nothing malicious to
  review yet at that point.
- **vs AST02 (Supply Chain Compromise):** AST02's integrity controls (hash pins,
  signed digests) reach *code dependencies* the skill declares and installs. AST05 is
  the *documentation* a skill points to at runtime — a surface those same integrity
  tools do not reach, because the referenced content was never part of the signed
  package graph in the first place.
- **vs AST07 (Update Drift):** AST07 is the *skill's own version* changing.
  AST05 is the identical drift phenomenon applied to *referenced content the skill
  points to*, which can change while the skill itself stays pinned, unchanged, and
  passing every version-based integrity check.
- **vs AST08 (Poor Scanning):** externally referenced content can be absent, or served
  differently, at scan time versus run time (the Reviewer Bait-and-Switch mechanism
  above) — this widens AST08's detection gap specifically to content a scanner may
  never actually observe, regardless of how good the scanner's own analysis is.

## Scope and out-of-artifact boundary

Whether a given referenced URL currently serves clean or malicious content is a live,
time-varying fact about an external host — not a property this artifact can determine
once and cache as ground truth. A detector can check *whether pinning/re-verification
exists as a control* (static-detectable) without being able to certify *what the
pinned content currently says on the open internet* (out of this artifact's reach).
The exact split is fixed in `coverage-matrix.md`.

## References

Full attack-scenario catalog (including Malicious Instructions Embedded in Documents,
resource-exhaustion DoS) and the complete preventive-mitigation list are the
whitepaper's own AST05 section (source: `ast05.md`). This file is the delta on top of
it.
