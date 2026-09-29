"""Instalment pause service (SPEC §10, §24.3). Pauses next day's loan instalment."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from chhatri.audit.log import AuditLog
from chhatri.domain.models import Decision, InstalmentPause
from chhatri.ids import IdFactory
from chhatri.store.repositories import Store


class InstalmentService:
    """Pause the next day's loan instalment when a payout happens."""

    def __init__(self, store: Store, audit: AuditLog, ids: IdFactory) -> None:
        self.store = store
        self.audit = audit
        self.ids = ids

    def pause_next(
        self, merchant_id: str, event_date: date, decision: Decision, at: datetime
    ) -> InstalmentPause | None:
        """Pause the next day's instalment (event_date + 1 day).

        Only pauses if:
        - The merchant has a loan
        - The instalment for event_date + 1 is not already paused

        Args:
            merchant_id: The merchant.
            event_date: The event date (claim date).
            decision: The decision that triggered the payout.
            at: The time this action is audited.

        Returns:
            An InstalmentPause if one was created, or None if conditions not met.
        """
        # Get the merchant's loan
        loan = self.store.city.loans.get(merchant_id)
        if not loan:
            return None

        # Tomorrow's instalment
        instalment_date = event_date + timedelta(days=1)

        # Check if already paused
        existing_pauses = self.store.pauses(merchant_id=merchant_id)
        if any(p.instalment_date == instalment_date for p in existing_pauses):
            return None

        # Create pause
        pause_id = self.ids.next("pause")
        pause = InstalmentPause(
            id=pause_id,
            loan_id=loan.id,
            merchant_id=merchant_id,
            instalment_date=instalment_date,
            amount_paise=loan.daily_instalment_paise,
            reason=f"Payout from {decision.outcome} decision {decision.id}",
            decision_id=decision.id,
            created_at=at,
        )

        self.store.add_pause(pause)

        # Audit
        self.audit.append(
            at=at,
            actor="workflow:payout",
            action="instalment-pause",
            subject_type="instalment-pause",
            subject_id=pause.id,
            data={
                "merchant_id": merchant_id,
                "loan_id": loan.id,
                "instalment_date": str(instalment_date),
                "amount_paise": loan.daily_instalment_paise,
                "lender_name": loan.lender_name,
                "decision_id": decision.id,
            },
        )

        return pause
