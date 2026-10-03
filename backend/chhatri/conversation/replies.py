"""Replies to a classified merchant message (SPEC §13.5, §13.6).

- WHY_AMOUNT → EXPLAIN_AREA from the merchant's latest paid decision when it was decided today
  (§13.5 "If no payout today: FALLBACK_HELP"). EXPLAIN_AREA says "half", so a share other than 50 %
  uses the §9.6 formula (EXPLAIN_AREA_FORMULA); a personal payout uses EXPLAIN_PERSONAL (formula).
- DISPUTE_AMOUNT → ``open_dispute`` → DISPUTE_ACK → CASE_CHIP (deck test EXPLAINED: the numbers were
  shown and a human review is opened; the first case after a load is C-2291). When no decision has settled a
  claim there is nothing to dispute: DISPUTE_NO_PAYOUT and no case. A second dispute for the same decision gets
  DISPUTE_ALREADY_OPEN and the chip of the case that is still open (K5).
- REPORT_ILLNESS → ASK_SLIP while a silence check-in is open, else ILLNESS_NO_SILENCE.
- BUY_COVER → ``quote_cover`` → COVER_BLOCKED (when blocked) + COVER_LINK; when no link could be
  created (logged) COVER_LINK_UNAVAILABLE instead of the link (deck test BLOCKED).
- COVER_STATUS → the merchant's cover from its derived status (K6): COVER_STATUS_STARTS while WAITING,
  COVER_STATUS_UNPAID when the premium is due, else COVER_STATUS_ACTIVE; without a current cover it is a
  purchase question and follows BUY_COVER. BUY_COVER says COVER_BLOCKED_NOW when the blocking alert is already
  in force, COVER_BLOCKED when it starts later.
- AFFIRM / DENY answer the silence check-in ("सब ठीक है?") while it is open; GREETING, UNKNOWN and
  an AFFIRM/DENY with no open check-in → FALLBACK_HELP, or the merchant's open next step when one waits
  (``next_step``: "your slip has been read, reply yes", "our team is checking your claim", …).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Final

from chhatri.clock import IST
from chhatri.conversation.cover_text import NO_LIVE_COVER, cover_status_line
from chhatri.conversation.intents import Intent
from chhatri.conversation.messages import date_en, date_hi, render
from chhatri.conversation.outbox import Outbox, Outgoing
from chhatri.conversation.ports import ClaimsPort, ConversationStore
from chhatri.domain.enums import CoverQuoteOutcome, MessageKind
from chhatri.domain.models import Case, Explanation, Merchant, Message
from chhatri.money import format_inr

logger = logging.getLogger(__name__)

HALF_SHARE_PCT: Final = 50

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
    """ "Sent to a claims officer · case C-2291" (English only, not voiced); a phone also gets the Hindi line."""
    return Outgoing(
        key="CASE_CHIP",
        kind=MessageKind.CASE_CHIP,
        text_hi=None,
        text_en=render("CASE_CHIP", "en", case_id=case_id),
        case_id=case_id,
        voiced=False,
        wire_hi=render("CASE_CHIP_WIRE", "hi", case_id=case_id),
    )


class Replies:
    """Intent → §13.5 flow."""

    def __init__(
        self,
        *,
        outbox: Outbox,
        claims: ClaimsPort,
        store: ConversationStore,
        next_step: Callable[[str], Outgoing | None] | None = None,
    ) -> None:
        self._outbox = outbox
        self._claims = claims
        self._store = store
        self._next_step = next_step
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
        step = self._next_step(merchant.id) if self._next_step is not None else None
        return await self.send(merchant, step or Outgoing.text("FALLBACK_HELP"))

    async def _why(self, merchant: Merchant, text: str) -> tuple[Message, ...]:
        decision = self._claims.latest_paid_decision(merchant.id)
        if decision is None or decision.explanation is None or not self._today(decision.decided_at):
            return await self._fallback(merchant, text)
        return await self.send(merchant, explanation_message(decision.explanation))

    async def _dispute(self, merchant: Merchant, text: str) -> tuple[Message, ...]:
        outcome = await self._claims.open_dispute(merchant.id, text)
        case = outcome.case
        if case is None:
            return await self.send(merchant, Outgoing.text("DISPUTE_NO_PAYOUT"))
        if case.merchant_id != merchant.id:
            raise ValueError(f"dispute case {case.id} belongs to {case.merchant_id}, not {merchant.id}")
        return await self.dispute_opened(merchant, case, already_open=outcome.already_open)

    async def dispute_opened(
        self, merchant: Merchant, case: Case, *, already_open: bool
    ) -> tuple[Message, ...]:
        """DISPUTE_ACK (or DISPUTE_ALREADY_OPEN) and the case chip: the answer to a dispute, from chat or the app (N5)."""
        if already_open:
            return await self.send(
                merchant, Outgoing.text("DISPUTE_ALREADY_OPEN", case_id=case.id), case_chip(case.id)
            )
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
            key = "COVER_BLOCKED_NOW" if quote.blocking_alert_in_force else "COVER_BLOCKED"
            outgoing.append(Outgoing.text(key, starts_on_hi=date_hi(starts), starts_on_en=date_en(starts)))
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
        today = self._outbox.now().astimezone(IST).date()
        key, facts = cover_status_line(self._store.cover(merchant.id), today)
        if key == NO_LIVE_COVER:
            return await self._buy_cover(merchant, text)
        return await self.send(merchant, Outgoing.text(key, **facts))
