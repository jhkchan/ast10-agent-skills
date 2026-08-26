# Development

Repository layout, how to run the harnesses, and what each kind of evidence in this repo
actually answers.

# Repository layout

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
scripts/                   pooled scoring rule, content hashing, judge harness, dogfood,
                           manifest signing (sign_usf.py — see docs/signing.md)
eval/                      scorecards + the dashboard generator
cli/ast10.py               list / status / route / install  (Python)
cli/bin/cli.js             list / route / audit / coverage / status  (Node, no deps)
cli/lib/bridge.py          the one implementation `route` and `audit` both call
commands/ast/              14 slash commands wrapping the workflows above
.claude-plugin/            marketplace.json — the eleven-skill index
docs/                      architecture, the judge dashboard, ADRs, glossary, signing.md
ruff.toml                  the lint + format contract CI runs unflagged
```

Read [`docs/architecture.md`](architecture.md) for how those pieces bind to each
other, and [`docs/adr/0004-per-scenario-detectability-contract.md`](adr/0004-per-scenario-detectability-contract.md)
for the tiering contract every coverage matrix is written against.

# Development

```bash
python3 -m pytest -q                            # the full suite
python3 validators/usf.py skills/*/skill.usf.yaml   # every shipped manifest
python3 scripts/sign_usf.py verify              # every signature; needs no key, and is
                                                # exactly what CI runs (docs/signing.md)
python3 validators/tier_lock.py fixtures/manifest.yaml   # tier-drift check
python3 scripts/dogfood.py                      # our detectors over our own skills
python3 scripts/ship_floor.py                   # recompute every stored judge verdict in
                                                # eval/scorecards/ (and scores.json if present);
                                                # exits 1 if it finds neither
python3 eval/generate_f1_report.py              # re-measure every corpus, rewrite the F1 report
python3 eval/generate_dashboard.py              # rewrite the dashboard results table
python3 scripts/generate_badges.py              # rewrite the README badge row from its sources
python3 eval/calibration.py                     # judge bias, judge quality, and the robustness block
python3 eval/robustness.py                      # leave-one-judge-out + missing-data sensitivity alone
python3 scripts/refusal_ledger.py               # every discarded judgment must be on the record
ruff check . && ruff format --check .           # exactly what CI runs; see ruff.toml
```

Some of those write documents that are committed alongside the code, and each is
regenerated-and-compared by the test suite rather than trusted:

- [`docs/f1-report.md`](f1-report.md) — every category's measured precision,
  recall and F1, with each individual case verdict recorded in
  [`eval/f1-report.json`](../eval/f1-report.json) so any figure can be re-derived by
  hand. Written by `python3 eval/generate_f1_report.py`.
- [`docs/dogfood-report.md`](dogfood-report.md) — every firing of every
  detector over this repository's own eleven skill packages, waived or not, with
  the reason for each waiver. Written by
  `python3 scripts/dogfood.py --markdown --out docs/dogfood-report.md`.
- [`docs/skill-eval-report.md`](skill-eval-report.md) — the **with/without**
  eval delta. Written by `python3 eval/generate_skill_eval_report.py` from the
  committed runs under `eval/skill-eval-workspace/`.
- [`docs/external-validation.md`](external-validation.md) — the detectors
  run over **360 skill packages this repository did not write**, with per-check
  firing counts before and after the two fixes that run produced. The machine-
  readable record is [`eval/external-validation.json`](../eval/external-validation.json);
  written by `python3 scripts/external_validation.py`. It is a false-positive
  study and establishes nothing about recall — the corpora contain no labelled
  malicious skill, and the report says so in those words.
- **The badge row under this page's own H1** — every figure in it is derived from
  the artifact that produced it, never typed. Written by
  `python3 scripts/generate_badges.py`, which rewrites only the block between its
  two marker comments. It is guarded twice, on purpose:
  [`tests/test_badges.py`](../tests/test_badges.py) never imports the generator and
  re-derives every figure straight from `eval/scorecards/`, `eval/f1-report.json`,
  the iteration-3 control runs, the USF manifests and `scenarios/registry.yaml`,
  so a wrong literal *inside* the generator still fails; `tests/test_generate_badges.py`
  unit-tests the generator itself, including the caveat states no clean run reaches.

## Three kinds of evidence, and what each one answers

They use three different units and are never averaged with one another:

| Surface | The question it answers |
| --- | --- |
| [Judge scores](skill-judge-dashboard.md) | Is the **text** of a `SKILL.md` well written against the pinned eight-dimension rubric? No prompt is ever executed. Unit: a total out of 120. |
| [Detector F1](f1-report.md) | Do the shipped Python check scripts separate this repository's own labelled vulnerable and clean fixtures? Real output measurement — of the scripts, not of an agent. Unit: precision/recall/F1 per category. |
| [With/without evals](skill-eval-report.md) | Does an agent **holding** a skill behave better than the same agent holding nothing? Unit: the fraction of a case's hand-authored assertions a graded response satisfied, and the **delta** between the two arms. |

Only the third one has ever measured an agent's output. Every case in
`skills/*/evals/evals.json` runs twice — once with the skill installed, once
without it and nothing else changed — and the delta is the deliverable. The agent
under test and the grader are always different models, and both are recorded in
every artifact. Nothing on that surface feeds the ship gate.

All three are measured over material this repository authored. The one
measurement that is not is [`docs/external-validation.md`](external-validation.md),
and it is a **fourth unit again** — how often the detectors fire on benign work
nobody wrote for them. It is never averaged with the three above, it feeds no
gate, and because every package in its corpora is presumed benign it says nothing
whatever about whether these detectors would catch a real attack.

```bash
python3 eval/skill_evals.py --dry-run            # the plan; writes nothing, calls nothing
python3 eval/skill_evals.py                      # run every case in both arms, grade, aggregate
python3 eval/skill_eval_grade.py review          # which assertions the skill actually moved
python3 eval/generate_skill_eval_report.py       # publish docs/skill-eval-report.md
python3 eval/skill_evals.py --case-file control.json   # the blind control set
python3 eval/skill_evals.py --case-file regression.json  # the spent corpus, kept for regressions
```

There are three authored corpora and they answer three different questions.
`skills/*/evals/evals.json` is the **tuned** set — the cases an iteration reads and
edits a `SKILL.md` against — and a delta on it says the skill improved on cases
somebody was looking at while improving it. `skills/*/evals/control.json` is the
**blind control**: one case per skill, eleven in total, authored from each skill's
own files and the whitepaper rather than from any measured result, and a delta on
*it* is the only thing here that says the improvement generalised.
`skills/*/evals/regression.json` is a **regression suite and not a control** — it
held the control role under the name `heldout.json` until iteration 3 tuned an
advisory fix against one of its cases and published per-skill deltas from it, which
spends a control. The cases were kept because one a skill used to pass and now
fails is still a regression worth catching; no number from that file is evidence
that anything generalised.

The three are never pooled, and every non-default run writes under its own
`<skill>-<corpus>-case-<n>` slugs so a workspace names the corpus that produced it.
Each non-tuned file carries its own notice: the control's says that reading it
while editing a skill spends the only thing it is worth, that the iteration which
spends it owes the next one a replacement set, and what that costs — this is the
third corpus, an eval programme that burns a control per iteration is not
sustainable, and a future iteration should rotate the two or three skills whose
results actually steered an edit rather than re-authoring all eleven.

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

---

[< Back to the README](../README.md)
