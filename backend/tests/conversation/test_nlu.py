"""Tests for optional LLM NLU (SPEC §13.2). Falls back to rules on any error."""

import pytest

from chhatri.conversation.intents import Intent
from chhatri.conversation.nlu import classify_with_llm
from chhatri.integrations.base import ChatModel, IntegrationError


class FakeChatModel(ChatModel):
    """Fake chat model for testing."""

    def __init__(self, response: dict | None = None, error: str | None = None):
        self.response = response
        self.error = error

    async def complete_json(
        self, system: str, user: str, schema: dict, *, schema_name: str
    ) -> dict:
        if self.error:
            raise IntegrationError("fake_chat", self.error)
        if self.response is None:
            raise ValueError("No response configured")
        return self.response


@pytest.mark.asyncio
async def test_classify_with_llm_success():
    """LLM returns a valid intent."""
    chat = FakeChatModel(response={"intent": "WHY_AMOUNT"})
    result = await classify_with_llm("why did I get only this", chat)
    assert result == Intent.WHY_AMOUNT


@pytest.mark.asyncio
async def test_classify_with_llm_valid_enum_values():
    """LLM returns valid enum value."""
    for intent_value in [
        "WHY_AMOUNT",
        "DISPUTE_AMOUNT",
        "REPORT_ILLNESS",
        "BUY_COVER",
        "COVER_STATUS",
        "GREETING",
        "AFFIRM",
        "DENY",
        "UNKNOWN",
    ]:
        chat = FakeChatModel(response={"intent": intent_value})
        result = await classify_with_llm("test text", chat)
        assert result == Intent(intent_value)


@pytest.mark.asyncio
async def test_classify_with_llm_invalid_intent_fallback():
    """LLM returns invalid intent → fall back to rules."""
    # Fallback should return UNKNOWN or use rules
    chat = FakeChatModel(response={"intent": "INVALID_INTENT"})
    result = await classify_with_llm("test text", chat)
    # Should not raise, should fall back gracefully
    assert isinstance(result, Intent)


@pytest.mark.asyncio
async def test_classify_with_llm_error_fallback():
    """LLM error → fall back to rules."""
    chat = FakeChatModel(error="API timeout")
    result = await classify_with_llm(
        "मुझे इतने ही पैसे क्यों मिले?", chat
    )
    # Should fall back to rules and get WHY_AMOUNT
    assert result == Intent.WHY_AMOUNT


@pytest.mark.asyncio
async def test_classify_with_llm_none_chat():
    """chat=None → use rules only."""
    result = await classify_with_llm(
        "मुझे इतने ही पैसे क्यों मिले?", None
    )
    # Should fall back to rules
    assert result == Intent.WHY_AMOUNT
