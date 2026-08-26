---
artifact: adr
version: "1.0"
created: 2026-08-25
updated: 2026-08-25
status: accepted
supersedes: "0004, in part — gate-4's case-count rule only. Every other clause of the per-scenario detectability contract stands unchanged."
---

# ADR-0007: Gate-4's Case Count Is a Floor, Not an Equality

## Status

Accepted, and implemented in `fixtures/test_manifest.py`.

## Context

Gate-4 sized every category's labeled corpus by

    cases == max(MIN_FLOOR, 2 * detectable_scenarios)      MIN_FLOOR = 6

and `fixtures/test_manifest.py` asserted that as an **equality**. The floor did the work it
was designed for: AST02 has exactly one static-detectable scenario, so `2 * 1 = 2` is
raised to 6, and that is what pushed its corpus to encode AST02-S03 in three distinct
surfaces rather than one shape three times. `skills/AST02/coverage-matrix.md` says so.

The equality has a second effect that was never argued for. It forbids a category from
carrying **more** cases than the formula yields, so a corpus cannot be strengthened by
adding a further real surface of a scenario it already covers. Extending AST02's
config-file-hijacking check to Codex's `.codex/config.toml` — a project-scoped file that
ships inside a repository and whose `[mcp_servers.*]` entries carry `command`/`args` that
spawn a process — produced exactly that: a fourth vulnerable/clean pair encoding the same
scenario through a mechanism the first three do not reach, which gate-4 rejected purely for
being additional.

That is the formula preventing coverage rather than guaranteeing it.

## Decision

**Gate-4's case count is a minimum.** The assertion becomes

    cases >= max(MIN_FLOOR, 2 * detectable_scenarios)      MIN_FLOOR = 6

`MIN_FLOOR` does not move, the doubling term does not move, and the empty-tier branch is
untouched: a category whose detectable tier is empty still ships zero cases, publishes no
F1, and is never padded. That branch is the never-pad rule and this ADR does not weaken it.

Two existing guards already bound the corpus from the other side, which is why relaxing
this one does not open a hole:

- `fixtures/test_manifest.py::test_cases_are_class_balanced` keeps vulnerable and clean
  counts equal, so cases cannot be added on one side to move a number.
- `tests/test_corpus_discriminates_mechanism.py` requires every added clean case to be a
  near miss that a syntax-only baseline trips, and re-derives the ablation F1 that each
  coverage matrix quotes. A case added to inflate a score has to survive an ablation that
  is recomputed in the same run.

## Consequences

- AST02 ships **8** cases against a floor of 6, and publishes
  `scenario-level 1.000 (AST02-S03, n=8)`.
- The ablation baseline in `tests/test_corpus_discriminates_mechanism.py` now reads TOML as
  well as JSON. A clean case no baseline reaches is not a near miss; without this the Codex
  pair would have passed the discrimination guard by being invisible to it.
- The measured syntax-only baseline moves from `tp 2, fp 1, fn 1` to `tp 3, fp 2, fn 1`,
  F1 `0.667` either way, and `skills/AST02/coverage-matrix.md` is corrected in this change.
- A category may now grow its corpus without a registry change. What it may **not** do is
  publish an F1 over a tier the registry leaves empty, or add an unbalanced or
  non-discriminating case; those are still failures.

## What this ADR does not claim

It does not claim the four surfaces are all of AST02-S03's surfaces. OpenClaw is a
declared USF platform and no auto-executing, package-shippable config surface was found for
it in its documentation; none is encoded here rather than one being invented.
