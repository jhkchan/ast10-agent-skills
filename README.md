# owasp-ast10-agent-skills

The **OWASP Agentic Skills Top 10** (AST01–AST10) operationalised as eleven installable
agent skills: ten per-category detector skills that audit a candidate skill package
before you install it, plus one advisory skill that triages a free-text finding to its
primary AST category using the whitepaper's own decision tree.

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

Three ways in. All of them install the same eleven skill packages.

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
node cli/bin/cli.js audit fixtures/AST01/V1-obfuscated-payload --fail-on-detect
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

`F1` is the number the category publishes today, in the manifests' own vocabulary:

- **`pending-detector`** — the category has a labeled, class-balanced fixture corpus, and
  no shipped detector function consumes it yet. The denominator exists; the measurement
  does not.
- **`declared-and-uncovered`** — the labeled detectable tier is *empty*. Per the never-pad
  rule this category publishes no F1 at any corpus size, and says so in its matrix rather
  than manufacturing a number off fixtures written to separate perfectly.

| AST | Skill | What it detects | F1 |
| --- | --- | --- | --- |
| AST01 | `ast01-malicious-skills` | Hidden payloads in an otherwise-legitimate package — credential stealers, backdoors, and the natural-language instruction layer that carries a payload with zero suspicious code | `pending-detector` |
| AST02 | `ast02-supply-chain-compromise` | Registry flooding, dependency confusion in a nested `requirements.txt` / `package.json`, config-file hijacking, maintainer account takeover | `declared-and-uncovered` |
| AST03 | `ast03-over-privileged-skills` | Permission manifests broader than the stated function, write scopes reaching secrets or admin scope, undeclared shell exec, wildcard egress | `pending-detector` |
| AST04 | `ast04-insecure-metadata` | Brand-impersonating names, permission-understating manifests, `risk_tier` spoofing, unsafe YAML/JSON/TOML deserialization at load time | `pending-detector` |
| AST05 | `ast05-untrusted-external-instructions` | Skills that fetch external documents and follow them as instruction rather than treat them as data; missing provenance boundaries; remote responses reaching an executable sink | `pending-detector` |
| AST06 | `ast06-weak-isolation` | Execution in the host agent's own security context — full filesystem, shell and network — because sandboxing is optional, absent, or escaped | `pending-detector` |
| AST07 | `ast07-update-drift` | Unpinned installs, rollback attacks, hot-reload abuse, auto-update onto a malicious "patch" release | `declared-and-uncovered` |
| AST08 | `ast08-poor-scanning` | Natural-language-only malicious intent, shell-parsing evasion, zero-width / bidi / homoglyph smuggling, scanner impersonation, missing scan attestation | `pending-detector` |
| AST09 | `ast09-no-governance` | No inventory, no approval workflow, orphaned skills after offboarding, regulated-data exposure with no audit trail | `declared-and-uncovered` |
| AST10 | `ast10-cross-platform-reuse` | Security metadata — `risk_tier`, permissions, signatures, `deny_write` — silently dropped when a skill is ported between runtimes | `declared-and-uncovered` |
| — | `advisory` | Not a detector. Routes a free-text finding to its primary AST category via the whitepaper's decision tree and returns category-specific remediation | not scored on F1 (judged on guidance quality) |

Four of the ten publish nothing, and that is the honest reading of the registry rather
than a gap in the work: AST07 and AST09 have **zero** static-detectable scenarios in the
whitepaper's own enumeration (every scenario is temporal or organisational), and AST02 and
AST10 each have exactly one, unlabeled and unimplemented. See each category's
`coverage-matrix.md` for the per-scenario reasoning and the evidence that would decide it.

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
- **No published F1 for four of ten categories**, and `pending-detector` for the other six.
  The fixture corpora are class-balanced and real; the detector functions that consume them
  are largely not written yet. The coverage matrices name every gap.
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
python3 eval/generate_dashboard.py              # rewrite the dashboard results table
ruff check . && ruff format --check .           # exactly what CI runs; see ruff.toml
```

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
