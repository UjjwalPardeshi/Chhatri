"""SPEC §12 CaseService: ids from C-2291, SLA due_by, validation, resolve, audit."""

from __future__ import annotations

from datetime import timedelta

import pytest

from chhatri.audit.log import AuditLog
from chhatri.cases.service import CaseService
from chhatri.clock import ist
from chhatri.domain.enums import CaseKind, CaseStatus
from chhatri.ids import IdFactory
from chhatri.policy.engine import evaluate_personal_claim
from chhatri.policy.rules import default_rules
from chhatri.store.repositories import Store
from tests.policy import builders as b

RULES = default_rules()
AT = ist(2025, 8, 19, 17, 12)


@pytest.fixture
def store() -> Store:
    return Store(b.city())


@pytest.fixture
def audit() -> AuditLog:
    return AuditLog()


@pytest.fixture
def service(store: Store, audit: AuditLog) -> CaseService:
    return CaseService(store, audit, IdFactory(), RULES)


def dispute(service: CaseService, **kw: object):
    args = {
        "kind": CaseKind.DISPUTE,
        "merchant_id": "S-0142",
        "at": AT,
        "summary_en": "Merchant says the loss was bigger than ₹1,380",
        "summary_hi": "मेरा नुकसान ज़्यादा हुआ।",
        "evidence": {"merchant_text": "मेरा नुकसान ज़्यादा हुआ।"},
    }
    return service.open(**{**args, **kw})  # type: ignore[arg-type]


def referred_mismatch(store: Store):
    claim = b.personal_claim(slip=b.slip(patient_name="Sunil Pawar"))
    store.add_claim(claim)
    facts = b.personal_facts(claim=claim)
    d = evaluate_personal_claim(facts, RULES, decision_id="D-000001", now=AT)
    store.add_decision(d)
    return claim, d


def test_first_case_is_c2291_with_sla(service: CaseService, store: Store, audit: AuditLog) -> None:
    case = dispute(service)
    assert (case.id, case.status, case.opened_at, case.due_by) == (
        "C-2291",
        CaseStatus.OPEN,
        AT,
        AT + timedelta(hours=24),
    )
    assert case.evidence == {"merchant_text": "मेरा नुकसान ज़्यादा हुआ।"}
    assert dispute(service).id == "C-2292"
    assert store.case("C-2291") == case
    entry = audit.entries()[0]
    assert (entry.action, entry.actor, entry.subject_id) == ("case.open", "system", "C-2291")
    assert entry.data["due_by"] == "2025-08-20T17:12:00+05:30"


def test_personal_review_links_referred_decision(service: CaseService, store: Store) -> None:
    claim, d = referred_mismatch(store)
    case = dispute(service, kind=CaseKind.PERSONAL_CLAIM_REVIEW, claim_id=claim.id, decision_id=d.id)
    assert (case.kind, case.claim_id, case.decision_id) == (CaseKind.PERSONAL_CLAIM_REVIEW, claim.id, d.id)


def test_personal_review_requires_referred_decision(service: CaseService, store: Store) -> None:
    with pytest.raises(ValueError, match="REFERRED"):
        dispute(service, kind=CaseKind.PERSONAL_CLAIM_REVIEW)
    claim = b.personal_claim()
    store.add_claim(claim)
    approved = evaluate_personal_claim(b.personal_facts(claim=claim), RULES, decision_id="D-000005", now=AT)
    store.add_decision(approved)
    with pytest.raises(ValueError, match="REFERRED"):
        dispute(service, kind=CaseKind.PERSONAL_CLAIM_REVIEW, decision_id=approved.id)


def test_open_validation(service: CaseService, store: Store) -> None:
    claim, d = referred_mismatch(store)
    with pytest.raises(KeyError):
        dispute(service, merchant_id="S-9999")
    with pytest.raises(ValueError, match="summary"):
        dispute(service, summary_en="  ")
    with pytest.raises(ValueError, match="does not belong"):
        dispute(service, merchant_id="S-0907", claim_id=claim.id)
    with pytest.raises(ValueError, match="does not belong"):
        dispute(service, merchant_id="S-0907", decision_id=d.id)
    store.add_claim(b.personal_claim(id="CL-000077"))
    with pytest.raises(ValueError, match="not for claim"):
        dispute(service, claim_id="CL-000077", decision_id=d.id)
    with pytest.raises(KeyError):
        dispute(service, decision_id="D-404")


def test_resolve(service: CaseService, store: Store, audit: AuditLog) -> None:
    case = dispute(service)
    later = AT + timedelta(hours=2)
    done = service.resolve(
        case.id, status=CaseStatus.CLOSED, by="officer:priya", resolution="Numbers explained", at=later
    )
    assert (done.status, done.resolved_by, done.resolved_at, done.resolution) == (
        CaseStatus.CLOSED,
        "officer:priya",
        later,
        "Numbers explained",
    )
    assert store.cases(CaseStatus.OPEN) == ()
    entry = audit.entries()[-1]
    assert (entry.action, entry.actor, entry.data["within_sla"]) == ("case.resolve", "officer:priya", True)
    with pytest.raises(ValueError, match="already"):
        service.resolve(case.id, status=CaseStatus.APPROVED, by="officer:priya", resolution="x", at=later)


@pytest.mark.parametrize(
    ("kw", "message"),
    [
        ({"status": CaseStatus.OPEN}, "resolves to"),
        ({"by": "merchant:S-0142"}, "actor"),
        ({"at": AT - timedelta(minutes=1)}, "before it was opened"),
    ],
)
def test_resolve_validation(service: CaseService, kw: dict, message: str) -> None:
    case = dispute(service)
    args = {"status": CaseStatus.DECLINED, "by": "officer:priya", "resolution": "Declined", "at": AT}
    with pytest.raises(ValueError, match=message):
        service.resolve(case.id, **{**args, **kw})


def test_resolve_unknown_case(service: CaseService) -> None:
    with pytest.raises(KeyError):
        service.resolve("C-9999", status=CaseStatus.CLOSED, by="system", resolution="x", at=AT)


def test_resolution_after_sla_flagged(service: CaseService, audit: AuditLog) -> None:
    case = dispute(service)
    service.resolve(
        case.id,
        status=CaseStatus.CLOSED,
        by="workflow:follow-up",
        resolution="SLA",
        at=AT + timedelta(hours=25),
    )
    assert audit.entries()[-1].data["within_sla"] is False


def test_resolve_accepts_string_status_and_blank_note(service: CaseService, store: Store) -> None:
    case = dispute(service)
    done = service.resolve(case.id, status="APPROVED", by="officer:priya", resolution="  ", at=AT)  # type: ignore[arg-type]
    assert done.status is CaseStatus.APPROVED
    assert done.resolution == "Approved by officer:priya"
    with pytest.raises(ValueError):
        service.resolve(dispute(service).id, status="MAYBE", by="system", resolution="x", at=AT)  # type: ignore[arg-type]


def test_open_accepts_string_kind(service: CaseService) -> None:
    assert dispute(service, kind="DISPUTE").kind is CaseKind.DISPUTE
