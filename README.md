# owasp-ast10-agent-skills

The **OWASP Agentic Skills Top 10** (AST01–AST10) operationalised as eleven installable
agent skills: one per AST category plus an advisory skill that triages a free-text finding
to its primary category using the whitepaper's own decision tree.

**Eight of the ten category skills ship executable detectors** that audit a candidate skill
package before you install it. **Two — `AST07` Update Drift and `AST09` No Governance — ship
none, and cannot**: every one of their scenarios needs evidence that does not exist inside a
single skill package (version history, organisational process). That is a published boundary,
not a gap; the table below and each `coverage-matrix.md` say so scenario by scenario.

Each skill is a knowledge package. `SKILL.md` carries the decision rules and the seams
between adjacent categories; the mechanism lives in `scripts/` (and in an optional
`references/`, which no skill ships today — the long-form source is the whitepaper). Every
category ships a `coverage-matrix.md` that states, scenario by scenario, what the package
claims to decide and what it does not — and a category with nothing detectable in an
artifact publishes **no F1 at all** rather than a padded one.

---

## ⚠️ Not an OWASP project

**This repository is an independent, community open-source implementation. It is NOT an
official OWASP project, is not published by OWASP, and carries no OWASP endorsement,
review, or affiliation — despite the repository name.**

- The **OWASP Agentic Skills Top 10** is the source publication this repository
  implements. Full credit for the taxonomy, the attack-scenario catalog, the decision
  tree, and the Universal Skill Format proposal belongs to that project and its
  contributors.
- **Ken Huang (DistributedApps.ai) is the project leader** of the OWASP Agentic Skills
  Top 10, and originated the taxonomy and the source repository. He did not author,
  review, or endorse this repository.
- The maintainer of this repository, **Jacky Chan (Beever AI / Votee AI), is a credited
  Reviewer/Contributor to the publication** — listed in its "Reviewers and Contributors"
  table. That is the extent of the relationship: contributor credit on the publication,
  not authorship of it, not leadership of the project, and not a mandate to implement it.
  Treat this repo as insider-adjacent community work, not as an arm's-length citation and
  not as an official reference implementation.
- Nothing here should be read as OWASP guidance. Where this repo and the whitepaper
  disagree, **the whitepaper wins** — see [`docs/architecture.md`](docs/architecture.md)
  for the authority chain each skill is bound to.

`OWASP` is a trademark of the OWASP Foundation. The name appears here descriptively, to
identify the standard being implemented.

---

## Installation

Two ways to install the eleven skill packages, plus one machine-readable index to drive
either of them from a script. None of the three copies `commands/ast/` — those come with
the clone; see [Or just use the slash commands](#or-just-use-the-slash-commands).

### Method 1 — Copy the skills into your agent's skills directory

Works with any runtime that discovers skills from a directory (Claude Code, and the other
agent runtimes that adopted the `SKILL.md` folder convention).

```bash
git clone https://github.com/jhkchan/owasp-ast10-agent-skills.git
cd owasp-ast10-agent-skills

# One category — the destination directory takes the frontmatter `name`,
# which is the identifier a runtime matches invocations against.
cp -r skills/AST03 ~/.claude/skills/ast03-over-privileged-skills

# Or all ten detectors plus the advisory triage skill.
python3 cli/ast10.py install --all --target ~/.claude/skills
```

### Method 2 — The marketplace manifest as a skill index

The repo ships [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json):
a flat, machine-readable index of all eleven skills, each entry pairing the
frontmatter `name` a runtime matches invocations against with a one-line description.
`tests/test_packaging.py` fails the build if it drifts from `skills/` in either
direction, so it is a safe thing to script against:

```bash
# Every skill name the repo publishes, for a scripted install loop.
python3 -c "import json;print('\n'.join(s['name'] for s in json.load(open('.claude-plugin/marketplace.json'))['skills']))"
```

It is an index, not a plugin-bundle declaration — installation itself goes through
Method 1 or Method 3.

### Method 3 — The CLI

`cli/ast10.py` needs Python 3.11+ and PyYAML, and nothing else. It reads the repository's
own manifests, so it can never report a coverage number the manifests disagree with.

```bash
python3 cli/ast10.py list                    # every skill + its F1 state
python3 cli/ast10.py status                  # per-category coverage and tiering
python3 cli/ast10.py route "<finding text>"  # triage a finding to an AST id
python3 cli/ast10.py install --all --target ~/.claude/skills
python3 cli/ast10.py install --skill AST01 --skill advisory --dry-run
```

A second front end, `cli/bin/cli.js`, ships alongside it for Node 18+ with **zero** npm
dependencies (`package.json` exposes it as `ast10-skills`). It is not a rewrite: `route`
and `audit` shell out to `cli/lib/bridge.py`, so the decision tree and the detectors have
exactly one implementation, and `tests/test_cli.py` fails if the two front ends ever
disagree on a number. It adds two verbs the Python CLI does not have — `audit <path>`,
which runs every detector over a candidate package, and `coverage` — while `install` stays
Python-only.

```bash
node cli/bin/cli.js audit fixtures/AST01/V1-obfuscated-payload-exec --fail-on-detect
node cli/bin/cli.js coverage
```

[`cli/README.md`](cli/README.md) has the full verb-by-verb comparison and explains how to
read an `audit` report.

---

## Usage

### Audit a candidate skill package before installing it

Every detector operates on a plain package dict — the manifest plus the package's own
files — so it can run against a directory you just cloned, or against bytes you have not
written to disk yet.

```bash
python3 - <<'PY'
import importlib.util, pathlib

spec = importlib.util.spec_from_file_location(
    "ast01", "skills/AST01/scripts/detector.py"
)
ast01 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ast01)

package = {
    "manifest": {"content_hash": None},              # nothing to verify against
    "files": {"SKILL.md": pathlib.Path("skills/AST01/SKILL.md").read_text()},
}
for finding in ast01.run_all(package):
    print(finding.scenario, finding.detected, "-", finding.evidence)
PY
```

```
AST01-content-hash-missing True - manifest.content_hash.value is unset
AST01-content-hash-mismatch False - no declared hash to compare
AST01-social-engineering-prerequisites False - no install instruction pipes a remote fetch into a shell
AST01-soul-md-persistence False - no declared write scope and no bundled script writes to SOUL.md
AST01-memory-poisoning False - no declared write scope and no bundled script writes to MEMORY.md
AST01-identity-clone-exfiltration False - no bundled script both reads an identity artifact and sends outbound
AST01-websocket-c2 False - no bundled script opens a WebSocket to an undeclared host
AST01-undeclared-egress False - every hardcoded egress destination is covered by the declared allowlist
AST01-hidden-output-injection False - no concealed instruction carrier in the package's output templates
AST01-obfuscated-payload-exec False - no encoded blob is decoded into an execution sink
```

`run_all` returns one `Finding` per registered check, **including the ones that did not
fire**. A detector that only reports hits cannot be distinguished from a detector that
did not run — which is the AST08 failure this repo is about.

### Triage a finding through the decision tree

```bash
python3 cli/ast10.py route "overprivileged agent with write access to production secrets"
```

```json
{
  "ast_id": "AST03",
  "category": "Over-Privileged Skills",
  "guidance": "AST03 — Over-Privileged Skills. Recommend rotating any credentials or secrets the skill could reach, then restricting the skill's permissions to read-only ...",
  "reasoning": "Routed to AST03 (Over-Privileged Skills) as the primary root cause per the decision tree's rule order; 1 total rule(s) matched.",
  "contributing": [],
  "matched_phrase": "overprivileged",
  "branch": null
}
```

`matched_phrase` is the literal span that fired the rule and `branch` is the whitepaper
decision-tree branch number when the match came from one of its four numbered branches
(`null` for the six extended categories, which the tree does not number). Both are there so
a routing decision can be argued with rather than only accepted.

When more than one branch of the tree matches, the router records **one** primary root
cause and lists the rest under `contributing` — it never splits a single finding across
two categories. A finding that matches nothing comes back as `ast_id: null` with a request
for manual triage, never a guessed category.

The advisory skill's own script works standalone too, for use inside a runtime:

```bash
python3 skills/advisory/scripts/triage.py "the scanner missed an obfuscated instruction"
```

### Validate a USF manifest

Every skill in this repo ships a `skill.usf.yaml` in the whitepaper's proposed Universal
Skill Format. The validator does a structural pass against
`schemas/usf-v1.schema.json` **and** a semantic pass: it recomputes the `risk_tier` floor
from the declared permissions rather than trusting the field, and reports the signature
state instead of treating "unsigned" as "valid".

```bash
python3 validators/usf.py skills/AST01/skill.usf.yaml
```

```
skills/AST01/skill.usf.yaml: warn: author.identity: no decentralized identity anchor declared; a registry cannot bind this package to a publisher, so installation counts and author names remain unverifiable trust signals
skills/AST01/skill.usf.yaml: OK (signature=unsigned, risk_tier floor=L0, 0 error(s), 1 warning(s))
```

Validate the whole roster at once:

```bash
python3 validators/usf.py skills/*/skill.usf.yaml
```

Useful flags: `--update-content-hash` recomputes the `content_hash` over the skill's
shipped surface, and `--strict` turns warnings into a non-zero exit. Note that
`--strict` **fails on this repo's own roster today** — every shipped manifest declares
no identity anchor and no signature, on purpose (see
[What this does not do](#what-this-does-not-do)). That is the flag behaving correctly:
a warning nobody has to act on is a warning that gets ignored.

### Or just use the slash commands

The checkout also carries `commands/ast/` — fourteen slash commands that wrap the four
workflows above in natural language, so you do not have to remember which script does
what. They come with the clone, not with a skill install: none of the three methods above
copies them, because `marketplace.json` is a skill index and not a plugin-bundle
declaration. Point your runtime's command directory at `commands/ast/`, or copy it, to get
`/ast:…` on the prompt.

| Command | Does |
| --- | --- |
| `/ast:audit-skill-package` | Full AST01–AST10 sweep over one candidate skill directory, closing with a coverage ledger |
| `/ast:audit-ast01` … `/ast:audit-ast10` | One category's checks, for when you already know what you are looking for |
| `/ast:triage-finding` | Walk the decision tree on a free-text finding |
| `/ast:validate-usf-manifest` | Structural + semantic pass over a `skill.usf.yaml` |
| `/ast:check-coverage` | What the sweep decided, what needs a judge, what is not decidable at all |

### Read a coverage matrix

`skills/<AST>/coverage-matrix.md` is the artifact an F1 number is defended with. It states
the authority chain, tiers every one of the whitepaper's named scenarios for that category
as `static-detectable` / `agent-judgable` / `out-of-artifact`, publishes the
declared-and-uncovered rows with the evidence that *would* decide them, and shows the
corpus arithmetic.

```bash
python3 cli/ast10.py status         # the summary across all ten categories
less skills/AST01/coverage-matrix.md
```

Each matrix ships the command that re-derives its own numbers from the registry, so a
reader can check the table rather than believe it:

```bash
python3 -c "import yaml; [print(s['id'], '|', s['title'], '|', s['tier']) for s in yaml.safe_load(open('scenarios/registry.yaml'))['scenarios'] if s['category']=='AST01']"
```

---

## Skills

Two independent states per category, and collapsing them is the mistake this table exists
to prevent: one says what code exists, the other says what was measured.

**Detector state** — derived, not asserted. `scenarios/registry.yaml` is authoritative on
which scenarios are `static-detectable`; `fixtures/manifest.yaml` is authoritative on
which of those carry a shipped check and a labeled fixture pair.
`tests/test_docs.py::test_readme_detector_state_matches_the_state_derived_from_the_manifests`
re-derives every value below from those two files and fails on drift, so this column
cannot describe a check that does not exist:

- **`implemented`** — every scenario the registry tiers `static-detectable` for this
  category has a check in `skills/<AST>/scripts/detector.py` and a labeled fixture pair.
  Nothing decidable is unbuilt.
- **`coverage-debt`** — the registry tiers a scenario `static-detectable`, so one package's
  own bytes *can* decide it, and no shipped check does. Decidable-but-unbuilt, which is a
  different and more embarrassing thing than undetectable. **No category is in this state
  today.** The state is defined and tested for anyway, so that regressing into it shows up
  on the front page instead of only inside a matrix.
- **`declared-and-uncovered`** — the registry tiers *every* scenario in the category
  `agent-judgable` or `out-of-artifact`. There is nothing for a static check to decide, so
  no check ships and no F1 is published at any corpus size.

**F1** — what was measured, quoted verbatim from `fixtures/manifest.yaml`. Every number
carries the scope it was measured at, because quoting one without its scope is the
overclaim the labels exist to block:

- **`scenario-level`** — measured over checks that decide a named whitepaper scenario's
  *defining condition*.
- **`artifact-signal-only`** — measured over checks that decide an enabling *precondition*
  a benign package can also exhibit (an unbounded retry loop, an unpinned reference, an
  absent permissions block). It is **not** coverage of any named scenario and may never be
  quoted as one. AST05 publishes only this.
- **both, separated by `;`** — a `mixed-proxy` category, scored separately per scope so the
  proxy half cannot ride on the scenario half.
- **`declared-and-uncovered`** — no number, at any corpus size. This is the never-pad rule:
  an empty detectable tier is reported as empty rather than filled with fixtures written to
  separate perfectly.
- **a bare number (`1.0`)** — AST10 alone stores `published_f1` as a JSON float rather than
  a labeled string; its scope is `scenario-level`, carried in the sibling `f1_scope` field
  and printed beside it by `python3 cli/ast10.py status`.

The "What the shipped detector decides" column describes **only checks that exist and run
today** — it is the check roster, not the category's subject matter. For what each category
*covers as knowledge*, read its `SKILL.md`; for what is decidable and refused, read its
`coverage-matrix.md`.

| AST | Skill | What the shipped detector decides | Detector state | F1 |
| --- | --- | --- | --- | --- |
| AST01 | `ast01-malicious-skills` | Ten checks: `content_hash` absent or mismatched; install prose that pipes a remote fetch into a shell; a declared or coded write to `SOUL.md`; the same for `MEMORY.md`; a script that both reads an identity artifact and sends outbound; a WebSocket to an undeclared host; a hardcoded egress destination outside the declared allowlist; concealed instructions in the package's own output templates; an encoded blob decoded into an execution sink | `implemented` | `scenario-level 1.000 (8 labeled checks, n=16)` |
| AST02 | `ast02-supply-chain-compromise` | One check: a command-bearing value in a config file the host auto-executes **at project open** — `.claude/settings.json` hooks, an MCP/env control-plane override, a `.vscode/tasks.json` `folderOpen` task. Registry flooding, dependency confusion and maintainer-account takeover are tiered `out-of-artifact` and no check claims them | `implemented` | `scenario-level 1.000 (AST02-S03, n=6)` |
| AST03 | `ast03-over-privileged-skills` | Four checks: a declared write grant reaching the agent's own identity files (`SOUL.md`, `MEMORY.md`, `AGENTS.md`); no declared write floor at all; shell execution combined with unbounded egress; a blanket or wildcard egress declaration in place of an enumerated domain allowlist. Only the first covers a named scenario — the other three are a precondition and two signals | `implemented` | `scenario-level 1.00 (AST03-S03, n=2); artifact-signal-only 1.00 (n=4)` |
| AST04 | `ast04-insecure-metadata` | Six checks: a declared allowlist contradicted by the destination a bundled script actually reaches; `risk_tier` below the floor its own permissions derive; code-executing YAML tags and unsafe loaders; `__proto__` / `constructor` keys in shipped JSON next to an unsafe merge site; redefined TOML tables; invisible code points (flagged as a carrier class and stopped there, not convicted as an instruction) | `implemented` | `scenario-level 1.00 (n=10)` |
| AST05 | `ast05-untrusted-external-instructions` | Five checks, **every one a precondition**: a fetched document reaching an instruction sink; a remote response body reaching an executable sink; decision rules that consume upstream content with no provenance boundary; a blanket egress grant; a wildcard entry in the declared allowlist. The registry tiers all six AST05 scenarios `agent-judgable` or `out-of-artifact`, so none of these covers one | `implemented` | `artifact-signal-only 1.00 (n=6)` |
| AST06 | `ast06-weak-isolation` | Five checks: a bundled script that shell-execs or writes a host-persistence path; a declared write scope reaching the filesystem root or the home directory; shell granted with no bounding command list; declared writes into a shared workspace namespace; an absent or empty permissions block. The first two decide AST06-S01's two disjuncts; the rest are a precondition and two signals | `implemented` | `scenario-level 1.00 (AST06-S01, n=4); artifact-signal-only 1.00 (n=2)` |
| AST07 | `ast07-update-drift` | **No check ships, and none can.** All three AST07 scenarios — malicious update, rollback, hot-reload abuse — are defined by a *change between versions*, and one package at one moment carries no second version to compare against. The skill is knowledge only; `coverage-matrix.md` names the version-history evidence that would decide each one | `declared-and-uncovered` | `declared-and-uncovered` |
| AST08 | `ast08-poor-scanning` | Four checks: an obfuscated instruction found by decode-and-rescan over the normalized view (comparing match counts per view, so a decoy in the clear cannot mask a smuggled copy); a branch that arms only under a specific environment; scanner-host hazards (padding runs, recursive archives, decompression ratio, symlink escape); bytecode the import machinery would prefer over its own source | `implemented` | `scenario-level 1.00 (4 scenario checks, n=8)` |
| AST09 | `ast09-no-governance` | **No check ships, and none can.** All seven AST09 scenarios are `out-of-artifact`: inventory, approval, ownership and offboarding live in an organisation's process, not in a package. The skill is knowledge only; `coverage-matrix.md` names the governance-system evidence that would decide each one | `declared-and-uncovered` | `declared-and-uncovered` |
| AST10 | `ast10-cross-platform-reuse` | One check: a payload hidden in an encoded blob that survives a port — decoded (base64, hex escapes, gzip-under-base64), then judged at the *content* layer, so a package carrying a legitimate encoded blob is not convicted for carrying one. Security metadata stripped during a port can be narrated inside a fake `SKILL.md`, so it is tiered `out-of-artifact` and no check claims it | `implemented` | `1.0` |
| — | `advisory` | Not a detector. Routes a free-text finding to its primary AST category via the whitepaper's decision tree and returns category-specific remediation | n/a — not a detector | not scored on F1 (judged on guidance quality) |

Four readings of that table are worth spelling out, because each is easy to get backwards.

**Shipped checks and measured checks are different counts, on purpose.** AST01 ships ten
checks and publishes an F1 over eight: its two `content_hash` checks decide a
*precondition* rather than a named scenario, so they run on every audit and enter no
denominator. AST03 (4 shipped / 3 labeled), AST04 (6 / 5), AST05 (5 / 3) and AST06 (5 / 3)
have the same shape. A check that runs and is never scored is not a hidden number — it is
a check whose `CHECK_COVERAGE` entry says outright that firing it proves nothing about a
whitepaper scenario.

**AST07 and AST09 publish nothing, and that is the registry talking, not a backlog.** Both
have **zero** static-detectable scenarios in the whitepaper's own enumeration — every
scenario is temporal or organisational — so no corpus size would give them a denominator.

**AST05 ships five checks and still covers no scenario.** It has an empty detectable tier
like AST07 and AST09, yet it publishes a number, because its checks decide real
preconditions and the corpus that measures them is real. What stops that from being a
padded F1 is the scope label: `artifact-signal-only` is not comparable with a
`scenario-level` number and cannot be quoted as AST05 coverage.
`tests/test_coverage_matrix.py::test_ast05_publishes_no_scenario_level_number_because_its_detectable_tier_is_empty` fails if
AST05's `published_f1` ever says `scenario-level`.

**A 1.00 is a discrimination claim about one hand-built corpus.** AST10's single
static-detectable scenario (AST10-S06, Silent Supply Chain Injection) is implemented and
measured over six labeled cases whose three *clean* packages each carry a real encoded
blob — one of them the same gzip-under-base64 shape as the vulnerable case — so a check
that fired on "contains an encoded blob" scores 0.67, not 1.00, and the matrix shows that
arithmetic. Read `skills/AST10/coverage-matrix.md` before quoting the number. The same
caveat applies to every 1.00 in the column.

---

## What this does not do

The single hardest limit: **a detector reads one skill package at one moment in time.**
Whole classes of AST risk are not properties of a snapshot, and this repo refuses to
pretend otherwise rather than shipping a proxy that scores well.

- **No runtime or multi-session observation.** AST01's Cognitive Degradation chain, AST07's
  drift, and AST09's governance failures are defined by accumulation across invocations.
  A package that will degrade its host and one that will not are byte-identical at install
  time. These are tiered `out-of-artifact` and published with the telemetry that *would*
  decide them.
- **No world knowledge.** Deciding that `gogle-workspace` is a deliberate near-miss of a
  legitimate name needs an external popularity and legitimate-name corpus the package does
  not carry. Typosquatting is `agent-judgable`, not static.
- **No organisational context.** Whether a skill is approved, inventoried, owned, or
  deprovisioned lives in your governance system, not in the artifact. AST09 is entirely
  out-of-artifact for that reason.
- **No sandbox, no enforcement, no blocking.** These skills report; they do not quarantine
  a package, revoke a signature, or stop an install. A verified signature answers *who
  published this*, never *is this safe*, and this repo will not conflate the two.
- **Every published F1 is a floor, not a rate.** The per-category numbers in the table above
  are measured over that category's own hand-labeled corpus at the locked gate-4 size —
  `max(6, 2 x detectable_scenarios)` — by authors who also wrote the checks. They establish
  that each check separates its vulnerable case from its clean one; they do not estimate
  performance on skills nobody here wrote. Categories reading `declared-and-uncovered`
  publish no number at any corpus size. A fourth state the tooling still understands,
  `pending-detector` — a labeled corpus exists that no detector consumes — is **unused
  today**: every labeled corpus in the repository is read by a detector, and
  `tests/test_coverage_matrix.py::test_every_authored_category_has_a_wired_corpus_or_is_declared_unwired`
  fails any category that publishes `pending-detector` while its corpus is wired. The coverage matrices name every gap.
- **No judged scorecards yet.** The eight-dimension skill-judge run has not been executed.
  [`docs/skill-judge-dashboard.md`](docs/skill-judge-dashboard.md) publishes the rubric,
  the ship rule, and the provider roster with an explicit *no judged run recorded yet*
  state — including the providers that are unavailable from this environment and why.
- **One declared platform.** Every `skill.usf.yaml` declares `platforms: [claude]`. Adding
  a platform is a re-validation event, not an edit — AST10's whole premise is that security
  properties are lost in translation between runtimes.
- **Unsigned packages.** Every manifest ships `signature: "unsigned"` with an explicit
  placeholder. Publishing a key that anchors to nothing would manufacture exactly the false
  trust signal AST10 warns about.

---

## Repository layout

```
skills/AST01..AST10/       SKILL.md (knowledge) + coverage-matrix.md (detectability
  ├── SKILL.md               contract) + skill.usf.yaml (USF manifest) + scripts/
  ├── coverage-matrix.md
  ├── skill.usf.yaml
  └── scripts/detector.py
skills/advisory/           the triage skill (scripts/triage.py holds the routing tree)
scenarios/registry.yaml    62 whitepaper scenarios, each with a tier and a written reason
fixtures/                  class-balanced vulnerable/clean corpora + manifest.yaml
detectors/                 shared F1 engine, reporter, and per-skill scaffold
validators/                USF manifest validator + the registry tier-lock hash
adapters/                  judge-matrix provider adapters (bedrock, claude-cli, ...)
scripts/                   pooled scoring rule, content hashing, judge harness, dogfood
eval/                      scorecards + the dashboard generator
cli/ast10.py               list / status / route / install  (Python)
cli/bin/cli.js             list / route / audit / coverage / status  (Node, no deps)
cli/lib/bridge.py          the one implementation `route` and `audit` both call
commands/ast/              14 slash commands wrapping the workflows above
.claude-plugin/            marketplace.json — the eleven-skill index
docs/                      architecture, the judge dashboard, ADRs, glossary
ruff.toml                  the lint + format contract CI runs unflagged
```

Read [`docs/architecture.md`](docs/architecture.md) for how those pieces bind to each
other, and [`docs/adr/0004-per-scenario-detectability-contract.md`](docs/adr/0004-per-scenario-detectability-contract.md)
for the tiering contract every coverage matrix is written against.

## Development

```bash
python3 -m pytest -q                            # the full suite
python3 validators/usf.py skills/*/skill.usf.yaml   # every shipped manifest
python3 validators/tier_lock.py fixtures/manifest.yaml   # tier-drift check
python3 scripts/dogfood.py                      # our detectors over our own skills
python3 scripts/ship_floor.py                   # recompute every stored judge verdict
python3 eval/generate_f1_report.py              # re-measure every corpus, rewrite the F1 report
python3 eval/generate_dashboard.py              # rewrite the dashboard results table
ruff check . && ruff format --check .           # exactly what CI runs; see ruff.toml
```

Two of those write documents that are committed alongside the code, and both are
regenerated-and-compared by the test suite rather than trusted:

- [`docs/f1-report.md`](docs/f1-report.md) — every category's measured precision,
  recall and F1, with each individual case verdict recorded in
  [`eval/f1-report.json`](eval/f1-report.json) so any figure can be re-derived by
  hand. Written by `python3 eval/generate_f1_report.py`.
- [`docs/dogfood-report.md`](docs/dogfood-report.md) — every firing of every
  detector over this repository's own eleven skill packages, waived or not, with
  the reason for each waiver. Written by
  `python3 scripts/dogfood.py --markdown --out docs/dogfood-report.md`.

Reformatting a skill's `scripts/*.py` changes the bytes its `content_hash` covers, so the
manifests have to be re-stamped afterwards or `validators/usf.py` will (correctly) report
a mismatch:

```bash
for f in skills/*/skill.usf.yaml; do python3 validators/usf.py --update-content-hash "$f"; done
```

CI runs the deterministic layer only. The LLM-judge layer is maintainer-local and
deliberately absent from the workflow: it needs Bedrock credentials, a local `claude` CLI,
and a z.ai key, and no secret is referenced anywhere in `.github/workflows/eval.yml`. The
maintainer runs the judge locally and commits the resulting scorecards, so a reviewer
diffs recorded scores rather than trusting an unreproducible CI run. A green CI run means
*every assertion this repo can make without a model held* — not *the skills scored Grade
A*. Those are different claims and the split keeps them apart.

## Contributing

[`CONTRIBUTING.md`](CONTRIBUTING.md) covers how to add a skill, the three tiers a new
scenario must declare itself under, and the rule that a new detector needs a hand-labeled
fixture corpus before it may publish an F1 at all.

## License

[Apache-2.0](LICENSE), Copyright 2026 Jacky Chan. Third-party attributions — the OWASP
whitepaper as source material, the vendored scoring pipeline, and the pinned skill-judge
rubric — plus the vendoring policy are in [`NOTICE`](NOTICE) and
[`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).
