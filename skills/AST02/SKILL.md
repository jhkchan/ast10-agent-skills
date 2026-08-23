---
name: ast02-supply-chain-compromise
description: "Detect and triage OWASP AST02 Supply Chain Compromise — registry flooding, dependency confusion in a skill's nested requirements.txt/package.json, config-file hijacking (.claude/settings.json, hooks), and maintainer-account takeover. Use when auditing a skill registry's provenance controls, when a skill's top-level files look clean but its dependency tree is unaudited, when a repository's config files (not its source) are the suspected execution path, or when deciding whether a finding belongs here versus AST01 (the payload) or AST08 (the missed detection)."
---

# AST02 - Supply Chain Compromise

Pattern: Knowledge. Decision rules for where AST02 controls reach and where they
structurally cannot; mechanism (hash-pinning checks, config-file diffing) lives in
`scripts/`, and the frozen scenario tiers live in `coverage-matrix.md`.

## Why this is not "npm supply-chain security, renamed"

Mature ecosystems (npm, PyPI, Cargo) already have provenance norms — code signing,
security review, sandbox-by-default. The whitepaper's own evidence is that the barrier
to publishing on ClawHub was a SKILL.md file and a one-week-old GitHub account: no
code signing, no security review, no sandbox by default. The decision consequence is
that "the skill is on a registry" carries near-zero provenance signal for AST02
purposes — a registry-membership lookup is not verification. Treat registry presence
and cryptographic verification as two different assertions with two different checks.

## Decision rules

1. **A registry membership check is not integrity verification.** Cryptographic
   verification requires a signature over a canonical digest, plus append-only
   inclusion proofs and consistency proofs (Certificate-Transparency-style). A lookup
   that only confirms "this hash is listed" cannot detect a transparency-log operator
   silently rewriting history; it only detects a hash mismatch against whatever the
   log currently claims.
2. **Sign the bundle, not the entry point.** The signature must cover a canonical
   digest of SKILL.md *plus every declared resource file*, so a post-publish edit to
   any declared file — not just the top-level manifest — invalidates it. A signature
   scheme that only hashes SKILL.md leaves every referenced resource file an
   unauthenticated attack surface.
3. **The payload is usually in the nested dependency, not the top-level skill.**
   Dependency Confusion tampers with a transitive package, not the surface skill file
   — this is precisely why a scanner that only inspects the skill's own top-level
   files (the AST08 failure mode) misses it. A skill named "Summarize YouTube Videos"
   that imports `yutube-dl-core` instead of the legitimate package is the canonical
   shape: the surface skill reads clean.
4. **Version ranges are not a security control; hash pins are.** `requests>=2.25.0`
   permits any future release under that range, including a compromised one, to satisfy
   the dependency at install time with no new review. `requests==2.31.0
   --hash=sha256:<digest>` pins to bytes, not to a mutable name+range. Hash-checking
   mode requires *every* package in the transitive tree to carry a hash — a partial
   pin is not a pin.
5. **Repository configuration files are executable code, not passive metadata — treat
   them as first-class attack surface.** `.claude/settings.json`, hooks, and
   environment-override files (e.g. `ANTHROPIC_BASE_URL`) can trigger on repo-open,
   before any user action and before any skill even runs — this is a distinct trigger
   condition from AST01's "user installs/invokes a malicious skill."
6. **Revocation must be addressable at three granularities, or it isn't usable.** A
   compromised signing key, one bad skill version by content digest, and an entire
   publisher are three different blast radii; a revocation mechanism that can only
   revoke "the whole publisher" over-blocks every other skill from a large publisher
   for one bad release, and under-scopes when only a single key is compromised. Hosts
   must consult a revocation endpoint at load time with a bounded freshness window —
   a revocation list checked only at publish time misses post-publish compromise.

## Distinguishing AST02 from its neighbors

- **vs AST01:** AST02 is delivery/provenance; AST01 is payload. "Publishers could
  upload unlimited packages with no scanning" is an AST02 finding about the registry
  even if every uploaded skill that day happened to be benign.
- **vs AST05 (Untrusted External Instructions):** AST02's code-integrity controls
  (hash pins, signed digests) can pin and verify a *dependency*. They cannot pin a
  *document a skill merely reads at runtime* — that is AST05's surface exactly because
  those integrity controls do not reach it. A CVE fixed in a pinned dependency and a
  poisoned referenced runbook are different attack surfaces requiring different
  controls, even when both are "external content the skill trusts."
- **vs AST07 (Update Drift):** AST02 is compromise at publish/delivery time
  (Maintainer Account Takeover pushing v2.0 with a payload); AST07 is drift after a
  *legitimate* install goes unpatched, or an update mechanism blindly applying
  upstream changes. The Maintainer Account Takeover scenario sits at the seam: the
  takeover itself is AST02, and an agent auto-applying that malicious update without
  human review is the AST07 half of the same incident.
- **vs AST08:** a scanner that never inspects the recursive dependency tree — only
  the top-level skill file — is an AST08 gap that *causes* AST02 dependency-confusion
  attacks to go undetected. Classify the missed detection capability as AST08 and the
  underlying compromise as AST02; they are not interchangeable labels for one finding.

## Real-world anchors worth citing precisely

Claude Code CVE-2025-59536 and CVE-2026-21852 are the concrete evidence that config-file
hijacking is not theoretical: simply cloning and opening a malicious repository
triggered RCE and API-key exfiltration before the user saw any dialog. Trail of Bits
(Jun 3, 2026) is the concrete evidence against relying on scanning alone here — they
bypassed every scanner they tested and explicitly recommend the traditional
supply-chain response (curated marketplace, pinned versions, controlled publish/update
rights) *because* automated scanning cannot replace trust decisions. Cite these, not a
generic "supply chain attacks are increasing" framing.

## Scope and out-of-artifact boundary

Maintainer Account Takeover is a registry-side event — whether a given publisher
account was actually compromised is not observable from the skill artifact itself; a
detector can only observe *symptoms* (a signing-key change, an anomalous version jump)
that a coverage matrix may tier as agent-judgable rather than static-detectable. The
authoritative tier and its written reason live in `coverage-matrix.md`; this file does
not pre-empt that lock.

## References

Full attack-scenario catalog and preventive-mitigation list are the whitepaper's own
AST02 section (source: `ast02.md`). This file is the delta on top of it.
