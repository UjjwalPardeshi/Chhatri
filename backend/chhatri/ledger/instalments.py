"""Loan instalment pause with the simulated lender (SPEC §10, §24.3; binding decision B2).

After a payout, the instalment due the day after the event date is paused: it moves to the end of
the tenure with no penalty. Nothing happens (None) when the merchant has no loan or that instalment
is already paused. The lender is always "Simulated lender (NBFC partner)" (SPEC §0.1, §10).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Final

from chhatri.audit.log import AuditLog
from chhatri.clock import require_aware
from chhatri.domain.enums import DecisionOutcome
from chhatri.domain.models import Decision, InstalmentPause
from chhatri.ids import IdFactory
from chhatri.money import format_inr
from chhatri.store.repositories import Store

logger = logging.getLogger(__name__)

LENDER: Final = "Simulated lender (NBFC partner)"
ACTOR: Final = "workflow:payout"
NEXT_DAY: Final = timedelta(days=1)


class InstalmentService:
    """Pause tomorrow's loan instalment after an approved payout (SPEC §10)."""

    def __init__(self, store: Store, audit: AuditLog, ids: IdFactory) -> None:
        self._store = store
        self._audit = audit
        self._ids = ids

    def pause_next(
        self, merchant_id: str, event_date: date, decision: Decision, at: datetime
    ) -> InstalmentPause | None:
        """Pause the instalment due on event_date + 1 day; None without a loan or when already paused."""
        at = require_aware(at)
        if decision.merchant_id != merchant_id:
            raise ValueError(f"decision {decision.id} is for {decision.merchant_id}, not {merchant_id}")
        if decision.outcome is not DecisionOutcome.APPROVED:
            raise ValueError(f"decision {decision.id} is {decision.outcome}; only APPROVED payouts pause")
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
        self._audit.append(
            at=at,
            actor=ACTOR,
            action="instalment.pause",
            subject_type="instalment_pause",
            subject_id=pause.id,
            data={
                "merchant_id": merchant_id,
                "loan_id": loan.id,
                "lender": LENDER,
                "instalment_date": due.isoformat(),
                "amount_paise": pause.amount_paise,
                "decision_id": decision.id,
                "moved_to": "end of tenure",
                "penalty_paise": 0,
            },
        )
        return pause
