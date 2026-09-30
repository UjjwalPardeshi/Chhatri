"""Area trigger evaluation and zone status (SPEC §8.2, §24.2).

At hour boundary t, with n = rules.area.consecutive_hours (3) and window [t − n h, t), a zone
triggers when ALL hold (all comparisons strictly less than):
(a) a RAIN or CIVIC alert for the zone, already issued at t, is valid for the whole window;
(b) each of the n completed hourly indices < index_floor_pct AND the window index < the zone's
    lower_bound_pct;
(c) shops_in_index ≥ min_shops_in_index;
(d) (zone, day) is not in `already_triggered`, where day = date of the last completed hour.
Indices are computed over the zone's covered, open merchants (see `area_index`), identically to
`zone_window`. Zone status (first match wins):
- `triggered`: fired now, or already triggered that day (the map keeps the zone red for the day);
- `no_data`: fewer than min_shops_in_index shops, or nothing expected in the window;
- `watch`: an alert is valid for the last completed hour and hours_below ≥ 1 (SPEC: 1–2 hours
  below floor with alert; 3 hours without a trigger — e.g. the window is not all under the alert
  — also stays `watch`);
- `slow_day`: no alert for the last completed hour and (window index < lower bound or
  hours_below ≥ 1) — the Z9 case of SPEC §17.2;
- `normal` otherwise.
`hours_below` counts consecutive completed hours below the floor, newest backwards, alert or not.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from types import MappingProxyType
from typing import Final

import numpy as np

from chhatri.clock import floor_hour, require_aware
from chhatri.detect.area_index import check_expected, hourly_sums, ratio
from chhatri.detect.city_arrays import arrays_for, open_hours
from chhatri.detect.types import ZoneState, ZoneStatusName
from chhatri.domain.enums import AlertKind
from chhatri.domain.models import Alert, AreaTrigger
from chhatri.forecast.rounding import round_paise
from chhatri.ids import IdFactory
from chhatri.policy.rules import PolicyRules
from chhatri.sim.types import City, SalesPanel

HOUR: Final = timedelta(hours=1)
TRIGGER_ALERT_KINDS: Final = frozenset({AlertKind.RAIN, AlertKind.CIVIC})
FULL_PCT: Final = 100  # SPEC §4.3: drop_pct = 100 − index_pct


def alert_for(
    alerts: Sequence[Alert], zone_id: str, start: datetime, end: datetime, now: datetime
) -> Alert | None:
    """The earliest-issued (then lowest id) RAIN/CIVIC alert issued by `now` valid for all of [start, end)."""
    matches = [
        a
        for a in alerts
        if a.kind in TRIGGER_ALERT_KINDS and a.issued_at <= now and a.covers(zone_id, start, end)
    ]
    return min(matches, key=lambda a: (a.issued_at, a.id)) if matches else None


def _hours_below(hourly: Sequence[int | None], floor: int) -> int:
    count = 0
    for value in reversed(hourly):
        if value is None or value >= floor:
            break
        count += 1
    return count


def _status(
    *,
    fired: bool,
    done: bool,
    quorum: bool,
    window: int | None,
    lower: int,
    alert_last_hour: bool,
    below: int,
) -> ZoneStatusName:
    if fired or done:
        return "triggered"
    if not quorum or window is None:
        return "no_data"
    if alert_last_hour:
        return "watch" if below >= 1 else "normal"
    return "slow_day" if (window < lower or below >= 1) else "normal"


def _zone_indices(
    actual: SalesPanel, expected_p50: np.ndarray, rows: np.ndarray, i: int, j: int
) -> tuple[tuple[int | None, ...], int | None]:
    act, exp = hourly_sums(actual, expected_p50, rows, i, j)
    hourly = tuple(ratio(int(a), round_paise(float(e))) for a, e in zip(act, exp, strict=True))
    return hourly, ratio(int(act.sum()), round_paise(float(exp.sum())))


def _evaluate_zone(ctx: _Context, zone_id: str, rows: np.ndarray) -> tuple[ZoneState, AreaTrigger | None]:
    hourly, window = _zone_indices(ctx.actual, ctx.expected_p50, rows, ctx.i, ctx.j)
    area = ctx.rules.area
    try:
        lower = ctx.lower_bounds[zone_id]
    except KeyError:
        raise ValueError(f"lower_bounds has no entry for zone {zone_id}") from None
    below = _hours_below(hourly, area.index_floor_pct)
    quorum = rows.size >= area.min_shops_in_index
    window_alert = alert_for(ctx.alerts, zone_id, ctx.start, ctx.at, ctx.at)
    last_alert = alert_for(ctx.alerts, zone_id, ctx.at - HOUR, ctx.at, ctx.at)
    done = (zone_id, ctx.day) in ctx.already_triggered
    fired_alert = window_alert if below == len(hourly) and quorum and not done else None
    trigger = None
    if fired_alert is not None and window is not None and window < lower:
        trigger = _trigger(ctx, zone_id, fired_alert, hourly, window, lower, rows.size)
    fired = trigger is not None
    status = _status(
        fired=fired,
        done=done,
        quorum=quorum,
        window=window,
        lower=lower,
        alert_last_hour=last_alert is not None,
        below=below,
    )
    shown_alert = window_alert if fired else last_alert
    state = ZoneState(
        zone_id=zone_id,
        status=status,
        index_pct=window,
        hourly_pct=hourly,
        hours_below=below,
        alert_id=shown_alert.id if shown_alert else None,
        shops_in_index=int(rows.size),
        lower_bound_pct=lower,
    )
    return state, trigger


def _trigger(
    ctx: _Context,
    zone_id: str,
    alert: Alert,
    hourly: tuple[int | None, ...],
    window: int,
    lower: int,
    shops: int,
) -> AreaTrigger:
    """The trigger record; every hourly index is an int here because all hours were below the floor."""
    return AreaTrigger(
        id=IdFactory.area_trigger(zone_id, ctx.day),
        zone_id=zone_id,
        alert_id=alert.id,
        window_start=ctx.start,
        window_end=ctx.at,
        index_pct=window,
        drop_pct=FULL_PCT - window,
        hourly_index_pct=tuple(int(h) for h in hourly if h is not None),
        lower_bound_pct=lower,
        shops_in_index=shops,
        fired_at=ctx.at,
    )


@dataclass(frozen=True, slots=True)
class _Context:
    """Inputs shared by every zone of one evaluation."""

    at: datetime
    start: datetime
    day: date
    actual: SalesPanel
    expected_p50: np.ndarray
    alerts: tuple[Alert, ...]
    lower_bounds: Mapping[str, int]
    rules: PolicyRules
    already_triggered: frozenset[tuple[str, date]]
    i: int
    j: int

    @classmethod
    def build(
        cls,
        at: datetime,
        actual: SalesPanel,
        expected_p50: np.ndarray,
        alerts: Sequence[Alert],
        lower_bounds: Mapping[str, int],
        rules: PolicyRules,
        already_triggered: frozenset[tuple[str, date]],
    ) -> _Context:
        hours = rules.area.consecutive_hours
        start = at - hours * HOUR
        i = actual.hour_index(start)
        if i + hours > actual.hours:
            raise IndexError(
                f"window ending {at.isoformat()} extends past the panel end {actual.end.isoformat()}"
            )
        return cls(
            at,
            start,
            (at - HOUR).date(),
            actual,
            expected_p50,
            tuple(alerts),
            lower_bounds,
            rules,
            already_triggered,
            i,
            i + hours,
        )


def evaluate_hour(
    at: datetime,
    city: City,
    actual: SalesPanel,
    expected_p50: np.ndarray,
    alerts: Sequence[Alert],
    lower_bounds: Mapping[str, int],
    rules: PolicyRules,
    already_triggered: frozenset[tuple[str, date]],
) -> tuple[tuple[AreaTrigger, ...], Mapping[str, ZoneState]]:
    """Evaluate every zone for the window ending at hour boundary `at` (SPEC §8.2).

    Raises ValueError when `at` is not on an hour boundary or inputs are inconsistent, IndexError
    when the window is not inside the actual panel. Returns (triggers in zone order, states by zone).
    """
    at = require_aware(at)
    if floor_hour(at) != at:
        raise ValueError(f"evaluate_hour needs an hour boundary, got {at.isoformat()}")
    check_expected(actual, expected_p50)
    ctx = _Context.build(at, actual, expected_p50, alerts, lower_bounds, rules, already_triggered)
    arrays = arrays_for(city)
    covered = np.flatnonzero(arrays.covered)
    members = covered[open_hours(city, covered, ctx.start, ctx.j - ctx.i).any(axis=1)]
    triggers: list[AreaTrigger] = []
    states: dict[str, ZoneState] = {}
    for code, zone in enumerate(city.zones):
        state, trigger = _evaluate_zone(ctx, zone.id, members[arrays.zone_code[members] == code])
        states[zone.id] = state
        if trigger is not None:
            triggers.append(trigger)
    return tuple(triggers), MappingProxyType(states)
