---
name: ast01-malicious-skills
description: "Detect and triage OWASP AST01 Malicious Skills — hidden payloads (credential stealers, backdoors, social-engineering prose) shipped inside an otherwise-legitimate-looking SKILL.md or its dependency tree. Use when reviewing a skill before install, when a previously-clean skill starts behaving differently after repeated invocation (possible cognitive-degradation drift, not a single bad write), when classifying whether a finding is AST01 versus a AST02 supply-chain or AST04 metadata problem, or when deciding what a container sandbox does and does not stop."
---

# AST01 - Malicious Skills

Pattern: Knowledge. Read the orientation block, take a route, then descend only as far as
the route sends you. No mechanism is in this file: the static checks live in
`scripts/detector.py` and the frozen per-scenario tier list in `coverage-matrix.md`.

## Orientation — read this much, then decide whether to read the rest

- **Fires when** you hold a skill package and are asking whether *its own bytes* carry a
  payload: pre-install review, triage of something already found, or a category argument
  against AST02, AST04, AST05 or AST08.
- **Decides** one question, and only that one: does this package contradict its own
  declaration? Nothing here convicts a construct on its own.
- **Never decides** anything that exists only across invocations: drift, degradation,
  climbing retry counts. There the honest verdict is a domain gap, not `clean`.
- **Stop now** if the route below sends you elsewhere. The rest of this file will not
  answer that question and will cost you the context to ask it properly.

### Route first

| If the finding is | Go |
| --- | --- |
| a compromised registry, a hijacked maintainer account, a poisoned nested dependency | **AST02** — stop reading here |
| code execution during *parsing* of the manifest (a legacy YAML loader) | **AST04** — stop reading here |
| a payload in a document the skill only *references*, absent from the shipped package | **AST05** — stop reading here |
| a detector that should have caught this and did not | **AST08** — stop reading here |
| a payload, an install instruction, an identity read or an egress path in this package's own files | this skill — continue below |
| unclear, or it reads like several of these at once | `node cli/bin/cli.js route "<finding text>"` names the primary category and lists contributing control failures separately |

### Then descend only this far

| Section | Read it when |
| --- | --- |
| The predicate shape | you are writing, extending or defending a check — it is why a bare construct match is not a finding |
| Decision rules | always: six rules, and the reason this file exists |
| Distinguishing AST01 from its neighbors | the route above was contested, or one incident spans two categories |
| Where the shipped checks go quiet | **MANDATORY before you report any negative result.** A pass from `scripts/detector.py` is not a clean verdict until you have read it |
| Scope and out-of-artifact boundary | the complaint is degradation-shaped — "it was fine, and now the agent behaves differently" |

**Do NOT load `coverage-matrix.md`** to decide whether something is a finding. It is the
tier contract and the F1 denominator; open it only to cite the authoritative tier of a
named scenario. **Do NOT load `scripts/detector.py`** to learn what the checks decide —
the quiet list below states each scenario check's scope and every silence in prose. Read the
source only for the three checks the quiet list does not cover, because they decide no AST01
scenario: `AST01-content-hash-missing` and `AST01-content-hash-mismatch` are declared
artifact-signal-only and category-precondition respectively, and `AST01-obfuscated-payload-exec`
decides AST08-S02, not an AST01 scenario. Otherwise read the
source only to change it.

## The predicate shape every check here uses, and why the obvious one is unusable

The intuitive AST01 rule is a construct search: does this package contain a
fetch-piped-into-a-shell install line, a WebSocket client, a write to `SOUL.md`, an
outbound `requests.post`. Each of those convicts a large population of legitimate
skills — installers, relay clients, memory-management tools, API integrations — so a
scanner built that way gets switched off inside a week and stops being a control.

Every check in `scripts/detector.py` is therefore a **two-part predicate: a construct,
plus a contradiction of the package's own declaration.** `AST01-S10` is not "a bundled
script calls out"; it is "a bundled script's hardcoded destination host is absent from
the manifest's own `network.allow`". `AST01-S08` is not "a script reads `SOUL.md`"; it
is "one script both reads an identity artifact *and* carries an outbound send" —
either half alone clears. The manifest is not evidence of good behaviour in this
design; it is the *other operand*, and the finding is the distance between two halves
the author shipped together in one package.

Two things follow that reviewers get wrong in opposite directions. A construct with a
matching declaration is **not** a finding here, however alarming it reads. And a
manifest that declares everything cannot be contradicted, so it silences the checks
that depend on it — see the quiet list below before reading any negative result as
"no payload".

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
4. **Runtime accumulation is a different measurement, not a weaker static finding — so
   a clean static pass is not evidence about it.** Every check here decides a
   contradiction wholly present in one snapshot. None can observe a quantity that only
   exists across invocations: retry counts, context growth, how often a skill re-reads
   its own memory file, whether output verbosity is climbing. For a degradation-shaped
   complaint ("this skill was fine, and now the agent behaves differently"), the honest
   output is not `clean` but *no in-artifact contradiction found; the claim is outside
   this instrument's domain*. Two places carry the only durable in-reach trace: a diff
   of the identity artifacts across sessions, and the host's own invocation telemetry.
   Report the static result and the domain gap together, or the pass will be read as an
   acquittal it never was.
5. **A skill's identity-artifact read is worse than its write.** Reading `SOUL.md` /
   `MEMORY.md` / persona/config files lets an attacker clone the agent's *behavioral*
   identity (not just its credentials) for replay or impersonation elsewhere. Because
   agentic identity is contextual, not just cryptographic, a read-only permission
   request against these files still warrants the same elevated review as a write
   request.
6. **Instruction-hierarchy enforcement has to survive skill-to-skill handoffs.** A
   downstream model node that treats a prior skill's *output* as instruction rather
   than as provenance-tagged untrusted data re-triggers this whole category one hop
   later, with the malicious artifact already past install review. Certify the boundary
   at every node that consumes another node's output, not only at the user-to-agent
   edge.

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

## Where the shipped checks go quiet, and what each silence owes a reviewer

**MANDATORY before you report a negative.** A negative result from this package means "no
in-package contradiction of this shape", never "clean". These are the specific silences,
and none of them is recoverable by re-running the scan.

- **An unbounded egress declaration disarms the egress family in one move.** When the
  manifest declares `network: true`, `policy: allow-all`, or `allow: ["*"]`, there is
  nothing left to contradict, so `AST01-S02`, `AST01-S09` and `AST01-S10` all clear
  every host by construction. That breadth is a genuine finding — it is AST03's and
  AST06's — and reading AST01's silence there as "no exfiltration path" is the single
  most common misread of these results. Score the breadth first, then hand the egress
  destinations to manual review.
- **A package with no permissions block at all disarms the declaration half
  everywhere.** The identity checks fall back to the bundled-script scan only, and
  every egress check clears. Frontmatter-only skills (`network: true` and nothing more)
  are the common real-world shape, not an edge case; treat "no manifest" as an
  escalation trigger rather than as a missing input.
- **`AST01-S02` distinguishes *undecided* from *clean*, and only the evidence string
  carries it.** A command with no literal destination host gives the allowlist nothing
  to evaluate, so the check reports negative with `undecided` in its evidence. Any
  pipeline that consumes only the boolean loses that distinction and will report a
  host-parameterised installer as passing.
- **The identity checks are asymmetric on purpose, and the asymmetry is a gap.** The
  write side is keyed to the exact, case-sensitive names `SOUL.md` and `MEMORY.md`; the
  read side (`AST01-S08`) matches a wider family — `SOUL`, `MEMORY`, `AGENTS`,
  `PERSONA`, `IDENTITY` across `.md`, `.json`, `.yaml`. A *write* to `PERSONA.json` or
  `AGENTS.md` is therefore caught by no write check here (the `AGENTS.md` grant is
  AST03's manifest check, a different instrument). Widen by hand whenever a host uses
  non-default identity filenames.
- **Prose and code are read by different checks with different file scopes.** The
  install-instruction check reads markdown only, because an instruction aimed at a
  human lives in prose; the egress, identity and WebSocket checks read script suffixes
  only. Anything that crosses the line — a destination host named only in a README
  while the script builds the URL at runtime, or prose instructing the agent to run a
  bundled helper — is decided by neither and is entirely the reviewer's.
- **The concealment check is scoped to what the skill *returns*, and decodes exactly
  one layer.** `AST01-S11` reads fenced output/template/response blocks, template-suffix
  files, and `templates/`|`output/` paths — concealed content elsewhere in the package
  is AST04/AST08's carrier scan, which decides no scenario. Its base64 arm accepts a
  blob only when one decode yields printable text; a blob that decodes to another
  encoded layer, to gzip, or to non-UTF-8 bytes returns nothing. AST10's check is the
  one that goes deeper — run it before concluding an opaque blob is inert.

## Scope and out-of-artifact boundary

The Cognitive Degradation chain (decision rule 4) and any finding that depends on
*repeated* runtime behavior over multiple sessions cannot be established from a static
read of one skill package — the artifact alone has no session history. Whether this
skill's declared-detectable tier includes any *static precursor signals* (e.g. unbounded
retry loops, verbose-output patterns) versus classifying the full degradation chain as
agent-judgable or out-of-artifact is fixed in `coverage-matrix.md`, not decided here;
do not infer a tier from this prose.

## References — what is loadable, and when

| Resource | Load it when |
| --- | --- |
| `coverage-matrix.md` | you must cite the authoritative tier of a named AST01 scenario, or defend the narrowed F1 denominator |
| `scripts/detector.py` | you are changing a check — never to find out what one decides |
| the whitepaper's own AST01 section | you need the full attack-scenario catalog, the real-world evidence (ClawHavoc campaign, USENIX Security 2026 measurement study, Snyk ToxicSkills), or the complete preventive-mitigation list |

Treat this file as the delta on top of that section, not a restatement of it. This package
ships no `references/` directory: the source it would excerpt is the whitepaper, which is
not redistributable here, so the pointer is to the publication rather than to a local copy
of it.
