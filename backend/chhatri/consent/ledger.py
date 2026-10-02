"""The consent records of one scenario run (N6, fs-07 section 9.2) and the gate every flow asks.

One ``ConsentBook`` per ``Store`` (a reload makes a new Store, so it starts afresh). It is installed only while the
flag ``n6_consents`` is on; with no book installed, or one that is not enabled, every gate passes, so Waves 1 and 2
run exactly as today. A withdrawal replaces the record with ``model_copy`` and the book keeps every record, so an
old receipt still opens. Seeded consents write no audit entry: they pre-date the replay.

Consent is granted by an action that needs the data and never on its own. A paid payment link grants it, so the
book looks at the run's paid link payments when it is read: the link's own grant if the app made one, otherwise the
two purposes the chat notice covers.
"""

from __future__ import annotations

import threading
import weakref
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Literal

from pydantic import Field

from chhatri.audit.log import AuditLog
from chhatri.consent import notice
from chhatri.domain.enums import PremiumMethod, PremiumStatus
from chhatri.domain.models import Frozen
from chhatri.ids import IdFactory
from chhatri.store.repositories import Store

__all__ = ["Consent", "ConsentBook", "PendingGrant", "consent_book", "consent_gate_open", "install_consents"]


class Consent(Frozen):
    id: str = Field(pattern=r"^CN-\d{6,}$")
    merchant_id: str
    purpose: Literal["SALES_DATA_FOR_CLAIM", "SLIP_DATA_FOR_HOSPITAL_CLAIM", "SETTLEMENT_DEDUCTION"]
    status: Literal["ACTIVE", "WITHDRAWN"]
    notice_version: str | None = None
    granted_at: datetime
    withdrawn_at: datetime | None = None
    source: Literal["PAYMENT_APP", "PAYMENT_CHAT", "SLIP_UPLOAD", "SEEDED"]
    payment_id: str | None = None


@dataclass(frozen=True, slots=True)
class PendingGrant:
    """What the app ticked when it asked for a payment link; it becomes consent only when that link is paid."""

    purposes: tuple[str, ...]
    notice_version: str
    at: datetime


class ConsentBook:
    def __init__(self, store: Store, ids: IdFactory, audit: AuditLog) -> None:
        self._store, self._ids, self._audit = store, ids, audit
        self._lock = threading.RLock()
        self._records: dict[str, Consent] = {}
        self._latest: dict[tuple[str, str], str] = {}
        self._pending: dict[str, PendingGrant] = {}  # payment id -> the app's grant
        self._handled: set[str] = set()
        self._erased: dict[str, datetime] = {}  # slip id -> erased_at
        self.enabled = False

    # ------------------------------------------------------------------ install
    def seed(self) -> None:
        """Three ACTIVE SEEDED records for each merchant with a seeded cover (no audit entries)."""
        with self._lock:
            for merchant_id, cover in sorted(self._store.city.covers.items()):
                for purpose in notice.PURPOSES:
                    self._put(
                        Consent(
                            id=self._ids.next("consent"),
                            merchant_id=merchant_id,
                            purpose=purpose,  # type: ignore[arg-type]
                            status="ACTIVE",
                            granted_at=cover.purchased_at,
                            source="SEEDED",
                        )
                    )
            self.enabled = True

    def _put(self, record: Consent) -> None:
        self._records[record.id] = record
        self._latest[(record.merchant_id, record.purpose)] = record.id

    # ------------------------------------------------------------------ reads
    def latest(self, merchant_id: str, purpose: str) -> Consent | None:
        self.reconcile(merchant_id)
        with self._lock:
            key = self._latest.get((merchant_id, purpose))
            return self._records[key] if key else None

    def is_active(self, merchant_id: str, purpose: str) -> bool:
        record = self.latest(merchant_id, purpose)
        return record is not None and record.status == "ACTIVE"

    def get(self, consent_id: str) -> Consent:
        with self._lock:
            try:
                return self._records[consent_id]
            except KeyError:
                raise KeyError(f"unknown consent {consent_id}") from None

    def erased_at(self, slip_id: str) -> datetime | None:
        with self._lock:
            return self._erased.get(slip_id)

    # ------------------------------------------------------------------ writes
    def grant(
        self,
        merchant_id: str,
        purpose: str,
        *,
        source: str,
        at: datetime,
        notice_version: str | None,
        payment_id: str | None = None,
    ) -> Consent | None:
        """A new ACTIVE record unless one is already ACTIVE (at most one per merchant and purpose); audited."""
        with self._lock:
            key = self._latest.get((merchant_id, purpose))
            if key is not None and self._records[key].status == "ACTIVE":
                return None
            record = Consent(
                id=self._ids.next("consent"),
                merchant_id=merchant_id,
                purpose=purpose,  # type: ignore[arg-type]
                status="ACTIVE",
                notice_version=notice_version,
                granted_at=at,
                source=source,  # type: ignore[arg-type]
                payment_id=payment_id,
            )
            self._put(record)
        self._audit.append(
            at=at,
            actor=f"merchant:{merchant_id}",
            action="consent.granted",
            subject_type="consent",
            subject_id=record.id,
            data={
                "merchant_id": merchant_id,
                "purpose": purpose,
                "source": source,
                "notice_version": notice_version,
                "payment_id": payment_id,
            },
        )
        return record

    def replace(self, record: Consent) -> None:
        with self._lock:
            self.get(record.id)
            self._records[record.id] = record

    def mark_erased(self, slip_id: str, at: datetime) -> None:
        with self._lock:
            self._erased[slip_id] = at

    def expect_payment(self, payment_id: str, grant: PendingGrant) -> None:
        with self._lock:
            self._pending[payment_id] = grant

    # ------------------------------------------------------------------ the paid link carries the grant
    def reconcile(self, merchant_id: str | None = None) -> None:
        for payment in self._store.premiums(merchant_id):
            if payment.method is not PremiumMethod.PAYMENT_LINK or payment.status is not PremiumStatus.PAID:
                continue
            with self._lock:
                if payment.id in self._handled:
                    continue
                self._handled.add(payment.id)
                pending = self._pending.get(payment.id)
            purposes = pending.purposes if pending else (notice.SALES, notice.SETTLEMENT)
            for purpose in purposes:
                self.grant(
                    payment.merchant_id,
                    purpose,
                    source="PAYMENT_APP" if pending else "PAYMENT_CHAT",
                    at=pending.at if pending else payment.created_at,
                    notice_version=pending.notice_version if pending else None,
                    payment_id=payment.id,
                )


_BOOKS: Final[weakref.WeakKeyDictionary[Store, ConsentBook]] = weakref.WeakKeyDictionary()
_BOOKS_LOCK: Final = threading.Lock()


def install_consents(store: Store, ids: IdFactory, audit: AuditLog, settings: Any) -> ConsentBook | None:
    """Seed the book of this run when ``n6_consents`` is on; with the flag off nothing is installed."""
    from chhatri.features import is_enabled

    if not is_enabled("n6_consents", settings):
        return None
    book = ConsentBook(store, ids, audit)
    book.seed()
    with _BOOKS_LOCK:
        _BOOKS[store] = book
    return book


def consent_book(store: Store) -> ConsentBook | None:
    try:
        with _BOOKS_LOCK:
            return _BOOKS.get(store)
    except TypeError:  # a test double that cannot be weakly referenced or hashed has no book
        return None


def consent_gate_open(store: Store, merchant_id: str, purpose: str) -> bool:
    """True when the flag is off (no book), or the merchant has an ACTIVE consent for ``purpose``."""
    book = consent_book(store)
    return True if book is None or not book.enabled else book.is_active(merchant_id, purpose)
