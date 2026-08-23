# Third-Party Licenses

This document catalogues the third-party source vendored into
`owasp-ast10-agent-skills`. The vendoring choice is recorded in spec.md
gate-3 ("Vendor a standalone copy of `ship_floor.py`, `content_hash.py`,
`eval_counts.py` into `scripts/` ... No live dependency on another repo") and
its rationale in plan.md's "Risky code touchpoints" (T-2.2): the pooled
Grade-A aggregate rule must match "the exact formula locked at Gate B half 1"
bit for bit, so a copy — not a live import across repos — is the only way to
guarantee this repo and its upstream can never silently diverge without a
visible re-vendor.

## License-compatibility policy

This repo is a provider-agnostic GitHub publication (spec.md contract) and
follows the same compatibility policy as its vendoring source,
`REDACTED-SIBLING-REPO`:

Acceptable license families:

- Apache-2.0, MIT, BSD (2-clause, 3-clause), ISC — fully permissive
- Python Software Foundation License (PSF-2.0) — permissive

**NOT** compatible, and SHALL trigger review before any new dependency or
vendored source introduces them: GPL (v2, v3, LGPL), AGPL, SSPL, BUSL,
Commons Clause, CC-BY-NC.

## Vendored files (`scripts/`)

`scripts/ship_floor.py`, `scripts/content_hash.py` and `scripts/eval_counts.py`
are standalone copies of the same-named files from
[REDACTED-SIBLING-REPO](https://example.invalid/redacted-sibling-repo)
(Apache License, Version 2.0; Copyright 2026 Votee AI). No live dependency —
each file is a plain-copy snapshot living in this repo's own `scripts/`.

| Path | Upstream | Copyright | License | Vendored at commit |
| --- | --- | --- | --- | --- |
| `scripts/ship_floor.py` | `REDACTED-SIBLING-REPO` `scripts/ship_floor.py` | 2026 Votee AI | Apache-2.0 | `34ac48d680323ce4b5302c8a756db6327984b59e` |
| `scripts/content_hash.py` | `REDACTED-SIBLING-REPO` `scripts/content_hash.py` | 2026 Votee AI | Apache-2.0 | `34ac48d680323ce4b5302c8a756db6327984b59e` |
| `scripts/eval_counts.py` | `REDACTED-SIBLING-REPO` `scripts/eval_counts.py` | 2026 Votee AI | Apache-2.0 | `34ac48d680323ce4b5302c8a756db6327984b59e` |

Upstream publishes no semver tags as of the vendored commit (`git describe
--tags` returns no names); the commit SHA above is the pin, per plan.md T-2.2
("recording the upstream commit hash and semver tag of whatever is copied").

**What was kept verbatim vs. adapted**, so drift is auditable file-by-file:

- `content_hash.py` — copied unmodified (the `content_sha256()` algorithm and
  `SURFACE_GLOBS` are generic; only the module docstring gained a provenance
  note pointing here).
- `eval_counts.py` — `MIN_EVALS`, `MIN_NEGATIVE_EVALS`, `is_negative_eval()`
  and its regex are copied unmodified. `EVAL_COUNTS` is **not** copied: it is
  keyed upstream by `REDACTED-SIBLING-REPO`' own skill directory names,
  which do not exist in this repo. It starts as an empty dict here, to be
  populated by T-3.x once this repo's own `AST01`.."AST10"` + advisory skills
  are authored — same contract (keyed by skill directory name), no data.
- `ship_floor.py` — the aggregate formula itself is copied unmodified and
  MUST stay that way without a deliberate re-vendor: `FLOORS`, `POOLED_TARGET`
  (108), `POOLED_LOWER_BOUND` (105), `MIN_ROUNDS` (4), `AGG_METHOD`,
  `RUBRIC_SHA`, `INDEPENDENT_METHODS`, `pooled_stats()`, `dim_means_of()`,
  `aggregate_verdict()`, `verdict_of()`, `_is_invalidated()`, `binding_block()`
  are all byte-identical to upstream. Upstream's `A_MINUS`/`MANDATED` skill-name
  sets and the delivery-floor check in `main()` were **dropped**: those name
  `REDACTED-SIBLING-REPO`' own skill roster and are not part of the
  formula — this repo's spec/plan define no equivalent "mandated area"
  concept. `main()` here is a thin, repo-local driver over the same
  `aggregate_verdict()` rule, reading `OWASP_AST10_ROOT` (was `MMAS_ROOT`
  upstream) instead.

All three files are Apache-2.0, the same license family as this repo, so no
compatibility review is required for the copy itself.

## Rubric pin (not yet vendored as a tree)

`ship_floor.py`'s `RUBRIC_SHA` constant pins the same skill-judge rubric
version (`3027f20f3181758385a1bb8c022d4041dfb4de84`) that
`REDACTED-SIBLING-REPO` vendors at `vendor/skill-judge/` from
[softaworks/agent-toolkit](https://github.com/softaworks/agent-toolkit)
(`skills/skill-judge`, MIT, (c) 2026 Leonardo Flores) — spec.md's contract:
"scored ... against the pinned 8-dimension skill-judge rubric." This repo
does not yet vendor its own copy of the rubric tree itself (out of T-2.2's
scope); `RUBRIC_SHA` only pins which version any recorded `scores.json`
`aggregate.rubric_sha` must match. Vendoring `vendor/skill-judge/` here,
mirroring the pattern above, is tracked as follow-up work, not silently
assumed done.

## Audit metadata

- **Audit date:** 2026-08-21
- **Scope:** `scripts/ship_floor.py`, `scripts/content_hash.py`,
  `scripts/eval_counts.py` (T-2.2)
- **Scan result:** PASS — both license families present (Apache-2.0 vendored
  code; this repo's own license posture) are mutually compatible
