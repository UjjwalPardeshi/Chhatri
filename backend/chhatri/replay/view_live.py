"""SPEC §19.2 JSON for the live map: ClockState, ZoneSnapshot, Kpis, StateSnapshot (SPEC §17.2, §20).

Documented choices (SPEC silent, chosen so the deck reads exactly right):
- ClockState.label is "Mumbai · {scenario name with spaces} replay · HH:MM · simulated", e.g.
  "Mumbai · monsoon replay · 17:00 · simulated".
- ZoneSnapshot.index_pct/status/hours_below come from the detection run at floor_hour(now)
  (`ZoneBoard`); live_index_pct is the B3 sliding window. The label shows the trigger's index
  for a zone that triggered today (the number it was paid on, deck "Z7 · 37% · 46 shops"), else
  the trailing 3-hour index ``index_pct`` — the number the Sales row and the "Why Zone 9 got
  nothing" sentence quote (SPEC §8.2, §17.2), so the label never disagrees with them while the
  live value moves inside the hour; "—" when there is no data. ``shops`` = covered pilot shops
  (SPEC §5.4).
- ZoneSnapshot.alert: the triggering alert for a triggered zone; otherwise the alert already
  issued for the zone that is in force or still to come (valid_to > now), earliest valid_from first.
- Kpis: shops_paid and total_paid count CREDITED payouts; trigger_to_money_min is the longest
  trigger → credit time of any credited area payout, in whole minutes (the deck's 4 min).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from chhatri.domain.enums import PayoutStatus
from chhatri.domain.models import Alert, AreaTrigger, Payout
from chhatri.money import format_inr
from chhatri.replay.board import trigger_day
from chhatri.replay.feed import FEED_LIMIT, FeedItem
from chhatri.replay.live import LiveValues, live_values, rain_band
from chhatri.replay.view_records import iso, trigger_view

if TYPE_CHECKING:
    from chhatri.replay.state import Runtime

__all__ = [
    "CITY_NAME",
    "build_zone_snapshot",
    "clock_view",
    "feed_view",
    "kpis_view",
    "live",
    "snapshot",
    "zone_alert",
    "zone_label",
    "zone_snapshot",
    "zone_trigger",
]

CITY_NAME: Final = "Mumbai"
NO_DATA: Final = "—"
SECONDS_PER_MINUTE: Final = 60


def clock_view(rt: Runtime) -> dict[str, Any]:
    """ClockState (SPEC §19.2)."""
    now, scenario = rt.clock.now(), rt.scenario
    label = f"{CITY_NAME} · {scenario.name.replace('_', ' ')} replay · {now:%H:%M} · simulated"
    return {
        "now": iso(now),
        "scenario": scenario.name,
        "scenario_title": scenario.title,
        "running": rt.engine.running,
        "speed": float(rt.engine.speed),
        "start": iso(scenario.start),
        "end": iso(scenario.end),
        "label": label,
    }


def live(rt: Runtime) -> LiveValues:
    """Zone live indices and hex values now (B3)."""
    hours = rt.static.rules.area.consecutive_hours
    return live_values(rt.world, rt.static.city, rt.hex_index, rt.clock.now(), hours)


def zone_trigger(rt: Runtime, zone_id: str) -> AreaTrigger | None:
    """Today's trigger for the zone, if it fired."""
    today = rt.clock.now().date()
    return next((t for t in rt.store.triggers() if t.zone_id == zone_id and trigger_day(t) == today), None)


def zone_alert(rt: Runtime, zone_id: str) -> Alert | None:
    """The alert the zone card shows (see module docstring)."""
    trigger = zone_trigger(rt, zone_id)
    if trigger is not None:
        return rt.world.alert(trigger.alert_id)
    now = rt.clock.now()
    known = [a for a in rt.world.feed_alerts if zone_id in a.zone_ids and a.issued_at <= now < a.valid_to]
    return min(known, key=lambda a: (a.valid_from, a.id)) if known else None


def zone_label(zone_id: str, pct: int | None, shops: int) -> str:
    """The map label, e.g. Z7 · 37% · 46 shops (SPEC §20)."""
    return f"{zone_id} · {NO_DATA if pct is None else f'{pct}%'} · {shops} shops"


def _zone_alert_view(alert: Alert | None) -> dict[str, Any] | None:
    if alert is None:
        return None
    return {
        "id": alert.id,
        "level": alert.level.value,
        "kind": alert.kind.value,
        "valid_from": iso(alert.valid_from),
        "valid_to": iso(alert.valid_to),
        "headline_en": alert.headline_en,
    }


def build_zone_snapshot(rt: Runtime, zone_id: str, live_pct: int | None) -> dict[str, Any]:
    """ZoneSnapshot for a precomputed live index (one live pass serves every zone)."""
    zone = rt.static.city.geography.zone(zone_id)
    state = rt.board.states.get(zone_id)
    shops = rt.zone_shops[zone_id]
    trigger = zone_trigger(rt, zone_id)
    trailing = state.index_pct if state is not None else None
    shown = trigger.index_pct if trigger is not None else trailing
    return {
        "zone_id": zone_id,
        "ward": zone.ward,
        "name": zone.name,
        "shops": shops,
        "index_pct": trailing,
        "live_index_pct": live_pct,
        "lower_bound_pct": rt.world.lower_bounds[zone_id],
        "status": state.status if state is not None else "no_data",
        "hours_below": state.hours_below if state is not None else 0,
        "alert": _zone_alert_view(zone_alert(rt, zone_id)),
        "label": zone_label(zone_id, shown, shops),
    }


def zone_snapshot(rt: Runtime, zone_id: str) -> dict[str, Any]:
    """ZoneSnapshot (SPEC §19.2); KeyError for an unknown zone."""
    return build_zone_snapshot(rt, zone_id, live(rt).zones[zone_id])


def _area_minutes(rt: Runtime, payout: Payout) -> int | None:
    """Minutes from the area trigger to this credited payout; None for a personal payout."""
    claim = rt.store.claim(rt.store.decision(payout.decision_id).claim_id)
    trigger = rt.store.area_trigger(claim.trigger_id) if claim.trigger_id else None
    if trigger is None or payout.credited_at is None:
        return None
    return int((payout.credited_at - trigger.fired_at).total_seconds() // SECONDS_PER_MINUTE)


def kpis_view(rt: Runtime) -> dict[str, Any]:
    """Kpis (SPEC §19.2, §17.2: 3 zones · 312 shops · 4 min)."""
    credited = [p for p in rt.store.payouts() if p.status is PayoutStatus.CREDITED]
    minutes = [m for m in (_area_minutes(rt, p) for p in credited) if m is not None]
    total = sum(p.amount_paise for p in credited)
    return {
        "zones_triggered": len({t.zone_id for t in rt.store.triggers()}),
        "shops_paid": len({p.merchant_id for p in credited}),
        "trigger_to_money_min": max(minutes) if minutes else None,
        "total_paid_paise": total,
        "total_paid_label": format_inr(total),
        "instalments_paused": len(rt.store.pauses()),
    }


def feed_view(item: FeedItem) -> dict[str, Any]:
    """FeedItem (SPEC §19.2); optional keys are omitted, never null."""
    view: dict[str, Any] = {"id": item.id, "at": iso(item.at), "type": item.type, "text_en": item.text_en}
    if item.zone_id is not None:
        view["zone_id"] = item.zone_id
    if item.merchant_id is not None:
        view["merchant_id"] = item.merchant_id
    return view


def snapshot(rt: Runtime) -> dict[str, Any]:
    """StateSnapshot (SPEC §19.2)."""
    values = live(rt)
    return {
        "clock": clock_view(rt),
        "zones": [build_zone_snapshot(rt, z.id, values.zones[z.id]) for z in rt.static.city.zones],
        "hexes": dict(values.hexes),
        "kpis": kpis_view(rt),
        "triggers": [trigger_view(t) for t in rt.store.triggers()],
        "explanations": dict(rt.board.explanations),
        "feed": [feed_view(item) for item in rt.feed.latest(FEED_LIMIT)],
        "demo_merchant_id": rt.scenario.demo_merchant_id,
        "rain_band": rain_band(rt.world, rt.static.zones_geojson, rt.clock.now()),
    }
