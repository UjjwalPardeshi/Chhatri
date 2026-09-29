"""Shared simulation value types (SPEC §6.1, §24.1). Scaffold — read-only for builders.

These are plain frozen containers so the forecast, detect, replay and backtest packages can be built
and tested against them before the simulator exists.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from types import MappingProxyType

import numpy as np

from chhatri.clock import require_aware
from chhatri.domain.models import Alert, Cover, Loan, Merchant, Zone

HOUR = timedelta(hours=1)


def _freeze(mapping: Mapping) -> Mapping:
    return mapping if isinstance(mapping, MappingProxyType) else MappingProxyType(dict(mapping))


@dataclass(frozen=True, slots=True)
class Hex:
    h3: str
    zone_id: str
    center_lat: float
    center_lng: float


@dataclass(frozen=True, slots=True)
class Geography:
    zones: tuple[Zone, ...]
    zones_geojson: dict
    hexes: tuple[Hex, ...]
    hexes_geojson: dict

    def zone(self, zone_id: str) -> Zone:
        for zone in self.zones:
            if zone.id == zone_id:
                return zone
        raise KeyError(zone_id)


@dataclass(frozen=True, slots=True)
class ShopProfile:
    merchant_id: str
    base_day_paise: int
    open_hour: int
    close_hour: int
    hour_weights: tuple[float, ...]
    dow_mult: tuple[float, ...]
    rain_sensitivity: float
    avg_ticket_paise: int

    def __post_init__(self) -> None:
        if len(self.hour_weights) != 24 or len(self.dow_mult) != 7:
            raise ValueError("hour_weights needs 24 values and dow_mult 7")
        if not 0 <= self.open_hour < self.close_hour <= 24:
            raise ValueError("business hours must satisfy 0 <= open < close <= 24")

    def is_business_hour(self, hour: int) -> bool:
        return self.open_hour <= hour < self.close_hour


@dataclass(frozen=True, slots=True)
class City:
    seed: int
    geography: Geography
    merchants: tuple[Merchant, ...]
    profiles: Mapping[str, ShopProfile]
    covers: Mapping[str, Cover]
    loans: Mapping[str, Loan]
    _rows: Mapping[str, int] = field(init=False, repr=False, compare=False)
    _zone_rows: Mapping[str, tuple[int, ...]] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        ids = [m.id for m in self.merchants]
        if ids != sorted(ids) or len(set(ids)) != len(ids):
            raise ValueError("merchants must be unique and sorted by id")
        rows = {mid: i for i, mid in enumerate(ids)}
        zone_rows: dict[str, list[int]] = {}
        for i, merchant in enumerate(self.merchants):
            zone_rows.setdefault(merchant.zone_id, []).append(i)
        object.__setattr__(self, "profiles", _freeze(self.profiles))
        object.__setattr__(self, "covers", _freeze(self.covers))
        object.__setattr__(self, "loans", _freeze(self.loans))
        object.__setattr__(self, "_rows", MappingProxyType(rows))
        object.__setattr__(self, "_zone_rows", MappingProxyType({z: tuple(r) for z, r in zone_rows.items()}))

    @property
    def zones(self) -> tuple[Zone, ...]:
        return self.geography.zones

    def merchant(self, merchant_id: str) -> Merchant:
        return self.merchants[self._rows[merchant_id]]

    def row(self, merchant_id: str) -> int:
        return self._rows[merchant_id]

    def zone_rows(self, zone_id: str) -> tuple[int, ...]:
        return self._zone_rows.get(zone_id, ())

    def merchants_in_zone(self, zone_id: str) -> tuple[Merchant, ...]:
        return tuple(self.merchants[i] for i in self.zone_rows(zone_id))


@dataclass(frozen=True, slots=True)
class SalesPanel:
    """Hourly sales for M merchants over H contiguous hours. Row order = City.merchants order.

    Hour h covers [start + h, start + h + 1). Arrays are read-only views.
    """

    merchant_ids: tuple[str, ...]
    start: datetime
    hours: int
    amount_paise: np.ndarray  # (M, H) int64
    txns: np.ndarray  # (M, H) int32

    def __post_init__(self) -> None:
        start = require_aware(self.start)
        if start.minute or start.second or start.microsecond:
            raise ValueError("SalesPanel.start must be on an hour boundary")
        expected = (len(self.merchant_ids), self.hours)
        if self.amount_paise.shape != expected or self.txns.shape != expected:
            raise ValueError(f"arrays must have shape {expected}")
        amount = np.asarray(self.amount_paise, dtype=np.int64)
        txns = np.asarray(self.txns, dtype=np.int32)
        amount.setflags(write=False)
        txns.setflags(write=False)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "amount_paise", amount)
        object.__setattr__(self, "txns", txns)

    @property
    def end(self) -> datetime:
        return self.start + self.hours * HOUR

    def hour_index(self, ts: datetime) -> int:
        """Index of the hour containing `ts`. Raises IndexError outside the panel."""
        delta = require_aware(ts) - self.start
        idx = int(delta // HOUR)
        if not 0 <= idx < self.hours:
            raise IndexError(f"{ts.isoformat()} outside panel [{self.start.isoformat()}, {self.end.isoformat()})")
        return idx

    def window(self, start: datetime, end: datetime) -> SalesPanel:
        """Sub-panel for the half-open hour range [start, end); both on hour boundaries."""
        i = self.hour_index(start)
        if end <= start:
            raise ValueError("window end must be after start")
        j = i + int((require_aware(end) - require_aware(start)) // HOUR)
        if j > self.hours:
            raise IndexError("window extends past the panel")
        return SalesPanel(self.merchant_ids, self.start + i * HOUR, j - i, self.amount_paise[:, i:j], self.txns[:, i:j])

    def day(self, day: date) -> SalesPanel:
        from chhatri.clock import at

        return self.window(at(day, 0), at(day, 0) + 24 * HOUR)


@dataclass(frozen=True, slots=True)
class GroundTruth:
    zone_day_loss_pct: Mapping[tuple[str, date], float]
    zone_day_label: Mapping[tuple[str, date], str]
    closures: Mapping[str, tuple[tuple[date, date], ...]]


@dataclass(frozen=True, slots=True)
class ScenarioOverrides:
    rain_mm: Mapping[tuple[str, date], tuple[float, ...]] = field(default_factory=dict)
    alerts: tuple[Alert, ...] = ()
    slow_days: Mapping[tuple[str, date], float] = field(default_factory=dict)
    closures: Mapping[str, tuple[tuple[date, date], ...]] = field(default_factory=dict)
    quiet_days: tuple[date, ...] = ()


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    title: str
    day: date
    start: datetime
    end: datetime
    demo_merchant_id: str
    overrides: ScenarioOverrides
    history_start: date
    slip_sample: str | None = None


@dataclass(frozen=True, slots=True)
class Calibration:
    """Output of scripts/calibrate.py (SPEC §17.4). Defaults are the pre-calibration guesses."""

    anil_base_day_paise: int = 420_000
    zone_rain_scale: Mapping[str, float] = field(default_factory=lambda: {"Z3": 1.0, "Z7": 1.0, "Z12": 1.0})
    z9_slow_depth: float = 0.39
    z7_other_scale: float = 1.0
    z7_tune_merchant_id: str | None = None
    z7_tune_base_day_paise: int | None = None
