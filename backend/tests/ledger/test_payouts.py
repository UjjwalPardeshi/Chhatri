"""SPEC §10 PayoutService: APPROVED only, idempotent execute/credit, audited (B2 re-validation)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from chhatri.audit.log import AuditLog
from chhatri.clock import ist
from chhatri.domain.enums import DecisionOutcome, PayoutStatus
from chhatri.domain.models import Decision
from chhatri.ids import IdFactory
from chhatri.ledger.payouts import RAIL, PayoutService
from chhatri.money import rupees
from chhatri.policy.engine import evaluate_area_claim
from chhatri.policy.rules import default_rules
from chhatri.store.repositories import Store
from tests.policy import builders as b

RULES = default_rules()
DECIDED = ist(2025, 8, 19, 17)
CREDIT = ist(2025, 8, 19, 17, 4)


@pytest.fixture
def service(store: Store, audit: AuditLog, ids: IdFactory) -> PayoutService:
    return PayoutService(store, audit, ids, RULES)


def approved(store: Store, did: str = "D-000001", **kw: object) -> Decision:
    d = evaluate_area_claim(b.area_facts(), RULES, decision_id=did, now=DECIDED)
    d = d.model_copy(update=kw) if kw else d
    store.add_decision(d)
    return d


def test_execute_creates_pending_payout(service: PayoutService, store: Store, audit: AuditLog) -> None:
    d = approved(store)
    p = service.execute(d)
    assert (p.id, p.status, p.amount_paise, p.rail) == ("P-000001", PayoutStatus.PENDING, rupees(1380), RAIL)
    assert RAIL == "Paytm settlement (simulated)"
    assert (p.created_at, p.credited_at, p.reference) == (DECIDED, None, "CHHATRI-SIM-P-000001")
    assert store.payout_for_decision(d.id) is p
    [entry] = audit.entries()
    assert (entry.action, entry.actor, entry.subject_id, entry.at) == (
        "payout.execute",
        "workflow:payout",
        p.id,
        DECIDED,
    )
    assert entry.data["amount_paise"] == rupees(1380)


def test_execute_is_idempotent(service: PayoutService, store: Store, audit: AuditLog) -> None:
    d = approved(store)
    assert service.execute(d) is service.execute(d)
    assert len(store.payouts()) == 1 and len(audit) == 1


@pytest.mark.parametrize("outcome", [DecisionOutcome.REFERRED, DecisionOutcome.DECLINED])
def test_execute_rejects_non_approved(service: PayoutService, store: Store, outcome: DecisionOutcome) -> None:
    d = approved(store, outcome=outcome)
    with pytest.raises(ValueError, match="only APPROVED"):
        service.execute(d)
    assert store.payouts() == ()


def test_execute_rejects_unknown_or_altered_decision(service: PayoutService, store: Store) -> None:
    d = evaluate_area_claim(b.area_facts(), RULES, decision_id="D-000009", now=DECIDED)
    with pytest.raises(KeyError):
        service.execute(d)
    stored = approved(store)
    with pytest.raises(ValueError, match="differs"):
        service.execute(stored.model_copy(update={"amount_paise": rupees(9999)}))


def test_execute_refuses_second_payout_for_same_claim(service: PayoutService, store: Store) -> None:
    service.execute(approved(store, "D-000001"))
    twin = approved(store, "D-000002")
    with pytest.raises(ValueError, match="already paid"):
        service.execute(twin)


def test_credit_by_payout_or_decision_id_idempotent(
    service: PayoutService, store: Store, audit: AuditLog
) -> None:
    d = approved(store)
    p = service.execute(d)
    credited = service.credit(p.id, CREDIT)
    assert (credited.status, credited.credited_at) == (PayoutStatus.CREDITED, CREDIT)
    assert service.credit(d.id, CREDIT + timedelta(minutes=9)) is credited
    assert store.payout(p.id) is credited
    assert [e.action for e in audit.entries()] == ["payout.execute", "payout.credit"]
    assert store.latest_paid_decision("S-0142") == d


def test_credit_errors(service: PayoutService, store: Store) -> None:
    with pytest.raises(KeyError):
        service.credit("P-404", CREDIT)
    p = service.execute(approved(store))
    with pytest.raises(ValueError, match="before it was created"):
        service.credit(p.id, DECIDED - timedelta(minutes=1))
    store.replace_payout(p.model_copy(update={"status": PayoutStatus.FAILED}))
    with pytest.raises(ValueError, match="only PENDING"):
        service.credit(p.id, CREDIT)


def test_credit_due_at_is_rail_delay(service: PayoutService, store: Store) -> None:
    assert service.credit_due_at(approved(store)) == CREDIT
