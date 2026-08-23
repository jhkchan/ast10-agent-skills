# AST08 — Poor Scanning: coverage matrix

Audit artifact for ADR-0004's per-scenario detectability contract. It states, for every
attack scenario the OWASP Agentic Skills Top 10 names under AST08, which tier it sits in,
what `skills/AST08/scripts/detector.py` actually checks for it, and why. It is not a
summary of the whitepaper; read the whitepaper's own AST08 section for the threat
description.

**Authority.** `scenarios/registry.yaml` is authoritative on tier. This file restates that
tiering for AST08 and adds the detector-side and corpus-side facts an auditor needs to
verify it. Where this file and the registry disagree, the registry wins and this file is
the defect.

**Read this first.** AST08 is the category where the contract's two failure modes come
apart. AST07 has nothing to detect and honestly publishes nothing. AST08 has **four**
scenarios the registry tiers static-detectable and ships **zero** detectors for any of
them, while its six labeled fixtures measure a property that is not one of the
whitepaper's eight AST08 scenarios at all. The absence of an F1 here is a **debt**, not an
honesty carve-out, and the sections below say exactly what would pay it off.

**Sources cross-checked when this file was written (2026-08-23).**

| What | Where |
| --- | --- |
| Scenario list, titles, tiers, written reasons | `scenarios/registry.yaml`, entries `AST08-S01`–`AST08-S08` |
| Whitepaper body | OWASP Agentic Skills Top 10, §9 "AST08 - Poor Scanning", pp. 40–45; the eight Attack Scenarios sub-headings run pp. 41–42 |
| Detector | `skills/AST08/scripts/detector.py`, plus the shared scan in `detectors/scaffold.py` |
| Corpus labelling | `fixtures/manifest.yaml`, category `AST08` (`tier_lock_hash: 3a70c4332c9d0794e248baf728cb65715f9e0b6956dab506927f8b8f7d11526b`) |
| Fixture files on disk | `fixtures/AST08/` |
| Sizing and never-pad rules | `features/owasp-ast10-agent-skills/spec.md` gate-4, S-003, S-007 |

### The count is eight, and the whitepaper says seven

AST08's own introductory sentence promises "7 attack scenarios" and its table of contents
lists seven, omitting **Scanner Host Compromise and Resource Exhaustion**. The body carries
it as a full sub-heading between Scanner-Target Evasion and Bytecode Cache Poisoning. The
registry extracts from the body and therefore counts eight — one of the four
TOC-invisible scenarios recorded in ADR-0004's 2026-08-23 amendment, and the only one of
the four that lands in this category. It is tiered `static-detectable`, so the omission is
not cosmetic: reading the TOC instead of the body would have dropped a quarter of AST08's
detectable surface before any detector was written.
`tests/test_scenario_registry.py::test_scenario_counts_match_the_whitepaper_extraction`
pins the count at 8 so it cannot drift back.

## Scenario table

Legend for the detector column:

- `—` — nothing is checked, and nothing should be by this detector: the tier says a single
  package cannot decide the scenario (`out-of-artifact`), or the decision is semantic and
  routed to the judge rather than to a deterministic rule (`agent-judgable`).
- **`nothing shipped`** — the registry tiers this scenario static-detectable, a detector
  *is* owed, and `detector.py` does not contain one.
- A named function — the function in `detector.py` that decides the scenario.

| Scenario id | Whitepaper title | Tier | What the detector actually checks | Written reason for the tier |
| --- | --- | --- | --- | --- |
| `AST08-S01` | Natural-Language Bypass | `agent-judgable` | — | The scenario is defined by the absence of any static signal — that is its whole point. The prose is in the package, so it is in-artifact, but only semantic judgement can decide it. |
| `AST08-S02` | Obfuscated Instruction | `static-detectable` | **`nothing shipped`** | The encoded blob is in the package's bytes. Decoding candidate encodings and re-running the detection rules over the decoded view is deterministic — the whitepaper's own "run every detection rule over the normalized view as well as the raw bytes" mitigation. |
| `AST08-S03` | Scanner Impersonation | `agent-judgable` | — | The self-presentation is prose in the package, and judging that it manufactures unearned trust is semantic. The exfiltration half is separately static (AST01-S10); the impersonation half is not. |
| `AST08-S04` | Context-Dependent Malice | `static-detectable` | **`nothing shipped`** | The logic bomb ships with the package: an environment-keyed guard (hostname, username, date comparison, file-existence probe) wrapping a dangerous branch is a control-flow shape a static rule matches, without ever running the code. |
| `AST08-S05` | Model-Dependent Injection Resistance | `out-of-artifact` | — | The whitepaper is explicit: "The artifact never changed, and every gate still passes ... injection resistance is a behavioral property of the runtime model rather than of the skill's bytes." There is nothing in the package to detect. |
| `AST08-S06` | Scanner-Target Evasion | `out-of-artifact` | — | The defining condition is a property of the adversary's process and of a specific scanner's ruleset — that this artifact was tuned against that scanner. No package can testify to how it was produced. As the whitepaper puts it, a published detection rate is measured against an adversary who does not yet hold the scanner while the deployed one does. |
| `AST08-S07` | Scanner Host Compromise and Resource Exhaustion | `static-detectable` | **`nothing shipped`** | Every listed vector is a measurable property of the files in the package: archive nesting depth, compression ratio, file count, symlink targets escaping the scan root, and non-regular file types. Deterministic limits decide it before any parsing happens. |
| `AST08-S08` | Bytecode Cache Poisoning | `static-detectable` | **`nothing shipped`** | Both the .pyc and the source ship in the package. A sourceless .pyc, or a .pyc whose disassembly does not correspond to its adjacent source, is a source-to-bytecode provenance comparison over package contents. |

Tier totals: **4 static-detectable, 2 agent-judgable, 2 out-of-artifact.** Detector
functions bound to a named scenario: **0 of 4 owed.**

`SKILL.md` promises this file will fix "whether [Model-Dependent Injection Resistance] is
checkable at all from a static skill package". It is not: `AST08-S05` is
`out-of-artifact`, with the whitepaper's own sentence as the reason.

## What the detector does ship, and why it is not in the table

`detector.py` contains exactly one function, registered under the id
`AST08-invisible-unicode-smuggling`:

- **What it checks.** `detect_invisible_unicode_smuggling` delegates to
  `detectors.scaffold.detect_invisible_unicode_smuggling`, which scans every entry of
  `pkg["files"]` plus `pkg["manifest"]["description"]` against
  `INVISIBLE_UNICODE_RE = [\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]` —
  zero-width characters, bidi embedding/override/isolate controls, word joiners, and BOM —
  and returns a `Finding` naming the first file that carries any, with the distinct code
  points as evidence. The same function backs AST04's own smuggling scenario; the two
  categories share the regex and supply only their scenario id. (The class is quoted here
  in `\uXXXX` escapes for the same reason `detectors/scaffold.py` writes it that way:
  pasting the literal glyphs into an audit file would smuggle the exact code points the
  rule exists to catch, invisibly, into a document reviewers read by eye.)
- **Why it is not a row above.** `AST08-invisible-unicode-smuggling` is not one of the
  whitepaper's eight AST08 scenarios. It derives from AST08's preventive mitigations
  ("strip zero-width characters, bidirectional embedding/override/isolate controls
  (U+202A–U+202E, U+2066–U+2069), variation selectors and tag characters ... then
  re-match"), and the mitigation text itself points at AST04 for the attack. It is a real
  check of a real control; it is not coverage of an AST08 scenario, and the table would be
  lying if it appeared there.
- **What it is specifically not.** It is **not** `AST08-S02` Obfuscated Instruction. S02 is
  a payload hidden in an encoded blob — base64 in a comment block — that the model decodes
  at runtime; deciding it requires iterative decode-then-rescan under a depth and size
  bound. The shipped function performs no decoding of any kind. It flags a carrier class
  and stops. Treating a carrier-presence check as coverage of S02 would be the exact error
  the whitepaper names: "Reporting the anomaly is not detecting the payload."

`SCENARIO_TIERS` in the same module carries a second local id,
`AST08-scan-evasion-narrative: agent-judgable`, with no registry counterpart. Its nearest
registry relation is `AST08-S06` Scanner-Target Evasion, which the registry tiers
`out-of-artifact`, not agent-judgable — the module's local tiering is one tier more
optimistic than the registry's. The registry wins; there is no such agent-judgable scenario
in AST08. The module's docstring records that it predates the registry.

**The F1 number that exists in the repo today measures none of this category.**
`skills/AST08/scripts/test_ast08_detector.py::test_s007_f1_at_least_080_on_declared_detectable_tier`
asserts F1 >= 0.80 against six fixtures authored inline in the test file, for
`AST08-invisible-unicode-smuggling`. It is a unit test of the Unicode scan against a corpus
written beside it — not a run over `fixtures/AST08/`, and not a scenario-level AST08
number. It should never be quoted as one.

## Declared and uncovered

The out-of-artifact tier — the scenarios that stay uncovered no matter how many detectors
are written.

### `AST08-S05` — Model-Dependent Injection Resistance

*A skill approved under one backbone model is later executed by a host configured with a
weaker model, on which the identical tool-output injection now succeeds.*

**Why one package cannot decide it.** The whitepaper decides this one itself: "The artifact
never changed, and every gate still passes ... injection resistance is a behavioral
property of the runtime model rather than of the skill's bytes." Two deployments with
identical package hashes, identical signatures and identical scan verdicts differ in
exploitability because of a configuration value held by the host. There is no
in-artifact signal — not even a partial one; the registry sets `artifact_signal: null` —
because the exploitable and non-exploitable cases are byte-identical. This is the sharpest
counterexample in the whole registry to the assumption that a passing gate is a property of
the thing gated.

**Evidence that would decide it.**

1. The identity and version of the backbone model that actually executes the skill at each
   node, resolved at run time rather than at review time — the whitepaper's mitigation is to
   treat that model as "a controlled, re-evaluable security dependency, not a neutral
   interpreter".
2. An injection-resistance measurement for that specific model against a stated evaluation
   suite and version, with a date — a behavioural benchmark result, not a claim.
3. The review-time profile to compare it against: the integrity-protected record tying the
   original verdict to "skill digest, model/version, policy and toolset versions or digests,
   privilege level, evaluation suite/version, date, known limits, and re-test trigger". The
   scenario is decided by *diffing* (1) against (3), which means neither the package nor any
   single scan result can decide it; the pair has to be retained and compared.
4. The privilege level of the node, since the whitepaper scopes the concern to
   "action-taking or otherwise privileged nodes" — the same model swap at a read-only node
   is not the same finding.

**Where this belongs instead.** Nothing here reaches a skill-package detector. It is a
host-side admission-control check: refuse or re-scope execution when the live runtime
profile no longer matches the profile the approval was issued against.

### `AST08-S06` — Scanner-Target Evasion

*Because the scanner is a known static target, an adversary runs it locally and iterates
the skill against its rules and guard prompt offline until it passes.*

**Why one package cannot decide it.** The defining condition is a fact about how the
artifact was *produced* — that someone iterated it against a particular scanner's rules and
guard prompt — and no artifact can testify to its own authoring process. A skill tuned
against SkillSpector and a skill that merely happens to contain none of SkillSpector's
patterns are indistinguishable in the bytes; that indistinguishability is the point of the
tuning. The registry's reason quotes the structural consequence: a published detection rate
is measured against an adversary who does not yet hold the scanner, while the deployed
adversary does.

**Evidence that would decide it.** Nothing decides it outright, and a claim to have decided
it would itself be a scanning failure. What raises or lowers the posterior:

1. Which scanner and which ruleset/guard-prompt version the artifact was submitted to, and
   whether either is public. The scenario is only available to the adversary against a
   scanner they can obtain — SkillSpector is open source and ClawHub's stack is publicly
   described.
2. Submission-side telemetry from the registry: repeated near-miss submissions of the same
   skill from one identity, minimally edited between attempts, is the observable shadow of
   an offline tuning loop — and it lives in the registry's logs, not in the package.
3. A bypass rate measured under white-box or query access to the deployed scanner, per
   `SKILL.md` decision rule 5 and the underlying adaptive-attack result (Carlini and Wagner
   2017; Tramer et al. 2020). This does not decide any individual artifact; it bounds how
   much the scanner's detection rate is worth as evidence about all of them.

**Artifact signal, and why it is emphatically not coverage.** The registry records:
*"Context-padding, unopened archive or binary containers, and scanner-directed prose — each
individually static (AST08-S02, S07, S08) but none evidence that tuning occurred."* This is
the most seductive false-coverage claim in the category. Detecting all three of those
signals is worth doing and is exactly what the four owed detectors below would do — but
finding them proves a payload was hidden, not that the hiding was iterated against a
specific scanner. Reporting "no evasion detected" on their absence would invert the
scenario's own logic: a successfully tuned artifact is precisely the one where they are
absent.

### The two agent-judgable scenarios

`AST08-S01` Natural-Language Bypass and `AST08-S03` Scanner Impersonation are **not** in
the declared-and-uncovered set. Their evidence is in the package — it is prose, and prose
ships — so they are in-artifact; what they lack is a deterministic rule. They are routed to
the judge harness and, per `detectors/engine.py`, are reported separately and never folded
into the F1 denominator. `AST08-S01` in particular cannot be moved to `static-detectable`
by any amount of rule-writing: it is *defined* as the case where no static signal exists,
so a rule that matched it would be matching something else.

## What is owed: the four static-detectable scenarios with no detector

This is AST08's coverage debt, distinct from the declared-and-uncovered set above. Each is
decidable from package bytes; none has a function.
`fixtures/manifest.yaml` lists `AST08-S04`, `AST08-S07`, `AST08-S08` under
`uncovered_static_detectable` and omits `AST08-S02` only because AST01's corpus exercises
S02's shape from its own side (`AST01-S1`, an obfuscated payload pair, links
`registry_ids: [AST08-S02]` at `covers: full`). From *this* package's perspective all four
are unimplemented.

| Scenario | What a detector would have to decide | Why it is deterministic |
| --- | --- | --- |
| `AST08-S02` Obfuscated Instruction | Iteratively decode candidate encodings (base64 and friends) under an explicit depth and size bound, re-run every rule over each decoded layer, and report against the raw artifact with the decoded view retained as evidence. Bound exhaustion is an INCOMPLETE event, never a clean result. | The encoded blob is in the bytes; decoding is a pure function of them. |
| `AST08-S04` Context-Dependent Malice | Match the control-flow shape: an environment-keyed guard — hostname, username, date comparison, file-existence probe — wrapping a dangerous branch. | The logic bomb ships with the package; the shape is visible without executing anything. |
| `AST08-S07` Scanner Host Compromise and Resource Exhaustion | Enforce limits before parsing: archive nesting depth, compression ratio, file count, symlink targets resolving outside the scan root, non-regular file types. | Each is a measurable property of the files as they sit on disk. |
| `AST08-S08` Bytecode Cache Poisoning | Flag a sourceless `.pyc`, and compare a `.pyc`'s disassembly against its adjacent source for divergence. | Both artifacts ship in the package; the comparison is provenance arithmetic over its contents. |

Note that `AST08-S07` is the scenario that attacks the detector itself. A detector for it
must be written to survive its own input — which is why the whitepaper puts the limits
*before* parsing, and why "the scan crashed" and "the scan found nothing" must be different
outcomes.

## F1 denominator for AST08

**Which scenarios count: `AST08-S02`, `AST08-S04`, `AST08-S07`, `AST08-S08` — the
static-detectable tier, four scenarios.**

- `AST08-S01` and `AST08-S03` are excluded: agent-judgable scenarios are scored by the
  judge harness and reported alongside the F1 row, never inside it
  (`detectors/engine.py`, `detectors/f1_reporter.py::CategoryReportRow.agent_judgable`).
  ADR-0004's prose describes the denominator as "static-detectable + agent-judgable"; the
  implemented rule, and spec.md S-007's own Given ("restricted to the subset classified as
  static-detectable in the coverage matrix"), is static-detectable only. The implementation
  is what publishes the number, so it governs — flagged here rather than papered over.
- `AST08-S05` and `AST08-S06` are excluded as `out-of-artifact`, and appear in the
  published breakdown as declared-uncovered rows rather than vanishing from it.

**What AST08 publishes today: no F1.** `fixtures/manifest.yaml` records
`published_f1: pending-detector`, `f1_scope: category-precondition`,
`status: proxy-covered`. That is the correct state, for a reason worth stating precisely:

**AST08 is not entitled to the empty-tier exemption.** gate-4's never-pad rule ("a category
whose detectable tier is empty publishes no F1 at all") is what protects AST07 permanently.
It does not apply here — AST08's detectable tier holds four scenarios. AST08's silence is
therefore temporary and owed, and the four detectors above are what discharge it.

**What must not be published in the meantime.** Feeding the six fixtures currently labeled
for this category into the shipped detector returns
`{"status": "measured", "f1": 0.0, "precision": 0.0, "recall": 0.0, "tp": 0, "fp": 0, "fn": 0}`
— verified by running it. Every counter is zero because the labels (`AST08-S1`) and the
detector's scenario set (`AST08-invisible-unicode-smuggling`) intersect to nothing, so the
0.0 is not a measurement of poor detection; it is the arithmetic of an empty intersection
wearing a `measured` status. Publishing it as AST08's F1 would be worse than publishing
nothing, in both directions: it understates a Unicode scan that does work, and it implies a
corpus/detector pairing that does not exist. The routing rule stands: any number this
category publishes must name the scenario it measures.

`detectors/engine.py` refuses the same pairing outright. Passing an `AST08-S1`-labeled
fixture to `run_category` against a registry-keyed coverage matrix raises
`UnregisteredScenarioFixtureError: fixture(s) reference scenario_id(s) absent from the
coverage matrix for category 'AST08': ['AST08-S1']` (verified) — deliberately loud rather
than silently shrinking the denominator by one case.

## Corpus entitlement versus what is on disk

| Quantity | Value | Where it comes from |
| --- | --- | --- |
| Static-detectable scenarios (registry) | 4 | `scenarios/registry.yaml` |
| Labeled detectable checks (manifest) | 1 | `fixtures/manifest.yaml` `AST08.registry_coverage.labeled_detectable_checks` |
| **Entitlement under `max(6, 2 x labeled)`** | **6** | `max(6, 2 x 1) = 6`; `declared_expected_cases: 6` |
| Entitlement at full registry coverage | 8 | `max(6, 2 x 4) = 8`; `cases_at_full_static_coverage: 8` |
| Cases admitted to the corpus | 6 | `fixtures/manifest.yaml` `AST08.cases` |
| Fixture files present under `fixtures/AST08/` | **6** | `find fixtures/AST08 -type f` |

The count reconciles: six entitled, six labeled, six on disk, three vulnerable
(`V1`, `V2`, `V3`) and three clean (`C4`, `C5`, `C6`), class-balanced as gate-4 requires.
Writing the four owed detectors raises the entitlement from 6 to 8 — `max(6, 2 x 4)` —
and those cases must be authored before this category's F1 may be published. That 8
assumes the scan-attestation precondition check is *replaced*, not kept alongside: the
formula counts labeled checks, so retaining it as a fifth would put the entitlement at
`max(6, 2 x 5) = 10`. The manifest's `cases_at_full_static_coverage: 8` is computed off
the registry's four static-detectable scenarios only and therefore encodes the replace
reading.

**What the six cases actually vary.** All six carry `fixture_scenario_id: AST08-S1`, a
local id, not a registry id — the registry's `AST08-S01` is Natural-Language Bypass, an
unrelated agent-judgable scenario, so the visual near-collision is a trap for a reader
skimming frontmatter. The vulnerable files set `scan_attestation: null`; the clean files set
`scan_attestation: "reports/scan-2026-08-20.json"`. Nothing else differs — the three
vulnerable files are byte-identical to one another, as are the three clean ones. The
manifest declares this honestly as `covers: category-precondition` with a stated
`derivation` from AST08's mitigations ("Require every scan to emit a machine-readable
coverage record...", "Continuously re-scan installed skills as scanner models improve") and
from the Universal Skill Format's `scan_status` field, linking `registry_ids: []`.

Two consequences an auditor should not have to discover on their own:

1. **No detector reads `scan_attestation`.** The only code in the repo that touches scan
   attestation is `validators/usf.py` check 6, which enforces coherence between
   `scan_status.scanner` and `scan_status.result` (an unscanned package must declare
   `scanner: none`) and warns when the field is absent. That is a manifest validator, not an
   AST08 detector, and it is not scored by any F1. The six cases are currently unexercised
   by anything.
2. **Three identical copies do not add statistical power.** Six cases over a single
   binary field, with three duplicates on each side, is one distinguishing observation
   repeated — the corpus satisfies gate-4's count and class balance while carrying roughly
   one case worth of information. If these fixtures are retained when the four real
   detectors land, they should be diversified or replaced rather than counted.

## Changing a tier in this file

The tiering is frozen against the labeled corpus by `fixtures/manifest.yaml`'s
`tier_lock_hash` for AST08
(`3a70c4332c9d0794e248baf728cb65715f9e0b6956dab506927f8b8f7d11526b`), a sha256 over the
sorted `id:tier` pairs (`validators/tier_lock.py`). Moving any AST08 scenario between tiers
changes that hash, which per S-011 forces the corpus back through re-labeling and the judge
matrix back through a re-run before any F1 for this category may be published. The
reclassification most likely to be attempted is `AST08-S06` Scanner-Target Evasion, from
`out-of-artifact` up to `agent-judgable`, on the strength of `detector.py`'s local
`AST08-scan-evasion-narrative` id. Resist it on the merits: a judge reading the package can
assess whether prose looks scanner-directed, but the scenario is defined by an authoring
process that left no trace in the package, so a confident verdict either way would be
unearned.
