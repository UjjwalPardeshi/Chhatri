"""Optional LLM NLU (SPEC §13.2): rules first, LLM only for UNKNOWN, rules on any error."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from chhatri.conversation.intents import Intent
from chhatri.conversation.nlu import INTENT_SCHEMA, IntentResult, detect_intent
from chhatri.integrations.base import IntegrationError


class FakeChat:
    def __init__(self, result: Any = None, error: BaseException | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[str, str, dict[str, Any], str]] = []

    async def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, schema_name: str
    ) -> dict[str, Any]:
        self.calls.append((system, user, schema, schema_name))
        if self.error is not None:
            raise self.error
        return self.result


async def test_rules_only_without_chat() -> None:
    assert await detect_intent("मेरा नुकसान ज़्यादा हुआ।", None) == IntentResult(Intent.DISPUTE_AMOUNT, "rules")
    assert await detect_intent("gibberish words", None) == IntentResult(Intent.UNKNOWN, "rules")


async def test_rules_win_for_known_utterances_and_chat_is_not_called() -> None:
    chat = FakeChat({"intent": "GREETING"})
    result = await detect_intent("Red alert tomorrow. Cover me today.", chat)
    assert result == IntentResult(Intent.BUY_COVER, "rules")
    assert chat.calls == []


async def test_llm_extends_unknown_text() -> None:
    chat = FakeChat({"intent": "REPORT_ILLNESS"})
    result = await detect_intent("my leg is broken, can't open the shop", chat)
    assert result == IntentResult(Intent.REPORT_ILLNESS, "llm")
    system, user, schema, name = chat.calls[0]
    assert schema is INTENT_SCHEMA
    assert name == "merchant_intent"
    assert "my leg is broken" in user
    assert "WHY_AMOUNT" in system


def test_schema_enumerates_exactly_the_intents() -> None:
    assert INTENT_SCHEMA["properties"]["intent"]["enum"] == [i.value for i in Intent]
    assert INTENT_SCHEMA["required"] == ["intent"]


@pytest.mark.parametrize(
    "result",
    [
        {"intent": "APPROVE_PAYMENT"},
        {"intent": "why_amount"},
        {"intent": 3},
        {},
        ["WHY_AMOUNT"],
        None,
    ],
)
async def test_invalid_llm_output_falls_back_to_rules(result: Any, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    outcome = await detect_intent("something unclear", FakeChat(result))
    assert outcome == IntentResult(Intent.UNKNOWN, "rules")
    assert "falling back to rules" in caplog.text


@pytest.mark.parametrize(
    "error",
    [
        IntegrationError("sarvam_chat", "timeout", retryable=True),
        ValueError("bad json"),
        RuntimeError("boom"),
    ],
)
async def test_llm_errors_fall_back_to_rules(error: BaseException, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    outcome = await detect_intent("something unclear", FakeChat(error=error))
    assert outcome == IntentResult(Intent.UNKNOWN, "rules")
    assert "falling back to rules" in caplog.text


async def test_llm_unknown_is_accepted_as_unknown() -> None:
    assert await detect_intent("something unclear", FakeChat({"intent": "UNKNOWN"})) == IntentResult(
        Intent.UNKNOWN, "llm"
    )
