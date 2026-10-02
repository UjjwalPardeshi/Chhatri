"""Which COVER_STATUS line describes a cover on a date (K6, fs-07 section 5.3).

One function serves the chat reply (`conversation.replies`) and the cover card (`replay.view_cover`), so the app, the
console and WhatsApp can never word the same cover two ways. The status is the derived one: COVER_STATUS_STARTS
while WAITING, COVER_STATUS_UNPAID when the premium is due, COVER_STATUS_ACTIVE otherwise, and COVER_STATUS_NONE
for a merchant with no live cover (none, cancelled, lapsed or waiting for a payment).
"""

from __future__ import annotations

from datetime import date
from typing import Final

from chhatri.conversation.messages import date_en, date_hi
from chhatri.domain.models import Cover
from chhatri.policy.cover import EffectiveStatus, effective_status, premium_due

NO_LIVE_COVER: Final = "COVER_STATUS_NONE"
LIVE_STATUSES: Final = frozenset({EffectiveStatus.WAITING, EffectiveStatus.ACTIVE})


def cover_status_line(cover: Cover | None, today: date) -> tuple[str, dict[str, str]]:
    """``(catalogue key, facts)`` of the COVER_STATUS line for `cover` on `today`."""
    if cover is None or effective_status(cover, today) not in LIVE_STATUSES:
        return NO_LIVE_COVER, {}
    if effective_status(cover, today) is EffectiveStatus.WAITING:
        return "COVER_STATUS_STARTS", {
            "starts_on_hi": date_hi(cover.starts_on),
            "starts_on_en": date_en(cover.starts_on),
        }
    paid = cover.prepaid_through
    if paid is None or premium_due(cover, today):
        return "COVER_STATUS_UNPAID", {}
    return "COVER_STATUS_ACTIVE", {"prepaid_hi": date_hi(paid), "prepaid_en": date_en(paid)}
