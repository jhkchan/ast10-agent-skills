# Architecture

How the pieces of this repository bind to each other, and — more importantly — which one
wins when two of them disagree.

This repository is an independent community implementation of the OWASP Agentic Skills
Top 10. It is **not** an official OWASP project and carries no OWASP endorsement. See
[`../README.md`](../README.md).

---

## The one-paragraph version

The whitepaper enumerates attack scenarios. `scenarios/registry.yaml` records every one of
them with a **detectability tier** and a written reason. Each category's
`coverage-matrix.md` turns that tiering into an F1 contract — what this package claims to
decide, what it refuses to claim, and the corpus arithmetic behind the number. `fixtures/`
holds the class-balanced evidence, `skills/<AST>/scripts/detector.py` holds the checks, `SKILL.md`
holds the knowledge an agent needs to use them, and `skill.usf.yaml` declares what the
package is allowed to touch. The judge matrix scores the `SKILL.md` bodies against a
pinned rubric; `scripts/ship_floor.py` decides whether the result ships.

---

## Authority chain

Every coverage matrix opens with this ranking, and it is the single most load-bearing
thing in the repository. When two artifacts disagree, the lower rank is a bug.

| Rank | Artifact | Authoritative on |
| --- | --- | --- |
| 1 | The [OWASP Agentic Skills Top 10 **v1.0**](https://owasp.org/www-project-agentic-skills-top-10/assets/publications/ast10-top10-whitepaper-2.pdf) whitepaper's "Attack Scenarios" body for that category | the enumeration — how many scenarios exist, and their titles verbatim |
| 2 | `scenarios/registry.yaml` | the **tier** of each scenario, and the written reason for it |
| 3 | `skills/<AST>/coverage-matrix.md` | the F1 denominator, the corpus accounting, the coverage debt |
| 4 | `fixtures/manifest.yaml` | which fixture case is labeled against which check |
| 5 | `skills/<AST>/scripts/detector.py` | implementation only — subordinate to rank 2 |

A detector module's `SCENARIO_TIERS` is a **mirror of the registry, not an opinion about
it**: it maps `scenarios/registry.yaml`'s canonical scenario ids (`AST07-S01`) to the tier
the registry assigns them, enumerates the category completely, and says nothing whatever
about any individual check. A module never invents a tier, and there is no such thing as
an interim one — where the module and the registry ever differ, the module is the bug.
`tests/test_scenario_tiers_are_registry_keyed.py` enforces that over all ten categories.

That test exists because the modules did not always agree on what the table's KEYS were.
AST01–AST06 keyed it by their own check slugs (`AST01-content-hash-missing`) while
AST07–AST10 keyed it by registry ids, and the divergence stayed invisible until something
counted the table. `node cli/bin/cli.js list` does: under check-keying it printed
`AST01 [static-detectable x10]` — ten *checks* wearing a *scenario* tier label — against a
registry that rules seven AST01 scenarios static-detectable. `list` now prints the two
quantities under their own nouns ("11 scenarios: 7 static-detectable … · 10 checks
shipped") for the same reason.

The per-check question is a second table's job. `CHECK_COVERAGE`, keyed by check id in the
same module, answers "does this check decide a named scenario?" using
`fixtures/manifest.yaml`'s own vocabulary — `full`, `artifact-signal-only`,
`category-precondition`. Collapsing the two is how the same
predicate came to be ruled `static-detectable` where it let a detector claim coverage and
`artifact_signal`-only where counting it would have obliged someone to build one. The
registry closes the other side of that with `artifact_signal_decidable` and
`artifact_signal_checks`; `tests/test_tier_doctrine_symmetry.py` fails if either file
moves without the other, and `f1_report` returns the module's `F1_SCOPE` beside every
number so a proxy F1 cannot be quoted as scenario coverage.

---

## The artifacts, in dependency order

### `scenarios/registry.yaml` — 62 scenarios, each with a tier

The spine. One entry per named whitepaper scenario, carrying `id`, `category`, `title`
(verbatim), `tier`, a written `reason`, and an `artifact_signal` where one exists.

Three tiers, defined in
[`adr/0004-per-scenario-detectability-contract.md`](adr/0004-per-scenario-detectability-contract.md):

| Tier | Meaning | Enters an F1 denominator? |
| --- | --- | --- |
| `static-detectable` | A deterministic rule over the package's own bytes decides the scenario's defining condition. | Yes — this tier *is* the denominator. |
| `agent-judgable` | The evidence is in the package, but the decision needs semantic judgement. | No. Reported as a separate list, never folded in. |
| `out-of-artifact` | Not decidable from one package at all — needs runtime telemetry, world knowledge, or organisational context. | No. Published as **declared-and-uncovered** with the evidence that *would* decide it. |

An `artifact_signal` is an enabling precondition a benign package can also exhibit (an
unbounded retry loop, an unpinned external reference). Implementing one is honest work,
but a detector that fires on it has **not** covered the scenario, and a matrix that
reports it as coverage is the failure this contract exists to prevent. Fixtures labeled
against a signal carry `covers: artifact-signal-only`.

`validators/tier_lock.py` hashes a category's tiering. That hash is pinned in the matrix.
Reclassifying any scenario changes the hash, which is the signal that the fixture corpus
must be re-labeled and the judge matrix re-run before an F1 can be republished.

### `skills/<AST>/SKILL.md` — knowledge, and only knowledge

The knowledge layer. Frontmatter (`name`, `description`) is what a runtime routes on; the
body carries the decision rules, the seams between adjacent categories ("vs AST02", "vs
AST04"), and the boundary conditions that make each preventive control fail.

**No mechanism lives here.** Not because prose-with-code is ugly, but because a fenced
implementation in a knowledge file is a second copy of the detector that nothing tests and
nothing updates. `tests/test_ast_skill_layout_lint.py` enforces this mechanically: it fails
any `SKILL.md` that exceeds the D5 line budget, embeds a fenced `python` block, restates a
generic definition, or omits its category's distinctive whitepaper markers (real CVE ids,
named campaigns, cited papers). That lint is a deterministic floor under the D1 Knowledge
Delta dimension the judge matrix scores.

### `skills/<AST>/coverage-matrix.md` — the F1 contract

The artifact an F1 number is defended with, and the reason a reader should believe it.
Each one publishes:

- the **authority chain** above;
- **every** scenario in the category, tiered, with the reason for that tier;
- a **declared-and-uncovered** table for the out-of-artifact rows, naming the evidence
  that would decide each one — published rather than dropped, so absent coverage is
  visible instead of implied;
- **coverage debt** — scenarios that *are* decidable and that this package does not yet
  decide, which is a different and more embarrassing thing than "undetectable";
- the **corpus arithmetic**: `cases = max(6, 2 × detectable_scenarios)`, class-balanced,
  drawn only from the static-detectable tier;
- the **tier-lock hash**, plus the shell one-liner that re-derives the table from the
  registry so a reader can check it rather than believe it.

### `skills/<AST>/skill.usf.yaml` — the manifest under test, applied to itself

The whitepaper's proposed **Universal Skill Format**: `permissions.files.read/write/
deny_write`, `permissions.network.allow/deny`, `permissions.shell`, `requires`,
`risk_tier`, `scan_status`, `signature`, `content_hash`, `changelog`.

This repo eats its own cooking: every skill it ships carries a USF manifest, validated by
`validators/usf.py` against `schemas/usf-v1.schema.json`. The validator does two passes:

1. **Structural** — Draft 2020-12 schema validation (`jsonschema`), imported defensively
   so a missing dependency raises rather than silently skipping the check.
2. **Semantic** — it recomputes the `risk_tier` floor from the declared permissions rather
   than trusting the field (`risk_tier` spoofing is AST04), reports `signature_state`
   instead of treating unsigned as valid, and warns on a missing identity anchor.

Two deliberate choices worth understanding before you "fix" them. `deny_write` lists
`SOUL.md` / `MEMORY.md` / `AGENTS.md` even though `write: []` is already empty — `write:
[]` is a property of *this* package, while `deny_write` is a floor that has to survive a
port to a runtime whose default is write-everything, which is AST10's implicit privilege
escalation. And `scan_status.result: "unscanned"` is declared rather than omitted: an
absent scan status is indistinguishable from one stripped during a port, which is the
AST10 failure itself.

`content_hash` covers the shipped surface defined by `scripts/content_hash.py`'s
`SURFACE_GLOBS` (`SKILL.md`, `references/*.md`, `scripts/*.py`, `evals/evals.json`).
`skill.usf.yaml` itself is outside that surface — that is what stops the hash from
depending on the field that carries it.

Three of those four patterns match a file in every skill, so every stamped `content_hash`
here is a digest over `SKILL.md` plus `scripts/*.py` plus `evals/evals.json`. Only
`references/*.md` is left over, and its glob results match **no file in this repository**:
no skill ships a `references/` directory. That leftover pattern is kept anyway, and `scripts/content_hash.py` splits the four out as
`POPULATED_SURFACE_GLOBS` / `UNPOPULATED_SURFACE_GLOBS` so the split is a value a test can
read rather than a comment a reader has to trust: the day a skill adds a
`references/notes.md` it must enter the hash without anyone remembering to widen the
tuple, because a surface definition that silently stops covering a shipped file is the
AST10 metadata-loss shape.
`tests/scripts/test_content_hash.py::test_unpopulated_surface_globs_are_still_unpopulated`
fails if that stops being true, and
`test_shipped_content_hash_is_reproducible_from_the_populated_globs_alone` re-derives
every skill's digest from the populated patterns alone to prove the claim.

`evals/evals.json` was in the unmatched half until the with/without eval cases were
authored. Every skill now ships one, the pattern moved to `POPULATED_SURFACE_GLOBS`, and
every skill's `content_hash` was re-stamped in the same change — which is the behaviour
the two tuples exist to force. Nothing about the hashing algorithm or the surface
definition moved; only which patterns match a file did.

**`signature` is the field the rest of this section exists to keep honest.** All eleven
manifests are signed: each carries a real `ed25519:<128 hex>` value over its own RFC 8785
payload, plus `author.identity: did:web:jhkchan.github.io` and the `author.signing_key`
that identity publishes at `https://jhkchan.github.io/.well-known/did.json`. Anyone can
check the set with `python3 scripts/sign_usf.py verify --identity did:web:jhkchan.github.io`,
which needs no key and no secret.

They shipped unsigned before that, with the literal placeholder `"unsigned"` and both
anchor fields absent rather than empty, and the reason is worth keeping: a DID or a public
key that anchors to nothing is the false trust signal AST10 is about. `validators/usf.py`
still distinguishes the explicit placeholder from a real value rather than treating either
as "valid", which is what makes both states legible rather than one of them a gap.

What a verified signature answers is *who published this*, never *is this safe* — and a
`did:web` anchor is worth exactly as much as control of that domain and its TLS.
`config/did-web-anchor.json` is a committed copy of the published document so CI can check
the manifests against it without a network call
(`tests/test_signing_anchor.py`); the live resolution stays in `verify --identity`, where
an unreachable anchor exits 3 and is never confused with a pass.

Signing them is implemented, not aspirational. `scripts/sign_usf.py` writes
`author.identity`, `author.signing_key` and `signature` in a single rewrite, with all three
*inside* the signed payload (the payload is the whole manifest minus `signature`,
canonicalised per RFC 8785), so a signature cannot be moved to another publisher's identity
and an identity cannot be swapped under an existing signature. There is no code path that
yields one without the other. Because each manifest signs its own `content_hash`, the
signer recomputes every target's hash first and refuses the whole run if one has drifted:
signing a stale manifest would attest to bytes that are not there.

The custody split is the same shape as the judge split above. `keygen` and `sign` are
maintainer-local and refuse to run when the environment says CI; `verify` is a public-key
operation, so `.github/workflows/eval.yml` runs it on every PR and the private key is never
present. [`signing.md`](signing.md) is the runbook, and
`tests/test_signing_key_never_enters_the_repo.py` is what fails if a key ever reaches this
tree.

### `skills/<AST>/scripts/detector.py` — the mechanism

Pure functions over a plain package dict:

```python
{"manifest": {...}, "files": {"<relative/path>": "<text>"}}
```

Each check returns a `Finding(scenario, detected, evidence)`, and `run_all` returns one
per registered check **including the ones that did not fire** — a detector that reports
only hits is indistinguishable from a detector that did not run.

Shared machinery lives in `detectors/`:

- `detectors/scaffold.py` — `Finding`, `run_all`, `static_detectable`, and the `f1_report`
  every per-skill module delegates to. For an empty detectable tier it returns
  `{"status": "declared-and-uncovered", "f1": None}` — the never-pad rule, implemented,
  not merely documented.
- `detectors/engine.py` — `run_category`, which scores a category's fixtures. It raises
  `OutOfArtifactFixtureError` if a fixture is bound to an out-of-artifact scenario and
  `UnregisteredScenarioFixtureError` if a fixture names a scenario the matrix does not
  know. Both are contract violations that fail loudly rather than dropping out of the
  denominator through a silent `.get()` miss.
- `detectors/f1_reporter.py` — builds the per-category verdict rows, each decided on that
  category alone. There is no suite-wide pass/fail that a strong category could carry a
  weak one through.
- `detectors/corpus.py` — the join between `fixtures/manifest.yaml`'s labeled cases and
  the detector functions. It reads a case directory into the `{"manifest", "files"}`
  package shape (everything except `skill.usf.yaml`, which is the manifest, not package
  content) and resolves each labeled check's `detector_check` field to the function that
  decides it. Before it existed the corpus and the detectors used different id namespaces
  and nothing read the fixtures, which is why every category published
  `pending-detector`. A `clean` case expects **nothing** to fire, not merely that its own
  check stays silent — a check firing on a clean case is a false positive whichever check
  it is.
- `detectors/fixture_loader.py` — the runnable half of that join. It loads a fixture
  directory the way `cli/lib/bridge.py` loads a candidate under audit, including the
  bridge's own `SURFACE_SCOPED` rule (AST01's content-hash checks are specified over the
  declared shipped surface, so feeding them the wider scan view would report a mismatch on
  every well-formed fixture — a false positive manufactured by the harness), and attaches
  the byte views a detector asks for by shipping its own `load_package_dir`. AST08 is the
  only module that does: a `.pyc` header and a zip central directory are not decoded text
  and its two host-hazard scenarios are decided from exactly those bytes.

### `eval/generate_f1_report.py` and `scripts/dogfood.py --markdown` — the published measurements

Two generated, committed documents, each regenerated-and-compared by the test suite so a
number in the repository can never be older than the corpus it describes:

- [`f1-report.md`](f1-report.md) / `eval/f1-report.json` — every category's measured
  precision, recall and F1, each individual case verdict included so a reader can
  re-derive any published figure by hand. The gate verdict is computed by
  `detectors/f1_reporter.py` from the `covers: full` checks alone; `artifact-signal-only`
  checks are scored into their own block and never supply the gate figure. The report also
  carries a **clean-leakage** column — how many of a category's clean packages had *any*
  check in its module fire on them, including checks the case was not labeled against,
  which the per-check confusion matrix structurally cannot see.
- [`dogfood-report.md`](dogfood-report.md) — every firing of every detector over this
  repository's own eleven packages, waived or not, with each waiver's written reason, plus
  a re-run through the bridge's wider scan view so the claim that scanning
  `skill.usf.yaml` as text finds nothing extra is measured rather than assumed.

### `eval/skill_evals.py` — the third kind of evidence

Judge scores grade the *text* of a `SKILL.md`; detector F1 grades the *scripts*. Neither
grades what an agent holding the skill actually produces. `eval/skill_evals.py` runs every
case in `skills/<AST>/evals/evals.json` **twice** — once with the skill's `SKILL.md`
installed as the agent's operating instructions, once with that one block removed and
nothing else changed — and the **delta between the two pass rates is the deliverable**.
Both prompts are built by one function from one list of sections, so "the arms differ in
exactly one respect" is a property of the construction rather than a claim about it, and
each arm's `prompt.txt` is committed so the claim stays auditable after the run.

The agent under test and the grader are always different models: the runner exits rather
than let one model grade its own output, and both names are written into every
`timing.json`, `grading.json` and `benchmark.json`. `eval/skill_eval_grade.py` is a
stricter second pass over the same workspace — it blinds each run behind an opaque token,
scrubs arm markers out of the text, rejects a PASS whose evidence does not quote the
graded output, and classifies every assertion across the two arms into
`assertion-review.json`. [`skill-eval-report.md`](skill-eval-report.md), written by
`eval/generate_skill_eval_report.py`, is that surface's published page.

It is a **third, separate** surface. A `pass_rate` there is not an F1 and not a judge
total, the three are never averaged, and nothing on that surface reaches
`scripts/ship_floor.py`.

### `fixtures/` — the evidence

One directory per case, named `V<n>-<check>` (vulnerable) or `C<n>-<check>` (clean), each
containing a `SKILL.md`. `fixtures/manifest.yaml` is the label file: it records
`min_floor: 6`, the formula `max(min_floor, 2 * count(detectable_scenarios))`, and per
category the `detectable_scenarios` (with `registry_ids` and a `covers` value), the
`cases`, the `status`, the `f1_scope`, and `published_f1`.

The never-pad rule is enforced here, not just described: a category with an empty labeled
detectable tier records `cases: []`, `published_f1: null`, `status:
declared-and-uncovered`. **Two of ten categories are in that state today — AST07 and
AST09** — and the arithmetic floor of six cases does **not** override it: `max(6, 2 × 0) =
6` is true and irrelevant, because the floor exists to stop a category with two detectable
scenarios publishing an F1 off a two-case corpus, not to require six cases for a category
with nothing to detect.

A third shape sits between the two and is easy to misread as coverage. AST05 has zero
static-detectable scenarios in the registry, yet ships checks and a six-case corpus. What
it publishes is `f1_scope: artifact-signal-only` — a measurement of five signal checks
that decide *preconditions*, none of which covers a named AST05 scenario. That is not the
never-pad rule being bent; it is the rule working, because the number travels with a scope
label that forbids quoting it as scenario coverage.
`tests/test_coverage_matrix.py::test_ast05_publishes_no_scenario_level_number_because_its_detectable_tier_is_empty`
asserts AST05's `published_f1` says `artifact-signal-only` and never says
`scenario-level`.

### The judge matrix — `adapters/`, `scripts/judge_harness.py`, `scripts/ship_floor.py`

Detectors are measured by F1. `SKILL.md` bodies are measured by a multi-provider LLM judge,
because "does this file teach an agent something it did not know" has no fixture.

```
adapters/base.py          ProviderAdapter (check_availability + judge), AdapterStatus,
                          RosterResult, and the append-only audit-trail writers
adapters/bedrock.py       four Bedrock on-demand models, us-west-2, `converse`
adapters/claude_cli.py    local `claude -p --model <id>` subprocess
adapters/anthropic_compatible.py   Anthropic-shaped HTTP endpoints (GLM via api.z.ai)
        │
        ▼
scripts/judge_harness.py  call_model() → one provider's 8 sub-scores
                          run_judge()  → loops the roster, pools survivors, writes JSON
        │
        ▼
scripts/ship_floor.py     aggregate_verdict() → SHIP | BLOCKED
        │
        ▼
eval/scorecards/*.json → eval/generate_dashboard.py → docs/skill-judge-dashboard.md
```

Three properties hold this together:

**Declare or skip.** `AdapterStatus` refuses to construct an unavailable status without a
non-empty reason. Unavailable providers are recorded in `config/audit.yml` — never
averaged in as zero, never dropped without a record. `runtime_entries` is append-only.

**Failures are recorded, not fatal.** An adapter that raises mid-round is excluded from
that round's pool with a timestamped audit entry; the run continues and publishes
`status: "partial"`.

**Nothing stored is believed.** `aggregate_verdict` recomputes every published statistic
from `aggregate.judgments` before comparing it to the stored value. A stored mean is a
claim; the judgments are the evidence. `eval/generate_dashboard.py` calls the same function
the gate calls, so the dashboard and the gate cannot drift apart.

**The prompt carries the scale, and the judge must justify itself.** `build_prompt` reads
the pinned rubric off disk at build time and quotes each dimension's own band table, red
flags and worked examples verbatim — there is no second copy of the bands in this repository
to drift, and the prompt refuses to build if the vendored bytes do not hash to the pinned
`RUBRIC_CONTENT_SHA256`. The response contract is one object per dimension carrying a score
and a one-sentence `why`; a judgement whose justification is missing, empty, or repeated
across dimensions is recorded as **malformed** and excluded from the pool with an audit-trail
entry, exactly as a crashed provider is — the entry names the skill, the provider, the 1-based
round, the parse error and a redacted excerpt of the response, and is appended to
`config/audit.yml` by `adapters.base.record_failure` before `run_judge` returns. That
persistence dates from 2026-08-24 and run 5 predates it: its ten discards were recorded
nowhere, and `eval/run5-refusals.md` reconstructs what the bytes still allow.
`scripts/refusal_ledger.py` fails the build on any scorecard whose pooled `n` is below its
attempted `n` without matching records, and `eval/robustness.py` — printed by
`eval/calibration.py` and written to `eval/robustness.json` — re-runs the live gate with each
single judge dropped and with those missing attempts refilled at the same judge's own mean on
the same skill, so the published ship count travels with the margin around it rather than alone. Both properties date from 2026-08-23 and both are
breaking: **scores measured under this prompt are not comparable to `eval/scorecards-run1/` or
`eval/scorecards-run2/`**, which were produced by a prompt that sent only the dimension names
and forbade prose. Those two directories are kept unmodified as the record of the earlier
instrument. `eval/scorecards/` is **run 5**, the corpus every published figure comes from;
`eval/scorecards-run3/` and `eval/scorecards-run4/` are the archived runs scored under this same
prompt. Each consecutive pair differs by a known set of `SKILL.md` edits and nothing else — eight
files between runs 3 and 4, one file (`AST01`) between runs 4 and 5 — which is what makes them
controlled comparisons rather than three snapshots. See the callout at the top of
[`skill-judge-dashboard.md`](skill-judge-dashboard.md).

The ship rule itself — mean ≥ 108, mean − 1.0 × σ/√n ≥ 108, per-dimension floors, ≥ 4 pooled
rounds — and the full provider roster with the unavailable entries and their reasons are in
[`skill-judge-dashboard.md`](skill-judge-dashboard.md).

**The gate was changed exactly once.** Its second clause read `mean − σ ≥ 105` from the moment
`ship_floor.py` was vendored through run 4. On 2026-08-24
[`adr/0006-confidence-bound-on-the-pooled-mean.md`](adr/0006-confidence-bound-on-the-pooled-mean.md)
replaced it with the confidence bound above, because `mean − σ` is a spread statistic and the
question the clause asks is about a mean: the retired form made the verdict track the panel's
dispersion rather than the artifact, and flipped `AST08` — byte-identical between runs 3 and 4 —
from BLOCKED to SHIP. The record was written and the constant fixed before the run it judges.
`eval/scorecards/` and the dashboard table it feeds are **run 5**, the first corpus judged by the
rule above; `eval/scorecards-run4/` keeps run 4's verdicts as the retired clause issued them and is
**not** re-gated. That the change altered no run-4 verdict is re-derived by
`tests/test_generate_dashboard.py` rather than asserted, which is what lets run 5's board be read
as a fact about the skills. `POOLED_LOWER_BOUND` survives in the source as a retired constant, read
by nothing in the gate, so ADR-0005's arithmetic stays regenerable.

### `cli/ast10.py` and `.claude-plugin/marketplace.json` — distribution

The CLI reads the repository's own manifests for every number it prints, so it cannot
report a coverage state the manifests disagree with, and `route` delegates to the advisory
skill's own `triage.py` rather than keeping a second copy of the decision tree.

`.claude-plugin/marketplace.json` is a **Claude Code plugin marketplace manifest**:
marketplace identity plus a single `plugins[]` entry, `owasp-ast10`, whose `source` is the
repository root and which declares both component paths — `./skills` for the eleven skills,
keyed on the SKILL.md frontmatter `name` a runtime routes on, and `./commands/ast` for the
fourteen slash commands. It was a flat `{name, description}` index until that was found to
be sitting at the path Claude Code reserves for a marketplace, where
`/plugin marketplace add` on this repository failed outright and no install path delivered
the commands. `.claude-plugin/plugin.json` carries the same identity for the plugin itself,
and `tests/test_packaging.py` fails the build if the two manifests disagree, if either
declared path stops resolving to what is on disk, or if a command file appears outside the
declared path and would silently not install. The manifest no longer restates the skill
roster, so there is no index left to drift.

The plugin's `displayName` — the string a picker actually renders — leads with
**"Unofficial"**, because a picker often drops the description, and the moment of
installation is exactly where "OWASP Agentic Skills Top 10" without a qualifier reads as an
OWASP-published artifact. The marketplace `name` does not: it is the kebab identifier typed
after `@`, never rendered as a title, and qualifying it produced
`owasp-ast10@unofficial-owasp-ast10-agent-skills`, which repeats what the rendered name
already says. The disclaimer is carried where it is read, not in every field that could hold
it. `cli/ast10.py install` and a
`cp -r` of `skills/` remain the non-plugin paths, and neither copies `commands/ast/`.

---

## Two loops, not one

The repository has two independent quality gates, and conflating them is the mistake worth
avoiding.

| | Detection loop | Knowledge loop |
| --- | --- | --- |
| **Measures** | Does the detector decide the scenario correctly? | Does `SKILL.md` teach an agent something it did not know? |
| **Instrument** | `detectors/engine.py` over `fixtures/` | multi-provider judge over the pinned 8-dimension rubric |
| **Unit** | one category | one skill package |
| **Output** | per-category F1, or `declared-and-uncovered` | pooled mean + per-dimension means |
| **Gate** | the coverage matrix's F1 contract | `ship_floor.aggregate_verdict` |
| **Reported in** | `coverage-matrix.md`, `cli/ast10.py status` | `docs/skill-judge-dashboard.md` |

A category can hold a perfect F1 over a two-check corpus and still be a poor skill; a skill
can score Grade A on the rubric and detect nothing. Neither number substitutes for the
other, and they are never summed.

The `advisory` skill sits outside the detection loop entirely: it triages findings someone
else raised, contributes to no F1 denominator, and is judged only on guidance relevance and
reasoning quality (spec.md S-002).

---

## Where the whole thing stops

Every detector reads one skill package at one moment in time. That boundary is not an
implementation gap to be closed later — it is a property of the artifact, and the
`out-of-artifact` tier exists to name it honestly rather than approximate around it.
AST07 and AST09 have zero static-detectable scenarios for exactly this reason: drift and
governance are not properties of a snapshot. See
[What this does not do](../README.md#what-this-does-not-do).
