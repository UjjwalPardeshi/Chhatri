"""The merchant's answer to "may we ask your doctor to confirm your visit?" (SPEC §9.2, the doctor confirmation).

The answer is written to the run's consent book under ``DOCTOR_CONFIRMATION`` (``notice.DOCTOR``): a Yes is an ACTIVE
record, a No a WITHDRAWN one. It is written whether or not ``n6_consents`` is on: with the feature off the book is
installed empty and disabled, so every other gate stays open while an explicit answer still binds. The claim pipeline
reads ``book.latest(merchant_id, DOCTOR)`` before it contacts anyone, so a recorded No always means the doctor is never
asked, and "never asked" stays distinguishable from "said no".

Audit rows (``consent.granted`` / ``consent.refused``) carry ids and codes only: the pre-check id, the check-in date and
where the answer came from. Never a patient name, a doctor, a hospital or a slip date.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Final, Literal

from chhatri.audit.log import AuditLog
from chhatri.consent.ledger import Consent, consent_book, ensure_consent_book
from chhatri.consent.notice import DOCTOR
from chhatri.ids import IdFactory
from chhatri.store.repositories import Store

__all__ = [
    "DOCTOR_VERIFICATION",
    "WIRE_PURPOSE",
    "ConsentSource",
    "DoctorConsents",
    "doctor_consent",
    "record_doctor_consent",
    "verification_consents",
]

DOCTOR_VERIFICATION: Final = DOCTOR  # the ledger purpose
# the purpose word of the chat card and the confirm route (design 2.4)
WIRE_PURPOSE: Final = "doctor_verification"
ConsentSource = Literal["APP", "CHAT"]
_LEDGER_SOURCE: Final = {"APP": "CLAIM_APP", "CHAT": "CLAIM_CHAT"}


class DoctorConsents:
    """The doctor-confirmation answers of one run, kept in that run's consent book."""

    def __init__(self, store: Store, *, ids: IdFactory, audit: AuditLog, settings: Any = None) -> None:
        self._store, self._ids, self._audit, self._settings = store, ids, audit, settings

    def record(
        self,
        *,
        merchant_id: str,
        granted: bool,
        at: datetime,
        source: str = "APP",
        precheck_id: str | None = None,
        checkin: date | None = None,
    ) -> Consent:
        """Write the answer (Yes: ACTIVE, No: WITHDRAWN) and audit it."""
        if source not in _LEDGER_SOURCE:
            raise ValueError(f"source must be APP or CHAT, not {source!r}")
        book = ensure_consent_book(self._store, self._ids, self._audit, self._settings)
        extra = {"precheck_id": precheck_id, "checkin": None if checkin is None else checkin.isoformat()}
        return book.answer(
            merchant_id, DOCTOR, granted=granted, source=_LEDGER_SOURCE[source], at=at, extra=extra
        )

    def latest(self, merchant_id: str) -> Consent | None:
        return doctor_consent(self._store, merchant_id)


def verification_consents(
    store: Store, *, ids: IdFactory, audit: AuditLog, settings: Any = None
) -> DoctorConsents:
    """The recorder over `store` (cheap: the state lives in the store's consent book)."""
    return DoctorConsents(store, ids=ids, audit=audit, settings=settings)


def record_doctor_consent(
    store: Store,
    *,
    ids: IdFactory,
    audit: AuditLog,
    merchant_id: str,
    granted: bool,
    at: datetime,
    source: str = "APP",
    precheck_id: str | None = None,
    checkin: date | None = None,
    settings: Any = None,
) -> Consent:
    """One answer, for scripted replays and goldens that skip the chat."""
    return verification_consents(store, ids=ids, audit=audit, settings=settings).record(
        merchant_id=merchant_id,
        granted=granted,
        at=at,
        source=source,
        precheck_id=precheck_id,
        checkin=checkin,
    )


def doctor_consent(store: Store, merchant_id: str) -> Consent | None:
    """The latest answer of `merchant_id` in this run, None when the question was never answered (read-only)."""
    book = consent_book(store)
    return None if book is None else book.latest(merchant_id, DOCTOR)
