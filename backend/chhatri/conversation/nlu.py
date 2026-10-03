"""Intent detection with an optional language model (SPEC §13.2).

The deterministic rules (``intents.classify``) run first and win whenever they recognise the text,
so every deck utterance behaves identically with live Sarvam and with the simulator (the three live
tests of §13.6 never depend on a model's mood). Only text the rules call UNKNOWN is sent to the
chat model (``sarvam-105b``, JSON-schema response) when one is configured. Its answer is accepted
only when it is exactly one of the ``Intent`` values; on any error or invalid answer the rules'
UNKNOWN stands and a warning is logged (the merchant's text is never logged). Tests use rules only.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, Literal, Protocol

from chhatri.ai.chain import ChainResult, Rejection
from chhatri.ai.labels import AiLabel, FallbackReason
from chhatri.conversation.intents import Intent, classify
from chhatri.integrations.base import ChatModel

logger = logging.getLogger(__name__)

SCHEMA_NAME: Final = "merchant_intent"
MAX_PROMPT_CHARS: Final = 500
INTENT_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "description": "The merchant's intent.",
            "enum": [intent.value for intent in Intent],
        }
    },
    "required": ["intent"],
    "additionalProperties": False,
}
SYSTEM_PROMPT: Final = (
    "You classify one WhatsApp message from an Indian shop owner (Hindi, Hinglish or English) who has "
    "Paytm income cover. Answer with one intent: WHY_AMOUNT (asks why the payout was this amount), "
    "DISPUTE_AMOUNT (says the loss was bigger or the payout is wrong), REPORT_ILLNESS (owner or family "
    "is ill, injured or in hospital), BUY_COVER (wants to buy cover), COVER_STATUS (asks about their "
    "cover), GREETING, AFFIRM (yes/ok), DENY (no), UNKNOWN (anything else). Never answer anything else."
)

Source = Literal["rules", "llm"]


@dataclass(frozen=True, slots=True)
class IntentResult:
    """The detected intent and who decided it (audited as ``intent.detected``)."""

    intent: Intent
    source: Source
    label: AiLabel | None = None  # the H26 label of a model-classified intent (None when the rules decided)


def _parse(result: object) -> Intent:
    if not isinstance(result, dict):
        raise ValueError("response is not an object")
    value = result.get("intent")
    if not isinstance(value, str) or value not in Intent.__members__:
        raise ValueError("response intent is not one of the intents")
    return Intent(value)


async def detect_intent(text: str, chat: ChatModel | None) -> IntentResult:
    """Rules first; the chat model only for UNKNOWN text; rules again on any model error."""
    ruled = classify(text)
    if ruled is not Intent.UNKNOWN or chat is None:
        return IntentResult(ruled, "rules")
    try:
        answer = await chat.complete_json(
            SYSTEM_PROMPT,
            f"Merchant message: {text[:MAX_PROMPT_CHARS]}",
            INTENT_SCHEMA,
            schema_name=SCHEMA_NAME,
        )
        return IntentResult(_parse(answer), "llm")
    except Exception as exc:  # SPEC §13.2: on ANY error fall back to the rules
        logger.warning("nlu: chat model unusable (%s); falling back to rules", type(exc).__name__)
        return IntentResult(ruled, "rules")


INTENT_TIMEOUT_S: Final = 6.0


class IntentChain(Protocol):
    """The Ask chat chain (Gemini, then Sarvam): `integrations.chat_chain` satisfies it."""

    async def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        schema_name: str,
        timeout_s: float,
        accept: Callable[[dict[str, Any]], Rejection | None] | None = None,
    ) -> ChainResult[dict[str, Any]]: ...


def _accept(answer: dict[str, Any]) -> Rejection | None:
    try:
        _parse(answer)
    except ValueError:
        return Rejection(FallbackReason.INVALID_REPLY)
    return None


async def detect_intent_chain(text: str, chain: IntentChain | None) -> IntentResult:
    """Rules first; for UNKNOWN text the Gemini-then-Sarvam chain, labelled; rules again when no link answers.

    Only a LIVE or FALLBACK answer from a real model is "llm"; the label says which provider and model decided.
    """
    ruled = classify(text)
    if ruled is not Intent.UNKNOWN or chain is None:
        return IntentResult(ruled, "rules")
    try:
        result = await chain.complete_json(
            SYSTEM_PROMPT,
            f"Merchant message: {text[:MAX_PROMPT_CHARS]}",
            INTENT_SCHEMA,
            schema_name=SCHEMA_NAME,
            timeout_s=INTENT_TIMEOUT_S,
            accept=_accept,
        )
        if result.value is None:
            return IntentResult(ruled, "rules", result.label)
        return IntentResult(_parse(result.value), "llm", result.label)
    # the chain never raises for a provider failure; anything else falls back to the rules
    except Exception as exc:
        logger.warning("nlu: intent chain unusable (%s); falling back to rules", type(exc).__name__)
        return IntentResult(ruled, "rules")
