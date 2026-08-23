"""Live judge harness for OWASP AST detector skills (spec.md S-001, S-006, S-008).

Runs one skill through the pluggable multi-provider judge matrix (spec.md
"Judge matrix ... runs across four provider adapters ... in a pluggable
pattern") and publishes every surviving provider's eight-dimension
sub-scores plus the pooled aggregate. A provider that raises mid-round
(timeout, auth failure, crash) is excluded from the pool with an
audit-trail entry rather than aborting the run (spec.md S-008: "excludes
that provider's judgment from the pooled computation with an audit-trail
entry (timestamp, provider name, error message)").

The prior-art seams this repo inherited (the upstream eval-harness repository's
scripts/run_evals.py ``call_model`` and scripts/judge_skill.py
``run_judge``) are ``RuntimeError`` stubs, not working code -- this module
is the fresh, live implementation spec.md's Assumptions section calls out
as net-new work.

``call_model`` is the per-provider primitive; ``run_judge`` is the
end-to-end orchestrator that loops every configured adapter, pools the
surviving judgments, and writes ``scores.json``.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

# The pinned skill-judge rubric: 8 dimensions, 120 points total (build-notes.md
# "skill-judge rubric (softaworks)"). D1 Knowledge Delta is the dimension the
# per-dimension floor gate (spec.md gate-2) polices most aggressively.
DIMENSIONS: tuple[str, ...] = ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8")

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class JudgeAdapter(Protocol):
    """Duck-typed provider-adapter contract ``call_model`` invokes.

    The real adapters (bedrock, claude-cli, anthropic-compatible, ...) are
    T-2.1's concern; this harness only depends on this minimal shape so it
    can be exercised against fakes without a live provider. Matches
    ``adapters.base.ProviderAdapter.judge(self, prompt: str) -> str`` --
    every shipped adapter owns its own timeout via constructor config
    (e.g. ``ClaudeCliAdapter(timeout_s=...)``), so this harness never passes
    a ``timeout`` kwarg into ``judge()``.
    """

    name: str

    def judge(self, prompt: str) -> str: ...


class JudgmentParseError(ValueError):
    """Raised when a provider's raw response cannot be parsed into scores."""


def _build_prompt(skill_content: str) -> str:
    """Default judging prompt: the pinned 8-dimension rubric plus a strict
    JSON-only response contract so ``_parse_scores`` has a stable shape to
    parse regardless of which provider answers."""
    return (
        "Score the following Claude Agent Skill against the pinned "
        "skill-judge 8-dimension rubric (D1 Knowledge Delta 20, D2 Mindset "
        "+ Appropriate Procedures 15, D3 Anti-Pattern Quality 15, D4 "
        "Specification Compliance 15, D5 Progressive Disclosure 15, D6 "
        "Freedom Calibration 15, D7 Pattern Recognition 10, D8 Practical "
        "Usability 15). Respond with a single JSON object of the exact "
        'shape {"D1": <int>, "D2": <int>, "D3": <int>, "D4": <int>, '
        '"D5": <int>, "D6": <int>, "D7": <int>, "D8": <int>} and nothing '
        f"else.\n\n---\n{skill_content}\n---"
    )


def _parse_scores(raw_text: str) -> dict[str, float]:
    """Extract the eight D1-D8 dimension scores from a provider's raw text.

    Untrusted model output is a trust boundary: a response missing a
    dimension or that is not JSON at all raises rather than being silently
    padded or dropped.
    """
    match = _JSON_OBJECT_RE.search(raw_text)
    if match is None:
        raise JudgmentParseError(f"no JSON object found in model response: {raw_text!r}")
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise JudgmentParseError(f"model response is not valid JSON: {exc}") from exc

    scores_payload = payload.get("scores", payload) if isinstance(payload, dict) else {}
    missing = [d for d in DIMENSIONS if d not in scores_payload]
    if missing:
        raise JudgmentParseError(f"model response missing dimension score(s): {missing}")
    return {d: float(scores_payload[d]) for d in DIMENSIONS}


def call_model(adapter: JudgeAdapter, prompt: str, *, timeout: float = 60.0) -> dict[str, Any]:
    """Invoke a single provider adapter and return its per-dimension judgment.

    Returns ``{"provider": ..., "scores": {"D1": ..., ..., "D8": ...},
    "total": <sum>, "raw_response": <str>}`` -- all eight sub-scores are
    always present when this returns (spec.md S-001/S-006: "all eight
    dimension sub-scores per provider"). Whatever the adapter raises
    (timeout, RuntimeError, auth failure) propagates unchanged so
    ``run_judge`` can record the failure rather than this function
    silently swallowing it.

    ``timeout`` is accepted for callers that want to document a per-round
    budget, but is never forwarded into ``adapter.judge()``: every shipped
    adapter (``adapters.base.ProviderAdapter``) declares ``judge(self,
    prompt: str) -> str`` and owns its own timeout via constructor config
    instead (``ClaudeCliAdapter(timeout_s=...)``, etc.) -- forwarding a
    ``timeout=`` kwarg here made every live adapter raise ``TypeError``.
    """
    raw = adapter.judge(prompt)
    scores = _parse_scores(raw)
    return {
        "provider": adapter.name,
        "scores": scores,
        "total": sum(scores.values()),
        "raw_response": raw,
    }


def _pool(judgments: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Mean-pool per-dimension scores across every surviving judgment."""
    if not judgments:
        return None
    pooled_scores = {d: sum(j["scores"][d] for j in judgments) / len(judgments) for d in DIMENSIONS}
    return {
        "scores": pooled_scores,
        "total": sum(pooled_scores.values()),
        "n_providers": len(judgments),
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_judge(
    skill_path: str | Path,
    adapters: list[JudgeAdapter],
    *,
    output_path: str | Path = "scores.json",
    prompt: str | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Judge one skill across every configured adapter and publish scores.json.

    Loops every adapter, calling :func:`call_model`. A raising adapter is
    excluded from the pool with an audit-trail entry -- timestamp, provider
    name, error message -- rather than aborting the run (spec.md S-008).
    The run publishes ``status: "complete"`` when every adapter succeeded,
    ``"partial"`` when some but not all did, and ``"failed"`` when none did.
    Writes the result to ``output_path`` as JSON and returns the same dict.
    """
    skill_path = Path(skill_path)
    skill_content = skill_path.read_text(encoding="utf-8")
    judge_prompt = prompt if prompt is not None else _build_prompt(skill_content)

    judgments: list[dict[str, Any]] = []
    audit_trail: list[dict[str, str]] = []
    for adapter in adapters:
        try:
            judgments.append(call_model(adapter, judge_prompt, timeout=timeout))
        except Exception as exc:  # noqa: BLE001 - any adapter failure is recorded, never crashes the run
            audit_trail.append(
                {
                    "timestamp": _now_iso(),
                    "provider": getattr(adapter, "name", repr(adapter)),
                    "error": str(exc),
                }
            )

    if not judgments:
        status = "failed"
    elif audit_trail:
        status = "partial"
    else:
        status = "complete"

    result: dict[str, Any] = {
        "skill": str(skill_path),
        "timestamp": _now_iso(),
        "judgments": judgments,
        "audit_trail": audit_trail,
        "pooled": _pool(judgments),
        "status": status,
    }

    output_path = Path(output_path)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
