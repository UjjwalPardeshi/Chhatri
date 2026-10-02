"""GET /api/merchants/{id}/cover: the cover card the mini-app reads (K6; data-model-and-api 5.1, fs-04 6.2).

The status is derived from the stored status and the replay date (`policy.cover.effective_status`), so the app, the
console (`merchant_detail`) and the chat reply agree. The two status sentences are catalogue lines rendered here
(COVER_STATUS_*; a merchant with no live cover gets COVER_STATUS_NONE). The price is the cover's own, which the seed
and the payment set at the zone price; a merchant with no cover gets the price his zone would pay, and nulls for the
dates and amounts. ``alert_*`` says whether an alert for the zone is in force at the replay time.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final

from chhatri.clock import IST
from chhatri.conversation.cover_text import cover_status_line
from chhatri.conversation.messages import bilingual
from chhatri.domain.models import Alert
from chhatri.money import format_inr
from chhatri.policy.cover import EffectiveStatus, effective_status, premium_due
from chhatri.replay.view_records import iso, iso_date

if TYPE_CHECKING:
    from datetime import datetime

    from chhatri.replay.state import Runtime

__all__ = ["alert_in_force", "cover_view"]

ONE_MINUTE: Final = timedelta(minutes=1)


def alert_in_force(rt: Runtime, zone_id: str, now: datetime) -> Alert | None:
    """The earliest alert for the zone that is issued and valid at `now` (``valid_from <= now < valid_to``)."""
    alerts = rt.world.shocks.alerts_between(now, now + ONE_MINUTE)
    valid = [
        a for a in alerts if zone_id in a.zone_ids and a.issued_at <= now and a.valid_from <= now < a.valid_to
    ]
    return min(valid, key=lambda a: (a.valid_from, a.id)) if valid else None


def _money(paise: int | None) -> dict[str, Any]:
    return {"paise": paise, "label": None if paise is None else format_inr(paise)}


def cover_view(rt: Runtime, merchant_id: str) -> dict[str, Any]:
    """The cover card of one merchant at the replay time; KeyError for an unknown merchant."""
    merchant = rt.static.city.merchant(merchant_id)
    now = rt.clock.now()
    today = now.astimezone(IST).date()
    cover = rt.store.cover(merchant_id)
    status = effective_status(cover, today)
    key, facts = cover_status_line(cover, today)
    text_hi, text_en = bilingual(key, **facts)
    zone_name = next(zone.name for zone in rt.static.city.zones if zone.id == merchant.zone_id)
    per_day = (
        cover.premium_per_day_paise if cover is not None else rt.premiums.premium_per_day(merchant.zone_id)
    )
    alert = alert_in_force(rt, merchant.zone_id, now)
    has_record = cover is not None and status is not EffectiveStatus.NONE
    limit = rt.static.rules.annual_limit_paise if has_record else None
    claimed = rt.store.paid_last_365_days_paise(merchant_id, today) if has_record else None
    remaining = max(limit - claimed, 0) if limit is not None and claimed is not None else None
    amounts = {
        "annual_limit": _money(limit),
        "amount_claimed": _money(claimed),
        "amount_remaining": _money(remaining),
    }
    return {
        "merchant_id": merchant_id,
        "cover_id": cover.id if cover is not None else None,
        "status": status.value,
        "status_text_hi": text_hi,
        "status_text_en": text_en,
        "zone_id": merchant.zone_id,
        "zone_name": zone_name,
        "purchased_at": iso(cover.purchased_at) if cover is not None else None,
        "starts_on": iso_date(cover.starts_on) if cover is not None else None,
        "prepaid_through": iso_date(cover.prepaid_through)
        if cover is not None and cover.prepaid_through
        else None,
        "waiting_period_days": rt.static.rules.cover.waiting_period_days,
        "premium_per_day_paise": per_day,
        "premium_per_day_label": format_inr(per_day),
        "premium_due": premium_due(cover, today),
        **{f"{name}_{part}": money[part] for name, money in amounts.items() for part in ("paise", "label")},
        "alert_active": alert is not None,
        "alert_id": alert.id if alert is not None else None,
    }
