# AST03 Coverage Matrix — Over-Privileged Skills

Per-scenario detectability contract for AST03, required by
`docs/adr/0004-per-scenario-detectability-contract.md`. This is the artifact the narrowed
F1 denominator is defended with: it states which of the whitepaper's named AST03
scenarios this package claims to decide, which it does not, and why.

This repository is an independent community reference implementation. It is **not** an
official OWASP project and carries no OWASP endorsement (see `NOTICE`).

AST03's tiering turns on one distinction the category keeps re-posing: a permission
*grant* is in the manifest, and the *exercise* of that grant happens in a runtime this
package never sees. Grants are decidable here. Exercises are not.

## Authority chain

| Rank | Artifact | Authoritative on |
| --- | --- | --- |
| 1 | OWASP Agentic Skills Top 10, AST03 "Attack Scenarios" body | the enumeration — 5 scenarios, titles verbatim |
| 2 | `scenarios/registry.yaml` | the tier of each scenario, and its written reason |
| 3 | this file | the F1 denominator, the corpus accounting, the coverage debt |
| 4 | `fixtures/manifest.yaml` | which fixture case is labeled against which check |
| 5 | `skills/AST03/scripts/detector.py` | implementation only — subordinate to rank 2 |

AST03-S05 "Low-Privilege Skill Invokes a High-Privilege Skill" is one of the four
scenarios the whitepaper's table of contents omits and its body carries; it is counted
here (`docs/adr/0004` Amendment 2026-08-23).

## Scenario tiering — 5 of 5

| Scenario | Whitepaper title | Tier | What the detector actually checks | Why this tier |
| --- | --- | --- | --- | --- |
| AST03-S01 | Weather Assistant Data Exfiltration | agent-judgable | — (proxy only: `detect_shell_network_privilege_combo` fires when a shell grant and an unbounded egress declaration appear together, which is breadth, not mismatch) | Both the declared read scope and the stated description are in the package, but the scenario turns on "far beyond what it needs" — a purpose-versus-scope judgement no fixed rule settles. The same read of `~/.clawdbot/.env` is legitimate for a credential-management skill. |
| AST03-S02 | Database Admin Wipe | out-of-artifact | — | The defining event is a runtime trick: an injected instruction arriving in input the package does not contain, acted on by a host runtime that evaluates permissions at the tool-call level. Neither the payload nor the runtime is in the package. |
| AST03-S03 | Identity File Backdoors | static-detectable | `detect_identity_file_write_grant` — fires when a declared `write` entry reaches `SOUL.md`, `MEMORY.md` or `AGENTS.md` (by name, by a glob matching it at the package root, or by a root-recursive grant such as `./**`) and no `deny_write` entry shadows it, applying USF's most-specific-wins precedence. A scoped recursive grant like `/secrets/**` does not reach them and does not fire. | The request is the artifact: a declared write permission naming `SOUL.md`, `MEMORY.md` or `AGENTS.md`, or the absence of the USF `deny_write` entries for them, is a pure structural check on the manifest. |
| AST03-S04 | Logic-layer Injection of Privileged Actions (LPCI) | out-of-artifact | — | The payload arrives at runtime in input the package never holds, and the escalation depends on the host runtime's permission-evaluation granularity. LAAF validates this by executing against a live runtime, which is precisely what a package snapshot cannot substitute for. |
| AST03-S05 | Low-Privilege Skill Invokes a High-Privilege Skill | out-of-artifact | — | The scenario spans two packages plus the host's inter-skill trust configuration. Nothing in either package alone shows the delegation edge or whether the host verifies the original caller. |

Tally: **1 static-detectable, 1 agent-judgable, 3 out-of-artifact**.

```
python3 -c "import yaml; [print(s['id'], '|', s['title'], '|', s['tier']) for s in yaml.safe_load(open('scenarios/registry.yaml'))['scenarios'] if s['category']=='AST03']"
```

## Declared and uncovered

Three of AST03's five scenarios. Published here rather than dropped, per `docs/adr/0004`
and spec.md S-003; none enters the fixture corpus or any F1 denominator.

| Scenario | Whitepaper title | Why one skill package cannot decide it | Evidence that would decide it |
| --- | --- | --- | --- |
| AST03-S02 | Database Admin Wipe | The manifest can show that `manage_database` holds admin credentials; it cannot show the injected instruction that turns a read task into a wipe, because that instruction arrives at runtime in input the package does not contain. The whitepaper's own control for it — "bind authorization to the task the user approved ... before each action" — is a per-action runtime check, so the gap is between the grant and the task, and only one of those two is in the artifact. | A runtime authorization trace: the task grant the user actually approved, and for each subsequent tool call the action, resource, destination and conditions evaluated against it, with the input provenance that triggered the call. Deciding the scenario requires observing a destructive call that the approved task never covered — an event, not a declaration. |
| AST03-S04 | Logic-layer Injection of Privileged Actions (LPCI) | The payload is planted in memory, a vector store, or another tool's output and treated as an operator-level instruction later; the package holds none of those stores. LPCI's Persistence and Trace Tamper stages are designed specifically to survive or evade a point-in-time review, and the runtime's tool-call-level (rather than intent-level) permission evaluation is a host property. | Execution against a live runtime, which is what LAAF (arXiv:2603.17239) instruments: staged payload delivery across the six-stage lifecycle, the memory/vector-store contents at each stage, the instruction-versus-data provenance tags the runtime applied, and the resulting privileged action with the consent path it did or did not take. A static read of the package cannot substitute for the execution. |
| AST03-S05 | Low-Privilege Skill Invokes a High-Privilege Skill | The scenario is a property of an *edge* between two packages plus the host configuration that decides whether the callee re-verifies the original caller. Read alone, the low-privilege package shows a call it is entitled to make and the high-privilege package shows an operation it is entitled to perform; the confused-deputy condition exists only in their composition. | The host's inter-skill trust configuration and a delegation trace: which skills may invoke which, whether the privileged skill receives and independently validates the *original* caller's identity, permissions and authorization context, and an invocation record showing a privileged operation performed for a caller that could not have requested it directly. Two packages plus the runtime's trust graph — never one package. |

Registry `artifact_signal` values for these three, recorded so a future detector can
implement them under a proxy label and never as coverage:

- AST03-S02: an unscoped administrative credential grant carrying destructive capability
  with no per-action confirmation declared in the manifest.
- AST03-S04: bundled code that routes external input or tool output into a privileged
  action path with no provenance tag or instruction-versus-data boundary.
- AST03-S05: a privileged skill that declares no caller-authorization requirement for
  delegated invocations — visible in one package, insufficient to decide the scenario.

## Coverage debt

### What was closed, and what the closure does not buy

Three defects this file previously recorded are fixed. They are named here rather than
deleted, because a coverage matrix that only ever describes the present state cannot be
audited against its own history.

1. **AST03-S03 had no implementing check.** `detect_unbounded_write_scope` was the only
   write-side check and it never read a path — it fired on `deny_write` being absent or
   empty and passed otherwise, so both of the scenario's shapes slipped past it: a
   manifest declaring `write: ["SOUL.md"]` was not read at all, and a manifest whose
   `deny_write` was non-empty but omitted the identity files passed on a length check
   while leaving `SOUL.md` writable. `detect_identity_file_write_grant` now decides both.
2. **Every check read a field vocabulary the USF schema does not define.** The module
   documented its shape as `permissions.deny_write`, `permissions.shell.allowed` and
   `permissions.network.policy`, none of which appears in `schemas/usf-v1.schema.json`.
   The consequence was concrete: run against this repository's own AST03 manifest — which
   denies writes to `SOUL.md`, `MEMORY.md` and `AGENTS.md` — `AST03-unbounded-write-scope`
   reported `detected=True`. Permission reads now go through
   `detectors/scaffold.py`'s accessors, which understand the USF spelling, the flattened
   spelling `scripts/dogfood.py::translate_permissions` produces, and the bare-boolean
   frontmatter shorthand. `test_identity_write_grant_is_clear_on_this_repositorys_own_ast03_manifest`
   pins the regression.
3. **The fixture corpus was not wired to the detector.** Nothing loaded a fixture into a
   detector. `detectors/fixture_loader.py` now does, reusing `cli/lib/bridge.py`'s
   candidate-package reader rather than adding a third translator.

What the closure does not buy: AST03-S03's scenario-level number rests on **two** cases,
which is below the six-case floor and is stated as under-powered wherever it is published.

### A fixture pair did not encode its scenario, and was rewritten

`fixtures/manifest.yaml` labeled the `AST03-V1`/`AST03-C2` pair `covers: full` against
AST03-S03 on the strength of being "generalised … from identity files to a sensitive-path
list": it varied `allow_write: ["/secrets/**"]` against `["./workdir/**"]` and never
mentioned `SOUL.md`, `MEMORY.md` or `AGENTS.md`. A production-secrets write is a real
over-privilege finding and it is not Identity File Backdoors, so the pair measured
something other than the scenario it was counted against. Both files were rewritten to
request an identity-file write and the directories renamed to
`fixtures/AST03/{V1,C2}-identity-file-write-grant`. The **claim** was wrong, not the tier;
the correction is recorded in the manifest's own `reason` field so it cannot read as a
silent retune.

The other two pairs were rewritten from ad-hoc frontmatter keys (`shell_exec`,
`network_allow`) onto the USF permission block, which is what made them readable by any
detector at all.

### The signal-symmetry ruling, applied here

`skills/AST03/scripts/detector.py` declares, per check, what it does NOT claim:

| Check | `CHECK_COVERAGE` | Ruling |
| --- | --- | --- |
| `AST03-identity-file-write-grant` | `full` → `AST03-S03` | The only check in the module that claims a named scenario. Its predicate *is* the registry's stated defining condition — a declared write reaching an identity file that `deny_write` does not shadow — evaluated over the package's own manifest with nothing read from outside it. |
| `AST03-unbounded-write-scope` | `category-precondition` | Derives from AST03's first preventive mitigation ("require skills to declare a permission manifest … reject skills without one"), not from AST03-S03. It fires only when no write floor is declared at all — no permissions block, or a files block with no `deny_write` key — and is deliberately blind to the content of a declared floor. An explicitly empty `deny_write: []` is a stated floor and does not fire; `schemas/usf-v1.schema.json` requires the key for exactly that reason. |
| `AST03-shell-network-privilege-combo` | `artifact-signal-only` → `AST03-S01`, `AST06-S02` | Its two conjuncts are verbatim the `artifact_signal`s the registry declares on those scenarios — "unrestricted shell … alongside a narrow stated function" and "a manifest declaring `network: true` or `policy: allow-all` rather than a domain allowlist". Both halves are decidable from the package and the registry now says so (`artifact_signal_decidable`); neither decides its scenario, so the check may never be published as coverage. |
| `AST03-wildcard-network-egress` | `artifact-signal-only` → `AST06-S02` | The same signal read alone. AST03's own mitigation asks for the shape it tests ("adopt network allowlists scoped to specific domains, not a binary `network: true/false`"), and the registry tiers AST06-S02 out-of-artifact because the pivot depends on the host's sandbox and co-located services. Precondition, never scenario. |
| `AST03-task-scope-mismatch` | *retired — no function ever shipped* | The module's old fifth id, and the only one with no code behind it. It was a local slug for the AST03-S01 row of the tiering table above: deciding that a permission is broader than the skill's *stated function* means reading the stated function as prose. It is gone from all three tables now that `SCENARIO_TIERS` is keyed by registry ids, because what it recorded is stated there directly and more precisely — `SCENARIO_TIERS["AST03-S01"] == "agent-judgable"`, the registry's own ruling on the scenario it stood in for. That is what the judge harness and `/owasp-ast10:audit-ast03`'s coverage footer now report as not decided by this run. It is not a check, so it has no `CHECK_COVERAGE` entry: listing it there would claim the module computes a predicate it does not compute. It never entered an F1 denominator and still does not. |

`F1_SCOPE` for this module is therefore **`mixed-proxy`**, and `f1_report` returns that
label beside any number it computes. The point of the ruling is that the same predicate
gets the same answer in `scenarios/registry.yaml` and here — a signal is not
package-decidable when that lets a detector claim coverage and out-of-artifact when it
would oblige someone to build one. `tests/test_tier_doctrine_symmetry.py` fails if the two
files diverge.

### Two of the three labeled fixture pairs are still proxies

`fixtures/manifest.yaml` records this category as `status: proxy-covered`,
`f1_scope: mixed-proxy`:

| Fixture check | Cases | Registry parent | Parent tier | `covers` | What the pair actually varies |
| --- | --- | --- | --- | --- | --- |
| `AST03-S1` Identity-file write grant | `V1` / `C2` | AST03-S03 Identity File Backdoors | static-detectable | full | `write: ["SOUL.md","MEMORY.md", …]` with a `deny_write` that omits them, against a non-identity write with all three pinned in `deny_write` |
| `AST03-S2` Unrestricted shell grant alongside unbounded egress | `V3` / `C4` | AST03-S01 Weather Assistant Data Exfiltration | agent-judgable | artifact-signal-only | `shell: true` + `network.allow: ["*"]` against `shell: false` + an enumerated single-host allowlist, description held fixed at "formats markdown tables" |
| `AST03-S3` Wildcard network egress | `V5` / `C6` | AST06-S02 Network Pivot | out-of-artifact | artifact-signal-only | `network.allow: ["*"]` against `["api.example.com"]`, shell closed in both so the conjunctive combo check cannot fire on either |

Two thirds of the corpus measures artifact signals for scenarios the registry does not
tier static-detectable, one of them belonging to AST06. Those four cases may be reported
only under a proxy heading.

One expected cross-fire, stated rather than hidden: `AST03-wildcard-network-egress` also
fires on `AST03-V3`, because that package genuinely declares blanket egress. It is a true
reading of the predicate, not a false positive — each check is scored only over its own
labeled pair, so the two never blend. No check fires on any case labeled clean.

## F1 denominator for AST03

**Which scenarios count.** The declared-detectable tier is 1 static-detectable +
1 agent-judgable = **2 of 5** scenarios (AST03-S03 and AST03-S01). The two halves are
measured by different instruments and are never summed:

- **Deterministic detector F1** (spec.md S-007, `detectors/engine.py`) is computed over
  `static-detectable` scenarios only. For AST03 that denominator is a single scenario,
  **AST03-S03 Identity File Backdoors**, and the only fixture cases bound to it are
  `AST03-V1` / `AST03-C2` — 2 of the 6 cases present.
- **AST03-S01** is agent-judgable: scored by the judge harness, reported separately,
  never folded into the deterministic denominator. `detect_shell_network_privilege_combo`
  and the `AST03-V3` / `AST03-C4` pair address its `artifact_signal`, not the scenario.
- **AST03-S02, S04, S05** are out-of-artifact: excluded from both, published above as
  declared-and-uncovered.

**Measured** (`python3 detectors/fixture_loader.py AST03`):

| Corpus check | Detector check | `covers` | TP | FP | FN | TN | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `AST03-S1` | `AST03-identity-file-write-grant` | full | 1 | 0 | 0 | 1 | 1.00 |
| `AST03-S2` | `AST03-shell-network-privilege-combo` | artifact-signal-only | 1 | 0 | 0 | 1 | 1.00 |
| `AST03-S3` | `AST03-wildcard-network-egress` | artifact-signal-only | 1 | 0 | 0 | 1 | 1.00 |

**Published as two figures, never one.** `fixtures/manifest.yaml` records
`published_f1: "scenario-level 1.00 (AST03-S03, n=2); artifact-signal-only 1.00 (n=4)"`:

1. a scenario-level F1 over AST03-S03, denominator 2 cases — below the 6-case floor, and
   therefore explicitly under-powered;
2. a proxy-level figure over the remaining 4 cases, labeled `artifact-signal-only` and
   naming its parents (AST03-S01 agent-judgable, AST06-S02 out-of-artifact).

Averaging the six cases into one number would report `1 of 5` named-scenario coverage as
though it were category coverage. AST03's detectable tier is not empty, so the never-pad
rule's "publishes no F1" clause does not apply; the discipline it imposes here is
narrower and stricter — publish the scenario-level number over the two cases that earn
it, and keep the proxy cases visible and separate rather than letting them inflate the
denominator.

`AST03-unbounded-write-scope` has no labeled pair at all: it is a category precondition
with no scenario to be scored against, and every fixture in this corpus declares a write
floor, so it fires on none of them. Its true-positive and true-negative behaviour is
covered by unit tests in `skills/AST03/scripts/test_ast03_detector.py`, not by the corpus.

## Corpus entitlement and actual corpus

Formula, locked at gate-4: `cases = max(6, 2 x detectable_scenarios)`, class-balanced,
drawn only from the static-detectable tier.

| Quantity | Value | Derivation |
| --- | --- | --- |
| Registry static-detectable scenarios | 1 | `scenarios/registry.yaml` (AST03-S03) |
| **Entitlement at full registry coverage** | **6** | `max(6, 2 x 1)` |
| Labeled detectable checks in the corpus | 3 | `fixtures/manifest.yaml` `detectable_scenarios` |
| Entitlement at present labeling | 6 | `max(6, 2 x 3)` |
| **Actual fixture count under `fixtures/AST03/`** | **6** | 3 vulnerable + 3 clean, one pair per labeled check |
| Cases bound to a `covers: full` scenario | 2 | `AST03-V1` / `AST03-C2` |

AST03's case count matches its entitlement on both readings — the count is right and the
*distribution* is not. Six cases are owed to AST03-S03; two are bound to it, and four are
spent on proxies for scenarios that can never enter this denominator. Closing the gap
means authoring four more AST03-S03 cases as their own labeled checks (a `MEMORY.md`
grant, an `AGENTS.md` grant, a root-recursive `./**` grant, a grant fully shadowed by
`deny_write`) and moving the existing four proxy cases into a separately reported lane —
which under the locked formula raises the entitlement rather than redistributing within
it, and is therefore a corpus-growth decision rather than a relabeling.

```
ls -1d fixtures/AST03/*/ | wc -l
python3 -c "import yaml; c=yaml.safe_load(open('fixtures/manifest.yaml'))['categories']['AST03']; print(len(c['cases']), len(c['detectable_scenarios']), c['status'], c['f1_scope'])"
```

## Tier lock

`registry_tier_lock: e54b26ff23820840a724cc4ac9db658c8cadb92422b3c3eee06d05138c7ce59d`

```
python3 -c "import yaml; from validators.tier_lock import tier_lock_hash; print(tier_lock_hash([s for s in yaml.safe_load(open('scenarios/registry.yaml'))['scenarios'] if s['category']=='AST03']))"
```

Reclassifying any AST03 scenario changes this hash, which is the signal that the corpus
must be re-labeled and the judge matrix re-run before an F1 for this category can be
published (spec.md S-011, `validators/tier_lock.py`).
