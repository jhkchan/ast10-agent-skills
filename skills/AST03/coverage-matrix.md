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
| AST03-S01 | Weather Assistant Data Exfiltration | agent-judgable | — (proxy only: `detect_shell_network_privilege_combo` fires on `shell.allowed` and `network.policy == "allow-all"` together, which is breadth, not mismatch) | Both the declared read scope and the stated description are in the package, but the scenario turns on "far beyond what it needs" — a purpose-versus-scope judgement no fixed rule settles. The same read of `~/.clawdbot/.env` is legitimate for a credential-management skill. |
| AST03-S02 | Database Admin Wipe | out-of-artifact | — | The defining event is a runtime trick: an injected instruction arriving in input the package does not contain, acted on by a host runtime that evaluates permissions at the tool-call level. Neither the payload nor the runtime is in the package. |
| AST03-S03 | Identity File Backdoors | static-detectable | partially — `detect_unbounded_write_scope` fires only when `permissions.deny_write` is absent or empty; it does not check identity-file paths | The request is the artifact: a declared write permission naming `SOUL.md`, `MEMORY.md` or `AGENTS.md`, or the absence of the USF `deny_write` entries for them, is a pure structural check on the manifest. |
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

### The one static-detectable scenario is only partially implemented

AST03-S03's defining condition has two halves, and `detect_unbounded_write_scope`
implements neither of them directly. It fires when `permissions.deny_write` is absent or
empty and passes otherwise, reporting `deny_write covers N path(s)`. It never inspects
which paths those are, and it never inspects `permissions.files.write`. Both of the
scenario's own shapes therefore slip past it:

- a manifest declaring `write: ["SOUL.md"]` — the scenario's literal wording, "a skill
  requesting write access to SOUL.md and MEMORY.md" — is not read at all;
- a manifest whose `deny_write` is non-empty but omits the identity files, e.g.
  `deny_write: ["/etc/**"]`, passes on a length check while leaving `SOUL.md` writable.

What the check does decide is a broader, weaker property: no write floor was declared at
all. That is worth keeping, and it is not AST03-S03.

### The detector reads fields the USF v1 schema does not define

`skills/AST03/scripts/detector.py` documents its own package shape as
`manifest.permissions.deny_write`, `manifest.permissions.shell.allowed` and
`manifest.permissions.network.policy`. `schemas/usf-v1.schema.json` — the schema
`docs/adr/0004` says detectors anchor on — defines `permissions.files.deny_write`,
`permissions.shell` as a **boolean**, and `permissions.network.allow` as a domain list
with an optional `deny`. There is no `permissions.deny_write`, no `shell.allowed` and no
`network.policy` anywhere in the schema.

The consequence is not cosmetic. Run the detector over this repository's own AST03
manifest — a package that explicitly denies writes to `SOUL.md`, `MEMORY.md` and
`AGENTS.md`:

```
python3 -c "
import sys, yaml; sys.path.insert(0,'.')
from skills.AST03.scripts import detector as d
m = yaml.safe_load(open('skills/AST03/skill.usf.yaml').read().split('---\n',1)[1])
print(*d.run_all({'manifest': m, 'files': {}}), sep='\n')"
```

`AST03-unbounded-write-scope` reports `detected=True`, evidence
`permissions.deny_write is unset or empty`, against a manifest that declares three
deny_write entries. Every conforming USF manifest is a false positive, and
`AST03-shell-network-privilege-combo` can never fire because `network.policy` is always
`None`. A shape adapter, or a rewrite onto the schema's field paths, is a prerequisite to
any F1 from this detector.

### The fixture corpus is not wired to the detector

`fixtures/AST03/` cases carry their signal in SKILL.md frontmatter keys — `allow_write`,
`shell_exec`, `network_allow` — which match neither the detector's package shape nor the
USF schema. Nothing in the repository loads a fixture file into a detector; the corpus and
the detector were built against different shapes and have never met. `published_f1` for
this category reads `pending-detector` for that reason.

### Two of the three labeled fixture pairs are proxies

`fixtures/manifest.yaml` records this category as `status: proxy-covered`,
`f1_scope: mixed-proxy`:

| Fixture check | Cases | Registry parent | Parent tier | `covers` | What the pair actually varies |
| --- | --- | --- | --- | --- | --- |
| `AST03-S1` Production-secrets write scope | `V1` / `C2` | AST03-S03 Identity File Backdoors | static-detectable | full | `allow_write: ["/secrets/**"]` vs `["./workdir/**"]` |
| `AST03-S2` Undeclared shell-exec permission | `V3` / `C4` | AST03-S01 Weather Assistant Data Exfiltration | agent-judgable | artifact-signal-only | `shell_exec: unrestricted` vs `none`, description held fixed at "formats markdown tables" |
| `AST03-S3` Wildcard network egress | `V5` / `C6` | AST06-S02 Network Pivot | out-of-artifact | artifact-signal-only | `network_allow: ["*"]` vs `["api.example.com"]` |

Two thirds of the corpus measures artifact signals for scenarios the registry does not
tier static-detectable, one of them belonging to AST06. Those four cases may be reported
only under a proxy heading. Adequacy caveat on the one `covers: full` pair: it varies a
production-secrets glob, which generalises AST03-S03's structural check from identity
files to a sensitive-path list; it does not exercise `SOUL.md`, `MEMORY.md` or
`AGENTS.md`, the paths the scenario and the whitepaper's mitigation both name.

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

**Nothing is publishable today**, for the reasons under Coverage debt: the detector reads
field paths the USF schema does not define and reports a false positive on every
conforming manifest, and no code path feeds a fixture into it.

**What must ship with the number when it exists.** Any AST03 F1 has to be published as
two figures, not one:

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

AST03 is the only one of these three categories whose case count matches its entitlement
on both readings — the count is right and the *distribution* is not. Six cases are owed to
AST03-S03; two are bound to it, and four are spent on proxies for scenarios that can never
enter this denominator. Closing the gap means authoring four more AST03-S03 cases
(`SOUL.md` / `MEMORY.md` / `AGENTS.md` write requests, and non-empty `deny_write` lists
that omit them) and moving the existing four proxy cases into a separately reported lane —
not raising the total.

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
