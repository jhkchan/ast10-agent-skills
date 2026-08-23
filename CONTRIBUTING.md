# Contributing

Thanks for looking. Before anything else, two things about what this repo is.

**It is not an OWASP project.** The repository name says OWASP; the project is not
one, is not published by OWASP, and carries no OWASP endorsement or review. The
[OWASP Agentic Skills Top 10](https://owasp.org/) whitepaper is the *source
material* this repo implements, and credit for the taxonomy, the attack-scenario
catalog, the decision tree, and the Universal Skill Format proposal belongs to
that project and its contributors. Ken Huang leads it. See the README's
disclaimer for the full statement — a contribution that blurs that line will be
asked to change, however good the code is.

**Every number here is a claim someone can check.** The repo's whole point is
that a clean scan result is a statement about coverage, not about safety. So the
review bar is not "does it work" but "does it say what it actually measured".
Most of what follows is that rule applied to specific files.

Local setup is three commands:

```bash
pip install pytest pyyaml jsonschema
python3 -m pytest -q          # the whole assertion layer
ruff check .                  # must be clean; CI runs the same
```

---

## Adding a skill

A skill is a directory under `skills/`. The eleven that ship today are the ten
AST categories plus `advisory`; a twelfth would be a sibling, not a subfolder.

```
skills/<ID>/
  SKILL.md              required — frontmatter + the knowledge
  skill.usf.yaml        required — Universal Skill Format v1.0 manifest
  coverage-matrix.md    required for a detector skill
  scripts/detector.py   required for a detector skill
  scripts/test_*.py     required alongside any script
  references/*.md       optional — long-form material SKILL.md points at
```

**1. `SKILL.md` carries knowledge, not mechanism.** This repo follows a
deliberate split: `SKILL.md` holds the decision rules — what separates this
category from the adjacent ones, which preventive controls fail and under what
conditions, what makes a finding *this* category rather than a neighbour's.
Executable logic lives in `scripts/`; long-form material lives in
`references/`. A `SKILL.md` that is mostly a procedure has the split backwards.
No skill in this repository ships a `references/` directory today — the long-form
source is the whitepaper, which is not redistributable here — so if you add one,
re-stamp the manifest: `references/*.md` is inside the `content_hash` surface
(`scripts/content_hash.py`) and every stamped digest here currently covers
`SKILL.md` plus `scripts/*.py` and nothing else.

The frontmatter needs a `name` and a `description`. The `name` is the
identifier a runtime matches invocations against, so it must equal the entry in
`.claude-plugin/marketplace.json` — `tests/test_packaging.py` fails the build if
those two drift. Write the `description` for *retrieval*: it is the only text an
agent sees when deciding whether to load the skill, so it should name the
concrete symptoms and the triage decisions the skill can settle, not summarize
the category in the abstract.

**2. `skill.usf.yaml` must validate.**

```bash
python3 validators/usf.py skills/<ID>/skill.usf.yaml
```

The validator recomputes the `risk_tier` floor from the declared permissions
rather than trusting the field, and reports the signature state instead of
treating `unsigned` as valid. Declare the narrowest permissions the skill
actually uses, and keep `deny_write` populated even when `write` is empty —
`write: []` is a property of this package, `deny_write` is a floor that has to
survive a port to a runtime whose default is write-everything.

Regenerate the content hash whenever the shipped surface changes:

```bash
python3 validators/usf.py --update-content-hash skills/<ID>/skill.usf.yaml
```

Note that the unsigned / no-DID **warnings are expected** and are the repo's
honest declared posture, which is why CI does not run the validator with
`--strict`. Do not silence them by inventing an identity anchor that anchors to
nothing — publishing a DID or public key that nobody can verify manufactures
exactly the false trust signal AST10 warns about.

**3. List the skill in the marketplace manifest.** Add a `{name, description}`
entry to `.claude-plugin/marketplace.json` and bump `skill_count`.

**4. Point the repo's own detectors at your skill.**

```bash
python3 scripts/dogfood.py
```

This runs every detector this repo ships over every skill package this repo
ships, including your new one, and fails on any finding. If your skill trips a
detector, fix it. If — and only if — the finding is genuinely a false positive
on your own source, add a waiver to `config/dogfood_waivers.yml` with all four
fields: `skill`, `scenario`, `evidence_contains` (which pins the waiver to the
exact file), and a `reason` that explains why. A waiver that stops matching
anything fails the job too, so the file cannot quietly accumulate dead entries.

Rewording a detector's evidence string so it stops matching its own scan is not
a fix. That is the AST08 scanner-evasion pattern turned inward, and review will
treat it as such.

---

## Tiering rules a new scenario must declare

`scenarios/registry.yaml` is **authoritative on tier**. Every scenario the
whitepaper names appears there exactly once, with the whitepaper's verbatim
title. Adding a scenario means adding an entry with all of:

| Field | What it must say |
| --- | --- |
| `id` | `AST<NN>-S<NN>`, unique |
| `category` | the owning `AST<NN>` |
| `title` | the whitepaper's title, **verbatim** — not a paraphrase |
| `description` | the attack in the whitepaper's own terms |
| `tier` | one of the three below |
| `reason` | why that tier, in prose, specific to this scenario |
| `artifact_signal` | required *only* for `out-of-artifact` scenarios that have a partial in-package proxy |

The three tiers, and the test for each:

**`static-detectable`** — a deterministic rule over the package's own bytes and
structure (SKILL.md, frontmatter, bundled scripts, lockfiles, the USF manifest)
decides the scenario's **defining condition**. No prose intent-reading, no state
from outside the package.

**`agent-judgable`** — all the evidence is inside the package, but deciding it
needs semantic judgement of prose, naming, or stated purpose. In-artifact, not
mechanically decidable. Typosquatting lives here: the dependency names are right
there in the lockfile, but deciding that `gogle-workspace` is a deliberate
near-miss needs world knowledge of what the legitimate name is.

**`out-of-artifact`** — not decidable from one package at all. The defining
condition lives in version history, remotely hosted content, another package,
the host runtime, the registry's state, or an organisation's process.

### The defining-condition rule

This is the one that gets argued about, so it is worth stating flatly: **a
scenario is `static-detectable` only if the package decides the scenario
itself.** Where the package can show an enabling *precondition* while the
defining event happens somewhere else, the scenario stays `out-of-artifact` and
the precondition goes in `artifact_signal`, explicitly labeled a partial proxy.
It is never promoted to coverage of the scenario.

Two thirds of the whitepaper's named attack surface is currently
`out-of-artifact` — 34 of 62. That number is supposed to be uncomfortable. It is
the honest one, and a PR that improves it by re-tiering rather than by building
a detector will be rejected.

### Tier changes invalidate downstream work

A category's fixture labels and its published F1 are only valid for the tiering
they were labeled against. `validators/tier_lock.py` binds them with a hash over
every scenario's `id:tier` pair:

```bash
python3 validators/tier_lock.py fixtures/manifest.yaml
```

If you re-tier a scenario, this fails, and that is working as intended. Re-tier
means: recompute the affected category's `tier_lock_hash` in
`fixtures/manifest.yaml` **and** the one recorded in its `coverage-matrix.md`,
re-label the fixture corpus, and re-run the judge before republishing any F1.
Updating the hash on its own, without redoing the labeling, silently
republishes a number the corpus was never labeled against.

---

## A new detector needs fixtures before it can claim an F1

This is a hard rule, not a preference.

**Fixtures first.** A detector may not publish a precision, recall, or F1 figure
until a hand-labeled fixture corpus exists for it in `fixtures/<ID>/` and is
declared in `fixtures/manifest.yaml`. Code that runs is not evidence that it
works.

**Corpus size is a formula, not a judgement call:**

```
cases = max(6, 2 × count(detectable_scenarios))
```

class-balanced between vulnerable (`V*`) and clean (`C*`) cases, drawn **only**
from the category's `static-detectable` tier. Six is a floor, not a target.

**An empty detectable tier publishes no F1.** A category with nothing
static-detectable reports `declared-and-uncovered` and no number. Do not pad the
corpus to manufacture one. `detectors/scaffold.f1_report()` enforces this in
code, and the categories that ship in exactly that state say so — `AST09`, whose seven
named scenarios are all out-of-artifact, is the clearest case and its
`skills/AST09/scripts/detector.py` derives its empty `DETECTORS` map from its empty
static-detectable tier rather than merely asserting it.

**Zero denominators report `0.0`, never `1.0`.** A corpus where nothing was
detected must not come back as a perfect score. Both `detectors/scaffold.py` and
`detectors/engine.py` already do this; a new reporter must match.

**Say what the corpus actually measures.** Each declared check in
`fixtures/manifest.yaml` carries a `covers` field with three legal values, and
picking the flattering one is the failure this field exists to prevent:

- `full` — the registry tiers every linked scenario `static-detectable`, so the
  corpus measures the scenario itself.
- `artifact-signal-only` — the linked scenario is **not** `static-detectable`;
  the corpus measures its `artifact_signal` precondition and must not be
  reported as coverage of the scenario. The category's status becomes
  `proxy-covered`.
- `category-precondition` — the check derives from the category's preventive
  mitigations rather than from any named scenario, and must state a
  `derivation`.

**Fixtures bound to the wrong tier are a hard error, not a warning.**
`detectors/engine.run_category()` raises `OutOfArtifactFixtureError` on a
fixture pointing at an out-of-artifact scenario and
`UnregisteredScenarioFixtureError` on an unknown `scenario_id`, rather than
letting either silently shrink the F1 denominator.

**Update the coverage matrix.** `skills/<ID>/coverage-matrix.md` must exhaust
the category — every registry scenario appears exactly once with the registry's
tier and the whitepaper's verbatim title, a written reason, and a statement of
what the detector actually checks. It also lists every out-of-artifact scenario
under "Declared and uncovered" with the evidence that *would* decide it, because
S-003 requires the tier be published, not merely excluded. The tests in
`tests/test_coverage_matrix*.py` recompute all of this from the sources rather
than trusting the prose.

---

## The judge layer is local, not CI

CI runs the deterministic layer only: pytest, ruff, the USF validator, the
tier-lock drift check, and the dogfood pass. The LLM-judge run
(`scripts/judge_harness.py` → `scripts/ship_floor.py`) needs Bedrock
credentials, a local `claude` CLI, and a z.ai key, and is **maintainer-only** —
no cloud credentials are configured for the workflow and none should be. The
maintainer runs it locally and commits the scorecard artifacts so reviewers diff
recorded scores instead of trusting an unreproducible CI run.

The ship gate is pooled across judges: mean ≥ 108 **and** mean − stdev ≥ 105
**and** every per-dimension floor met, over at least `MIN_ROUNDS` pooled
judgments. A provider that could not be reached is declared in
`config/audit.yml` with a recorded reason — never silently averaged as zero and
never dropped without a record.

---

## Licensing and attribution

Contributions are accepted under the [Apache License 2.0](LICENSE), the license
this repo ships under.

New dependencies and any vendored source must land in
[`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md) in the same PR, with the
upstream, copyright holder, license, and — for vendored code — the exact pinned
commit. Apache-2.0, MIT, BSD, ISC and PSF-2.0 are acceptable; GPL, LGPL, AGPL,
SSPL, BUSL, Commons Clause and CC-BY-NC require review before the code lands.
Vendored files are pinned snapshots: re-vendor at a new commit and record it,
rather than editing a vendored file in place, or the drift audit stops meaning
anything.
