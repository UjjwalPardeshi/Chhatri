"""Plumbing shared by the Gemini adapters (ADR 0003 rule 7, fs-05 section 10.4).

One call is `POST {base}/models/{model}:generateContent` over httpx, built on the same retry module as every other
live client: timeouts, retries only on HTTP 429 and 5xx with the SPEC §14 backoff, and `IntegrationError`s whose
messages hold a status code or an exception type name, never a provider body. The key travels in the
`x-goog-api-key` header and nowhere else, never in a URL (as in `scripts/check_keys.py`), and is never logged.
The model id comes from the environment and is echoed in the H26 label; no model is named in the code.

Structured output. The request asks for JSON (`responseMimeType`) shaped by the caller's schema (`responseJsonSchema`,
cut down to the keywords Gemini supports) with thinking switched off, so a short answer is fast and the output
budget is not spent on thoughts. The reply is always checked against the caller's full schema, whatever the API
enforced. The structured-output fields are the one part of the request that cannot be tried without a key: if the API
answers HTTP 400 the same call is sent once more with the schema in the prompt and without those fields, and the
adapter keeps using that shape. A second 400 is a plain error (a rejected key, for one).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

import httpx
from jsonschema import validators

from chhatri.ai.errors import InvalidReply
from chhatri.integrations.retry import (
    DEFAULT_RETRY,
    DEFAULT_TIMEOUT_S,
    HTTP_CLIENT_ERROR_MIN,
    HttpStatusError,
    RetryPolicy,
    Sleep,
    http_request,
    json_object,
)

logger = logging.getLogger(__name__)

GEMINI_BASE_URL: Final = "https://generativelanguage.googleapis.com/v1beta"
API_KEY_HEADER: Final = "x-goog-api-key"
JSON_MIME_TYPE: Final = "application/json"
DEFAULT_MAX_OUTPUT_TOKENS: Final = (
    2048  # a Hindi and English answer is several hundred tokens; thinking is off
)
DEFAULT_TEMPERATURE: Final = 0.1  # as the Sarvam chat adapter (SPEC §14.1)
INTERACTIVE_POLICY: Final = RetryPolicy(
    max_attempts=1
)  # fs-05 section 10.4: one attempt per link on interactive paths
HTTP_BAD_REQUEST: Final = HTTP_CLIENT_ERROR_MIN
PROMPT_ONLY_NOTE: Final = (
    "Reply with one JSON object and nothing else. It must validate against this JSON Schema:"
)
CLEAN_FINISH: Final = "STOP"

_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_FINISH_WORD = re.compile(r"^[A-Z_]{3,40}$")
_FENCE = re.compile(r"^```[A-Za-z0-9_-]*[ \t]*\n?(.*?)\n?```$", re.DOTALL)
# The JSON Schema keywords `responseJsonSchema` supports. Everything else (maxLength, pattern, default, $schema ...)
# is left out of the request and enforced on the reply instead.
_SCHEMA_KEYWORDS: Final = frozenset(
    {
        "type",
        "title",
        "description",
        "enum",
        "items",
        "prefixItems",
        "minItems",
        "maxItems",
        "minimum",
        "maximum",
        "anyOf",
        "oneOf",
        "properties",
        "additionalProperties",
        "required",
        "propertyOrdering",
        "$ref",
        "$defs",
    }
)
_NAMED_SCHEMAS: Final = frozenset({"properties", "$defs"})  # a mapping of name to schema
_SCHEMA_LISTS: Final = frozenset({"anyOf", "oneOf", "prefixItems"})


def sanitize_schema(schema: Any) -> Any:
    """A copy of `schema` that holds only the keywords Gemini's `responseJsonSchema` supports."""
    if not isinstance(schema, Mapping):
        return schema
    return {key: _sanitize_value(key, value) for key, value in schema.items() if key in _SCHEMA_KEYWORDS}


def _sanitize_value(key: str, value: Any) -> Any:
    if key in _NAMED_SCHEMAS and isinstance(value, Mapping):
        return {name: sanitize_schema(sub) for name, sub in value.items()}
    if key in _SCHEMA_LISTS and isinstance(value, list | tuple):
        return [sanitize_schema(sub) for sub in value]
    if key in ("items", "additionalProperties"):
        return sanitize_schema(value)
    return list(value) if isinstance(value, list | tuple) else value


def clean_model_id(model: str) -> str:
    """A model id as the API names it, or a ValueError for text that is not one (it goes into a URL path)."""
    cleaned = model.strip().removeprefix("models/").strip()
    if not cleaned:
        raise ValueError("model id is required for live Gemini")
    if not _MODEL_ID.fullmatch(cleaned):
        raise ValueError("model id has characters a Gemini model name never has")
    return cleaned


def reply_text(data: Mapping[str, Any], *, integration: str) -> str:
    """The answer text of a `generateContent` response, or `InvalidReply` (blocked, cut off, empty, no candidate)."""
    feedback = data.get("promptFeedback")
    if isinstance(feedback, Mapping) and feedback.get("blockReason"):
        raise InvalidReply(integration, "the prompt was blocked by the provider")
    candidates = data.get("candidates")
    candidate = candidates[0] if isinstance(candidates, list) and candidates else None
    if not isinstance(candidate, Mapping):
        raise InvalidReply(integration, "response had no candidates")
    finish = candidate.get("finishReason")
    if isinstance(finish, str) and finish != CLEAN_FINISH:
        word = finish if _FINISH_WORD.fullmatch(finish) else "OTHER"
        raise InvalidReply(integration, f"reply did not finish ({word})")
    content = candidate.get("content")
    parts = content.get("parts") if isinstance(content, Mapping) else None
    texts = [
        part["text"]
        for part in (parts if isinstance(parts, list) else [])
        if isinstance(part, Mapping) and isinstance(part.get("text"), str) and not part.get("thought")
    ]
    text = "".join(texts)
    if not text.strip():
        raise InvalidReply(integration, "empty model reply")
    return text


def parse_json_text(text: str, schema: Mapping[str, Any], *, integration: str) -> dict[str, Any]:
    """Decode the reply (a code fence is tolerated) and validate it against the caller's full `schema`."""
    stripped = text.strip()
    fenced = _FENCE.match(stripped)
    try:
        data = json.loads(fenced.group(1) if fenced else stripped)
    except json.JSONDecodeError as exc:
        raise InvalidReply(integration, "model reply was not JSON") from exc
    if not isinstance(data, dict):
        raise InvalidReply(integration, "model reply was not a JSON object")
    validator = validators.validator_for(schema)(schema)
    if next(iter(validator.iter_errors(data)), None) is not None:
        raise InvalidReply(integration, "model reply did not match the schema")
    return data


class GeminiCaller:
    """One adapter's connection to `generateContent`: auth, bounds, retries and the two request shapes."""

    def __init__(
        self,
        integration: str,
        api_key: str,
        model: str,
        *,
        max_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        thinking_budget: int | None = 0,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        base_url: str = GEMINI_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
        policy: RetryPolicy = DEFAULT_RETRY,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for live Gemini")
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        if not base_url.startswith("https://"):
            raise ValueError("base_url must be https")
        self.model = clean_model_id(model)
        self._integration = integration
        self._key = api_key
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._thinking_budget = thinking_budget
        self._timeout_s = timeout_s
        self._url = f"{base_url.rstrip('/')}/models/{self.model}:generateContent"
        self._transport = transport
        self._policy = policy
        self._sleep = sleep
        self._prompt_only = False

    async def json_text(
        self, system: str, parts: Sequence[Mapping[str, Any]], schema: Mapping[str, Any]
    ) -> str:
        """The model's JSON text for `parts`: schema-constrained when the API accepts that, else prompt-only."""
        data: Mapping[str, Any] | None = None
        if not self._prompt_only:
            try:
                data = await self._post(self._body(system, parts, schema, constrained=True))
            except HttpStatusError as exc:
                if exc.status != HTTP_BAD_REQUEST:
                    raise
                logger.info(
                    "%s: HTTP 400 for the structured request; sending the schema in the prompt",
                    self._integration,
                )
        if data is None:
            data = await self._post(self._body(system, parts, schema, constrained=False))
            self._prompt_only = True
        return reply_text(data, integration=self._integration)

    def _body(
        self, system: str, parts: Sequence[Mapping[str, Any]], schema: Mapping[str, Any], *, constrained: bool
    ) -> dict[str, Any]:
        config: dict[str, Any] = {
            "temperature": self._temperature,
            "maxOutputTokens": self._max_tokens,
            "responseMimeType": JSON_MIME_TYPE,
        }
        instruction = system
        if constrained:
            config["responseJsonSchema"] = sanitize_schema(schema)
            if self._thinking_budget is not None:
                config["thinkingConfig"] = {"thinkingBudget": self._thinking_budget}
        else:
            instruction = (
                f"{system}\n\n{PROMPT_ONLY_NOTE}\n{json.dumps(schema, default=dict, ensure_ascii=False)}"
            )
        return {
            "systemInstruction": {"parts": [{"text": instruction}]},
            "contents": [{"role": "user", "parts": list(parts)}],
            "generationConfig": config,
        }

    async def _post(self, body: Mapping[str, Any]) -> Mapping[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout_s, transport=self._transport) as client:
            response = await http_request(
                client,
                "POST",
                self._url,
                integration=self._integration,
                policy=self._policy,
                sleep=self._sleep,
                json=body,
                headers={API_KEY_HEADER: self._key},
            )
        return json_object(response, integration=self._integration)
