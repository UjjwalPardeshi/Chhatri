"""Payouts on the simulated Paytm settlement rail (SPEC §10, §24.3; binding decision B2).

`execute` turns an APPROVED decision into a PENDING payout (idempotent on the decision id) after
re-validating that the decision is the stored one, APPROVED, and that no other decision for the
same claim has been paid. `credit` marks it CREDITED at the given simulated time (idempotent). The
rail delay (`payout_rail_delay_minutes`) is applied by the caller's scheduler; `credit_due_at` gives
that time (SPEC §17.2: decisions 17:00, credits 17:04). Every state change is audited.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Final

from chhatri.audit.log import AuditLog
from chhatri.clock import require_aware
from chhatri.domain.enums import DecisionOutcome, PayoutStatus
from chhatri.domain.models import Decision, Payout
from chhatri.ids import IdFactory
from chhatri.policy.rules import PolicyRules
from chhatri.store.repositories import Store

logger = logging.getLogger(__name__)

RAIL: Final = "Paytm settlement (simulated)"
REFERENCE_PREFIX: Final = "CHHATRI-SIM-"
ACTOR: Final = "workflow:payout"


class PayoutService:
    """Execute and credit payouts for APPROVED decisions (SPEC §10)."""

    def __init__(self, store: Store, audit: AuditLog, ids: IdFactory, rules: PolicyRules) -> None:
        self._store = store
        self._audit = audit
        self._ids = ids
        self._rules = rules

    def credit_due_at(self, decision: Decision) -> datetime:
        """When the simulated rail credits a payout: decided_at + payout_rail_delay_minutes (§10)."""
        return decision.decided_at + timedelta(minutes=self._rules.payout_rail_delay_minutes)

    def _validate(self, decision: Decision) -> None:
        stored = self._store.decision(decision.id)
        if stored != decision:
            raise ValueError(f"decision {decision.id} differs from the stored decision")
        if decision.outcome is not DecisionOutcome.APPROVED or decision.amount_paise <= 0:
            raise ValueError(f"decision {decision.id} is {decision.outcome}; only APPROVED amounts are paid")
        for sibling in self._store.decisions_for_claim(decision.claim_id):
            if sibling.id != decision.id and self._store.payout_for_decision(sibling.id) is not None:
                raise ValueError(f"claim {decision.claim_id} was already paid under {sibling.id}")

    def execute(self, decision: Decision) -> Payout:
        """PENDING payout for an APPROVED decision; returns the existing one on a repeat call."""
        existing = self._store.payout_for_decision(decision.id)
        if existing is not None:
            return existing
        self._validate(decision)
        payout_id = self._ids.next("payout")
        payout = Payout(
            id=payout_id,
            decision_id=decision.id,
            merchant_id=decision.merchant_id,
            amount_paise=decision.amount_paise,
            status=PayoutStatus.PENDING,
            rail=RAIL,
            created_at=decision.decided_at,
            credited_at=None,
            reference=f"{REFERENCE_PREFIX}{payout_id}",
        )
        self._store.add_payout(payout)
        self._audit.append(
            at=decision.decided_at,
            actor=ACTOR,
            action="payout.execute",
            subject_type="payout",
            subject_id=payout.id,
            data={
                "decision_id": decision.id,
                "claim_id": decision.claim_id,
                "merchant_id": decision.merchant_id,
                "amount_paise": payout.amount_paise,
                "rail": RAIL,
                "reference": payout.reference,
                "status": payout.status.value,
            },
        )
        logger.info("payout %s pending for decision %s", payout.id, decision.id)
        return payout

    def _find(self, payout_id_or_decision_id: str) -> Payout:
        by_decision = self._store.payout_for_decision(payout_id_or_decision_id)
        return by_decision if by_decision is not None else self._store.payout(payout_id_or_decision_id)

    def credit(self, payout_id_or_decision_id: str, at: datetime) -> Payout:
        """Mark the payout CREDITED at `at` (idempotent); KeyError when no such payout exists."""
        at = require_aware(at)
        payout = self._find(payout_id_or_decision_id)
        if payout.status is PayoutStatus.CREDITED:
            return payout
        if payout.status is not PayoutStatus.PENDING:
            raise ValueError(f"payout {payout.id} is {payout.status}; only PENDING payouts can be credited")
        if at < payout.created_at:
            raise ValueError(f"payout {payout.id} cannot be credited before it was created")
        credited = payout.model_copy(update={"status": PayoutStatus.CREDITED, "credited_at": at})
        self._store.replace_payout(credited)
        self._audit.append(
            at=at,
            actor=ACTOR,
            action="payout.credit",
            subject_type="payout",
            subject_id=payout.id,
            data={
                "decision_id": payout.decision_id,
                "merchant_id": payout.merchant_id,
                "amount_paise": payout.amount_paise,
                "reference": payout.reference,
                "status": credited.status.value,
            },
        )
        logger.info("payout %s credited", payout.id)
        return credited
