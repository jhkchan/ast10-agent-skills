# AST02 Coverage Matrix — Supply Chain Compromise

Per-scenario detectability contract for AST02, required by
`docs/adr/0004-per-scenario-detectability-contract.md`. This is the artifact the narrowed
F1 denominator is defended with: it states which of the whitepaper's named AST02
scenarios this package claims to decide, which it does not, and why.

This repository is an independent community reference implementation. It is **not** an
official OWASP project and carries no OWASP endorsement (see `NOTICE`).

AST02 is the category where the honest answer is smallest. Three of its four named
scenarios are properties of a registry, a resolver, or an account — none of which is
inside the package a skill reviewer holds. The fourth is decided here.

## Authority chain

| Rank | Artifact | Authoritative on |
| --- | --- | --- |
| 1 | OWASP Agentic Skills Top 10, AST02 "Attack Scenarios" body | the enumeration — 4 scenarios, titles verbatim |
| 2 | `scenarios/registry.yaml` | the tier of each scenario, and its written reason |
| 3 | this file | the F1 denominator, the corpus accounting, the coverage debt |
| 4 | `fixtures/manifest.yaml` | which fixture case is labeled against which check |
| 5 | `skills/AST02/scripts/detector.py` | implementation only — subordinate to rank 2 |

## Scenario tiering — 4 of 4

| Scenario | Whitepaper title | Tier | What the detector actually checks | Why this tier |
| --- | --- | --- | --- | --- |
| AST02-S01 | Registry Flooding | out-of-artifact | — | "Coordinated" and "hundreds" are properties of the registry's publication corpus over time. A single package is indistinguishable from one member of a flood and from one honest publication. |
| AST02-S02 | Dependency Confusion | out-of-artifact | — | The defining condition is that the resolver selects an attacker's package in place of the intended nested one. Deciding it needs the resolution namespace and the registry's contents at install time; neither is in the package. |
| AST02-S03 | Config-File Hijacking | static-detectable | `detect_config_file_hijacking` — over the config paths a host auto-reads at project open only, firing on a hook entry carrying a command, an MCP server entry that spawns a process, a control-plane environment override, or a task declared `runOn: folderOpen` | Those config files ship inside the package. A command-bearing value under a key the host auto-executes at project open (a hook entry, `.claude/settings.json`, an `ANTHROPIC_BASE_URL` override) is a structural key-and-value match. |
| AST02-S04 | Maintainer Account Takeover | out-of-artifact | — | Requires registry-side authentication and session state. A post-takeover release signed with the legitimate key is byte-indistinguishable from an honest one, so no in-package signal exists at all. |

Tally: **1 static-detectable, 0 agent-judgable, 3 out-of-artifact**.

```
python3 -c "import yaml; [print(s['id'], '|', s['title'], '|', s['tier']) for s in yaml.safe_load(open('scenarios/registry.yaml'))['scenarios'] if s['category']=='AST02']"
```

## Declared and uncovered

Three of AST02's four scenarios. Published here rather than dropped, per `docs/adr/0004`
and spec.md S-003; none enters the fixture corpus or any F1 denominator.

| Scenario | Whitepaper title | Why one skill package cannot decide it | Evidence that would decide it |
| --- | --- | --- | --- |
| AST02-S01 | Registry Flooding | The scenario is a statement about a *population* of publications — coordinated bulk upload to crowd out legitimate alternatives. Nothing distinguishes one member of a flood from one honest publication at the artifact level; the whitepaper's own evidence for the category is a registry whose publish barrier was "a SKILL.md file and a one-week-old GitHub account", which is a registry property, not a package property. | The registry's own publication corpus over a time window: per-publisher upload rate and burst timing, account-age-at-first-publish, near-duplicate clustering across SKILL.md bodies and declared resources, and shared signing keys or infrastructure across nominally distinct publishers. The USENIX Security 2026 measurement study's finding that 54.1% of malicious skills traced to a single publisher cluster is exactly the kind of conclusion that needs the corpus, not the artifact. |
| AST02-S02 | Dependency Confusion | The package can show *what it asked for*; the scenario is about *what the resolver hands back*. A nested requirement that resolves to the intended internal package on one host resolves to an attacker's public package of the same name on another, with the package bytes unchanged. | The install-time resolution trace: the ordered index/registry list in effect, the candidate versions each index offered for every transitive requirement, and the digest actually installed, compared against the intended internal source. Equivalently, a resolved lockfile with `--hash=sha256:` entries for the complete transitive tree, produced on the host that will install it. |
| AST02-S04 | Maintainer Account Takeover | The whitepaper's condition is that a trusted author's *account* was compromised and used to push a backdoored version. Authorship is not observable from the artifact: a release pushed by an attacker holding the legitimate signing key verifies exactly as an honest release does. The registry declares this the one scenario with no in-package signal at all. | Registry-side authentication and publication state: auth and session logs for the publishing account, signing-key provenance and rotation history, publication cadence and origin (IP, CI identity) versus the maintainer's baseline, plus a transparency log with append-only inclusion and consistency proofs so a silently rewritten publication history is detectable. A revocation endpoint consulted at load time is what makes the answer actionable once known. |

Registry `artifact_signal` values: AST02-S01 and AST02-S04 declare **none** — there is no
partial proxy to implement. AST02-S02 declares one: transitive dependencies pinned as
version ranges rather than immutable `sha256:` hashes, the precondition the whitepaper's
own mitigation ("Pin all nested dependencies to immutable hashes") targets. That signal is
a decidable lockfile property and is **not** coverage of AST02-S02; a corpus built against
it measures pin posture, never resolver behaviour. No shipped check computes it, so
`artifact_signal_checks` for AST02-S02 is still empty and nothing may be labeled against
it.

## What the detector ships

One check, for the one scenario a package can decide.

| Detector function | Check id | `CHECK_COVERAGE` | Registry link |
| --- | --- | --- | --- |
| `detect_config_file_hijacking` | `AST02-config-file-hijacking` | `full` | AST02-S03 |

`SCENARIO_TIERS` enumerates all four of the category's scenarios, keyed by the registry's
canonical ids and carrying the registry's tier for each — `AST02-S03` static-detectable,
`AST02-S01`, `AST02-S02` and `AST02-S04` out-of-artifact. So a reader of the module, not
only a reader of this file, sees the three-quarters of the category that is out of reach.

Three counts are in play and the module keeps them in separate tables: **four** registry
scenarios (`SCENARIO_TIERS`), **one** of them static-detectable (`STATIC_DETECTABLE`, the
F1 denominator), and **one** shipped check (`CHECK_COVERAGE`, keyed by check id — the table
above). They coincide at one here, which is exactly why this module's earlier check-keyed
table looked correct: the slug map happened to be one-to-one, so `node cli/bin/cli.js list`
printed the right number for AST02 while printing ten for AST01's seven scenarios. Agreeing
by coincidence is not agreeing, and the keying is now the registry's in every module.

`F1_SCOPE` is `scenario-level`: the module's only check is `covers: full` against a scenario
the registry independently tiers static-detectable.

### Two decisions inside the check, both load-bearing

1. **It is keyed on the config surface, not on the presence of a command.** A shell command
   in a bundled script is ordinary; the same command in `.claude/settings.json` is an
   execution path the host enters with no user action. The scan therefore runs only over
   the paths a host auto-reads at project open (`.claude/settings.json`,
   `.claude/hooks.json`, `.mcp.json`, `.cursor/*`, `.vscode/tasks.json`,
   `.vscode/settings.json`), matched on the tail of the package-relative path so a config
   nested one directory down still counts. A `package.json` `postinstall` command is
   deliberately out of scope: it is a real risk and it is not this scenario's trigger.
2. **Within those files it is keyed on the auto-executed key.** A settings file carrying
   permissions, a model name, or `EDITOR=vim` is the normal case. The four shapes that fire
   are the ones the whitepaper names: a hook entry with a `command`, an MCP server entry
   that spawns a process, an environment override of a control-plane variable
   (`ANTHROPIC_BASE_URL`, `NODE_OPTIONS`, `LD_PRELOAD`, `GIT_SSH_COMMAND`, …), and a task
   declared `runOn: folderOpen`.

An unparseable config file is reported as *undecided*, not clean — malformed metadata is
AST04's parsing surface, and silently treating it as an absence of findings would be the
scanner-coverage failure AST08 is about.

## Coverage debt

**AST02-S03 is now labeled and implemented here, not booked to another category.** It
previously had no detector at all, and its only corpus was a pair filed under AST01
(`AST01-V3` / `AST01-C4`, "destructive postinstall") that varied a `postinstall` value
between `rm -rf $HOME` and `mkdir -p .cache`. Both this file and AST01's recorded, in
writing, that the pair "does not exercise that trigger" while still declaring
`covers: full` over AST02-S03. That is the fixture-authorship failure the detectability
contract exists to prevent: a corpus labeled against a scenario whose defining condition it
never encodes, passed by a detector that never existed.

The pair is **deleted from AST01's corpus**, and AST02 now ships eight cases of its own that
exercise the project-open trigger on four surfaces: the three the whitepaper names, plus a
Codex `.codex/config.toml` MCP entry whose `command`/`args` spawn a process when the
project's config layer loads. Nothing was
retuned to make a detector pass: the fixture was wrong about the scenario and was replaced.

Remaining debt for this category is the three out-of-artifact scenarios, which is not debt
this package can pay. AST02-S02's pin-posture `artifact_signal` remains unimplemented; if a
check is written for it, it enters `CHECK_COVERAGE` as `covers: artifact-signal-only` and a
corpus may then be labeled against *that*, under a scope which is explicitly not AST02's
scenario coverage.

**Six orphaned fixture files, deleted earlier and still gone.** `fixtures/AST02/` once held
three vulnerable/clean pairs that `fixtures/manifest.yaml` did not declare: a typosquat pair
proxying an AST01 scenario the registry tiers agent-judgable, a pin-posture pair proxying
AST02-S02's `artifact_signal`, and a lockfile-hash pair mapping to no named scenario. None
of them encoded AST02-S03, and none of them is among the eight cases the directory holds now.
`tests/test_coverage_matrix_ast07_ast08.py::test_ast02_ships_no_orphan_fixture_corpus` names
all six by directory so re-adding one cannot hide inside a legitimate corpus.

## F1 denominator for AST02

**Which scenarios count.** The declared-detectable tier is 1 static-detectable +
0 agent-judgable = **1 of 4** scenarios (AST02-S03). AST02-S01, S02 and S04 are
out-of-artifact and are excluded from the denominator, published above as declared-and-
uncovered.

**Published number.** `fixtures/manifest.yaml` publishes
`scenario-level 1.000 (AST02-S03, n=8)`, recomputed from the corpus by
`skills/AST02/scripts/test_ast02_detector.py` on every run. Measured: tp 4, fp 0, fn 0
across 4 vulnerable and 4 clean cases.

**What that number is and is not.** It is one scenario, eight hand-authored cases, and an
author who also wrote the detector — internal consistency, not field performance. It is
also not a statement about the category: three quarters of AST02's named attack surface is
still exactly as undetectable as before, and the number carries the scenario id precisely
so it cannot be read as "AST02 is covered". The clean half of each pair is a deliberate
near-miss chosen so a command-string grep would score 0.5 rather than 1.0:

| Pair | Vulnerable | Clean — the near miss |
| --- | --- | --- |
| hook command | `SessionStart` hook running `curl … \| sh` | the same settings file with permissions and a model name only |
| environment override | `ANTHROPIC_BASE_URL` pointed at an attacker proxy | the same `env` block setting `EDITOR` and `PAGER` |
| folder-open task | `runOn: folderOpen` executing `bootstrap.sh` | the byte-identical task command with no `runOn` trigger |

That claim is measured rather than asserted. `tests/test_corpus_discriminates_mechanism.py`
re-runs this corpus through an ablated check — a command-looking string inside any shipped
JSON or TOML config, with both halves of the real predicate (is the file auto-read at
project open? does the value sit under a key the host executes?) deleted. It scores
**F1 0.667** (tp 3, fp 2, fn 1) against the shipped check's 1.000: it misses the
environment-override case entirely, because that vulnerable file contains a URL and no
command, and it false-positives on both clean near misses — the folder-open case, which
carries the byte-identical command with no trigger, and the Codex case, which carries the
identical command string under `description`, a key nothing executes. Every one of those
errors is the corpus doing its job.

**Why a number here is not the padding the never-pad rule forbids.** The rule bars
manufacturing an F1 for a category whose detectable tier is empty. AST02's is not empty —
the registry tiers AST02-S03 static-detectable — and the corpus labels exactly that one
scenario, at the entitlement the formula gives it. What the rule *would* forbid, and what
this corpus does not do, is labeling cases against pin posture, name similarity, or
lockfile hash equality and reporting the result as AST02 coverage. Those three were the
delisted corpus and they stay delisted.

Note the two different reasons "no F1" can have, both still live in this repository:
AST07's and AST09's is a registry tier with no static-detectable scenario in it at all.
AST02 used to be reported alongside them for a third reason — an empty *labeled* tier under
a non-empty *registry* one — and no longer is.

## Corpus entitlement and actual corpus

Formula, locked at gate-4: `cases = max(6, 2 x detectable_scenarios)`, class-balanced,
drawn only from the static-detectable tier.

| Quantity | Value | Derivation |
| --- | --- | --- |
| Registry static-detectable scenarios | 1 | `scenarios/registry.yaml` (AST02-S03) |
| **Entitlement at full registry coverage** | **6** | `max(6, 2 x 1)` |
| Labeled detectable checks in the corpus | 1 | `fixtures/manifest.yaml` `detectable_scenarios` |
| Entitlement at present labeling | 6 | `max(6, 2 x 1)` — the floor, not the doubling |
| **Actual fixture count under `fixtures/AST02/`** | **8** | 4 vulnerable + 4 clean |

The floor of 6 over a single scenario is what pushed the corpus to cover four distinct
surfaces of AST02-S03 rather than one shape repeated. That is the formula doing useful
work: a one-scenario category still has to show the scenario in more than one dress.

```
ls -1d fixtures/AST02/*/ | wc -l
python3 -c "import yaml; c=yaml.safe_load(open('fixtures/manifest.yaml'))['categories']['AST02']; print(len(c['cases']), len(c['detectable_scenarios']), c['status'], c['published_f1'])"
```

Re-run the published number:

```
python3 -c "import sys; sys.path.insert(0,'.'); import importlib.util; from detectors import corpus; s=importlib.util.spec_from_file_location('d','skills/AST02/scripts/detector.py'); m=importlib.util.module_from_spec(s); sys.modules['d']=m; s.loader.exec_module(m); print(m.f1_report(corpus.category_fixtures('AST02')))"
```

## Tier lock

`registry_tier_lock: a5f7bcfdeb219c2a30da4e7cb492933bb33ec67390fea7117a36045e0793622c`

```
python3 -c "import yaml; from validators.tier_lock import tier_lock_hash; print(tier_lock_hash([s for s in yaml.safe_load(open('scenarios/registry.yaml'))['scenarios'] if s['category']=='AST02']))"
```

Reclassifying any AST02 scenario changes this hash, which is the signal that the corpus
must be re-labeled and the judge matrix re-run before an F1 for this category can be
published (spec.md S-011, `validators/tier_lock.py`). The corpus-internal `tier_lock_hash`
in `fixtures/manifest.yaml` now equals this value, because every AST02 entry in that file
is keyed by its registry id and carries the registry's tier — the two hashes are computed
over identical `id:tier` sets. That is agreement, not a copied constant; edit either side
and they diverge.
