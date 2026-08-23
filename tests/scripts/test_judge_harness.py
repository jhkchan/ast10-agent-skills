"""Tests for scripts.judge_harness -- spec.md S-001, S-006, S-008 (T-2.3)."""

from __future__ import annotations

import json

import pytest

from scripts.judge_harness import DIMENSIONS, JudgmentParseError, call_model, run_judge


class _FakeAdapter:
    """Deterministic stand-in for a live provider adapter (no network calls).

    The real adapters (bedrock, claude-cli, anthropic-compatible) are T-2.1's
    concern -- this harness only depends on the ``name`` + ``judge()`` shape,
    so a fake exercises the harness end to end without a live provider call.
    """

    def __init__(
        self,
        name: str,
        scores: dict[str, int] | None = None,
        error: Exception | None = None,
    ):
        self.name = name
        self._scores = scores
        self._error = error

    def judge(self, prompt: str, *, timeout: float = 60.0) -> str:
        if self._error is not None:
            raise self._error
        return json.dumps(self._scores)


def _full_scores(base: int) -> dict[str, int]:
    return {d: base for d in DIMENSIONS}


def test_call_model_returns_all_eight_dimension_scores():
    """S-001/S-006: a single provider's judgment always carries all D1-D8 sub-scores."""
    adapter = _FakeAdapter("claude-cli", scores=_full_scores(15))

    result = call_model(adapter, "judge this skill")

    assert result["provider"] == "claude-cli"
    assert set(result["scores"]) == set(DIMENSIONS)
    assert result["scores"]["D1"] == 15.0
    assert result["total"] == pytest.approx(15.0 * len(DIMENSIONS))


def test_call_model_raises_on_malformed_response():
    """call_model surfaces a parse failure rather than fabricating scores."""
    adapter = _FakeAdapter("broken", scores={"D1": 10})  # missing D2-D8

    with pytest.raises(JudgmentParseError):
        call_model(adapter, "judge this skill")


def test_run_judge_emits_scores_json_with_per_provider_and_pooled_scores(tmp_path):
    """S-001/S-006: an end-to-end run over one skill with two working adapters
    emits scores.json with all eight dimension sub-scores per provider plus
    the pooled aggregate."""
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("---\nname: sample-skill\n---\nBody.", encoding="utf-8")
    output_path = tmp_path / "scores.json"

    adapters = [
        _FakeAdapter("claude-cli", scores=_full_scores(18)),
        _FakeAdapter("bedrock", scores=_full_scores(12)),
    ]

    result = run_judge(skill_file, adapters, output_path=output_path)

    assert result["status"] == "complete"
    assert len(result["judgments"]) == 2
    for judgment in result["judgments"]:
        assert set(judgment["scores"]) == set(DIMENSIONS)
    assert result["pooled"]["scores"]["D1"] == pytest.approx(15.0)
    assert result["pooled"]["n_providers"] == 2
    assert result["audit_trail"] == []

    on_disk = json.loads(output_path.read_text(encoding="utf-8"))
    assert on_disk == result


def test_run_judge_excludes_crashed_provider_with_audit_trail(tmp_path):
    """S-008: a provider that raises mid-round is excluded from the pool with
    an audit-trail entry (timestamp, provider name, error message); the run
    still publishes, marked partial, with the audit trail attached."""
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("---\nname: sample-skill\n---\nBody.", encoding="utf-8")
    output_path = tmp_path / "scores.json"

    adapters = [
        _FakeAdapter("claude-cli", scores=_full_scores(18)),
        _FakeAdapter("openai-compatible", error=TimeoutError("provider timed out after 60s")),
    ]

    result = run_judge(skill_file, adapters, output_path=output_path)

    assert result["status"] == "partial"
    assert len(result["judgments"]) == 1
    assert len(result["audit_trail"]) == 1
    entry = result["audit_trail"][0]
    assert entry["provider"] == "openai-compatible"
    assert "timed out" in entry["error"]
    assert "timestamp" in entry
    assert result["pooled"]["n_providers"] == 1

    assert output_path.exists()
