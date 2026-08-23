---
artifact: coverage-matrix
category: AST06
category_name: Weak Isolation
version: "1.0"
created: 2026-08-23
task: T-3.1b
tier_authority: scenarios/registry.yaml
corpus_authority: fixtures/manifest.yaml
detector: skills/AST06/scripts/detector.py
tier_lock_hash: "d22946d405b961a25da7194c868288f384bc8035d4555112acd49a5421ae30e3"
registry_scenarios: 5
static_detectable: 1
agent_judgable: 0
out_of_artifact: 4
---

# AST06 — Weak Isolation: coverage matrix

This is the audit artifact `skills/AST06/SKILL.md` points at when it says the
static-detectable / agent-judgable split "is fixed in `coverage-matrix.md`". It is not a
summary of the whitepaper's AST06 section.

The shape of this category: **four of its five named scenarios are properties of a
deployment, not of a package.** AST06 is about the absence of a boundary around the
skill, and a skill package cannot see the boundary it is or is not inside. Exactly one
scenario — Host Escape — is written into the artifact, because the escape is code and
declared scope that ship with the skill.

**Authority chain.** `scenarios/registry.yaml` is authoritative on tier; this file
reproduces its tiering and may not diverge from it. `fixtures/manifest.yaml` is
authoritative on which fixture cases exist. The `SCENARIO_TIERS` dict inside
`skills/AST06/scripts/detector.py` is an interim declaration by its own docstring
("superseded by … T-3.1's authored `skills/AST06/coverage-matrix.md` once locked") —
where it disagrees with this file, this file wins.

## Scenario table

Legend for the detector column:

- A named function means a deterministic check ships and runs for that scenario.
- **partial** means a check ships but decides something narrower than the scenario's
  defining condition; the cell says what the difference is.
- `—` means no deterministic check over the package's own bytes can decide it.

| Scenario | Whitepaper title | Tier | What the detector actually checks | Reason for the tier |
| --- | --- | --- | --- | --- |
| `AST06-S01` | Host Escape | static-detectable | **partial** — `detect_unrestricted_shell_exec()` fires when `manifest.permissions.shell.allowed` is truthy and `shell.commands` is empty or absent. It does **not** scan bundled scripts for a shell-exec call site (`os.system`, `subprocess`) writing to a host persistence location (crontab, systemd unit, shell rc, launch agent), and it does **not** read `permissions.files.write` / `deny_write` for a scope reaching filesystem root — the two halves of the registry's defining condition. | The escape is written into the package: a shell-exec call site targeting host persistence outside the skill's own tree, or a declared write scope reaching `/`. Both are structural facts of the artifact at rest, which is what makes this the one AST06 scenario the package decides itself. What ships is a broader precondition — "shell is granted with no command allowlist" — which flags a superset of packages, including many that never write outside their tree. See [Reconciliation debt](#reconciliation-debt): the check also reads a manifest shape `schemas/usf-v1.schema.json` does not define, and raises `AttributeError` on a conformant manifest. |
| `AST06-S02` | Network Pivot | out-of-artifact | `—` | The scenario turns on the host having no network sandbox and on which services are co-located — deployment facts. The identical package is contained on a sandboxed host and pivots on an unsandboxed one, so nothing in the package separates the two outcomes. |
| `AST06-S03` | Skill Shadowing | out-of-artifact | `—` | Shadowing is a name collision resolved against the host's installed-skill set and its precedence configuration (OpenClaw's workspace > managed > bundled). One package cannot know which name it collides with, or that it wins the collision. The registry records no `artifact_signal`: a legitimate skill and a shadowing one can be byte-identical apart from a name that is only meaningful relative to the host's inventory. |
| `AST06-S04` | Localhost Attack Surface | out-of-artifact | `—` | The exposed surface is the agent host's own control interface — the ClawJacked (CVE-2026-32025) gateway — not any skill package. No skill artifact carries the bind address, the auth policy, or the rate limit that decide it. |
| `AST06-S05` | Cross-Agent Workspace Contamination | out-of-artifact | `—` | Sharing is a deployment topology property: whether two agents are pointed at the same writable workspace, memory, configuration, shell, or browser state is decided outside every package involved. A package can declare that it writes to a path; it cannot know who else writes there. |

## Detector checks that are not whitepaper scenarios

`skills/AST06/scripts/detector.py` declares three scenario ids.

| Detector scenario id | Maps to | Status |
| --- | --- | --- |
| `AST06-unrestricted-shell-exec` | `AST06-S01` (partially) | See the table row above. Verified behaviour on the dict shape it expects: `{"shell": {"allowed": true}}` fires; `{"shell": {"allowed": true, "commands": ["ls"]}}` does not. |
| `AST06-missing-sandbox-declaration` | *no named scenario* | Fires when `manifest.permissions` is absent or empty. A category precondition drawn from AST06's premise that isolation is an architectural default rather than a tunable policy — "sandboxing is available if configured" is evidence *for* the finding. It corresponds to no named scenario and has no fixture pair. It is also the check most likely to produce noise: on any package whose manifest is not loaded, it fires unconditionally. |
| `AST06-cross-skill-data-leak` | closest to `AST06-S05` | Declared `agent-judgable` in `SCENARIO_TIERS` and deliberately absent from `DETECTORS`. The registry tiers the corresponding named scenario **out-of-artifact**, not agent-judgable, because sharing is a deployment fact. Since nothing is implemented, the practical effect is nil — it stays out of `STATIC_DETECTABLE` either way — but the module's tier label disagrees with the registry and this file, and should be reconciled. |

## Declared and uncovered

Four of AST06's five scenarios are out-of-artifact. None enters the fixture corpus
(`detectors/engine.py::run_category` raises `OutOfArtifactFixtureError` if one ever
does). For each: why one package cannot decide it, the enabling precondition the package
*can* show, and the evidence that would actually decide it.

### `AST06-S02` — Network Pivot

- **Why one package cannot decide it.** Two independent deployment facts carry the
  scenario: that the host applies no network sandbox, and that other services with
  harvestable credentials are co-located. Neither is a package property. A skill that
  egresses is contained on a sandboxed host and is a pivot on an unsandboxed one.
- **Enabling precondition the package shows** (`artifact_signal`): a manifest declaring
  `network: true` or a blanket allow policy rather than a domain allowlist — the
  precondition the whitepaper's "domain allowlists, not a binary `network: true/false`"
  posture targets. A partial proxy; never coverage.
- **Evidence that would decide it.** The host's egress policy as enforced (seccomp /
  network namespace / firewall state), the service inventory co-resident with the agent,
  and the credential material reachable from the agent's own context. That is a host
  posture assessment, not a package scan.

### `AST06-S03` — Skill Shadowing

- **Why one package cannot decide it.** The finding is the precedence-plus-hot-reload
  combination, not a defect in any single skill. Deciding it means knowing which skill
  names are already installed at which precedence tier and that this package's name wins
  — three pieces of host state, none of them in the package. The registry records **no**
  `artifact_signal`: there is not even a partial proxy, because the shadowing package
  can be indistinguishable from the legitimate one except by name.
- **Evidence that would decide it.** The host's resolved skill inventory across all three
  precedence tiers, the precedence configuration in force, and hot-reload settings —
  i.e. a name-collision resolution run against the installed set, plus whether a
  confirmation prompt gates a workspace override.

### `AST06-S04` — Localhost Attack Surface

- **Why one package cannot decide it.** The vulnerable object is the agent runtime's own
  control interface. No skill package binds it, authenticates it, or rate-limits it; a
  package installed on a ClawJacked-vulnerable gateway and the same package on a patched
  one are identical.
- **Enabling precondition the package shows** (`artifact_signal`): a bundled script that
  binds a listening socket without authentication. The registry is explicit that this is
  a *related but distinct* exposure from the host control interface the scenario names —
  a skill opening its own port is not the agent gateway being reachable from a browser
  tab.
- **Evidence that would decide it.** The runtime's bind address and port, its
  authentication and origin-check behaviour, and its throttling under repeated attempts
  — observed against a running instance or read from its deployment manifest. That is
  precisely `skills/AST06/SKILL.md` decision rule 3 applied to a deployment, which the
  skill file itself flags as not always recoverable from a static artifact.

### `AST06-S05` — Cross-Agent Workspace Contamination

- **Why one package cannot decide it.** The scenario needs two agents and one shared
  writable location. A package can state where it writes; it cannot state who else reads
  or writes there, nor that the other party later treats the content as trusted without
  re-validation.
- **Enabling precondition the package shows** (`artifact_signal`): declared writes to
  shared workspace, memory, or credential paths with no agent-scoped namespace. This is
  what `fixtures/AST06/{V5,C6}-shared-credential-namespace/` actually measure —
  `covers: artifact-signal-only` in `fixtures/manifest.yaml`, the precondition and not
  the contamination.
- **Evidence that would decide it.** The deployment's state-sharing topology (which
  agents or sessions are pointed at the same writable paths), plus provenance metadata on
  the shared artifacts showing whether a consumer validated before consuming — the
  whitepaper's "preserve provenance and validate artifacts before another agent consumes
  them" control observed in operation.

### Agent-judgable

**None.** AST06 has no agent-judgable scenario: every scenario is either decided by the
package's own structure (`AST06-S01`) or by deployment state no amount of semantic
judgement over the package can recover. The judge harness scores no AST06 scenario. Note
that `skills/AST06/scripts/detector.py` nonetheless labels `AST06-cross-skill-data-leak`
agent-judgable; that label disagrees with the registry and this file, and is listed under
[Reconciliation debt](#reconciliation-debt).

## F1 denominator statement

**Which scenarios count.** Exactly one: `AST06-S01` (Host Escape). It is the only AST06
scenario this file tiers `static-detectable`, and only static-detectable scenarios enter
the denominator — `detectors/engine.py::run_category` scores only `Tier.STATIC_DETECTABLE`
cases, and `detectors/scaffold.py::f1_report` intersects each fixture's expected set with
`STATIC_DETECTABLE` before counting. There are no agent-judgable scenarios to report
separately. The four out-of-artifact scenarios are declared-and-uncovered above and never
appear in the corpus.

AST06 does publish an F1: its detectable tier is non-empty, so the never-pad rule that
silences AST05 and AST09 does not apply.

**The one-scenario denominator has a specific hazard, and it is why
`fixtures/manifest.yaml` marks this category `f1_scope: mixed-proxy`.** Four of the six
fixture cases (`V1`/`C2` filesystem-root write scope, `V3`/`C4` unrestricted sudo) are
labeled `covers: full` against `AST06-S01` and are eligible for the denominator. The
remaining two (`V5`/`C6` shared credential namespace) are labeled
`covers: artifact-signal-only` and proxy `AST06-S05`, which is **out-of-artifact**. Those
two must be excluded from any scenario-level AST06 F1. If the manifest-local check id
`AST06-S3` is fed to the engine as a static-detectable coverage entry rather than resolved
to its out-of-artifact registry parent, a third of the corpus enters the denominator
measuring a precondition and gets reported as scenario coverage. The engine's
`OutOfArtifactFixtureError` guard only fires when the case is keyed by the registry id, so
the id-resolution step is load-bearing, not clerical.

**Publication status.** `published_f1: pending-detector`, and that is accurate. No loader
in this repo converts a fixture `SKILL.md` into the `{"manifest": …, "files": …}` mapping
the detector consumes. Constructed directly as
`{"files": {"SKILL.md": <bytes>}, "manifest": {}}`, `AST06-unrestricted-shell-exec`
returns `detected=False` on all six fixtures and `AST06-missing-sandbox-declaration`
returns `detected=True` on all six — vulnerable and clean alike, because the constructed
package carries no `permissions` block. Neither result discriminates, so the current
corpus carries no measured signal at all. That is a wiring gap, not a detection result.

## Corpus entitlement and actual count

| Quantity | Value | Source |
| --- | --- | --- |
| Registry scenarios in AST06 | 5 | `scenarios/registry.yaml` |
| Registry static-detectable | 1 | `AST06-S01` only |
| Entitlement at full registry coverage — `max(6, 2 × 1)` | **6** | `cases_at_full_static_coverage`; the floor binds, not the multiplier |
| Labeled detectable checks in the corpus | 3 | `AST06-S1`, `AST06-S2` (both `covers: full` → `AST06-S01`), `AST06-S3` (`covers: artifact-signal-only` → `AST06-S05`) |
| Declared expected cases — `max(6, 2 × 3)` | **6** | `declared_expected_cases` |
| Fixture files actually present under `fixtures/AST06/` | **6** | 3 vulnerable + 3 clean, class-balanced |

Both formulas land on 6 and the corpus holds 6, so the count is satisfied twice over and
`uncovered_static_detectable` is empty — AST06 is the only one of these three categories
with no *scenario-level* coverage debt. That is a weaker statement than it sounds: the
category's static tier is a single scenario, four of the six cases attack it from two
angles (declared write scope reaching root, and unrestricted privilege escalation), and
the remaining two measure a precondition for an out-of-artifact scenario. Full formulaic
coverage of a one-scenario tier is not broad coverage of AST06.

Present on disk, all six matching the manifest's declared paths:

```
fixtures/AST06/V1-filesystem-root-write-scope/SKILL.md    vulnerable  -> AST06-S01 (covers: full)
fixtures/AST06/C2-filesystem-root-write-scope/SKILL.md    clean       -> AST06-S01 (covers: full)
fixtures/AST06/V3-unrestricted-sudo/SKILL.md              vulnerable  -> AST06-S01 (covers: full)
fixtures/AST06/C4-unrestricted-sudo/SKILL.md              clean       -> AST06-S01 (covers: full)
fixtures/AST06/V5-shared-credential-namespace/SKILL.md    vulnerable  -> proxy for AST06-S05 (artifact-signal-only)
fixtures/AST06/C6-shared-credential-namespace/SKILL.md    clean       -> proxy for AST06-S05 (artifact-signal-only)
```

## Reconciliation debt

1. **`detect_unrestricted_shell_exec` crashes on a USF-conformant manifest.**
   `schemas/usf-v1.schema.json` declares `permissions.shell` as a **boolean**
   (`validators/usf.py` reads it as `bool(permissions.get("shell"))`). The detector calls
   `shell.get("allowed")` on it, which raises `AttributeError: 'bool' object has no
   attribute 'get'` — verified against a schema-valid permissions block. The check works
   only on a hand-built dict shape the repo's own schema rejects, and `shell.commands`
   does not exist in USF v1 at all.
2. **Neither half of `AST06-S01`'s defining condition is implemented.** No scan of
   bundled scripts for a shell-exec call site writing to host persistence, and no read of
   `permissions.files.write` / `deny_write` for a root-reaching scope — even though the
   corpus's own `V1`/`C2` pair is labeled against exactly that write-scope shape.
3. **`AST06-missing-sandbox-declaration` maps to no named scenario** and fires on any
   package whose manifest is not loaded. It is a category precondition and must not be
   counted as AST06 coverage.
4. **The module tiers `AST06-cross-skill-data-leak` agent-judgable**; the registry tiers
   the corresponding named scenario `AST06-S05` out-of-artifact. Harmless today (nothing
   is implemented), wrong on the label.
5. **No fixture loader**, so `published_f1` stays `pending-detector`.
6. **Two of six cases proxy an out-of-artifact scenario.** They must be resolved to
   `AST06-S05` before the engine sees them, so the guard excludes them, rather than
   entering the denominator under their manifest-local id.

## Change control

The tiering above is bound to `tier_lock_hash`
`d22946d405b961a25da7194c868288f384bc8035d4555112acd49a5421ae30e3`
(`validators/tier_lock.py`). Moving any AST06 scenario between tiers invalidates every
fixture case labeled under the old tier, changes the hash, and requires the corpus to be
re-labeled and the judge run repeated before an F1 may be republished (ADR-0004, S-011).
