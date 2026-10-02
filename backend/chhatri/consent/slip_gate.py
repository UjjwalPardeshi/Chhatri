"""The slip gate of the pre-check route (N6, fs-07 section 9.3): a slip is read only under an ACTIVE slip consent.

With the flag off the gate passes. With it on, a merchant with no ACTIVE slip consent can give it in the same call
(``consent: true`` and the current ``notice_version``); the grant is recorded (source SLIP_UPLOAD) and then the slip is
read. Without both, ``ConsentConflict("consent_required")`` (HTTP 409) is raised and nothing is read.
"""

from __future__ import annotations

from typing import Any

from chhatri.consent import notice
from chhatri.consent.errors import ConsentConflict
from chhatri.consent.ledger import consent_book

__all__ = ["require_slip_consent"]


def require_slip_consent(
    runtime: Any, merchant_id: str, *, consent: bool | None, notice_version: str | None
) -> None:
    book = consent_book(runtime.store)
    if book is None or not book.enabled or book.is_active(merchant_id, notice.SLIP):
        return
    if consent is True and notice_version == notice.NOTICE_VERSION:
        book.grant(
            merchant_id,
            notice.SLIP,
            source="SLIP_UPLOAD",
            at=runtime.clock.now(),
            notice_version=notice_version,
        )
        return
    raise ConsentConflict("consent_required", "we need your OK before we read a slip")
