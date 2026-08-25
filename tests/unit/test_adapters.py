"""Unit tests for adapters/base.py + the three concrete provider adapters
(plan.md T-2.1: "Build the provider-adapter interface with
declare-or-skip-with-reason handling").

Exercises:
  S-004 — an unavailable provider is skipped, its reason is recorded in
          config/audit.yml, and the roster build never fails.
  S-008 — a mid-round RuntimeError excludes only that provider's judgment,
          with an audit-trail entry of timestamp/provider/error message.

`judge()`'s live network/subprocess path is intentionally NOT exercised
here (no credentials, no network, no real `claude` binary in CI) — only
`check_availability()` (pure, no I/O) and the base-module dispatch logic
around a fake adapter are unit-tested, per the Hard rule "use a fake/mock
and document the gap" (steps/04-build-tdd.md).
"""

from __future__ import annotations

import pathlib
import sys
import types

import pytest
import yaml

from adapters.anthropic_compatible import ZAI_API_KEY_ENV, AnthropicCompatibleAdapter
from adapters.base import (
    AdapterError,
    AdapterStatus,
    ProviderAdapter,
    build_roster,
    call_adapter,
    static_unavailable,
)
from adapters.bedrock import MODELS, BedrockAdapter
from adapters.claude_cli import ClaudeCliAdapter

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
AUDIT_PATH = REPO_ROOT / "config" / "audit.yml"


class _FakeAdapter(ProviderAdapter):
    """Test double: availability and judge() outcome fixed at construction
    time, so S-004/S-008 can be exercised without network access or real
    credentials."""

    def __init__(self, name: str, available: bool = True, reason: str = "", fail_with: str | None = None) -> None:
        self.name = name
        self._available = available
        self._reason = reason
        self._fail_with = fail_with

    def check_availability(self) -> AdapterStatus:
        return AdapterStatus(self.name, available=self._available, reason=self._reason)

    def judge(self, prompt: str) -> str:
        if self._fail_with is not None:
            raise RuntimeError(self._fail_with)
        return f"judged:{prompt}"


# --- config/audit.yml: static declare-or-skip entries -----------------------


def test_audit_yml_declares_dashscope_unavailable_with_exact_reason():
    data = yaml.safe_load(AUDIT_PATH.read_text(encoding="utf-8"))
    entries = {k: v for k, v in data["providers"].items() if "dashscope" in k.lower()}
    assert entries, "expected a declared-unavailable dashscope entry in config/audit.yml"
    (entry,) = entries.values()
    assert entry["status"] == "unavailable"
    # spec.md S-004 Then: 'recorded reason in config/audit.yml ("DASHSCOPE_API_KEY unset")'
    assert entry["reason"] == "DASHSCOPE_API_KEY unset"


def test_audit_yml_declares_bedrock_anthropic_geo_blocked():
    data = yaml.safe_load(AUDIT_PATH.read_text(encoding="utf-8"))
    entries = {
        k: v
        for k, v in data["providers"].items()
        if v.get("adapter") == "bedrock" and "anthropic" in str(v.get("model", "")).lower()
    }
    assert entries, "expected a declared-unavailable bedrock anthropic.* entry"
    (entry,) = entries.values()
    assert entry["status"] == "unavailable"
    assert "unsupported countries" in entry["reason"]


def test_audit_yml_declares_zai_openai_compatible_path_unfunded():
    data = yaml.safe_load(AUDIT_PATH.read_text(encoding="utf-8"))
    entries = {k: v for k, v in data["providers"].items() if "zai" in k.lower()}
    assert entries, "expected a declared-unavailable z.ai openai-compatible entry"
    (entry,) = entries.values()
    assert entry["status"] == "unavailable"
    assert "unfunded" in entry["reason"] or "Insufficient balance" in entry["reason"]


def test_static_unavailable_reads_all_declared_entries_with_reasons():
    statuses = static_unavailable(AUDIT_PATH)
    assert len(statuses) >= 3
    assert all(isinstance(s, AdapterStatus) for s in statuses)
    assert all(not s.available for s in statuses)
    assert all(s.reason.strip() for s in statuses)


# --- S-004: unavailable adapter is skipped, recorded, run does not fail ----


def test_build_roster_skips_unavailable_adapter_with_recorded_reason(tmp_path):
    audit_path = tmp_path / "audit.yml"
    dashscope_like = _FakeAdapter("openai-compatible/dashscope", available=False, reason="DASHSCOPE_API_KEY unset")
    claude_cli = _FakeAdapter("claude-cli/sonnet", available=True)
    bedrock = _FakeAdapter("bedrock/nova-pro", available=True)

    roster = build_roster([claude_cli, bedrock, dashscope_like], audit_path=audit_path)

    assert [a.name for a in roster.available] == ["claude-cli/sonnet", "bedrock/nova-pro"]
    assert [s.name for s in roster.unavailable] == ["openai-compatible/dashscope"]
    assert roster.unavailable[0].reason == "DASHSCOPE_API_KEY unset"

    recorded = yaml.safe_load(audit_path.read_text(encoding="utf-8"))
    reasons = [e["reason"] for e in recorded["runtime_entries"] if e["provider"] == "openai-compatible/dashscope"]
    assert reasons == ["DASHSCOPE_API_KEY unset"]


def test_build_roster_never_raises_when_some_adapters_unavailable(tmp_path):
    audit_path = tmp_path / "audit.yml"
    adapters = [
        _FakeAdapter("claude-cli/sonnet", available=True),
        _FakeAdapter("openai-compatible/dashscope", available=False, reason="DASHSCOPE_API_KEY unset"),
    ]
    roster = build_roster(adapters, audit_path=audit_path)  # must not raise
    assert len(roster.available) == 1
    assert len(roster.unavailable) == 1


def test_adapter_status_unavailable_requires_a_reason():
    with pytest.raises(ValueError):
        AdapterStatus("x", available=False, reason="")


# --- S-008: mid-round RuntimeError excludes only that judgment -------------


def test_call_adapter_excludes_crashed_provider_and_records_audit_entry(tmp_path):
    audit_path = tmp_path / "audit.yml"
    crashing = _FakeAdapter("openai-compatible/timeout-provider", fail_with="timed out after 30s")

    result = call_adapter(crashing, "judge this skill", audit_path=audit_path)

    assert result is None
    recorded = yaml.safe_load(audit_path.read_text(encoding="utf-8"))
    entries = [e for e in recorded["runtime_entries"] if e["provider"] == "openai-compatible/timeout-provider"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["status"] == "failed"
    assert entry["reason"] == "timed out after 30s"
    assert entry["timestamp"]


def test_call_adapter_excludes_only_the_crashed_provider(tmp_path):
    audit_path = tmp_path / "audit.yml"
    healthy = _FakeAdapter("claude-cli/sonnet")
    crashing = _FakeAdapter("openai-compatible/timeout-provider", fail_with="boom")

    healthy_result = call_adapter(healthy, "p", audit_path=audit_path)
    crashed_result = call_adapter(crashing, "p", audit_path=audit_path)

    assert healthy_result == "judged:p"
    assert crashed_result is None
    recorded = yaml.safe_load(audit_path.read_text(encoding="utf-8"))
    # only the crash is recorded -- the healthy call never touches the audit trail
    assert len(recorded["runtime_entries"]) == 1


def test_adapter_error_is_a_runtime_error():
    # spec.md S-008: "the openai-compatible adapter ... raises a RuntimeError"
    assert issubclass(AdapterError, RuntimeError)


# --- concrete adapters: check_availability() is pure / no network ----------


def test_bedrock_adapter_rejects_unknown_model():
    with pytest.raises(ValueError):
        BedrockAdapter("not-a-real-model")


def test_bedrock_adapter_models_match_verified_ids():
    # build-notes.md "Judge / target model matrix — VERIFIED LIVE"
    assert MODELS["gpt-oss-120b"] == "openai.gpt-oss-120b-1:0"
    assert MODELS["qwen3-235b"] == "qwen.qwen3-235b-a22b-2507-v1:0"
    assert MODELS["deepseek-v3.2"] == "deepseek.v3.2"
    # the `us.` inference-profile prefix is REQUIRED; the bare id fails on-demand
    assert MODELS["nova-pro"] == "us.amazon.nova-pro-v1:0"


def test_bedrock_adapter_unavailable_without_credentials(monkeypatch):
    adapter = BedrockAdapter("nova-pro")
    monkeypatch.setattr(adapter, "_get_credentials", lambda: None)
    status = adapter.check_availability()
    assert status.available is False
    assert "credential" in status.reason.lower()


def test_bedrock_adapter_available_with_credentials(monkeypatch):
    adapter = BedrockAdapter("nova-pro")
    monkeypatch.setattr(adapter, "_get_credentials", lambda: object())
    status = adapter.check_availability()
    assert status.available is True


def test_claude_cli_adapter_unavailable_when_binary_missing(monkeypatch):
    monkeypatch.setattr("adapters.claude_cli.shutil.which", lambda _: None)
    status = ClaudeCliAdapter().check_availability()
    assert status.available is False
    assert status.reason


def test_claude_cli_adapter_available_when_binary_present(monkeypatch):
    monkeypatch.setattr("adapters.claude_cli.shutil.which", lambda _: "/usr/local/bin/claude")
    status = ClaudeCliAdapter().check_availability()
    assert status.available is True


def test_anthropic_compatible_unavailable_without_api_key(monkeypatch):
    monkeypatch.delenv(ZAI_API_KEY_ENV, raising=False)
    status = AnthropicCompatibleAdapter.from_env().check_availability()
    assert status.available is False
    assert ZAI_API_KEY_ENV in status.reason


def test_anthropic_compatible_available_with_api_key(monkeypatch):
    monkeypatch.setenv(ZAI_API_KEY_ENV, "test-key")
    status = AnthropicCompatibleAdapter.from_env().check_availability()
    assert status.available is True


# --- token accounting: what a provider reported, or the absence of it -------
#
# Added with `eval/skill_evals.py`, whose contract requires a real per-run
# `total_tokens` and forbids inventing one. Three facts are pinned:
# the count is read from the response rather than estimated; a provider that
# reports nothing yields None rather than a plausible integer; and a previous
# call's count can never be attributed to a later one.


class _FakeBedrockClient:
    """Stands in for boto3's bedrock-runtime client, `converse` only."""

    def __init__(self, response):
        self.response = response

    def converse(self, **_kwargs):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _fake_boto3(response=None, *, client=True, session=None):
    """A stand-in `boto3` module.

    `adapters/bedrock.py` imports boto3 lazily inside the methods that use it,
    on purpose, so that a missing install degrades one adapter rather than the
    whole package. These tests exercise OUR parsing of what `converse` returns
    and never touch boto3's own behaviour, so binding the real package here
    would add a dependency that buys no coverage -- and CI does not install it,
    which is exactly how these tests failed there while passing on a machine
    that happens to have the AWS CLI. Injecting the module keeps them running
    everywhere and, unlike `pytest.importorskip`, they can never skip silently.
    """
    mod = types.ModuleType("boto3")
    if client:
        mod.client = lambda *a, **k: _FakeBedrockClient(response)
    if session is not None:
        mod.Session = session
    return mod


def _bedrock_with(monkeypatch, response):
    monkeypatch.setitem(sys.modules, "boto3", _fake_boto3(response))
    return BedrockAdapter("nova-pro")


_TEXT_ONLY = {"output": {"message": {"content": [{"text": "hello"}]}}}


def test_bedrock_records_the_usage_block_converse_returns(monkeypatch):
    response = dict(_TEXT_ONLY, usage={"inputTokens": 900, "outputTokens": 100, "totalTokens": 1000})
    adapter = _bedrock_with(monkeypatch, response)
    assert adapter.judge("p") == "hello"
    assert adapter.last_usage.total_tokens == 1000
    assert adapter.last_usage.input_tokens == 900
    assert adapter.last_usage.output_tokens == 100
    assert MODELS["nova-pro"] in adapter.last_usage.source


def test_bedrock_records_no_usage_when_the_response_carries_none(monkeypatch):
    adapter = _bedrock_with(monkeypatch, dict(_TEXT_ONLY))
    adapter.judge("p")
    assert adapter.last_usage is None


def test_bedrock_never_carries_a_previous_calls_token_count_forward(monkeypatch):
    """A stale count attributed to a later call is a fabricated measurement."""
    fake = _fake_boto3(dict(_TEXT_ONLY, usage={"totalTokens": 7}))
    monkeypatch.setitem(sys.modules, "boto3", fake)
    adapter = BedrockAdapter("nova-pro")
    adapter.judge("first")
    assert adapter.last_usage.total_tokens == 7

    fake.client = lambda *a, **k: _FakeBedrockClient(RuntimeError("throttled"))
    with pytest.raises(AdapterError):
        adapter.judge("second")
    assert adapter.last_usage is None


def test_bedrock_ignores_a_usage_field_that_is_not_a_number(monkeypatch):
    adapter = _bedrock_with(monkeypatch, dict(_TEXT_ONLY, usage={"totalTokens": "lots"}))
    adapter.judge("p")
    assert adapter.last_usage.total_tokens is None


def test_token_usage_sums_a_pair_only_when_both_halves_are_present():
    from adapters.base import TokenUsage

    assert TokenUsage.from_pair(10, 5, "src").total_tokens == 15
    assert TokenUsage.from_pair(10, None, "src").total_tokens is None
    assert TokenUsage.from_pair(None, None, "src").total_tokens is None


def test_claude_cli_reports_no_token_usage_and_says_so_by_being_none(monkeypatch):
    """`claude -p` print mode returns the answer and nothing about cost."""
    import subprocess

    class _Completed:
        returncode = 0
        stdout = "an answer"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Completed())
    adapter = ClaudeCliAdapter()
    assert adapter.judge("p") == "an answer"
    assert adapter.last_usage is None


# --- the documented degradation path, which nothing exercised ---------------
#
# adapters/bedrock.py imports boto3 lazily and check_availability() promises
# `available=False, reason="boto3 is not installed"` when it is absent. That
# promise was never tested: every bedrock test ran on a machine that had boto3,
# which is also why CI's ModuleNotFoundError went unnoticed until it fired.


def test_bedrock_reports_itself_unavailable_when_boto3_is_absent(monkeypatch):
    """The lazy import exists so one missing package degrades one adapter."""
    monkeypatch.setitem(sys.modules, "boto3", None)  # import boto3 -> ImportError
    status = BedrockAdapter("nova-pro").check_availability()
    assert status.available is False
    assert status.reason == "boto3 is not installed"


def test_bedrock_reports_itself_unavailable_when_credentials_are_absent(monkeypatch):
    """A resolvable boto3 with no credentials is a different refusal, and the
    reason a roster records must say which one it hit."""

    class _NoCredsSession:
        def get_credentials(self):
            return None

    monkeypatch.setitem(sys.modules, "boto3", _fake_boto3(client=False, session=_NoCredsSession))
    status = BedrockAdapter("nova-pro").check_availability()
    assert status.available is False
    assert status.reason == "no AWS credentials configured"
