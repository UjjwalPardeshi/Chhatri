"""The consent block of a cover purchase (N6, fs-07 section 9.3): what ``POST /api/premium/link`` checks and records.

With the flag off none of this runs and ``consents`` is ignored. With it on, a merchant with no live cover must send the
two purposes needed to buy and the notice version in force; nothing is created otherwise. The app's ticks become
consent only when the link is paid.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from chhatri.clock import IST
from chhatri.consent import notice
from chhatri.consent.ledger import ConsentBook, PendingGrant, consent_book
from chhatri.policy.cover import EffectiveStatus, effective_status

__all__ = ["PurchaseInvalid", "check_purchase", "expect_grant"]

LIVE: frozenset[EffectiveStatus] = frozenset({EffectiveStatus.ACTIVE, EffectiveStatus.WAITING})


class PurchaseInvalid(ValueError):
    """The consent block is incomplete or out of date (HTTP 422); ``fields`` names what is wrong."""

    def __init__(self, fields: dict[str, str]) -> None:
        super().__init__("consent is incomplete")
        self.fields = fields


def _book(runtime: Any) -> ConsentBook | None:
    book = consent_book(runtime.store)
    return book if book is not None and book.enabled else None


def check_purchase(
    runtime: Any, merchant_id: str, consents: tuple[str, ...] | None, notice_version: str | None
) -> None:
    """Raise PurchaseInvalid unless the block is complete for this merchant; no-op while the flag is off."""
    if _book(runtime) is None:
        return
    today = runtime.clock.now().astimezone(IST).date()
    if effective_status(runtime.store.cover(merchant_id), today) in LIVE:
        return  # a renewal: consents are optional
    fields: dict[str, str] = {}
    if not set(consents or ()) >= notice.REQUIRED_TO_BUY:
        fields["consents"] = "required purposes missing"
    if notice_version != notice.NOTICE_VERSION:
        fields["notice_version"] = "out of date"
    if fields:
        raise PurchaseInvalid(fields)


def expect_grant(
    runtime: Any,
    merchant_id: str,
    payment_id: str,
    consents: tuple[str, ...] | None,
    notice_version: str | None,
    now: datetime,
) -> None:
    """Remember what the app ticked; it is recorded when ``payment_id`` is paid."""
    book = _book(runtime)
    if book is None or not consents:
        return
    book.expect_payment(
        payment_id,
        PendingGrant(purposes=tuple(dict.fromkeys(consents)), notice_version=notice_version or "", at=now),
    )
