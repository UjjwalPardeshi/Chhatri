"""The five steps of one claim in the tracker (K5; fs-04 9.1 and 9.5, data-model-and-api 5.1).

Every step is read from what was recorded: the decisions, the payout, the lender's request (or the BUILT pause) and the
review case. Nothing is recomputed, and each reason is a catalogue line in both languages (`TRACK_*`, the formula and
reason lines the chat already uses), so the app words nothing about money itself. A claim that is REFERRED waits at
Decided; DECLINED skips Paid and the EDI holiday; a merchant with no loan skips the EDI holiday. The lender decides the
EDI holiday: its refusal code goes to the console in `reason_code`, and the merchant's text names the lender and
gives the reason in words, never the code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, Final

from chhatri.clock import IST
from chhatri.conversation.messages import bilingual, date_en, date_hi
from chhatri.conversation.reasons import declined_reason_key, officer_reason_key, referred_track_key
from chhatri.domain.enums import (
    CaseKind,
    ClaimKind,
    DecisionOutcome,
    HolidayStatus,
    PayoutStatus,
    Severity,
)
from chhatri.domain.enums import CheckStatus as Check
from chhatri.domain.models import Case, Claim, Decision, HolidayRequest, InstalmentPause, Payout
from chhatri.money import format_inr
from chhatri.replay.view_records import iso

if TYPE_CHECKING:
    from datetime import datetime

    from chhatri.replay.state import Runtime

__all__ = ["ClaimFacts", "claim_steps"]

OFFICER_PREFIX: Final = "officer:"
ONE_DAY: Final = timedelta(days=1)
Line = tuple[str, str]


@dataclass(frozen=True, slots=True)
class ClaimFacts:
    """The records the steps of one claim read."""

    rt: Runtime
    claim: Claim
    first: Decision  # what the engine decided
    effective: Decision  # what stands: an officer's decision replaces the referral it resolves
    payout: Payout | None
    case: Case | None  # the review case of a referred personal claim


def _step(
    name: str,
    status: str,
    *,
    result: str | None = None,
    at: datetime | None = None,
    line: Line | None = None,
    code: str | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "result": result,
        "at": iso(at) if at is not None else None,
        "reason_hi": line[0] if line is not None else None,
        "reason_en": line[1] if line is not None else None,
        "reason_code": code,
    }


def _dates(days: tuple[date, ...]) -> dict[str, str]:
    return {"dates_hi": ", ".join(date_hi(d) for d in days), "dates_en": ", ".join(date_en(d) for d in days)}


def detected_step(f: ClaimFacts, detected_at: datetime) -> dict[str, Any]:
    if f.claim.kind is ClaimKind.AREA:
        drop = f.claim.drop_pct if f.claim.drop_pct is not None else 0
        return _step(
            "Detected", "completed", at=detected_at, line=bilingual("TRACK_DETECTED_AREA", drop=drop)
        )
    line = bilingual("TRACK_DETECTED_PERSONAL", **_dates(f.claim.silent_dates))
    return _step("Detected", "completed", at=detected_at, line=line)


def checked_step(f: ClaimFacts) -> dict[str, Any]:
    first = f.first
    if first.outcome is DecisionOutcome.DECLINED:
        key, facts = "TRACK_CHECKED_FAILED", {}
    elif first.outcome is DecisionOutcome.REFERRED:
        key, facts = referred_track_key(first), {}
    else:
        key, facts = "TRACK_CHECKED_OK", {"passed": len(first.checks)}
    waived = [c for c in first.checks if c.severity is Severity.HARD and c.status is not Check.PASS]
    if first.outcome is DecisionOutcome.APPROVED and waived:  # an APPROVED decision has no HARD issue
        raise ValueError(f"decision {first.id} is APPROVED with a HARD check that is not PASS")
    return _step("Checked", "completed", at=first.decided_at, line=bilingual(key, **facts))


def decided_step(f: ClaimFacts) -> dict[str, Any]:
    decision = f.effective
    if decision.outcome is DecisionOutcome.REFERRED:
        return _step("Decided", "current", result="REFERRED")
    if decision.outcome is DecisionOutcome.DECLINED:
        by_officer = decision.decided_by.startswith(OFFICER_PREFIX)
        key = (
            officer_reason_key(decision, CaseKind.PERSONAL_CLAIM_REVIEW)
            if by_officer
            else declined_reason_key(decision)
        )
        return _step("Decided", "completed", result="DECLINED", at=decision.decided_at, line=bilingual(key))
    explanation = decision.explanation
    if explanation is None:
        raise ValueError(f"approved decision {decision.id} has no explanation")
    key = "EXPLAIN_PERSONAL" if explanation.drop_pct is None else "EXPLAIN_AREA_FORMULA"
    line = bilingual(key, formula_hi=explanation.formula_hi, formula_en=explanation.formula_en)
    return _step("Decided", "completed", result="APPROVED", at=decision.decided_at, line=line)


def paid_step(f: ClaimFacts) -> dict[str, Any]:
    outcome, payout = f.effective.outcome, f.payout
    if outcome is DecisionOutcome.DECLINED:
        return _step("Paid", "skipped")
    if outcome is DecisionOutcome.REFERRED or payout is None:
        return _step("Paid", "pending")
    if payout.status is PayoutStatus.CREDITED:
        return _step("Paid", "completed", at=payout.credited_at, line=bilingual("PAYOUT_CARD"))
    if payout.status is PayoutStatus.FAILED:
        return _step("Paid", "current", line=bilingual("TRACK_PAID_FAILED"))
    minutes = f.rt.static.rules.payout_rail_delay_minutes
    return _step("Paid", "current", line=bilingual("TRACK_PAID_ETA", minutes=minutes))


def _lender_answer(rt: Runtime, decision: Decision) -> tuple[HolidayRequest | None, InstalmentPause | None]:
    """The lender's request for this decision (flag on), else the BUILT unconditional pause (flag off)."""
    requests = [r for r in rt.store.holiday_requests(decision.merchant_id) if r.decision_id == decision.id]
    if requests:
        return requests[-1], None
    pauses = [p for p in rt.store.pauses(decision.merchant_id) if p.decision_id == decision.id]
    return None, (pauses[-1] if pauses else None)


def _granted_line(keys: tuple[str, str, str], due: date, answered: datetime, paise: int) -> Line:
    """Tomorrow's, today's or a dated instalment, as the chat says it (the date of the answer decides)."""
    tomorrow, today, dated = keys
    answered_on, instalment = answered.astimezone(IST).date(), format_inr(paise)
    if due == answered_on + ONE_DAY:
        return bilingual(tomorrow, instalment=instalment)
    if due == answered_on:
        return bilingual(today, instalment=instalment)
    return bilingual(dated, instalment=instalment, date_hi=date_hi(due), date_en=date_en(due))


HOLIDAY_KEYS: Final = ("HOLIDAY_GRANTED", "HOLIDAY_GRANTED_TODAY", "HOLIDAY_GRANTED_ON")
PAUSE_KEYS: Final = ("INSTALMENT_PAUSED", "INSTALMENT_PAUSED_TODAY", "INSTALMENT_PAUSED_ON")


def _request_step(request: HolidayRequest) -> dict[str, Any]:
    if request.status is HolidayStatus.REQUESTED:
        return _step("EDI holiday", "current", line=bilingual("TRACK_EDI_REQUESTED"))
    answered = request.decided_at or request.requested_at
    if request.status is HolidayStatus.GRANTED:
        line = _granted_line(HOLIDAY_KEYS, request.instalment_date, answered, request.instalment_paise)
        return _step("EDI holiday", "completed", result="GRANTED", at=answered, line=line)
    if request.status is HolidayStatus.NO_RESPONSE:
        line = bilingual("TRACK_EDI_NO_RESPONSE")
        return _step("EDI holiday", "completed", result="NO_RESPONSE", at=answered, line=line)
    code = request.reason_code.value if request.reason_code is not None else None
    refused, why = bilingual("TRACK_EDI_REFUSED"), bilingual("TRACK_EDI_REFUSED_WHY", **_reason_words(code))
    line = (f"{refused[0]} {why[0]}", f"{refused[1]} {why[1]}")
    return _step("EDI holiday", "completed", result="REFUSED", at=answered, line=line, code=code)


def _reason_words(code: str | None) -> dict[str, str]:
    if code is None:
        raise ValueError("a refused holiday request has a reason code")
    reason_hi, reason_en = bilingual(f"HOLIDAY_REASON_{code}")
    return {"reason_hi": reason_hi, "reason_en": reason_en}


def edi_step(f: ClaimFacts, paid: dict[str, Any]) -> dict[str, Any]:
    outcome = f.effective.outcome
    if outcome is DecisionOutcome.DECLINED:
        return _step("EDI holiday", "skipped")
    if outcome is DecisionOutcome.REFERRED:
        return _step("EDI holiday", "pending")
    if f.rt.static.city.loans.get(f.effective.merchant_id) is None:
        return _step("EDI holiday", "skipped", result="NO_LOAN", line=bilingual("TRACK_EDI_NONE"))
    request, pause = _lender_answer(f.rt, f.effective)
    if request is not None:
        return _request_step(request)
    if pause is not None:
        line = _granted_line(PAUSE_KEYS, pause.instalment_date, pause.created_at, pause.amount_paise)
        return _step("EDI holiday", "completed", result="GRANTED", at=pause.created_at, line=line)
    return _step("EDI holiday", "current" if paid["status"] == "completed" else "pending")


def claim_steps(f: ClaimFacts, detected_at: datetime) -> list[dict[str, Any]]:
    """Detected, Checked, Decided, Paid and EDI holiday, in that order."""
    paid = paid_step(f)
    return [detected_step(f, detected_at), checked_step(f), decided_step(f), paid, edi_step(f, paid)]
