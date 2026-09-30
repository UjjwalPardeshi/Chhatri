"""SPEC §19.2 ZonePanel with the exact deck rows of SPEC §17.2 (deck slide 6).

Rows, in order (Paid and Total only once the zone has triggered today):
- Alert: "Red alert from 14:00" (level, then the alert's start; "Red alert from Tue 14:00" when it
  starts on another day), or "No weather alert".
- Sales: "37% of expected for 3 hours" — the trigger's window index for a triggered zone, else
  the trailing index at floor_hour(now); "No sales data yet" without data.
- Cover: "46 of 46 prepaid" — covered pilot shops whose premium is prepaid through today.
- Paid: "17:04, with the settlement" once the first payout is credited, "Due 17:04, with the
  settlement" before, "No payouts" when every claim was declined.
- Total: "₹58,900 · instalments paused" — credited amount (approved amount while pending), with
  " · instalments paused" once any instalment of these payouts is paused.
`hourly` lists every completed hour of the replay (from the scenario's start hour) with the zone's
hourly index (B4: nothing from the hour in progress).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, Final

from chhatri.clock import IST, floor_hour
from chhatri.detect.area_index import index_rows, window_index
from chhatri.domain.enums import DecisionOutcome, PayoutStatus
from chhatri.domain.models import Alert, AreaTrigger, Decision, Payout
from chhatri.money import format_inr
from chhatri.replay.fmt import hhmm, weekday_short
from chhatri.replay.view_live import build_zone_snapshot, live, zone_alert, zone_trigger
from chhatri.replay.view_records import iso

if TYPE_CHECKING:
    from chhatri.replay.state import Runtime

__all__ = ["alert_row", "zone_panel"]

HOUR: Final = timedelta(hours=1)
NO_ALERT: Final = "No weather alert"
NO_SALES: Final = "No sales data yet"
NO_PAYOUTS: Final = "No payouts"
PAUSED_SUFFIX: Final = " · instalments paused"


def alert_row(alert: Alert | None, today: date) -> str:
    """The Alert row: Red alert from 14:00, Red alert from Tue 14:00, or No weather alert (SPEC §17.2)."""
    if alert is None:
        return NO_ALERT
    start = alert.valid_from.astimezone(IST)
    when = hhmm(start) if start.date() == today else f"{weekday_short(start.date())} {hhmm(start)}"
    return f"{alert.level.value.title()} alert from {when}"


def _trigger_payouts(rt: Runtime, trigger: AreaTrigger) -> tuple[list[Payout], int]:
    """(payouts of the trigger's approved claims, Σ approved amount)."""
    payouts: list[Payout] = []
    approved = 0
    for decision in _trigger_decisions(rt, trigger):
        approved += decision.amount_paise
        payout = rt.store.payout_for_decision(decision.id)
        if payout is not None:
            payouts.append(payout)
    return payouts, approved


def _trigger_decisions(rt: Runtime, trigger: AreaTrigger) -> list[Decision]:
    decisions: list[Decision] = []
    for merchant in rt.static.city.merchants_in_zone(trigger.zone_id):
        for decision in rt.store.decisions_for(merchant.id):
            if decision.outcome is not DecisionOutcome.APPROVED:
                continue
            if rt.store.claim(decision.claim_id).trigger_id == trigger.id:
                decisions.append(decision)
    return decisions


def _paid_rows(rt: Runtime, trigger: AreaTrigger) -> tuple[list[dict[str, str]], list[Payout]]:
    payouts, approved = _trigger_payouts(rt, trigger)
    credited = [p for p in payouts if p.status is PayoutStatus.CREDITED]
    if credited:
        first = min(p.credited_at for p in credited if p.credited_at is not None)
        paid = f"{hhmm(first)}, with the settlement"
        total = sum(p.amount_paise for p in credited)
    elif approved:
        due = trigger.fired_at + timedelta(minutes=rt.static.rules.payout_rail_delay_minutes)
        paid, total = f"Due {hhmm(due)}, with the settlement", approved
    else:
        paid, total = NO_PAYOUTS, 0
    decision_ids = {p.decision_id for p in payouts}
    paused = any(pause.decision_id in decision_ids for pause in rt.store.pauses())
    total_text = format_inr(total) + (PAUSED_SUFFIX if paused else "")
    return [{"label": "Paid", "value": paid}, {"label": "Total", "value": total_text}], credited


def _cover_row(rt: Runtime, zone_id: str, today: date) -> dict[str, str]:
    covered = [mid for mid in rt.static.city.covers if rt.static.city.merchant(mid).zone_id == zone_id]
    prepaid = 0
    for merchant_id in covered:
        cover = rt.store.cover(merchant_id)
        if cover is not None and cover.prepaid_through is not None and cover.prepaid_through >= today:
            prepaid += 1
    return {"label": "Cover", "value": f"{prepaid} of {rt.zone_shops[zone_id]} prepaid"}


def _sales_row(rt: Runtime, zone_id: str, trigger: AreaTrigger | None) -> dict[str, str]:
    state = rt.board.states.get(zone_id)
    pct = trigger.index_pct if trigger is not None else (state.index_pct if state is not None else None)
    hours = rt.static.rules.area.consecutive_hours
    value = NO_SALES if pct is None else f"{pct}% of expected for {hours} hours"
    return {"label": "Sales", "value": value}


def _hourly(rt: Runtime, zone_id: str) -> list[dict[str, Any]]:
    now = rt.clock.now()
    first, last = floor_hour(rt.scenario.start), floor_hour(now)
    if last <= first:
        return []
    visible = rt.world.visible(now)
    rows_out = []
    hour = first
    while hour < last:
        rows = index_rows(rt.static.city, zone_id, hour, hour + HOUR)
        pct = window_index(visible, rt.world.p50, rows, hour, hour + HOUR)[2]
        rows_out.append({"hour": iso(hour), "index_pct": pct})
        hour += HOUR
    return rows_out


def zone_panel(rt: Runtime, zone_id: str) -> dict[str, Any]:
    """ZonePanel (SPEC §19.2, exact §17.2 strings); KeyError for an unknown zone."""
    snapshot = build_zone_snapshot(rt, zone_id, live(rt).zones[zone_id])
    today = rt.clock.now().date()
    trigger = zone_trigger(rt, zone_id)
    rows = [
        {"label": "Alert", "value": alert_row(zone_alert(rt, zone_id), today)},
        _sales_row(rt, zone_id, trigger),
        _cover_row(rt, zone_id, today),
    ]
    credited: list[Payout] = []
    if trigger is not None:
        paid_rows, credited = _paid_rows(rt, trigger)
        rows.extend(paid_rows)
    total = sum(p.amount_paise for p in credited)
    return {
        "zone": snapshot,
        "triggered": trigger is not None,
        "rows": rows,
        "explanation": rt.board.explanations.get(zone_id),
        "shops_paid": len({p.merchant_id for p in credited}),
        "total_paid_paise": total,
        "total_paid_label": format_inr(total),
        "hourly": _hourly(rt, zone_id),
    }
