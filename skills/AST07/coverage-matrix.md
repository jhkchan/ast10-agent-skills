# AST07 — Update Drift: coverage matrix

Audit artifact for ADR-0004's per-scenario detectability contract. It states, for every
attack scenario the OWASP Agentic Skills Top 10 names under AST07, which tier it sits in,
what `skills/AST07/scripts/detector.py` actually checks for it, and why. It is not a
summary of the whitepaper; read the whitepaper's own AST07 section for the threat
description.

**Authority.** `scenarios/registry.yaml` is authoritative on tier. This file restates that
tiering for AST07 and adds the detector-side and corpus-side facts an auditor needs to
verify it. Where this file and the registry disagree, the registry wins and this file is
the defect.

**Sources cross-checked when this file was written (2026-08-23).**

| What | Where |
| --- | --- |
| Scenario list, titles, tiers, written reasons | `scenarios/registry.yaml`, entries `AST07-S01`–`AST07-S03` |
| Whitepaper body | OWASP Agentic Skills Top 10, §8 "AST07 - Update Drift", pp. 37–39; the three Attack Scenarios sub-headings are on p. 38 |
| Detector | `skills/AST07/scripts/detector.py` |
| Corpus labelling | `fixtures/manifest.yaml`, category `AST07` (`tier_lock_hash: d57441e6771d6e62845b3cec9efbea906b6e4b09bd309d0723d06225323b84c7`) |
| Fixture files on disk | `fixtures/AST07/` |
| Sizing and never-pad rules | `features/owasp-ast10-agent-skills/spec.md` gate-4, S-003, S-007 |

AST07 is one of the two categories where the whitepaper's table of contents and its body
agree on the scenario count: three, in both. Nothing was recovered or lost in extraction
here (contrast AST08, where the body names one scenario the TOC omits).

## Scenario table

Legend for the detector column:

- `—` — nothing is checked, and nothing should be: the tier says a single package cannot
  decide this scenario.
- A named function — the function in `detector.py` that decides the scenario.

| Scenario id | Whitepaper title | Tier | What the detector actually checks | Written reason for the tier |
| --- | --- | --- | --- | --- |
| `AST07-S01` | Malicious Update | `out-of-artifact` | — | "Update" is a relation between two versions and "compromised account" is registry-side state. A single package cannot show that it differs maliciously from a predecessor it does not contain. |
| `AST07-S02` | Rollback Attack | `out-of-artifact` | — | Requires the release timeline — version ordering and prior content hashes — plus knowledge of which prior version was vulnerable. None of that is in a single artifact snapshot. |
| `AST07-S03` | Hot-Reload Abuse | `out-of-artifact` | — | Requires runtime reload-event history from the host process and the directory's permissions on the deployed host. The package at rest is identical before and after the swap. |

Tier totals: **0 static-detectable, 0 agent-judgable, 3 out-of-artifact.** AST07 and AST09
are the only two categories in the registry whose scenario sets are *unanimously*
out-of-artifact — so neither has a judge-scored tier either — and they get there by
different routes: AST09's scenarios are organisational
(`tests/test_scenario_registry.py::test_ast09_has_no_static_detectable_scenario`), AST07's
are temporal. AST05 also has an empty static-detectable tier but retains one agent-judgable
scenario, so it is not in the same position.

### Detector state, verified

`detector.py` ships `DETECTORS = {}` — zero detector functions — and
`STATIC_DETECTABLE == set()`. Calling `f1_report()` returns
`{"status": "declared-and-uncovered", "f1": None}` (verified by running the module;
asserted by `skills/AST07/scripts/test_ast07_detector.py::test_s007_empty_tier_never_manufactures_an_f1`).

The engine refuses to score this category by accident as well as by design: passing any
AST07 scenario into `detectors.engine.run_category` as a fixture raises
`OutOfArtifactFixtureError` rather than silently scoring it (verified:
`out-of-artifact scenario(s) present in fixture corpus for category 'AST07': ['AST07-S01']`).

### Known defect in the detector module's own declaration

`detector.py`'s `SCENARIO_TIERS` names only two scenarios, under local ids that are not
registry ids:

```
"AST07-rollback-attack": "out-of-artifact"
"AST07-hot-reload-abuse": "out-of-artifact"
```

`AST07-S01` Malicious Update has no entry at all. The module predates
`scenarios/registry.yaml` (its own docstring says so) and was written against the two
scenarios `plan.md` happened to name. **Consequence for the published F1: none** — all
three scenarios are out-of-artifact, so the static-detectable set is empty under either
enumeration and the category publishes no number either way. **Consequence for the audit:
real** — a reader checking the detector module alone would conclude AST07 has two
scenarios. This matrix, not `SCENARIO_TIERS`, is the complete list. The fix is to re-key
`SCENARIO_TIERS` to the three registry ids; it does not move a tier, so it does not trip
the S-011 tier lock or require a corpus re-label.

## Declared and uncovered

Every AST07 scenario is out-of-artifact, so this section is the whole category. For each:
why one skill package cannot decide it, and the evidence that would.

### `AST07-S01` — Malicious Update

*A trusted skill author's account is compromised and the attacker pushes v2.0 with a
payload; auto-updating agents receive it silently.*

**Why one package cannot decide it.** The scenario has two halves and the package holds
neither. "Malicious" here is not a property of the shipped bytes in isolation — a payload
that would be flagged on its own merits is an AST01 finding, and this skill would report
it as one. What makes it an *update* attack is that these bytes differ from the bytes the
operator already trusted; that comparison needs the predecessor, which by definition is
not in this package. The second half — that a compromised maintainer account, rather than
the legitimate maintainer, authored the push — is authentication state held by the
registry.

**Evidence that would decide it.**

1. The predecessor artifact itself, or a signed release-transparency log entry binding
   `version -> content hash -> publisher key` for the version previously installed, so the
   two releases can be compared without trusting either party's claim about which came
   first.
2. A semantic diff between predecessor and successor, scoped to behaviour rather than
   text — the whitepaper's own mitigation is to "validate all changes through a semantic
   security check" and route substantive changes to human review, which presupposes a diff
   exists to check.
3. Registry-side account and key events for the publishing identity: credential resets,
   new signing keys, publish-source changes, MFA state at push time. Without these the
   most a reviewer can say is "the content changed", not "the account was taken over".

**What the artifact does show, and why it is not coverage.** The registry records an
`artifact_signal` for this scenario: *"Absent signature or content-hash pinning, which is
what lets an update land unverified."* That is an enabling precondition, not the scenario.
A skill can be perfectly hash-pinned and still be maliciously updated once the operator
accepts the new hash; a skill can be unpinned for years and never receive a malicious
update. Under `scenarios/registry.yaml`'s `defining_condition_rule` an artifact signal
"is never counted as coverage of the scenario" — see the corpus section below, where three
of the six files sitting in `fixtures/AST07/` are exactly such signals.

### `AST07-S02` — Rollback Attack

*An attacker forces a downgrade to a known-vulnerable version via dependency-resolution
manipulation.*

**Why one package cannot decide it.** A version string in a manifest is an ordinal with no
direction of travel. `1.4.2` is not "a downgrade" — it is a downgrade only relative to a
`1.5.0` that was previously resolved, and only when nobody asked for `1.4.2`. `SKILL.md`'s
decision rule 2 states the discriminator: the signal is "resolved version *decreased*
without an explicit operator action requesting that specific version", not "resolved
version decreased". Both the prior resolution and the operator's intent live outside the
package.

**Evidence that would decide it.**

1. The release timeline for the skill — the ordered set of published versions with their
   content hashes — so "decreased" is decidable at all.
2. The resolver's decision record from the install or update run: what constraint was
   requested, what candidate set the registry offered, and what was resolved. A downgrade
   forced by resolution manipulation is visible here and nowhere else.
3. An operator-intent record distinguishing a deliberate pin-back (an admin choosing a
   known-good older release after a bad update) from an imposed one. Without this the
   detector convicts every legitimate rollback.
4. A vulnerability record — CVE or registry advisory — marking the resolved target
   vulnerable, which is what makes the downgrade an attack rather than a preference. The
   whitepaper's mitigation "subscribe to registry security advisories and auto-alert on
   CVE matches for installed skills" is the operational form of this feed.

**Artifact signal, not coverage.** The registry records *"Version ranges rather than
immutable pins in the dependency specification."* An unpinned range is the surface a
rollback is executed against, which is why `SKILL.md`'s decision rule 1 makes hash pinning
the control. It is still not the scenario, and it fails in both directions: a `sha256:`
pin blocks a resolver-driven downgrade without making a past one observable, and an
unpinned range that never resolves backwards is not a rollback attack.

### `AST07-S03` — Hot-Reload Abuse

*The skill directory is writable; an attacker modifies SKILL.md mid-session and the agent
picks up changes without restart.*

**Why one package cannot decide it.** This is the strongest out-of-artifact case in the
repo, and the registry marks it accordingly: `artifact_signal: null` — there is not even a
partial precondition visible in the package. The reason is that the attack leaves the
package in a perfectly ordinary state. Read the directory before the swap and you see a
valid skill; read it after and you see a different valid skill. Nothing in either snapshot
records that a reload happened between them, and neither snapshot is malformed. The two
facts that define the scenario — that the deployed directory was writable by a party other
than the installer, and that the host re-read the file without restarting — are properties
of the host filesystem and the host process. `SKILL.md`'s decision rule 3 is the design
consequence: the fix is a configuration control ("prohibit hot-reload in non-development
environments"), not a detection rule, because detecting arbitrary swapped-in content is an
unwinnable race.

**Evidence that would decide it.**

1. Host runtime reload telemetry — the watcher's own event stream (OpenClaw's
   `SkillsWatcher` is the whitepaper's named example), giving reload timestamps and the
   path reloaded, correlated to a session that was already running.
2. Filesystem permission and ownership state of the deployed skill directory on the host,
   plus the identity that wrote the modified file.
3. A before/after content-hash pair for the same install path within one session — which
   requires an inventory that records a hash and a last-verified timestamp per installed
   skill, the whitepaper's sixth preventive mitigation. That mitigation exists precisely
   because without it this scenario is invisible after the fact.

Note the ordering: (3) alone proves the bytes changed; (1) proves the change took effect
without a restart; (2) attributes it. A control claiming to detect hot-reload abuse from
fewer than all three is claiming more than its evidence supports.

## F1 denominator for AST07

**Which scenarios count: none. AST07 publishes no F1.**

The denominator is the category's `static-detectable` tier
(`detectors/engine.py::run_category` scores only `Tier.STATIC_DETECTABLE` fixtures;
`skills/AST07/scripts/detector.py::f1_report` derives its denominator from
`STATIC_DETECTABLE`). For AST07 that tier is empty, so:

- `f1_report()` returns `{"status": "declared-and-uncovered", "f1": None}` — never a
  number, and specifically never `0.0` or `1.0`.
- `fixtures/manifest.yaml` records `status: declared-and-uncovered`, `f1_scope: none`,
  `published_f1: null`.
- `detectors/f1_reporter.py::report_category` maps `f1 is None` to the status string
  `declared-and-uncovered` in the published per-category breakdown, so the row appears in
  the report rather than being dropped from it.

**Why the absence of a number is the honest result and not a gap.** Padding is available
and cheap here — six fixture files already sit on disk (see below) that a detector could
be written to separate perfectly. Publishing that as "AST07 detection F1" would report the
distance between a fixture author and a detector author who are the same person, on checks
that decide none of the three scenarios the category is about. ADR-0004 accepted a narrower
denominator specifically to avoid this: "the published F1 measures detection rather than
fixture authorship". gate-4 makes it a rule — "a category whose detectable tier is empty
publishes **no F1 at all** ... it must never be padded to manufacture a number" — and
S-003 makes it a tested invariant.

The claim this category *can* honestly make is a scope claim, not a score: all three named
AST07 scenarios are enumerated, tiered, and reasoned above, and each states the evidence
that would decide it. A reader can check that list against the whitepaper in a minute.

## Corpus entitlement versus what is on disk

| Quantity | Value | Where it comes from |
| --- | --- | --- |
| Static-detectable scenarios (registry) | 0 | `scenarios/registry.yaml` |
| Labeled detectable checks (manifest) | 0 | `fixtures/manifest.yaml` `AST07.registry_coverage.labeled_detectable_checks` |
| Literal reading of `max(6, 2 x detectable)` | 6 | arithmetic only |
| **Entitlement actually in force** | **0** | the never-pad rule overrides the floor when the detectable tier is empty |
| Cases admitted to the corpus | 0 | `fixtures/manifest.yaml` `AST07.cases: []` |
| Fixture files present under `fixtures/AST07/` | **6** | `find fixtures/AST07 -type f` |

**The floor does not apply to an empty tier.** `max(6, 2 x 0) = 6` is arithmetically true
and operationally wrong: the `MIN_FLOOR = 6` exists to stop a category with one or two
detectable scenarios publishing an F1 off a two-case corpus, not to require six cases for a
category with nothing to detect. The implemented rule branches on the empty tier first —
`expected = max(min_floor, 2 * labeled) if labeled else 0`
(`tests/test_scenario_registry.py::test_declared_expected_size_follows_the_locked_formula`)
— and the manifest declares `declared_expected_cases: 0`. AST07's entitlement is zero
cases.

**The six files on disk are not the corpus.** They predate the registry reconciliation and
are unreferenced by `fixtures/manifest.yaml`, which lists `cases: []` for AST07. They are
labeled with *local* ids that collide visually with registry ids while meaning something
else entirely — a trap for anyone reading the fixture frontmatter without the registry
open:

| File pair | Local id in frontmatter | What the pair actually varies | Nearest registry relation |
| --- | --- | --- | --- |
| `V1-missing-signed-content-hash`, `C2-missing-signed-content-hash` | `AST07-S1` | `signed_content_hash` present vs. `null` | The **artifact signal** declared on `AST07-S01`, not the scenario |
| `V3-unpinned-update-channel`, `C4-unpinned-update-channel` | `AST07-S2` | `update_source` pinned to `@v1.4.2` vs. `@latest` | The **artifact signal** declared on `AST07-S02`, not the scenario |
| `V5-absent-version-field`, `C6-absent-version-field` | `AST07-S3` | `version` present vs. `null` | No registry relation at all. `AST07-S03` declares `artifact_signal: null`. This pair derives from the mitigation "maintain an inventory of installed skills with version, hash, and last-verified timestamp" |

Read the collision carefully: local `AST07-S3` is "absent semantic version field" while
registry `AST07-S03` is "Hot-Reload Abuse". They share no content. Three of the six files
therefore proxy an enabling precondition (which the registry's `defining_condition_rule`
forbids counting as coverage), and two of them proxy nothing named at all.

Two options are open and both are honest; neither may be taken silently:

1. **Delete them**, on the grounds that a category with a zero-case entitlement should not
   ship fixture files at all.
2. **Keep them and re-label them** as an explicitly-named artifact-signal corpus —
   `covers: artifact-signal-only` for the first two pairs, `covers: category-precondition`
   with a stated `derivation` for the third — admitted to `fixtures/manifest.yaml` under a
   scope that is *not* AST07's F1. Any check built on them measures pin discipline, which
   is a real and useful control (`SKILL.md` decision rule 1), and must be reported under
   that name.

What is not open: admitting them as `AST07-S01`/`S02`/`S03` cases. `detectors/engine.py`
enforces this mechanically — such a fixture raises `OutOfArtifactFixtureError`.

## Changing a tier in this file

The tiering is frozen against the labeled corpus by
`fixtures/manifest.yaml`'s `tier_lock_hash` for AST07
(`d57441e6771d6e62845b3cec9efbea906b6e4b09bd309d0723d06225323b84c7`), a sha256 over the
sorted `id:tier` pairs (`validators/tier_lock.py`). Moving any AST07 scenario out of
`out-of-artifact` changes that hash, which per S-011 forces the corpus back through
re-labeling and the judge matrix back through a re-run before any F1 for this category may
be published. Because AST07's corpus is currently empty, the cost of a reclassification is
lower here than anywhere else in the repo — which is a reason to get the tiering right on
the merits, not a reason to treat it as provisional.
