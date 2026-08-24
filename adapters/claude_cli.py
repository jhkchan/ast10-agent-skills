"""adapters/claude_cli.py — local Claude Code CLI provider adapter
(plan.md T-2.1: "the only working Claude-as-judge route").

build-notes.md: local `claude -p --model <id>` WORKS (Claude Code
2.1.238). Bedrock's `anthropic.*` models are geo-blocked from this
environment (see adapters/bedrock.py), so this subprocess route is the
only way to get a Claude judgment into the judge matrix.
"""

from __future__ import annotations

import shutil
import subprocess

from adapters.base import AdapterError, AdapterStatus, ProviderAdapter

DEFAULT_MODEL = "sonnet"
DEFAULT_TIMEOUT_S = 120


class ClaudeCliAdapter(ProviderAdapter):
    """Invokes the local `claude` binary in print mode:
    `claude -p --model <model> <prompt>`. There is no API key to check —
    availability is whether the binary is reachable on PATH."""

    def __init__(self, model: str = DEFAULT_MODEL, timeout_s: int = DEFAULT_TIMEOUT_S) -> None:
        self.model = model
        self.timeout_s = timeout_s
        self.name = f"claude-cli/{model}"

    def check_availability(self) -> AdapterStatus:
        if shutil.which("claude") is None:
            return AdapterStatus(self.name, available=False, reason="claude CLI not found on PATH")
        return AdapterStatus(self.name, available=True)

    def judge(self, prompt: str) -> str:
        # `claude -p` print mode emits the answer on stdout and NOTHING about
        # token cost, so `last_usage` stays None for this adapter and every
        # artifact built on it records the absence rather than a guess
        # (adapters/base.py, ProviderAdapter.last_usage). `--output-format
        # json` would carry a usage block, but it also changes stdout from the
        # answer text into an envelope — a transport change to the one route
        # that reaches Claude at all, made for a metric. Not worth it.
        self.last_usage = None
        try:
            result = subprocess.run(
                ["claude", "-p", "--model", self.model, prompt],
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdapterError(f"{self.name}: timed out after {self.timeout_s}s") from exc
        except OSError as exc:
            raise AdapterError(f"{self.name}: failed to launch claude CLI: {exc}") from exc

        if result.returncode != 0:
            raise AdapterError(f"{self.name}: exited {result.returncode}: {result.stderr.strip()}")
        return result.stdout
