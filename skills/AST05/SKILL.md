---
name: ast05-untrusted-external-instructions
description: "Detect and triage OWASP AST05 Untrusted External Instructions — skills that fetch external documentation (URLs, runbooks, schemas) and follow it as instruction rather than treat it as data, including Author Rug-Pull, Reviewer Bait-and-Switch, transitive reference chaining, and relay-node amplification in multi-skill chains. Use when a skill's referenced content has no hash pin, when a reviewed skill's external dependency could have changed since review, when triaging a skill-chain injection that no single node's review caught, or when deciding whether a finding belongs here versus AST01 or AST02."
---

# AST05 - Untrusted External Instructions

Pattern: Knowledge. The category exists because textual external references have none
of the tooling that code dependencies already have — no hash-pin field, no lockfile
for prose, and signing the skill package says nothing about what a URL returns at
runtime. Mechanism lives in `scripts/detector.py`: a call-site dataflow scan that
follows a fetched response body to the agent's instruction channel or to an
executable sink, a gated check for a declared instruction-versus-data convention,
and two reads of how wide the declared fetch surface is. Every one of them is an
`artifact_signal` proxy, never coverage of a named AST05 scenario — frozen scenario
tiers and the reason for that live in `coverage-matrix.md`.

## Why review-time inspection cannot close this category

The reviewed object and the executed object are different objects, and no control in
the skill format connects them. A package can be reviewed, signed and hash-pinned; the
*documents it points at* cannot, because the format has no hash-pin field for prose and
no lockfile for a URL. A skill that passed review yesterday and points at a URL its
author still controls is silently rewritten today with no version bump, no
re-signature, and no diff anywhere in the artifact — the Author Rug-Pull shape.

That is why this category's static-detectable tier is **empty** and why this package
publishes no scenario-level F1 at all. It is not a gap in the detector. Every one of
AST05's six scenarios needs evidence the artifact cannot hold: the referenced document
at two points in time, or from several fetch vantage points, or the chain actually
followed, or the pipeline's per-node backbone models. The five checks that do ship read
*enabling preconditions* and are declared `artifact-signal-only` — a label that travels
with every number they produce, so no consumer can quietly promote a proxy into
coverage.

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

## Where the shipped checks go quiet

The two dataflow checks parse Python with `ast` and match call nodes — never source
text. That choice is load-bearing: a regex for `requests.get` matches this module's own
pattern tables and every fixture literal quoted in the tests beside it, so a text-based
version of these checks convicts the scanner itself. It also fixes the boundaries of
what they can see.

- **A declared boundary and an implemented boundary are indistinguishable here.** The
  taint is cleared by a call to any name in the boundary set (`sanitize`, `quarantine`,
  `as_reference_data`, `tag_untrusted`, …) or by a provenance marker in a nearby string
  literal. A function named `sanitize()` whose body is `return text` clears the finding
  completely. At the static layer, naming the control is the control — verifying that it
  does anything is a manual step, and it is the highest-yield one on this whole page.
- **Taint does not cross a function boundary or a file.** Fetch in one helper, sink in
  another, and both checks clear. Same for a fetch whose response is stored on an object
  attribute and read back later.
- **Python only, and an unparsed file is an INCOMPLETE that reads as a pass.** A
  JavaScript or shell fetcher produces no nodes at all. A `.py` file that fails to parse
  is counted and named in the evidence string, but the verdict is still negative — read
  the evidence, not the boolean.
- **The instruction-channel name list is narrow on purpose.** Only names that denote the
  channel itself (`prompt`, `messages`, `instructions`, `system_prompt`, …) are sinks.
  `rules`, `context`, `system` and `persona` were removed after they fired on a
  correctly-written clean fixture. A skill whose channel is spelled anything else is
  uncovered — precision was bought with recall here, deliberately.
- **`json.loads(response.text)` is not a sink and must not be made one.** Parsing a body
  as data is the correct handling; convicting it would fire on every well-written HTTP
  client in the corpus and destroy the check's usefulness.
- **The absent-boundary check is gated on a Python fetch call site.** A package that
  fetches only through a shell command never opens the gate, so the boundary question is
  never asked of it.

## Scope and out-of-artifact boundary

Whether a given referenced URL currently serves clean or malicious content is a live,
time-varying fact about an external host — not a property this artifact can determine
once and cache as ground truth. **None of AST05's six named scenarios is decidable from
a single skill package**, so this category publishes no scenario-level F1 at all. A
detector can check *whether a control exists* — an unpinned reference, a fetched body
reaching an instruction or executable sink, an absent boundary convention, an unbounded
fetch surface — without being able to certify *what the referenced content currently
says on the open internet*, or that the author will edit it after review. Those checks
are declared `artifact-signal-only` for exactly that reason. The exact split, and the
number the proxy corpus does publish, are fixed in `coverage-matrix.md`.

## References

Full attack-scenario catalog (including Malicious Instructions Embedded in Documents,
resource-exhaustion DoS) and the complete preventive-mitigation list are the
whitepaper's own AST05 section (source: `ast05.md`). This file is the delta on top of
it.
