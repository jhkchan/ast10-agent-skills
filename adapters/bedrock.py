"""adapters/bedrock.py — AWS Bedrock provider adapter (plan.md T-2.1).

Verified models (build-notes.md "Judge / target model matrix — VERIFIED
LIVE", region us-west-2, 2026-08-21):

    gpt-oss-120b   openai.gpt-oss-120b-1:0          reasoning model — the
                                                     text block follows a
                                                     leading reasoningContent
                                                     block, not the first one
    qwen3-235b     qwen.qwen3-235b-a22b-2507-v1:0
    deepseek-v3.2  deepseek.v3.2
    nova-pro       us.amazon.nova-pro-v1:0          the `us.` inference
                                                     profile prefix is
                                                     REQUIRED — the bare
                                                     model id fails
                                                     on-demand invocation

`anthropic.*` on Bedrock is GEO-BLOCKED from this environment
(ValidationException: "not allowed from unsupported countries") and is
declared unavailable in config/audit.yml rather than implemented here
(spec.md S-004; plan.md T-2.1 reconciliation).
"""

from __future__ import annotations

from adapters.base import AdapterError, AdapterStatus, ProviderAdapter, TokenUsage

REGION = "us-west-2"

# name -> Bedrock model id, exactly as verified in build-notes.md. The
# `us.` prefix on nova-pro is load-bearing, not stylistic.
MODELS: dict[str, str] = {
    "gpt-oss-120b": "openai.gpt-oss-120b-1:0",
    "qwen3-235b": "qwen.qwen3-235b-a22b-2507-v1:0",
    "deepseek-v3.2": "deepseek.v3.2",
    "nova-pro": "us.amazon.nova-pro-v1:0",
}


def _as_int(value: object) -> int | None:
    """Coerce a reported token count, or None if the field was absent/unusable.

    A usage field that is missing and one that is zero are different facts; a
    field that is a string the API was not documented to send is a third. None
    keeps all three from collapsing into a plausible-looking integer.
    """
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class BedrockAdapter(ProviderAdapter):
    """One Bedrock on-demand model, invoked via boto3's bedrock-runtime
    `converse` API. `model` must be a key of MODELS."""

    def __init__(self, model: str, region: str = REGION) -> None:
        if model not in MODELS:
            raise ValueError(f"unknown bedrock model {model!r}; choose one of {sorted(MODELS)}")
        self.model = model
        self.model_id = MODELS[model]
        self.region = region
        self.name = f"bedrock/{model}"

    def _get_credentials(self):
        """Isolated so tests can stub credential resolution without
        touching real AWS config or the network (boto3 imported lazily so
        a missing boto3 install degrades this one adapter, not the whole
        `adapters` package)."""
        import boto3

        return boto3.Session().get_credentials()

    def check_availability(self) -> AdapterStatus:
        try:
            creds = self._get_credentials()
        except ImportError:
            return AdapterStatus(self.name, available=False, reason="boto3 is not installed")
        if creds is None:
            return AdapterStatus(self.name, available=False, reason="no AWS credentials configured")
        return AdapterStatus(self.name, available=True)

    def judge(self, prompt: str) -> str:
        import boto3

        # Cleared FIRST, before anything can fail: `last_usage` must never
        # survive from a previous call and be read as this call's cost
        # (adapters/base.py, ProviderAdapter.last_usage).
        self.last_usage = None
        client = boto3.client("bedrock-runtime", region_name=self.region)
        try:
            response = client.converse(
                modelId=self.model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
            )
        except Exception as exc:  # boto3 raises botocore.exceptions.ClientError et al.
            raise AdapterError(f"{self.name}: {exc}") from exc

        # `converse` reports token usage per call. It was discarded until
        # eval/skill_evals.py needed a real per-run total_tokens; recorded
        # here rather than re-derived by a tokenizer guess downstream.
        usage = response.get("usage") or {}
        if usage:
            self.last_usage = TokenUsage(
                input_tokens=_as_int(usage.get("inputTokens")),
                output_tokens=_as_int(usage.get("outputTokens")),
                total_tokens=_as_int(usage.get("totalTokens")),
                source=f"bedrock converse usage ({self.model_id})",
            )

        blocks = response.get("output", {}).get("message", {}).get("content", [])
        # Reasoning models (gpt-oss-120b) place the answer AFTER a leading
        # reasoningContent block (build-notes.md) — take the first block
        # that actually carries `text` rather than assuming index 0.
        for block in blocks:
            if "text" in block:
                return block["text"]
        raise AdapterError(f"{self.name}: no text content block in response")
