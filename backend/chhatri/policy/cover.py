"""Cover purchase quote (SPEC §9.5; deck slide 8 "Red alert tomorrow. Cover me today." → BLOCKED).

A new cover always starts `waiting_period_days` after the purchase date. The request for an
immediate start is BLOCKED when an alert for the merchant's zone is relevant at `now`:
- valid now: `valid_from ≤ now < valid_to`, or
- already issued and starting within the lookahead: `issued_at ≤ now` and `valid_from < now + lookahead`.

Interpretations (documented, SPEC §9.5 is silent):
- An alert is only known once issued, so both clauses require `issued_at ≤ now`, and an alert that
  has already ended (`valid_to ≤ now`) is not relevant.
- When several alerts are relevant, the one with the earliest (valid_from, id) is reported.
- `existing` must belong to the merchant; it does not change the outcome because a *new* cover
  always waits (SPEC §9.5 "always").

The status a merchant sees and the engine reads is derived (K6, fs-07 section 5.3): `effective_status` takes the
stored status and a date, so a cover bought for the 25th reads WAITING until the 25th and ACTIVE from then on, and
`premium_due` says when an ACTIVE cover has run out of prepaid days. Both are pure; `on` is the replay date in IST.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Final

from chhatri.clock import require_aware
from chhatri.domain.enums import CoverQuoteOutcome, CoverStatus
from chhatri.domain.models import Alert, Cover, CoverQuote, Merchant
from chhatri.policy.rules import PolicyRules


class EffectiveStatus(StrEnum):
    """What the API and the engine call a cover's status: the five stored values, plus NONE (no cover record)."""

    NONE = "NONE"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    WAITING = "WAITING"
    ACTIVE = "ACTIVE"
    LAPSED = "LAPSED"
    CANCELLED = "CANCELLED"


STORED_AS_THEY_ARE: Final = frozenset(
    {CoverStatus.CANCELLED, CoverStatus.LAPSED, CoverStatus.PENDING_PAYMENT}
)
BLOCKED_REASON_EN: Final = "New cover starts after the waiting period"
BLOCKED_REASON_HI: Final = "नया कवर वेटिंग पीरियड के बाद शुरू होता है"
OK_REASON_EN: Final = "No alert for your area. New cover starts after the {days}-day waiting period"
OK_REASON_HI: Final = "आपके इलाके के लिए कोई अलर्ट नहीं है। नया कवर {days} दिन के वेटिंग पीरियड के बाद शुरू होता है"


def effective_status(cover: Cover | None, on: date) -> EffectiveStatus:
    """The cover's status on `on` (fs-07 section 5.3).

    No cover is NONE. CANCELLED, LAPSED and PENDING_PAYMENT stay as stored. A stored WAITING or ACTIVE cover is
    WAITING before `starts_on` and ACTIVE from `starts_on` on, so the start date alone decides.
    """
    if cover is None:
        return EffectiveStatus.NONE
    if cover.status in STORED_AS_THEY_ARE:
        return EffectiveStatus(cover.status.value)
    return EffectiveStatus.WAITING if on < cover.starts_on else EffectiveStatus.ACTIVE


def premium_due(cover: Cover | None, on: date) -> bool:
    """An ACTIVE cover whose `prepaid_through` is missing or before `on` (the test behind COVER_STATUS_UNPAID)."""
    if effective_status(cover, on) is not EffectiveStatus.ACTIVE or cover is None:
        return False
    return cover.prepaid_through is None or cover.prepaid_through < on


def is_relevant_alert(alert: Alert, zone_id: str, now: datetime, lookahead: timedelta) -> bool:
    """True when `alert` blocks an immediate cover start in `zone_id` at `now` (SPEC §9.5)."""
    if zone_id not in alert.zone_ids or alert.issued_at > now or alert.valid_to <= now:
        return False
    valid_now = alert.valid_from <= now
    starts_soon = alert.valid_from < now + lookahead
    return valid_now or starts_soon


def blocking_alert(zone_id: str, now: datetime, alerts: Sequence[Alert], rules: PolicyRules) -> Alert | None:
    """The earliest relevant alert for the zone, or None (SPEC §9.5)."""
    lookahead = timedelta(hours=rules.cover.alert_lookahead_hours)
    relevant = [a for a in alerts if is_relevant_alert(a, zone_id, now, lookahead)]
    return min(relevant, key=lambda a: (a.valid_from, a.id)) if relevant else None


def evaluate_cover_purchase(
    merchant: Merchant,
    existing: Cover | None,
    *,
    now: datetime,
    alerts: Sequence[Alert],
    premium_per_day_paise: int,
    rules: PolicyRules,
    quote_id: str,
) -> CoverQuote:
    """Quote a new cover: BLOCKED during/just before a known alert, else OK (SPEC §9.5, §24.3)."""
    now = require_aware(now)
    if premium_per_day_paise <= 0:
        raise ValueError("premium_per_day_paise must be positive")
    if existing is not None and existing.merchant_id != merchant.id:
        raise ValueError(f"cover {existing.id} belongs to {existing.merchant_id}, not {merchant.id}")
    waiting_days = rules.cover.waiting_period_days
    days_prepaid = rules.premium.first_payment_days
    alert = blocking_alert(merchant.zone_id, now, alerts, rules)
    common = {
        "id": quote_id,
        "merchant_id": merchant.id,
        "requested_at": now,
        "starts_on": now.date() + timedelta(days=waiting_days),
        "premium_per_day_paise": premium_per_day_paise,
        "first_payment_paise": premium_per_day_paise * days_prepaid,
        "days_prepaid": days_prepaid,
    }
    if alert is not None:
        return CoverQuote(
            outcome=CoverQuoteOutcome.BLOCKED,
            reason_en=BLOCKED_REASON_EN,
            reason_hi=BLOCKED_REASON_HI,
            blocking_alert_id=alert.id,
            blocking_alert_in_force=alert.valid_from <= now,
            **common,
        )
    return CoverQuote(
        outcome=CoverQuoteOutcome.OK,
        reason_en=OK_REASON_EN.format(days=waiting_days),
        reason_hi=OK_REASON_HI.format(days=waiting_days),
        blocking_alert_id=None,
        **common,
    )
