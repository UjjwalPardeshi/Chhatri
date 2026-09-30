"""Live Sarvam chat with JSON-schema output (SPEC §14.1, §13.2).

`client.chat.completions(model="sarvam-105b", messages=[…], temperature=0.1,
response_format={"type": "json_schema", "json_schema": {"name": …, "schema": …}}, max_tokens=…)`
→ `.choices[0].message.content` (endpoint `POST /v1/chat/completions`).

The reply must be a JSON object that validates against the requested schema; anything else raises
`IntegrationError` so that callers fall back to deterministic rules (SPEC §13.2). The model never
sets money: callers only accept enum values (§0.2).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from jsonschema import exceptions as jsonschema_exceptions
from jsonschema import validators

from chhatri.integrations.base import IntegrationError
from chhatri.integrations.retry import DEFAULT_TIMEOUT_S
from chhatri.integrations.sarvam_client import ClientFactory, SarvamCaller, default_client_factory, field_of

CHAT_TEMPERATURE = 0.1  # SPEC §14.1
CHAT_MAX_TOKENS = 512
INTEGRATION = "sarvam_chat"


def check_schema(schema: Mapping[str, Any]) -> None:
    """Reject malformed schemas before spending a model call on them."""
    validator_cls = validators.validator_for(schema)
    try:
        validator_cls.check_schema(schema)
    except jsonschema_exceptions.SchemaError as exc:
        raise ValueError("invalid JSON schema for chat completion") from exc


def parse_json_reply(content: Any, schema: Mapping[str, Any]) -> dict[str, Any]:
    """Decode the model reply and validate it against `schema`."""
    if not isinstance(content, str) or not content.strip():
        raise IntegrationError(INTEGRATION, "empty model reply")
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise IntegrationError(INTEGRATION, "model reply was not JSON") from exc
    if not isinstance(data, dict):
        raise IntegrationError(INTEGRATION, "model reply was not a JSON object")
    validator = validators.validator_for(schema)(schema)
    errors = sorted(validator.iter_errors(data), key=lambda err: list(err.absolute_path))
    if errors:
        raise IntegrationError(INTEGRATION, "model reply did not match the schema")
    return data


def first_message_content(response: Any) -> Any:
    choices = field_of(response, "choices")
    if not isinstance(choices, list | tuple) or not choices:
        raise IntegrationError(INTEGRATION, "response had no choices")
    message = field_of(choices[0], "message")
    if message is None:
        raise IntegrationError(INTEGRATION, "response had no message")
    return field_of(message, "content")


class LiveSarvamChat:
    """ChatModel backed by Sarvam chat completions (SPEC §14.1)."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "sarvam-105b",
        max_tokens: int = CHAT_MAX_TOKENS,
        caller: SarvamCaller | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for live Sarvam chat")
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        self.model = model
        self.max_tokens = max_tokens
        self._caller = caller or SarvamCaller(
            INTEGRATION, client_factory or default_client_factory(api_key, DEFAULT_TIMEOUT_S)
        )

    async def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, schema_name: str
    ) -> dict[str, Any]:
        if not schema_name.strip():
            raise ValueError("schema_name is required")
        check_schema(schema)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        response_format = {"type": "json_schema", "json_schema": {"name": schema_name, "schema": schema}}
        options = self._caller.request_options()

        def run(client: Any) -> Any:
            return client.chat.completions(
                model=self.model,
                messages=messages,
                temperature=CHAT_TEMPERATURE,
                response_format=response_format,
                max_tokens=self.max_tokens,
                request_options=options,
            )

        response = await self._caller.call(run)
        return parse_json_reply(first_message_content(response), schema)
