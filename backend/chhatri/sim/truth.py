"""Ground truth for the backtest (SPEC §6.3, §18, §24.1).

- ``zone_day_loss_pct[(zone, day)] = 1 - Σ actual / Σ counterfactual`` over the zone's covered
  shops (both from `SalesSimulator`, same noise); 0.0 when the counterfactual is 0. Zones with no
  covered shop are omitted.
- ``zone_day_label`` from the shock calendar, by precedence bandh > slow_day > rain > normal,
  where "rain" means any hour of the day has a rain impact (r3 > 0, including rain in the last
  two hours of the previous day).
- ``closures``: merchant -> closure ranges clipped to the requested days (merchants with none are
  omitted).
"""

from __future__ import annotations

from datetime import date, timedelta
from types import MappingProxyType
from typing import TYPE_CHECKING

import numpy as np

from chhatri.clock import at
from chhatri.sim.rainfall import HOURS
from chhatri.sim.types import HOUR, GroundTruth

if TYPE_CHECKING:
    from chhatri.sim.sales import SalesSimulator
    from chhatri.sim.weather import ShockCalendar

TRAILING_HOURS = 3
LABEL_BANDH = "bandh"
LABEL_SLOW = "slow_day"
LABEL_RAIN = "rain"
LABEL_NORMAL = "normal"


def _zone_sums(totals: np.ndarray, zone_row: np.ndarray, covered: np.ndarray, n_zones: int) -> np.ndarray:
    """(Z, days) Σ over covered merchants of each zone."""
    onehot = np.zeros((n_zones, totals.shape[0]), dtype=np.int64)
    onehot[zone_row[covered], np.flatnonzero(covered)] = 1
    return onehot @ totals


def _rain_days(shocks: ShockCalendar, start_day: date, days: int) -> np.ndarray:
    """(Z, days) bool: any hour of the day with r3 > 0."""
    rain = shocks.zone_rain(at(start_day, 0) - (TRAILING_HOURS - 1) * HOUR, HOURS * days + TRAILING_HOURS - 1)
    r3 = np.lib.stride_tricks.sliding_window_view(rain, TRAILING_HOURS, axis=1).sum(axis=2)
    return (r3 > 0).reshape(rain.shape[0], days, HOURS).any(axis=2)


def _label(bandh: bool, slow: float, rain: bool) -> str:
    if bandh:
        return LABEL_BANDH
    if slow > 0:
        return LABEL_SLOW
    return LABEL_RAIN if rain else LABEL_NORMAL


def _clipped(ranges: tuple[tuple[date, date], ...], first: date, last: date) -> tuple[tuple[date, date], ...]:
    return tuple((max(s, first), min(e, last)) for s, e in ranges if s <= last and e >= first)


def build_ground_truth(
    sim: SalesSimulator, shocks: ShockCalendar, start_day: date, end_day: date
) -> GroundTruth:
    """GroundTruth for the inclusive day range (see module docstring)."""
    if end_day < start_day:
        raise ValueError(f"end_day {end_day} is before start_day {start_day}")
    days = (end_day - start_day).days + 1
    city = sim.city
    zone_ids = shocks.zone_ids
    zone_index = {z: i for i, z in enumerate(zone_ids)}
    zone_row = np.array([zone_index[m.zone_id] for m in city.merchants], dtype=np.intp)
    covered = np.array([m.id in city.covers for m in city.merchants], dtype=bool)
    actual = _zone_sums(sim.daily_totals(start_day, end_day, shocked=True), zone_row, covered, len(zone_ids))
    baseline = _zone_sums(
        sim.daily_totals(start_day, end_day, shocked=False), zone_row, covered, len(zone_ids)
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        loss = np.where(baseline > 0, 1.0 - actual / np.where(baseline > 0, baseline, 1), 0.0)
    rain = _rain_days(shocks, start_day, days)
    slow = shocks.slow_depths(start_day, days)
    zones_with_shops = sorted(set(zone_row[covered].tolist()))
    losses: dict[tuple[str, date], float] = {}
    labels: dict[tuple[str, date], str] = {}
    for d in range(days):
        day = start_day + timedelta(days=d)
        bandh = shocks.is_bandh(day)
        for z in zones_with_shops:
            losses[(zone_ids[z], day)] = float(loss[z, d])
            labels[(zone_ids[z], day)] = _label(bandh, float(slow[z, d]), bool(rain[z, d]))
    closures = {m.id: _clipped(shocks.closures(m.id), start_day, end_day) for m in city.merchants}
    return GroundTruth(
        zone_day_loss_pct=MappingProxyType(losses),
        zone_day_label=MappingProxyType(labels),
        closures=MappingProxyType({m: r for m, r in closures.items() if r}),
    )
