"""Business-initiated messages (SPEC §13.5, §13.7, §17.2; binding decision B2).

Called by the orchestrator's workflow steps at simulated time:
- ``area_payout`` at credit time (monsoon 17:04): AREA_PAYOUT_INTRO (template
  ``chhatri_area_payout`` outside the 24 h window) → PAYOUT_CARD (badge "No claim needed") → SOUNDBOX.
- ``instalment_paused`` at pause time (17:05): INSTALMENT_PAUSED when the paused instalment is
  tomorrow's; the illness claim for Wednesday pauses Thursday's instalment while it is paid on
  Thursday, so "today's" (INSTALMENT_PAUSED_TODAY) or a dated line (INSTALMENT_PAUSED_ON) is used
  whenever "tomorrow's" would be false.
- ``personal_paid`` at credit time: PERSONAL_PAID, or OFFICER_APPROVED when an officer's decision is
  being paid (the illness_mismatch story), then PAYOUT_CARD and SOUNDBOX.
- ``checkin_silent`` (11:20): CHECKIN_SILENT (template ``chhatri_checkin`` outside the window).
- ``officer_result`` at the officer's decision: OFFICER_DECLINED with the reason; an approval is
  told once the money is credited, by ``personal_paid`` ("… {amount} जमा" must be true when read),
  so it returns no message. A DISPUTE case (SPEC §12, §13.5) is answered without a new payout: the
  officer CLOSES it and the disputed decision stands, so the merchant gets OFFICER_DECLINED with the
  dispute reason (area numbers, or the personal daily cap) — the "24 घंटे में जवाब मिलेगा" promise
  of DISPUTE_ACK is kept.

Every money message is checked against its decision and payout (APPROVED, same merchant, same
amount, CREDITED); a mismatch raises ``ValueError`` rather than telling a merchant a wrong number.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import MappingProxyType
from typing import Final

from chhatri.clock import IST
from chhatri.conversation.messages import bilingual, date_en, date_hi, name_facts, render
from chhatri.conversation.outbox import (
    TEMPLATE_AREA_PAYOUT,
    TEMPLATE_CHECKIN,
    Outbox,
    Outgoing,
    WhatsAppTemplate,
)
from chhatri.conversation.ports import MerchantDirectory
from chhatri.conversation.reasons import dispute_reason_key, officer_reason_key
from chhatri.domain.enums import CaseKind, CaseStatus, DecisionOutcome, MessageKind, PayoutStatus
from chhatri.domain.models import AreaTrigger, Case, Decision, InstalmentPause, Merchant, Message, Payout
from chhatri.money import format_inr

OFFICER_PREFIX: Final = "officer:"
ONE_DAY: Final = timedelta(days=1)


def _require(condition: bool, problem: str) -> None:
    if not condition:
        raise ValueError(problem)


def check_paid(decision: Decision, payout: Payout) -> None:
    """A payout message may only describe a credited payout of an approved decision."""
    _require(decision.outcome is DecisionOutcome.APPROVED, f"decision {decision.id} is not APPROVED")
    _require(payout.decision_id == decision.id, f"payout {payout.id} is not for decision {decision.id}")
    _require(payout.merchant_id == decision.merchant_id, f"payout {payout.id} is for another merchant")
    _require(payout.amount_paise == decision.amount_paise, f"payout {payout.id} amount differs from decision")
    _require(payout.status is PayoutStatus.CREDITED, f"payout {payout.id} is {payout.status}, not CREDITED")


def payout_card(payout: Payout, badge_key: str) -> Outgoing:
    """PAYOUT_CARD: amount label, the §13.4 subtitle lines and the badge (not voiced)."""
    subtitle_hi, subtitle_en = bilingual("PAYOUT_CARD")
    card = MappingProxyType(
        {
            "amount_label": format_inr(payout.amount_paise),
            "subtitle_hi": subtitle_hi,
            "subtitle_en": subtitle_en,
            "badge": render(badge_key, "en"),
        }
    )
    return Outgoing(
        key="PAYOUT_CARD", kind=MessageKind.PAYOUT_CARD, text_hi=None, text_en=None, card=card, voiced=False
    )


class Notifications:
    """Messages Chhatri starts (SPEC §13.5)."""

    def __init__(self, *, outbox: Outbox, directory: MerchantDirectory) -> None:
        self._outbox = outbox
        self._directory = directory

    def _today(self) -> date:
        return self._outbox.now().astimezone(IST).date()

    async def _paid(
        self, merchant: Merchant, text: Outgoing, payout: Payout, badge_key: str
    ) -> tuple[Message, ...]:
        told = await self._outbox.send(merchant, text)
        card = await self._outbox.send(merchant, payout_card(payout, badge_key))
        return told, card, await self._outbox.announce(merchant, payout.amount_paise)

    async def area_payout(
        self, decision: Decision, payout: Payout, trigger: AreaTrigger
    ) -> tuple[Message, ...]:
        check_paid(decision, payout)
        merchant = self._directory.merchant(decision.merchant_id)
        _require(
            trigger.zone_id == merchant.zone_id, f"trigger {trigger.id} is not for zone {merchant.zone_id}"
        )
        explanation = decision.explanation
        _require(
            explanation is None or explanation.drop_pct == trigger.drop_pct,
            f"decision {decision.id} drop differs from trigger {trigger.id}",
        )
        names = name_facts(merchant)
        amount = format_inr(payout.amount_paise)
        template = WhatsAppTemplate(TEMPLATE_AREA_PAYOUT, (names["name_hi"], str(trigger.drop_pct), amount))
        intro = Outgoing.text("AREA_PAYOUT_INTRO", template=template, drop=trigger.drop_pct, **names)
        return await self._paid(merchant, intro, payout, "PAYOUT_CARD_BADGE")

    async def personal_paid(self, decision: Decision, payout: Payout) -> tuple[Message, ...]:
        check_paid(decision, payout)
        merchant = self._directory.merchant(decision.merchant_id)
        by_officer = decision.decided_by.startswith(OFFICER_PREFIX)
        key = "OFFICER_APPROVED" if by_officer else "PERSONAL_PAID"
        badge = "PAYOUT_CARD_BADGE_OFFICER" if by_officer else "PAYOUT_CARD_BADGE_PERSONAL"
        text = Outgoing.text(key, amount=format_inr(payout.amount_paise), **name_facts(merchant))
        return await self._paid(merchant, text, payout, badge)

    async def instalment_paused(self, pause: InstalmentPause) -> Message:
        merchant = self._directory.merchant(pause.merchant_id)
        instalment = format_inr(pause.amount_paise)
        today, due = self._today(), pause.instalment_date
        if due == today + ONE_DAY:
            reply = Outgoing.text("INSTALMENT_PAUSED", instalment=instalment)
        elif due == today:
            reply = Outgoing.text("INSTALMENT_PAUSED_TODAY", instalment=instalment)
        else:
            reply = Outgoing.text(
                "INSTALMENT_PAUSED_ON", instalment=instalment, date_hi=date_hi(due), date_en=date_en(due)
            )
        return await self._outbox.send(merchant, reply)

    async def checkin_silent(self, merchant_id: str, first_silent_day: date) -> Message:
        merchant = self._directory.merchant(merchant_id)
        _require(first_silent_day < self._today(), f"silent day {first_silent_day} is not in the past")
        names = name_facts(merchant)
        template = WhatsAppTemplate(TEMPLATE_CHECKIN, (names["name_hi"],))
        return await self._outbox.send(
            merchant, Outgoing.text("CHECKIN_SILENT", template=template, name_hi=names["name_hi"])
        )

    async def officer_result(self, decision: Decision, case: Case) -> tuple[Message, ...]:
        _require(
            decision.merchant_id == case.merchant_id, f"decision {decision.id} is not for case {case.id}"
        )
        if case.kind is CaseKind.DISPUTE:
            return (await self._dispute_answered(decision, case),)
        _require(
            decision.decided_by.startswith(OFFICER_PREFIX), f"decision {decision.id} is not an officer's"
        )
        if decision.outcome is DecisionOutcome.APPROVED:
            return ()
        _require(decision.outcome is DecisionOutcome.DECLINED, f"decision {decision.id} is still REFERRED")
        merchant = self._directory.merchant(decision.merchant_id)
        reason_hi, reason_en = bilingual(officer_reason_key(decision, case.kind))
        reply = Outgoing.text(
            "OFFICER_DECLINED", reason_hi=reason_hi, reason_en=reason_en, **name_facts(merchant)
        )
        return (await self._outbox.send(merchant, reply.with_case(case.id)),)

    async def _dispute_answered(self, disputed: Decision, case: Case) -> Message:
        """OFFICER_DECLINED for a CLOSED dispute: the disputed decision stands (SPEC §12, §13.5)."""
        _require(case.status is CaseStatus.CLOSED, f"dispute case {case.id} is {case.status}, not CLOSED")
        _require(
            disputed.id == case.decision_id, f"decision {disputed.id} is not the one disputed in {case.id}"
        )
        merchant = self._directory.merchant(disputed.merchant_id)
        reason_hi, reason_en = bilingual(dispute_reason_key(disputed))
        reply = Outgoing.text(
            "OFFICER_DECLINED", reason_hi=reason_hi, reason_en=reason_en, **name_facts(merchant)
        )
        return await self._outbox.send(merchant, reply.with_case(case.id))
