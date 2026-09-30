"""SPEC §10 InstalmentService: pause event_date + 1 with the simulated lender, once, audited."""

from __future__ import annotations

from datetime import date

import pytest

from chhatri.audit.log import AuditLog
from chhatri.clock import ist
from chhatri.domain.enums import DecisionOutcome
from chhatri.domain.models import Decision
from chhatri.ids import IdFactory
from chhatri.ledger.instalments import LENDER, InstalmentService
from chhatri.money import rupees
from chhatri.policy.engine import evaluate_area_claim
from chhatri.policy.rules import default_rules
from chhatri.store.repositories import Store
from tests.policy import builders as b

PAUSE_AT = ist(2025, 8, 19, 17, 5)
EVENT = date(2025, 8, 19)


@pytest.fixture
def service(store: Store, audit: AuditLog, ids: IdFactory) -> InstalmentService:
    return InstalmentService(store, audit, ids)


def decision(**kw: object) -> Decision:
    d = evaluate_area_claim(b.area_facts(), default_rules(), decision_id="D-000001", now=ist(2025, 8, 19, 17))
    return d.model_copy(update=kw) if kw else d


def test_pauses_tomorrows_instalment(service: InstalmentService, store: Store, audit: AuditLog) -> None:
    pause = service.pause_next("S-0142", EVENT, decision(), PAUSE_AT)
    assert pause is not None
    assert (pause.id, pause.loan_id, pause.instalment_date) == ("IP-000001", "L-S-0142", date(2025, 8, 20))
    assert (pause.amount_paise, pause.decision_id, pause.created_at) == (rupees(600), "D-000001", PAUSE_AT)
    assert LENDER == "Simulated lender (NBFC partner)"
    assert LENDER in pause.reason and "end of the tenure" in pause.reason and "₹600" in pause.reason
    assert store.pauses("S-0142") == (pause,)
    [entry] = audit.entries()
    assert (entry.action, entry.actor, entry.at) == ("instalment.pause", "workflow:payout", PAUSE_AT)
    assert entry.data["lender"] == LENDER and entry.data["instalment_date"] == "2025-08-20"
    assert entry.data["penalty_paise"] == 0


def test_second_pause_for_same_day_is_none(service: InstalmentService, store: Store) -> None:
    assert service.pause_next("S-0142", EVENT, decision(), PAUSE_AT) is not None
    assert service.pause_next("S-0142", EVENT, decision(), PAUSE_AT) is None
    assert len(store.pauses()) == 1


def test_no_loan_means_no_pause(service: InstalmentService, store: Store) -> None:
    d = decision(merchant_id="S-0907")
    assert service.pause_next("S-0907", EVENT, d, PAUSE_AT) is None
    assert store.pauses() == ()


def test_rejects_other_merchant_or_unapproved(service: InstalmentService) -> None:
    with pytest.raises(ValueError, match="is for"):
        service.pause_next("S-0907", EVENT, decision(), PAUSE_AT)
    with pytest.raises(ValueError, match="only APPROVED"):
        service.pause_next("S-0142", EVENT, decision(outcome=DecisionOutcome.REFERRED), PAUSE_AT)
