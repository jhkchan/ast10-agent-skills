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

## The loader-name trap: why "which loader class does it name" is the wrong question

The tempting shortcut is a safety ladder over PyYAML loader names — `UnsafeLoader` bad,
`FullLoader` fine, `SafeLoader` best. That ladder is wrong, and building a detector on
it produces a confident pass over an RCE-capable call site.

`FullLoader` was introduced in PyYAML 5.1 as the safe-by-default replacement and then
had two documented remote-code-execution bypasses against it — CVE-2020-1747 (fixed in
5.3.1) and CVE-2020-14343 (fixed in 5.4) — both reached through `python/object/new`
constructor paths that `FullLoader` was believed to have closed. PyYAML 6.0 then removed
the implicit default entirely and made the `Loader` argument mandatory, which is the
upstream project's own statement that no default is defensible.

The decision rule that follows is version-independent, and it has to be: a skill package
does not pin the host's PyYAML version, so "safe on 5.4+" is not a property the artifact
can establish about the machine that will load it. **Treat `SafeLoader` / `safe_load` as
the only acceptor. Every other spelling — `UnsafeLoader`, `FullLoader`, a bare
`yaml.load()` with no `Loader=`, or a `Loader=` bound to a name defined elsewhere —
fires.** That is what `detect_yaml_injection` implements, and it is why the check does
not consult loader names as a hierarchy: it looks for the one construct that has never
had an object-construction path, and treats its absence as the finding.

The same reasoning transfers, with different specifics, to the other two runtimes a
skill may target: `js-yaml` and Ruby `Psych` each expose an opt-back-in unsafe API, and
neither is scanned by this package at all (see the quiet list).

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
3. **`risk_tier` spoofing is decided against a *derived floor*, and the comparison is
   deliberately one-directional.** The floor this repository computes from the declared
   permission set (`validators/usf.py::derive_risk_tier`) is: `L0` reads only; `L1` an
   effective non-identity write and/or an allowlisted egress; `L2` shell; `L3` shell
   combined with write, or a granted write to an agent identity file. Only a declared
   tier strictly *below* that floor is the finding — declaring above it is conservative
   and must not fire, or every cautious author gets convicted and the signal dies. Three
   consequences follow that a reviewer has to supply by hand, because the check is
   silent for all three: a manifest with **no** `risk_tier` has nothing to contradict
   (that is metadata completeness, a different finding); a manifest with no permission
   block has no floor to derive; and a `write` entry that `deny_write` fully shadows
   grants no capability, so it correctly does not raise the floor — which means a broad
   write list paired with an equally broad deny list legitimately sits at `L0` and the
   breadth never surfaces here.
4. **A permission-understating manifest is caught by cross-referencing the declaration
   against the bundled code, not by validating the declaration.** `network: false`
   declared alongside a script that calls `curl` to an external endpoint passes a
   schema-only validator cleanly — "is `network` a valid boolean" is satisfied — and
   that is why schema validation is the wrong instrument. But both sides of the
   contradiction ship in the same package: the declared permission in the manifest and
   the egress call site in the bundled script. The closing check is a
   declared-versus-code cross-check over package bytes, which is why
   `coverage-matrix.md` and `scenarios/registry.yaml` both tier `AST04-S02`
   **static-detectable** and why no runtime observation is required to decide it.
   Sandboxed execution buys you breadth — it catches egress the static pass missed,
   through an interpreter, a vendored binary, or a hostname assembled at runtime — but
   it is a superset, not the closing condition. Do not read "a schema check does not
   catch this" as "only a behavioral check catches this"; that inference is what
   downgrades a static scenario into an unimplementable one.
5. **ASCII smuggling and zero-width payloads are invisible to a human reviewer by
   design, so they are a normalization requirement, not a review-process one — and the
   carrier's base rate is too high for its presence to convict.** Prose that embeds
   base64 or control characters passes casual inspection precisely because it was
   authored to. Static normalization must therefore run *before* any human review step,
   never as a substitute for one. But the carrier is also ordinary: measured for this
   project, a plain-text extraction of the whitepaper's own PDF carries 860 code points
   in exactly the class `detectors/scaffold.py` scans for, all of them typesetting
   artifacts. That base rate is why the shared invisible-Unicode scan is declared a
   **category precondition and never scenario coverage** — presence is a prompt to
   decode and re-scan (AST08-S02's job), not a verdict.

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

## Where the shipped checks go quiet

- **The YAML loader scan reads `.py` only.** A skill whose loader is JavaScript
  (`js-yaml` with a full schema) or Ruby (`Psych` with aliases enabled, or
  `YAML.unsafe_load`) has no scanned call site, and the payload half will not save you
  either: the tag scan matches `!!python/…` and `!!ruby/…` and nothing a JS loader
  would need. Read the loader by hand whenever the package ships a non-Python runtime.
- **The `Loader=` decision is made inside a 200-character window after each
  `yaml.load(`.** A safe call whose `Loader=yaml.SafeLoader` sits beyond that window
  (a long multi-line call, a loader chosen above the call) false-positives; an unsafe
  call that happens to have the literal `SafeLoader` within that window — a comment, an
  adjacent safe call, or an import laundered as `from yaml import UnsafeLoader as
  SafeLoader` — clears. The window is a string match, not a resolution of the name; the
  only spellings resolved independently of it are a literal `yaml.unsafe_load(` and a
  literal `Loader=yaml.UnsafeLoader`.
- **`.md` frontmatter is only extracted when the file opens with `---` on the first
  byte.** A leading BOM or blank line yields no frontmatter block and the tag scan sees
  nothing. Body prose is excluded on purpose (this file discusses `!!python/object` and
  must not convict itself), so a payload parked in a fenced block in the body is out of
  scope by design — that is AST08's carrier-and-decode surface, not this one.
- **The prototype-pollution scan reads keys in shipped `.json` only,** and a malformed
  JSON file is skipped silently. The polluting key delivered as a YAML or TOML value, or
  built at runtime, is not seen. The in-package recursive merge is corroborating
  evidence only — its absence is expected, because the exploiting merge usually lives in
  the *host*, and requiring it would miss the common shape of a skill that ships only
  the poisoned manifest.
- **The TOML check decides structure, not meaning.** It fires on a redefined
  single-bracket table (found by text scan before `tomllib`, which raises on
  redefinition and used to swallow the finding) and on top-level keys outside a fixed
  six-name allowlist. A precedence attack expressed entirely *within* expected keys, or
  in an `[[array_of_tables]]`, passes — array tables legitimately repeat.
- **`AST04-S02` needs an egress primitive and an absolute URL on the same source
  line.** A host in a variable, a base URL joined from parts, or an endpoint read from
  the environment yields no site to compare against the allowlist. And a manifest
  declaring unrestricted egress (`allow: ["*"]`) is not understating anything, so the
  check clears by design — that breadth is AST03's finding, and letting it read as an
  AST04 pass is the misread to guard against.

## Scope and out-of-artifact boundary

Brand impersonation (a skill named `google-workspace-integration` with no affiliation
to Google) is checkable against a trademark/brand list at publish time but requires an
external reference corpus this artifact does not carry — whether that makes it
static-detectable-with-a-supplied-list or agent-judgable is fixed in
`coverage-matrix.md`, not decided here.

## References

Full attack-scenario catalog and preventive-mitigation list are the whitepaper's own
AST04 section (source: `ast04.md`). This file is the delta on top of it. The PyYAML CVE
identifiers and the 6.0 mandatory-`Loader` change above are upstream facts, not
whitepaper content, and are stated here because the whitepaper's own framing of loader
safety is not sufficient to build a correct check on.
