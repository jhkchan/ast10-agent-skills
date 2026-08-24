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
publishes_scenario_level_f1: true
published_f1: "scenario-level 1.00 (AST06-S01, n=4); artifact-signal-only 1.00 (n=2)"
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
`skills/AST06/scripts/detector.py` restates that registry tiering verbatim, keyed by the
same canonical scenario ids — all five of them, `AST06-S01` static-detectable and the
other four out-of-artifact — and says nothing whatever about any individual check. Per-check
metadata lives in the same module's `CHECK_COVERAGE`; where any of the three disagrees with
`scenarios/registry.yaml`, the registry wins.

## Scenario table

Legend for the detector column:

- A named function means a deterministic check ships and runs for that scenario.
- **partial** means a check ships but decides something narrower than the scenario's
  defining condition; the cell says what the difference is.
- `—` means no deterministic check over the package's own bytes can decide it.

| Scenario | Whitepaper title | Tier | What the detector actually checks | Reason for the tier |
| --- | --- | --- | --- | --- |
| `AST06-S01` | Host Escape | static-detectable | `detect_host_persistence_write()` parses each bundled `.py` file and fires when a shell-exec call site (`os.system`, `os.popen`, `subprocess.run/call/check_call/check_output/Popen`) or a write call site (`open(..., "w"/"a")`, `Path.write_text`, `shutil.copy`, `os.symlink`) targets a host persistence location outside the skill's own tree — cron table or `/etc/cron.d`, systemd unit or `systemctl enable`, launchd directory or `launchctl load`, shell rc file, `/etc/rc.local`, `~/.ssh/authorized_keys`, a Windows Run key. `detect_root_write_scope()` reads the declared write policy and fires when an *effective* write entry (one `deny_write` does not shadow, evaluated through `validators/usf.py`'s own `write_allowed`) reaches filesystem root or names a host persistence path. | The escape is written into the package: a shell-exec call site targeting host persistence outside the skill's own tree, **or** a declared write scope reaching `/`. Both are structural facts of the artifact at rest, which is what makes this the one AST06 scenario the package decides itself. The registry states the condition as a disjunction and the two checks implement one disjunct each, so together they decide it as written. They match `ast.Call` nodes, never source text: a path named in a docstring, a comment, or a constant table is describing the location, not writing to it, and every detector in this repository does exactly that. |
| `AST06-S02` | Network Pivot | out-of-artifact | `—` | The scenario turns on the host having no network sandbox and on which services are co-located — deployment facts. The identical package is contained on a sandboxed host and pivots on an unsandboxed one, so nothing in the package separates the two outcomes. |
| `AST06-S03` | Skill Shadowing | out-of-artifact | `—` | Shadowing is a name collision resolved against the host's installed-skill set and its precedence configuration (OpenClaw's workspace > managed > bundled). One package cannot know which name it collides with, or that it wins the collision. The registry records no `artifact_signal`: a legitimate skill and a shadowing one can be byte-identical apart from a name that is only meaningful relative to the host's inventory. |
| `AST06-S04` | Localhost Attack Surface | out-of-artifact | `—` | The exposed surface is the agent host's own control interface — the ClawJacked (CVE-2026-32025) gateway — not any skill package. No skill artifact carries the bind address, the auth policy, or the rate limit that decide it. |
| `AST06-S05` | Cross-Agent Workspace Contamination | out-of-artifact | `—` | Sharing is a deployment topology property: whether two agents are pointed at the same writable workspace, memory, configuration, shell, or browser state is decided outside every package involved. A package can declare that it writes to a path; it cannot know who else writes there. |

Re-derive the ids, titles and tiers in this table from the authority at rank 2,
so a reader can check the table rather than believe it:

```
python3 -c "import yaml; [print(s['id'], '|', s['title'], '|', s['tier']) for s in yaml.safe_load(open('scenarios/registry.yaml'))['scenarios'] if s['category']=='AST06']"
```

## Detector checks and what each one claims

`skills/AST06/scripts/detector.py` declares six scenario ids: five implemented checks
and one that is deliberately not implemented.

| Detector scenario id | Maps to | Status |
| --- | --- | --- |
| `AST06-host-persistence-write` | `AST06-S01` (`covers: full`) | The first disjunct of the registry's defining condition, verbatim. See the table row above. The whitepaper's scenario text is "malicious skill executes `os.system()` to plant a cron job on the host, persisting beyond skill uninstall"; this matches that call site, not a capability that would merely permit it. |
| `AST06-root-write-scope` | `AST06-S01` (`covers: full`) | The second disjunct. Effective scope only: an entry `deny_write` fully shadows grants no capability and is not reported, evaluated through `validators/usf.py::write_allowed` so "deny_write always wins over write" means the same thing in the validator and in the detector. Reads both the USF-nested `permissions.files.write` and the flat translated `permissions.write`. |
| `AST06-unrestricted-shell-exec` | no named scenario (`covers: category-precondition`) | Shell granted with nothing bounding it — a wildcard entry such as `sudo *` does not bound. Derived from AST06's premise that isolation is an architectural default and from its "implement per-skill process isolation" mitigation, **not** from AST06-S01: a granted shell is a capability and the scenario's defining condition is an act. It flags a superset of packages, so it may not claim coverage of a named scenario. |
| `AST06-unscoped-shared-state-write` | `AST06-S05`'s `artifact_signal` (`covers: artifact-signal-only`) | Computes that scenario's declared signal verbatim — "declared writes to shared workspace, memory, or credential paths with no agent-scoped namespace". Fires on an effective write to an identity/memory file, a credential store (`~/.aws/credentials`, `~/.netrc`, `.env`), a shared workspace root, or a shared agent-memory directory, unless the path carries an `agents/<id>/` or `sessions/<id>/` segment. Never coverage: whether a second agent is pointed at the same state, and whether it later treats the content as trusted, are deployment facts. |
| `AST06-missing-sandbox-declaration` | `AST10-S04`'s `artifact_signal` (`covers: artifact-signal-only`) | Fires when `manifest.permissions` is absent or empty. `scenarios/registry.yaml` names *this check by name* as the reader of AST10-S04 Manifest Stripping's `artifact_signal`, and records `artifact_signal_decidable: package-decidable`. It cannot decide AST10-S04: without the pre-port manifest, a ported package with no permission block is indistinguishable from one that never declared any. It has no fixture pair and is the check most likely to produce noise — on any package whose manifest is not loaded, it fires unconditionally. |
| `AST06-cross-skill-data-leak` | `AST06-S05`'s `artifact_signal` (`covers: artifact-signal-only`) | Declared in `CHECK_COVERAGE` and absent from `DETECTORS`. Nothing is implemented and nothing may be: the registry tiers `AST06-S05` out-of-artifact because whether data actually crossed between two co-installed skills is an execution-trace property. It keeps its entry rather than being deleted, because an id silently dropped reads as a check that never existed instead of one that was ruled out on purpose. |

### The signal-symmetry ruling, applied here

A tier-doctrine review found `AST06-missing-sandbox-declaration` classified two ways at
once: `static-detectable` in this module, where it counted as a detector, and
`artifact_signal` in the registry entry where counting it would have obliged someone to
build one. The registry's own text had already noticed the two were the same predicate and
still ruled them differently.

Both files now give it one ruling. Missing permission metadata IS decidable by inspecting
the package alone, the registry says so in `artifact_signal_decidable`, and precisely
because it is only a precondition the module declares `covers: artifact-signal-only` and
may never publish it as coverage of AST10-S04. `F1_SCOPE` for this module is
**`mixed-proxy`** — one `full` pair, one category precondition, three proxies — returned by
`f1_report` beside any number.
`tests/test_tier_doctrine_symmetry.py` fails if either file moves without the other.

### What changed, and what the earlier version of this page got wrong

Three claims on this page were true when it was written and are false now. Two were
pinned by tests in `tests/test_coverage_matrix.py` so that fixing the defect would force
this section to be rewritten in the same change:

1. **"`detect_unrestricted_shell_exec` crashes on a USF-conformant manifest."** It called
   `.get("allowed")` on a field `schemas/usf-v1.schema.json` declares a **boolean**, so
   the one category with a static-detectable scenario could not be run against a
   conformant package at all. It now reads the boolean, the `{allowed, commands}`
   mapping, and a bare command string.
2. **"Neither half of `AST06-S01`'s defining condition is implemented."** Both halves are
   implemented, and each is scored over a labeled pair.
3. **"The module tiers `AST06-cross-skill-data-leak` agent-judgable."** It is now tiered
   `out-of-artifact`, matching the registry's tier for `AST06-S05`.

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

**Publication status.** `published_f1: "scenario-level 1.00 (AST06-S01, n=4);
artifact-signal-only 1.00 (n=2)"`. The two halves are printed separately and never
summed, because summing them would fold a precondition proxy into a scenario-level
figure — the exact blending `f1_scope: mixed-proxy` exists to prevent.
`detectors/fixture_loader.py` loads each fixture directory the way `cli/lib/bridge.py`
loads a candidate package and scores every labeled check over its OWN vulnerable/clean
pair:

| Corpus check | Detector check | covers | tp | fp | fn | tn |
| --- | --- | --- | --- | --- | --- | --- |
| `AST06-S1` Filesystem-root write scope | `AST06-root-write-scope` | full | 1 | 0 | 0 | 1 |
| `AST06-S2` Privilege-escalated host persistence | `AST06-host-persistence-write` | full | 1 | 0 | 0 | 1 |
| `AST06-S3` Shared unscoped credential namespace | `AST06-unscoped-shared-state-write` | artifact-signal-only | 1 | 0 | 0 | 1 |

Run every check in the module over every case — not just the check each pair was labeled
against — and no check fires on any of the three clean cases.
`AST06-unrestricted-shell-exec` additionally fires on `V3` and nothing else, which is
correct: that fixture declares an unbounded shell and its clean counterpart declares an
`apt-get` allow-list.

Read the number for what it is. Three checks each separating one hand-built pair, on a
corpus this project authored, is evidence that the checks discriminate at all — the
property a review found missing across this repository — and it is not evidence of field
precision. `AST06-missing-sandbox-declaration` has no pair at all: every fixture declares
a permission block, so it fires on none of them. Its true-positive and true-negative
cases live in `skills/AST06/scripts/test_ast06_detector.py`, and its absence from the
corpus is recorded below as open debt rather than counted as a pass.

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
angles (a declared write scope reaching root, and a privilege-escalated persistence
call site), and the remaining two measure a precondition for an out-of-artifact
scenario. Full formulaic coverage of a one-scenario tier is not broad coverage of
AST06: Network Pivot, Skill Shadowing, Localhost Attack Surface and Cross-Agent
Workspace Contamination remain undecidable from a package, and no number on this page
says anything about them.

Present on disk, all six matching the manifest's declared paths:

```
fixtures/AST06/V1-filesystem-root-write-scope/SKILL.md    vulnerable  -> AST06-S01 (covers: full)
fixtures/AST06/C2-filesystem-root-write-scope/SKILL.md    clean       -> AST06-S01 (covers: full)
fixtures/AST06/V3-unrestricted-sudo/SKILL.md              vulnerable  -> AST06-S01 (covers: full)
fixtures/AST06/C4-unrestricted-sudo/SKILL.md              clean       -> AST06-S01 (covers: full)
fixtures/AST06/V5-shared-credential-namespace/SKILL.md    vulnerable  -> proxy for AST06-S05 (artifact-signal-only)
fixtures/AST06/C6-shared-credential-namespace/SKILL.md    clean       -> proxy for AST06-S05 (artifact-signal-only)
```

**All six were re-authored when the detectors landed, and one of them was mislabeled.**
Each fixture previously consisted of a stub `SKILL.md` whose frontmatter carried a marker
string naming the mechanism — `allow_write: ["/"]`, `shell_permission: "sudo *"`,
`secrets_namespace: none` — and a one-line body. No fixture contained a script or a
permission block, so a detector that separated them would have been reading the label off
the fixture, which is the fixture-authorship failure the detectability contract exists to
prevent.

The `V3`/`C4` pair was worse than thin: it was **mislabeled**. It carried the name
"Unrestricted sudo permission" and a reason describing "a static check on the
shell-permission field shape", while being labeled `covers: full` against `AST06-S01`
Host Escape — a scenario whose defining condition is a persistence write, which nothing in
the pair encoded. It is now named "Privilege-escalated host persistence" and the
vulnerable member shells out under sudo to copy a launch daemon into
`/Library/LaunchDaemons` and register it with `launchctl`, which is the whitepaper's Host
Escape scenario directly. The clean member needs the same privilege for
`sudo apt-get --version` and writes only inside its own sandbox. `fixtures/manifest.yaml`
carries the same note inline.

## Reconciliation debt

Closed since the previous revision of this page:

1. ~~`detect_unrestricted_shell_exec` crashes on a USF-conformant manifest.~~ It reads
   the USF bare boolean, the `{allowed, commands}` mapping, and a bare command string.
   `tests/test_coverage_matrix.py::test_ast06_shell_check_reads_the_usf_bare_boolean_instead_of_crashing`
   pins the fix.
2. ~~Neither half of `AST06-S01`'s defining condition is implemented.~~ Both are, and
   each is scored over a labeled pair.
3. ~~The module tiers `AST06-cross-skill-data-leak` agent-judgable.~~ It is tiered
   `out-of-artifact`, matching the registry.
4. ~~No fixture loader.~~ `detectors/fixture_loader.py`.

Open:

1. **`AST06-missing-sandbox-declaration` has no fixture pair** and remains the noisiest
   check in the module: on any package whose manifest fails to load it fires
   unconditionally, so a harness bug and a stripped manifest are indistinguishable in its
   output. Unit-tested both ways; not measured over the corpus.
2. **`AST06-unrestricted-shell-exec` has no fixture pair either.** It fires on `V3` and
   on nothing else in the corpus, which is the right behaviour, but no case is *labeled*
   against it, so that is an observation rather than a measurement. Giving either of
   these a pair would add corpus checks and, by the locked formula, take the declared
   corpus above six cases — a change to `detectable_scenarios` that moves the category's
   `tier_lock_hash` and requires the whole corpus to be re-labeled (ADR-0004, S-011).
3. **The persistence scan reads Python only.** `detectors/pysource.py` parses `.py`
   files; a `.sh` installer, a `package.json` `postinstall`, or a `Makefile` target
   planting the same cron job is not seen. The location table is platform-complete
   (cron, systemd, launchd, shell rc, `rc.local`, `authorized_keys`, Windows Run key);
   the *language* coverage is not.
4. **Two of six cases proxy an out-of-artifact scenario.** They must be resolved to
   `AST06-S05` before the engine sees them, so the guard excludes them, rather than
   entering the denominator under their manifest-local id. `run_corpus` keeps them in
   their own `artifact-signal-only` slice and never sums them into the scenario-level
   figure.

## Change control

The tiering above is bound to `tier_lock_hash`
`d22946d405b961a25da7194c868288f384bc8035d4555112acd49a5421ae30e3`
(`validators/tier_lock.py`). Moving any AST06 scenario between tiers invalidates every
fixture case labeled under the old tier, changes the hash, and requires the corpus to be
re-labeled and the judge run repeated before an F1 may be republished (ADR-0004, S-011).
