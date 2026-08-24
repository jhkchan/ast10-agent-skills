---
artifact: coverage-matrix
category: AST04
category_name: Insecure Metadata
version: "1.1"
created: 2026-08-23
task: T-3.1b
tier_authority: scenarios/registry.yaml
corpus_authority: fixtures/manifest.yaml
detector: skills/AST04/scripts/detector.py
tier_lock_hash: "59f45799d2b1b4522f230694615b3d283d91c6c436373f14f7fa5be025b808f0"
registry_scenarios: 7
static_detectable: 5
agent_judgable: 1
out_of_artifact: 1
---

# AST04 — Insecure Metadata: coverage matrix

This is the audit artifact `skills/AST04/SKILL.md` points at when it says the
static-detectable / agent-judgable / out-of-artifact split "is fixed in
`coverage-matrix.md`, not decided here". It is not a summary of the whitepaper's AST04
section. It states, per named scenario, what tier the scenario carries, why, and what
`skills/AST04/scripts/detector.py` actually executes against it — including where the
answer is "nothing".

**Authority chain.** `scenarios/registry.yaml` is authoritative on tier; this file
reproduces its tiering and may not diverge from it. `fixtures/manifest.yaml` is
authoritative on which fixture cases exist and what they are labeled against. The
`SCENARIO_TIERS` dict inside `skills/AST04/scripts/detector.py` is implementation and is
subordinate to both.

**What changed in v1.1.** Every one of AST04's five static-detectable scenarios now has
a deterministic check and a labeled fixture pair, and the corpus is run through the
detector by `detectors/fixture_loader.py` rather than sitting unread. Three claims this
file previously made are therefore retired, and each is recorded below rather than
quietly dropped: the two "**not implemented**" rows, the `tomllib`-swallows-the-finding
gap on AST04-S07, and the "no fixture loader" publication status.

## Scenario table

Legend for the detector column:

- A named function means a deterministic check ships and runs for that scenario.
- `—` means no deterministic check is possible from one package (agent-judgable or
  out-of-artifact); the tier column says which.

| Scenario | Whitepaper title | Tier | What the detector actually checks | Reason for the tier |
| --- | --- | --- | --- | --- |
| `AST04-S01` | Brand Impersonation | agent-judgable | `—` | `name`, `author` and `description` all ship in the package, so the evidence is in-artifact — but deciding that `google-workspace-integration` implies a vendor relationship its author does not have is a semantic judgement against world knowledge. A deterministic rule needs the trademark and vendor-namespace corpus the whitepaper's own mitigation assumes ("enforce brand/trademark protection … in the registry UI"), and no package carries it. |
| `AST04-S02` | Permission Understating | static-detectable | `detect_permission_understating()` — for every line of a bundled `.py`/`.sh`/`.js`/`.ts`/`.rb`/`.ps1` file carrying both an egress primitive (`curl`, `wget`, `requests.get`, `fetch`, `urlopen`, …) and an absolute `http(s)://` URL, extract the destination host and test it against `permissions.network.allow` default-deny and host-exact, the same rule `validators/usf.py::network_egress_allowed` applies. An allowlist containing `*` does not fire: breadth is AST03's finding, not this one. | Both sides of the contradiction ship together: the declared permission in the USF manifest and the egress call site in the bundled script. A declared-versus-observed cross-check decides it from package bytes alone. Requiring a literal host is what keeps prose and identifier names (`detect_unrestricted_network_fetch`) out of the result — the finding has to name a destination the manifest can be checked against. |
| `AST04-S03` | Risk Tier Spoofing | static-detectable | `detect_risk_tier_spoofing()` — re-nests the declared permission block into the USF shape, calls `validators/usf.py::derive_risk_tier` for the L0–L3 floor, and fires when the declared `risk_tier` ranks strictly below it. Declaring *above* the floor is conservative and does not fire; an absent tier does not fire, because there is no self-classification to contradict. | The whitepaper's mitigation states the check outright: "cross-reference `risk_tier` declarations against the permission manifest scope". The declared tier and the scope contradicting it are two fields of the same manifest. The derivation is this repository's one ladder rather than a second one invented in the detector, so the validator and the detector cannot give different answers to the same manifest. |
| `AST04-S04` | YAML Code Execution | static-detectable | `detect_yaml_injection()` — both halves. Raw-text scan of every shipped `.yaml`/`.yml` file, and of the *frontmatter block only* of every `.md` file, for a `!!python/…` or `!!ruby/…` construction tag; plus a scan of bundled `.py` for `yaml.unsafe_load(`, `Loader=yaml.UnsafeLoader`, or a bare `yaml.load(` with no `SafeLoader` within 200 characters. Either half firing is the finding. Nothing is ever deserialized. | The dangerous tag is a literal byte sequence in the frontmatter and the loader opt-in is a call site in bundled code; both are parse-time facts. Scanning only the frontmatter of a Markdown file, never its body, is deliberate: this repository's own `skills/AST04/SKILL.md` names `!!python/object` in prose, and documentation is not a payload. A package can ship the payload for a host loader it does not bundle, which is why the halves are OR-ed rather than AND-ed. |
| `AST04-S05` | Staged Loader | out-of-artifact | `—` | The defining condition is that the package pulled by the referenced `requirements.txt` is malicious, and that package is resolved off-artifact at install time. The staging structure is visible; the payload is not. |
| `AST04-S06` | JSON Prototype Pollution | static-detectable | `detect_json_injection()` — `json.loads` each `.json` file and walk the parsed tree for the key names `__proto__`, `constructor`, `prototype` at any depth. An in-package recursive merge (a `for (… in …)` loop assigning `target[key] = …` in bundled `.js`/`.ts`) is reported in the evidence as corroboration, and is deliberately **not** required. Malformed JSON is skipped. | Both halves are in the package in the whitepaper's example, but the whitepaper puts the exploiting merge in "Node.js runtimes that perform the merge" — which may be the host. Requiring an in-package merge site would therefore miss the common shape: a skill that ships only the poisoned `manifest.json`. The polluting key in shipped metadata is the package-side defining condition, and it has no legitimate purpose in a skill manifest. |
| `AST04-S07` | TOML / Config Injection | static-detectable | `detect_toml_injection()` — scan the config **text** for a redefined single-bracket `[table]` header (a `[[array_of_tables]]` legitimately repeats and does not fire), then `tomllib.loads` and flag any top-level key outside `{name, description, version, settings, permissions, metadata}`. | The overriding keys and the precedence-violating tables are literal structure in a shipped config file; a schema-plus-allowlist check over it decides them. The text scan runs *before* the parse on purpose: `tomllib` raises `TOMLDecodeError` on a redefined table, and parsing first meant the raise swallowed the very shape the scenario names. |

Re-derive the ids, titles and tiers in this table from the authority at rank 2,
so a reader can check the table rather than believe it:

```
python3 -c "import yaml; [print(s['id'], '|', s['title'], '|', s['tier']) for s in yaml.safe_load(open('scenarios/registry.yaml'))['scenarios'] if s['category']=='AST04']"
```

## Detector checks that are not whitepaper scenarios

`skills/AST04/scripts/detector.py` ships six CHECKS. Five map onto registry scenarios;
one does not. Three counts are in play here and the module keeps them in separate
tables: **seven** registry scenarios (`SCENARIO_TIERS`, keyed by canonical registry id
and carrying the registry's tier for each), **five** of them static-detectable
(`STATIC_DETECTABLE`, the F1 denominator), and **six** shipped checks (`CHECK_COVERAGE`,
keyed by check id — the table below). Reading any one of those as another is the
overclaim the keying split removed: while `SCENARIO_TIERS` was keyed by check slugs,
`node cli/bin/cli.js list` reported AST04 as deciding six scenarios.

| Detector check id | Maps to | `CHECK_COVERAGE` | Basis |
| --- | --- | --- | --- |
| `AST04-permission-understating` | `AST04-S02` | `full` | Named scenario, which the registry independently tiers `static-detectable`. |
| `AST04-risk-tier-spoofing` | `AST04-S03` | `full` | Named scenario, which the registry independently tiers `static-detectable`. |
| `AST04-yaml-injection` | `AST04-S04` | `full` | Named scenario, which the registry independently tiers `static-detectable`. |
| `AST04-json-injection` | `AST04-S06` | `full` | Named scenario, which the registry independently tiers `static-detectable`. |
| `AST04-toml-injection` | `AST04-S07` | `full` | Named scenario, which the registry independently tiers `static-detectable`. |
| `AST04-invisible-unicode-smuggling` | *no named AST04 scenario* | `category-precondition` | Category precondition, not a scenario. It derives from AST04's preventive-mitigation list ("flag suspicious patterns … specifically ASCII smuggling, base64 payloads, and zero-width characters invisible to human reviewers") and from the ClawHub/Snyk `toxicskills-goof` evidence bullet. The registry files the closest *named* scenario under AST08 (`AST08-S02`, Obfuscated Instruction), and the scan logic is shared with AST08 via `detectors/scaffold.py::detect_invisible_unicode_smuggling`. It must never be counted as coverage of an AST04 scenario, and it has no fixture pair. Because of it, the module's `F1_SCOPE` is `mixed-proxy` even though every corpus-labeled check is `covers: full`. |

The two `f1_scope` fields answer different questions and are both correct: the module's
`F1_SCOPE` is computed over every check the module ships (five `full` plus one
`category-precondition` = `mixed-proxy`), while `fixtures/manifest.yaml`'s AST04
`f1_scope` is computed over the checks the *corpus labels* (five `full` =
`scenario-level`). The unicode check has no fixture pair, so it enters no published
number.

## Declared and uncovered

One AST04 scenario is out-of-artifact. It is declared here and never enters the fixture
corpus (`detectors/engine.py::run_category` raises `OutOfArtifactFixtureError` if one
ever does).

### `AST04-S05` — Staged Loader

- **Why one package cannot decide it.** The scenario is not "a skill references a
  dependency file"; it is "the package that dependency file resolves to executes a
  malicious payload at install time". The `requirements.txt` reference is in the
  artifact. What the reference resolves to is not: it is fetched from an index at
  install time, is version-range dependent, and can change between the review fetch and
  the install fetch without any edit to the skill. A detector deciding this from the
  package alone would be deciding it from the *name* of a dependency, which is
  `AST04-S01`'s problem restated, not this one.
- **Enabling precondition the package shows** (`artifact_signal` in
  `scenarios/registry.yaml`): a `SKILL.md` referencing an install-time-executing
  dependency file — `requirements.txt`, a `package.json` with a `postinstall`, a
  `setup.py` — whose resolved contents are not shipped in the package. This is a partial
  proxy. It is not labeled by any AST04 fixture and is not published as coverage.
- **Evidence that would decide it.** (1) The resolved dependency set at install time —
  a lockfile pinning exact versions and hashes, or the install transcript — plus (2) the
  contents of each resolved package, plus (3) execution of its install-time hooks under
  observation in a sandbox. That is the whitepaper's own mitigation ("treat
  `requirements.txt`, `package.json` and `pyproject.toml` as untrusted code whose
  installation is sandboxed"), and it is an install-pipeline capability, not a static
  package property. A registry-side or CI-side scanner with a resolver could decide it;
  a single-package detector cannot.

### Agent-judgable (in-artifact, not mechanically decidable)

Listed separately because these are *not* uncovered — the evidence is in the package —
but they are scored by the judge harness, never by a deterministic detector, and they
never enter the F1 denominator.

- **`AST04-S01` Brand Impersonation.** Evidence needed to decide it deterministically: a
  trademark / official-vendor-namespace corpus plus a publisher-identity attestation
  binding the author to the named brand. Absent that corpus, the decision is a semantic
  similarity judgement, which is exactly what a judge is for.

## F1 denominator statement

**Which scenarios count.** Only scenarios this file tiers `static-detectable` may enter
AST04's F1 denominator — `AST04-S02`, `AST04-S03`, `AST04-S04`, `AST04-S06`,
`AST04-S07`. `AST04-S01` (agent-judgable) is reported separately by the judge harness
and never folded in; `AST04-S05` (out-of-artifact) is reported as declared-and-uncovered
above and never appears in the corpus at all. This matches the implementation:
`detectors/engine.py::run_category` scores only `Tier.STATIC_DETECTABLE` cases and
returns `agent_judgable` and `declared_uncovered` as separate tuples.

**What is actually measurable today: all five.** Each has a labeled vulnerable/clean
fixture pair at `covers: full`, and each pair is scored over its own two cases by
`detectors/fixture_loader.py::run_corpus`, which loads a fixture directory exactly the
way `cli/lib/bridge.py` loads a candidate under audit. Per-pair scoring is deliberate: a
check that fired on everything would take a false positive on its own clean case rather
than disappearing into a category-wide average.

Measured (`python3 detectors/fixture_loader.py AST04`):

| Corpus check | Detector check | Registry scenario | TP | FP | FN | TN | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `AST04-S1` | `AST04-yaml-injection` | `AST04-S04` | 1 | 0 | 0 | 1 | 1.00 |
| `AST04-S2` | `AST04-json-injection` | `AST04-S06` | 1 | 0 | 0 | 1 | 1.00 |
| `AST04-S3` | `AST04-toml-injection` | `AST04-S07` | 1 | 0 | 0 | 1 | 1.00 |
| `AST04-S4` | `AST04-permission-understating` | `AST04-S02` | 1 | 0 | 0 | 1 | 1.00 |
| `AST04-S5` | `AST04-risk-tier-spoofing` | `AST04-S03` | 1 | 0 | 0 | 1 | 1.00 |

**Publication status.** `fixtures/manifest.yaml` records
`published_f1: "scenario-level 1.00 (n=10)"`. Read it with the caveat it deserves: ten
cases is the gate-4 floor, not statistical power, and every case was authored by the
same hand that wrote the check it scores. What the number does establish is the property
whose absence blocked publication — each check separates its vulnerable case from its
clean case, and no check fires on any clean fixture in the category. The clean cases are
built to make that non-trivial: `C4` ships the same unsafe recursive merge as `V3`, `C8`
makes the same `curl` calls as `V7`, and `C10` holds the same destructive shell-plus-write
scope as `V9` and differs only in declaring it honestly.

AST04 does publish an F1 — its static-detectable tier is non-empty, so the never-pad rule
that silences AST05 and AST09 does not apply here.

## Corpus entitlement and actual count

| Quantity | Value | Source |
| --- | --- | --- |
| Registry scenarios in AST04 | 7 | `scenarios/registry.yaml` |
| Registry static-detectable | 5 | `AST04-S02`, `S03`, `S04`, `S06`, `S07` |
| Entitlement at full registry coverage — `max(6, 2 × 5)` | **10** | `cases_at_full_static_coverage` |
| Labeled detectable checks in the corpus | 5 | `AST04-S1` … `AST04-S5` in `fixtures/manifest.yaml` |
| Declared expected cases — `max(6, 2 × 5)` | **10** | `declared_expected_cases` |
| Fixture files actually present under `fixtures/AST04/` | **10** | 5 vulnerable + 5 clean, class-balanced |

The corpus satisfies the locked gate-4 formula and is at full coverage of the registry's
static tier: `uncovered_static_detectable` is now empty. No case was padded to reach any
number — every one of the ten is bound to a scenario the registry independently tiers
static-detectable, and the two categories the whitepaper leaves undecidable are absent
by tier rather than by omission.

Present on disk, all ten matching the manifest's declared paths:

```
fixtures/AST04/V1-yaml-frontmatter-injection/SKILL.md   vulnerable  -> AST04-S04
fixtures/AST04/C2-yaml-frontmatter-injection/SKILL.md   clean       -> AST04-S04
fixtures/AST04/V3-json-metadata-injection/SKILL.md      vulnerable  -> AST04-S06
fixtures/AST04/C4-json-metadata-injection/SKILL.md      clean       -> AST04-S06
fixtures/AST04/V5-toml-metadata-injection/SKILL.md      vulnerable  -> AST04-S07
fixtures/AST04/C6-toml-metadata-injection/SKILL.md      clean       -> AST04-S07
fixtures/AST04/V7-permission-understating/SKILL.md      vulnerable  -> AST04-S02
fixtures/AST04/C8-permission-understating/SKILL.md      clean       -> AST04-S02
fixtures/AST04/V9-risk-tier-spoofing/SKILL.md           vulnerable  -> AST04-S03
fixtures/AST04/C10-risk-tier-spoofing/SKILL.md          clean       -> AST04-S03
```

Each directory is a package, not a single file. The three pre-existing pairs carried
their payload as a *string inside SKILL.md frontmatter* — a `frontmatter_raw:` block
scalar holding a quoted `!!python/object` tag, a bare JSON object pasted between the
frontmatter fences, a duplicate TOML table in the same place. None of those is a file any
scan reads, and none would execute in any loader. They were rewritten as real packages
(`metadata.yaml` + `scripts/loader.py`, `manifest.json` + `scripts/merge.js`,
`config.toml`), which is a fixture-authorship correction and is recorded as such in
`fixtures/manifest.yaml`'s per-check `reason` fields.

## Reconciliation debt

Open items a reviewer should expect to see closed before AST04's number is treated as
more than a floor. Recording them here is the point of the artifact.

1. **Ten cases is the floor, not power.** Every check is scored over exactly one
   vulnerable and one clean case. That is enough to prove discrimination and nowhere near
   enough to estimate a rate. Adding cases means adding labeled checks under the gate-4
   formula, so growth has to come from new scenario coverage, not from padding.
2. **The fixtures and the checks share an author.** The corpus cannot detect a blind spot
   that both the check and its fixture were written around. An adversarial corpus authored
   against the checks — not with them — is the missing instrument.
3. **`AST04-S06` is decided on the polluting key alone.** The merge site is reported when
   the package ships one, and a package that ships neither key nor merge is indistinguishable
   from one whose host performs the merge safely. This is argued in the scenario table
   rather than treated as settled.
4. **`AST04-S02` needs a literal destination.** An egress call site whose URL is assembled
   at runtime (`base + path`) carries no host for the manifest to be checked against and is
   not flagged. Constant-folding a bounded expression would extend the check; it is not
   implemented.
5. **One detector check maps to no AST04 scenario.** `AST04-invisible-unicode-smuggling`
   is a category precondition, must not be counted toward AST04 coverage, and has no
   fixture pair.

## Change control

The tiering above is bound to `tier_lock_hash`
`59f45799d2b1b4522f230694615b3d283d91c6c436373f14f7fa5be025b808f0`
(`validators/tier_lock.py`). It was recomputed when `AST04-S4` and `AST04-S5` were added
to the corpus: the lock hashes this category's whole `<id>:<tier>` set, so labeling two
new checks moves it even though no existing scenario changed tier. The registry-side lock
`registry_tier_lock` is unchanged, because `scenarios/registry.yaml` did not change.

Moving any AST04 scenario between tiers invalidates every fixture case labeled under the
old tier, changes the hash again, and requires the category's corpus to be re-labeled and
its judge run repeated before an F1 may be republished (ADR-0004, S-011).
