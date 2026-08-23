---
name: ast01-malicious-skills
description: "Detect and triage OWASP AST01 Malicious Skills — hidden payloads (credential stealers, backdoors, social-engineering prose) shipped inside an otherwise-legitimate-looking SKILL.md or its dependency tree. Use when reviewing a skill before install, when a previously-clean skill starts behaving differently after repeated invocation (possible cognitive-degradation drift, not a single bad write), when classifying whether a finding is AST01 versus a AST02 supply-chain or AST04 metadata problem, or when deciding what a container sandbox does and does not stop."
---

# AST01 - Malicious Skills

Pattern: Knowledge. This file carries the decision rules that separate AST01 from its
four adjacent categories and the boundary conditions that make each preventive control
fail; the static-detectable checks it justifies live in `scripts/` (T-3.3) and the
frozen per-scenario tier list lives in `coverage-matrix.md` (T-3.1), not here.

## Why this is not "malware scanning with extra steps"

Traditional malicious-package detection assumes the payload is code. AST01 payloads
split across two layers that do not share a detector: the code layer (shell/Python
calls) and the natural-language instruction layer (markdown prose telling the agent
to act). A skill can carry zero suspicious code and still be malicious — three lines
of markdown were sufficient to exfiltrate SSH keys (Snyk, Feb 2026). Any detector that
only inspects executable fragments has a built-in blind spot; the decision rule is
that code-layer and prose-layer analysis are two independent required checks, not one
check with two input types.

## Decision rules

1. **A verified signature answers "who published this," never "is this safe."**
   Ed25519 signing composes with behavioral scanning and reputation; it does not
   substitute for either. Treat a signed-but-unscanned skill as unscanned, not as
   trusted-by-transitivity.
2. **Container isolation constrains the launched script, not the agent.** A malicious
   SKILL.md can persuade the *host agent* to invoke tools outside the sandbox boundary
   entirely through natural-language instruction — no escape required. A finding that
   "the skill ran in a locked-down container" does not close an AST01 review; the
   induced-tool-call path is a separate, unclosed surface. Retain skill identity,
   version, and content hash on every induced host-side action so it can be attributed
   back to the instructing skill.
3. **Memory/identity-file writes are a separate control plane from install-time gates.**
   A signed, scanned, reputation-clean skill can still poison `MEMORY.md` or `SOUL.md`
   in a *later* session — that is a runtime, post-install attack that install-time
   signature/scan gates structurally cannot see. Any write from a skill to an identity
   artifact is elevated-risk by default, independent of that skill's install-time score.
4. **Cognitive degradation is drift, not an event — do not gate only at install.** QSAF's
   six-stage chain (trigger injection → resource starvation → behavioral drift → memory
   entrenchment → functional override → systemic collapse) can be entered by accident
   (verbose output, unbounded retries) or on purpose by a skill that reads clean in a
   one-time review and degrades the host agent only after repeated invocation. Because
   it requires runtime accumulation, it evades exactly the one-time scanning and
   manifest review that AST08/AST04 controls rely on — a category this skill's
   detectable tier explicitly cannot close from a single artifact inspection.
5. **A skill's identity-artifact read is worse than its write.** Reading `SOUL.md` /
   `MEMORY.md` / persona/config files lets an attacker clone the agent's *behavioral*
   identity (not just its credentials) for replay or impersonation elsewhere. Because
   agentic identity is contextual, not just cryptographic, a read-only permission
   request against these files still warrants the same elevated review as a write
   request.

## Distinguishing AST01 from its neighbors (the seam, not the overlap)

- **vs AST02 (Supply Chain Compromise):** AST02 is the *delivery mechanism* — a
  compromised registry, a takeover'd maintainer account, a poisoned nested dependency.
  AST01 is the payload once delivered. A typosquatted package name (`gogle-workspace`)
  that turns out to carry no payload is AST02-only; the same package carrying a
  credential stealer is both. Do not double-tier a single finding into both matrices —
  classify by which control would have stopped it: registry/publisher controls → AST02;
  payload-content controls → AST01.
- **vs AST04 (Insecure Metadata):** AST04 covers *unsafe parsing* of the skill's own
  metadata files triggering code execution at load time (e.g. legacy YAML loaders).
  AST01's Instruction Override and hidden-payload scenarios require no parser bug at
  all — the prose itself is the payload, read and acted on exactly as designed.
- **vs AST05 (Untrusted External Instructions):** if the payload sits in the skill's
  own SKILL.md body, it's AST01. If a malicious author places the same payload in a
  document the skill merely *references* (a URL, a runbook), keeping the shipped
  SKILL.md clean, that's AST05 — the skill passes install-time review because there is
  nothing to review yet.
- **vs AST08 (Poor Scanning):** AST08 is about detector capability/coverage; AST01 is
  about what the malicious artifact does. A missed AST01 finding is an AST08 defect in
  the tool that should have caught it, not a second AST01 finding.

## Attack-scenario notes worth the extra sentence

- **Typosquatting vs. slopsquatting vs. ToxicSkills:** these three terms are not
  synonyms. Typosquatting exploits human misreading (`clawhud` vs `clawhub`);
  slopsquatting exploits LLM-hallucinated package names; "ToxicSkills" is Snyk's
  research-program name for its broader agent-skill corpus, not an attack technique.
  A detector or reviewer conflating them will mis-tag findings against the wrong
  mitigation family.
- **Hidden prompt injection in skill *output*, not just skill *input*:** a malicious
  skill can embed concealed instructions in what it *returns*, so a downstream model
  node that treats a prior skill's output as trusted instruction (rather than
  provenance-tagged untrusted data) re-triggers the same class of attack one hop later.
  This is why instruction-hierarchy enforcement has to survive skill-to-skill handoffs,
  not just the user-to-agent boundary.
- **A verified-publisher signal is only as strong as its revocation path.** Binding a
  signature to a bare public key (not a resolvable, revocable publisher identity — key
  id + publisher id such as a domain or `did:web` + a published verification key) means
  a compromised signer cannot be revoked without breaking every skill that key ever
  signed. Absence of a revocation mechanism is itself a finding, not a missing feature.

## Scope and out-of-artifact boundary

The Cognitive Degradation chain (decision rule 4) and any finding that depends on
*repeated* runtime behavior over multiple sessions cannot be established from a static
read of one skill package — the artifact alone has no session history. Whether this
skill's declared-detectable tier includes any *static precursor signals* (e.g. unbounded
retry loops, verbose-output patterns) versus classifying the full degradation chain as
agent-judgable or out-of-artifact is fixed in `coverage-matrix.md`, not decided here;
do not infer a tier from this prose.

## References

Full attack-scenario catalog, real-world evidence (ClawHavoc campaign, USENIX Security
2026 measurement study, Snyk ToxicSkills), and the complete preventive-mitigation list
are the whitepaper's own AST01 section — treat this file as the delta on top of it, not
a restatement of it. See `references/` for source excerpts once populated (T-3.3).
