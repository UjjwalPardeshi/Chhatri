"""Replies to a classified merchant message (SPEC §13.5, §13.6).

- WHY_AMOUNT → EXPLAIN_AREA from the merchant's latest paid decision when it was decided today
  (§13.5 "If no payout today: FALLBACK_HELP"). EXPLAIN_AREA says "half", so a share other than 50 %
  uses the §9.6 formula (EXPLAIN_AREA_FORMULA); a personal payout uses EXPLAIN_PERSONAL (formula).
- DISPUTE_AMOUNT → ``open_dispute`` → DISPUTE_ACK → CASE_CHIP (deck test EXPLAINED: the numbers were
  shown and a human review is opened; the first case after a load is C-2291).
- REPORT_ILLNESS → ASK_SLIP while a silence check-in is open, else ILLNESS_NO_SILENCE.
- BUY_COVER → ``quote_cover`` → COVER_BLOCKED (when blocked) + COVER_LINK; when no link could be
  created (logged) COVER_LINK_UNAVAILABLE instead of the link (deck test BLOCKED).
- COVER_STATUS → the merchant's cover (active / starts on / premium unpaid); without a current cover
  it is a purchase question and follows BUY_COVER.
- AFFIRM / DENY answer the silence check-in ("सब ठीक है?") while it is open; GREETING, UNKNOWN and
  an AFFIRM/DENY with no open check-in → FALLBACK_HELP.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Final

from chhatri.clock import IST
from chhatri.conversation.intents import Intent
from chhatri.conversation.messages import date_en, date_hi, render
from chhatri.conversation.outbox import Outbox, Outgoing
from chhatri.conversation.ports import ClaimsPort, ConversationStore
from chhatri.domain.enums import CoverQuoteOutcome, CoverStatus, MessageKind
from chhatri.domain.models import Explanation, Merchant, Message
from chhatri.money import format_inr

logger = logging.getLogger(__name__)

HALF_SHARE_PCT: Final = 50
NOT_YET_STARTED: Final = frozenset({CoverStatus.WAITING, CoverStatus.PENDING_PAYMENT})

Handler = Callable[[Merchant, str], Awaitable[tuple[Message, ...]]]


def explanation_message(explanation: Explanation) -> Outgoing:
    """EXPLAIN_AREA (deck wording) or the §9.6 formula for personal / non-half payouts."""
    formula = {"formula_hi": explanation.formula_hi, "formula_en": explanation.formula_en}
    if explanation.drop_pct is None:
        return Outgoing.text("EXPLAIN_PERSONAL", **formula)
    if explanation.share_pct != HALF_SHARE_PCT:
        return Outgoing.text("EXPLAIN_AREA_FORMULA", **formula)
    return Outgoing.text(
        "EXPLAIN_AREA",
        weekday_hi=explanation.weekday_hi,
        weekday_en=explanation.weekday_en,
        expected=format_inr(explanation.expected_day_paise),
        drop=explanation.drop_pct,
    )


def case_chip(case_id: str) -> Outgoing:
    """ "Sent to a claims officer · case C-2291" (English only, not voiced)."""
    return Outgoing(
        key="CASE_CHIP",
        kind=MessageKind.CASE_CHIP,
        text_hi=None,
        text_en=render("CASE_CHIP", "en", case_id=case_id),
        case_id=case_id,
        voiced=False,
    )


class Replies:
    """Intent → §13.5 flow."""

    def __init__(self, *, outbox: Outbox, claims: ClaimsPort, store: ConversationStore) -> None:
        self._outbox = outbox
        self._claims = claims
        self._store = store
        self._handlers: Mapping[Intent, Handler] = MappingProxyType(
            {
                Intent.WHY_AMOUNT: self._why,
                Intent.DISPUTE_AMOUNT: self._dispute,
                Intent.REPORT_ILLNESS: self._illness,
                Intent.BUY_COVER: self._buy_cover,
                Intent.COVER_STATUS: self._cover_status,
                Intent.GREETING: self._fallback,
                Intent.AFFIRM: self._affirm,
                Intent.DENY: self._deny,
                Intent.UNKNOWN: self._fallback,
            }
        )

    async def respond(self, merchant: Merchant, intent: Intent, text: str) -> tuple[Message, ...]:
        return await self._handlers[intent](merchant, text)

    async def send(self, merchant: Merchant, *outgoing: Outgoing) -> tuple[Message, ...]:
        return tuple([await self._outbox.send(merchant, out) for out in outgoing])

    def _today(self, moment: datetime) -> bool:
        return moment.astimezone(IST).date() == self._outbox.now().astimezone(IST).date()

    async def _fallback(self, merchant: Merchant, text: str) -> tuple[Message, ...]:
        return await self.send(merchant, Outgoing.text("FALLBACK_HELP"))

    async def _why(self, merchant: Merchant, text: str) -> tuple[Message, ...]:
        decision = self._claims.latest_paid_decision(merchant.id)
        if decision is None or decision.explanation is None or not self._today(decision.decided_at):
            return await self._fallback(merchant, text)
        return await self.send(merchant, explanation_message(decision.explanation))

    async def _dispute(self, merchant: Merchant, text: str) -> tuple[Message, ...]:
        case = await self._claims.open_dispute(merchant.id, text)
        if case.merchant_id != merchant.id:
            raise ValueError(f"dispute case {case.id} belongs to {case.merchant_id}, not {merchant.id}")
        return await self.send(merchant, Outgoing.text("DISPUTE_ACK"), case_chip(case.id))

    async def _illness(self, merchant: Merchant, text: str) -> tuple[Message, ...]:
        open_silence = self._claims.open_silence(merchant.id) is not None
        return await self.send(merchant, Outgoing.text("ASK_SLIP" if open_silence else "ILLNESS_NO_SILENCE"))

    async def _affirm(self, merchant: Merchant, text: str) -> tuple[Message, ...]:
        if self._claims.open_silence(merchant.id) is None:
            return await self._fallback(merchant, text)
        return await self.send(merchant, Outgoing.text("CHECKIN_OK"))

    async def _deny(self, merchant: Merchant, text: str) -> tuple[Message, ...]:
        if self._claims.open_silence(merchant.id) is None:
            return await self._fallback(merchant, text)
        return await self.send(merchant, Outgoing.text("CHECKIN_WHAT_HAPPENED"))

    async def _buy_cover(self, merchant: Merchant, text: str) -> tuple[Message, ...]:
        quote, payment = await self._claims.quote_cover(merchant.id)
        if quote.merchant_id != merchant.id:
            raise ValueError(f"quote {quote.id} is for {quote.merchant_id}, not {merchant.id}")
        outgoing: list[Outgoing] = []
        if quote.outcome is CoverQuoteOutcome.BLOCKED:
            starts = quote.starts_on
            outgoing.append(
                Outgoing.text("COVER_BLOCKED", starts_on_hi=date_hi(starts), starts_on_en=date_en(starts))
            )
        if payment is not None and payment.link_url:
            outgoing.append(
                Outgoing.text(
                    "COVER_LINK",
                    first_payment=format_inr(quote.first_payment_paise),
                    per_day=format_inr(quote.premium_per_day_paise),
                    url=payment.link_url,
                )
            )
        else:
            logger.warning("conversation: no premium link for quote %s; told the merchant", quote.id)
            outgoing.append(Outgoing.text("COVER_LINK_UNAVAILABLE"))
        return await self.send(merchant, *outgoing)

    async def _cover_status(self, merchant: Merchant, text: str) -> tuple[Message, ...]:
        cover = self._store.cover(merchant.id)
        today = self._outbox.now().astimezone(IST).date()
        if cover is None or cover.status not in NOT_YET_STARTED | {CoverStatus.ACTIVE}:
            return await self._buy_cover(merchant, text)
        if cover.status in NOT_YET_STARTED or cover.starts_on > today:
            starts = cover.starts_on
            reply = Outgoing.text(
                "COVER_STATUS_STARTS", starts_on_hi=date_hi(starts), starts_on_en=date_en(starts)
            )
        elif cover.prepaid_through is None or cover.prepaid_through < today:
            reply = Outgoing.text("COVER_STATUS_UNPAID")
        else:
            paid = cover.prepaid_through
            reply = Outgoing.text("COVER_STATUS_ACTIVE", prepaid_hi=date_hi(paid), prepaid_en=date_en(paid))
        return await self.send(merchant, reply)
