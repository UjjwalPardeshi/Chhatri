"""Flow handlers for ConversationService (SPEC §13.5).

Extracted from service.py to keep service.py under 800 lines.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from chhatri.conversation.messages import bilingual, render
from chhatri.domain.enums import Direction
from chhatri.domain.models import Merchant, Message

if TYPE_CHECKING:
    from chhatri.conversation.service import ConversationService


async def handle_why_amount(
    service: ConversationService, merchant: Merchant, now: datetime
) -> list[Message]:
    """WHY_AMOUNT flow: show explanation (SPEC §13.5)."""
    latest = service.claims.latest_paid_decision(merchant.id)
    if latest is None:
        return await send_fallback_help(service, merchant, now)

    # EXPLAIN_AREA with decision facts
    if latest.explanation:
        exp = latest.explanation
        from chhatri.money import format_inr
        hi_text, en_text = bilingual(
            "EXPLAIN_AREA",
            weekday_hi=exp.weekday_hi,
            weekday_en=exp.weekday_en,
            expected=format_inr(exp.expected_day_paise),
            drop=exp.drop_pct or 0,
        )
    else:
        return await send_fallback_help(service, merchant, now)

    msg = await service._send_message(merchant, hi_text, en_text, now)
    return [msg]


async def handle_dispute(
    service: ConversationService, merchant: Merchant, text: str, now: datetime
) -> list[Message]:
    """DISPUTE_AMOUNT flow: open case (SPEC §13.5)."""
    from chhatri.domain.enums import MessageKind

    case = await service.claims.open_dispute(merchant.id, text)

    messages = []

    # DISPUTE_ACK
    hi_text, en_text = bilingual("DISPUTE_ACK")
    ack_msg = await service._send_message(
        merchant,
        hi_text,
        en_text,
        now,
    )
    messages.append(ack_msg)

    # CASE_CHIP
    chip_msg = Message(
        id=service.ids.next("message"),
        merchant_id=merchant.id,
        direction=Direction.OUTBOUND,
        channel=service.channel_name,
        kind=MessageKind.CASE_CHIP,
        text_en=render("CASE_CHIP", "en", case_id=case.id),
        created_at=now,
    )
    service.store.add_message(chip_msg)
    service.audit.append(
        at=now,
        actor="ai-agent",
        action="message_outbound",
        subject_type="message",
        subject_id=chip_msg.id,
        data={"kind": "case_chip", "case_id": case.id},
    )
    messages.append(chip_msg)

    # Publish case event
    service.bus.publish(
        "case",
        now,
        {"case": case.model_dump(mode="json")},
    )

    return messages


async def handle_report_illness(
    service: ConversationService, merchant: Merchant, now: datetime
) -> list[Message]:
    """REPORT_ILLNESS flow: check if outreach is open, ask for slip (SPEC §13.5)."""
    silence = service.claims.open_silence(merchant.id)
    if silence is None:
        # No outreach open, send fallback
        return await send_fallback_help(service, merchant, now)

    # ASK_SLIP
    hi_text, en_text = bilingual("ASK_SLIP")
    msg = await service._send_message(merchant, hi_text, en_text, now)
    return [msg]


async def handle_buy_cover(
    service: ConversationService, merchant: Merchant, now: datetime
) -> list[Message]:
    """BUY_COVER flow: get quote, send link or blocked (SPEC §13.5)."""
    from chhatri.money import format_inr

    quote, payment = await service.claims.quote_cover(merchant.id)

    messages = []

    if quote.outcome.value == "BLOCKED":
        # COVER_BLOCKED
        hi_text, en_text = bilingual(
            "COVER_BLOCKED",
            starts_on_hi=service._format_date_hi(quote.starts_on),
            starts_on_en=service._format_date_en(quote.starts_on),
        )
        msg = await service._send_message(
            merchant,
            hi_text,
            en_text,
            now,
        )
        messages.append(msg)
    else:
        # COVER_LINK
        hi_text, en_text = bilingual(
            "COVER_LINK",
            first_payment=format_inr(quote.first_payment_paise),
            per_day=format_inr(quote.premium_per_day_paise),
            url=payment.link_url or "https://paytm.me/chhatri",
        )
        msg = await service._send_message(
            merchant,
            hi_text,
            en_text,
            now,
        )
        messages.append(msg)

    return messages


async def handle_cover_status(
    service: ConversationService, merchant: Merchant, now: datetime
) -> list[Message]:
    """COVER_STATUS flow: provide information (SPEC §13.5)."""
    # For now, use fallback help as no specific COVER_STATUS template
    return await send_fallback_help(service, merchant, now)


async def handle_acknowledge(
    service: ConversationService,
    merchant: Merchant,
    intent,
    now: datetime,
) -> list[Message]:
    """Handle GREETING, AFFIRM, DENY (SPEC §13.5)."""
    from chhatri.conversation.intents import Intent

    if intent == Intent.GREETING:
        hi_text = "नमस्ते! मैं छतरी हूँ।"
        en_text = "Hello! I'm Chhatri."
    elif intent == Intent.AFFIRM:
        hi_text = "ठीक है!"
        en_text = "Great!"
    else:  # DENY
        hi_text = "समझा।"
        en_text = "Okay."

    msg = await service._send_message(merchant, hi_text, en_text, now)
    return [msg]


async def send_fallback_help(
    service: ConversationService, merchant: Merchant, now: datetime
) -> list[Message]:
    """Send FALLBACK_HELP (SPEC §13.5)."""
    hi_text, en_text = bilingual("FALLBACK_HELP")
    msg = await service._send_message(merchant, hi_text, en_text, now)
    return [msg]
