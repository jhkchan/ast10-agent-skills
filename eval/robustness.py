#!/usr/bin/env python3
"""eval/robustness.py — how much of the published ship count survives a perturbation.

`docs/skill-judge-dashboard.md` publishes a board. A board is a count, and a
count hides its own margin: **11 of 11** reads the same whether every skill
clears by ten points or whether three of them clear by a tenth on the strength
of one judge. This module asks the two questions that separate those cases, and
it asks them with the LIVE gate rather than with a re-implementation of it.

**1. Leave one judge out.** For each provider on the panel, drop every judgment
it cast and re-run `ship_floor.aggregate_verdict` over what is left, skill by
skill. The output is one ship count per excluded judge. A board that is 11 of 11
with all six judges and 8 of 11 without one of them is resting on that judge, and
a reader is entitled to know which one and by how much.

**2. Missing-data sensitivity.** Run 5 attempted 198 judgments and pooled 188.
The ten that never arrived were not a random sample: two of them were AST01's,
from the two judges that scored AST01 lowest. For every skill whose pooled `n`
is below its attempted `n`, this module refills the gap with the **same
provider's own observed mean on the same skill** — the least-assuming number
available, because it assumes only that a judge would have scored roughly what it
scored on its other rounds of that same file — and re-runs the gate. Where a
verdict changes, that verdict depends on judgments nobody can produce.

WHY THIS IS NOT A SECOND GATE
-----------------------------
Neither analysis re-issues anything. No scorecard is modified, no imputed value
is written into any published figure, and the verdicts in
`eval/scorecards/*.json` and in the dashboard's Results table stand exactly as
issued. What is published is the *margin* around them. Both analyses call
`ship_floor.aggregate_verdict` directly — the same function the ship gate calls —
rather than re-deriving the two clauses here, because a robustness report that
re-implements the rule is measuring its own copy of the rule. It reads no gate
constant it does not print, and it changes none.

`eval/calibration.py` prints this report alongside its panel diagnostics; that
file deliberately never touches the verdict machinery (see its docstring and
`tests/test_calibration.py::test_calibration_imports_only_the_constants_it_reports`),
which is exactly why the gate-calling half lives here instead.

Usage::

    python3 eval/robustness.py                  # print the tables, write eval/robustness.json
    python3 eval/robustness.py --json           # the same figures, machine-readable
    python3 eval/robustness.py --scorecards DIR # point at another corpus
    python3 eval/robustness.py --no-emit        # print only
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:  # allow `python3 eval/robustness.py`
    sys.path.insert(0, str(REPO_ROOT))

from scripts.refusal_ledger import attempted_of, missing_attempts  # noqa: E402
from scripts.ship_floor import (  # noqa: E402
    AGG_METHOD,
    CONFIDENCE_K,
    DIM_KEYS,
    MIN_ROUNDS,
    POOLED_TARGET,
    RUBRIC_SHA,
    aggregate_verdict,
    dim_means_of,
    pooled_stats,
)

SCORECARD_DIR = REPO_ROOT / "eval" / "scorecards"

#: Where the machine-readable robustness figures are written. Committed, so a
#: reviewer reading a diff sees a leave-one-out ship count move without running
#: anything, and `tests/test_robustness.py` fails if the file drifts from what
#: the recorded scorecards produce.
ROBUSTNESS_PATH = REPO_ROOT / "eval" / "robustness.json"


class RobustnessError(ValueError):
    """A scorecard that cannot be read as a panel of judgments."""


@dataclass(frozen=True)
class Row:
    """One judgment: who cast it, what it totalled, and its dimension scores."""

    provider: str
    total: float
    scores: dict[str, float]

    @property
    def gradeable(self) -> bool:
        """True when this judgment recorded every dimension the floors are applied to."""
        return all(key in self.scores for key in DIM_KEYS)


@dataclass(frozen=True)
class Panel:
    """One skill's recorded panel, reduced to what the gate reads.

    ``method`` and ``rubric_sha`` are carried from the scorecard rather than
    from this repo's constants so that a corpus judged against a different pin
    BLOCKS here exactly as it would at the gate, instead of being quietly
    re-labelled with today's pin.
    """

    skill: str
    method: str | None
    rubric_sha: str | None
    attempted: int
    rows: tuple[Row, ...]
    missing: tuple[tuple[str, int | None], ...]

    @property
    def pooled(self) -> int:
        return len(self.rows)

    @property
    def providers(self) -> list[str]:
        return sorted({row.provider for row in self.rows})


def load_panels(directory: Path = SCORECARD_DIR) -> list[Panel]:
    """Every scorecard in ``directory`` as a :class:`Panel`, in filename order."""
    if not directory.is_dir():
        return []
    panels: list[Panel] = []
    for path in sorted(directory.glob("*.json")):
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RobustnessError(f"{path.name}: not valid JSON: {exc}") from exc
        if not isinstance(card, dict) or "judgments" not in card:
            continue
        aggregate = card.get("aggregate") if isinstance(card.get("aggregate"), dict) else {}
        rows: list[Row] = []
        for entry in card.get("judgments") or []:
            if not isinstance(entry, dict):
                raise RobustnessError(f"{path.name}: judgment entries must be objects")
            total = entry.get("total")
            if not isinstance(total, (int, float)):
                raise RobustnessError(f"{path.name}: a judgment from {entry.get('provider')!r} has no numeric total")
            raw = entry.get("scores") or {}
            scores = {str(k): float(v) for k, v in raw.items() if isinstance(v, (int, float))}
            rows.append(Row(str(entry.get("provider") or "<unnamed>"), float(total), scores))
        panels.append(
            Panel(
                skill=str(card.get("skill") or path.stem),
                method=aggregate.get("method", AGG_METHOD),
                rubric_sha=aggregate.get("rubric_sha", RUBRIC_SHA),
                attempted=attempted_of(card),
                rows=tuple(rows),
                missing=tuple((m.provider, m.round_index) for m in missing_attempts(card)),
            )
        )
    return panels


def gate(panel: Panel, rows: Sequence[Row]) -> dict[str, Any]:
    """Run the LIVE ship gate over ``rows`` and return its verdict and statistics.

    The aggregate block handed to `aggregate_verdict` is built here rather than
    read from the scorecard, because the whole point is to ask what the gate
    says about a panel that was never recorded. Every statistic in it comes from
    `pooled_stats`, so the rule's own drift check compares the recompute against
    itself and passes; what is being varied is the set of judgments, nothing
    else.
    """
    totals = [row.total for row in rows]
    dimsets = [{key: row.scores[key] for key in DIM_KEYS} for row in rows if row.gradeable]
    aggregate: dict[str, Any] = {
        "judgments": totals,
        "method": panel.method,
        "rubric_sha": panel.rubric_sha,
        "dim_n": len(dimsets),
        "dim_means": dim_means_of(dimsets) if dimsets else {},
    }
    stats: dict[str, Any] | None = None
    if len(totals) >= MIN_ROUNDS:
        stats = pooled_stats(totals)
        aggregate.update(stats)
    verdict, why = aggregate_verdict(panel.skill, aggregate)
    out: dict[str, Any] = {
        "skill": panel.skill,
        "n": len(totals),
        "verdict": verdict,
        "reason": why,
    }
    for key in ("mean", "stdev", "sem", "ci_lower"):
        out[key] = stats[key] if stats else None
    return out


def as_measured(panels: Sequence[Panel]) -> dict[str, Any]:
    """The board exactly as published: every recorded judgment, no perturbation."""
    verdicts = [gate(panel, panel.rows) for panel in panels]
    return {
        "n_skills": len(panels),
        "n_judgments": sum(panel.pooled for panel in panels),
        "n_attempted": sum(panel.attempted for panel in panels),
        "n_judges": len({provider for panel in panels for provider in panel.providers}),
        "ships": sum(1 for row in verdicts if row["verdict"] == "SHIP"),
        "skills": verdicts,
    }


def leave_one_judge_out(panels: Sequence[Panel]) -> dict[str, Any]:
    """Recompute every skill's verdict under the live gate with one judge dropped.

    One entry per provider on the panel, sorted by how much damage the exclusion
    does — fewest ships first, so a reader scanning the table meets the judge the
    board depends on before the judges it does not.
    """
    baseline = {row["skill"]: row for row in (gate(panel, panel.rows) for panel in panels)}
    judges = sorted({provider for panel in panels for provider in panel.providers})

    entries: list[dict[str, Any]] = []
    for judge in judges:
        dropped = 0
        skills: list[dict[str, Any]] = []
        for panel in panels:
            kept = [row for row in panel.rows if row.provider != judge]
            dropped += panel.pooled - len(kept)
            result = gate(panel, kept)
            result["verdict_as_measured"] = baseline[panel.skill]["verdict"]
            result["changed"] = result["verdict"] != baseline[panel.skill]["verdict"]
            skills.append(result)
        newly_blocked = [
            {"skill": row["skill"], "ci_lower": row["ci_lower"], "mean": row["mean"], "n": row["n"]}
            for row in skills
            if row["changed"] and row["verdict"] != "SHIP"
        ]
        entries.append(
            {
                "provider": judge,
                "judgments_dropped": dropped,
                "ships": sum(1 for row in skills if row["verdict"] == "SHIP"),
                "of": len(panels),
                "newly_blocked": newly_blocked,
                "skills": skills,
            }
        )

    entries.sort(key=lambda entry: (entry["ships"], entry["provider"]))
    ship_counts = [entry["ships"] for entry in entries]
    return {
        "note": (
            "Each row drops one judge's judgments entirely and re-runs "
            "ship_floor.aggregate_verdict over what remains. Nothing is excluded from any "
            "published figure: the board stands as issued, and this is the margin around it."
        ),
        "baseline_ships": sum(1 for row in baseline.values() if row["verdict"] == "SHIP"),
        "of": len(panels),
        "worst_ships": min(ship_counts) if ship_counts else None,
        "worst_judges": sorted(e["provider"] for e in entries if ship_counts and e["ships"] == min(ship_counts)),
        "skills_broken_by_any_single_exclusion": sorted(
            {row["skill"] for entry in entries for row in entry["newly_blocked"]}
        ),
        "judges": entries,
    }


def _impute_rows(panel: Panel) -> tuple[list[Row], list[dict[str, Any]], list[str]]:
    """One replacement judgment per missing attempt, at that judge's own mean on this skill.

    Returns the imputed rows, a record of what each one assumed, and the
    attempts that could not be imputed at all — a provider with no surviving
    judgment on this skill has no own-mean to borrow, and inventing one from the
    rest of the panel would be a different and much stronger assumption.
    """
    imputed: list[Row] = []
    record: list[dict[str, Any]] = []
    unimputable: list[str] = []
    for provider, round_index in panel.missing:
        own = [row for row in panel.rows if row.provider == provider]
        if not own:
            unimputable.append(f"{provider} round {round_index if round_index else '?'}")
            continue
        total = statistics.fmean(row.total for row in own)
        gradeable = [row for row in own if row.gradeable]
        scores = {key: statistics.fmean(row.scores[key] for row in gradeable) for key in DIM_KEYS} if gradeable else {}
        imputed.append(Row(provider, total, scores))
        record.append(
            {
                "provider": provider,
                "round": round_index,
                "imputed_total": round(total, 2),
                "from_n": len(own),
            }
        )
    return imputed, record, unimputable


def missing_data_sensitivity(panels: Sequence[Panel]) -> dict[str, Any]:
    """For each skill that lost judgments, the verdict it would have had if they had not been lost.

    Only skills with a gap appear. A skill that pooled everything it attempted
    has no sensitivity to report and rendering it as "unchanged" would pad the
    table with rows that are true by construction.
    """
    skills: list[dict[str, Any]] = []
    for panel in panels:
        gap = panel.attempted - panel.pooled
        if gap <= 0:
            continue
        imputed, record, unimputable = _impute_rows(panel)
        measured = gate(panel, panel.rows)
        what_if = gate(panel, list(panel.rows) + imputed)
        skills.append(
            {
                "skill": panel.skill,
                "pooled": panel.pooled,
                "attempted": panel.attempted,
                "missing": gap,
                "imputed": record,
                "not_imputable": unimputable,
                "as_measured": measured,
                "imputed_verdict": what_if,
                "changed": what_if["verdict"] != measured["verdict"],
            }
        )
    return {
        "note": (
            "Every attempt that was made and never pooled, refilled at the SAME provider's "
            "observed mean on the SAME skill, then re-gated. Not a correction: no imputed value "
            "is written into any scorecard, dashboard or README figure, and the published "
            "verdicts stand as issued. The imputation is load-bearing and is stated so it can be "
            "argued with — imputing at the pooled mean instead would leave every mean untouched "
            "and shrink every sem, turning a gap in the record into free confidence."
        ),
        "imputation": "same provider, same skill, that provider's own observed mean",
        "skills_with_a_gap": [row["skill"] for row in skills],
        "verdicts_changed": [row["skill"] for row in skills if row["changed"]],
        "skills": skills,
    }


def robustness(panels: Sequence[Panel]) -> dict[str, Any]:
    """The whole report: the board as measured, then the two perturbations."""
    if not panels:
        raise RobustnessError("no scorecards to analyse — is eval/scorecards/ empty?")
    return {
        "gate": {
            "rule": (
                f"mean >= {POOLED_TARGET} AND mean - {CONFIDENCE_K} * stdev/sqrt(n) >= "
                f"{POOLED_TARGET} AND every dimension mean >= its floor"
            ),
            "pooled_target": POOLED_TARGET,
            "confidence_k": CONFIDENCE_K,
            "min_rounds": MIN_ROUNDS,
            "applied_by": "scripts.ship_floor.aggregate_verdict",
        },
        "as_measured": as_measured(panels),
        "leave_one_judge_out": leave_one_judge_out(panels),
        "missing_data": missing_data_sensitivity(panels),
    }


def robustness_document(data: dict[str, Any], source: Path) -> dict[str, Any]:
    """`eval/robustness.json`: the same figures, committed and diffable.

    Carries no timestamp, for the reason `eval/judge-quality.json` carries none:
    the file is regenerated from frozen scorecards, so a wall-clock field would
    make every run a diff and hide the one change that matters — a ship count
    moving.
    """
    try:
        where = str(source.resolve().relative_to(REPO_ROOT))
    except ValueError:
        where = str(source)
    return {
        "generated_by": "eval/robustness.py",
        "source": where,
        "doctrine": (
            "Declare and record. These figures are the margin around the published board, not a "
            "revision of it. No judge is excluded from any published figure and no imputed "
            "judgment is written into any scorecard; both analyses re-run the live gate over a "
            "panel that was never recorded, and say so."
        ),
        **data,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _blocked_summary(rows: Iterable[dict[str, Any]]) -> str:
    parts = [f"{row['skill']} {row['ci_lower']:.1f}" if row["ci_lower"] is not None else row["skill"] for row in rows]
    return ", ".join(parts) if parts else "—"


def format_report(data: dict[str, Any]) -> str:
    """The human-readable tables. Column widths fixed so output diffs cleanly."""
    measured = data["as_measured"]
    lojo = data["leave_one_judge_out"]
    missing = data["missing_data"]
    lines: list[str] = []

    lines.append("Robustness: what the published ship count depends on")
    lines.append(
        f"  As measured: {measured['ships']} of {measured['n_skills']} ship, "
        f"from {measured['n_judgments']} of {measured['n_attempted']} attempted judgments "
        f"cast by {measured['n_judges']} judges."
    )
    lines.append(f"  Gate applied: {data['gate']['rule']}")
    lines.append("")

    lines.append("Leave one judge out (that judge's judgments dropped, live gate re-run)")
    lines.append(f"  {'excluded judge':<32} {'dropped':>7} {'ships':>7}  newly blocked (skill ci_lower)")
    for entry in lojo["judges"]:
        lines.append(
            f"  {entry['provider']:<32} {entry['judgments_dropped']:>7} "
            f"{entry['ships']:>3}/{entry['of']:<3}  {_blocked_summary(entry['newly_blocked'])}"
        )
    lines.append("")
    if lojo["worst_ships"] is not None and lojo["worst_ships"] < lojo["baseline_ships"]:
        lines.append(
            f"  The board is {lojo['baseline_ships']} of {lojo['of']} as measured and "
            f"{lojo['worst_ships']} of {lojo['of']} without {', '.join(lojo['worst_judges'])}."
        )
    if lojo["skills_broken_by_any_single_exclusion"]:
        lines.append(
            "  Skills that at least one single-judge exclusion blocks: "
            + ", ".join(lojo["skills_broken_by_any_single_exclusion"])
        )
    lines.append("")

    lines.append("Missing-data sensitivity (attempted, never pooled, refilled at that judge's own mean)")
    if not missing["skills"]:
        lines.append("  Every skill pooled every judgment it attempted; there is no gap to be sensitive to.")
        return "\n".join(lines)
    lines.append(f"  {'skill':<12} {'pooled':>6} {'att':>4} {'mean':>14} {'ci_lower':>16} {'verdict':>22}")
    for row in missing["skills"]:
        before, after = row["as_measured"], row["imputed_verdict"]
        mean_cell = f"{before['mean']:.1f} -> {after['mean']:.1f}"
        ci_cell = f"{before['ci_lower']:.1f} -> {after['ci_lower']:.1f}"
        verdict_cell = f"{before['verdict']} -> {after['verdict']}"
        flag = "  <<<" if row["changed"] else ""
        lines.append(
            f"  {row['skill']:<12} {row['pooled']:>6} {row['attempted']:>4} "
            f"{mean_cell:>14} {ci_cell:>16} {verdict_cell:>22}{flag}"
        )
    lines.append("")
    if missing["verdicts_changed"]:
        lines.append(
            "  Verdict(s) that do NOT survive imputation of their own missing judgments: "
            + ", ".join(missing["verdicts_changed"])
        )
    else:
        lines.append("  No verdict changes under this imputation.")
    lines.append(f"  {missing['note']}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eval/robustness.py",
        description="Leave-one-judge-out and missing-data sensitivity over eval/scorecards/*.json.",
    )
    parser.add_argument("--scorecards", default=str(SCORECARD_DIR), help="scorecard directory to read")
    parser.add_argument("--json", action="store_true", help="emit the figures as JSON instead of tables")
    parser.add_argument("--out", default=None, help=f"where to write the figures (default: {ROBUSTNESS_PATH.name})")
    parser.add_argument("--no-emit", action="store_true", help="print only; do not write the robustness file")
    args = parser.parse_args(argv)

    source = Path(args.scorecards)
    panels = load_panels(source)
    if not panels:
        print(f"{args.scorecards}: no scorecards recorded — nothing to perturb")
        return 0

    data = robustness(panels)
    print(json.dumps(data, indent=2) if args.json else format_report(data))

    # Written by default, but only for the corpus the committed file is *about*.
    # A `--scorecards some/other/dir` run must never overwrite the recorded
    # panel's figures with a foreign corpus's; an explicit --out asks for that
    # on purpose. Same rule, and the same reason, as eval/judge-quality.json.
    destination = Path(args.out) if args.out else ROBUSTNESS_PATH
    if not args.no_emit and (args.out or source.resolve() == SCORECARD_DIR.resolve()):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(robustness_document(data, source), indent=2) + "\n", encoding="utf-8")
        if not args.json:
            print(f"\n  Robustness figures written to {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
