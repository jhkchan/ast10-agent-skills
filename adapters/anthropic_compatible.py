"""adapters/anthropic_compatible.py — Anthropic-Messages-compatible HTTP
provider adapter (plan.md T-2.1: GLM `glm-5.2` via z.ai).

Verified route (build-notes.md, 2026-08-21):
    POST https://api.z.ai/api/anthropic/v1/messages
    header: x-api-key: $ZAI_API_KEY

The z.ai OpenAI-compatible path (`/api/paas/v4`) returns "Insufficient
balance" and must not be used — declared unavailable in config/audit.yml
instead (spec.md S-004).
"""

from __future__ import annotations

import os

from adapters.base import AdapterError, AdapterStatus, ProviderAdapter, TokenUsage

ZAI_BASE_URL = "https://api.z.ai/api/anthropic"
ZAI_API_KEY_ENV = "ZAI_API_KEY"
DEFAULT_MODEL = "glm-5.2"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TIMEOUT_S = 120
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicCompatibleAdapter(ProviderAdapter):
    """One Anthropic-Messages-compatible endpoint. Constructed with an
    explicit `api_key` so callers/tests never have to mutate os.environ;
    `from_env()` is the convenience constructor that reads ZAI_API_KEY."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str = ZAI_BASE_URL,
        timeout_s: int = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.timeout_s = timeout_s
        self.name = f"anthropic-compatible/{model}"

    @classmethod
    def from_env(cls, model: str = DEFAULT_MODEL) -> AnthropicCompatibleAdapter:
        return cls(model=model, api_key=os.environ.get(ZAI_API_KEY_ENV))

    def check_availability(self) -> AdapterStatus:
        if not self.api_key:
            return AdapterStatus(self.name, available=False, reason=f"{ZAI_API_KEY_ENV} unset")
        return AdapterStatus(self.name, available=True)

    def judge(self, prompt: str) -> str:
        import requests

        # See adapters/base.py, ProviderAdapter.last_usage: cleared before the
        # call so a previous call's count can never be read as this one's.
        self.last_usage = None

        try:
            response = requests.post(
                f"{self.base_url}/v1/messages",
                headers={"x-api-key": self.api_key or "", "anthropic-version": ANTHROPIC_VERSION},
                json={
                    "model": self.model,
                    "max_tokens": DEFAULT_MAX_TOKENS,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=self.timeout_s,
            )
        except requests.RequestException as exc:
            raise AdapterError(f"{self.name}: request failed: {exc}") from exc

        if response.status_code != 200:
            raise AdapterError(f"{self.name}: HTTP {response.status_code}: {response.text[:500]}")

        payload = response.json()
        # The Anthropic Messages shape reports input/output tokens but no
        # total; TokenUsage.from_pair sums them only when both are present,
        # so a half-reported call stays half-reported.
        usage = payload.get("usage") or {}
        if usage:
            self.last_usage = TokenUsage.from_pair(
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                source=f"anthropic-messages usage ({self.model})",
            )
        for block in payload.get("content", []):
            if block.get("type") == "text":
                return block["text"]
        raise AdapterError(f"{self.name}: no text content block in response")
