"""Live map values: zone live index, hex values and the rain band (SPEC §8.1, §19.2; B3, B4).

Binding decision B3, with t = floor_hour(now) and f = minutes past t / 60:
- zone live index = the sliding 3-hour window ending at `now` over the zone's covered merchants
  that are scheduled open in the span: completed hours count fully except the oldest, weighted
  (1 − f), and the hour in progress is weighted f, in actual and expected alike
  (`chhatri.detect.area_index.live_window_index`); at f = 0 it equals the trailing index;
- hex value = the same live index over the hex's own covered open merchants when at least
  `MIN_HEX_SHOPS` contribute and something is expected there, otherwise the zone's live index;
  null when the zone itself has no data (nothing expected);
- rain band = the ward polygons of zones with rain > 0 in the hour in progress, else None.
B4: only `ScenarioData.live_panel` is read, so the hour in progress enters pro-rated and nothing
after it is visible.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any, Final

import numpy as np

from chhatri.clock import floor_hour, require_aware
from chhatri.detect.area_index import live_window_index
from chhatri.detect.city_arrays import arrays_for, open_hours
from chhatri.forecast.rounding import round_half_up
from chhatri.replay.world import ScenarioData
from chhatri.sim.types import City

__all__ = ["MIN_HEX_SHOPS", "HexIndex", "LiveValues", "live_values", "rain_band"]

MIN_HEX_SHOPS: Final = 3
HOUR: Final = timedelta(hours=1)
SECONDS_PER_HOUR: Final = 3600.0
PERCENT: Final = 100


@dataclass(frozen=True, slots=True)
class HexIndex:
    """Row → hex position and hex → zone position, in `city.geography.hexes` order."""

    hex_ids: tuple[str, ...]
    hex_zone: np.ndarray  # (H,) index into city.zones
    row_hex: np.ndarray  # (M,) index into hex_ids

    @classmethod
    def build(cls, city: City) -> HexIndex:
        position = {hx.h3: i for i, hx in enumerate(city.geography.hexes)}
        zone_pos = {z.id: i for i, z in enumerate(city.zones)}
        missing = [m.id for m in city.merchants if m.h3_cell not in position]
        if missing:
            raise ValueError(f"merchants outside the hex grid: {missing[:5]}")
        return cls(
            hex_ids=tuple(hx.h3 for hx in city.geography.hexes),
            hex_zone=np.array([zone_pos[hx.zone_id] for hx in city.geography.hexes], dtype=np.int64),
            row_hex=np.array([position[m.h3_cell] for m in city.merchants], dtype=np.int64),
        )


@dataclass(frozen=True, slots=True)
class LiveValues:
    """Live index per zone and value per hex at one moment."""

    zones: Mapping[str, int | None]
    hexes: Mapping[str, int | None]


def _span(now: datetime, hours: int) -> tuple[datetime, int, np.ndarray]:
    """Start, length in hours and per-hour weights of the live window ending at `now`."""
    t = floor_hour(now)
    f = (require_aware(now) - t).total_seconds() / SECONDS_PER_HOUR
    if f == 0.0:
        return t - hours * HOUR, hours, np.ones(hours)
    weights = np.ones(hours + 1)
    weights[0], weights[-1] = 1.0 - f, f
    return t - hours * HOUR, hours + 1, weights


def _members(city: City, start: datetime, hours: int) -> np.ndarray:
    """(M,) covered merchants scheduled open in at least one hour of the span."""
    arrays = arrays_for(city)
    rows = np.arange(len(city.merchants), dtype=np.int64)
    return arrays.covered & open_hours(city, rows, start, hours).any(axis=1)


def _percent(actual: np.ndarray, expected: np.ndarray) -> np.ndarray:
    """Element-wise integer percent, half up, of non-negative paise; −1 where expected is 0."""
    safe = np.where(expected > 0, expected, 1)
    return np.where(expected > 0, (2 * PERCENT * actual + safe) // (2 * safe), -1)


def live_values(world: ScenarioData, city: City, index: HexIndex, now: datetime, hours: int) -> LiveValues:
    """Zone live indices and hex values at `now` (B3)."""
    start, span, weights = _span(now, hours)
    actual = world.live_panel(now)
    members = _members(city, start, span)
    zone_code = arrays_for(city).zone_code
    zones: dict[str, int | None] = {}
    for code, zone in enumerate(city.zones):
        rows = np.flatnonzero(members & (zone_code == code))
        zones[zone.id] = live_window_index(actual, world.p50, rows, now, hours)[2]
    i = actual.hour_index(start)
    act = actual.amount_paise[:, i : i + span].astype(np.float64) @ weights
    exp = np.asarray(world.p50[:, i : i + span], dtype=np.float64) @ weights
    hex_of = index.row_hex[members]
    n_hex = len(index.hex_ids)
    count = np.bincount(hex_of, minlength=n_hex)
    hex_act = round_half_up(np.bincount(hex_of, weights=act[members], minlength=n_hex))
    hex_exp = round_half_up(np.bincount(hex_of, weights=exp[members], minlength=n_hex))
    own = np.where(count >= MIN_HEX_SHOPS, _percent(hex_act, hex_exp), -1)
    zone_values = [zones[city.zones[int(z)].id] for z in index.hex_zone]
    hexes = {
        h3: (None if zone_value is None else (int(value) if value >= 0 else zone_value))
        for h3, value, zone_value in zip(index.hex_ids, own, zone_values, strict=True)
    }
    return LiveValues(zones=MappingProxyType(zones), hexes=MappingProxyType(hexes))


def rain_band(world: ScenarioData, zones_geojson: Mapping[str, Any], now: datetime) -> dict[str, Any] | None:
    """FeatureCollection of the ward polygons of zones raining in the hour in progress (B3)."""
    t = floor_hour(now)
    rain = world.shocks.rain_for_day(t.date())[:, t.hour]
    raining = {zone_id for zone_id, mm in zip(world.shocks.zone_ids, rain, strict=True) if mm > 0}
    features = [f for f in zones_geojson["features"] if f["properties"]["id"] in raining]
    return {"type": "FeatureCollection", "features": features} if features else None
