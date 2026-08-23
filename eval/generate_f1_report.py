#!/usr/bin/env python3
"""eval/generate_f1_report.py — measure every category's corpus and publish the result.

Runs each category's shipped detector over that category's own labeled
vulnerable/clean fixtures and writes two artifacts:

* ``eval/f1-report.json`` — the machine-readable record, per category and per
  labeled check, including each case's individual verdict so any published
  number can be re-derived by hand from the rows above it.
* ``docs/f1-report.md`` — the same measurement for a reader.

Four rules govern what may appear in them, and all four are the repository's,
not this script's:

**1. Per category, never averaged.** `detectors/f1_reporter.py` decides each
category's verdict from that category alone and returns a plain list of rows
carrying no suite-wide field. One category failing its 0.80 floor never moves
another category's number, and no line in either artifact reports a mean across
categories.

**2. An empty static-detectable tier publishes no F1.** `scenarios/registry.yaml`
is authoritative on tier. Where it tiers none of a category's scenarios
static-detectable, that category is recorded ``declared-and-uncovered`` with a
null F1 — never a zero, never a number borrowed from a proxy corpus, and never
padded up to a corpus that would produce one.

**3. Proxy coverage is reported apart from scenario coverage.** A labeled check
declaring ``covers: artifact-signal-only`` measures an enabling signal the
registry records beside an out-of-artifact or agent-judgable scenario; it is
never coverage of that scenario. Its cases are scored, but into their own
`artifact_signal_only` block. The gate verdict is computed from the
scenario-level block alone, which is why AST05 — three labeled checks, six
cases, every one of them a proxy — publishes a proxy F1 and a gate status of
``declared-and-uncovered`` at the same time. Both statements are true and the
report makes both.

**4. Nothing here is a generalisation claim.** Each number is measured over
fixtures written by this repository's own authors, at the corpus sizes
`fixtures/manifest.yaml`'s formula demands (``max(6, 2 x detectable)``,
class-balanced). That makes a low score meaningful and a perfect score nearly
meaningless: it says the rule separates the corpus it was built against. The
markdown says so on its face rather than in a footnote.

Usage::

    python3 eval/generate_f1_report.py            # write both artifacts
    python3 eval/generate_f1_report.py --check    # exit 1 if either is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:  # allow `python3 eval/generate_f1_report.py`
    sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from detectors.engine import CategoryResult  # noqa: E402
from detectors.f1_reporter import F1_THRESHOLD, report_category  # noqa: E402
from detectors.fixture_loader import (  # noqa: E402
    CheckResult,
    load_category_cases,
    load_detector,
    load_manifest,
    run_corpus,
)
from validators.tier_lock import check_manifest_tier_locks  # noqa: E402

REGISTRY_PATH = REPO_ROOT / "scenarios" / "registry.yaml"
JSON_OUT = REPO_ROOT / "eval" / "f1-report.json"
MARKDOWN_OUT = REPO_ROOT / "docs" / "f1-report.md"

CATEGORIES: tuple[str, ...] = tuple(f"AST{n:02d}" for n in range(1, 11))

SCENARIO_LEVEL = "full"
PROXY = "artifact-signal-only"


class F1ReportError(RuntimeError):
    """The report cannot be produced from the corpus as declared."""


# --------------------------------------------------------------------------- measure


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _confusion(checks: list[CheckResult]) -> dict[str, Any] | None:
    """Aggregate a set of same-scope checks into one precision/recall/F1 block.

    ``None`` when the set is empty — an absent measurement, which is a
    different fact from a measurement of zero and must not render as one.
    """
    if not checks:
        return None
    tp = sum(c.true_positives for c in checks)
    fp = sum(c.false_positives for c in checks)
    fn = sum(c.false_negatives for c in checks)
    tn = sum(c.true_negatives for c in checks)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "checks": [c.corpus_check for c in checks],
        "cases": sum(len(c.case_verdicts) for c in checks),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def registry_tiers() -> dict[str, dict[str, list[str]]]:
    """Per-category scenario ids by tier, from the file authoritative on tier."""
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    by_category: dict[str, dict[str, list[str]]] = {
        c: {"static-detectable": [], "agent-judgable": [], "out-of-artifact": []} for c in CATEGORIES
    }
    for scenario in registry.get("scenarios") or []:
        by_category.setdefault(
            scenario["category"],
            {"static-detectable": [], "agent-judgable": [], "out-of-artifact": []},
        )[scenario["tier"]].append(scenario["id"])
    return by_category


def clean_case_leakage(category: str, manifest: dict) -> dict[str, Any]:
    """Every check in a category's module that fires on any of its clean cases.

    The per-check confusion matrix only asks whether the check a case was
    labeled against fired on it. This asks the stricter question the corpus
    docstring already states as the rule -- "a clean case expects nothing to
    fire *at all*" -- across the whole module, so a check that convicts a
    package written to be clean for a sibling scenario is counted as the false
    positive it is, instead of hiding outside its own pair.
    """
    module = load_detector(category)
    clean = [c for c in load_category_cases(category, manifest) if not c.is_vulnerable]
    firings = [
        {"case": case.case_id, "check": finding.scenario, "evidence": finding.evidence}
        for case in clean
        for finding in module.run_all(case.pkg)
        if finding.detected
    ]
    return {"clean_cases": len(clean), "firings": firings}


def _class_balance(cases: list[dict]) -> dict[str, int]:
    vulnerable = sum(1 for c in cases if c["label"] == "vulnerable")
    return {"vulnerable": vulnerable, "clean": len(cases) - vulnerable}


def measure_category(category: str, manifest: dict, tiers: dict[str, dict[str, list[str]]]) -> dict[str, Any]:
    """One category's full row: what the registry declares, what the corpus measured."""
    entry = (manifest.get("categories") or {}).get(category) or {}
    declared = entry.get("detectable_scenarios") or []
    cases = entry.get("cases") or []
    tier = tiers.get(category, {"static-detectable": [], "agent-judgable": [], "out-of-artifact": []})

    check_rows: list[dict[str, Any]] = []
    scenario_block: dict[str, Any] | None = None
    proxy_block: dict[str, Any] | None = None
    leakage: dict[str, Any] = {"clean_cases": 0, "firings": []}

    if declared:
        leakage = clean_case_leakage(category, manifest)
        result = run_corpus(category, manifest)
        if result.cases() != len(cases):
            raise F1ReportError(
                f"{category}: the manifest declares {len(cases)} case(s) but the run "
                f"scored {result.cases()}; a published number would rest on a "
                f"denominator the corpus does not have"
            )
        for check in result.checks:
            check_rows.append(
                {
                    "corpus_check": check.corpus_check,
                    "detector_check": check.detector_check,
                    "covers": check.covers,
                    "registry_ids": list(check.registry_ids),
                    "true_positives": check.true_positives,
                    "false_positives": check.false_positives,
                    "false_negatives": check.false_negatives,
                    "true_negatives": check.true_negatives,
                    "precision": round(check.precision, 4),
                    "recall": round(check.recall, 4),
                    "f1": round(check.f1, 4),
                    "discriminates": check.discriminates,
                    "case_verdicts": [
                        {"case": case_id, "predicted_vulnerable": predicted, "labeled_vulnerable": labeled}
                        for case_id, predicted, labeled in check.case_verdicts
                    ],
                }
            )
        scenario_block = _confusion([c for c in result.checks if c.covers == SCENARIO_LEVEL])
        proxy_block = _confusion([c for c in result.checks if c.covers == PROXY])
        other = sorted({c.covers for c in result.checks} - {SCENARIO_LEVEL, PROXY})
        if other:
            raise F1ReportError(f"{category}: unknown coverage scope(s) {other}; the report has no column for them")

    # The gate verdict is decided from the scenario-level measurement alone,
    # by the module that owns the 0.80 floor. A category with only proxy
    # coverage has no scenario-level F1 and is therefore declared-and-uncovered
    # -- publishing its proxy number as the gate figure is the overclaim
    # `scenarios/registry.yaml`'s signal-symmetry rule forbids.
    verdict_input = CategoryResult(
        category=category,
        true_positives=(scenario_block or {}).get("true_positives", 0),
        false_positives=(scenario_block or {}).get("false_positives", 0),
        false_negatives=(scenario_block or {}).get("false_negatives", 0),
        true_negatives=(scenario_block or {}).get("true_negatives", 0),
        precision=(scenario_block or {}).get("precision"),
        recall=(scenario_block or {}).get("recall"),
        f1=(scenario_block or {}).get("f1"),
        scored_case_ids=(),
        declared_uncovered=tuple(tier["out-of-artifact"]),
        agent_judgable=tuple(tier["agent-judgable"]),
    )
    row = report_category(verdict_input)

    detectable_checks = len(declared)
    formula_minimum = max(int(manifest.get("min_floor", 6)), 2 * detectable_checks) if detectable_checks else 0

    return {
        "category": category,
        "name": entry.get("name", ""),
        "status": row.status,
        "threshold": row.threshold,
        "f1_scope": entry.get("f1_scope", "none"),
        "corpus_status": entry.get("status", ""),
        "registry": {
            "scenarios": len(tier["static-detectable"]) + len(tier["agent-judgable"]) + len(tier["out-of-artifact"]),
            "static_detectable": sorted(tier["static-detectable"]),
            "agent_judgable": sorted(tier["agent-judgable"]),
            "out_of_artifact": sorted(tier["out-of-artifact"]),
        },
        "corpus": {
            "labeled_detectable_checks": detectable_checks,
            "cases": len(cases),
            "formula_minimum": formula_minimum,
            "meets_formula": len(cases) >= formula_minimum,
            "class_balance": _class_balance(cases),
        },
        "scenario_level": scenario_block,
        "artifact_signal_only": proxy_block,
        "any_check_firing_on_a_clean_case": leakage,
        "checks": check_rows,
        "note": (entry.get("registry_coverage") or {}).get("note", ""),
    }


def build_report() -> dict[str, Any]:
    """Measure every category. Raises before publishing anything if a tier lock broke."""
    manifest = load_manifest()
    violations = check_manifest_tier_locks(manifest)
    if violations:
        raise F1ReportError(
            "refusing to publish an F1 report against a corpus whose tier lock no "
            f"longer recomputes (S-011): {violations}"
        )
    tiers = registry_tiers()
    return {
        "generated_by": "eval/generate_f1_report.py",
        "threshold": F1_THRESHOLD,
        "rules": [
            "Each category is scored and gated on its own; no suite-wide average is computed.",
            "scenarios/registry.yaml is authoritative on tier; an empty static-detectable "
            "tier publishes no F1 and is recorded declared-and-uncovered.",
            "A check declaring covers: artifact-signal-only is scored into its own block "
            "and is never counted as coverage of the scenario it sits beside.",
            "Every number is measured over this repository's own hand-authored fixtures "
            "and is not a generalisation claim.",
        ],
        "corpus_formula": manifest.get("formula", ""),
        "categories": [measure_category(c, manifest, tiers) for c in CATEGORIES],
    }


# ---------------------------------------------------------------------------- render


def _pct(block: dict[str, Any] | None, key: str) -> str:
    if block is None:
        return "—"
    return f"{block[key]:.3f}"


def _f1_cell(row: dict[str, Any]) -> str:
    block = row["scenario_level"]
    if block is None:
        return "— *(no scenario-level corpus)*"
    flag = "" if block["f1"] >= F1_THRESHOLD else " ⚠"
    return f"**{block['f1']:.3f}**{flag}"


STATUS_LABEL = {
    "pass": "PASS",
    "fail": "FAIL",
    "declared-and-uncovered": "declared-and-uncovered",
}

PREAMBLE = """# Per-category detector F1

Generated by `eval/generate_f1_report.py`. Do not hand-edit: run the generator.
The machine-readable record, including every individual case verdict, is
`eval/f1-report.json`.

Every figure below was produced by running a category's shipped detector over
that category's own labeled fixtures under `fixtures/`. Nothing is estimated and
nothing is averaged across categories — `detectors/f1_reporter.py` decides each
category's verdict from that category alone, so a failing number stands next to
a passing one without either moving the other.

## How to read a row

<!-- COLUMN-GUIDE -->

A category can hold a proxy F1 and a gate status of `declared-and-uncovered` at
the same time — AST05 does. Both are true: three checks separate their six
labeled packages, and none of AST05's six named scenarios is decidable from one
package, so nothing there is scenario coverage.

## What these numbers are not

They are measured over fixtures written by this repository's own authors, at the
corpus sizes the formula demands — six to sixteen packages per category. That
makes a **low** score informative and a **perfect** score nearly uninformative:
it says a rule separates the corpus it was built against, not that it survives an
adversary who can read the rule. No bypass rate under white-box access is
claimed anywhere in this repository, and AST08's own mitigations ask for one.
"""


#: The Results table's column glossary. Held as data rather than as literal
#: markdown so no source line has to exceed the repository's 120-column rule to
#: describe a column properly.
COLUMN_GUIDE: tuple[tuple[str, str], ...] = (
    (
        "Registry static-detectable",
        "How many of the category's whitepaper scenarios `scenarios/registry.yaml` — the file "
        "authoritative on tier — rules decidable from one package's own bytes. Zero here means no "
        "F1 is publishable for the category at any corpus size.",
    ),
    (
        "Cases (floor)",
        "Labeled vulnerable/clean fixtures actually scored, against the `max(6, 2 × detectable)` "
        "floor `fixtures/manifest.yaml` sets.",
    ),
    (
        "Precision / Recall / F1",
        "Measured over the checks declaring `covers: full` — the ones that decide a named "
        "scenario's own defining condition.",
    ),
    (
        "Proxy F1",
        "Measured over the checks declaring `covers: artifact-signal-only`. These measure an "
        "enabling signal recorded beside a scenario the registry rules out-of-artifact or "
        "agent-judgable. **A proxy number is never coverage of that scenario** and never enters "
        "the gate.",
    ),
    (
        "Clean leakage",
        "How many of the category's clean packages had *any* check in its module fire on them, "
        "counting checks the case was not labeled against. The per-check confusion matrix cannot "
        "see those: a rule that convicts a package written to be clean for a sibling scenario is "
        "a false positive whether or not it owns that pair.",
    ),
    (
        "Gate",
        "The `F1 ≥ 0.80` verdict, decided from the scenario-level column alone.",
    ),
)


def _column_guide() -> str:
    rows = "\n".join(f"| **{name}** | {meaning} |" for name, meaning in COLUMN_GUIDE)
    return f"| Column | Meaning |\n| --- | --- |\n{rows}"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [PREAMBLE.rstrip().replace("<!-- COLUMN-GUIDE -->", _column_guide()), "", "## Results", ""]
    lines.append(
        "| Category | Registry static-detectable | Cases (floor) | Precision | Recall | F1 | "
        "Proxy F1 | Clean leakage | Gate |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for row in report["categories"]:
        corpus = row["corpus"]
        detectable = len(row["registry"]["static_detectable"])
        cases_cell = f"{corpus['cases']} ({corpus['formula_minimum']})" if corpus["cases"] else "0"
        proxy = row["artifact_signal_only"]
        proxy_cell = f"{proxy['f1']:.3f} *(n={proxy['cases']})*" if proxy else "—"
        leakage = row["any_check_firing_on_a_clean_case"]
        leak_cell = "—" if not leakage["clean_cases"] else f"{len(leakage['firings'])}/{leakage['clean_cases']}"
        lines.append(
            f"| `{row['category']}` {row['name']} | {detectable} | {cases_cell} | "
            f"{_pct(row['scenario_level'], 'precision')} | {_pct(row['scenario_level'], 'recall')} | "
            f"{_f1_cell(row)} | {proxy_cell} | {leak_cell} | {STATUS_LABEL[row['status']]} |"
        )

    passing = [r["category"] for r in report["categories"] if r["status"] == "pass"]
    failing = [r["category"] for r in report["categories"] if r["status"] == "fail"]
    uncovered = [r["category"] for r in report["categories"] if r["status"] == "declared-and-uncovered"]
    lines += [
        "",
        f"**{len(passing)} categories clear the {F1_THRESHOLD:.2f} floor** "
        f"({', '.join(f'`{c}`' for c in passing) or 'none'}). "
        + (
            f"**{len(failing)} fall below it** ({', '.join(f'`{c}`' for c in failing)}). "
            if failing
            else "**None fall below it.** "
        )
        + f"{len(uncovered)} publish no F1 at all ({', '.join(f'`{c}`' for c in uncovered)}) — "
        "their static-detectable tier is empty, so there is nothing to measure and "
        "the corpus is not padded to invent something.",
        "",
        "## Per-category detail",
        "",
    ]

    for row in report["categories"]:
        lines += _render_category(row)

    return "\n".join(lines).rstrip() + "\n"


def _render_category(row: dict[str, Any]) -> list[str]:
    reg = row["registry"]
    corpus = row["corpus"]
    lines = [f"### `{row['category']}` — {row['name']}", ""]
    lines.append(
        f"Registry tiering: **{len(reg['static_detectable'])} static-detectable**, "
        f"{len(reg['agent_judgable'])} agent-judgable, {len(reg['out_of_artifact'])} out-of-artifact "
        f"of {reg['scenarios']} named scenarios. "
        f"Corpus scope: `{row['f1_scope']}`. Gate: **{STATUS_LABEL[row['status']]}**."
    )
    lines.append("")

    if not row["checks"]:
        lines += [
            "No labeled corpus, and none is publishable: the registry tiers none of this "
            "category's scenarios static-detectable. Recorded as declared-and-uncovered "
            "rather than measured.",
            "",
        ]
        if reg["out_of_artifact"]:
            lines += [f"Out-of-artifact scenarios: {', '.join(f'`{s}`' for s in reg['out_of_artifact'])}.", ""]
        if row["note"]:
            lines += [f"> {row['note']}", ""]
        return lines

    balance = corpus["class_balance"]
    lines.append(
        f"Corpus: **{corpus['cases']} cases** ({balance['vulnerable']} vulnerable / "
        f"{balance['clean']} clean) across {corpus['labeled_detectable_checks']} labeled check(s); "
        f"the `max(6, 2 × detectable)` floor for that many checks is {corpus['formula_minimum']}."
    )
    lines.append("")
    lines.append("| Check | Detector | Covers | Registry scenario | TP | FP | FN | TN | P | R | F1 |")
    lines.append("| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for check in row["checks"]:
        ids = ", ".join(f"`{i}`" for i in check["registry_ids"]) or "—"
        lines.append(
            f"| `{check['corpus_check']}` | `{check['detector_check']}` | {check['covers']} | {ids} | "
            f"{check['true_positives']} | {check['false_positives']} | {check['false_negatives']} | "
            f"{check['true_negatives']} | {check['precision']:.3f} | {check['recall']:.3f} | "
            f"{check['f1']:.3f} |"
        )
    lines.append("")

    if row["scenario_level"]:
        block = row["scenario_level"]
        lines.append(
            f"Scenario-level total (n={block['cases']}): precision {block['precision']:.3f}, "
            f"recall {block['recall']:.3f}, **F1 {block['f1']:.3f}**."
        )
    else:
        lines.append(
            "No scenario-level total: every labeled check here is `artifact-signal-only`, "
            "so this category measures signals and covers no named scenario."
        )
    if row["artifact_signal_only"]:
        block = row["artifact_signal_only"]
        lines.append(
            f"Proxy total (n={block['cases']}): precision {block['precision']:.3f}, "
            f"recall {block['recall']:.3f}, F1 {block['f1']:.3f} — **not scenario coverage**."
        )

    leakage = row["any_check_firing_on_a_clean_case"]
    if leakage["firings"]:
        lines += [
            "",
            f"**{len(leakage['firings'])} check(s) fired on a clean case** across "
            f"{leakage['clean_cases']} clean package(s) — counted here even where the "
            "firing check is not the one the case was labeled against:",
            "",
        ]
        for firing in leakage["firings"]:
            lines.append(f"- `{firing['case']}` → `{firing['check']}`: {firing['evidence']}")
    else:
        lines.append(
            f"No check in this module fires on any of its {leakage['clean_cases']} clean "
            "packages — not only the labeled one."
        )
    lines.append("")
    if row["note"]:
        lines += [f"> {row['note']}", ""]
    return lines


# ------------------------------------------------------------------------------ cli


def _json_text(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eval/generate_f1_report.py",
        description="Measure every category's corpus and write eval/f1-report.json + docs/f1-report.md.",
    )
    parser.add_argument("--check", action="store_true", help="exit 1 if either artifact is stale; write nothing")
    parser.add_argument("--json-out", default=str(JSON_OUT))
    parser.add_argument("--markdown-out", default=str(MARKDOWN_OUT))
    args = parser.parse_args(argv)

    report = build_report()
    json_text = _json_text(report)
    markdown_text = render_markdown(report)
    json_path = Path(args.json_out)
    markdown_path = Path(args.markdown_out)

    if args.check:
        stale = [
            str(path)
            for path, text in ((json_path, json_text), (markdown_path, markdown_text))
            if not path.is_file() or path.read_text(encoding="utf-8") != text
        ]
        if stale:
            print(f"out of date — run eval/generate_f1_report.py: {', '.join(stale)}")
            return 1
        print("eval/f1-report.json, docs/f1-report.md: up to date")
        return 0

    json_path.write_text(json_text, encoding="utf-8")
    markdown_path.write_text(markdown_text, encoding="utf-8")
    print(f"{json_path}: written\n{markdown_path}: written")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
