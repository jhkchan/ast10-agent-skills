# owasp-ast10-agent-skills

The [**OWASP Agentic Skills Top 10**](https://owasp.org/www-project-agentic-skills-top-10/)
(AST01–AST10) operationalised as eleven installable agent skills: one per AST category plus
an advisory skill that triages a free-text finding to its primary category using the
whitepaper's own decision tree.

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

- The **OWASP Agentic Skills Top 10** — the real project lives at
  [owasp.org/www-project-agentic-skills-top-10](https://owasp.org/www-project-agentic-skills-top-10/)
  — is the source publication this repository implements. Full credit for the taxonomy,
  the attack-scenario catalog, the decision tree, and the Universal Skill Format proposal
  belongs to that project and its contributors. Go read it there, not here.
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

Eleven skills: one per AST category, plus `advisory`, which is not a detector. Eight
categories ship an executable detector; `AST07` and `AST09` ship none, because nothing in one
package at one moment can decide their scenarios. The cells below are one-liners — the full
description of every shipped check is in [What each detector
decides](#what-each-detector-decides), and the vocabulary both tables use is in [Reading the
columns](#reading-the-columns).

| AST | Skill | What the detector decides | Detector state |
| --- | --- | --- | --- |
| AST01 | `ast01-malicious-skills` | Ten checks: identity-file writes, hash gaps, concealed and encoded egress | `implemented` |
| AST02 | `ast02-supply-chain-compromise` | One check: a config value the host auto-executes at project open | `implemented` |
| AST03 | `ast03-over-privileged-skills` | Four checks: identity-file write grants, no write floor, unbounded shell and egress | `implemented` |
| AST04 | `ast04-insecure-metadata` | Six checks: manifest contradicted by code, understated risk tier, executable parse constructs | `implemented` |
| AST05 | `ast05-untrusted-external-instructions` | Five checks, every one a precondition: fetched content reaching an instruction or execution sink | `implemented` |
| AST06 | `ast06-weak-isolation` | Five checks: host-persistence writes, root and home write scope, unbounded shell | `implemented` |
| AST07 | `ast07-update-drift` | **No check ships, and none can** — every scenario compares two versions | `declared-and-uncovered` |
| AST08 | `ast08-poor-scanning` | Four checks: decode-and-rescan, environment-armed branches, scanner-host hazards, stale bytecode | `implemented` |
| AST09 | `ast09-no-governance` | **No check ships, and none can** — every scenario lives in an organisation, not a package | `declared-and-uncovered` |
| AST10 | `ast10-cross-platform-reuse` | One check: an encoded payload judged after decoding, at the content layer | `implemented` |
| — | `advisory` | Not a detector — routes a free-text finding to its primary category | n/a — not a detector |

That column is the **check roster** — only checks that exist and run today — not the
category's subject matter. For what a category covers as *knowledge*, read its `SKILL.md`;
for what is decidable, what is refused, and why, read its `coverage-matrix.md`.

### Measured results

Two independent measurements, and collapsing them is the mistake this table exists to
prevent. **F1** is what the *detector* was measured at over the labeled fixture corpus.
**Judged** is what an independent judge panel scored the *knowledge package* — the `SKILL.md`
— against the skill-judge rubric. A category with no detector at all can still be a strong
skill, and a perfect F1 does not clear the judge gate. Per-judge scores and bias diagnostics
are in [`docs/skill-judge-dashboard.md`](docs/skill-judge-dashboard.md); the rubric behind
that column is third-party work, [credited in
full below](#what-11-of-11-is-and-what-it-is-not).

| Skill | F1 (measured) | Judged (run 5) |
| --- | --- | --- |
| `ast01-malicious-skills` | `scenario-level 1.00 (n=16)` | **SHIP** 110.1 |
| `ast02-supply-chain-compromise` | `scenario-level 1.00 (n=6)` | **SHIP** 111.8 |
| `ast03-over-privileged-skills` | `scenario-level 1.00 (n=2)` + `artifact-signal-only 1.00 (n=4)` | **SHIP** 112.2 |
| `ast04-insecure-metadata` | `scenario-level 1.00 (n=10)` | **SHIP** 111.6 |
| `ast05-untrusted-external-instructions` | `artifact-signal-only 1.00 (n=6)` | **SHIP** 110.6 |
| `ast06-weak-isolation` | `scenario-level 1.00 (n=4)` + `artifact-signal-only 1.00 (n=2)` | **SHIP** 112.1 |
| `ast07-update-drift` | `declared-and-uncovered` | **SHIP** 110.2 |
| `ast08-poor-scanning` | `scenario-level 1.00 (n=8)` | **SHIP** 109.7 |
| `ast09-no-governance` | `declared-and-uncovered` | **SHIP** 111.1 |
| `ast10-cross-platform-reuse` | `scenario-level 1.00 (n=6)` | **SHIP** 112.4 |
| `advisory` | not scored — judged on guidance quality | **SHIP** 112.2 |

Every F1 above is printed in one shape, `scope value (n)`, because a number quoted without
its scope is the overclaim the labels exist to block; the manifest's own string for each one,
parenthetical and all, is in that skill's block below. Every verdict and pooled mean is
recomputed by `scripts/ship_floor.py` from `eval/scorecards/<AST>.json` rather than copied
from a stored field.

**Eleven of the eleven skills clear the ship rule**: pooled mean ≥ 108, the confidence bound
`mean − 1.0 × σ/√n` ≥ 108, and all eight dimension means above their floors, over 16 to 18
pooled judgments from six independent judges. **The same board is 8 of 11 without the panel's
least discriminating judge, and one of the eleven does not survive imputation of its own
missing judgments** — both measured, both in [How fragile 11 of 11
is](docs/skill-judge-dashboard.md#how-fragile-11-of-11-is). Read that number with them and
with [What 11 of 11 is, and what it is not](#what-11-of-11-is-and-what-it-is-not) below — it
is four paragraphs and it is not decoration.

### What each detector decides

One block per skill, holding the description the roster above compresses to a line, the F1
exactly as `fixtures/manifest.yaml` records it, and that category's scenario-by-scenario matrix.

<details><summary><b>AST01</b> · <code>ast01-malicious-skills</code> · ten checks</summary>

Ten checks: `content_hash` absent or mismatched; install prose that pipes a remote fetch into a
shell; a declared or coded write to `SOUL.md`; the same for `MEMORY.md`; a script that both reads
an identity artifact and sends outbound; a WebSocket to an undeclared host; a hardcoded egress
destination outside the declared allowlist; concealed instructions in the package's own output
templates; an encoded blob decoded into an execution sink. Manifest F1
`scenario-level 1.000 (8 labeled checks, n=16)`;
[`skills/AST01/coverage-matrix.md`](skills/AST01/coverage-matrix.md).

</details>

<details><summary><b>AST02</b> · <code>ast02-supply-chain-compromise</code> · one check</summary>

One check: a command-bearing value in a config file the host auto-executes **at project open** —
`.claude/settings.json` hooks, an MCP/env control-plane override, a `.vscode/tasks.json`
`folderOpen` task. Registry flooding, dependency confusion and maintainer-account takeover are
tiered `out-of-artifact` and no check claims them. Manifest F1
`scenario-level 1.000 (AST02-S03, n=6)`;
[`skills/AST02/coverage-matrix.md`](skills/AST02/coverage-matrix.md).

</details>

<details><summary><b>AST03</b> · <code>ast03-over-privileged-skills</code> · four checks</summary>

Four checks: a declared write grant reaching the agent's own identity files (`SOUL.md`,
`MEMORY.md`, `AGENTS.md`); no declared write floor at all; shell execution combined with unbounded
egress; a blanket or wildcard egress declaration in place of an enumerated domain allowlist. Only
the first covers a named scenario — the other three are a precondition and two signals. Manifest
F1 `scenario-level 1.00 (AST03-S03, n=2); artifact-signal-only 1.00 (n=4)`;
[`skills/AST03/coverage-matrix.md`](skills/AST03/coverage-matrix.md).

</details>

<details><summary><b>AST04</b> · <code>ast04-insecure-metadata</code> · six checks</summary>

Six checks: a declared allowlist contradicted by the destination a bundled script actually reaches;
`risk_tier` below the floor its own permissions derive; code-executing YAML tags and unsafe
loaders; `__proto__` / `constructor` keys in shipped JSON next to an unsafe merge site; redefined
TOML tables; invisible code points (flagged as a carrier class and stopped there, not convicted as
an instruction). Manifest F1 `scenario-level 1.00 (n=10)`;
[`skills/AST04/coverage-matrix.md`](skills/AST04/coverage-matrix.md).

</details>

<details><summary><b>AST05</b> · <code>ast05-untrusted-external-instructions</code> · five checks, no scenario covered</summary>

Five checks, **every one a precondition**: a fetched document reaching an instruction sink; a
remote response body reaching an executable sink; decision rules that consume upstream content with
no provenance boundary; a blanket egress grant; a wildcard entry in the declared allowlist. The
registry tiers all six AST05 scenarios `agent-judgable` or `out-of-artifact`, so none of these
covers one. Manifest F1 `artifact-signal-only 1.00 (n=6)`;
[`skills/AST05/coverage-matrix.md`](skills/AST05/coverage-matrix.md).

</details>

<details><summary><b>AST06</b> · <code>ast06-weak-isolation</code> · five checks</summary>

Five checks: a bundled script that shell-execs or writes a host-persistence path; a declared write
scope reaching the filesystem root or the home directory; shell granted with no bounding command
list; declared writes into a shared workspace namespace; an absent or empty permissions block. The
first two decide AST06-S01's two disjuncts; the rest are a precondition and two signals. Manifest
F1 `scenario-level 1.00 (AST06-S01, n=4); artifact-signal-only 1.00 (n=2)`;
[`skills/AST06/coverage-matrix.md`](skills/AST06/coverage-matrix.md).

</details>

<details><summary><b>AST07</b> · <code>ast07-update-drift</code> · no check ships</summary>

**No check ships, and none can.** All three AST07 scenarios — malicious update, rollback,
hot-reload abuse — are defined by a *change between versions*, and one package at one moment
carries no second version to compare against. The skill is knowledge only; `coverage-matrix.md`
names the version-history evidence that would decide each one. Manifest F1
`declared-and-uncovered`; [`skills/AST07/coverage-matrix.md`](skills/AST07/coverage-matrix.md).

</details>

<details><summary><b>AST08</b> · <code>ast08-poor-scanning</code> · four checks</summary>

Four checks: an obfuscated instruction found by decode-and-rescan over the normalized view
(comparing match counts per view, so a decoy in the clear cannot mask a smuggled copy); a branch
that arms only under a specific environment; scanner-host hazards (padding runs, recursive
archives, decompression ratio, symlink escape); bytecode the import machinery would prefer over its
own source. Manifest F1 `scenario-level 1.00 (4 scenario checks, n=8)`;
[`skills/AST08/coverage-matrix.md`](skills/AST08/coverage-matrix.md).

</details>

<details><summary><b>AST09</b> · <code>ast09-no-governance</code> · no check ships</summary>

**No check ships, and none can.** All seven AST09 scenarios are `out-of-artifact`: inventory,
approval, ownership and offboarding live in an organisation's process, not in a package. The skill
is knowledge only; `coverage-matrix.md` names the governance-system evidence that would decide each
one. Manifest F1 `declared-and-uncovered`;
[`skills/AST09/coverage-matrix.md`](skills/AST09/coverage-matrix.md).

</details>

<details><summary><b>AST10</b> · <code>ast10-cross-platform-reuse</code> · one check</summary>

One check: a payload hidden in an encoded blob that survives a port — decoded (base64, hex escapes,
gzip-under-base64), then judged at the *content* layer, so a package carrying a legitimate encoded
blob is not convicted for carrying one. Security metadata stripped during a port can be narrated
inside a fake `SKILL.md`, so it is tiered `out-of-artifact` and no check claims it. Manifest F1
`1.0`, its scope `scenario-level` carried in the sibling `f1_scope` field;
[`skills/AST10/coverage-matrix.md`](skills/AST10/coverage-matrix.md).

</details>

<details><summary><b>advisory</b> · <code>advisory</code> · not a detector</summary>

Not a detector. Routes a free-text finding to its primary AST category via the whitepaper's
decision tree and returns category-specific remediation. It has no fixture corpus and no F1 at any
corpus size; the judge panel scores it on guidance quality like every other knowledge package,
which is why it carries a verdict and no number.

</details>

### Reading the columns

Three independent states per category, and collapsing them is the mistake the two tables exist
to prevent: one says what code exists, one says what the detector was measured at, and one
says how the *knowledge package* scored against an independent judge panel. A category can
have no detector at all and still be a strong skill, and a category with a perfect F1 can
still be blocked by the judge gate.

**Detector state** — derived, not asserted. `scenarios/registry.yaml` is authoritative on
which scenarios are `static-detectable`; `fixtures/manifest.yaml` is authoritative on
which of those carry a shipped check and a labeled fixture pair.
`tests/test_docs.py::test_readme_detector_state_matches_the_state_derived_from_the_manifests`
re-derives every value in the roster from those two files and fails on drift, so that column
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

**F1 scope** — what was measured, normalised to `scope value (n)` and derived from
`fixtures/manifest.yaml`. Every number carries the scope it was measured at:

- **`scenario-level`** — measured over checks that decide a named whitepaper scenario's
  *defining condition*.
- **`artifact-signal-only`** — measured over checks that decide an enabling *precondition*
  a benign package can also exhibit (an unbounded retry loop, an unpinned reference, an
  absent permissions block). It is **not** coverage of any named scenario and may never be
  quoted as one. AST05 publishes only this.
- **two entries joined by `+`** — a `mixed-proxy` category, scored separately per scope so the
  proxy half cannot ride on the scenario half. The manifest writes the same split with a `;`.
- **`declared-and-uncovered`** — no number, at any corpus size. This is the never-pad rule:
  an empty detectable tier is reported as empty rather than filled with fixtures written to
  separate perfectly.
- **AST10 alone** stores `published_f1` as a JSON float rather than a labeled string. Its
  scope lives in the sibling `f1_scope` field and its `n` in `cases_present`, which is where
  the results table gets the label it prints beside the number, and what
  `python3 cli/ast10.py status` prints beside it too.

### Four readings that are easy to get backwards

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

### How the ship gate was set

**The gate has been changed exactly once, and run 5 is the first corpus judged under the change.**
After run 4 was published, [ADR-0006](docs/adr/0006-confidence-bound-on-the-pooled-mean.md)
retired the `mean − σ ≥ 105` clause and replaced it with `mean − 1.0 × σ/√n ≥ 108` — a confidence
bound on the mean instead of a spread statistic — because the retired clause was shown not to be a
function of the artifact: `AST08`'s `SKILL.md` is byte-identical between runs 3 and 4 and that
clause alone flipped its verdict. The replacement constant was recorded **before** the run judged
by it, and it bought nothing **on the corpus it was adopted against**: nine of eleven shipped under
either rule on the run-4 corpus, and no verdict changed. That is checked, not asserted —
`tests/test_generate_dashboard.py` re-derives all eleven run-4 verdicts through today's gate
against the frozen `eval/scorecards-run4/`.

**On run 5 it bought a ship, and that has to be said in the same breath.** Under the retired clause
run 5 is **10 of 11**: `AST01` clears the mean (110.1 ≥ 108) and misses `mean − σ` at
110.1 − 6.65 = **103.4**, against 105. Under the clause in force it is 11 of 11. The change was
recorded before the run and no constant moved to produce that, but "the new rule costs nothing" is
a claim about run 4 and is false about run 5.

Nor is the confidence bound reliably the *stricter* rule. `mean − σ ≥ 105` and
`mean − σ/√n ≥ 108` are the bars `mean ≥ 105 + σ` and `mean ≥ 108 + σ/√n`, so the adopted clause
demands more only when `σ < 3/(1 − 1/√n)` — about 4.0 at `n = 16`. **At every one of run 5's eleven
`(n, σ)` pairs the adopted clause demands a lower mean than the retired one**, by 0.12 to 1.99
points, because this run's per-skill σ never falls below 4.16. Across all five recorded runs — 55
skill-runs — it has demanded a strictly higher mean on exactly three (`advisory` in run 3 at
σ 3.44, and `AST04` and `AST05` in run 4), with one exact tie (`AST06` in run 4, both clauses
demanding 109.04) counted apart from them. ADR-0006 replaced a clause that was **not a function of the artifact**;
it did not replace it with a uniformly stricter one, and on the corpus it now gates it is the more
permissive of the two.

`AST01` is the row where all of this lands at once: it is the skill the gate change buys, the skill
three of six single-judge exclusions block, and the skill whose two missing judgments flip it when
they are refilled at the means of the judges that lost them. See
[How fragile 11 of 11 is](docs/skill-judge-dashboard.md#how-fragile-11-of-11-is).

---

## What 11 of 11 is, and what it is not

Every skill in the table above clears the ship rule. That is the best number this repository has
ever published and it is the one most likely to be misread, so the four limits on it sit here
rather than in a footnote. The full board, the per-judge bias table and the judge-quality
diagnostics are in
[`docs/skill-judge-dashboard.md`](docs/skill-judge-dashboard.md).

The rubric those scores are graded *against* is not this project's work.
[**skill-judge**](https://github.com/softaworks/agent-toolkit/tree/main/skills/skill-judge),
from **softaworks/agent-toolkit**, (c) 2026 **Leonardo Flores**, **MIT** — that is the
8-dimension, 120-point rubric behind every judged number on this page. Its dimensions D1–D8,
their weights, and the per-dimension floors this repository's ship gate enforces are all its
definitions, not ours: this repo vendors the rubric and applies it, it did not author it, and
softaworks endorses this repository no more than OWASP does. It ships here verbatim at
[`vendor/skill-judge/SKILL.md`](vendor/skill-judge/SKILL.md), with its MIT licence and
[`vendor/skill-judge/PROVENANCE.md`](vendor/skill-judge/PROVENANCE.md) beside it, and it is
pinned twice: `RUBRIC_SHA` names the upstream commit, and `RUBRIC_CONTENT_SHA256` hashes the
vendored bytes — recomputed by `tests/test_rubric_pin.py` on every run, and re-asserted by the
judge harness before a prompt is built. A score here is therefore attributable to *specific
rubric bytes*, not to "the rubric" in the abstract.

**The corpus is self-authored.** The same project wrote the eleven skills, the fixtures, the
scenario registry *and* the rubric-grounded prompt the judges read. A high pooled score is
therefore evidence of **internal consistency** — these artifacts satisfy this repository's own
statement of what a good skill is — and it is **not** external validation. Nobody outside this
project has scored these files.

**The panel disagrees by most of a grade band.** Across the same eleven files the six judges span
an **11.4-point spread**, from `bedrock/qwen3-235b` at +6.5 to `bedrock/gpt-oss-120b` at −4.9,
while no judge moves more than 2.3 points between its own rounds — so the spread is systematic
bias, not noise. `bedrock/qwen3-235b` is `COARSE` on this run (79% of its dimension scores sit at
a dimension's maximum and 34% of its judgments return the full 120) and was flagged
`NON-DISCRIMINATING` on run 4; it is pooled into every published figure in both states, because
dropping a judge for what it said needs its own recorded decision. **Dropping it alone takes the
board to 8 of 11**: `AST01`, `AST07` and `AST08` fall below the confidence bound, at 106.7, 107.7
and 107.5. `AST01` fails on two further single-judge exclusions as well — drop
`anthropic-compatible/glm-5.2` and it reads 107.2, drop `claude-cli/sonnet` and it reads 107.7 —
so **three of the six possible single-judge exclusions block it**, and only three of the six leave
the board whole. The full table is in [How fragile 11 of 11
is](docs/skill-judge-dashboard.md#how-fragile-11-of-11-is). A pooled mean is a statement
about *the rubric as read by these six judges*, and
[ADR-0005](docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md) explains why it may not
be quoted beside a single-judge score.

**`k = 1.0` is one standard error of margin, and it is not a confidence level.** The judgments
behind a pooled mean are clustered — six judges read about three times each, each carrying a large
fixed offset — so they are not independent draws. Measured on run 4, the panel's intraclass
correlation is 0.666 and its design effect 2.15, which means `σ/√n` **understates** the true
standard error of the mean by roughly **1.47×**. The clause is published in points (it moves the
effective bar from 108.0 to about 109.2 here) and never as a percentage, and
[ADR-0006](docs/adr/0006-confidence-bound-on-the-pooled-mean.md) records the shortfall as the
first thing a future record should fix.

**Ten of the 198 attempted judgments never reached the pool, and the run that discarded them
recorded nothing.** The board is 188 binding judgments; the harness that refused the other ten
built its audit trail in memory, and the reasons and the raw responses are gone. Which skill,
judge and round each was IS recoverable from the order the surviving judgments are stored in, and
[`eval/run5-refusals.md`](eval/run5-refusals.md) is that reconstruction. It matters because the
gap is not neutral: **`AST01` lost the two judges that scored `AST01` lowest** (100.5 and 104.5
against its pooled 110.1), and replacing each missing attempt with that judge's own observed mean
on that skill puts `AST01` at 109.2 with a confidence bound of 107.6 — below the bar. Nothing is
imputed into any published figure and no verdict is re-issued; the eleventh ship simply depends on
two judgments nobody can produce. The harness now persists every refusal, and
`python3 scripts/refusal_ledger.py` fails if a scorecard's pooled `n` ever again falls below its
attempted `n` with nothing accounting for the difference.

Two further things a reader is entitled to know before quoting the count. `AST01` and `AST08`
clear the confidence bound by 0.4 and 0.7 points respectively, and this repository's own doctrine
says a threshold cleared by less than the instrument's run-to-run movement is not cleared.
And `AST09` went BLOCKED → SHIP between runs 4 and 5 **without its `SKILL.md` changing by a
byte**, on a pooled mean that rose 2.9 points: ADR-0006 stopped the gate depending on how much the
panel agreed, but nothing stops the mean itself moving between runs.

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
- **The judge scores are a panel's reading, not a measurement of quality.** Five runs are
  recorded and all eleven skills clear the ship rule on the fifth, but a pooled mean is
  a statement about the rubric *as read by these six judges*: they span 11.4 points on the
  same eleven files, the corpus and the rubric prompt are both self-authored, and the most
  generous judge is `COARSE` and still pooled. See
  [What 11 of 11 is, and what it is not](#what-11-of-11-is-and-what-it-is-not) above.
  [`docs/skill-judge-dashboard.md`](docs/skill-judge-dashboard.md) publishes the whole panel,
  the per-judge bias, the judge-quality diagnostics, and the providers that are unavailable
  from this environment and why. Do not quote a number from it next to a single-judge score:
  [ADR-0005](docs/adr/0005-judge-panel-calibration-and-the-lower-bound.md) explains why the
  two have different units.
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
python3 scripts/ship_floor.py                   # recompute every stored judge verdict in
                                                # eval/scorecards/ (and scores.json if present);
                                                # exits 1 if it finds neither
python3 eval/generate_f1_report.py              # re-measure every corpus, rewrite the F1 report
python3 eval/generate_dashboard.py              # rewrite the dashboard results table
python3 eval/calibration.py                     # judge bias, judge quality, and the robustness block
python3 eval/robustness.py                      # leave-one-judge-out + missing-data sensitivity alone
python3 scripts/refusal_ledger.py               # every discarded judgment must be on the record
ruff check . && ruff format --check .           # exactly what CI runs; see ruff.toml
```

Some of those write documents that are committed alongside the code, and each is
regenerated-and-compared by the test suite rather than trusted:

- [`docs/f1-report.md`](docs/f1-report.md) — every category's measured precision,
  recall and F1, with each individual case verdict recorded in
  [`eval/f1-report.json`](eval/f1-report.json) so any figure can be re-derived by
  hand. Written by `python3 eval/generate_f1_report.py`.
- [`docs/dogfood-report.md`](docs/dogfood-report.md) — every firing of every
  detector over this repository's own eleven skill packages, waived or not, with
  the reason for each waiver. Written by
  `python3 scripts/dogfood.py --markdown --out docs/dogfood-report.md`.
- [`docs/skill-eval-report.md`](docs/skill-eval-report.md) — the **with/without**
  eval delta. Written by `python3 eval/generate_skill_eval_report.py` from the
  committed runs under `eval/skill-eval-workspace/`.

### Three kinds of evidence, and what each one answers

They use three different units and are never averaged with one another:

| Surface | The question it answers |
| --- | --- |
| [Judge scores](docs/skill-judge-dashboard.md) | Is the **text** of a `SKILL.md` well written against the pinned eight-dimension rubric? No prompt is ever executed. Unit: a total out of 120. |
| [Detector F1](docs/f1-report.md) | Do the shipped Python check scripts separate this repository's own labelled vulnerable and clean fixtures? Real output measurement — of the scripts, not of an agent. Unit: precision/recall/F1 per category. |
| [With/without evals](docs/skill-eval-report.md) | Does an agent **holding** a skill behave better than the same agent holding nothing? Unit: the fraction of a case's hand-authored assertions a graded response satisfied, and the **delta** between the two arms. |

Only the third one has ever measured an agent's output. Every case in
`skills/*/evals/evals.json` runs twice — once with the skill installed, once
without it and nothing else changed — and the delta is the deliverable. The agent
under test and the grader are always different models, and both are recorded in
every artifact. Nothing on that surface feeds the ship gate.

```bash
python3 eval/skill_evals.py --dry-run            # the plan; writes nothing, calls nothing
python3 eval/skill_evals.py                      # run every case in both arms, grade, aggregate
python3 eval/skill_eval_grade.py review          # which assertions the skill actually moved
python3 eval/generate_skill_eval_report.py       # publish docs/skill-eval-report.md
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
whitepaper as source material, the vendored scoring pipeline, and the **skill-judge** rubric
(softaworks/agent-toolkit, (c) 2026 Leonardo Flores, MIT) vendored at
[`vendor/skill-judge/`](vendor/skill-judge/) under its own licence — plus the vendoring
policy are in [`NOTICE`](NOTICE) and
[`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).
