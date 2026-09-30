"""Synthetic City / SalesPanel builders for forecast and detect tests (SPEC §5.3, §6.2 shapes).

Independent of `chhatri.sim` so the model and detection logic can be tested fast and exactly.
Everything is a deterministic function of the arguments.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta

import numpy as np

from chhatri.clock import at, ist
from chhatri.domain.enums import AlertKind, AlertLevel, CoverStatus, ShopType
from chhatri.domain.models import Alert, Cover, Merchant, Zone
from chhatri.sim.types import City, Geography, SalesPanel, ShopProfile

# (median day ₹, avg ticket ₹, open, close) — SPEC §5.3
SHOP_TABLE: dict[ShopType, tuple[int, int, int, int]] = {
    ShopType.TEA_STALL: (4_000, 18, 6, 22),
    ShopType.STREET_FOOD: (6_000, 45, 10, 23),
    ShopType.FRUIT_VEG: (5_000, 60, 7, 21),
    ShopType.KIRANA: (9_000, 120, 7, 22),
    ShopType.PHARMACY: (12_000, 250, 8, 23),
    ShopType.SALON: (3_500, 150, 9, 21),
    ShopType.MOBILE_RECHARGE: (3_000, 100, 9, 21),
}
TYPES = tuple(ShopType)


def hour_weights(open_hour: int, close_hour: int) -> tuple[float, ...]:
    """A two-peak curve over business hours, zero outside, summing to 1."""
    hours = np.arange(24, dtype=np.float64)
    curve = np.exp(-((hours - 9.0) ** 2) / 8.0) + 1.2 * np.exp(-((hours - 18.0) ** 2) / 6.0) + 0.3
    curve[(hours < open_hour) | (hours >= close_hour)] = 0.0
    return tuple(float(v) for v in curve / curve.sum())


def make_city(
    zone_sizes: Sequence[tuple[str, int]] = (("Z1", 25), ("Z2", 25), ("Z3", 25)),
    *,
    seed: int = 7,
    weekly_off_every: int = 0,
    uncovered: frozenset[str] = frozenset(),
    extra_zones: Sequence[str] = (),
) -> City:
    """Merchants S-0001.. spread over the zones; every `weekly_off_every`-th merchant has a weekly off."""
    rng = np.random.default_rng(seed)
    zone_ids = sorted({z for z, _ in zone_sizes} | set(extra_zones), key=lambda z: int(z[1:]))
    zones = tuple(
        Zone(id=z, ward=f"W{z}", name=f"Zone {z}", centroid_lat=19.0, centroid_lng=72.8) for z in zone_ids
    )
    merchants, profiles, covers = [], {}, {}
    i = 0
    for zone_id, count in zone_sizes:
        for _ in range(count):
            i += 1
            mid = f"S-{i:04d}"
            shop_type = TYPES[i % len(TYPES)]
            median, ticket, open_hour, close_hour = SHOP_TABLE[shop_type]
            off = (i % 7) if weekly_off_every and i % weekly_off_every == 0 else None
            merchants.append(_merchant(mid, zone_id, shop_type, off))
            base = int(median * 100 * float(rng.lognormal(0.0, 0.3)))
            dow = tuple(float(v) for v in 1.0 + 0.1 * np.sin(np.arange(7) + i))
            profiles[mid] = ShopProfile(
                mid, base, open_hour, close_hour, hour_weights(open_hour, close_hour), dow, 0.8, ticket * 100
            )
            if mid not in uncovered:
                covers[mid] = _cover(mid)
    geography = Geography(
        zones=zones,
        zones_geojson={"type": "FeatureCollection", "features": []},
        hexes=(),
        hexes_geojson={"type": "FeatureCollection", "features": []},
    )
    return City(
        seed=seed, geography=geography, merchants=tuple(merchants), profiles=profiles, covers=covers, loans={}
    )


def _merchant(mid: str, zone_id: str, shop_type: ShopType, weekly_off: int | None) -> Merchant:
    return Merchant(
        id=mid,
        shop_name=f"Shop {mid}",
        owner_name=f"Owner {mid}",
        owner_name_hi="मालिक",
        kyc_name=f"OWNER {mid}",
        phone=f"+91990000{int(mid[2:]):04d}",
        zone_id=zone_id,
        lat=19.0,
        lng=72.8,
        h3_cell=f"88{zone_id}",
        shop_type=shop_type,
        weekly_off=weekly_off,
    )


def _cover(mid: str) -> Cover:
    return Cover(
        id=f"CV-{mid}",
        merchant_id=mid,
        purchased_at=ist(2024, 1, 1),
        starts_on=date(2024, 1, 8),
        premium_per_day_paise=500,
        prepaid_through=date(2026, 1, 1),
        status=CoverStatus.ACTIVE,
    )


def make_panel(
    city: City,
    first_day: date,
    days: int,
    *,
    seed: int = 11,
    closures: Mapping[str, Sequence[date]] | None = None,
    zone_dips: Mapping[tuple[str, date], float] | None = None,
) -> SalesPanel:
    """Hourly sales for whole days: base × dow × hour weight × noise; zero on weekly off / closures."""
    rng = np.random.default_rng(seed)
    m = len(city.merchants)
    profiles = [city.profiles[x.id] for x in city.merchants]
    base = np.array([p.base_day_paise for p in profiles], dtype=np.float64)
    weights = np.array([p.hour_weights for p in profiles])
    dows = np.array([(first_day + timedelta(days=d)).weekday() for d in range(days)])
    dow_mult = np.array([p.dow_mult for p in profiles])[:, dows]
    day_noise = rng.lognormal(0.0, 0.10, size=(m, days))
    hour_noise = rng.lognormal(0.0, 0.25, size=(m, days, 24))
    amount = base[:, None, None] * (dow_mult * day_noise)[:, :, None] * weights[:, None, :] * hour_noise
    open_day = np.ones((m, days), dtype=bool)
    for r, merchant in enumerate(city.merchants):
        if merchant.weekly_off is not None:
            open_day[r] &= dows != merchant.weekly_off
    for mid, closed in (closures or {}).items():
        for day in closed:
            open_day[city.row(mid), (day - first_day).days] = False
    for (zone_id, day), depth in (zone_dips or {}).items():
        amount[list(city.zone_rows(zone_id)), (day - first_day).days, :] *= 1.0 - depth
    amount = np.where(open_day[:, :, None], amount, 0.0)
    tickets = np.array([p.avg_ticket_paise for p in profiles], dtype=np.float64)
    txns = rng.poisson(amount / tickets[:, None, None]).astype(np.int32)
    paise = np.where(txns > 0, np.rint(amount), 0).astype(np.int64)
    return SalesPanel(
        tuple(x.id for x in city.merchants),
        at(first_day, 0),
        days * 24,
        paise.reshape(m, days * 24),
        txns.reshape(m, days * 24),
    )


def replace_cells(
    panel: SalesPanel,
    rows: Sequence[int],
    start: datetime,
    hours: int,
    amount: int | np.ndarray,
    txns: int | np.ndarray,
) -> SalesPanel:
    """A new panel with the given rows × [start, start+hours) cells overwritten."""
    new_amount = panel.amount_paise.copy()
    new_txns = panel.txns.copy()
    i = panel.hour_index(start)
    index = np.asarray(rows)[:, None]
    new_amount[index, np.arange(i, i + hours)[None, :]] = amount
    new_txns[index, np.arange(i, i + hours)[None, :]] = txns
    return SalesPanel(panel.merchant_ids, panel.start, panel.hours, new_amount, new_txns)


def make_alert(
    zone_ids: Sequence[str],
    valid_from: datetime,
    valid_to: datetime,
    *,
    kind: AlertKind = AlertKind.RAIN,
    issued_at: datetime | None = None,
    alert_id: str = "A-20250818-01",
) -> Alert:
    return Alert(
        id=alert_id,
        kind=kind,
        level=AlertLevel.RED,
        zone_ids=tuple(zone_ids),
        issued_at=issued_at or valid_from - timedelta(hours=20),
        valid_from=valid_from,
        valid_to=valid_to,
        source="IMD-style nowcast · simulated",
        headline_en="Red alert",
        headline_hi="रेड अलर्ट",
    )
