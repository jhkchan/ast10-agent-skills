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
scenarios the registry tiers static-detectable, and as of this revision it ships **four**
detector functions — one per scenario, each deciding that scenario's defining condition,
each measured against a labeled vulnerable/clean pair authored for it. The coverage debt
this file used to record is discharged; what replaces it is a number, and a number needs
its own scepticism. Read *What the published 1.0 is, and what it is not* before quoting it.

**Sources cross-checked when this file was written (2026-08-23).**

| What | Where |
| --- | --- |
| Scenario list, titles, tiers, written reasons | `scenarios/registry.yaml`, entries `AST08-S01`–`AST08-S08` |
| Whitepaper body | OWASP Agentic Skills Top 10, §9 "AST08 - Poor Scanning", pp. 40–45; the eight Attack Scenarios sub-headings run pp. 41–42 |
| Detector | `skills/AST08/scripts/detector.py`, plus the shared scan in `detectors/scaffold.py` |
| Corpus labelling | `fixtures/manifest.yaml`, category `AST08` (`tier_lock_hash: 08ea76d31a710007ab28c9d14480159426cd9e98c46f08950ceb22a8aa82dbd3`) |
| Fixture files on disk | `fixtures/AST08/` |
| Sizing and never-pad rules | `features/ast10-agent-skills/spec.md` gate-4, S-003, S-007 |

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

**Authority chain.** The whitepaper's own "Attack Scenarios" body for AST08 outranks
everything here on the enumeration itself — how many scenarios exist, and their titles
verbatim. `scenarios/registry.yaml` is authoritative on tier; this file reproduces its
tiering and may not diverge from it. This file is authoritative on the F1 denominator,
the corpus accounting and the coverage debt. `fixtures/manifest.yaml` is authoritative on
which fixture cases exist and what they are labeled against. The `SCENARIO_TIERS` dict
inside `skills/AST08/scripts/detector.py` is implementation and is subordinate to all of
them.

## Scenario table

Legend for the detector column:

- `—` — nothing is checked, and nothing should be by this detector: the tier says a single
  package cannot decide the scenario (`out-of-artifact`), or the decision is semantic and
  routed to the judge rather than to a deterministic rule (`agent-judgable`).
- **`nothing shipped`** — the registry tiers this scenario static-detectable, a detector
  *is* owed, and `detector.py` does not contain one. No AST08 row reads this any more.
- A named function — the function in `detector.py` that decides the scenario.

| Scenario id | Whitepaper title | Tier | What the detector actually checks | Written reason for the tier |
| --- | --- | --- | --- | --- |
| `AST08-S01` | Natural-Language Bypass | `agent-judgable` | — | The scenario is defined by the absence of any static signal — that is its whole point. The prose is in the package, so it is in-artifact, but only semantic judgement can decide it. |
| `AST08-S02` | Obfuscated Instruction | `static-detectable` | `detect_obfuscated_instruction` — re-runs the rule set over the **normalized view** (invisibles stripped, then NFKC) and over every **decoded layer** of an embedded encoding to depth 4 / 1 MiB, comparing match *counts* per view so a decoy in the clear cannot mask a smuggled occurrence in the same file; fires on a zero-width run that decodes to text; reports bound exhaustion as `INCOMPLETE`. Never fires on carrier presence alone. | The encoded blob is in the package's bytes. Decoding candidate encodings and re-running the detection rules over the decoded view is deterministic — the whitepaper's own "run every detection rule over the normalized view as well as the raw bytes" mitigation. |
| `AST08-S03` | Scanner Impersonation | `agent-judgable` | — | The self-presentation is prose in the package, and judging that it manufactures unearned trust is semantic. The exfiltration half is separately static (AST01-S10); the impersonation half is not. |
| `AST08-S04` | Context-Dependent Malice | `static-detectable` | `detect_context_dependent_malice` — parses each `.py` with `ast` and matches an **environment-identity guard** (hostname, username, uid, env-var equality, date comparison, file-existence probe, debugger probe) whose branch contains a **dangerous call** (exec, subprocess, egress, destruction). OS-portability predicates are excluded from the guard class on purpose. Unparseable sources are recorded `INCOMPLETE`. | The logic bomb ships with the package: an environment-keyed guard (hostname, username, date comparison, file-existence probe) wrapping a dangerous branch is a control-flow shape a static rule matches, without ever running the code. |
| `AST08-S05` | Model-Dependent Injection Resistance | `out-of-artifact` | — | The whitepaper is explicit: "The artifact never changed, and every gate still passes ... injection resistance is a behavioral property of the runtime model rather than of the skill's bytes." There is nothing in the package to detect. |
| `AST08-S06` | Scanner-Target Evasion | `out-of-artifact` | — | The defining condition is a property of the adversary's process and of a specific scanner's ruleset — that this artifact was tuned against that scanner. No package can testify to how it was produced. As the whitepaper puts it, a published detection rate is measured against an adversary who does not yet hold the scanner while the deployed one does. |
| `AST08-S07` | Scanner Host Compromise and Resource Exhaustion | `static-detectable` | `detect_scanner_host_hazard` — enforces declared bounds **before parsing**: `MAX_PACKAGE_FILES` 500, `MAX_FILE_BYTES` 2 MiB, `MAX_PADDING_RUN` 1000, `MAX_ARCHIVE_DEPTH` 1, `MAX_ARCHIVE_MEMBERS` 1000, `MAX_COMPRESSION_RATIO` 100:1, plus zip members escaping the extraction root, symlinks resolving outside the scan root, and non-regular files. Ratios come from the zip central directory; nothing is decompressed. | Every listed vector is a measurable property of the files in the package: archive nesting depth, compression ratio, file count, symlink targets escaping the scan root, and non-regular file types. Deterministic limits decide it before any parsing happens. |
| `AST08-S08` | Bytecode Cache Poisoning | `static-detectable` | `detect_bytecode_cache_poisoning` — source-to-bytecode provenance from the 16-byte PEP 552 header only: a sourceless `.pyc`, an **unchecked** hash-based `.pyc` (flags bit 1 clear), a checked hash-based `.pyc` whose recorded source hash contradicts the adjacent source, or a timestamp-based `.pyc` whose recorded source size does. A truncated header is `INCOMPLETE`-and-detected. The code object is never unmarshalled. | Both the .pyc and the source ship in the package. A sourceless .pyc, or a .pyc whose disassembly does not correspond to its adjacent source, is a source-to-bytecode provenance comparison over package contents. |

Tier totals: **4 static-detectable, 2 agent-judgable, 2 out-of-artifact.** Detector
functions bound to a named scenario: **4 of 4 owed.**

`SKILL.md` promises this file will fix "whether [Model-Dependent Injection Resistance] is
checkable at all from a static skill package". It is not: `AST08-S05` is
`out-of-artifact`, with the whitepaper's own sentence as the reason.

Re-derive the ids, titles and tiers in this table from the authority at rank 2,
so a reader can check the table rather than believe it:

```
python3 -c "import yaml; [print(s['id'], '|', s['title'], '|', s['tier']) for s in yaml.safe_load(open('scenarios/registry.yaml'))['scenarios'] if s['category']=='AST08']"
```

## How each check discriminates, and what it deliberately does not convict

A detector that fires on every package in its own corpus has an F1 of 0.667 and no
information. The four rules below are each a *conjunction* or a *differential*, never a
keyword, and each one's clean fixture carries the same surface feature as its vulnerable
one so that the difference being measured is the scenario and not the vocabulary.

| Check | Fires on | Deliberately does **not** fire on |
| --- | --- | --- |
| `detect_obfuscated_instruction` (S02) | A rule matching a view the raw bytes hid: the normalized view (more matches than raw), a decoded layer, or a zero-width run that decodes to text | A base64 blob that decodes to binary (a PNG, a key, a digest); a shell command written in the clear — nothing was hidden, so this is AST01's question; a bare BOM, whose legitimate use is explained |
| `detect_context_dependent_malice` (S04) | An environment-identity guard **and** a dangerous call inside the guarded branch | An OS-portability branch (`platform.system`, `sys.platform`, `os.name`) around a subprocess call; an env-var read with no dangerous branch; an unconditional subprocess call |
| `detect_scanner_host_hazard` (S07) | A measured bound being exceeded | A single-level archive with an ordinary ratio; a symlink that stays inside the package; a few blank lines |
| `detect_bytecode_cache_poisoning` (S08) | Bytecode whose provenance cannot be tied to shipped source | A checked hash-based `.pyc` whose recorded hash is the hash of the source beside it |

The measured consequence over `fixtures/AST08/` is in *F1 denominator for AST08* below:
each of the four checks scores 1 true positive, 0 false positives, 0 false negatives and
7 true negatives across the eight packages. The 7 matters as much as the 1 — every check
stays silent on the *other three scenarios'* vulnerable packages, not merely on the clean
ones, which is the cross-check a V-versus-C count alone would miss.

## What else the module carries, and why it is not in the table

`detect_invisible_unicode_smuggling` is still defined in `detector.py`, delegating to
`detectors.scaffold`, and is still exercised by two unit tests. It is **not** in
`DETECTORS`, `SCENARIO_TIERS`, or `CHECK_COVERAGE`, so it is not in the F1 denominator and
makes no coverage claim at all.

That is a demotion from its previous status as this category's only shipped check, and the
reason is the whitepaper's own scoping rule: "Report a hidden carrier as a finding in its
own right only where legitimate use does not explain it — scope that signal to constructs
with no plausible authoring path, such as ... a zero-width run that decodes to text." The
unscoped scan flags any code point in the class, a BOM included, which over-reports by that
standard. The *scoped* form of the same signal now lives inside
`detect_obfuscated_instruction`, where the stripped view is re-matched and a zero-width run
is decoded before anything is reported — which is also where the whitepaper puts it, in one
mitigation bullet with decode-and-rescan. Nothing was lost: AST04 keeps the unscoped scan
under its own scenario, which is where the mitigation text points for the attack.

(The character class is quoted throughout this file in `\uXXXX` escapes for the same reason
`detectors/scaffold.py` writes it that way: pasting the literal glyphs into an audit file
would smuggle the exact code points the rule exists to catch, invisibly, into a document
reviewers read by eye.)

`SCENARIO_TIERS` also used to carry a second local id,
`AST08-scan-evasion-narrative: agent-judgable`, with no registry counterpart and one tier
more optimistic than the registry's `out-of-artifact` for its nearest relation
(`AST08-S06`). It is gone: the table is now keyed to the registry's eight ids and restates
the registry's eight tiers, and
`skills/AST08/scripts/test_ast08_detector.py::test_the_registry_is_the_authority_for_every_tier_this_module_declares`
compares the two dictionaries directly so the module cannot acquire a private opinion again.

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
signals is worth doing and is exactly what the three shipped detectors below now do — but
finding them proves a payload was hidden, not that the hiding was iterated against a
specific scanner, and the checks landing has not moved this scenario one inch toward
decidable. Reporting "no evasion detected" on their absence would invert the
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

## What shipped for the four static-detectable scenarios

This section used to be titled "What is owed" and listed four scenarios with no function.
Each row now names the function that decides it and the mechanism it decides it with.

| Scenario | What the detector decides | Why it is deterministic |
| --- | --- | --- |
| `AST08-S02` Obfuscated Instruction | `detect_obfuscated_instruction`: iteratively decodes base64 / base64url / hex candidates under an explicit depth (4) and size (1 MiB) bound, re-runs every rule over each decoded layer, re-runs every rule over the normalized view and compares match counts against the raw bytes, and decodes zero-width runs. Bound exhaustion is an `INCOMPLETE` event, never a clean result. Findings are reported against the raw artifact with the decoded view as evidence. | The encoded blob is in the bytes; decoding is a pure function of them. |
| `AST08-S04` Context-Dependent Malice | `detect_context_dependent_malice`: matches the control-flow shape — an environment-identity guard wrapping a dangerous branch — from the `ast` parse tree. | The logic bomb ships with the package; the shape is visible without executing anything. |
| `AST08-S07` Scanner Host Compromise and Resource Exhaustion | `detect_scanner_host_hazard`: enforces the declared limits before parsing — file count, file size, padding runs, archive nesting depth, member count, declared compression ratio, members escaping the extraction root, symlinks escaping the scan root, non-regular files. | Each is a measurable property of the files as they sit on disk. |
| `AST08-S08` Bytecode Cache Poisoning | `detect_bytecode_cache_poisoning`: flags a sourceless `.pyc`, an unchecked hash-based `.pyc`, and a header whose recorded source hash or size contradicts the adjacent source. | Both artifacts ship in the package; the comparison is provenance arithmetic over its contents. |

`AST08-S07` is the scenario that attacks the detector itself, so two implementation
decisions are load-bearing rather than stylistic and are pinned by tests:

- **Nothing is decompressed.** Compression ratios are read from the zip central directory.
  Measuring a decompression bomb by decompressing it is detonating it.
- **Nothing is unmarshalled.** `AST08-S08` reads the 16-byte PEP 552 header and stops.
  `marshal.loads` on attacker-controlled bytes is a memory-safety hazard, so a scanner that
  unmarshals a package's `.pyc` to inspect it has handed the package the scanner host —
  demonstrating S07's failure while implementing S08's check.
  `test_s08_never_unmarshals_a_shipped_code_object` asserts the module imports neither
  `marshal` nor `pickle`.
- **The loader never follows a symlink.** `load_package_dir` records a link's target and
  whether it resolves outside the scan root, and reads nothing through it. The scan root is
  the thing being escaped, and the walker is the first thing an S07 package attacks.

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

**What AST08 publishes: `f1: 1.00`, scope `scenario-level`, over the eight labeled cases in
`fixtures/AST08/`.** `fixtures/manifest.yaml` records
`published_f1: "scenario-level 1.00 (4 scenario checks, n=8)"`, `f1_scope: scenario-level`,
`status: covered` — the number is published as a qualified string rather than a bare float
so that the scope and the corpus size travel with it into every summary table that quotes
it, including the CLI's and the README's. The measurement, reproduced by
`skills/AST08/scripts/test_ast08_detector.py::test_s007_f1_over_the_labeled_corpus_on_disk`
by loading each package off disk with `load_package_dir`:

| Check | TP | FP | FN | TN |
| --- | --- | --- | --- | --- |
| `AST08-S02` Obfuscated Instruction | 1 | 0 | 0 | 7 |
| `AST08-S04` Context-Dependent Malice | 1 | 0 | 0 | 7 |
| `AST08-S07` Scanner Host Compromise | 1 | 0 | 0 | 7 |
| `AST08-S08` Bytecode Cache Poisoning | 1 | 0 | 0 | 7 |
| **Category** | **4** | **0** | **0** | — |

`test_the_published_f1_in_the_manifest_is_the_measured_one` recomputes the number and
compares it to the manifest, so the published figure cannot drift from the corpus it
claims to come from.

### What the published 1.0 is, and what it is not

This is the strongest claim in this file and it deserves the category's own scepticism
applied to it, because AST08 is precisely the category about scanners that publish numbers.

- **It is measured, not asserted.** It comes from running the four shipped functions over
  eight packages on disk, in a test that fails if either side changes.
- **n = 8, and the corpus was written by the people who wrote the rules.** That is the
  smallest corpus gate-4 permits for four checks, and it is the single most important
  qualifier on the number. AST08's own mitigations demand a false-positive rate measured
  "against a benign corpus of real, widely installed skills", with the corpus's size and
  provenance stated. No such corpus is used here; the eight clean/vulnerable packages are
  hand-authored. **This number is not a false-positive rate.**
- **It is a non-adaptive measurement.** The whitepaper's decision rule 5 and the underlying
  adversarial-ML result (Carlini and Wagner 2017; Tramer et al. 2020) say a detection rate
  measured without an adaptive adversary overstates robustness. No bypass rate under
  white-box access is claimed, and every rule here is published in a public repository, so
  the adversary holds the scanner. Each of the four checks has a knowable evasion: prose
  that carries the payload with no encoding at all (which is `AST08-S01`, agent-judgable by
  construction), a guard predicate outside the listed identity set, an archive format the
  member-name test does not recognise, or bytecode that never ships as a `.pyc`.
- **It says nothing about the other four scenarios.** Two are judged, two are undecidable
  from a package. A category-level "1.0" that a reader takes as "AST08 is covered" would be
  the exact misreading `f1_scope` exists to prevent: the scope label is `scenario-level`
  over four named scenarios, not over the category.

**AST08 is not entitled to the empty-tier exemption.** gate-4's never-pad rule ("a category
whose detectable tier is empty publishes no F1 at all") is what protects AST07 permanently.
It does not apply here — AST08's detectable tier holds four scenarios — which is why the
silence this file used to record was a debt rather than an honesty carve-out, and why
discharging it meant writing detectors rather than re-tiering scenarios.

**The routing rule that still stands.** Any number this category publishes
must name the scenario it measures. The corpus this one replaced was labeled `AST08-S1`, a local id, while
the shipped detector answered to `AST08-invisible-unicode-smuggling`: the two intersected to
nothing, so `f1_report` returned
`{"status": "measured", "f1": 0.0, "precision": 0.0, "recall": 0.0, "tp": 0, "fp": 0, "fn": 0}`
— a 0.0 that measured an empty intersection while wearing a `measured` status. Publishing
that would have been worse than publishing nothing, in both directions.
`detectors/engine.py` refuses the same pairing outright: passing an `AST08-S1`-labeled
fixture to `run_category` against a registry-keyed coverage matrix raises
`UnregisteredScenarioFixtureError` rather than silently shrinking the denominator by one
case, and
`tests/test_coverage_matrix_ast07_ast08.py::test_a_corpus_labeled_with_ids_the_detector_does_not_know_manufactures_a_hollow_zero`
keeps the arithmetic pinned for the next category that gets there.

## Corpus entitlement versus what is on disk

| Quantity | Value | Where it comes from |
| --- | --- | --- |
| Static-detectable scenarios (registry) | 4 | `scenarios/registry.yaml` |
| Labeled detectable checks (manifest) | 4 | `fixtures/manifest.yaml` `AST08.registry_coverage.labeled_detectable_checks` |
| **Entitlement under `max(6, 2 x labeled)`** | **8** | `max(6, 2 x 4) = 8`; `declared_expected_cases: 8` |
| Entitlement at full registry coverage | 8 | `max(6, 2 x 4) = 8`; `cases_at_full_static_coverage: 8` |
| Cases admitted to the corpus | 8 | `fixtures/manifest.yaml` `AST08.cases` |
| Fixture files present under `fixtures/AST08/` | **21** | every file and symlink under `fixtures/AST08/`, not only the Markdown |

Eight entitled, eight labeled, eight packages on disk, four vulnerable (`V1`–`V4`) and four
clean (`C5`–`C8`), class-balanced as gate-4 requires. The two entitlement figures coincide
because the corpus now labels exactly the registry's static-detectable set and nothing else.

**The corpus this replaced, and why replacement rather than re-labeling.** The previous six
cases all carried `fixture_scenario_id: AST08-S1` — a local id, not a registry id; the
registry's `AST08-S01` is Natural-Language Bypass, an unrelated agent-judgable scenario, so
the visual near-collision was a trap for a reader skimming frontmatter. The three vulnerable
files set `scan_attestation: null`, the three clean files set
`scan_attestation: "reports/scan-2026-08-20.json"`, and nothing else differed: the three
vulnerable files were byte-identical to one another, as were the three clean ones. No
detector in the repository read that field — the only code that touches scan attestation is
`validators/usf.py` check 6, a manifest validator that no F1 scores — so six cases over a
single binary field, three duplicates a side, carried roughly one observation and exercised
nothing. Re-labeling could not fix that: the field is a category precondition drawn from
AST08's mitigations, not one of the whitepaper's eight scenarios, so no re-labeling makes it
measure a scenario. It is gone, and the entitlement formula is why it is not kept alongside:
counting it as a fifth labeled check would put the entitlement at `max(6, 2 x 5) = 10` for
one field read.

**What the eight packages vary.** One vulnerable/clean pair per scenario, and each pair's
clean half carries the same surface feature as its vulnerable half so the pair measures the
scenario rather than the vocabulary:

| Case | Package | Encodes |
| --- | --- | --- |
| `AST08-V1` | `fixtures/AST08/V1-obfuscated-instruction` | A payload two base64 layers deep in a comment block, decoding to an agent-directed override plus a credential read and an egress destination |
| `AST08-C5` | `fixtures/AST08/C5-obfuscated-instruction` | The same carriers, no payload: a base64 blob that is a real PNG, and `curl ... \| sh` written in the clear |
| `AST08-V2` | `fixtures/AST08/V2-context-dependent-malice` | `scripts/collect.py` gating a credential-tar-to-`curl` on `socket.gethostname()` and a date comparison |
| `AST08-C6` | `fixtures/AST08/C6-context-dependent-malice` | Both halves separately: a `platform.system()` portability branch, and an unconditional `subprocess.check_output` |
| `AST08-V3` | `fixtures/AST08/V3-scanner-host-hazard` | A 5,000-newline padding run, a real zip whose only member is another zip, and a symlink to `../../../../etc/passwd` |
| `AST08-C7` | `fixtures/AST08/C7-scanner-host-hazard` | A real single-level `.docx` with an ordinary ratio, and a symlink that stays inside the package |
| `AST08-V4` | `fixtures/AST08/V4-bytecode-cache-poisoning` | A sourceless `__pycache__/uploader.cpython-311.pyc`, plus an unchecked hash-based `util` cache beside a `util.py` |
| `AST08-C8` | `fixtures/AST08/C8-bytecode-cache-poisoning` | A checked hash-based `.pyc` whose recorded hash is the hash of the `util.py` shipped beside it |

Two consequences an auditor should not have to discover on their own:

1. **The binary fixtures are verified, not trusted.** A fixture that does not actually
   encode its scenario cannot test a detector, so the corpus is checked structurally by
   `test_the_clean_bytecode_fixture_really_is_a_checked_hash_based_cache`,
   `test_the_vulnerable_bytecode_fixture_really_is_sourceless_and_unchecked`,
   `test_the_scanner_host_fixture_really_carries_a_nested_archive_and_an_escaping_symlink`
   and `test_the_clean_scanner_host_fixture_carries_the_same_features_within_bounds` — PEP
   552 flag bits read directly, zip members enumerated, the symlink's escape recomputed.
2. **`fixtures/AST08/` is exempted from this repository's `.gitignore` for `*.pyc` and
   `__pycache__/`.** That exemption is deliberate and is what makes `AST08-S08` testable at
   all; the two `!` lines in `.gitignore` carry the reason. The clean fixture's `.pyc`
   verifies its recorded source hash only when the header's magic is the running
   interpreter's (the hash is keyed by magic), so on another CPython version that one
   comparison is skipped and reported `INCOMPLETE` rather than failing — the checked flag
   bit, which is what forecloses silent selection, is version-independent and always
   asserted.

## Changing a tier in this file

The tiering is frozen against the labeled corpus by `fixtures/manifest.yaml`'s
`tier_lock_hash` for AST08
(`08ea76d31a710007ab28c9d14480159426cd9e98c46f08950ceb22a8aa82dbd3`), a sha256 over the
sorted `id:tier` pairs (`validators/tier_lock.py`). Moving any AST08 scenario between tiers
changes that hash, which per S-011 forces the corpus back through re-labeling and the judge
matrix back through a re-run before any F1 for this category may be published. The
reclassification most likely to be attempted is `AST08-S06` Scanner-Target Evasion, from
`out-of-artifact` up to `agent-judgable`. Resist it on the merits: a judge reading the
package can assess whether prose looks scanner-directed, but the scenario is defined by an
authoring process that left no trace in the package, so a confident verdict either way would
be unearned. Now that this category publishes a number, the second most likely pressure is
the opposite one — re-tiering a scenario *down* to make a rule's failure disappear. The lock
catches both directions, and the F1 is republished only after the corpus is re-labeled.
