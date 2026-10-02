"""Live Gemini chat with JSON-schema output (ADR 0003 rule 7, fs-05 section 10.4, task N2.1).

Implements the BUILT `ChatModel` protocol exactly as `LiveSarvamChat` does: the reply must be a JSON object that
validates against the requested schema, anything else raises `IntegrationError` so that the chain tries the next
link and a template answers last. The model never sets money (ADR 0001): callers accept only closed fields and
validated text. The model id comes from `GEMINI_MODEL` and is echoed in the label.

The prompt is the caller's: `system` becomes the system instruction and `user` the single user turn. The model gets no
tools, no retrieval and no write access (H16). Untrusted text goes in through `chhatri.ai.untrusted.wrap_untrusted`.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from chhatri.integrations.gemini_client import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_TEMPERATURE,
    GEMINI_BASE_URL,
    GeminiCaller,
    parse_json_text,
)
from chhatri.integrations.retry import DEFAULT_RETRY, DEFAULT_TIMEOUT_S, RetryPolicy, Sleep
from chhatri.integrations.sarvam_chat import check_schema

INTEGRATION = "gemini_chat"


class LiveGeminiChat:
    """ChatModel backed by Gemini `generateContent` (ADR 0003)."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str,
        max_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        thinking_budget: int | None = 0,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        base_url: str = GEMINI_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
        policy: RetryPolicy = DEFAULT_RETRY,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._caller = GeminiCaller(
            INTEGRATION,
            api_key,
            model,
            max_tokens=max_tokens,
            temperature=temperature,
            thinking_budget=thinking_budget,
            timeout_s=timeout_s,
            base_url=base_url,
            transport=transport,
            policy=policy,
            sleep=sleep,
        )

    @property
    def model(self) -> str:
        """The configured model id, echoed in the H26 label."""
        return self._caller.model

    async def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, schema_name: str
    ) -> dict[str, Any]:
        if not schema_name.strip():
            raise ValueError("schema_name is required")
        check_schema(schema)
        text = await self._caller.json_text(system, [{"text": user}], schema)
        return parse_json_text(text, schema, integration=INTEGRATION)
