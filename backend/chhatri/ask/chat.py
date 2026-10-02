"""The chat's route to Ask Chhatri: UNKNOWN text is answered by the Ask service when `n2_ask_chhatri` is on (5.12).

Known intents behave exactly as before. The reply is one message whose `meta` carries `mode`, `provider`, `model`,
`fallback_reason`, `clauses`, `next_action` and `scam_warning`, so the phone simulator can show the label. A question
over 500 characters is answered with ASK_TOO_LONG. The service is built per call from the loaded scenario.
"""

from __future__ import annotations

from typing import Any, Final

from chhatri.ask.copy import render_pair
from chhatri.ask.types import MAX_QUESTION_CHARS, AskAnswer
from chhatri.ask.wiring import build_ask_service
from chhatri.config import Settings
from chhatri.conversation.ask_port import UnknownAnswerer, UnknownReply
from chhatri.features import is_enabled

__all__ = ["ChatAsk", "unknown_answerer"]

FEATURE: Final = "n2_ask_chhatri"


def reply_meta(answer: AskAnswer) -> dict[str, Any]:
    label = answer.label.to_wire()
    return {
        "ask_id": answer.ask_id,
        "mode": label["mode"],
        "provider": label["provider"],
        "model": label["model"],
        "fallback_reason": label["fallback_reason"],
        "clauses": [clause.id for clause in answer.clauses],
        "next_action": answer.next_action.kind,
        "scam_warning": answer.scam_warning,
    }


class ChatAsk:
    """Implements `UnknownAnswerer` over one loaded scenario `rt`."""

    def __init__(self, rt: Any, settings: Settings) -> None:
        self._rt, self._settings = rt, settings

    async def answer_unknown(self, merchant_id: str, text: str) -> UnknownReply:
        if len(text.strip()) > MAX_QUESTION_CHARS:
            hi, en = render_pair("ASK_TOO_LONG")
            meta = {
                "mode": "LIVE",
                "provider": "rules",
                "model": None,
                "fallback_reason": None,
                "clauses": [],
                "next_action": "ASK_AGAIN",
                "scam_warning": False,
            }
            return UnknownReply(hi, en, meta)
        service = build_ask_service(static=self._rt.static, runtime=self._rt, settings=self._settings)
        answer = await service.answer(merchant_id, text)
        return UnknownReply(answer.answer_hi, answer.answer_en, reply_meta(answer))


def unknown_answerer(rt: Any, settings: Settings) -> UnknownAnswerer | None:
    """The chat's Ask answerer, or None while `n2_ask_chhatri` is off."""
    return ChatAsk(rt, settings) if is_enabled(FEATURE, settings) else None
