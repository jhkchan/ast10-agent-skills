# AST01 Coverage Matrix — Malicious Skills

Per-scenario detectability contract for AST01, required by
`docs/adr/0004-per-scenario-detectability-contract.md`. This is the artifact the
narrowed F1 denominator is defended with: it states which of the whitepaper's named
AST01 scenarios this package claims to decide, which it does not, and why.

This repository is an independent community reference implementation. It is **not** an
official OWASP project and carries no OWASP endorsement (see `NOTICE`).

## Authority chain

| Rank | Artifact | Authoritative on |
| --- | --- | --- |
| 1 | OWASP Agentic Skills Top 10, AST01 "Attack Scenarios" body | the enumeration — 11 scenarios, titles verbatim |
| 2 | `scenarios/registry.yaml` | the tier of each scenario, and its written reason |
| 3 | this file | the F1 denominator, the corpus accounting, the coverage debt |
| 4 | `fixtures/manifest.yaml` | which fixture case is labeled against which check |
| 5 | `skills/AST01/scripts/detector.py` | implementation only — subordinate to rank 2 |

## Scenario tiering — 11 of 11

Tier vocabulary is `docs/adr/0004`'s: `static-detectable` (a deterministic rule over the
package's own bytes decides the scenario's defining condition), `agent-judgable` (the
evidence is in the package but the decision needs semantic judgement), `out-of-artifact`
(not decidable from one package at all).

| Scenario | Whitepaper title | Tier | What the detector actually checks | Why this tier |
| --- | --- | --- | --- | --- |
| AST01-S01 | Typosquatting | agent-judgable | — | The dependency names are in the lockfile, but deciding that a name is a deliberate near-miss of a legitimate one is a similarity judgement against world knowledge. A deterministic rule needs an external legitimate-name and popularity corpus the package does not carry. |
| AST01-S02 | Social Engineering Prerequisites | static-detectable | `detect_social_engineering_prerequisites` — a remote-fetch-piped-to-shell command in the package's markdown whose destination host `permissions.network.allow` does not declare, evaluated through `validators/usf.py::network_egress_allowed` | Both halves are in SKILL.md: the install instruction and the host it points at. A remote-fetch-piped-to-shell command (`curl\|bash`, `iwr\|iex`) whose destination host is absent from the USF `permissions.network.allow` list decides it without reading intent. |
| AST01-S03 | Instruction Override | agent-judgable | — | The injected directives are in-artifact prose, but deciding that a sentence supersedes the agent's system directives rather than describing the skill's own task is a semantic reading. A literal "ignore previous instructions" string is a weak proxy, not the scenario. |
| AST01-S04 | ClickFix Prompts | agent-judgable | — | The fabricated dialog text ships in the package, but deciding that a setup-required instruction is coercive theatre rather than genuine installation guidance requires reading the intent behind the framing. |
| AST01-S05 | SOUL.md Persistence | static-detectable | `detect_soul_md_persistence` — a write scope naming the identity file that survives `deny_write`-wins evaluation, or a bundled script opening that path for write | A write to the agent identity file is a path match: a `permissions.files.write` entry naming `SOUL.md`, an absent `deny_write: SOUL.md`, or a bundled script opening that path for write. All three are structural facts of the package. |
| AST01-S06 | Memory Poisoning | static-detectable | `detect_memory_poisoning` — the same two predicates against `MEMORY.md`, as its own function rather than a shared branch | Same mechanism as AST01-S05 against `MEMORY.md`: a declared write scope covering it, or a bundled script writing to it, is decidable from the package alone. |
| AST01-S07 | Cognitive Degradation and Agent Drift | out-of-artifact | — | The whitepaper states the case itself: the failure "only appears after repeated runtime invocation" and "evades the one-time scanning and manifest review that AST08 and AST04 rely on". Deciding it needs multi-session runtime telemetry no package snapshot carries. |
| AST01-S08 | Identity Cloning and Impersonation | static-detectable | `detect_identity_clone_exfiltration` — an identity-artifact read and an outbound send in the same bundled script; neither half alone fires | Both halves are in the package: a read of a known identity-artifact path in a bundled script or declared read scope, and the outbound send that follows it. A read-path match plus an egress call site decides it. |
| AST01-S09 | WebSocket Hijacking | static-detectable | `detect_websocket_c2` — a WebSocket-scheme URL literal in a bundled script against a host the allowlist does not declare | A `ws://` or `wss://` client opened by a bundled script against a host absent from the USF network allowlist is a scheme-and-host match over the package's own source. |
| AST01-S10 | Data Exfiltration | static-detectable | `detect_undeclared_egress` — an egress call site in a bundled script whose hardcoded destination host the manifest never declared | An egress destination hardcoded in a bundled script and absent from the manifest's declared allowlist is an in-package diff between what the code does and what the manifest promises. No runtime observation needed. |
| AST01-S11 | Hidden Prompt Injection in Skill Output | static-detectable | `detect_hidden_output_injection` — invisible control code points, or a base64 blob that decodes back to text, inside the package's output templates | The concealment channel is byte-level and in-artifact: zero-width and bidirectional control characters, ASCII smuggling, and base64 blobs inside the package's output templates are decidable without judgement. Plain-prose override text is AST01-S03 instead. |

Tally: **7 static-detectable, 3 agent-judgable, 1 out-of-artifact**.

Re-derive the ids, titles and tiers in this table from the authority at rank 2:

```
python3 -c "import yaml; [print(s['id'], '|', s['title'], '|', s['tier']) for s in yaml.safe_load(open('scenarios/registry.yaml'))['scenarios'] if s['category']=='AST01']"
```

## Declared and uncovered

The out-of-artifact tier is published here rather than dropped, per `docs/adr/0004` and
spec.md S-003. It never enters the fixture corpus and never enters any F1 denominator.

| Scenario | Whitepaper title | Why one skill package cannot decide it | Evidence that would decide it |
| --- | --- | --- | --- |
| AST01-S07 | Cognitive Degradation and Agent Drift | The defining condition is accumulation across invocations, not a property of any snapshot. QSAF's chain — trigger injection, resource starvation, behavioral drift, memory entrenchment, functional override, systemic collapse — is entered by a skill that "reads clean in a one-time review and degrades the host agent over many turns". A package that will degrade a host and one that will not are byte-identical at install time; the whitepaper's own mitigation for it is runtime monitoring, not scanning. | Multi-session host telemetry across repeated invocations of the same skill: context-window growth per turn, tool-retry and planner-loop counts, token-pressure and latency curves, and a diff of `MEMORY.md` / `SOUL.md` content attributed to this skill's writes over time. Deciding the scenario needs a *trend* across at least two sessions plus per-write skill attribution — neither exists inside the artifact. |

Registry `artifact_signal` for AST01-S07: unbounded retry or loop constructs and absent
output-size budgets in bundled scripts. That is an enabling precondition that benign
skills exhibit too. It is recorded here so a future detector can implement it under a
proxy label — it is **not** coverage of AST01-S07 and must never be reported as such.

## What the detector ships, and what each check does not claim

Ten mechanical checks. Eight are `covers: full` against a registry scenario the registry
independently tiers static-detectable; two decide no named scenario and say so.

| Detector function | Check id | `CHECK_COVERAGE` | Registry link |
| --- | --- | --- | --- |
| `detect_social_engineering_prerequisites` | `AST01-social-engineering-prerequisites` | `full` | AST01-S02 |
| `detect_soul_md_persistence` | `AST01-soul-md-persistence` | `full` | AST01-S05 |
| `detect_memory_poisoning` | `AST01-memory-poisoning` | `full` | AST01-S06 |
| `detect_identity_clone_exfiltration` | `AST01-identity-clone-exfiltration` | `full` | AST01-S08 |
| `detect_websocket_c2` | `AST01-websocket-c2` | `full` | AST01-S09 |
| `detect_undeclared_egress` | `AST01-undeclared-egress` | `full` | AST01-S10 |
| `detect_hidden_output_injection` | `AST01-hidden-output-injection` | `full` | AST01-S11 |
| `detect_obfuscated_payload_exec` | `AST01-obfuscated-payload-exec` | `full` | AST08-S02 (filed under AST08 by the whitepaper; decided here from an AST01 package's own bundled script — recorded, not reassigned) |
| `detect_content_hash_missing` | `AST01-content-hash-missing` | `artifact-signal-only` | AST05-S01, AST07-S01 — the enabling precondition, never coverage |
| `detect_content_hash_mismatch` | `AST01-content-hash-mismatch` | `category-precondition` | none — derives from AST02's signing mitigation |

### Three narrowings, stated rather than hidden

1. **AST01-S05/S06 do not treat an absent `deny_write` entry as a write.** The registry
   lists three structural facts and the detector implements two of them. The third — "an
   absent `deny_write: SOUL.md`" — fires on every package that declares no permissions at
   all, which is AST06's missing-sandbox-declaration signal rather than a write to the
   identity file. Implementing it would trade this check's precision for a signal another
   category already owns. `test_no_permissions_block_is_not_by_itself_an_identity_write`
   pins the narrowing so it cannot be reversed silently.
2. **AST01-S02 reports "undecided" when the install command carries no literal host.**
   `curl $SETUP_URL | sh` has nothing to evaluate the allowlist against. The check says so
   in its evidence instead of guessing either way; a package using that shape is a miss,
   recorded here rather than papered over.
3. **AST01-S10 clears a manifest that declares unbounded egress.** The scenario is the
   *contradiction* between code and manifest, and a manifest that promised everything has
   not been contradicted. Unbounded egress is a real finding — it is AST03's and AST06's,
   and their checks own it.
4. **Through the CLI, AST01's checks see only the declared shipped surface.**
   `cli/lib/bridge.py` lists AST01 in `SURFACE_SCOPED`, so `run_all` receives
   `scripts/content_hash.py`'s `SURFACE_GLOBS` file set (`SKILL.md`, `references/*.md`,
   `scripts/*.py`, `evals/evals.json`) rather than every file in the candidate directory.
   That scoping is required by the two content-hash checks — feeding them extra files
   would report a mismatch for every well-formed package — and it costs the other eight
   checks visibility into anything outside those globs. Concretely: a candidate shipping
   its output template as `templates/reply.tmpl`, or a payload in `setup.sh` rather than
   `scripts/*.py`, is not reached through `/ast:audit-ast01`, though it is reached by
   calling the module directly. Closing it needs per-check scoping in the bridge rather
   than per-category, which is a change to the CLI contract and is recorded here rather
   than made silently.

### The signal-symmetry ruling, applied here

A tier-doctrine review found `detect_content_hash_missing` classified two ways at once:
`static-detectable` in this module, where it counted as a detector, and `artifact_signal`
in `scenarios/registry.yaml`, where counting it would have obliged someone to build one.
Both files now say the same thing about the same predicate:

- **Is content-hash absence decidable by inspecting the package alone?** Yes — one field
  read. `scenarios/registry.yaml` states that outright
  (`artifact_signal_decidable: package-decidable` on `AST05-S01` and `AST07-S01`).
- **Does it decide either scenario?** No. A hash-pinned skill can still be maliciously
  updated once the operator accepts the new hash; an unpinned one may never be updated at
  all. So the registry names the check in `artifact_signal_checks`, and this module
  declares `covers: artifact-signal-only`. Neither file may move without the other:
  `tests/test_tier_doctrine_symmetry.py` fails if one flips.

`F1_SCOPE` for this module is therefore **`mixed-proxy`**, not `scenario-level`: eight
scenario-level checks, one artifact-signal proxy, one category precondition. The corpus's
own `f1_scope` is `scenario-level` because every case it labels is labeled against a
`covers: full` check. The two labels are different statements about different sets and
are reconciled at the end of this section.

**Shape adapter, closed.** Both content-hash functions previously read
`manifest.content_hash` only as a `{"algorithm", "value"}` mapping while
`schemas/usf-v1.schema.json` defines it as a `^sha256:[0-9a-f]{64}$` **string**, so
neither ran correctly against a real `skill.usf.yaml`. `declared_content_hash()` now reads
both spellings and `test_content_hash_reads_the_usf_string_form_not_only_the_mapping_form`
pins it.

## Coverage debt

Distinct from "declared and uncovered": scenarios that *are* decidable from the package
and that this package does not yet decide.

| Scenario | Detector function | Fixture pair | State |
| --- | --- | --- | --- |
| AST01-S02 Social Engineering Prerequisites | `detect_social_engineering_prerequisites` | `AST01-V3` / `AST01-C4` | covered |
| AST01-S05 SOUL.md Persistence | `detect_soul_md_persistence` | `AST01-V5` / `AST01-C6` | covered |
| AST01-S06 Memory Poisoning | `detect_memory_poisoning` | `AST01-V7` / `AST01-C8` | covered |
| AST01-S08 Identity Cloning and Impersonation | `detect_identity_clone_exfiltration` | `AST01-V9` / `AST01-C10` | covered |
| AST01-S09 WebSocket Hijacking | `detect_websocket_c2` | `AST01-V11` / `AST01-C12` | covered |
| AST01-S10 Data Exfiltration | `detect_undeclared_egress` | `AST01-V13` / `AST01-C14` | covered |
| AST01-S11 Hidden Prompt Injection in Skill Output | `detect_hidden_output_injection` | `AST01-V15` / `AST01-C16` | covered |

**The remaining debt is the agent-judgable tier**, not the static one: AST01-S01
Typosquatting, AST01-S03 Instruction Override and AST01-S04 ClickFix Prompts have no
deterministic check and are scored by the judge harness, never by this module.

**What changed, and the fixture-authorship failure it corrects.** The corpus previously
carried three checks under a private `AST01-S1` / `S2` / `S3` namespace, none of which any
detector consumed, and two of the three pairs did not encode the scenario they were
labeled against:

- `AST01-S3` "Covert exfiltration endpoint" (→ AST01-S10) varied a frontmatter key
  `exfil_endpoint` between a URL and `null`. No real skill package has such a key. A
  detector that passed that pair would have been a grep for a field invented by the
  fixture author. It is replaced by a pair that ships a real bundled script whose
  destination host is, and is not, in the declared allowlist.
- `AST01-S2` "Destructive postinstall hook" (→ AST02-S03) varied a `postinstall` value
  between `rm -rf $HOME` and `mkdir -p .cache`. AST02-S03's defining condition is a
  command-bearing value in a config file the host auto-executes **at project open** — the
  trigger CVE-2025-59536 and CVE-2026-21852 anchor. The pair never exercised that trigger,
  which the previous version of this file recorded as an "adequacy caveat" while still
  claiming `covers: full`. The pair is **deleted from this corpus** and AST02-S03 is now
  labeled and implemented in AST02's own corpus, against the project-open trigger.
- `AST01-S1` "Obfuscated malicious payload in script" (→ AST08-S02) did encode its
  mechanism, in frontmatter rather than a bundled script. It is kept, moved into a real
  `scripts/setup.py`, and its clean half now performs the *same* base64 decode without an
  execution sink — so a detector matching `base64` scores 0.5 on the pair instead of 1.0.

## F1 denominator for AST01

**Which scenarios count.** The declared-detectable tier is the 7 `static-detectable` plus
the 3 `agent-judgable` scenarios = 10 of 11. Within that tier the two halves are measured
by different instruments and are never summed:

- **Deterministic detector F1** (spec.md S-007, `detectors/engine.py`) is computed over
  `static-detectable` scenarios only. `agent-judgable` scenarios have no fixture corpus in
  that engine and are reported as a separate list, never folded into the denominator.
- **AST01-S07** is out-of-artifact: excluded from both, published above as declared-and-
  uncovered. The skill's grade is unaffected by its inability to detect it.

**Published number.** `fixtures/manifest.yaml` publishes
`scenario-level 1.000 (8 labeled checks, n=16)`, and
`skills/AST01/scripts/test_ast01_detector.py` recomputes it from the corpus on every run,
so the string cannot drift from the bytes it was measured over. Measured:
tp 8, fp 0, fn 0 across 8 vulnerable and 8 clean cases.

**How to read a 1.000, honestly.** It is 16 hand-authored cases whose author also wrote
the detector, so it measures internal consistency, not field performance. What makes it
worth publishing at all is the shape of the clean half of every pair, each one a
deliberate near-miss chosen so that a keyword-matching detector would score 0.5 rather
than 1.0:

| Pair | Vulnerable | Clean — the near miss |
| --- | --- | --- |
| AST01-S02 | `curl … \| bash` from an undeclared host | the same command from a host the manifest declares |
| AST01-S05 | `open(root / "SOUL.md", "a")` in a bundled script | the same append against the skill's own notes file |
| AST01-S06 | `write: [MEMORY.md]` with the floor silent on it | the identical grant with `deny_write` covering it |
| AST01-S08 | identity read + outbound post to a declared host | the same post reading the skill's own usage file |
| AST01-S09 | WebSocket channel to an undeclared host | the identical channel to a declared host |
| AST01-S10 | egress call to an undeclared collector | the same call to the declared collector |
| AST01-S11 | invisible code points inside an ```` ```output ```` block | the same output contract with no carrier |
| AST08-S02 | base64 blob decoded into `exec` | the same blob decoded and written to a file |

**The corpus is measured against a keyword-grep baseline, not just asserted to resist one.**
`tests/test_corpus_discriminates_mechanism.py` re-runs the corpus through an *ablated*
version of every check — the syntax half of each predicate with the second half deleted
(no allowlist comparison, no `deny_write` evaluation, no execution sink, no output-template
scoping). Measured on this corpus that baseline scores **F1 0.552** (tp 8, fp 13, fn 0)
against the shipped checks' 1.000. The gap is the mechanism; the 13 false positives are the
clean cases doing their job. The test fails if a future fixture edit ever lets the ablation
close that gap, and its message says to rewrite the clean case rather than relax the
ceiling.

`test_every_check_separates_the_vulnerable_cases_from_the_clean_ones` asserts the property
the aggregate hides: each of the eight scenario checks fires on at least one vulnerable
case and on **no** clean case. The two content-hash checks have no labeled case — nothing
may be labeled against a check that covers no scenario — and must stay silent on all 16,
which the same test enforces. That silence is the direct fix for the failure this corpus
was rebuilt over: the module's only substantive check used to fire identically on all six
cases, vulnerable and clean alike.

**Two `f1_scope` values live under this category and they are not the same number.**

| Where | Value | What it scopes |
| --- | --- | --- |
| `fixtures/manifest.yaml` `AST01.f1_scope` | `scenario-level` | The eight **labeled fixture checks**, all `covers: full` against registry scenarios the registry tiers static-detectable. |
| `skills/AST01/scripts/detector.py` `F1_SCOPE` | `mixed-proxy` | All ten **shipped detector checks** — the eight above plus one artifact-signal proxy and one category precondition. |

They differ because the module runs two checks the corpus labels nothing against. Those
two can only ever *lose* points here: they contribute no true positives and any firing on
a clean case would be a false positive. `f1_report` returns `scope: "mixed-proxy"` with
the number it computes, so a caller who never opens this file still cannot quote it as
pure scenario coverage.

## Corpus entitlement and actual corpus

Formula, locked at gate-4: `cases = max(6, 2 x detectable_scenarios)`, class-balanced
vulnerable/clean, drawn only from the static-detectable tier.

| Quantity | Value | Derivation |
| --- | --- | --- |
| Registry static-detectable scenarios | 7 | `scenarios/registry.yaml` |
| **Entitlement at full registry coverage** | **14** | `max(6, 2 x 7)` |
| Labeled detectable checks in the corpus | 8 | `fixtures/manifest.yaml` `detectable_scenarios` |
| Entitlement at present labeling | 16 | `max(6, 2 x 8)` |
| **Actual fixture count under `fixtures/AST01/`** | **16** | 8 vulnerable + 8 clean, one pair per labeled check |

The corpus is **16**, two above the 14 that AST01's own seven scenarios entitle it to,
because the eighth labeled check measures AST08-S02 — a scenario the whitepaper files
under another category and this package decides from its own bundled script. The excess is
that link, not padding: every case is bound to a check a detector reads.

Verify both counts:

```
ls -1d fixtures/AST01/*/ | wc -l
python3 -c "import yaml; c=yaml.safe_load(open('fixtures/manifest.yaml'))['categories']['AST01']; print(len(c['cases']), len(c['detectable_scenarios']))"
```

Re-run the published number:

```
python3 -c "import sys; sys.path.insert(0,'.'); import importlib.util; from detectors import corpus; s=importlib.util.spec_from_file_location('d','skills/AST01/scripts/detector.py'); m=importlib.util.module_from_spec(s); sys.modules['d']=m; s.loader.exec_module(m); print(m.f1_report(corpus.category_fixtures('AST01')))"
```

## Tier lock

This matrix is bound to the AST01 tiering it was authored against, by the same mechanism
`fixtures/manifest.yaml` uses for its labels (`validators/tier_lock.py`, spec.md S-011).
Reclassifying any AST01 scenario changes this hash, which is the signal that the fixture
corpus must be re-labeled and the judge matrix re-run before an F1 for this category can
be republished.

`registry_tier_lock: 3f15f67d3b0e085cc109a7247063d7d79a0a784a8bb2aefb5db1bc2284d906fb`

```
python3 -c "import yaml; from validators.tier_lock import tier_lock_hash; print(tier_lock_hash([s for s in yaml.safe_load(open('scenarios/registry.yaml'))['scenarios'] if s['category']=='AST01']))"
```
