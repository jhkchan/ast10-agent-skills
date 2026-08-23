---
name: ast10-cross-platform-reuse
description: "Detect and triage OWASP AST10 Cross-Platform Reuse — security metadata (risk_tier, permissions, signatures) silently dropped when a skill is ported between OpenClaw, Claude Code, Cursor, and VS Code, cross-registry arbitrage, and Universal Skill Format manifest validation (deny_write precedence, network allowlist default-deny, signed content hash). Use when validating a manifest against the Universal Skill Format schema, when a skill is being ported across runtimes and needs a re-validation gate, when a permission finding needs binding to a specific field's precedence rule, or when distinguishing this category from the nine it structurally underwrites."
---

# AST10 - Cross-Platform Reuse

Pattern: Knowledge. The decision rule this category turns on: AST10 is not a protocol
problem (MCP already standardizes the transport) — it is that no shared vocabulary for
*security metadata itself* exists, so identical intent (deny this skill write access to
identity files) is expressible on one platform and inexpressible on another. Mechanism
(USF schema validation) lives in `scripts/`, anchored on the schema below; frozen
scenario tiers live in `coverage-matrix.md`.

## Attribution — read before citing this section

The Universal Skill Format is the **whitepaper's own published proposal** (OWASP
Agentic Skills Top 10, ast10.md), not an invention of this project. This skill adopts
and validates against that published schema; it does not originate it. Any prose in
this repo that implies otherwise is a documentation defect, not a design decision (see
`docs/context.md` glossary delta, T-4.3).

## The manifest's own precedence rules — get these exactly right

```yaml
permissions:
  files:
    write: [~/.config/app.json]
    deny_write: [SOUL.md, MEMORY.md, AGENTS.md]
  network:
    allow: [api.example.com]
    deny: "*"
  shell: false
```

1. **`deny_write` always wins over `write` for any path it lists — most-specific-wins,
   not first-match.** A manifest granting broad `write` access with `SOUL.md` also
   present under `deny_write` denies that one path; a validator that evaluates `write`
   and `deny_write` independently rather than as one most-specific-wins resolution
   will misreport this as a conflict or, worse, as a grant.
2. **`network.allow` is evaluated default-deny; the `deny: "*"` line is redundant
   auditability, not an override.** Only domains explicitly listed under `allow` are
   permitted egress — this is true with or without an explicit `deny: "*"` present.
   Do not implement `deny: "*"` as a rule that must fire to produce the default-deny
   behavior; the absence of a domain from `allow` is sufficient on its own.
3. **Host matching is exact-or-suffix-at-a-label-boundary, host component only — no
   wildcard subdomains, scheme, or port matching unless a future revision states
   otherwise.** This is the same matching discipline AST08's egress-suppression rule
   requires, applied here to the manifest's own allowlist field: substring or
   prefix matching on unparsed URL text is a bypassable implementation, not a
   stricter one.
4. **`signature` covers the canonical JCS (RFC 8785) serialization of the manifest,
   excluding `signature` itself and including `content_hash`.** Validating a
   signature against an arbitrary JSON serialization of the same fields (rather than
   the canonical form) admits semantically-identical-but-differently-serialized
   manifests that fail or falsely pass verification depending on the serializer's
   key ordering and whitespace choices — canonicalization is not optional cleanup, it
   is what makes the signature checkable at all.
5. **`risk_tier` is an untrusted author assertion that governance policy must not be
   driven by directly.** Per the format's own design rationale, automated governance
   decisions must be driven by *permission-derived* risk classification computed from
   the manifest's actual grants; `risk_tier` is used only to detect
   under-declaration or policy inconsistency against that independently-derived
   classification — the same principle as AST04's Risk Tier Spoofing decision rule,
   restated here as the format's own stated design intent rather than an external
   critique of it.

## Decision rules for the porting event itself

6. **Porting is a re-validation trigger, never an equivalence assumption.** A skill
   with `risk_tier: L3` and a scoped `network.allow` on its source platform ported to
   a platform with no equivalent field does not inherit that platform's default
   permissiveness safely — it inherits the target's *default*, silently, unless
   porting explicitly re-validates the full security metadata against the target
   platform's actual enforcement surface. "It worked correctly on the source
   platform" is evidence about the source platform only.
7. **Cross-registry arbitrage exploits install-count as a trust proxy across
   registries that do not share scanning intelligence.** A skill lightly scanned on
   one registry and promoted to a more trusted one, leveraging accumulated install
   count as a false trust signal, defeats any single registry's own scanning — the
   control is cross-registry threat-intelligence sharing, not a stronger scanner on
   any one registry alone.
8. **Manifest Stripping and Implicit Privilege Escalation are the same underlying
   event described from two ends.** Stripping (the source manifest's fields drop
   during translation) is the cause; Implicit Privilege Escalation (the ported skill
   inherits the target platform's broader default) is the effect. A finding that
   only checks "did fields get dropped" without checking "what does the target
   platform default to in their absence" understates the actual exposure.

## Distinguishing AST10 from its neighbors

AST10 is structurally different from AST01–AST09: it is the metadata substrate the
other nine categories' controls are expressed *in*. `deny_write` is AST01's
identity-file-protection control given a field; `network.allow` is AST03's
domain-allowlist control given a field; `signature` + `content_hash` are AST01/AST02's
provenance controls given fields. A finding that a specific field is missing,
malformed, or silently dropped is AST10; a finding that the *value* of a present field
is wrong for the skill's function is the corresponding AST01–AST09 category. The two
frequently co-occur (a stripped `deny_write` field is both an AST10 porting defect and
an AST01-relevant exposure) — record both, since they are fixed by different actors
(the porting tool vendor vs. the skill author/reviewer).

## Scope and out-of-artifact boundary

Cross-Registry Arbitrage and Multi-Platform Campaign require observing a skill (or its
install-count history) across *multiple registries at once* — no single skill artifact
carries another registry's state. Whether these are checkable at all, and at what
tier, is fixed in `coverage-matrix.md`; this file does not assert a tier for them.

## References

The full Universal Skill Format proposal (complete field list: identity, signatures,
content hashes, permissions, `deny_write`, network allowlists, required tools, risk
tier, scan status, changelog) and the whitepaper's browser-only metadata-loss
simulator are in the whitepaper's own AST10 section (source: `ast10.md`). This file is
the delta on top of it.
