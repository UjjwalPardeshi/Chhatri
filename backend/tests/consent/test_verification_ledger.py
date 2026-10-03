"""The merchant's answer to "may we ask your doctor?" lands in the run's consent book under DOCTOR_CONFIRMATION.

The pipeline reads `book.latest(merchant, DOCTOR)` first, so a recorded No must be a WITHDRAWN record (never "nothing
written", which would fall through to the open gate) and a Yes an ACTIVE one, whether or not `n6_consents` installed the
book. The audit rows carry ids and codes only: never a patient name, a doctor or a slip date.
"""

from __future__ import annotations

from datetime import date

from chhatri.audit.log import AuditLog
from chhatri.clock import ist
from chhatri.consent.ledger import ConsentBook, consent_book, consent_gate_open
from chhatri.consent.notice import DOCTOR, SALES
from chhatri.consent.verification import (
    DOCTOR_VERIFICATION,
    doctor_consent,
    record_doctor_consent,
    verification_consents,
)
from chhatri.ids import IdFactory
from chhatri.store.repositories import Store
from tests.policy import builders as b

AT = ist(2025, 8, 21, 11, 21)
CHECKIN = date(2025, 8, 20)


def _rig() -> tuple[Store, IdFactory, AuditLog]:
    return Store(b.city()), IdFactory(), AuditLog()


def test_the_purpose_is_the_doctor_constant() -> None:
    assert DOCTOR_VERIFICATION == DOCTOR == "DOCTOR_CONFIRMATION"


def test_nothing_is_recorded_before_the_merchant_answers() -> None:
    store, _, _ = _rig()
    assert doctor_consent(store, "S-0142") is None


def test_a_yes_is_an_active_record_even_without_the_consent_feature() -> None:
    store, ids, audit = _rig()
    assert consent_book(store) is None  # n6_consents off: nothing installed
    record = record_doctor_consent(
        store,
        ids=ids,
        audit=audit,
        merchant_id="S-0142",
        granted=True,
        at=AT,
        source="CHAT",
        precheck_id="PC-000001",
        checkin=CHECKIN,
    )
    book = consent_book(store)
    assert isinstance(book, ConsentBook) and not book.enabled
    assert (record.purpose, record.status, record.granted_at) == (DOCTOR, "ACTIVE", AT)
    assert book.latest("S-0142", DOCTOR) == record and book.is_active("S-0142", DOCTOR)
    assert doctor_consent(store, "S-0142") == record
    assert consent_gate_open(store, "S-0142", SALES)  # a disabled book keeps every other gate open


def test_a_no_is_a_withdrawn_record_that_binds() -> None:
    store, ids, audit = _rig()
    record = record_doctor_consent(
        store, ids=ids, audit=audit, merchant_id="S-0142", granted=False, at=AT, source="APP"
    )
    book = consent_book(store)
    assert book is not None
    assert (record.status, record.withdrawn_at) == ("WITHDRAWN", AT)
    assert book.latest("S-0142", DOCTOR) is not None and not book.is_active("S-0142", DOCTOR)


def test_a_later_answer_replaces_the_earlier_one() -> None:
    store, ids, audit = _rig()
    record_doctor_consent(
        store, ids=ids, audit=audit, merchant_id="S-0142", granted=True, at=AT, source="APP"
    )
    later = record_doctor_consent(
        store, ids=ids, audit=audit, merchant_id="S-0142", granted=False, at=AT, source="CHAT"
    )
    assert doctor_consent(store, "S-0142") == later and later.status == "WITHDRAWN"
    again = record_doctor_consent(
        store, ids=ids, audit=audit, merchant_id="S-0142", granted=True, at=AT, source="CHAT"
    )
    assert doctor_consent(store, "S-0142") == again and again.status == "ACTIVE"


def test_answers_are_per_store_and_per_merchant() -> None:
    store, ids, audit = _rig()
    record_doctor_consent(
        store, ids=ids, audit=audit, merchant_id="S-0142", granted=True, at=AT, source="APP"
    )
    assert doctor_consent(store, "S-0907") is None
    assert doctor_consent(Store(b.city()), "S-0142") is None  # a scenario load starts afresh


def test_the_n6_book_is_reused_when_it_is_installed() -> None:
    store, ids, audit = _rig()
    first = verification_consents(store, ids=ids, audit=audit)
    second = verification_consents(store, ids=ids, audit=audit)
    first.record(merchant_id="S-0142", granted=True, at=AT, source="APP")
    assert second.latest("S-0142") is not None


def test_the_audit_says_granted_or_refused_with_ids_only() -> None:
    store, ids, audit = _rig()
    yes = record_doctor_consent(
        store,
        ids=ids,
        audit=audit,
        merchant_id="S-0142",
        granted=True,
        at=AT,
        source="CHAT",
        precheck_id="PC-000001",
        checkin=CHECKIN,
    )
    no = record_doctor_consent(
        store,
        ids=ids,
        audit=audit,
        merchant_id="S-0907",
        granted=False,
        at=AT,
        source="APP",
        precheck_id="PC-000002",
        checkin=CHECKIN,
    )
    entries = {e.subject_id: e for e in audit.entries()}
    granted, refused = entries[yes.id], entries[no.id]
    assert (granted.action, refused.action) == ("consent.granted", "consent.refused")
    assert granted.actor == "merchant:S-0142" and granted.subject_type == "consent"
    assert granted.data == {
        "merchant_id": "S-0142",
        "purpose": DOCTOR,
        "source": "CLAIM_CHAT",
        "notice_version": None,
        "payment_id": None,
        "precheck_id": "PC-000001",
        "checkin": "2025-08-20",
    }
    text = repr([e.data for e in audit.entries()])
    for secret in ("Anil", "Rao", "KEM", "MMC"):
        assert secret not in text
