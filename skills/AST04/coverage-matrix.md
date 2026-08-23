---
artifact: coverage-matrix
category: AST04
category_name: Insecure Metadata
version: "1.0"
created: 2026-08-23
task: T-3.1b
tier_authority: scenarios/registry.yaml
corpus_authority: fixtures/manifest.yaml
detector: skills/AST04/scripts/detector.py
tier_lock_hash: "16a47c857a31fd6ac2bc7e441933b1232023f3b964727100cf3d8c8e9c9283ba"
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
`SCENARIO_TIERS` dict inside `skills/AST04/scripts/detector.py` is an interim
declaration by its own docstring ("superseded by … T-3.1's authored
`skills/AST04/coverage-matrix.md` once locked") — where it disagrees with this file,
this file wins and the module is the thing that must be reconciled. The delta is
recorded in [Detector checks that are not whitepaper scenarios](#detector-checks-that-are-not-whitepaper-scenarios)
and [Reconciliation debt](#reconciliation-debt).

## Scenario table

Legend for the detector column:

- A named function means a deterministic check ships and runs for that scenario.
- **not implemented** means the registry tiers the scenario static-detectable but no
  check for it exists in this skill's detector. This is coverage debt, not a
  detectability claim.
- `—` means no deterministic check is possible from one package (agent-judgable or
  out-of-artifact); the tier column says which.

| Scenario | Whitepaper title | Tier | What the detector actually checks | Reason for the tier |
| --- | --- | --- | --- | --- |
| `AST04-S01` | Brand Impersonation | agent-judgable | `—` | `name`, `author` and `description` all ship in the package, so the evidence is in-artifact — but deciding that `google-workspace-integration` implies a vendor relationship its author does not have is a semantic judgement against world knowledge. A deterministic rule needs the trademark and vendor-namespace corpus the whitepaper's own mitigation assumes ("enforce brand/trademark protection … in the registry UI"), and no package carries it. |
| `AST04-S02` | Permission Understating | static-detectable | **not implemented** | Both sides of the contradiction ship together: the declared permission in the USF manifest and the egress call site in the bundled script. A declared-versus-observed cross-check decides it from package bytes alone, so it is static-detectable — but no function in this detector reads `permissions.network.allow` against fetch call sites in bundled code. `skills/AST04/SKILL.md` decision rule 4 asserts the closing check is behavioral (sandboxed runtime observation); the registry's static tier rests on the narrower, purely structural half — a call to a host absent from the declared allowlist — which is decidable at rest. |
| `AST04-S03` | Risk Tier Spoofing | static-detectable | **not implemented** | The whitepaper's mitigation states the check outright: "cross-reference `risk_tier` declarations against the permission manifest scope". The declared tier and the scope contradicting it are two fields of the same manifest. The derivation exists in this repo — `validators/usf.py::derive_risk_tier` maps a permission set onto L0–L3 — but nothing in `skills/AST04/scripts/detector.py` imports or calls it, and no fixture pair exercises it. |
| `AST04-S04` | YAML Code Execution | static-detectable | `detect_yaml_injection()` — scans every `.py` file in the package for `yaml.unsafe_load(`, `Loader=yaml.UnsafeLoader`, or a bare `yaml.load(` with no `SafeLoader` inside a 200-character window after the call. It does **not** scan `.yaml`/frontmatter bytes for the `!!python/object` tag. | The dangerous tag is a literal byte sequence in the frontmatter and the loader opt-in is a call site in bundled code; both are parse-time facts. The detector deliberately implements only the loader half, per `SKILL.md`'s decision rule that PyYAML has been `FullLoader`-safe since 5.1 so the loader choice is the load-bearing finding. Consequence to audit: a package that carries the `!!python/object` payload but ships no Python loader of its own is not flagged by this check. |
| `AST04-S05` | Staged Loader | out-of-artifact | `—` | The defining condition is that the package pulled by the referenced `requirements.txt` is malicious, and that package is resolved off-artifact at install time. The staging structure is visible; the payload is not. |
| `AST04-S06` | JSON Prototype Pollution | static-detectable | `detect_json_injection()` — `json.loads` each `.json` file and walk the parsed tree for the key names `__proto__`, `constructor`, `prototype` at any depth. Malformed JSON is skipped. | Both halves are in the package: the polluting key in the manifest and the unsafe recursive-merge call site in bundled JavaScript. The detector implements the key half only — there is no scan of bundled `.js` for a recursive merge — so it flags the precondition the whitepaper is explicit is not sufficient on its own ("`JSON.parse` itself only creates an own property"). Partial coverage of a scenario the registry tiers fully decidable. |
| `AST04-S07` | TOML / Config Injection | static-detectable | `detect_toml_injection()` — `tomllib.loads` each `.toml` file and flag any top-level key outside `{name, description, version, settings, permissions, metadata}`. | The overriding keys and the precedence-violating tables are literal structure in a shipped config file; a schema-plus-allowlist check over the parsed config decides it. Coverage is partial and in one specific way: the duplicate-table override named in the registry reason (a second `[permissions]` table) makes `tomllib` raise `TOMLDecodeError`, which the function swallows with `continue`, so the duplicate-table shape is skipped rather than flagged. The implemented check catches unexpected *new* top-level tables, not redefinitions of expected ones. |

## Detector checks that are not whitepaper scenarios

`skills/AST04/scripts/detector.py` declares four scenario ids. Three map onto registry
scenarios; one does not.

| Detector scenario id | Maps to | Basis |
| --- | --- | --- |
| `AST04-yaml-injection` | `AST04-S04` | Named scenario. |
| `AST04-json-injection` | `AST04-S06` | Named scenario. |
| `AST04-toml-injection` | `AST04-S07` | Named scenario. |
| `AST04-invisible-unicode-smuggling` | *no named AST04 scenario* | Category precondition, not a scenario. It derives from AST04's preventive-mitigation list ("flag suspicious patterns … specifically ASCII smuggling, base64 payloads, and zero-width characters invisible to human reviewers") and from the ClawHub/Snyk `toxicskills-goof` evidence bullet. The registry files the closest *named* scenario under AST08 (`AST08-S02`, Obfuscated Instruction), and the scan logic is shared with AST08 via `detectors/scaffold.py::detect_invisible_unicode_smuggling`. It must never be counted as coverage of an AST04 scenario, and it has no fixture pair. |

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
returns `agent_judgable` and `declared_uncovered` as separate tuples, and
`detectors/scaffold.py::f1_report` intersects each fixture's expected set with the
module's `STATIC_DETECTABLE` before counting.

**What is actually measurable today.** Of those five, the fixture corpus labels three
(`AST04-S04`, `AST04-S06`, `AST04-S07`, all at `covers: full` in
`fixtures/manifest.yaml`). `AST04-S02` and `AST04-S03` are the declared coverage debt —
they are in the denominator's *scope* but have neither a detector check nor a fixture
pair, so no F1 computed today speaks to them. Any published AST04 F1 must be reported
alongside that two-scenario gap, or it silently narrows the denominator to the three
scenarios the corpus happens to cover.

**Publication status.** `fixtures/manifest.yaml` records `published_f1: pending-detector`
for AST04, and that is accurate: no loader in this repo converts a fixture `SKILL.md`
into the `{"manifest": …, "files": …}` mapping the detector consumes. Constructed
directly as `{"files": {"SKILL.md": <bytes>}, "manifest": {}}`, all four AST04 checks
return `detected=False` on all six fixtures — vulnerable and clean alike — because the
YAML check scans `.py` files, the JSON check scans `.json` files, and the TOML check
scans `.toml` files, while every fixture is a single `SKILL.md` carrying its payload as
frontmatter text. AST04 therefore has a **wiring gap, not a detection result**. The
honest report until that gap closes is `pending-detector`, not a number.

AST04 does publish an F1 in principle — its static-detectable tier is non-empty, so the
never-pad rule that silences AST05 and AST09 does not apply here.

## Corpus entitlement and actual count

| Quantity | Value | Source |
| --- | --- | --- |
| Registry scenarios in AST04 | 7 | `scenarios/registry.yaml` |
| Registry static-detectable | 5 | `AST04-S02`, `S03`, `S04`, `S06`, `S07` |
| Entitlement at full registry coverage — `max(6, 2 × 5)` | **10** | `cases_at_full_static_coverage` |
| Labeled detectable checks in the corpus | 3 | `AST04-S1`, `AST04-S2`, `AST04-S3` in `fixtures/manifest.yaml` |
| Declared expected cases — `max(6, 2 × 3)` | **6** | `declared_expected_cases` |
| Fixture files actually present under `fixtures/AST04/` | **6** | 3 vulnerable + 3 clean, class-balanced |

The corpus satisfies the locked gate-4 formula against what it labels (6 = max(6, 2×3))
and is four cases short of the 10 that full coverage of the registry's static tier would
demand. The shortfall is exactly the two unlabeled scenarios `AST04-S02` and
`AST04-S03`, which `fixtures/manifest.yaml` lists under `uncovered_static_detectable`.
No case was padded to reach any number: every one of the six is bound to a scenario the
registry independently tiers static-detectable.

Present on disk, all six matching the manifest's declared paths:

```
fixtures/AST04/V1-yaml-frontmatter-injection/SKILL.md   vulnerable  -> AST04-S04
fixtures/AST04/C2-yaml-frontmatter-injection/SKILL.md   clean       -> AST04-S04
fixtures/AST04/V3-json-metadata-injection/SKILL.md      vulnerable  -> AST04-S06
fixtures/AST04/C4-json-metadata-injection/SKILL.md      clean       -> AST04-S06
fixtures/AST04/V5-toml-metadata-injection/SKILL.md      vulnerable  -> AST04-S07
fixtures/AST04/C6-toml-metadata-injection/SKILL.md      clean       -> AST04-S07
```

## Reconciliation debt

Open items a reviewer should expect to see closed before AST04 publishes a number.
Recording them here is the point of the artifact; none of them is silently absorbed.

1. **No fixture loader.** Nothing maps `fixtures/AST04/*/SKILL.md` onto the detector's
   `pkg` shape. Until it exists, AST04's F1 is `pending-detector`.
2. **Two static-detectable scenarios have no check.** `AST04-S02` (Permission
   Understating) and `AST04-S03` (Risk Tier Spoofing). `AST04-S03`'s derivation already
   exists at `validators/usf.py::derive_risk_tier` and is simply not wired in.
3. **Two implemented checks cover their scenario partially.** `AST04-S06` matches the
   polluting key but not the unsafe recursive merge the whitepaper says is required for
   exploitation; `AST04-S07` cannot see the duplicate-table override because `tomllib`
   raises before the allowlist runs.
4. **One detector check maps to no AST04 scenario.** `AST04-invisible-unicode-smuggling`
   is a category precondition. It must not be counted toward AST04 coverage, and it
   currently has no fixture pair.

## Change control

The tiering above is bound to `tier_lock_hash`
`16a47c857a31fd6ac2bc7e441933b1232023f3b964727100cf3d8c8e9c9283ba`
(`validators/tier_lock.py`). Moving any AST04 scenario between tiers invalidates every
fixture case labeled under the old tier, changes the hash, and requires the category's
corpus to be re-labeled and its judge run repeated before an F1 may be republished
(ADR-0004, S-011).
