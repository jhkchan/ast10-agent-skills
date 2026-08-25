#!/usr/bin/env python3
"""eval/generate_skill_eval_report.py — publish the with/without eval delta.

THE THIRD REPORT SURFACE, AND WHY IT IS ITS OWN PAGE
====================================================

This repository publishes three kinds of evidence. They answer three different
questions, they are measured in three different units, and none of them is an
average of the others:

* **Judge scores** — is the TEXT of a `SKILL.md` well written against the
  vendored eight-dimension rubric? No prompt is ever executed. Unit: a total out
  of 120. (`eval/scorecards*/`, `docs/skill-judge-dashboard.md`.)
* **Detector F1** — do the shipped Python check scripts separate this
  repository's own labelled vulnerable/clean fixtures? Real output measurement,
  of the scripts rather than of an agent. Unit: precision/recall/F1 per
  category. (`fixtures/`, `docs/f1-report.md`.)
* **With/without evals** — does an agent HOLDING a skill behave better than the
  same agent holding nothing? Unit: the fraction of a case's hand-authored
  assertions a graded response satisfied, and the delta between the two arms.
  (`eval/skill-eval-workspace/`, and this page.)

The third one is the only one that has ever measured an agent's output. It gets
its own page for exactly that reason: a `pass_rate` printed beside an F1 or a
judge total would be read as commensurable with them, and it is not. Nothing
this script writes feeds `scripts/ship_floor.py`; no gate constant is read,
imported or moved anywhere below.

WHAT IT READS AND WHAT IT REFUSES TO INVENT
===========================================

Input is the committed workspace: every `eval/skill-eval-workspace/iteration-N/`
that carries a `benchmark.json`. Two modules write that file — `eval/skill_evals.py`
(inline grading, the one-command path) and `eval/skill_eval_grade.py` (the blind
second-pass grader) — under slightly different envelopes around an identical
`run_summary`. This reader accepts both and records which module produced each
iteration, because "who graded it" is part of the result.

It publishes coverage as loudly as it publishes the delta. An iteration that ran
two of the corpus's cases is reported as two of the corpus's cases; there is no
arrangement of these numbers under which a partial run reads as a full one.

Usage::

    python3 eval/generate_skill_eval_report.py            # write docs/skill-eval-report.md
    python3 eval/generate_skill_eval_report.py --check    # exit 1 if it is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:  # allow `python3 eval/generate_skill_eval_report.py`
    sys.path.insert(0, str(REPO_ROOT))

WORKSPACE = REPO_ROOT / "eval" / "skill-eval-workspace"
SKILLS_DIR = REPO_ROOT / "skills"
MARKDOWN_OUT = REPO_ROOT / "docs" / "skill-eval-report.md"

#: The two arms, in the order every artifact writes them.
CONFIGURATIONS = ("with_skill", "without_skill")

#: One sentence per surface, so a reader who lands here first cannot mistake this
#: page's unit for either of the other two.
SURFACE_INDEX: tuple[tuple[str, str, str], ...] = (
    (
        "Judge scores",
        "Is the *text* of a `SKILL.md` well written against the vendored eight-dimension "
        "rubric? No prompt is ever executed. Unit: a total out of 120.",
        "[`skill-judge-dashboard.md`](skill-judge-dashboard.md)",
    ),
    (
        "Detector F1",
        "Do the shipped Python check scripts separate this repository's own labelled "
        "vulnerable and clean fixtures? Real output measurement — of the scripts, not of "
        "an agent. Unit: precision/recall/F1 per category.",
        "[`f1-report.md`](f1-report.md)",
    ),
    (
        "With/without evals",
        "Does an agent *holding* a skill behave better than the same agent holding "
        "nothing? Unit: the fraction of a case's hand-authored assertions a graded "
        "response satisfied, and the **delta** between the two arms.",
        "**this page**",
    ),
)


def authored_case_count(skills_dir: Path = SKILLS_DIR) -> tuple[int, int]:
    """`(cases, assertions)` across every `skills/*/evals/evals.json` on disk."""
    cases = 0
    assertions = 0
    for path in sorted(skills_dir.glob("*/evals/evals.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for case in payload.get("evals", []):
            cases += 1
            assertions += len(case.get("assertions", []))
    return cases, assertions


def discover_iterations(workspace: Path = WORKSPACE) -> list[tuple[int, dict[str, Any]]]:
    """`(N, benchmark payload)` for every iteration that has been aggregated.

    Sorted by N. An iteration directory with runs but no `benchmark.json` is not
    yet a result and is skipped rather than half-reported.
    """
    found: list[tuple[int, dict[str, Any]]] = []
    if not workspace.is_dir():
        return found
    for directory in sorted(workspace.iterdir()):
        if not directory.is_dir() or not directory.name.startswith("iteration-"):
            continue
        suffix = directory.name.removeprefix("iteration-")
        if not suffix.isdigit():
            continue
        benchmark = directory / "benchmark.json"
        if not benchmark.is_file():
            continue
        found.append((int(suffix), json.loads(benchmark.read_text(encoding="utf-8"))))
    return sorted(found, key=lambda pair: pair[0])


def _models(payload: dict[str, Any]) -> tuple[str, str]:
    """`(agent, grader)` from either writer's envelope.

    `eval/skill_evals.py` writes `models: {agent, grader}`; `eval/skill_eval_grade.py`
    writes `agent_models: [...]` and `grader_models: [...]`. Both are read rather
    than one being normalised away, because a report that quietly dropped the
    grader identity would be the exact omission this surface exists to prevent.
    """
    models = payload.get("models")
    if isinstance(models, dict):
        return str(models.get("agent", "unrecorded")), str(models.get("grader", "unrecorded"))
    agents = payload.get("agent_models") or []
    graders = payload.get("grader_models") or []
    return (", ".join(agents) or "unrecorded", ", ".join(graders) or "unrecorded")


def _paired_count(payload: dict[str, Any]) -> int:
    counts = payload.get("counts", {})
    for key in ("cases_paired", "evals_paired"):
        if key in counts:
            return int(counts[key])
    return 0


def _case_rows(payload: dict[str, Any]) -> list[tuple[str, float | None, float | None, float | None]]:
    """Per-case `(slug, with, without, delta)` from either writer's envelope."""
    rows: list[tuple[str, float | None, float | None, float | None]] = []
    for case in payload.get("cases", []):
        rows.append(
            (
                str(case.get("eval")),
                case.get("with_skill", {}).get("pass_rate"),
                case.get("without_skill", {}).get("pass_rate"),
                case.get("pass_rate_delta"),
            )
        )
    for case in payload.get("per_eval", []):
        rows.append(
            (
                str(case.get("eval_slug")),
                case.get("with_skill"),
                case.get("without_skill"),
                case.get("delta_pass_rate"),
            )
        )
    return sorted(rows, key=lambda row: row[0])


def _num(value: Any, digits: int = 2) -> str:
    """A number for a table cell, or an em dash. Never a zero standing in for
    an absent measurement."""
    if value is None:
        return "—"
    if isinstance(value, bool):  # pragma: no cover - defensive; no bool metric exists
        return str(value)
    return f"{float(value):.{digits}f}"


def _signed(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{float(value):+.{digits}f}"


def render(iterations: list[tuple[int, dict[str, Any]]], authored: tuple[int, int]) -> str:
    cases, assertions = authored
    lines: list[str] = []
    add = lines.append

    add("# With/without skill evals")
    add("")
    add(
        "Generated by `eval/generate_skill_eval_report.py` from the committed workspace under "
        "`eval/skill-eval-workspace/`. Do not hand-edit: run the generator."
    )
    add("")
    add(
        "**This is the only surface in this repository that measures an agent's output.** Every "
        "case here runs twice — once by an agent handed the skill's `SKILL.md` as its operating "
        "instructions, once by the same agent handed nothing else different — and the delta "
        "between the two pass rates is the deliverable. A skill that grades well on the rubric "
        "and does not beat its own absence here has not been shown to work."
    )
    add("")
    add(
        "This repository is an independent community implementation. It is **not** an official "
        "OWASP project and carries no OWASP endorsement — see [`../README.md`](../README.md) and "
        "[`../NOTICE`](../NOTICE)."
    )
    add("")

    add("## Three kinds of evidence, three different questions")
    add("")
    add("| Surface | The question it answers | Where |")
    add("| --- | --- | --- |")
    for name, question, where in SURFACE_INDEX:
        add(f"| **{name}** | {question} | {where} |")
    add("")
    add(
        "The three are never averaged and never plotted together. A `pass_rate` on this page is "
        "not a detector F1 and not a judge rubric total, and nothing on this page feeds the ship "
        "gate in `scripts/ship_floor.py`."
    )
    add("")

    add("## The authored corpus")
    add("")
    add(
        f"`skills/*/evals/evals.json` currently holds **{cases} cases** carrying "
        f"**{assertions} assertions**, hand-authored in the field names the "
        "[agentskills.io evaluating-skills guidance](https://agentskills.io/skill-creation/evaluating-skills) "
        "fixes. A full iteration is therefore "
        f"{cases} × 2 = {cases * 2} agent runs. `tests/test_eval_cases.py` gates the shape of "
        "every case; `python3 eval/skill_evals.py --dry-run` prints the plan without calling a model."
    )
    add("")

    if not iterations:
        add("## Results")
        add("")
        add(
            "**No iteration has been aggregated yet.** The workspace holds no `benchmark.json`, so "
            "this page publishes no delta. It will not publish one until a run does."
        )
        add("")
        return "\n".join(lines) + "\n"

    add("## Results by iteration")
    add("")
    add(
        "`coverage` is the number of cases that produced a graded run in **both** arms, against the "
        "authored corpus. A delta computed over two different case sets is not a delta, so an "
        "iteration that covered part of the corpus says so here rather than in a footnote."
    )
    add("")
    add("| Iteration | Coverage | Agent under test | Grader | with_skill | without_skill | Δ pass_rate |")
    add("| --- | --- | --- | --- | --- | --- | --- |")
    for number, payload in iterations:
        agent, grader = _models(payload)
        summary = payload.get("run_summary", {})
        with_mean = summary.get("with_skill", {}).get("pass_rate", {}).get("mean")
        without_mean = summary.get("without_skill", {}).get("pass_rate", {}).get("mean")
        delta = summary.get("delta", {}).get("pass_rate")
        add(
            f"| iteration-{number} | {_paired_count(payload)} of {cases} | `{agent}` | `{grader}` | "
            f"{_num(with_mean)} | {_num(without_mean)} | {_signed(delta)} |"
        )
    add("")
    add(
        "The agent under test and the grader are always different models, enforced rather than "
        "encouraged: `eval/skill_evals.py` exits rather than let one model grade its own output, "
        "and both names are written into every `timing.json`, every `grading.json` and every "
        "`benchmark.json`."
    )
    add("")

    add("## Every case that ran")
    add("")
    add("| Iteration | Eval | with_skill | without_skill | Δ | Graded by |")
    add("| --- | --- | --- | --- | --- | --- |")
    for number, payload in iterations:
        generator = payload.get("generated_by", "unrecorded")
        for slug, with_rate, without_rate, delta in _case_rows(payload):
            add(
                f"| iteration-{number} | `{slug}` | {_num(with_rate)} | {_num(without_rate)} | "
                f"{_signed(delta)} | `{generator}` |"
            )
    add("")

    add("## What these numbers do not say")
    add("")
    add(
        "- **One agent model is one point of evidence, not a population.** A delta measured on one "
        "model is a fact about that model holding these skills."
    )
    add(
        "- **A case that scores the same in both arms is a result, not a bug.** It says the "
        "assertion set did not discriminate — see the `passed_in_both` bucket in "
        "`assertion-review.json`, written by `python3 eval/skill_eval_grade.py review`."
    )
    add(
        "- **A `-heldout-` row is a spent control, and its delta is not evidence of "
        "generalisation.** Those rows were produced by the corpus then called `heldout.json`, "
        "which answered *did this edit generalise* until iteration 3 tuned an advisory fix "
        "against one of its cases and published per-skill deltas from all eleven. It has been "
        "retired to `skills/*/evals/regression.json`, a regression suite and not a control; "
        "the control that answers that question now is `skills/*/evals/control.json`, whose "
        "rows carry a `-control-` slug. The run directories keep the name they were written "
        "under, because the workspace is frozen evidence."
    )
    add(
        "- **Some assertions are answerable from the attached fixture files alone.** The labelled "
        "fixture packages carry their own provenance header, so both arms can read a scenario id "
        "off the input. Which assertions those are is measured and frozen by "
        "`tests/test_eval_cases.py::test_the_assertions_answerable_from_the_attached_files_are_the_recorded_ones` "
        "rather than left to memory."
    )
    add(
        "- **Grading is blind, and the claim is narrow.** The grader is never told which arm "
        "produced a response, and `eval/skill_eval_grade.py` additionally hides the run behind an "
        "opaque token and scrubs arm markers out of the text. What no prompt can remove is that an "
        "agent holding a skill writes like one."
    )
    add("")
    add(
        "Every figure above is regenerable: `python3 eval/skill_evals.py --iteration N "
        "--benchmark-only` rebuilds an iteration's `benchmark.json` from the run directories "
        "without calling a model, and `python3 eval/generate_skill_eval_report.py --check` fails "
        "if this page has drifted from them."
    )
    add("")
    return "\n".join(lines) + "\n"


def build() -> str:
    return render(discover_iterations(), authored_case_count())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish docs/skill-eval-report.md from the committed with/without eval workspace."
    )
    parser.add_argument("--check", action="store_true", help="exit 1 if the page is stale; write nothing")
    parser.add_argument("--markdown-out", default=str(MARKDOWN_OUT))
    args = parser.parse_args(argv)

    out = Path(args.markdown_out)
    rendered = build()

    if args.check:
        current = out.read_text(encoding="utf-8") if out.is_file() else ""
        if current != rendered:
            print(f"{out}: stale — run `python3 eval/generate_skill_eval_report.py`", file=sys.stderr)
            return 1
        print(f"{out}: up to date")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(rendered, encoding="utf-8")
    print(f"{out}: written")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
