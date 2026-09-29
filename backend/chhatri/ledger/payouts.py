"""Payout service (SPEC §10, §24.3). Executes APPROVED decisions and credits payouts."""

from __future__ import annotations

from datetime import datetime

from chhatri.audit.log import AuditLog
from chhatri.domain.enums import DecisionOutcome, PayoutStatus
from chhatri.domain.models import Decision, Payout
from chhatri.ids import IdFactory
from chhatri.policy.rules import PolicyRules
from chhatri.store.repositories import Store


class PayoutService:
    """Execute APPROVED decisions to create payouts, and credit them (idempotent)."""

    def __init__(self, store: Store, audit: AuditLog, ids: IdFactory, rules: PolicyRules) -> None:
        self.store = store
        self.audit = audit
        self.ids = ids
        self.rules = rules

    def execute(self, decision: Decision) -> Payout:
        """Execute an APPROVED decision and create a PENDING payout.

        Idempotent on decision.id: if a payout already exists for this decision, return it.

        Args:
            decision: Must have outcome APPROVED.

        Returns:
            A Payout with status PENDING, credited_at None, and reference deterministic.

        Raises:
            ValueError: If decision is not APPROVED.
        """
        if decision.outcome != DecisionOutcome.APPROVED:
            raise ValueError(f"Can only execute APPROVED decisions, got {decision.outcome}")

        # Check if payout already exists (idempotent)
        existing = self.store.payout_for_decision(decision.id)
        if existing:
            return existing

        # Create new payout
        payout_id = self.ids.next("payout")
        reference = f"CHH-{payout_id}"

        payout = Payout(
            id=payout_id,
            decision_id=decision.id,
            merchant_id=decision.merchant_id,
            amount_paise=decision.amount_paise,
            status=PayoutStatus.PENDING,
            rail="Paytm settlement (simulated)",
            created_at=decision.decided_at,
            credited_at=None,
            reference=reference,
        )

        self.store.add_payout(payout)

        # Audit
        self.audit.append(
            at=decision.decided_at,
            actor="policy-engine",
            action="payout-execute",
            subject_type="payout",
            subject_id=payout.id,
            data={
                "decision_id": decision.id,
                "amount_paise": payout.amount_paise,
                "merchant_id": payout.merchant_id,
                "reference": reference,
            },
        )

        return payout

    def credit(self, payout_id_or_decision_id: str, at: datetime) -> Payout:
        """Credit a payout, setting status to CREDITED and credited_at (idempotent on decision_id).

        Args:
            payout_id_or_decision_id: Either a payout_id or decision_id. If it's a decision_id,
                find the payout for that decision.
            at: The time the payout was credited (simulated time).

        Returns:
            The credited Payout.

        Raises:
            KeyError: If payout or decision not found.
        """
        # Determine which is which
        payout = None
        decision_id = None

        if payout_id_or_decision_id.startswith("P-"):
            # It's a payout_id
            payout = self.store._payouts.get(payout_id_or_decision_id)
            if not payout:
                raise KeyError(f"Payout {payout_id_or_decision_id} not found")
            decision_id = payout.decision_id
        else:
            # Assume it's a decision_id
            decision_id = payout_id_or_decision_id
            payout = self.store.payout_for_decision(decision_id)
            if not payout:
                raise KeyError(f"No payout for decision {decision_id}")

        # If already credited, return (idempotent)
        if payout.status == PayoutStatus.CREDITED and payout.credited_at:
            return payout

        # Credit the payout
        credited_payout = payout.model_copy(update={
            "status": PayoutStatus.CREDITED,
            "credited_at": at,
        })

        self.store.replace_payout(credited_payout)

        # Audit
        self.audit.append(
            at=at,
            actor="system",
            action="payout-credit",
            subject_type="payout",
            subject_id=payout.id,
            data={
                "decision_id": decision_id,
                "amount_paise": payout.amount_paise,
                "merchant_id": payout.merchant_id,
            },
        )

        return credited_payout
