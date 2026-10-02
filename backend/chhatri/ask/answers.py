"""The rules answer known intents (fs-05 section 4, step 5): catalogue text filled with engine facts, no model.

The handlers are the BUILT ones of `conversation.replies`, returning text instead of sending a message. The two that
write (DISPUTE_AMOUNT opens a case, BUY_COVER makes a quote and a payment link) run only because the word lists matched
the text, never because a model chose them. A paid decision older than today is explained with the date-neutral
EXPLAIN_AREA_FORMULA or EXPLAIN_PERSONAL, because EXPLAIN_AREA says "today".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Final

from chhatri.clock import IST
from chhatri.conversation.cover_text import NO_LIVE_COVER, cover_status_line
from chhatri.conversation.intents import Intent
from chhatri.conversation.messages import bilingual, date_en, date_hi, render
from chhatri.conversation.ports import ClaimsPort, ConversationStore
from chhatri.conversation.replies import explanation_message
from chhatri.domain.enums import CoverQuoteOutcome
from chhatri.domain.models import Decision, Merchant
from chhatri.money import format_inr

logger = logging.getLogger(__name__)

__all__ = ["RuleAnswer", "answer_intent"]

_AREA_CLAUSES: Final = ("C4.1", "C2")
_PERSONAL_CLAUSES: Final = ("C4.1", "C3")
_AREA_FACTS: Final = ("decision.latest.expected_day", "decision.latest.drop_pct", "decision.latest.share_pct")
_PERSONAL_FACTS: Final = ("decision.latest.expected_day", "decision.latest.share_pct", "decision.latest.days")
_COVER_FACTS: Final = ("cover.status", "cover.starts_on")


@dataclass(frozen=True, slots=True)
class RuleAnswer:
    """Lines as `(hindi or None, english)`, the clauses and fact keys they rest on, and what happened."""

    lines: tuple[tuple[str | None, str], ...]
    clause_ids: tuple[str, ...] = ()
    fact_keys: tuple[str, ...] = ()
    case_id: str | None = None
    case_opened: bool = False
    check_in_open: bool = False
    decision: Decision | None = None

    @property
    def answer_hi(self) -> str:
        return "\n".join(hi if hi is not None else en for hi, en in self.lines)

    @property
    def answer_en(self) -> str:
        return "\n".join(en for _, en in self.lines)


def _pair(key: str, **facts: object) -> tuple[str | None, str]:
    hindi, english = bilingual(key, **facts)
    return hindi, english


def _help() -> RuleAnswer:
    return RuleAnswer((_pair("FALLBACK_HELP"),))


def _decided_today(decision: Decision, today: date) -> bool:
    return decision.decided_at.astimezone(IST).date() == today


def _why(claims: ClaimsPort, merchant: Merchant, today: date) -> RuleAnswer:
    decision = claims.latest_paid_decision(merchant.id)
    if decision is None or decision.explanation is None:
        return _help()
    explanation = decision.explanation
    area = explanation.drop_pct is not None
    if _decided_today(decision, today):
        out = explanation_message(explanation)
        line = (out.text_hi, out.text_en or "")
    else:
        formula = {"formula_hi": explanation.formula_hi, "formula_en": explanation.formula_en}
        line = _pair("EXPLAIN_AREA_FORMULA" if area else "EXPLAIN_PERSONAL", **formula)
    return RuleAnswer(
        (line,),
        clause_ids=_AREA_CLAUSES if area else _PERSONAL_CLAUSES,
        fact_keys=_AREA_FACTS if area else _PERSONAL_FACTS,
        decision=decision,
    )


async def _dispute(claims: ClaimsPort, merchant: Merchant, text: str) -> RuleAnswer:
    outcome = await claims.open_dispute(merchant.id, text)
    case = outcome.case
    if case is None:
        return RuleAnswer((_pair("DISPUTE_NO_PAYOUT"),), clause_ids=("C9",))
    if case.merchant_id != merchant.id:
        raise ValueError(f"dispute case {case.id} belongs to {case.merchant_id}, not {merchant.id}")
    first = _pair("DISPUTE_ALREADY_OPEN", case_id=case.id) if outcome.already_open else _pair("DISPUTE_ACK")
    chip = (None, render("CASE_CHIP", "en", case_id=case.id))
    return RuleAnswer((first, chip), clause_ids=("C9",), case_id=case.id, case_opened=True)


def _illness(claims: ClaimsPort, merchant: Merchant) -> RuleAnswer:
    open_silence = claims.open_silence(merchant.id) is not None
    key = "ASK_SLIP" if open_silence else "ILLNESS_NO_SILENCE"
    return RuleAnswer((_pair(key),), clause_ids=("C3",), check_in_open=open_silence)


async def _buy_cover(claims: ClaimsPort, merchant: Merchant) -> RuleAnswer:
    quote, payment = await claims.quote_cover(merchant.id)
    if quote.merchant_id != merchant.id:
        raise ValueError(f"quote {quote.id} is for {quote.merchant_id}, not {merchant.id}")
    lines: list[tuple[str | None, str]] = []
    if quote.outcome is CoverQuoteOutcome.BLOCKED:
        key = "COVER_BLOCKED_NOW" if quote.blocking_alert_in_force else "COVER_BLOCKED"
        lines.append(_pair(key, starts_on_hi=date_hi(quote.starts_on), starts_on_en=date_en(quote.starts_on)))
    if payment is not None and payment.link_url:
        lines.append(
            _pair(
                "COVER_LINK",
                first_payment=format_inr(quote.first_payment_paise),
                per_day=format_inr(quote.premium_per_day_paise),
                url=payment.link_url,
            )
        )
    else:
        logger.warning("ask: no premium link for quote %s; told the merchant", quote.id)
        lines.append(_pair("COVER_LINK_UNAVAILABLE"))
    return RuleAnswer(tuple(lines), clause_ids=("C5", "C6"))


async def _cover_status(
    claims: ClaimsPort, store: ConversationStore, merchant: Merchant, today: date
) -> RuleAnswer:
    key, facts = cover_status_line(store.cover(merchant.id), today)
    if key == NO_LIVE_COVER:
        return await _buy_cover(claims, merchant)
    return RuleAnswer((_pair(key, **facts),), clause_ids=("C5",), fact_keys=_COVER_FACTS)


def _checkin(claims: ClaimsPort, merchant: Merchant, key: str) -> RuleAnswer:
    if claims.open_silence(merchant.id) is None:
        return _help()
    return RuleAnswer((_pair(key),), clause_ids=("C3",), check_in_open=True)


async def answer_intent(
    intent: Intent,
    *,
    merchant: Merchant,
    text: str,
    claims: ClaimsPort,
    store: ConversationStore,
    today: date,
) -> RuleAnswer:
    """The catalogue answer of a known intent (GREETING and UNKNOWN get FALLBACK_HELP)."""
    if intent is Intent.WHY_AMOUNT:
        return _why(claims, merchant, today)
    if intent is Intent.DISPUTE_AMOUNT:
        return await _dispute(claims, merchant, text)
    if intent is Intent.REPORT_ILLNESS:
        return _illness(claims, merchant)
    if intent is Intent.BUY_COVER:
        return await _buy_cover(claims, merchant)
    if intent is Intent.COVER_STATUS:
        return await _cover_status(claims, store, merchant, today)
    if intent is Intent.AFFIRM:
        return _checkin(claims, merchant, "CHECKIN_OK")
    if intent is Intent.DENY:
        return _checkin(claims, merchant, "CHECKIN_WHAT_HAPPENED")
    return _help()
