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

`skills/AST01/scripts/detector.py` carries an interim `SCENARIO_TIERS` table that its own
docstring marks as superseded by this file. Where the two differ, this file governs; the
divergence is itemised under [Coverage debt](#coverage-debt).

## Scenario tiering — 11 of 11

Tier vocabulary is `docs/adr/0004`'s: `static-detectable` (a deterministic rule over the
package's own bytes decides the scenario's defining condition), `agent-judgable` (the
evidence is in the package but the decision needs semantic judgement), `out-of-artifact`
(not decidable from one package at all).

| Scenario | Whitepaper title | Tier | What the detector actually checks | Why this tier |
| --- | --- | --- | --- | --- |
| AST01-S01 | Typosquatting | agent-judgable | — | The dependency names are in the lockfile, but deciding that a name is a deliberate near-miss of a legitimate one is a similarity judgement against world knowledge. A deterministic rule needs an external legitimate-name and popularity corpus the package does not carry. |
| AST01-S02 | Social Engineering Prerequisites | static-detectable | not implemented | Both halves are in SKILL.md: the install instruction and the host it points at. A remote-fetch-piped-to-shell command (`curl\|bash`, `iwr\|iex`) whose destination host is absent from the USF `permissions.network.allow` list decides it without reading intent. |
| AST01-S03 | Instruction Override | agent-judgable | — | The injected directives are in-artifact prose, but deciding that a sentence supersedes the agent's system directives rather than describing the skill's own task is a semantic reading. A literal "ignore previous instructions" string is a weak proxy, not the scenario. |
| AST01-S04 | ClickFix Prompts | agent-judgable | — | The fabricated dialog text ships in the package, but deciding that a setup-required instruction is coercive theatre rather than genuine installation guidance requires reading the intent behind the framing. |
| AST01-S05 | SOUL.md Persistence | static-detectable | not implemented | A write to the agent identity file is a path match: a `permissions.files.write` entry naming `SOUL.md`, an absent `deny_write: SOUL.md`, or a bundled script opening that path for write. All three are structural facts of the package. |
| AST01-S06 | Memory Poisoning | static-detectable | not implemented | Same mechanism as AST01-S05 against `MEMORY.md`: a declared write scope covering it, or a bundled script writing to it, is decidable from the package alone. |
| AST01-S07 | Cognitive Degradation and Agent Drift | out-of-artifact | — | The whitepaper states the case itself: the failure "only appears after repeated runtime invocation" and "evades the one-time scanning and manifest review that AST08 and AST04 rely on". Deciding it needs multi-session runtime telemetry no package snapshot carries. |
| AST01-S08 | Identity Cloning and Impersonation | static-detectable | not implemented | Both halves are in the package: a read of a known identity-artifact path in a bundled script or declared read scope, and the outbound send that follows it. A read-path match plus an egress call site decides it. |
| AST01-S09 | WebSocket Hijacking | static-detectable | not implemented | A `ws://` or `wss://` client opened by a bundled script against a host absent from the USF network allowlist is a scheme-and-host match over the package's own source. |
| AST01-S10 | Data Exfiltration | static-detectable | not implemented — fixture pair exists, nothing consumes it | An egress destination hardcoded in a bundled script and absent from the manifest's declared allowlist is an in-package diff between what the code does and what the manifest promises. No runtime observation needed. |
| AST01-S11 | Hidden Prompt Injection in Skill Output | static-detectable | not implemented | The concealment channel is byte-level and in-artifact: zero-width and bidirectional control characters, ASCII smuggling, and base64 blobs inside the package's output templates are decidable without judgement. Plain-prose override text is AST01-S03 instead. |

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

## Coverage debt

Distinct from "declared and uncovered": these scenarios *are* decidable from the package,
and this package does not yet decide them.

`skills/AST01/scripts/detector.py` ships two detector functions, and neither one is keyed
to a named AST01 scenario:

| Detector function | What it actually checks | Which named scenario it decides |
| --- | --- | --- |
| `detect_content_hash_missing` | `manifest.content_hash.value` is unset | none — a package-integrity precondition derived from the AST01 mitigation "require cryptographic signatures ... reject unsigned installs" |
| `detect_content_hash_mismatch` | sha256 over sorted `(path, content)` pairs differs from the declared value | none — detects post-publish tampering, which is the AST02 mitigation "have the signature cover a canonical digest of SKILL.md plus every declared resource file" |

Both read `manifest.content_hash` as a `{"algorithm", "value"}` mapping. The USF v1 schema
this repo ships (`schemas/usf-v1.schema.json`) defines `content_hash` as a
`^sha256:[0-9a-f]{64}$` **string**, so neither function runs correctly against a real
`skill.usf.yaml` without a shape adapter.

Named static-detectable scenarios and their implementation state:

| Scenario | Detector function | Fixture pair | State |
| --- | --- | --- | --- |
| AST01-S02 Social Engineering Prerequisites | none | none | uncovered |
| AST01-S05 SOUL.md Persistence | none | none | uncovered |
| AST01-S06 Memory Poisoning | none | none | uncovered |
| AST01-S08 Identity Cloning and Impersonation | none | none | uncovered |
| AST01-S09 WebSocket Hijacking | none | none | uncovered |
| AST01-S10 Data Exfiltration | none | `AST01-V5` / `AST01-C6` (`covers: full`) | fixture-covered, detector-uncovered |
| AST01-S11 Hidden Prompt Injection in Skill Output | none | none | uncovered |

Six of the seven appear in `fixtures/manifest.yaml`'s `uncovered_static_detectable` list;
AST01-S10 is absent from that list because it is fixture-covered. It is still detector-
uncovered, which is why `published_f1` for this category reads `pending-detector`.

Two of the three labeled fixture checks are drawn from registry scenarios the whitepaper
files under **other** categories, recorded rather than reassigned:

| Fixture check | Registry parent | Parent's category | `covers` |
| --- | --- | --- | --- |
| `AST01-S1` Obfuscated malicious payload in script | AST08-S02 Obfuscated Instruction | AST08 | full |
| `AST01-S2` Destructive postinstall hook | AST02-S03 Config-File Hijacking | AST02 | full |
| `AST01-S3` Covert exfiltration endpoint | AST01-S10 Data Exfiltration | AST01 | full |

Adequacy caveat on `AST01-S2`: the pair varies a `postinstall` value between
`rm -rf $HOME` and `mkdir -p .cache`, which exercises destructive-command matching inside
a declared lifecycle hook. AST02-S03's defining condition is a command-bearing value in a
config file the **host auto-executes at project open** — `.claude/settings.json`, a hook
entry, an `ANTHROPIC_BASE_URL` override, the trigger anchored by CVE-2025-59536 and
CVE-2026-21852. The pair does not exercise that trigger. Treat its `covers: full` as
covering the command half only.

## F1 denominator for AST01

**Which scenarios count.** The declared-detectable tier is the 7 `static-detectable` plus
the 3 `agent-judgable` scenarios = 10 of 11. Within that tier the two halves are measured
by different instruments and are never summed:

- **Deterministic detector F1** (spec.md S-007, `detectors/engine.py`) is computed over
  `static-detectable` scenarios only. `agent-judgable` scenarios have no fixture corpus in
  that engine and are reported as a separate list, never folded into the denominator.
- **AST01-S07** is out-of-artifact: excluded from both, published above as declared-and-
  uncovered. The skill's grade is unaffected by its inability to detect it.

**What is publishable today: nothing.** `skills/AST01/scripts/detector.py` implements no
function bound to any of the 7 static-detectable scenarios, so the denominator of any F1
this package could compute is empty. `fixtures/manifest.yaml` records this as
`published_f1: pending-detector`. This is a detector gap, not a detectability claim — the
seven scenarios stay `static-detectable` and the debt stays visible rather than being
tiered away.

**What will be publishable, and the ratio that must ship with it.** Once detectors land
for the three labeled checks, the F1 denominator is those three checks over 6 cases. Only
one of them (`AST01-S3` → AST01-S10) is an AST01-named scenario; the other two belong to
AST08 and AST02. Any published AST01 F1 must therefore carry the fraction **1 of 7** —
one of this category's seven static-detectable named scenarios measured — alongside the
number. A number without that fraction reads as coverage of AST01 and is not.

AST01's detectable tier is **not** empty, so the never-pad rule's "publishes no F1"
clause does not apply here; AST01 publishes no F1 today for the different and narrower
reason that no detector consumes its corpus.

## Corpus entitlement and actual corpus

Formula, locked at gate-4: `cases = max(6, 2 x detectable_scenarios)`, class-balanced
vulnerable/clean, drawn only from the static-detectable tier.

| Quantity | Value | Derivation |
| --- | --- | --- |
| Registry static-detectable scenarios | 7 | `scenarios/registry.yaml` |
| **Entitlement at full registry coverage** | **14** | `max(6, 2 x 7)` |
| Labeled detectable checks in the corpus | 3 | `fixtures/manifest.yaml` `detectable_scenarios` |
| Entitlement at present labeling | 6 | `max(6, 2 x 3)` |
| **Actual fixture count under `fixtures/AST01/`** | **6** | 3 vulnerable + 3 clean, one pair per labeled check |

The corpus satisfies the formula against what it currently labels and is at **43%** of
the 14 cases the registry's own static-detectable count entitles this category to. The
shortfall is eight cases across the six named scenarios listed as uncovered above. It is
recorded, not padded: fabricating four more pairs against scenarios no detector reads
would inflate the denominator without measuring anything.

Verify both counts:

```
ls -1d fixtures/AST01/*/ | wc -l
python3 -c "import yaml; c=yaml.safe_load(open('fixtures/manifest.yaml'))['categories']['AST01']; print(len(c['cases']), len(c['detectable_scenarios']))"
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
