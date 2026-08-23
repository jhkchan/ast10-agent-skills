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
from collections.abc import Sequence

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
AUDIT_PATH = ROOT / "config" / "audit.yml"


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


class ProviderAdapter(abc.ABC):
    """One judge-matrix provider seam. Concrete adapters own exactly one
    provider's transport and never see the rubric or scoring pipeline —
    that lives in the harness built on top of this interface (plan.md
    T-2.3, `call_model`/`run_judge`)."""

    name: str

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


def record_failure(provider: str, error: str, path: pathlib.Path = AUDIT_PATH) -> dict:
    """Append a mid-round failure entry (spec.md S-008: "an audit-trail
    entry (timestamp, provider name, error message)"). The judgment itself
    is excluded from the pool by the caller (call_adapter); this only
    records why."""
    if not error.strip():
        raise ValueError("record_failure requires a non-empty error message")
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "provider": provider,
        "status": "failed",
        "reason": error,
    }
    return _append_runtime_entry(entry, path)


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
