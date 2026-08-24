"""adapters/base.py — provider-adapter interface (plan.md T-2.1).

Every judge-matrix provider (Bedrock, the local Claude CLI, an
Anthropic-Messages-compatible HTTP endpoint) implements ProviderAdapter.
The interface is deliberately thin: `check_availability()` is a pure,
no-network declare-or-skip check, and `judge()` is the one call that
crosses a process/network boundary.

Providers this repo cannot run at all (Bedrock's geo-blocked
`anthropic.*` models, DashScope with no API key, z.ai's unfunded
OpenAI-compatible path) are never coded against — they are declared
unavailable in config/audit.yml instead (spec.md: "Unavailable providers
are declared in config/audit.yml with a recorded reason, never silently
averaged as zero or dropped without record."). See static_unavailable().
"""

from __future__ import annotations

import abc
import dataclasses
import datetime
import pathlib
import re
from collections.abc import Sequence

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
AUDIT_PATH = ROOT / "config" / "audit.yml"

#: Statuses a runtime entry may carry. "failed" is a provider that raised
#: (timeout, auth, crash); "malformed" is a provider that answered but whose
#: answer would not bind (spec.md S-008 vs the justification contract in
#: scripts/judge_harness.py). They are kept distinct because "the provider was
#: down" and "the provider refused to explain its scores" are different facts
#: about a run, and a reader of config/audit.yml must be able to tell them
#: apart without reading the error string.
RECORDABLE_STATUSES = frozenset({"failed", "malformed"})

#: How many characters of a refused response are kept in the audit trail. Long
#: enough to see the shape of what came back (which keys, which dimension is
#: missing, whether it was prose instead of JSON); short enough that a run
#: which refuses ten judgments does not turn config/audit.yml into a corpus.
#: The FULL length is recorded alongside the excerpt, so a truncated record
#: says so in numbers rather than pretending it is complete.
MAX_RESPONSE_EXCERPT = 800

#: Credential shapes redacted out of a recorded response before it is written
#: to disk. A judge response should never contain one, which is exactly why a
#: response that does must not be committed verbatim into an append-only file:
#: the audit trail is the one artifact nobody re-reads before publishing.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9_\-]{12,}"), "<redacted:api-key>"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "<redacted:aws-access-key-id>"),
    (re.compile(r"ASIA[0-9A-Z]{16}"), "<redacted:aws-session-key-id>"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{20,}"), "<redacted:google-api-key>"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "<redacted:github-token>"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{12,}"), "<redacted:bearer-token>"),
    (re.compile(r"(?i)\b([A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD))\b\s*[=:]\s*\S+"), r"\1=<redacted>"),
)


def redact_secrets(text: str) -> str:
    """Blank out anything credential-shaped in `text`, naming what was removed.

    Named rather than deleted: a record that says ``<redacted:bearer-token>``
    still tells a reader what the response contained, which is the difference
    between redaction and omission.
    """
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def response_excerpt(text: str, limit: int = MAX_RESPONSE_EXCERPT) -> tuple[str, int]:
    """Return ``(excerpt, original_character_count)`` for a refused response.

    Redacted first, then truncated with an explicit marker. Never returns the
    empty string for a non-empty input, and never silently drops the tail: the
    marker names how many characters were cut, so "we kept 800 of 4,102" is
    readable off the record itself.
    """
    cleaned = redact_secrets(text)
    original = len(text)
    if len(cleaned) <= limit:
        return cleaned, original
    cut = len(cleaned) - limit
    return f"{cleaned[:limit]}… [truncated {cut} more characters]", original


class AdapterError(RuntimeError):
    """Raised by ProviderAdapter.judge() on any runtime failure (timeout,
    crash, auth failure, malformed response) — spec.md S-008: "the
    openai-compatible adapter times out and raises a RuntimeError." A
    plain RuntimeError satisfies that contract too (call_adapter() catches
    RuntimeError, not this subclass specifically); AdapterError exists so
    an adapter can raise something more specific than the bare base type.
    """


@dataclasses.dataclass(frozen=True)
class AdapterStatus:
    """Declare-or-skip result for one adapter: available, or unavailable
    with a written reason.

    spec.md S-004: the roster must list a skipped provider "as unavailable
    with the reason" — a reason is required, not optional, whenever
    available=False.
    """

    name: str
    available: bool
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.available and not self.reason.strip():
            raise ValueError(f"{self.name}: unavailable AdapterStatus requires a non-empty reason")


@dataclasses.dataclass(frozen=True)
class TokenUsage:
    """What one provider reported about the cost of one `judge()` call.

    Added for `eval/skill_evals.py`, whose contract requires a real
    `total_tokens` per run and forbids inventing one: "If a provider does not
    return a token count, record what it does return and say so rather than
    inventing a number." Bedrock's `converse` and the Anthropic-Messages
    endpoint both return a usage block that the adapters were discarding; the
    local `claude -p` print mode returns none at all. This type is how the
    three answers stay distinguishable downstream — a count, a partial count,
    or the absence of one with the reason attached.

    Every field is Optional because a partial report is a real outcome: an
    endpoint that returns input and output tokens but no total is recorded as
    exactly that, and `total_tokens` is summed from the halves only when both
    are present (see `from_pair`). `source` always names where the numbers came
    from, so a reader of a timing.json never has to guess which API said what.
    """

    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    source: str

    @classmethod
    def from_pair(cls, input_tokens: int | None, output_tokens: int | None, source: str) -> TokenUsage:
        """Usage for an endpoint that reports the two halves but no total."""
        total = None
        if input_tokens is not None and output_tokens is not None:
            total = input_tokens + output_tokens
        return cls(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total, source=source)

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


class ProviderAdapter(abc.ABC):
    """One judge-matrix provider seam. Concrete adapters own exactly one
    provider's transport and never see the rubric or scoring pipeline —
    that lives in the harness built on top of this interface (plan.md
    T-2.3, `call_model`/`run_judge`)."""

    name: str

    #: Token accounting from the MOST RECENT `judge()` call, or None when this
    #: provider reported none. Every concrete adapter must reset it to None on
    #: entry to `judge()` before doing anything else: a stale count carried
    #: over from a previous call and attributed to this one would be a
    #: fabricated measurement, which is the exact failure the field exists to
    #: avoid. Nothing in the judge matrix reads it; `eval/skill_evals.py` does.
    last_usage: TokenUsage | None = None

    @abc.abstractmethod
    def check_availability(self) -> AdapterStatus:
        """Return whether this adapter can run right now. Must never raise
        or make a network call — a credential/binary/config presence check
        only. That is what keeps declare-or-skip cheap enough to run
        before every round."""

    @abc.abstractmethod
    def judge(self, prompt: str) -> str:
        """Call the provider with `prompt`, return its raw text response.
        Raises AdapterError (a RuntimeError) on any runtime failure."""


@dataclasses.dataclass(frozen=True)
class RosterResult:
    """The pool a judge round actually runs against, split by spec.md
    S-004's declare-or-skip rule: `available` adapters run; `unavailable`
    ones are skipped and already recorded in the audit trail."""

    available: list[ProviderAdapter]
    unavailable: list[AdapterStatus]


def _load_audit(path: pathlib.Path) -> dict:
    if not path.is_file():
        return {"providers": {}, "runtime_entries": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.setdefault("providers", {})
    data.setdefault("runtime_entries", [])
    return data


def _save_audit(data: dict, path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")


def _append_runtime_entry(entry: dict, path: pathlib.Path) -> dict:
    data = _load_audit(path)
    data["runtime_entries"].append(entry)
    _save_audit(data, path)
    return entry


def record_unavailable(provider: str, reason: str, path: pathlib.Path = AUDIT_PATH) -> dict:
    """Append a runtime declare-or-skip entry (spec.md S-004): this
    provider was checked and skipped because `reason`. Append-only — never
    overwrites or removes a prior entry."""
    if not reason.strip():
        raise ValueError("record_unavailable requires a non-empty reason")
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "provider": provider,
        "status": "unavailable",
        "reason": reason,
    }
    return _append_runtime_entry(entry, path)


def record_failure(
    provider: str,
    error: str,
    path: pathlib.Path = AUDIT_PATH,
    *,
    status: str = "failed",
    skill: str | None = None,
    round_index: int | None = None,
    response: str | None = None,
) -> dict:
    """Append a mid-round failure entry (spec.md S-008: "an audit-trail
    entry (timestamp, provider name, error message)"). The judgment itself
    is excluded from the pool by the caller (call_adapter or
    scripts.judge_harness.run_judge); this is what makes the exclusion
    survive the process that made it.

    The four keyword arguments exist because "an audit-trail entry" was not
    enough to answer the only question anyone asks of a discarded judgment
    six weeks later — WHICH one was discarded. Run 5 of this repo's judge
    matrix refused 10 of 198 attempted judgments and recorded none of them
    (see eval/run5-refusals.md); the loss was total because the harness
    built its audit trail in memory and never called this function. So:

    * ``status`` — "failed" (the provider raised) or "malformed" (the
      provider answered and the answer would not bind). Restricted to
      RECORDABLE_STATUSES so a typo cannot invent a third category that
      every reader then has to guess at.
    * ``skill`` and ``round_index`` — WHICH attempt this was. A refusal
      that names only the provider cannot be matched against a scorecard's
      missing row, which is precisely the gap run 5 left. ``round_index``
      is the 1-based round number as printed by the harness.
    * ``response`` — enough of what the provider actually said to diagnose
      it, redacted and truncated by :func:`response_excerpt` and recorded
      with its original length. Never omitted when a response existed: the
      excerpt is the only copy that outlives the run.

    All four are optional so that the pre-existing callers
    (:func:`call_adapter`, which has no skill/round context) keep working
    unchanged; nothing about them is optional for the judge harness, whose
    tests assert every one of them is present.
    """
    if not error.strip():
        raise ValueError("record_failure requires a non-empty error message")
    if status not in RECORDABLE_STATUSES:
        raise ValueError(f"record_failure status must be one of {sorted(RECORDABLE_STATUSES)}, got {status!r}")
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "provider": provider,
        "status": status,
        "reason": error,
    }
    if skill is not None:
        entry["skill"] = skill
    if round_index is not None:
        entry["round"] = int(round_index)
    if response is not None:
        excerpt, original = response_excerpt(response)
        entry["response_excerpt"] = excerpt
        entry["response_chars"] = original
    return _append_runtime_entry(entry, path)


def runtime_entries(path: pathlib.Path = AUDIT_PATH) -> list[dict]:
    """Read back the append-only runtime entries recorded at `path`.

    The counterpart to record_unavailable/record_failure, and the reason it
    exists is the guard in scripts/refusal_guard.py: a record nothing reads
    is a record nobody notices the absence of.
    """
    return list(_load_audit(path).get("runtime_entries") or [])


def static_unavailable(path: pathlib.Path = AUDIT_PATH) -> list[AdapterStatus]:
    """The providers declared unavailable in config/audit.yml's static
    `providers` block — Bedrock's geo-blocked anthropic.* models, DashScope
    with no API key, z.ai's unfunded OpenAI-compatible path. These are
    never coded against (plan.md T-2.1), so there is no live adapter to
    check_availability() them; they are declared once and read back here."""
    data = _load_audit(path)
    return [
        AdapterStatus(name=key, available=False, reason=str(entry.get("reason", "")))
        for key, entry in data.get("providers", {}).items()
        if entry.get("status") == "unavailable"
    ]


def build_roster(adapters: Sequence[ProviderAdapter], audit_path: pathlib.Path = AUDIT_PATH) -> RosterResult:
    """Loop through the declared LIVE adapters (spec.md S-004: "the judge
    matrix initialization loops through declared adapters"); every
    unavailable one is skipped and recorded in config/audit.yml rather than
    silently dropped or averaged as zero. Combine with static_unavailable()
    for the full roster spec.md's four-adapter prose describes."""
    available: list[ProviderAdapter] = []
    unavailable: list[AdapterStatus] = []
    for adapter in adapters:
        status = adapter.check_availability()
        if status.available:
            available.append(adapter)
        else:
            unavailable.append(status)
            record_unavailable(status.name, status.reason, audit_path)
    return RosterResult(available=available, unavailable=unavailable)


def call_adapter(adapter: ProviderAdapter, prompt: str, audit_path: pathlib.Path = AUDIT_PATH) -> str | None:
    """Run one adapter's judge() call. A mid-round RuntimeError (spec.md
    S-008) excludes only that provider's judgment: record_failure() writes
    the audit entry and this returns None instead of propagating, so one
    crashed adapter cannot abort the whole round."""
    try:
        return adapter.judge(prompt)
    except RuntimeError as exc:
        record_failure(adapter.name, str(exc), audit_path)
        return None
