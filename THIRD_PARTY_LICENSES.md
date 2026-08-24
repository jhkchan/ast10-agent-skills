# Third-Party Licenses

This repository ships under the [Apache License, Version 2.0](LICENSE),
Copyright 2026 Jacky Chan. This document catalogues everything in it that
someone else owns.

| # | Component | Kind | License | Holder |
| --- | --- | --- | --- | --- |
| 0 | OWASP Agentic Skills Top 10 whitepaper | source material | see below | OWASP project + contributors |
| 1 | `scripts/ship_floor.py`, `scripts/content_hash.py`, `scripts/eval_counts.py` | vendored copy, commit-pinned | Apache-2.0 | 2026 Votee AI |
| 2 | skill-judge 8-dimension rubric (`vendor/skill-judge/`) | vendored verbatim, commit- and content-pinned | MIT | (c) 2026 Leonardo Flores |
| 3 | `PyYAML`, `jsonschema`, `cryptography` | installed dependency | MIT / MIT / Apache-2.0 OR BSD-3-Clause | upstream |

## Source material — the OWASP Agentic Skills Top 10 whitepaper

The whitepaper is not a dependency of this repository; it is the **source
material** the whole repository implements. Recorded here so the provenance
sits with the other attributions rather than only in prose:

| What | Where it lands in this repo |
| --- | --- |
| The AST01–AST10 taxonomy and category definitions | `skills/AST01/`..`skills/AST10/` |
| The named attack scenarios and their verbatim titles | `scenarios/registry.yaml` (62 scenarios), each category's `coverage-matrix.md` |
| The "Which AST Does My Finding Belong To?" decision tree | `skills/advisory/scripts/triage.py` |
| The Universal Skill Format (USF) v1.0 proposal | `schemas/usf-v1.schema.json`, `validators/usf.py`, every `skills/*/skill.usf.yaml` |

Credit for all of the above belongs to the OWASP Agentic Skills Top 10 project
and its contributors; **Ken Huang (DistributedApps.ai) is the project leader**
and originated the taxonomy. Scenario titles are reproduced verbatim for
identification and traceability — `tests/test_coverage_matrix*.py` fails on a
paraphrase, because a renamed scenario is an untraceable one.

**This repository is not an OWASP project** and carries no OWASP endorsement,
review, or affiliation, despite its name. Its maintainer is a credited entry in
the whitepaper's "Reviewers and Contributors" table — contributor credit on the
publication, not authorship of it and not leadership of the project. Where this
repository and the whitepaper disagree, the whitepaper is authoritative.
"OWASP" is a trademark of the OWASP Foundation, used descriptively here to
identify the standard being implemented. See `NOTICE` and the README
disclaimer.

## Vendoring rationale

The vendoring choice is recorded in spec.md
gate-3 ("Vendor a standalone copy of `ship_floor.py`, `content_hash.py`,
`eval_counts.py` into `scripts/` ... No live dependency on another repo") and
its rationale in plan.md's "Risky code touchpoints" (T-2.2): the pooled
Grade-A aggregate rule must match "the exact formula locked at Gate B half 1"
bit for bit, so a copy — not a live import across repos — is the only way to
guarantee this repo and its upstream can never silently diverge without a
visible re-vendor.

That guarantee has now done its job once. The two repositories **do** diverge, in
one clause of `ship_floor.py`, and the divergence is visible: it is recorded in
[`docs/adr/0006-confidence-bound-on-the-pooled-mean.md`](docs/adr/0006-confidence-bound-on-the-pooled-mean.md),
in `NOTICE`, in the file's own docstring, and per file below.

## License-compatibility policy

This repo is a provider-agnostic GitHub publication (spec.md contract) and
follows the same compatibility policy as its vendoring source (the
upstream eval-harness repository named in `NOTICE`'s attribution block):

Acceptable license families:

- Apache-2.0, MIT, BSD (2-clause, 3-clause), ISC — fully permissive
- Python Software Foundation License (PSF-2.0) — permissive

**NOT** compatible, and SHALL trigger review before any new dependency or
vendored source introduces them: GPL (v2, v3, LGPL), AGPL, SSPL, BUSL,
Commons Clause, CC-BY-NC.

## Vendored files (`scripts/`)

`scripts/ship_floor.py`, `scripts/content_hash.py` and `scripts/eval_counts.py`
are standalone copies of the same-named files from an upstream eval-harness
repository (Apache License, Version 2.0; Copyright 2026 Votee AI). Its slug is
not reproduced here — this project does not name sibling agent-skill
repositories in committed files, and Apache-2.0 section 4 attribution is
satisfied by the copyright holder, license and pinned commit recorded below.
No live dependency — each file is a plain-copy snapshot living in this repo's
own `scripts/`.

| Path | Upstream | Copyright | License | Vendored at commit |
| --- | --- | --- | --- | --- |
| `scripts/ship_floor.py` | upstream `scripts/ship_floor.py` | 2026 Votee AI | Apache-2.0 | `34ac48d680323ce4b5302c8a756db6327984b59e` |
| `scripts/content_hash.py` | upstream `scripts/content_hash.py` | 2026 Votee AI | Apache-2.0 | `34ac48d680323ce4b5302c8a756db6327984b59e` |
| `scripts/eval_counts.py` | upstream `scripts/eval_counts.py` | 2026 Votee AI | Apache-2.0 | `34ac48d680323ce4b5302c8a756db6327984b59e` |

Upstream publishes no semver tags as of the vendored commit (`git describe
--tags` returns no names); the commit SHA above is the pin, per plan.md T-2.2
("recording the upstream commit hash and semver tag of whatever is copied").

**What was kept verbatim vs. adapted**, so drift is auditable file-by-file:

- `content_hash.py` — copied unmodified (the `content_sha256()` algorithm and
  `SURFACE_GLOBS` are generic; only the module docstring gained a provenance
  note pointing here).
- `eval_counts.py` — `MIN_EVALS`, `MIN_NEGATIVE_EVALS`, `is_negative_eval()`
  and its regex are copied unmodified. `EVAL_COUNTS` is **not** copied: it is
  keyed upstream by that repository's own skill directory names,
  which do not exist in this repo. It starts as an empty dict here, to be
  populated by T-3.x once this repo's own `AST01`.."AST10"` + advisory skills
  are authored — same contract (keyed by skill directory name), no data.
- `ship_floor.py` — the aggregate formula was copied unmodified and has since
  been changed **exactly once**, by a recorded decision rather than by drift:
  [`docs/adr/0006-confidence-bound-on-the-pooled-mean.md`](docs/adr/0006-confidence-bound-on-the-pooled-mean.md)
  (2026-08-24) retired the second ship clause `mean − stdev ≥ POOLED_LOWER_BOUND
  (105)` and replaced it with `mean − CONFIDENCE_K (1.0) × stdev/√n ≥
  POOLED_TARGET (108)`, adding `CONFIDENCE_K` and the two published statistics
  `sem` and `ci_lower`. The reason is on the record: the retired clause used a
  spread statistic as a confidence bound on a mean, and was measured changing a
  verdict on a byte-identical file. **This repository and upstream now diverge
  in that one clause**; a score quoted across the two must name which rule
  produced it, and `POOLED_LOWER_BOUND` remains in the file at 105 as a retired
  constant that the gate no longer reads. Everything else stays byte-identical
  to upstream and MUST stay that way without a deliberate re-vendor or an ADR of
  the same standing: `FLOORS`, `POOLED_TARGET` (108), `MIN_ROUNDS` (4),
  `AGG_METHOD`, `RUBRIC_SHA`, `INDEPENDENT_METHODS`, `dim_means_of()`,
  `verdict_of()`, `_is_invalidated()`, `binding_block()`, and the whole of
  `pooled_stats()`/`aggregate_verdict()` apart from the clause named above.
  Upstream's `A_MINUS`/`MANDATED` skill-name
  sets and the delivery-floor check in `main()` were **dropped**: those name
  that repository's own skill roster and are not part of the
  formula — this repo's spec/plan define no equivalent "mandated area"
  concept. `main()` here is a thin, repo-local driver over the same
  `aggregate_verdict()` rule, reading `OWASP_AST10_ROOT` (was `MMAS_ROOT`
  upstream) instead.

All three files are Apache-2.0, the same license family as this repo, so no
compatibility review is required for the copy itself.

## Installed Python dependencies (not vendored)

These are imported, not copied. They are listed here because the policy above
requires review before any new dependency is introduced, and because a
dependency that nothing records is the AST02 shape this repo is about.

| Package | Used by | License | Why |
| --- | --- | --- | --- |
| `PyYAML` | `validators/usf.py`, `fixtures/`, several test modules | MIT | Manifest and fixture loading. Loaded via `SafeLoader` only — `UnsafeLoader` on a skill manifest is code execution (AST04). |
| `jsonschema` | `validators/usf.py` | MIT | Draft 2020-12 structural pass over `schemas/usf-v1.schema.json`. Imported defensively: the semantic half of the validator runs without it and raises `SchemaUnavailableError` rather than silently skipping the structural checks. |
| `cryptography` | `validators/usf.py` (optional) | Apache-2.0 OR BSD-3-Clause | ed25519 verification of a signed USF manifest. Imported lazily inside `verify_signature()`; every other code path works without it, and an unverifiable signature raises rather than returning "valid". |

All three are inside the acceptable license families above, so no compatibility
review is outstanding.

## Vendored rubric — skill-judge (MIT)

| Field | Value |
| --- | --- |
| Work | skill-judge, the 8-dimension agent-skill grading rubric (upstream path `skills/skill-judge` — not a path in this repository; the copy lives at `vendor/skill-judge/`) |
| Upstream | [softaworks/agent-toolkit](https://github.com/softaworks/agent-toolkit/tree/main/skills/skill-judge) |
| Copyright | (c) 2026 Leonardo Flores |
| License | MIT |
| Vendored at | [`vendor/skill-judge/SKILL.md`](vendor/skill-judge/SKILL.md), verbatim, unmodified |
| License text shipped | [`vendor/skill-judge/LICENSE`](vendor/skill-judge/LICENSE) — MIT, (c) 2026 Leonardo Flores |
| Provenance record | [`vendor/skill-judge/PROVENANCE.md`](vendor/skill-judge/PROVENANCE.md) |
| Upstream commit pin | `3027f20f3181758385a1bb8c022d4041dfb4de84` — `RUBRIC_SHA` in `scripts/ship_floor.py` |
| Content pin | `737ef3628f0e11353114c3bd05a1c9d0c448dbfec1ae85db839253cbe93198b6` — `RUBRIC_CONTENT_SHA256`, same file |
| Enforced by | `ship_floor.py` rejects any recorded `aggregate.rubric_sha` that differs; `tests/test_rubric_pin.py` recomputes the content hash from the vendored bytes; `scripts/judge_harness.py` refuses to build a prompt when they disagree |

The rubric is the substance behind this repo's ship gate: the per-dimension
floors `FLOORS` enumerates (`D1:17, D2:13, D3:13, D4:13, D5:13, D6:13, D7:8,
D8:13`) are that rubric's dimensions, and spec.md's contract is that skills are
"scored ... against the pinned 8-dimension skill-judge rubric."

**The rubric text does ship in this repository**, verbatim, at
`vendor/skill-judge/SKILL.md`. That makes this a redistribution, not merely a
citation, so the MIT obligation attaches in full: the license text and the
copyright notice ship beside the copy, in `vendor/skill-judge/LICENSE`, and
`vendor/skill-judge/PROVENANCE.md` records where the bytes came from. The
vendored bytes are unmodified and must stay so — an edit would break the content
pin and invalidate every recorded score at once.

**The two pins are different instruments and neither substitutes for the
other.** `RUBRIC_SHA` is the *upstream commit id*: it names which revision of
`softaworks/agent-toolkit` the rubric came from, and nothing inside this
repository can recompute it, so on its own it is a claim rather than a check.
`RUBRIC_CONTENT_SHA256` is the sha256 of the vendored bytes: it *is*
recomputable here, and `tests/test_rubric_pin.py` recomputes it on every run.
Vendoring is what closed the gap — before it, the only pin was the one that
could not be verified from inside the tree.

softaworks/agent-toolkit does not endorse and is not affiliated with this
repository. This project vendors and applies the rubric; it did not author it.

## Audit metadata

- **Audit date:** 2026-08-24 (supersedes the 2026-08-23 pass, which recorded the
  skill-judge rubric as a bare SHA pin with no tree beside it; the tree has since
  landed, so this pass re-describes what is actually redistributed. That in turn
  superseded the 2026-08-21 T-2.2 pass, which scoped only the vendored files)
- **Scope:** `scripts/ship_floor.py`, `scripts/content_hash.py`,
  `scripts/eval_counts.py` and `vendor/skill-judge/` (vendored); the
  skill-judge `RUBRIC_SHA` and `RUBRIC_CONTENT_SHA256` pins; the
  OWASP Agentic Skills Top 10 whitepaper as source material; `PyYAML`,
  `jsonschema`, `cryptography` as installed dependencies
- **This repo's license:** Apache-2.0 (root `LICENSE`, Copyright 2026 Jacky
  Chan) — present and asserted, no longer pending
- **Scan result:** PASS — every license family present (Apache-2.0 for the
  vendored pipeline and this repo; MIT for the vendored rubric and two
  dependencies; Apache-2.0 OR BSD-3-Clause for `cryptography`) sits inside the
  acceptable set above and is mutually compatible. No copyleft component is
  present, so no reciprocal obligation attaches.
- **Redistribution obligations:** two components are redistributed rather than
  merely depended on. Apache-2.0 section 4 for `scripts/ship_floor.py`,
  `content_hash.py` and `eval_counts.py` is met by the holder, license and pinned
  commit recorded above plus the root `LICENSE` and `NOTICE`. MIT is met for
  `vendor/skill-judge/SKILL.md` by `vendor/skill-judge/LICENSE` shipping the
  license text and copyright notice beside the copy.
- **Outstanding:** none. The one gap the previous pass recorded — a rubric
  identified only by a hash nobody here could check — is closed: the tree ships
  at `vendor/skill-judge/` with its license and provenance, and
  `tests/test_rubric_pin.py` verifies the bytes against `RUBRIC_CONTENT_SHA256`
  on every run.
