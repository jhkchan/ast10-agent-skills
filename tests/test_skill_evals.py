"""`eval/skill_evals.py` produces the repository's THIRD kind of evidence, and the
tests it needs are the ones that catch a delta which only *looks* measured.

The other two surfaces answer different questions and are tested elsewhere:
`tests/test_generate_dashboard.py` guards the judge scores (the TEXT of a
SKILL.md against a rubric, no prompt executed) and
`tests/test_generate_f1_report.py` guards detector F1 (the Python scripts against
labelled fixtures). This file guards the only surface that runs a prompt: does an
agent holding the skill beat the same agent holding nothing.

Six failure shapes are pinned here, and every one of them is a way a with/without
number could be published without meaning anything:

1. **A counterfactual that is not one.** If the two arms differ anywhere but the
   skill block, the delta measures that difference instead. Asserted structurally
   — the without_skill section list must be the with_skill list minus exactly one
   element, and no distinctive line of a SKILL.md may survive into the
   without_skill prompt.
2. **Self-grading.** The agent and the grader must be different models, that must
   be enforced rather than documented, and both names must appear in every
   artifact. The grader must also never be told which arm it is grading.
3. **A grading that did not bind.** A grader response with the wrong number of
   verdicts, a duplicated index, or a non-boolean must be recorded as a refusal —
   never coerced into a pass, a fail, or a silently shorter checklist. And the
   assertion TEXT must come from the case, not from whatever the grader echoed.
4. **A delta over two different case sets.** A case whose with_skill arm failed
   must leave BOTH means, not just one.
5. **An invented number.** A provider that reports no token count must produce
   null, never zero, and the mean must say how many runs it covers.
6. **A clobbered corpus.** A rerun must not overwrite a previous iteration, and a
   resume must skip completed work rather than re-running (and re-billing) it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from adapters.base import AdapterStatus, ProviderAdapter, TokenUsage
from eval import skill_evals as se

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# Fakes — nothing in this file touches a network or a model
# --------------------------------------------------------------------------- #


class FakeAdapter(ProviderAdapter):
    """Scripted adapter. `script` entries are returned in order; an Exception
    entry is raised instead. Records every prompt it was given."""

    def __init__(self, name: str, script: list, usage: TokenUsage | None = None) -> None:
        self.name = name
        self.script = list(script)
        self.usage = usage
        self.prompts: list[str] = []

    def check_availability(self) -> AdapterStatus:
        return AdapterStatus(self.name, available=True)

    def judge(self, prompt: str) -> str:
        self.prompts.append(prompt)
        self.last_usage = None
        if not self.script:
            raise AssertionError(f"{self.name}: called more times than the script allows")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        self.last_usage = self.usage
        return item


def grader_json(flags: list[bool], evidence: str = "quoted") -> str:
    """A well-formed grader response marking each assertion per `flags`."""
    return json.dumps(
        {"assertion_results": [{"index": i, "passed": p, "evidence": evidence} for i, p in enumerate(flags, start=1)]}
    )


BEDROCK_USAGE = TokenUsage(input_tokens=1000, output_tokens=200, total_tokens=1200, source="test")


@pytest.fixture(scope="module")
def all_cases() -> list[se.EvalCase]:
    return se.discover_cases()


@pytest.fixture
def case(all_cases) -> se.EvalCase:
    """One real case that attaches input files — the richest shape to test."""
    return next(c for c in all_cases if c.skill == "AST01" and c.case_id == 1)


# --------------------------------------------------------------------------- #
# 1. Discovery
# --------------------------------------------------------------------------- #


def test_every_authored_case_is_discovered(all_cases):
    on_disk = sum(
        len(json.loads(p.read_text(encoding="utf-8"))["evals"])
        for p in sorted((REPO_ROOT / "skills").glob("*/evals/evals.json"))
    )
    assert len(all_cases) == on_disk
    assert on_disk > 0


def test_discovery_covers_every_skill_that_ships_cases(all_cases):
    shipped = {p.parent.parent.name for p in (REPO_ROOT / "skills").glob("*/evals/evals.json")}
    assert {c.skill for c in all_cases} == shipped


def test_slugs_are_unique_and_name_both_halves(all_cases):
    slugs = [c.slug for c in all_cases]
    assert len(slugs) == len(set(slugs))
    for c in all_cases:
        assert c.slug == f"{c.skill}-case-{c.case_id}"


def test_skill_filter_selects_only_that_skill():
    cases = se.discover_cases(["AST04"])
    assert cases and {c.skill for c in cases} == {"AST04"}


def test_case_filter_selects_only_those_ids():
    cases = se.discover_cases(None, [1])
    assert cases and {c.case_id for c in cases} == {1}


def test_unknown_skill_raises_rather_than_running_fewer_cases():
    with pytest.raises(se.SkillEvalError, match="ship no evals"):
        se.discover_cases(["AST99"])


# --------------------------------------------------------------------------- #
# 2. The counterfactual: exactly one respect
# --------------------------------------------------------------------------- #


def test_without_skill_is_with_skill_minus_exactly_one_section(all_cases):
    for c in all_cases:
        with_sections = se.agent_prompt_sections(c, with_skill=True)
        without_sections = se.agent_prompt_sections(c, with_skill=False)
        assert len(with_sections) == len(without_sections) + 1, c.slug
        removed = [s for s in with_sections if s not in without_sections]
        assert len(removed) == 1, c.slug
        assert removed[0].startswith(">>>>>>>>>> BEGIN INSTALLED SKILL"), c.slug
        # Order and content of everything else is untouched.
        assert [s for s in with_sections if s != removed[0]] == without_sections, c.slug


def test_with_skill_prompt_carries_the_skill_md_verbatim(all_cases):
    for c in all_cases:
        content = c.skill_md.read_text(encoding="utf-8")
        assert content in se.build_agent_prompt(c, with_skill=True), c.slug


def test_without_skill_prompt_carries_no_line_of_the_skill(all_cases):
    """Not just "the whole file is absent" — no distinctive line of it survives."""
    for c in all_cases:
        prompt = se.build_agent_prompt(c, with_skill=False)
        lines = [
            line.strip()
            for line in c.skill_md.read_text(encoding="utf-8").splitlines()
            if len(line.strip()) > 60 and not line.strip().startswith(("#", "-", "|", ">"))
        ]
        assert lines, f"{c.slug}: no long lines to test against — weaken the filter, not the test"
        leaked = [line for line in lines if line in prompt]
        assert not leaked, f"{c.slug}: {len(leaked)} skill line(s) leaked into the without_skill arm"


def test_both_arms_inline_identical_input_file_text(case):
    section = se.files_section(case)
    assert section is not None
    assert section in se.build_agent_prompt(case, with_skill=True)
    assert section in se.build_agent_prompt(case, with_skill=False)


def test_a_directory_input_expands_to_every_file_beneath_it(all_cases):
    case = next(c for c in all_cases if any((REPO_ROOT / f).is_dir() for f in c.files))
    directory = next(REPO_ROOT / f for f in case.files if (REPO_ROOT / f).is_dir())
    section = se.files_section(case)
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        assert f"BEGIN FILE: {path.relative_to(REPO_ROOT).as_posix()}" in section


def test_a_binary_input_is_named_not_decoded(tmp_path):
    blob = tmp_path / "report.docx"
    blob.write_bytes(b"PK\x03\x04\xff\xfe\x00binary")
    case = se.EvalCase("AST01", "x", 1, "p", "e", ("report.docx",), ("a", "b"))
    section = se.files_section(case, repo=tmp_path)
    assert "[binary file:" in section and "not reproducible as text" in section


def test_an_oversized_input_is_a_hard_error_not_a_truncation(tmp_path, monkeypatch):
    big = tmp_path / "big.md"
    big.write_text("x" * 100, encoding="utf-8")
    monkeypatch.setattr(se, "MAX_INPUT_BYTES_PER_CASE", 10)
    case = se.EvalCase("AST01", "x", 1, "p", "e", ("big.md",), ("a", "b"))
    with pytest.raises(se.SkillEvalError, match="exceeds"):
        se.files_section(case, repo=tmp_path)


def test_a_missing_input_is_a_hard_error(tmp_path):
    case = se.EvalCase("AST01", "x", 1, "p", "e", ("nope.md",), ("a", "b"))
    with pytest.raises(se.SkillEvalError, match="does not exist"):
        se.files_section(case, repo=tmp_path)


# --------------------------------------------------------------------------- #
# 3. The grader is a different model, and is blinded
# --------------------------------------------------------------------------- #


def test_default_agent_and_grader_are_different_verified_models():
    assert se.DEFAULT_AGENT_MODEL != se.DEFAULT_GRADER_MODEL
    assert se.DEFAULT_AGENT_MODEL in se.VERIFIED_MODELS
    assert se.DEFAULT_GRADER_MODEL in se.VERIFIED_MODELS


def test_every_verified_model_builds_an_adapter_without_network():
    for spec in se.VERIFIED_MODELS:
        adapter = se.build_adapter(spec)
        assert adapter.name.endswith(spec.split("/", 1)[1])
        adapter.check_availability()  # must not raise and must not call out


def test_an_unverified_model_is_refused():
    with pytest.raises(se.SkillEvalError, match="verified roster"):
        se.build_adapter("bedrock/not-a-model")


def test_same_model_for_agent_and_grader_exits_two(capsys, tmp_path):
    code = se.main(
        [
            "--agent-model",
            "bedrock/nova-pro",
            "--grader-model",
            "bedrock/nova-pro",
            "--workspace",
            str(tmp_path),
            "--dry-run",
        ]
    )
    assert code == 2
    assert "grading its own output" in capsys.readouterr().err


def test_grading_prompt_never_names_the_arm(case):
    prompt = se.build_grading_prompt(case, "some response")
    lowered = prompt.lower()
    assert "with_skill" not in lowered
    assert "without_skill" not in lowered
    assert "skill" not in prompt.split("--- BEGIN REQUEST THAT WAS ANSWERED ---")[0].lower()


def test_grading_prompt_carries_no_skill_content(case):
    prompt = se.build_grading_prompt(case, "some response")
    skill_text = case.skill_md.read_text(encoding="utf-8")
    long_lines = [ln.strip() for ln in skill_text.splitlines() if len(ln.strip()) > 60]
    assert not [ln for ln in long_lines if ln in prompt]


def test_grading_prompt_is_a_pure_function_of_case_and_response(case):
    assert se.build_grading_prompt(case, "R") == se.build_grading_prompt(case, "R")
    assert se.build_grading_prompt(case, "R") != se.build_grading_prompt(case, "S")


def test_grading_prompt_lists_every_assertion_and_states_the_count(case):
    prompt = se.build_grading_prompt(case, "R")
    for text in case.assertions:
        assert text in prompt
    assert f"exactly {len(case.assertions)} entries" in prompt


# --------------------------------------------------------------------------- #
# 4. Grading that binds, or a recorded refusal
# --------------------------------------------------------------------------- #


def test_a_well_formed_grading_binds_to_the_cases_assertions(case):
    flags = [True] * len(case.assertions)
    flags[0] = False
    results = se.parse_grading(grader_json(flags), case)
    assert [r["passed"] for r in results] == flags
    assert [r["text"] for r in results] == list(case.assertions)


def test_the_assertion_text_comes_from_the_case_not_the_grader(case):
    payload = json.dumps(
        {
            "assertion_results": [
                {"index": i, "passed": True, "evidence": "e", "text": "a paraphrase the grader preferred"}
                for i in range(1, len(case.assertions) + 1)
            ]
        }
    )
    results = se.parse_grading(payload, case)
    assert [r["text"] for r in results] == list(case.assertions)


def test_json_wrapped_in_prose_or_a_code_fence_still_binds(case):
    flags = [True] * len(case.assertions)
    raw = f"Sure, here you go:\n```json\n{grader_json(flags)}\n```\nHope that helps."
    assert len(se.parse_grading(raw, case)) == len(case.assertions)


def test_evidence_longer_than_the_cap_is_truncated(case):
    flags = [True] * len(case.assertions)
    results = se.parse_grading(grader_json(flags, evidence="z" * 5000), case)
    assert all(len(r["evidence"]) == se.MAX_EVIDENCE_CHARS for r in results)


@pytest.mark.parametrize(
    ("raw", "match"),
    [
        ("I decline to grade this.", "no JSON object"),
        ('{"assertion_results": "yes"}', "no `assertion_results` list"),
        ('{"nope": {"a": 1}}', "no `assertion_results` list"),
        ('{"assertion_results": [{"index": 1, "passed": true, "evidence": "e"}]}', "result\\(s\\) for"),
    ],
)
def test_a_grading_that_will_not_bind_is_a_refusal(case, raw, match):
    with pytest.raises(se.GradingParseError, match=match):
        se.parse_grading(raw, case)


def test_a_duplicated_index_is_a_refusal(case):
    n = len(case.assertions)
    payload = json.dumps({"assertion_results": [{"index": 1, "passed": True, "evidence": "e"} for _ in range(n)]})
    with pytest.raises(se.GradingParseError, match="appears twice"):
        se.parse_grading(payload, case)


def test_a_non_boolean_verdict_is_a_refusal(case):
    n = len(case.assertions)
    payload = json.dumps(
        {"assertion_results": [{"index": i, "passed": "yes", "evidence": "e"} for i in range(1, n + 1)]}
    )
    with pytest.raises(se.GradingParseError, match="not a boolean"):
        se.parse_grading(payload, case)


def test_summary_is_re_derivable_from_its_own_assertion_results():
    results = [{"text": "a", "passed": True}, {"text": "b", "passed": False}, {"text": "c", "passed": True}]
    summary = se.summarise(results)
    assert summary == {"passed": 2, "failed": 1, "total": 3, "pass_rate": 0.6667}
    assert summary["passed"] + summary["failed"] == summary["total"]


# --------------------------------------------------------------------------- #
# 5. One (case, configuration) run: the artifacts the convention fixes
# --------------------------------------------------------------------------- #


def _run(case, tmp_path, *, agent_script=None, grader_script=None, usage=BEDROCK_USAGE, retries=1, cfg="with_skill"):
    agent = FakeAdapter("agent/A", agent_script or ["a full answer"], usage=usage)
    grader = FakeAdapter("grader/B", grader_script or [grader_json([True] * len(case.assertions))])
    dest = tmp_path / case.slug / cfg
    outcome = se.run_configuration(case, cfg, dest, agent, grader, grader_retries=retries)
    return outcome, dest, agent, grader


def test_a_completed_run_writes_exactly_the_convention_artifacts(case, tmp_path):
    outcome, dest, _, _ = _run(case, tmp_path)
    assert outcome["ok"]
    assert (dest / "outputs" / "response.md").read_text(encoding="utf-8") == "a full answer"
    assert (dest / "timing.json").is_file()
    assert (dest / "grading.json").is_file()
    assert (dest / "prompt.txt").is_file()
    assert (dest / "run.json").is_file()
    assert not (dest / "error.json").exists()


def test_timing_json_has_the_two_contract_fields_with_real_values(case, tmp_path):
    _, dest, _, _ = _run(case, tmp_path)
    timing = json.loads((dest / "timing.json").read_text(encoding="utf-8"))
    assert timing["total_tokens"] == 1200
    assert isinstance(timing["duration_ms"], int) and timing["duration_ms"] >= 0


def test_grading_json_has_the_two_contract_fields(case, tmp_path):
    _, dest, _, _ = _run(case, tmp_path)
    grading = json.loads((dest / "grading.json").read_text(encoding="utf-8"))
    assert set(grading["summary"]) == {"passed", "failed", "total", "pass_rate"}
    assert len(grading["assertion_results"]) == len(case.assertions)
    assert set(grading["assertion_results"][0]) == {"text", "passed", "evidence"}


def test_both_models_are_recorded_in_every_artifact(case, tmp_path):
    _, dest, _, _ = _run(case, tmp_path)
    for name in ("timing.json", "grading.json"):
        payload = json.loads((dest / name).read_text(encoding="utf-8"))
        assert payload["models"] == {"agent": "agent/A", "grader": "grader/B"}


def test_the_prompt_that_was_sent_is_kept_beside_the_answer(case, tmp_path):
    _, dest, agent, _ = _run(case, tmp_path)
    assert (dest / "prompt.txt").read_text(encoding="utf-8") == agent.prompts[0]


def test_a_provider_with_no_usage_records_null_tokens_not_zero(case, tmp_path):
    _, dest, _, _ = _run(case, tmp_path, usage=None)
    timing = json.loads((dest / "timing.json").read_text(encoding="utf-8"))
    assert timing["total_tokens"] is None
    assert "reports no token usage" in timing["token_source"]


def test_an_agent_failure_writes_an_error_and_no_grading(case, tmp_path):
    outcome, dest, _, grader = _run(case, tmp_path, agent_script=[RuntimeError("bedrock: throttled")])
    assert outcome["ok"] is False
    error = json.loads((dest / "error.json").read_text(encoding="utf-8"))
    assert error["stage"] == "agent" and "throttled" in error["error"]
    assert error["models"] == {"agent": "agent/A", "grader": "grader/B"}
    assert not (dest / "grading.json").exists()
    assert grader.prompts == []  # a failed agent is never graded


def test_an_empty_agent_response_is_a_recorded_failure(case, tmp_path):
    outcome, dest, _, _ = _run(case, tmp_path, agent_script=["   \n "])
    assert outcome["ok"] is False
    assert "empty response" in json.loads((dest / "error.json").read_text(encoding="utf-8"))["error"]


def test_the_grader_is_re_asked_once_then_the_refusal_is_recorded(case, tmp_path):
    outcome, dest, _, grader = _run(case, tmp_path, grader_script=["not json", "still not json"])
    assert outcome["ok"] is False
    assert len(grader.prompts) == 2
    error = json.loads((dest / "error.json").read_text(encoding="utf-8"))
    assert error["stage"] == "grading"
    assert [a["attempt"] for a in error["attempts"]] == [1, 2]
    assert all("response_excerpt" in a for a in error["attempts"])
    # The response the agent gave is still on disk: the run happened, the grading did not.
    assert (dest / "outputs" / "response.md").is_file()
    assert (dest / "timing.json").is_file()
    assert not (dest / "grading.json").exists()


def test_a_grader_that_recovers_on_the_retry_is_a_pass(case, tmp_path):
    good = grader_json([True] * len(case.assertions))
    outcome, dest, _, _ = _run(case, tmp_path, grader_script=["garbage", good])
    assert outcome["ok"]
    assert json.loads((dest / "grading.json").read_text(encoding="utf-8"))["grader_attempts"] == 2


def test_a_rerun_clears_the_previous_attempts_verdict(case, tmp_path):
    _run(case, tmp_path, grader_script=["nope", "nope"])
    dest = tmp_path / case.slug / "with_skill"
    assert (dest / "error.json").is_file()
    _run(case, tmp_path)
    assert (dest / "grading.json").is_file()
    assert not (dest / "error.json").exists()


# --------------------------------------------------------------------------- #
# 6. benchmark.json
# --------------------------------------------------------------------------- #


def _seed(iteration_dir: Path, slug: str, cfg: str, pass_rate: float, seconds: float, tokens: int | None):
    dest = iteration_dir / slug / cfg
    (dest / "outputs").mkdir(parents=True, exist_ok=True)
    (dest / "outputs" / "response.md").write_text("answer", encoding="utf-8")
    passed = round(pass_rate * 4)
    (dest / "grading.json").write_text(
        json.dumps(
            {
                "assertion_results": [{"text": f"a{i}", "passed": i < passed, "evidence": ""} for i in range(4)],
                "summary": {"passed": passed, "failed": 4 - passed, "total": 4, "pass_rate": pass_rate},
            }
        ),
        encoding="utf-8",
    )
    (dest / "timing.json").write_text(
        json.dumps({"total_tokens": tokens, "duration_ms": int(seconds * 1000)}), encoding="utf-8"
    )


def _seed_error(iteration_dir: Path, slug: str, cfg: str, reason: str = "bedrock: throttled"):
    dest = iteration_dir / slug / cfg
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "error.json").write_text(
        json.dumps({"stage": "agent", "provider": "agent/A", "error": reason}), encoding="utf-8"
    )


@pytest.fixture
def seeded(tmp_path) -> Path:
    it = tmp_path / "iteration-1"
    _seed(it, "AST01-case-1", "with_skill", 1.0, 10.0, 1000)
    _seed(it, "AST01-case-1", "without_skill", 0.5, 8.0, 400)
    _seed(it, "AST02-case-1", "with_skill", 0.75, 12.0, 1200)
    _seed(it, "AST02-case-1", "without_skill", 0.25, 6.0, 300)
    return it


def test_run_summary_has_exactly_the_contract_shape(seeded):
    summary = se.build_benchmark(seeded, {"agent": "a", "grader": "b"}, 1)["run_summary"]
    assert set(summary) == {"with_skill", "without_skill", "delta"}
    for cfg in ("with_skill", "without_skill"):
        assert set(summary[cfg]) == {"pass_rate", "time_seconds", "tokens"}
        for block in summary[cfg].values():
            assert {"mean", "stddev"} <= set(block)
    assert set(summary["delta"]) == {"pass_rate", "time_seconds", "tokens"}


def test_every_published_mean_is_re_derivable_from_the_cases_beside_it(seeded):
    benchmark = se.build_benchmark(seeded, {"agent": "a", "grader": "b"}, 1)
    rows = benchmark["cases"]
    for cfg in ("with_skill", "without_skill"):
        expected = sum(r[cfg]["pass_rate"] for r in rows) / len(rows)
        assert benchmark["run_summary"][cfg]["pass_rate"]["mean"] == round(expected, 4)


def test_the_delta_is_with_minus_without_from_the_published_means(seeded):
    summary = se.build_benchmark(seeded, {"agent": "a", "grader": "b"}, 1)["run_summary"]
    assert summary["with_skill"]["pass_rate"]["mean"] == 0.875
    assert summary["without_skill"]["pass_rate"]["mean"] == 0.375
    assert summary["delta"]["pass_rate"] == 0.5
    assert summary["delta"]["time_seconds"] == round(11.0 - 7.0, 2)
    assert summary["delta"]["tokens"] == round(1100.0 - 350.0, 1)


def test_an_unpaired_case_leaves_both_means_with_a_stated_reason(seeded):
    _seed(seeded, "AST03-case-1", "with_skill", 1.0, 99.0, 9999)
    _seed_error(seeded, "AST03-case-1", "without_skill")
    benchmark = se.build_benchmark(seeded, {"agent": "a", "grader": "b"}, 1)
    assert [r["eval"] for r in benchmark["cases"]] == ["AST01-case-1", "AST02-case-1"]
    assert benchmark["run_summary"]["with_skill"]["pass_rate"]["n"] == 2
    assert benchmark["counts"]["cases_excluded"] == 1
    excluded = benchmark["excluded"]
    assert [e["eval"] for e in excluded] == ["AST03-case-1"]
    assert "throttled" in excluded[0]["reason"]


def test_a_case_missing_a_whole_arm_is_excluded_as_absent(seeded):
    _seed(seeded, "AST04-case-1", "with_skill", 1.0, 5.0, 100)
    benchmark = se.build_benchmark(seeded, {"agent": "a", "grader": "b"}, 1)
    excluded = [e for e in benchmark["excluded"] if e["eval"] == "AST04-case-1"]
    assert excluded and excluded[0]["configuration"] == "without_skill"
    assert "not run" in excluded[0]["reason"]


def test_all_null_tokens_publish_no_mean_rather_than_zero(tmp_path):
    it = tmp_path / "iteration-1"
    _seed(it, "AST01-case-1", "with_skill", 1.0, 3.0, None)
    _seed(it, "AST01-case-1", "without_skill", 0.5, 3.0, None)
    summary = se.build_benchmark(it, {"agent": "a", "grader": "b"}, 1)["run_summary"]
    assert summary["with_skill"]["tokens"] == {"n": 0, "mean": None, "stddev": None}
    assert summary["delta"]["tokens"] is None


def test_a_partial_token_report_says_how_many_runs_it_covers(tmp_path):
    it = tmp_path / "iteration-1"
    _seed(it, "AST01-case-1", "with_skill", 1.0, 3.0, 500)
    _seed(it, "AST01-case-1", "without_skill", 1.0, 3.0, 500)
    _seed(it, "AST02-case-1", "with_skill", 1.0, 3.0, None)
    _seed(it, "AST02-case-1", "without_skill", 1.0, 3.0, None)
    summary = se.build_benchmark(it, {"agent": "a", "grader": "b"}, 1)["run_summary"]
    assert summary["with_skill"]["tokens"]["n"] == 1
    assert summary["with_skill"]["pass_rate"]["n"] == 2


def test_a_single_paired_case_reports_a_null_stddev_not_a_crash_and_not_a_zero(tmp_path):
    """One observation has no spread; 0.0 would dress that up as a measurement.

    This module and `eval/skill_eval_grade.py` both write a file called
    `benchmark.json`, and they used to disagree here — 0.0 in one, null in the
    other, for the identical situation. The reconciliation is null on both
    sides, which is the true statement and the one
    `tests/test_skill_eval_grade.py::test_a_single_run_reports_a_null_stddev_not_a_zero`
    already required of the other writer.
    """
    it = tmp_path / "iteration-1"
    _seed(it, "AST01-case-1", "with_skill", 1.0, 3.0, 500)
    _seed(it, "AST01-case-1", "without_skill", 0.0, 3.0, 500)
    summary = se.build_benchmark(it, {"agent": "a", "grader": "b"}, 1)["run_summary"]
    assert summary["with_skill"]["pass_rate"] == {"n": 1, "mean": 1.0, "stddev": None}


def test_both_benchmark_writers_publish_one_definition_of_stddev(seeded):
    """Neither module may explain `stddev` in its own words.

    `eval/skill_evals.py` imports `STDDEV_NOTE` from `eval/skill_eval_grade.py`
    rather than restating it, so a reader who meets the field in one iteration
    directory and again in the next is reading the same sentence. This test
    fails if either module starts carrying its own copy.
    """
    import eval.skill_eval_grade as grade

    benchmark = se.build_benchmark(seeded, {"agent": "a", "grader": "b"}, 1)
    assert benchmark["notes"]["stddev"] == grade.STDDEV_NOTE
    assert se.STDDEV_NOTE is grade.STDDEV_NOTE
    assert "a single observation has no spread" in benchmark["notes"]["stddev"]


def test_the_benchmark_records_both_models_and_the_standing_limitations(seeded):
    benchmark = se.build_benchmark(seeded, {"agent": "bedrock/qwen3-235b", "grader": "bedrock/gpt-oss-120b"}, 1)
    assert benchmark["models"] == {"agent": "bedrock/qwen3-235b", "grader": "bedrock/gpt-oss-120b"}
    assert se.SINGLE_AGENT_LIMITATION in benchmark["limitations"]
    assert se.GRADER_BLINDING_LIMITATION in benchmark["limitations"]
    assert se.PAIRING_RULE in benchmark["limitations"]


def test_the_benchmark_never_calls_its_number_an_f1_or_a_judge_total(seeded):
    benchmark = se.build_benchmark(seeded, {"agent": "a", "grader": "b"}, 1)
    assert "NOT a detector F1" in benchmark["measures"]
    blob = json.dumps(benchmark)
    assert '"f1"' not in blob and '"grade"' not in blob and '"verdict"' not in blob


# --------------------------------------------------------------------------- #
# 7. Iterations, resume, CLI
# --------------------------------------------------------------------------- #


def test_the_next_iteration_is_the_next_unused_integer(tmp_path):
    assert se.next_iteration(tmp_path) == 1
    (tmp_path / "iteration-1").mkdir()
    (tmp_path / "iteration-4").mkdir()
    (tmp_path / "not-an-iteration").mkdir()
    assert se.existing_iterations(tmp_path) == [1, 4]
    assert se.next_iteration(tmp_path) == 5


def test_is_complete_requires_a_response_and_a_parseable_grading(tmp_path, seeded):
    assert se.is_complete(seeded / "AST01-case-1" / "with_skill")
    (seeded / "AST01-case-1" / "with_skill" / "grading.json").write_text("{oops", encoding="utf-8")
    assert not se.is_complete(seeded / "AST01-case-1" / "with_skill")
    assert not se.is_complete(tmp_path / "nothing-here")


def test_an_error_json_is_not_completion(tmp_path):
    _seed_error(tmp_path, "AST01-case-1", "with_skill")
    assert not se.is_complete(tmp_path / "AST01-case-1" / "with_skill")


def test_dry_run_writes_nothing_and_calls_no_model(tmp_path, capsys):
    code = se.main(["--dry-run", "--workspace", str(tmp_path), "--skills", "AST01"])
    assert code == 0
    assert list(tmp_path.iterdir()) == []
    out = capsys.readouterr().out
    assert "nothing written, no model called" in out
    assert "AST01-case-1" in out


def test_benchmark_only_recomputes_from_disk_without_calling_a_model(seeded, capsys):
    code = se.main(["--benchmark-only", "--iteration", "1", "--workspace", str(seeded.parent)])
    assert code == 0
    benchmark = json.loads((seeded / "benchmark.json").read_text(encoding="utf-8"))
    assert benchmark["run_summary"]["delta"]["pass_rate"] == 0.5
    assert "rewritten from disk" in capsys.readouterr().out


def test_benchmark_only_on_a_missing_iteration_exits_two(tmp_path):
    assert se.main(["--benchmark-only", "--iteration", "9", "--workspace", str(tmp_path)]) == 2


def test_resume_skips_a_completed_configuration(monkeypatch, tmp_path, case):
    """A resumed long run must not re-bill work it already paid for."""
    iteration_dir = tmp_path / "iteration-1"
    _seed(iteration_dir, case.slug, "with_skill", 1.0, 5.0, 100)
    calls: list[str] = []

    def fake_run(c, configuration, config_dir, agent, grader, **kwargs):
        calls.append(configuration)
        _seed(iteration_dir, c.slug, configuration, 0.5, 5.0, 100)
        return {
            "ok": True,
            "summary": {"passed": 2, "failed": 2, "total": 4, "pass_rate": 0.5},
            "duration_ms": 5000,
            "total_tokens": 100,
        }

    monkeypatch.setattr(se, "run_configuration", fake_run)
    monkeypatch.setattr(se, "build_adapter", lambda spec: FakeAdapter(spec, []))
    code = se.main(
        ["--iteration", "1", "--workspace", str(tmp_path), "--skills", case.skill, "--cases", str(case.case_id)]
    )
    assert code == 0
    assert calls == ["without_skill"]


def test_no_resume_reruns_a_completed_configuration(monkeypatch, tmp_path, case):
    iteration_dir = tmp_path / "iteration-1"
    _seed(iteration_dir, case.slug, "with_skill", 1.0, 5.0, 100)
    calls: list[str] = []

    def fake_run(c, configuration, config_dir, agent, grader, **kwargs):
        calls.append(configuration)
        _seed(iteration_dir, c.slug, configuration, 0.5, 5.0, 100)
        return {
            "ok": True,
            "summary": {"passed": 2, "failed": 2, "total": 4, "pass_rate": 0.5},
            "duration_ms": 5000,
            "total_tokens": 100,
        }

    monkeypatch.setattr(se, "run_configuration", fake_run)
    monkeypatch.setattr(se, "build_adapter", lambda spec: FakeAdapter(spec, []))
    se.main(
        [
            "--iteration",
            "1",
            "--workspace",
            str(tmp_path),
            "--no-resume",
            "--skills",
            case.skill,
            "--cases",
            str(case.case_id),
        ]
    )
    assert calls == ["with_skill", "without_skill"]


def test_a_run_without_an_iteration_flag_never_writes_into_an_existing_one(monkeypatch, tmp_path, case):
    (tmp_path / "iteration-1").mkdir(parents=True)
    (tmp_path / "iteration-1" / "canary.txt").write_text("frozen", encoding="utf-8")

    def fake_run(c, configuration, config_dir, agent, grader, **kwargs):
        _seed(config_dir.parent.parent, c.slug, configuration, 1.0, 1.0, 10)
        return {
            "ok": True,
            "summary": {"passed": 4, "failed": 0, "total": 4, "pass_rate": 1.0},
            "duration_ms": 1000,
            "total_tokens": 10,
        }

    monkeypatch.setattr(se, "run_configuration", fake_run)
    monkeypatch.setattr(se, "build_adapter", lambda spec: FakeAdapter(spec, []))
    se.main(["--workspace", str(tmp_path), "--skills", case.skill, "--cases", str(case.case_id)])
    assert (tmp_path / "iteration-2" / "benchmark.json").is_file()
    assert (tmp_path / "iteration-1" / "canary.txt").read_text(encoding="utf-8") == "frozen"
    assert not (tmp_path / "iteration-1" / "benchmark.json").exists()


def test_feedback_json_gets_a_key_per_eval_and_keeps_human_notes(tmp_path):
    it = tmp_path / "iteration-1"
    it.mkdir(parents=True)
    se.write_feedback(it, ["AST01-case-1", "AST02-case-1"])
    assert json.loads((it / "feedback.json").read_text(encoding="utf-8")) == {
        "AST01-case-1": "",
        "AST02-case-1": "",
    }
    (it / "feedback.json").write_text(
        json.dumps({"AST01-case-1": "the without arm hallucinated a scenario id"}), encoding="utf-8"
    )
    merged = se.write_feedback(it, ["AST01-case-1", "AST02-case-1", "AST03-case-1"])
    assert merged["AST01-case-1"] == "the without arm hallucinated a scenario id"
    assert merged["AST03-case-1"] == ""


# --------------------------------------------------------------------------- #
# 8. This surface does not touch the other two
# --------------------------------------------------------------------------- #


def test_the_runner_reads_no_gate_constant_and_no_scorecard():
    source = (REPO_ROOT / "eval" / "skill_evals.py").read_text(encoding="utf-8")
    body = source.split('"""', 2)[2]  # the module docstring may name them prosaically
    for forbidden in ("ship_floor", "FLOORS", "POOLED_TARGET", "CONFIDENCE_K", "MIN_ROUNDS", "scorecards"):
        assert forbidden not in body, f"the eval runner must not reference {forbidden}"


def test_no_scorecard_or_gate_file_is_importable_from_this_module():
    imported = {name for name in dir(se) if not name.startswith("_")}
    assert "ship_floor" not in imported
    assert "aggregate_verdict" not in imported


# --------------------------------------------------------------------------- #
# 9. Composing with the blind grader in eval/skill_eval_grade.py
# --------------------------------------------------------------------------- #

GRADE_MODULE = REPO_ROOT / "eval" / "skill_eval_grade.py"


def _load_sibling_grader():
    """The blind grader module, or a skip. Loaded by path the way its own tests
    load it, so this file never depends on `eval/` being an importable package."""
    import importlib.util

    if not GRADE_MODULE.is_file():
        pytest.skip("eval/skill_eval_grade.py is not present in this checkout")
    spec = importlib.util.spec_from_file_location("skill_eval_grade_interop", GRADE_MODULE)
    module = importlib.util.module_from_spec(spec)
    # Registered before exec: the module defines dataclasses, and dataclasses
    # resolves annotations through sys.modules[cls.__module__].
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_run_json_names_the_arm_and_the_agent_that_produced_it(case, tmp_path):
    _, dest, _, _ = _run(case, tmp_path, cfg="without_skill")
    meta = json.loads((dest / "run.json").read_text(encoding="utf-8"))
    assert meta["configuration"] == "without_skill"
    assert meta["agent_model"] == "agent/A"
    assert meta["skill_content_included"] is False
    assert meta["eval"] == case.slug
    assert meta["input_files"] == list(case.files)


def test_run_json_marks_the_with_skill_arm_as_carrying_the_skill(case, tmp_path):
    _, dest, _, _ = _run(case, tmp_path, cfg="with_skill")
    assert json.loads((dest / "run.json").read_text(encoding="utf-8"))["skill_content_included"] is True


def test_the_sibling_blind_grader_can_name_the_agent_from_what_this_runner_wrote(case, tmp_path):
    """The interop point: a second process must be able to check the
    different-models rule against a run it did not perform."""
    grade = _load_sibling_grader()
    for attr in ("RunDir", "resolve_agent_model"):
        if not hasattr(grade, attr):
            pytest.skip(f"the sibling grader no longer exposes {attr}")
    _, dest, _, _ = _run(case, tmp_path)
    run = grade.RunDir(path=dest, eval_slug=case.slug, configuration="with_skill")
    assert grade.resolve_agent_model(run) == "agent/A"


def test_no_grade_produces_the_run_and_leaves_grading_alone(case, tmp_path):
    agent = FakeAdapter("agent/A", ["an answer"], usage=BEDROCK_USAGE)
    dest = tmp_path / case.slug / "with_skill"
    outcome = se.run_configuration(case, "with_skill", dest, agent, None)
    assert outcome["ok"] and outcome["summary"] is None
    assert (dest / "outputs" / "response.md").is_file()
    assert (dest / "timing.json").is_file()
    assert (dest / "run.json").is_file()
    assert not (dest / "grading.json").exists()
    assert json.loads((dest / "timing.json").read_text(encoding="utf-8"))["models"] == {"agent": "agent/A"}


def test_no_grade_completion_does_not_require_a_grading_json(case, tmp_path):
    agent = FakeAdapter("agent/A", ["an answer"], usage=BEDROCK_USAGE)
    dest = tmp_path / case.slug / "with_skill"
    se.run_configuration(case, "with_skill", dest, agent, None)
    assert se.is_complete(dest, require_grading=False)
    assert not se.is_complete(dest)


def test_no_grade_writes_no_benchmark_because_nothing_was_graded(monkeypatch, tmp_path, case, capsys):
    def fake_run(c, configuration, config_dir, agent, grader, **kwargs):
        assert grader is None
        (config_dir / "outputs").mkdir(parents=True, exist_ok=True)
        (config_dir / "outputs" / "response.md").write_text("a", encoding="utf-8")
        (config_dir / "timing.json").write_text(json.dumps({"total_tokens": 1, "duration_ms": 1}), encoding="utf-8")
        return {"ok": True, "summary": None, "duration_ms": 1, "total_tokens": 1}

    monkeypatch.setattr(se, "run_configuration", fake_run)
    monkeypatch.setattr(se, "build_adapter", lambda spec: FakeAdapter(spec, []))
    code = se.main(
        [
            "--no-grade",
            "--workspace",
            str(tmp_path),
            "--skills",
            case.skill,
            "--cases",
            str(case.case_id),
        ]
    )
    assert code == 0
    assert not (tmp_path / "iteration-1" / "benchmark.json").exists()
    assert not (tmp_path / "iteration-1" / "feedback.json").exists()
    assert "skill_eval_grade.py" in capsys.readouterr().out


def test_no_grade_does_not_refuse_a_matching_grader_model_it_never_uses(monkeypatch, tmp_path, case):
    monkeypatch.setattr(se, "build_adapter", lambda spec: FakeAdapter(spec, []))
    code = se.main(
        [
            "--no-grade",
            "--dry-run",
            "--workspace",
            str(tmp_path),
            "--agent-model",
            "bedrock/nova-pro",
            "--grader-model",
            "bedrock/nova-pro",
            "--skills",
            case.skill,
        ]
    )
    assert code == 0
