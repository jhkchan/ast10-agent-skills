# AST02 Coverage Matrix — Supply Chain Compromise

Per-scenario detectability contract for AST02, required by
`docs/adr/0004-per-scenario-detectability-contract.md`. This is the artifact the narrowed
F1 denominator is defended with: it states which of the whitepaper's named AST02
scenarios this package claims to decide, which it does not, and why.

This repository is an independent community reference implementation. It is **not** an
official OWASP project and carries no OWASP endorsement (see `NOTICE`).

AST02 is the category where the honest answer is smallest. Three of its four named
scenarios are properties of a registry, a resolver, or an account — none of which is
inside the package a skill reviewer holds.

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
| AST02-S03 | Config-File Hijacking | static-detectable | not implemented in this package — see Coverage debt | Those config files ship inside the package. A command-bearing value under a key the host auto-executes at project open (a hook entry, `.claude/settings.json`, an `ANTHROPIC_BASE_URL` override) is a structural key-and-value match. |
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
it measures pin posture, never resolver behaviour.

## Coverage debt

`skills/AST02/scripts/detector.py` ships **zero detector functions**, by design: its
docstring reasons from Maintainer Account Takeover being registry-side and concludes the
category's declared-detectable tier is empty. Under the registry that conclusion is now
one scenario too strong. AST02-S03 Config-File Hijacking is `static-detectable`, so the
category's declared-detectable tier contains exactly one scenario, and the detector
implements none of it.

The detector's interim `SCENARIO_TIERS` names only `AST02-maintainer-account-takeover`.
That agrees with the registry on AST02-S04's tier and is silent on the other three.

**AST02-S03's coverage is booked to another category.** `fixtures/manifest.yaml` records
that the pair `AST01-V3` / `AST01-C4` (destructive postinstall) links to registry parent
AST02-S03 at `covers: full`, which is why AST02-S03 does not appear in this category's
`uncovered_static_detectable` list. A reviewer reading AST02's row as
`declared-and-uncovered` while its only detectable scenario is fixture-covered under
AST01 is reading an accounting artefact, not a detection claim. Two consequences worth
stating plainly:

- The AST02 row understates coverage: the category's one detectable scenario has a
  labeled corpus, it is just not filed here.
- That corpus covers less of AST02-S03 than `covers: full` implies. It varies a
  `postinstall` value between `rm -rf $HOME` and `mkdir -p .cache`, exercising
  destructive-command matching inside a declared lifecycle hook. AST02-S03's defining
  condition is a command-bearing value in a config file the host auto-executes **at
  project open** — `.claude/settings.json`, a hook entry, an `ANTHROPIC_BASE_URL`
  override, the trigger CVE-2025-59536 and CVE-2026-21852 anchor. The pair does not
  exercise that trigger.

**Six orphaned fixture files.** `fixtures/AST02/` contains three vulnerable/clean pairs on
disk that `fixtures/manifest.yaml` no longer declares (`cases: []`, `cases_present: 0`).
They were built before the registry reconciliation and were delisted by it, correctly:

| On-disk pair | Fixture check | Registry parent | Parent tier | Why it cannot be a static-detectable AST02 case |
| --- | --- | --- | --- | --- |
| `V1` / `C2` typosquatted-dependency | `AST02-S1` Typosquatted dependency name | AST01-S01 Typosquatting | agent-judgable | The scenario is not tiered static-detectable, so it cannot enter a static-detectable corpus; and it is AST01's scenario, not AST02's. |
| `V3` / `C4` unpinned-wildcard-dependency | `AST02-S2` Unpinned wildcard dependency version | AST02-S02 Dependency Confusion | out-of-artifact | S-003 bars a fixture bound to an out-of-artifact scenario outright. The pair measures that scenario's `artifact_signal` (pin posture) and may only ever be reported as `artifact-signal-only`. |
| `V5` / `C6` lockfile-hash-mismatch | `AST02-S3` Lockfile content-hash mismatch | none | — | Maps to no named AST02 scenario. It derives from the category's mitigations ("pin all nested dependencies to immutable hashes"; "have the signature cover a canonical digest of SKILL.md plus every declared resource file"), which makes it `category-precondition`, not scenario coverage. |

Leaving the files on disk while the manifest declares none is a state a reviewer will
trip over. Resolution belongs to a fixture task, not to this matrix, and has exactly two
honest forms: delete the six files, or re-declare them in a non-F1 proxy lane labeled
`artifact-signal-only` / `category-precondition`. Re-listing them as
`detectable_scenarios` to give AST02 an F1 is the padding the never-pad rule forbids.

## F1 denominator for AST02

**Which scenarios count.** The declared-detectable tier is 1 static-detectable +
0 agent-judgable = **1 of 4** scenarios (AST02-S03). AST02-S01, S02 and S04 are
out-of-artifact and are excluded from the denominator, published above as declared-and-
uncovered.

**AST02 publishes no F1.** The labeled detectable tier in `fixtures/manifest.yaml` is
empty (`detectable_scenarios: []`, `cases: []`, `status: declared-and-uncovered`,
`published_f1: null`) and the shipped detector implements no check, so there is nothing to
compute a number over. Under gate-4 that is the required outcome, not a shortfall to be
worked around: a category whose detectable tier is empty publishes no F1 and is reported
`declared-and-uncovered`, never padded.

**Why that is a deliberate honesty choice, stated precisely.** Three quarters of AST02's
named attack surface is genuinely out of reach of any single-package detector, and for
two of those three scenarios the registry records no artifact signal at all. A category
in that position can always be given a respectable-looking F1 by authoring fixtures
against whatever a detector already happens to match — pin posture, name similarity,
lockfile hash equality — and labeling them as AST02 coverage. Each of those is a real
static property and none of them decides a named AST02 scenario. That number would
measure the fixture author's choice of proxy, not detection, and it would report the
category as covered while Registry Flooding, Dependency Confusion and Maintainer Account
Takeover remain exactly as undetectable as before. Publishing `null` states the true
position: the one AST02 scenario a package can decide is not yet decided here, and the
other three cannot be decided here at all.

Note the two different reasons "no F1" can have, both live in this repository: AST02's is
an empty *labeled* detectable tier under a non-empty *registry* one; AST09's is a registry
tier with no static-detectable scenario in it whatsoever.

## Corpus entitlement and actual corpus

Formula, locked at gate-4: `cases = max(6, 2 x detectable_scenarios)`, class-balanced,
drawn only from the static-detectable tier.

| Quantity | Value | Derivation |
| --- | --- | --- |
| Registry static-detectable scenarios | 1 | `scenarios/registry.yaml` (AST02-S03) |
| **Entitlement at full registry coverage** | **6** | `max(6, 2 x 1)` |
| Labeled detectable checks in the corpus | 0 | `fixtures/manifest.yaml` `detectable_scenarios: []` |
| Entitlement at present labeling | 0 | empty detectable tier — the never-pad rule sets this to 0, not to the floor of 6 |
| **Actual fixture count under `fixtures/AST02/`** | **6** | 3 vulnerable + 3 clean, all orphaned: declared by no manifest entry |
| Declared cases | 0 | `cases: []` |

The 6 files on disk are not the 6-case entitlement. They are the delisted pre-
reconciliation corpus described under [Coverage debt](#coverage-debt); the entitled corpus
for AST02-S03 — six cases exercising `.claude/settings.json`, hook entries and
environment-override keys — has not been authored.

```
ls -1d fixtures/AST02/*/ | wc -l
python3 -c "import yaml; c=yaml.safe_load(open('fixtures/manifest.yaml'))['categories']['AST02']; print(len(c['cases']), len(c['detectable_scenarios']), c['status'], c['published_f1'])"
```

## Tier lock

`registry_tier_lock: a5f7bcfdeb219c2a30da4e7cb492933bb33ec67390fea7117a36045e0793622c`

```
python3 -c "import yaml; from validators.tier_lock import tier_lock_hash; print(tier_lock_hash([s for s in yaml.safe_load(open('scenarios/registry.yaml'))['scenarios'] if s['category']=='AST02']))"
```

Reclassifying any AST02 scenario changes this hash, which is the signal that the corpus
must be re-labeled and the judge matrix re-run before an F1 for this category can be
published (spec.md S-011, `validators/tier_lock.py`).
