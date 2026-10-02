"""Loan instalments after a payout: the lender decides the EDI holiday (SPEC §10, §24.3; fs-03; ADR 0006).

``request_holiday`` (X4, flag ``x4_lender_request``) *asks* the merchant's lender to move the instalment due the
day after the event date to the end of the tenure. Chhatri checks its own preconditions first and then makes one
attempt:

| id | condition                                           | when not met                                  |
|----|-----------------------------------------------------|-----------------------------------------------|
| G1 | the decision is APPROVED (and the merchant's own)   | ``ValueError``                                |
| G3 | the merchant has a loan on record                   | nothing happens                               |
| G4 | no request yet for this loan and instalment date    | nothing happens (one request per instalment)  |
| G2 | the payout of the decision is CREDITED              | no request; the skip is audited               |

The lender answers by its own pre-agreed rule (`integrations/lender.py`). A grant creates the `InstalmentPause`;
a refusal or no answer in time creates none and never touches the payout. One attempt, no retry, a time limit
that is a setting: a late grant must never contradict a message that already said "not paused". Any error, an
answer to another request or silence is "not granted". Audit: ``instalment.holiday_request``,
``instalment.holiday_decision`` and, only on a grant, ``instalment.pause``; a G2 skip writes
``instalment.holiday_skipped``. The entries hold ids, codes and counts: no claim kind, reason or slip data.

``pause_next`` is the BUILT unconditional pause that serves the path with the flag off. Its lender is always
"Simulated lender (NBFC partner)" (SPEC §0.1, §10).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Final

from chhatri.audit.log import AuditLog
from chhatri.clock import require_aware
from chhatri.domain.enums import DecisionOutcome, HolidayStatus, PayoutStatus
from chhatri.domain.models import Decision, HolidayRequest, InstalmentPause, Loan, Payout
from chhatri.ids import IdFactory
from chhatri.integrations.base import IntegrationError, Lender, LenderAnswer, LenderRequest
from chhatri.money import format_inr
from chhatri.store.repositories import Store

logger = logging.getLogger(__name__)

LENDER: Final = "Simulated lender (NBFC partner)"
ACTOR: Final = "workflow:payout"
NEXT_DAY: Final = timedelta(days=1)
DEFAULT_LENDER_TIMEOUT_S: Final = (
    10.0  # fs-03 section 7.4 proposes 10 s: a target to tune (CHHATRI_LENDER_TIMEOUT_SECONDS)
)
SKIP_PAYOUT_NOT_CREDITED: Final = "PAYOUT_NOT_CREDITED"


@dataclass(frozen=True, slots=True)
class HolidayOutcome:
    """What one holiday step produced: the request in its final state, and the pause when the lender granted."""

    request: HolidayRequest
    pause: InstalmentPause | None


class InstalmentService:
    """Pause tomorrow's loan instalment after an approved payout (SPEC §10), or ask the lender to (X4)."""

    def __init__(
        self,
        store: Store,
        audit: AuditLog,
        ids: IdFactory,
        *,
        lender: Lender | None = None,
        timeout_seconds: float = DEFAULT_LENDER_TIMEOUT_S,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("the lender time limit must be positive")
        self._store = store
        self._audit = audit
        self._ids = ids
        self._lender = lender
        self._timeout_seconds = timeout_seconds

    # ------------------------------------------------------------------ X4: the lender decides

    async def request_holiday(
        self, merchant_id: str, event_date: date, decision: Decision, at: datetime
    ) -> HolidayOutcome | None:
        """Ask the lender to pause the instalment due on event_date + 1 day; None when a guard says nothing to do."""
        if self._lender is None:
            raise RuntimeError("request_holiday needs a lender; the service was built without one")
        at = require_aware(at)
        self._check_decision(merchant_id, decision)
        loan = self._store.city.loans.get(merchant_id)
        if loan is None:
            logger.debug("no loan for merchant %s; no holiday to request", merchant_id)
            return None
        due = event_date + NEXT_DAY
        if any(
            r.loan_id == loan.id and r.instalment_date == due
            for r in self._store.holiday_requests(merchant_id)
        ):
            logger.debug("holiday for %s on %s already requested", loan.id, due)
            return None
        payout = self._store.payout_for_decision(decision.id)
        if payout is None or payout.status is not PayoutStatus.CREDITED or payout.credited_at is None:
            self._audit_skip(merchant_id, decision, payout, at)
            return None
        request = self._open(loan, decision, payout, due, at)
        decided = await self._decide(request, loan, payout, at)
        pause = self._pause_on_grant(decided, loan, decision, event_date, at)
        return HolidayOutcome(decided, pause)

    def _open(
        self, loan: Loan, decision: Decision, payout: Payout, due: date, at: datetime
    ) -> HolidayRequest:
        request = HolidayRequest(
            id=self._ids.next("holiday"),
            merchant_id=loan.merchant_id,
            loan_id=loan.id,
            decision_id=decision.id,
            payout_id=payout.id,
            instalment_date=due,
            instalment_paise=loan.daily_instalment_paise,
            requested_at=at,
            status=HolidayStatus.REQUESTED,
        )
        self._store.add_holiday_request(request)
        self._audit.append(
            at=at,
            actor=ACTOR,
            action="instalment.holiday_request",
            subject_type="holiday_request",
            subject_id=request.id,
            data={
                "merchant_id": request.merchant_id,
                "loan_id": loan.id,
                "decision_id": decision.id,
                "payout_id": payout.id,
                "instalment_date": due.isoformat(),
                "amount_paise": request.instalment_paise,
                "lender": loan.lender_name,
            },
        )
        return request

    async def _decide(
        self, request: HolidayRequest, loan: Loan, payout: Payout, at: datetime
    ) -> HolidayRequest:
        """One attempt at the lender; the request in its final state, recorded and audited."""
        answer = await self._ask(request, payout)
        if answer is None:
            final = request.model_copy(update={"status": HolidayStatus.NO_RESPONSE, "decided_at": at})
        else:
            final = request.model_copy(
                update={"status": answer.decision, "reason_code": answer.reason_code, "decided_at": at}
            )
        self._store.replace_holiday_request(final)
        self._audit.append(
            at=at,
            actor=ACTOR,
            action="instalment.holiday_decision",
            subject_type="holiday_request",
            subject_id=final.id,
            data={
                "merchant_id": final.merchant_id,
                "loan_id": loan.id,
                "decision": final.status.value,
                "reason_code": final.reason_code.value if final.reason_code is not None else None,
                "moved_to": answer.moved_to if answer is not None else None,
                "penalty_paise": answer.penalty_paise if answer is not None else 0,
                "lender": answer.lender if answer is not None else loan.lender_name,
            },
        )
        return final

    async def _ask(self, request: HolidayRequest, payout: Payout) -> LenderAnswer | None:
        """The lender's answer, or None for every kind of silence (never an assumed grant)."""
        assert self._lender is not None and payout.credited_at is not None  # noqa: S101 - narrowed by the caller
        asked = LenderRequest(
            request_id=request.id,
            merchant_id=request.merchant_id,
            loan_id=request.loan_id,
            decision_id=request.decision_id,
            payout_id=payout.id,
            payout_credited_at=payout.credited_at,
            instalment_date=request.instalment_date,
            instalment_paise=request.instalment_paise,
            requested_at=request.requested_at,
        )
        try:
            answer = await asyncio.wait_for(
                self._lender.request_holiday(asked), timeout=self._timeout_seconds
            )
        except TimeoutError:
            logger.warning(
                "lender gave no answer to %s within %s s; recorded as NO_RESPONSE",
                request.id,
                self._timeout_seconds,
            )
            return None
        except IntegrationError as exc:
            logger.warning(
                "lender gave no answer to %s (%s); recorded as NO_RESPONSE", request.id, exc.safe_message
            )
            return None
        except Exception:
            logger.exception("lender failed on %s; recorded as NO_RESPONSE", request.id)
            return None
        if (answer.request_id, answer.loan_id) != (request.id, request.loan_id):
            logger.error("lender answered %s for %s; recorded as NO_RESPONSE", answer.request_id, request.id)
            return None
        return answer

    def _pause_on_grant(
        self, request: HolidayRequest, loan: Loan, decision: Decision, event_date: date, at: datetime
    ) -> InstalmentPause | None:
        if request.status is not HolidayStatus.GRANTED:
            return None
        pause = InstalmentPause(
            id=self._ids.next("pause"),
            loan_id=loan.id,
            merchant_id=request.merchant_id,
            instalment_date=request.instalment_date,
            amount_paise=request.instalment_paise,
            reason=(
                f"Lender granted holiday {request.id} after Chhatri payout {decision.id} for {event_date.isoformat()}: "
                f"{format_inr(request.instalment_paise)} instalment moved to the end of the tenure, "
                f"no penalty ({loan.lender_name})"
            ),
            decision_id=decision.id,
            created_at=at,
            request_id=request.id,
        )
        self._store.add_pause(pause)
        self._audit_pause(pause, loan, at, request_id=request.id)
        return pause

    def _audit_skip(self, merchant_id: str, decision: Decision, payout: Payout | None, at: datetime) -> None:
        self._audit.append(
            at=at,
            actor=ACTOR,
            action="instalment.holiday_skipped",
            subject_type="decision",
            subject_id=decision.id,
            data={
                "merchant_id": merchant_id,
                "decision_id": decision.id,
                "reason": SKIP_PAYOUT_NOT_CREDITED,
                "payout_status": payout.status.value if payout is not None else None,
            },
        )

    # ------------------------------------------------------------------ BUILT: the unconditional pause

    def pause_next(
        self, merchant_id: str, event_date: date, decision: Decision, at: datetime
    ) -> InstalmentPause | None:
        """Pause the instalment due on event_date + 1 day; None without a loan or when already paused."""
        at = require_aware(at)
        self._check_decision(merchant_id, decision)
        loan = self._store.city.loans.get(merchant_id)
        if loan is None:
            logger.debug("no loan for merchant %s; nothing to pause", merchant_id)
            return None
        due = event_date + NEXT_DAY
        if any(p.loan_id == loan.id and p.instalment_date == due for p in self._store.pauses(merchant_id)):
            logger.debug("instalment of %s on %s already paused", loan.id, due)
            return None
        pause = InstalmentPause(
            id=self._ids.next("pause"),
            loan_id=loan.id,
            merchant_id=merchant_id,
            instalment_date=due,
            amount_paise=loan.daily_instalment_paise,
            reason=(
                f"Chhatri payout {decision.id} for {event_date.isoformat()}: {format_inr(loan.daily_instalment_paise)} "
                f"instalment moved to the end of the tenure, no penalty ({LENDER})"
            ),
            decision_id=decision.id,
            created_at=at,
        )
        self._store.add_pause(pause)
        self._audit_pause(pause, loan, at, request_id=None)
        return pause

    # ------------------------------------------------------------------ shared

    @staticmethod
    def _check_decision(merchant_id: str, decision: Decision) -> None:
        """G1: only an APPROVED decision of that merchant leads to a pause or a request."""
        if decision.merchant_id != merchant_id:
            raise ValueError(f"decision {decision.id} is for {decision.merchant_id}, not {merchant_id}")
        if decision.outcome is not DecisionOutcome.APPROVED:
            raise ValueError(f"decision {decision.id} is {decision.outcome}; only APPROVED payouts pause")

    def _audit_pause(
        self, pause: InstalmentPause, loan: Loan, at: datetime, *, request_id: str | None
    ) -> None:
        # The BUILT entry is unchanged (the lender is the simulated one); a grant adds `request_id` (fs-03 §13).
        extra = {} if request_id is None else {"request_id": request_id}
        self._audit.append(
            at=at,
            actor=ACTOR,
            action="instalment.pause",
            subject_type="instalment_pause",
            subject_id=pause.id,
            data={
                "merchant_id": pause.merchant_id,
                "loan_id": loan.id,
                "lender": LENDER if request_id is None else loan.lender_name,
                "instalment_date": pause.instalment_date.isoformat(),
                "amount_paise": pause.amount_paise,
                "decision_id": pause.decision_id,
                "moved_to": "end of tenure",
                "penalty_paise": 0,
                **extra,
            },
        )
