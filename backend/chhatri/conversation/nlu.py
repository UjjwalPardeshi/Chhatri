"""Optional LLM NLU (SPEC §13.2). Accept only valid enum values; fall back to rules on any error."""

from __future__ import annotations

from chhatri.conversation.intents import Intent, classify
from chhatri.integrations.base import ChatModel, IntegrationError


async def classify_with_llm(
    text: str, chat: ChatModel | None = None
) -> Intent:
    """Classify user input using optional LLM NLU, with rule-based fallback.

    If chat is None or any error occurs (invalid response, timeout, API error),
    falls back to deterministic rules-based classification.

    Args:
        text: User input text
        chat: ChatModel instance (optional)

    Returns:
        Intent enum value
    """
    if chat is None:
        # No LLM available, use rules
        return classify(text)

    # Try LLM classification
    try:
        schema = {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "enum": [
                        "WHY_AMOUNT",
                        "DISPUTE_AMOUNT",
                        "REPORT_ILLNESS",
                        "BUY_COVER",
                        "COVER_STATUS",
                        "GREETING",
                        "AFFIRM",
                        "DENY",
                        "UNKNOWN",
                    ],
                }
            },
            "required": ["intent"],
        }

        result = await chat.complete_json(
            system="You are a merchant intent classifier for an insurance app. Classify the merchant's message into one of the provided intents. Be accurate and concise.",
            user=f"Classify this merchant message: {text}",
            schema=schema,
            schema_name="MerchantIntent",
        )

        # Validate response structure
        if not isinstance(result, dict):
            raise ValueError("LLM response is not a dict")

        intent_str = result.get("intent")
        if not isinstance(intent_str, str):
            raise ValueError("intent field is not a string")

        # Only accept valid enum values
        try:
            return Intent(intent_str)
        except ValueError:
            # Invalid intent value, fall back to rules
            return classify(text)

    except IntegrationError:
        # LLM API error (timeout, unavailable, etc.) → fall back to rules
        return classify(text)
    except Exception:
        # Any other error (validation, parsing, etc.) → fall back to rules
        return classify(text)
