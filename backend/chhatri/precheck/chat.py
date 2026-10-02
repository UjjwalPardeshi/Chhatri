"""The chat message of a pre-check (fs-02 8.3): text, a card with the fields, checklist and three actions, and the label."""

from __future__ import annotations

from typing import Any

from chhatri.conversation.messages import bilingual
from chhatri.conversation.outbox import Outgoing
from chhatri.domain.enums import MessageKind
from chhatri.precheck.model import Precheck, PrecheckStatus
from chhatri.precheck.view import card_view

SHOW_KEY = "SLIP_PRECHECK_SHOW"


def chat_outgoing(pc: Precheck, *, minimum: float) -> Outgoing:
    """READY says "please check it"; every other status says its guidance, in both languages."""
    key = SHOW_KEY if pc.status is PrecheckStatus.READY else (pc.guidance_key or SHOW_KEY)
    hi, en = bilingual(key)
    wire = pc.label.to_wire()
    meta: dict[str, Any] = {
        "precheck_id": pc.id,
        "precheck_status": pc.status.value,
        "mode": wire["mode"],
        "provider": wire["provider"],
        "model": wire["model"],
        "fallback_reason": wire["fallback_reason"],
    }
    return Outgoing(
        key=key,
        kind=MessageKind.TEXT,
        text_hi=hi,
        text_en=en,
        card=card_view(pc, minimum=minimum),
        meta=meta,
    )
