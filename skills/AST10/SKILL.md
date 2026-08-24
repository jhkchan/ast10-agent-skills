---
name: ast10-cross-platform-reuse
description: "Detect and triage OWASP AST10 Cross-Platform Reuse — security metadata (risk_tier, permissions, signatures) silently dropped when a skill is ported between OpenClaw, Claude Code, Cursor, and VS Code, cross-registry arbitrage, and Universal Skill Format manifest validation (deny_write precedence, network allowlist default-deny, signed content hash). Use when validating a manifest against the Universal Skill Format schema, when a skill is being ported across runtimes and needs a re-validation gate, when a permission finding needs binding to a specific field's precedence rule, or when distinguishing this category from the nine it structurally underwrites."
---

# AST10 - Cross-Platform Reuse

Pattern: Knowledge. The decision rule this category turns on: AST10 is not a protocol
problem (MCP already standardizes the transport) — it is that no shared vocabulary for
*security metadata itself* exists, so identical intent (deny this skill write access to
identity files) is expressible on one platform and inexpressible on another.

**Fires on** a manifest being validated against the Universal Skill Format, a skill moving
between runtimes, a permission finding that needs binding to a specific field's precedence
rule, or an encoded blob in an imported package. **Decides** whether a security-metadata
*field* is missing, malformed, or silently dropped. **Does not decide** whether a present
field's *value* is right for the skill it describes — that is the corresponding AST01–AST09
category, and the two co-occur often enough to be worth recording separately. Frozen
scenario tiers live in `coverage-matrix.md`.

### Run first, then read only what the finding needs

With a manifest in hand, `python3 validators/usf.py <manifest>` mechanizes rules 1–5:
deny_write/write coherence, default-deny egress with the `deny: "*"` spelling, host syntax,
signature and signing-key coherence, and `risk_tier` against the floor derived from the
declared permissions. With a package in hand, `node cli/bin/cli.js audit <pkg>` runs the one
shipped check behind rule 9. Read the rule text when a tool's output is contested, and for
the porting event itself, which no tool observes.

| If the finding is… | Read |
| --- | --- |
| a manifest field's meaning or precedence | rules 1–5, then stop |
| a skill that just changed runtimes | rules 6–8 |
| an encoded blob, or a scanner result on one | rule 9, then "Where the one shipped check goes quiet" |
| "is this AST10 or AST0n?" | "Distinguishing AST10 from its neighbors" |
| a write-up that attributes the Universal Skill Format | "Attribution" — mandatory before you cite it |
| a value that is wrong rather than a field that is absent | wrong skill → the AST01–AST09 category that owns that value |

**Do NOT open `coverage-matrix.md`** unless you need a binding tier, the F1 denominator, or
the off-artifact evidence for one named scenario; five of the six scenarios are
out-of-artifact and this file asserts no tier for them. **Do NOT reach for
`skills/AST10/scripts/detector.py`** for rules 1–5 — it holds only the rule-9 payload check.
The manifest semantics are `validators/usf.py` and the schema is
`schemas/usf-v1.schema.json`.

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

## The rule behind the one shipped check

9. **Silent Supply Chain Injection is the one AST10 scenario a single package decides,
   and the decision is made on the decoded bytes, not on the source.** The whitepaper's
   wording is precise: payloads "hidden inside encoded script blocks ... execute at agent
   speed once imported into a new ecosystem without structural validation", and the
   matching mitigation is to "build platform-agnostic skill scanners that evaluate the
   content layer independently of the runtime". Two consequences follow, and reviewers get
   both wrong in opposite directions. **Encoding is not the finding.** An embedded icon, a
   configuration blob, a compressed policy document, and the format's own hex
   `content_hash` and `signature` fields are all encoded, and flagging them makes a
   scanner unusable on precisely the conformant packages the Universal Skill Format exists
   to produce. **Nor is an unreadable payload a clean one.** When a blob is encrypted or
   triple-wrapped, the decoded content says nothing — but a package that hands an opaque
   literal to an interpreter has skipped the structural validation the scenario names, and
   that structure is itself the finding. Judge the decoded content layer where you can read
   it, and the decode-to-execution path where you cannot.

## Where the one shipped check goes quiet

`detect_encoded_payload_injection` fires on two structural conditions and nothing else:
**C1**, an encoded blob whose decoded text matches a payload-behaviour signature, and
**C2**, an encoded literal whose decoded result reaches an execution sink on the same
line or through a single assignment. Both arms have edges a reviewer inherits.

- **C1 convicts decoded *behaviour*, so a payload the signature set does not describe
  decodes and reads as inert.** The set covers interpreter invocation, destructive
  filesystem operations, credential harvesting, identity-file writes, fetch-and-execute,
  exfiltration, reverse shells and dynamic-execution sinks. A payload expressed outside
  that vocabulary passes C1 and is caught only if it also satisfies C2.
- **C2 follows the decode to a sink across at most one assignment.** Two hops — decode,
  store on an object attribute, execute later — breaks the link, and the package reads
  clean on both arms.
- **The USF integrity-field exclusion is keyed on the line's text, and only for bare
  hex.** Any hex run sharing a line with `content_hash`, `signature`, `digest`,
  `checksum`, `etag`, `uuid` and the rest of that list is skipped regardless of which
  field it actually belongs to; base64 candidates are never excluded this way. The
  exclusion is what makes the scanner usable on conformant packages, and it is also a
  named place to hide a hex blob.
- **The decode is bounded: depth 2, 256 KiB per blob, 400 candidates per file.** Past any
  of those, content is unexamined rather than examined-and-cleared. A deeply nested or
  blob-dense package needs a manual pass, not a re-run.

## Scope and out-of-artifact boundary

Cross-Registry Arbitrage and Multi-Platform Campaign require observing a skill (or its
install-count history) across *multiple registries at once* — no single skill artifact
carries another registry's state. Security Property Loss in Translation needs two
manifests plus the target schema, and Manifest Stripping and Implicit Privilege Escalation
need the pre-port copy and the target platform's defaults respectively. The tier for each,
and the evidence that would decide it, is fixed in `coverage-matrix.md`; this file does not
assert a tier for them.

## References

The full Universal Skill Format proposal (complete field list: identity, signatures,
content hashes, permissions, `deny_write`, network allowlists, required tools, risk
tier, scan status, changelog) and the whitepaper's browser-only metadata-loss
simulator are in the whitepaper's own AST10 section (source: `ast10.md`). This file is
the delta on top of it.
