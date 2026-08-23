---
name: ast04-insecure-metadata
description: "Detect and triage OWASP AST04 Insecure Metadata — brand-impersonating skill names, permission-understating manifests, risk_tier spoofing, unsafe YAML/JSON/TOML deserialization in SKILL.md frontmatter or config, and ASCII/zero-width smuggling. Use when validating a skill manifest's parser and schema, when a manifest's declared permissions need cross-checking against observed behavior, when triaging a YAML-load code-execution report, or when deciding whether a config-format finding is YAML, JSON, or TOML shaped (they are not interchangeable)."
---

# AST04 - Insecure Metadata

Pattern: Knowledge. The decision rule that governs this whole category: metadata is
the *only* signal most reviewers and installing agents act on, yet it is
attacker-controlled and deserialized automatically — often silently, with the agent's
full permission context. Mechanism (schema validation, unsafe-tag detection, Unicode
normalization) lives in `scripts/`; frozen scenario tiers live in
`coverage-matrix.md`.

## Why this is not "validate your YAML"

The naive read of AST04 is "sanitize the config parser." The whitepaper's own evidence
narrows that considerably: PyYAML has been `FullLoader`-safe by default since 5.1,
js-yaml safe by default since v4, and Ruby Psych `safe_load`-default since 3.1 — none
of the three major ecosystems execute code on load out of the box anymore. The actual
risk is a skill *loader* that opts back into the legacy unsafe API
(`yaml.UnsafeLoader`, or `FullLoader` on PyYAML pre-5.1). A detector that flags every
`yaml.load()` call as critical without checking which loader class it names will
false-positive on the safe default and miss nothing new; a detector that only checks
for the literal string `!!python/object` misses the more common finding, which is the
loader choice itself.

## Decision rules

1. **The semantic layer and the parsing layer are two independent findings, not one.**
   A field can lie (brand impersonation, permission understating, risk-tier spoofing)
   with zero parser involvement, and a parser can execute code with zero semantic
   deception (a technically honest manifest that still opts into an unsafe loader).
   Score them separately; a clean parsing check does not clear the semantic layer and
   vice versa.
2. **The three declared-format injection shapes are not the same vulnerability class
   and do not share a detector.** YAML's risk is a deserialization *construct*
   (`!!python/object/apply:...`) reachable only through the legacy unsafe loader.
   JSON's risk (`__proto__` prototype pollution) is not `JSON.parse` itself — parsing
   only creates an *own* property — it requires a separate, later unsafe recursive
   merge of the parsed object into a shared config object. TOML has no
   deserialization/code-execution construct at all; its risk is unvalidated key
   overrides injecting unexpected properties into a runner's config namespace when
   precedence rules between sources are not enforced. A single "config injection"
   check that doesn't distinguish these three will misattribute JSON pollution
   findings to a YAML-shaped fix, and will have no test at all for the TOML
   precedence case because there is no payload string to grep for.
3. **`risk_tier` is an untrusted author assertion, not evidence.** A self-declared
   `risk_tier: L0` must be independently validated against the *declared permission
   manifest* it accompanies (does L0/"safe" actually match a manifest with shell
   access and unrestricted network egress?) — treating the tier field as
   authoritative is itself the vulnerability the Risk Tier Spoofing scenario
   describes.
4. **A permission-understating manifest fails structurally, not just at review time.**
   `network: false` declared alongside a script that calls `curl` to an external
   endpoint is only catchable by cross-referencing the manifest against *observed
   runtime behavior* in a sandboxed test — a schema-only validator that checks "is
   `network` a valid boolean" passes this manifest cleanly. The check that closes
   this scenario is behavioral, not syntactic.
5. **ASCII smuggling and zero-width-character payloads are invisible to a human
   reviewer by design, which makes them a parser/normalization requirement, not a
   review-process requirement.** SKILL.md prose that embeds base64 or control
   characters passes casual human inspection precisely because it was authored to.
   Static analysis of metadata fields and prose has to run before any human review
   step, not as a substitute for one that already happened. (The whitepaper's own
   extraction of this document stripped 860 such invisible code points from its
   source PDF — a live instance of the exact signal this scenario describes, not a
   hypothetical.)

## Distinguishing AST04 from its neighbors

- **vs AST01:** AST01's Instruction Override lives in the *prose* the agent reads
  and follows; AST04's YAML/JSON/TOML scenarios require the metadata to be
  *deserialized* by a parser, triggering before any prose is even read as
  instruction. A payload that only fires when the parser processes a specific tag is
  AST04; a payload that fires because the agent read and obeyed sentences is AST01,
  even if both live in the same SKILL.md file.
- **vs AST03 (Over-Privileged Skills):** AST04 is the manifest *misdeclaring* its
  actual permission footprint (Permission Understating); AST03 is the manifest
  *honestly declaring* a footprint broader than the function needs. Same underlying
  risk (excessive access), different root cause and different fix — a schema/behavior
  cross-check fixes AST04; a scope-reduction review fixes AST03.
- **vs AST08 (Poor Scanning):** metadata and deserialization attacks are explicitly
  named in the whitepaper as evading pattern-matching scanners — a missed AST04
  finding due to scanner blindness (no Unicode normalization, no decode-and-rescan
  loop) is an AST08 gap in the tool, not a second AST04 finding on the same skill.

## Scope and out-of-artifact boundary

Brand impersonation (a skill named `google-workspace-integration` with no affiliation
to Google) is checkable against a trademark/brand list at publish time but requires an
external reference corpus this artifact does not carry — whether that makes it
static-detectable-with-a-supplied-list or agent-judgable is fixed in
`coverage-matrix.md`, not decided here.

## References

Full attack-scenario catalog and preventive-mitigation list are the whitepaper's own
AST04 section (source: `ast04.md`). This file is the delta on top of it.
