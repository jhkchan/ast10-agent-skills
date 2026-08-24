"""Guard on `docs/skill-eval-report.md`, the third report surface.

Every published figure in this repository is regenerable by a script and guarded
by a test. This module is that guard for the with/without eval page: it asserts
the committed page is exactly what the generator produces from the committed
workspace, that the page states its own unit and cross-links the other two
surfaces, and — the load-bearing one — that a partial run cannot render as a full
one.

What it deliberately does NOT do is call a model or run an eval. The page is a
projection of `eval/skill-eval-workspace/`, and if the projection is faithful the
numbers on it are as trustworthy as the workspace beneath it and no more.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.generate_skill_eval_report import (  # noqa: E402
    authored_case_count,
    build,
    discover_iterations,
    main,
    render,
)

REPORT = REPO_ROOT / "docs" / "skill-eval-report.md"


@pytest.fixture(scope="module")
def committed() -> str:
    assert REPORT.is_file(), "docs/skill-eval-report.md is missing — run eval/generate_skill_eval_report.py"
    return REPORT.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# The page is the generator's output, not a hand-edit
# --------------------------------------------------------------------------- #


def test_the_committed_page_is_exactly_what_the_generator_produces():
    assert main(["--check"]) == 0, "run `python3 eval/generate_skill_eval_report.py`"


def test_check_mode_writes_nothing(tmp_path):
    target = tmp_path / "skill-eval-report.md"
    assert main(["--check", "--markdown-out", str(target)]) == 1
    assert not target.exists()


def test_writing_then_checking_is_idempotent(tmp_path):
    target = tmp_path / "skill-eval-report.md"
    assert main(["--markdown-out", str(target)]) == 0
    assert main(["--check", "--markdown-out", str(target)]) == 0


# --------------------------------------------------------------------------- #
# It says what it measures, and does not let the reader confuse the surfaces
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "fragment",
    [
        "not a detector F1",
        "not a judge rubric total",
        "nothing on this page feeds the ship gate",
    ],
)
def test_the_page_refuses_the_three_confusions(committed, fragment):
    assert fragment in committed


@pytest.mark.parametrize(
    ("surface", "link"),
    [
        ("Judge scores", "skill-judge-dashboard.md"),
        ("Detector F1", "f1-report.md"),
    ],
)
def test_the_page_cross_links_the_other_two_surfaces(committed, surface, link):
    """A sentence saying what each surface answers, and a link to it."""
    assert surface in committed
    assert link in committed


def test_each_surface_gets_a_question_not_only_a_name(committed):
    for phrase in (
        "Is the *text* of a `SKILL.md` well written",
        "Do the shipped Python check scripts separate",
        "Does an agent *holding* a skill behave better",
    ):
        assert phrase in committed


def test_the_page_names_the_delta_as_the_deliverable(committed):
    assert "the delta between the two pass rates is the deliverable" in committed
    assert "does not beat its own absence here has not been shown to work" in committed


def test_the_page_records_both_the_agent_and_the_grader(committed):
    assert "Agent under test" in committed
    assert "Grader" in committed
    assert "always different models" in committed


# --------------------------------------------------------------------------- #
# A partial run may not read as a full one
# --------------------------------------------------------------------------- #


def test_the_authored_corpus_size_matches_the_files_on_disk(committed):
    cases, assertions = authored_case_count()
    assert f"**{cases} cases**" in committed
    assert f"**{assertions} assertions**" in committed


def test_every_iteration_publishes_its_coverage_against_the_whole_corpus(committed):
    cases, _ = authored_case_count()
    iterations = discover_iterations()
    for number, payload in iterations:
        counts = payload.get("counts", {})
        paired = counts.get("cases_paired", counts.get("evals_paired"))
        assert f"| iteration-{number} | {paired} of {cases} |" in committed, (
            f"iteration-{number} must publish its coverage as '{paired} of {cases}'; a partial "
            f"run that renders without its denominator reads as a full one"
        )


def test_an_empty_workspace_publishes_no_delta_at_all():
    """The failure mode here is a page that renders 0.00 for an iteration that never
    ran. Nothing is better than a zero that looks like a measurement."""
    page = render([], (33, 162))
    assert "No iteration has been aggregated yet" in page
    assert "Δ pass_rate" not in page


def test_a_missing_number_renders_as_a_dash_never_as_zero():
    payload = {
        "generated_by": "eval/skill_evals.py",
        "models": {"agent": "a", "grader": "b"},
        "counts": {"cases_paired": 0},
        "run_summary": {
            "with_skill": {"pass_rate": {"mean": None, "stddev": None}},
            "without_skill": {"pass_rate": {"mean": None, "stddev": None}},
            "delta": {"pass_rate": None},
        },
        "cases": [],
    }
    page = render([(1, payload)], (33, 162))
    assert "| 0.00 |" not in page
    assert "| — | — | — |" in page


# --------------------------------------------------------------------------- #
# Both benchmark writers are readable, because both write `benchmark.json`
# --------------------------------------------------------------------------- #


def test_both_writers_envelopes_render_their_models_and_their_cases():
    """`eval/skill_evals.py` and `eval/skill_eval_grade.py` wrap an identical
    `run_summary` in different envelopes. A reader that understood only one of
    them would silently drop half the evidence."""
    inline = {
        "generated_by": "eval/skill_evals.py",
        "models": {"agent": "bedrock/qwen3-235b", "grader": "bedrock/gpt-oss-120b"},
        "counts": {"cases_paired": 1},
        "run_summary": {
            "with_skill": {"pass_rate": {"mean": 1.0}},
            "without_skill": {"pass_rate": {"mean": 0.5}},
            "delta": {"pass_rate": 0.5},
        },
        "cases": [
            {
                "eval": "AST01-case-1",
                "with_skill": {"pass_rate": 1.0},
                "without_skill": {"pass_rate": 0.5},
                "pass_rate_delta": 0.5,
            }
        ],
    }
    blind = {
        "generated_by": "eval/skill_eval_grade.py",
        "agent_models": ["bedrock/qwen3-235b"],
        "grader_models": ["bedrock/deepseek-v3.2"],
        "counts": {"evals_paired": 1},
        "run_summary": {
            "with_skill": {"pass_rate": {"mean": 0.8}},
            "without_skill": {"pass_rate": {"mean": 0.4}},
            "delta": {"pass_rate": 0.4},
        },
        "per_eval": [{"eval_slug": "AST02-case-1", "with_skill": 0.8, "without_skill": 0.4, "delta_pass_rate": 0.4}],
    }
    page = render([(1, inline), (2, blind)], (33, 162))
    assert "`bedrock/gpt-oss-120b`" in page
    assert "`bedrock/deepseek-v3.2`" in page
    assert "`AST01-case-1`" in page
    assert "`AST02-case-1`" in page
    assert "`eval/skill_evals.py`" in page
    assert "`eval/skill_eval_grade.py`" in page


def test_discovery_skips_an_iteration_that_has_runs_but_no_benchmark(tmp_path):
    """An un-aggregated iteration is not a result; half-reporting it would publish a
    delta nobody computed."""
    (tmp_path / "iteration-1" / "AST01-case-1" / "with_skill").mkdir(parents=True)
    (tmp_path / "iteration-2").mkdir()
    (tmp_path / "iteration-2" / "benchmark.json").write_text(json.dumps({"run_summary": {}}), encoding="utf-8")
    found = discover_iterations(tmp_path)
    assert [number for number, _ in found] == [2]


def test_the_page_is_regenerable_without_touching_the_network():
    """`build()` reads only files. If this ever needs a model, the page has stopped
    being a projection of committed evidence."""
    assert build() == REPORT.read_text(encoding="utf-8")
