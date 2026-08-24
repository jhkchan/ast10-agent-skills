"""A discarded judgment must survive the process that discarded it.

Run 5 of the judge matrix attempted 198 judgments, pooled 188, and recorded
nothing at all about the other ten: `run_judge` built its audit trail in a local
list, `eval/run_judge_matrix.py` kept only the judgments, and the per-round file
holding everything else was deleted at the end of the loop. The reasons and the
raw responses are unrecoverable (`eval/run5-refusals.md`).

These tests are the reason that cannot happen twice. Every one of them asserts
against the FILE, not against the return value — a refusal that is only in the
returned dict is exactly the defect that lost run 5's ten.

Companion suites: `tests/test_refusal_ledger.py` (no scorecard may ship a gap it
cannot account for) and `tests/unit/test_adapters.py` (the append-only audit
path itself).
"""

from __future__ import annotations

import inspect
import json

import pytest
import yaml

from adapters.base import (
    AUDIT_PATH,
    MAX_RESPONSE_EXCERPT,
    RECORDABLE_STATUSES,
    record_failure,
    redact_secrets,
    response_excerpt,
    runtime_entries,
)
from scripts.judge_harness import DIMENSIONS, JudgmentParseError, call_model, load_rubric, run_judge


def _response(score: int = 14) -> str:
    """A judgement that parses: eight scores, eight distinct justifications.

    Clamped to each dimension's own maximum by the rubric rather than by a
    constant here — D7 is out of 10, and a fixture that ignored that would be
    testing the range check instead of the recording path.
    """
    maxima = load_rubric().maxima
    return json.dumps(
        {d: {"score": min(score, maxima[d]), "why": f"{d} cites the NEVER section, mid band."} for d in DIMENSIONS}
    )


class _FakeAdapter:
    def __init__(self, name: str, *, response: str | None = None, error: Exception | None = None) -> None:
        self.name = name
        self._response = response
        self._error = error

    def judge(self, prompt: str) -> str:
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


def _skill(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text("---\nname: sample-skill\n---\nBody.", encoding="utf-8")
    return path


def _entries(audit_file):
    return yaml.safe_load(audit_file.read_text(encoding="utf-8"))["runtime_entries"]


# ---------------------------------------------------------------------------
# 1. The refusal reaches the persisted record
# ---------------------------------------------------------------------------


def test_a_malformed_judgement_is_written_to_the_audit_file(tmp_path):
    """THE test this whole file exists for: a deliberately malformed adapter,
    and the refusal is on disk when the call returns."""
    audit_file = tmp_path / "audit.yml"
    adapters = [
        _FakeAdapter("bedrock/honest", response=_response(14)),
        # Parses as JSON, carries no justification: the pre-2026-08-23 flat
        # contract, which the judge prompt tells every provider is refused.
        _FakeAdapter("bedrock/unjustified", response=json.dumps({d: 15 for d in DIMENSIONS})),
    ]

    result = run_judge(
        _skill(tmp_path),
        adapters,
        output_path=tmp_path / "scores.json",
        skill="AST01",
        round_index=3,
        audit_path=audit_file,
    )

    assert [j["provider"] for j in result["judgments"]] == ["bedrock/honest"]

    (entry,) = _entries(audit_file)
    assert entry["provider"] == "bedrock/unjustified"
    assert entry["status"] == "malformed"
    assert entry["skill"] == "AST01"
    assert entry["round"] == 3
    assert entry["timestamp"]
    # The reason parse_judgment gave, not a generic "excluded".
    assert "flat contract" in entry["reason"]
    # Enough of the offending response to diagnose it.
    assert '"D1": 15' in entry["response_excerpt"]
    assert entry["response_chars"] == len(json.dumps({d: 15 for d in DIMENSIONS}))


def test_the_returned_audit_trail_is_the_persisted_entry(tmp_path):
    """A returned record that differs from the written one is two records, and
    the one that outlives the process is the file."""
    audit_file = tmp_path / "audit.yml"
    adapters = [_FakeAdapter("judge", response="I decline to answer in JSON.")]

    result = run_judge(
        _skill(tmp_path),
        adapters,
        output_path=tmp_path / "scores.json",
        skill="AST04",
        round_index=1,
        audit_path=audit_file,
    )

    (returned,) = result["audit_trail"]
    (persisted,) = _entries(audit_file)
    # `error` is the key spec.md S-008 names for the same string; everything
    # else must be the written entry verbatim.
    assert returned["error"] == persisted["reason"]
    assert {k: v for k, v in returned.items() if k != "error"} == persisted


def test_a_crashed_provider_is_recorded_as_failed_not_malformed(tmp_path):
    """ "the provider was down" and "the provider would not justify itself" are
    different facts and must stay distinguishable in the file."""
    audit_file = tmp_path / "audit.yml"
    adapters = [_FakeAdapter("bedrock/nova-pro", error=TimeoutError("read timed out after 180s"))]

    run_judge(
        _skill(tmp_path),
        adapters,
        output_path=tmp_path / "scores.json",
        skill="AST07",
        round_index=1,
        audit_path=audit_file,
    )

    (entry,) = _entries(audit_file)
    assert entry["status"] == "failed"
    assert "timed out" in entry["reason"]
    # No response existed, so none is claimed.
    assert "response_excerpt" not in entry
    assert entry["skill"] == "AST07"
    assert entry["round"] == 1


def test_every_refusal_in_a_round_is_recorded_not_just_the_first(tmp_path):
    audit_file = tmp_path / "audit.yml"
    adapters = [
        _FakeAdapter("a", response="{}"),
        _FakeAdapter("b", response=_response(13)),
        _FakeAdapter("c", error=RuntimeError("boom")),
        _FakeAdapter("d", response=json.dumps({d: {"score": 12, "why": "Good."} for d in DIMENSIONS})),
    ]

    result = run_judge(
        _skill(tmp_path),
        adapters,
        output_path=tmp_path / "scores.json",
        skill="AST02",
        round_index=2,
        audit_path=audit_file,
    )

    assert result["attempted"] == 4
    assert result["pooled_n"] == 1
    entries = _entries(audit_file)
    assert [e["provider"] for e in entries] == ["a", "c", "d"]
    assert [e["status"] for e in entries] == ["malformed", "failed", "malformed"]
    assert all(e["skill"] == "AST02" and e["round"] == 2 for e in entries)


def test_the_audit_file_is_append_only_across_rounds(tmp_path):
    """Round 2's refusal must not overwrite round 1's."""
    audit_file = tmp_path / "audit.yml"
    skill = _skill(tmp_path)
    for round_index in (1, 2, 3):
        run_judge(
            skill,
            [_FakeAdapter("flaky", response="not json at all")],
            output_path=tmp_path / "scores.json",
            skill="AST05",
            round_index=round_index,
            audit_path=audit_file,
        )
    assert [e["round"] for e in _entries(audit_file)] == [1, 2, 3]


def test_run_judge_records_by_default_and_offers_no_way_to_opt_out(tmp_path):
    """There is no argument value that means "discard without recording".

    `audit_path=None` is the default and means the repository's real
    config/audit.yml — not "no file". The signature is asserted rather than
    exercised so the test does not write to the repo's own audit trail.
    """
    signature = inspect.signature(run_judge)
    assert signature.parameters["audit_path"].default is None

    from scripts.judge_harness import DEFAULT_AUDIT_PATH

    assert DEFAULT_AUDIT_PATH == AUDIT_PATH
    assert DEFAULT_AUDIT_PATH.name == "audit.yml"


def test_the_skill_defaults_to_the_directory_the_scorecard_is_keyed_by(tmp_path):
    audit_file = tmp_path / "audit.yml"
    skill_dir = tmp_path / "AST09"
    skill_dir.mkdir()
    path = skill_dir / "SKILL.md"
    path.write_text("---\nname: sample\n---\nBody.", encoding="utf-8")

    run_judge(
        path,
        [_FakeAdapter("x", response="nope")],
        output_path=tmp_path / "scores.json",
        round_index=1,
        audit_path=audit_file,
    )

    assert _entries(audit_file)[0]["skill"] == "AST09"


# ---------------------------------------------------------------------------
# 2. What the recorded response looks like
# ---------------------------------------------------------------------------


def test_the_parse_error_carries_the_response_that_was_refused():
    """`call_model` is the only layer holding both; without this the excerpt
    cannot exist."""
    adapter = _FakeAdapter("broken", response='{"D1": {"score": 10, "why": "only one dimension"}}')

    with pytest.raises(JudgmentParseError) as caught:
        call_model(adapter, "judge this skill")

    assert caught.value.raw_response == '{"D1": {"score": 10, "why": "only one dimension"}}'


def test_a_long_response_is_truncated_and_says_by_how_much(tmp_path):
    audit_file = tmp_path / "audit.yml"
    long_response = "x" * (MAX_RESPONSE_EXCERPT + 500)

    run_judge(
        _skill(tmp_path),
        [_FakeAdapter("verbose", response=long_response)],
        output_path=tmp_path / "scores.json",
        skill="AST03",
        round_index=1,
        audit_path=audit_file,
    )

    (entry,) = _entries(audit_file)
    assert entry["response_chars"] == MAX_RESPONSE_EXCERPT + 500
    assert "truncated 500 more characters" in entry["response_excerpt"]
    # Truncated, not omitted.
    assert entry["response_excerpt"].startswith("x" * 100)


def test_a_credential_shaped_string_is_redacted_by_name_not_deleted():
    redacted = redact_secrets("failed: Authorization: Bearer abcdef0123456789xyz was rejected")
    assert "abcdef0123456789xyz" not in redacted
    assert "<redacted:bearer-token>" in redacted

    excerpt, original = response_excerpt("key sk-abcdef0123456789ABCDEF said no")
    assert "sk-abcdef0123456789ABCDEF" not in excerpt
    assert "<redacted:api-key>" in excerpt
    assert original == len("key sk-abcdef0123456789ABCDEF said no")


def test_a_short_response_is_recorded_whole():
    excerpt, original = response_excerpt("nope")
    assert excerpt == "nope"
    assert original == 4


# ---------------------------------------------------------------------------
# 3. record_failure's own contract
# ---------------------------------------------------------------------------


def test_record_failure_rejects_a_status_it_does_not_define(tmp_path):
    with pytest.raises(ValueError, match="status must be one of"):
        record_failure("p", "why", tmp_path / "audit.yml", status="ignored")


def test_record_failure_still_takes_its_original_three_arguments(tmp_path):
    """call_adapter has no skill/round context and must keep working."""
    audit_file = tmp_path / "audit.yml"
    entry = record_failure("openai-compatible/x", "timed out", audit_file)
    assert entry["status"] == "failed"
    assert "skill" not in entry and "round" not in entry
    assert runtime_entries(audit_file) == [entry]


def test_recordable_statuses_are_the_two_the_harness_can_produce():
    assert RECORDABLE_STATUSES == {"failed", "malformed"}
