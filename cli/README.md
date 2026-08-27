# `cli/` — command-line entry points

This repository is an independent community reference implementation of the OWASP
Agentic Skills Top 10. It is **not** an official OWASP project and carries no OWASP
endorsement, despite the repository name (see [`NOTICE`](../NOTICE)).

Two entry points ship here. They read the same manifests and are tested against each
other, so it does not matter which one a reader reaches for.

| | `cli/ast10.py` | `cli/bin/cli.js` |
| --- | --- | --- |
| Runtime | Python 3.11+, PyYAML | Node 18+, **zero** npm dependencies |
| Installs skills into a runtime | `install` | — |
| Lists the eleven skills | `list` | `list`, plus `--tier` |
| Triages a finding | `route` (JSON) | `route` (prints the matched rule) |
| Per-category coverage | `status` | `coverage` |
| Runs the detectors over a package | — | `audit <path>` |
| Repo/provider readiness | — | `status` |

`tests/test_cli.py` asserts the two agree on every per-category number and on routing.

## The Node CLI

```bash
node cli/bin/cli.js help
node cli/bin/cli.js list --tier static-detectable
node cli/bin/cli.js route "the scanner missed an obfuscated instruction"
node cli/bin/cli.js audit fixtures/AST01/V1-obfuscated-payload-exec
node cli/bin/cli.js audit fixtures/AST01/V1-obfuscated-payload-exec --sarif > ast10.sarif
node cli/bin/cli.js coverage
node cli/bin/cli.js status
```

Every command takes `--json`. `audit` takes `--fail-on-detect`, which exits 1 when any
check fires — the form to use in a pre-install gate.

### Reading a `list` row

Each row prints two counts, under two different nouns, because they are two different
quantities:

```
  AST01    ast01-malicious-skills
           11 scenarios: 7 static-detectable, 3 agent-judgable, 1 out-of-artifact  ·  10 checks shipped
```

**scenarios** are the whitepaper's named attack scenarios for the category, at the tier
`scenarios/registry.yaml` assigns each one. `list` reads them from the module's
`SCENARIO_TIERS`, which mirrors the registry, so these are the same numbers `coverage`
prints from the registry directly. **checks** is the size of the module's `DETECTORS` map.

The distinction is load-bearing and it was once got wrong here. While `SCENARIO_TIERS` was
keyed by check ids in six of the ten modules, `list` counted checks and labeled them with a
scenario tier — printing `AST01 [static-detectable x10]` against a registry that rules
seven AST01 scenarios static-detectable. One scenario can take several checks to decide,
and several checks decide no named scenario at all; each module's `CHECK_COVERAGE` rules on
every check individually, and `tests/test_scenario_tiers_are_registry_keyed.py` keeps the
two tables from merging again.

`--tier` filters to the skills that *declare* at least one scenario at that tier — for
`out-of-artifact` that is the tier no package can decide, so it selects categories by what
they publish as out of reach, not by what they detect.

### What it reads directly, and what it delegates

`cli/bin/cli.js` reads **data** out of the repository's own artifacts: SKILL.md
frontmatter, `scenarios/registry.yaml`'s tier lines, `fixtures/manifest.yaml`'s
per-category counters, `config/audit.yml`'s provider declarations. Because it ships with
no runtime dependencies, it scans those YAML files with narrow, indentation-anchored line
matchers rather than a parser — and `tests/test_cli.py` re-derives every number with
PyYAML and fails on any disagreement, so the shortcut cannot drift into wrong output.

It never re-implements a **decision**. `route` and `audit` shell out to
[`cli/lib/bridge.py`](lib/bridge.py), which calls:

- `skills/advisory/scripts/triage.py` — the whitepaper's own "Which AST Does My Finding
  Belong To?" decision tree, including its branch-5 rule that overlap is recorded as a
  contributing control failure and never split into a second primary;
- `skills/AST01..AST10/scripts/detector.py` — the per-category detectors;
- `scripts/dogfood.py` — the single USF v1 → detector-package shape translator.

So `route` and `audit` need `python3` on PATH. Override the interpreter with
`AST10_PYTHON`. `list`, `coverage` and `status` are pure Node.

### Reading an `audit` report

`audit` prints every check, **including the ones that did not fire**, and names every
category that ships no static detector. A detector that only reports hits is
indistinguishable from a detector that never ran, which is the AST08 failure this repo is
about.

Two package views are used, deliberately:

- AST01's content-hash pair runs over the **declared shipped surface**
  (`scripts/content_hash.py`'s `SURFACE_GLOBS`), so a well-formed package never reports a
  mismatch the harness itself manufactured;
- every other detector runs over **all text files**, because a candidate's `package.json`
  or `pyproject.toml` is exactly where AST04's findings live and neither is part of that
  surface.

The findings are detector-level **checks** — each module's own `DETECTORS` — and are
**not** coverage of the whitepaper's named scenarios. Each module's `CHECK_COVERAGE` says
so per check, in `fixtures/manifest.yaml`'s vocabulary (`full`, `artifact-signal-only`,
`category-precondition`), and `f1_report` returns the resulting `F1_SCOPE` beside any
number. The per-*scenario* tiers are a different table, `SCENARIO_TIERS`, which mirrors
`scenarios/registry.yaml` and is what `list` and `coverage` count. For the full picture,
read
`skills/<AST>/coverage-matrix.md`, or run `coverage`, which reports what each category
publishes and, where it publishes no F1, which of the two distinct reasons applies:

- `declared-and-uncovered` — the detectable tier is empty, so no number is published and
  the corpus is never padded to manufacture one;
- `pending-detector` — a labeled corpus exists and no detector consumes it yet. **No
  category is in this state today**; the CLI keeps the branch so that a corpus landing
  ahead of its detector reports as unmeasured rather than as measured-at-zero.
