"""SPEC §6.1-§6.3, §24.1: the vectorised sales simulator."""

from __future__ import annotations

import math
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from chhatri.clock import at
from chhatri.domain.enums import ShopType
from chhatri.sim.city import build_city
from chhatri.sim.rng import Stream, generator
from chhatri.sim.sales import SalesSimulator, rain_impact_curve, trend
from chhatri.sim.types import City, ScenarioOverrides
from chhatri.sim.weather import ShockCalendar, build_shocks

SEED = 20251019
FESTIVAL_DAY = date(2025, 8, 28)  # Thursday inside the 2025 Ganesh window
PREV_DAY = FESTIVAL_DAY - timedelta(days=1)


def test_rain_impact_spec_example() -> None:
    # SPEC §6.3: 60 mm over 3 h, FRUIT_VEG (0.90), normal zone -> impact 0.82
    assert round(0.90 * float(rain_impact_curve(60.0, False)), 2) == 0.82
    assert float(rain_impact_curve(60.0, True)) == pytest.approx(1 - math.exp(-60 / 18))
    assert float(rain_impact_curve(0.0, True)) == 0.0
    assert trend(date(2025, 8, 19)) == 1.0 and trend(date(2026, 8, 19)) == pytest.approx(1.05)


@pytest.fixture(scope="module")
def scripted(small_city: City, data_dir: Path) -> ShockCalendar:
    """Quiet festival day with scripted rain (incl. 23:00 the evening before), a slow day and a closure."""
    z7_rain = (0.0,) * 23 + (20.0,)
    rain = {("Z7", PREV_DAY): z7_rain, ("Z3", FESTIVAL_DAY): (0.0,) * 15 + (30.0, 30.0) + (0.0,) * 7}
    closed = next(m.id for m in small_city.merchants if m.zone_id == "Z12" and not m.is_demo)
    overrides = ScenarioOverrides(
        rain_mm=rain,
        slow_days={("Z9", FESTIVAL_DAY): 0.30},
        closures={closed: ((FESTIVAL_DAY, FESTIVAL_DAY),)},
        quiet_days=(PREV_DAY, FESTIVAL_DAY),
    )
    return build_shocks(small_city, data_dir, SEED, overrides)


def oracle(city: City, shocks: ShockCalendar, row: int, day: date, shocked: bool) -> np.ndarray:
    """Expected pre-Poisson amount for one merchant-day, straight from SPEC §6.2/§6.3."""
    m = city.merchants[row]
    p = city.profiles[m.id]
    rng = generator(SEED, Stream.SALES_NOISE, day.toordinal())
    day_z = rng.standard_normal(len(city.merchants))[row]
    hour_z = rng.standard_normal((len(city.merchants), 24))[row]
    festival = (
        1.2
        if m.shop_type in (ShopType.TEA_STALL, ShopType.STREET_FOOD, ShopType.FRUIT_VEG, ShopType.KIRANA)
        else 1.0
    )
    zone = city.geography.zone(m.zone_id)
    out = np.zeros(24)
    for h in range(24):
        if not p.is_business_hour(h) or m.weekly_off == day.weekday():
            continue
        value = p.base_day_paise * p.dow_mult[day.weekday()] * p.hour_weights[h] * festival * trend(day)
        value *= math.exp(0.10 * day_z - 0.005) * math.exp(0.25 * hour_z[h] - 0.03125)
        if shocked:
            r3 = sum(shocks.rain_mm(m.zone_id, at(day, h) - timedelta(hours=k)) for k in range(3))
            scale = 18.0 if zone.waterlogging_prone else 25.0
            value *= 1 - p.rain_sensitivity * (1 - math.exp(-r3 / scale))
            value *= 1 - shocks.slow_day_depth(m.zone_id, day)
            value *= 0.0 if any(s <= day <= e for s, e in shocks.closures(m.id)) else 1.0
        out[h] = math.floor(value + 0.5)
    return out


def test_formula_matches_spec_oracle(small_city: City, scripted: ShockCalendar) -> None:
    sim = SalesSimulator(small_city, scripted, SEED)
    actual = sim.generate(FESTIVAL_DAY, FESTIVAL_DAY)
    baseline = sim.counterfactual(FESTIVAL_DAY, FESTIVAL_DAY)
    zones_seen: set[str] = set()
    for row in range(0, len(small_city.merchants), 3):
        for panel, shocked in ((actual, True), (baseline, False)):
            expected = oracle(small_city, scripted, row, FESTIVAL_DAY, shocked)
            got = panel.amount_paise[row]
            txns = panel.txns[row]
            np.testing.assert_array_equal(got[txns > 0], expected[txns > 0])
            assert not got[txns == 0].any()
        zones_seen.add(small_city.merchants[row].zone_id)
    assert zones_seen == {"Z3", "Z7", "Z9", "Z12"}


def test_rain_r3_crosses_midnight(small_city: City, scripted: ShockCalendar) -> None:
    sim = SalesSimulator(small_city, scripted, SEED)
    rows = [
        r
        for r in small_city.zone_rows("Z7")
        if small_city.profiles[small_city.merchants[r].id].open_hour == 6
    ]
    act = sim.generate(FESTIVAL_DAY, FESTIVAL_DAY).amount_paise[rows].sum(axis=0)
    cf = sim.counterfactual(FESTIVAL_DAY, FESTIVAL_DAY).amount_paise[rows].sum(axis=0)
    assert act[6:].sum() == cf[6:].sum()  # 23:00 rain only reaches hours 0 and 1 of the next day
    grid = sim._shock_arrays(FESTIVAL_DAY, 1).rain_g  # noqa: SLF001
    z7 = scripted.zone_ids.index("Z7")
    np.testing.assert_allclose(grid[z7, :3], [1 - math.exp(-20 / 18)] * 2 + [0.0])


def test_shocks_combine_and_counterfactual_removes_them(small_city: City, scripted: ShockCalendar) -> None:
    sim = SalesSimulator(small_city, scripted, SEED)
    act = sim.generate(FESTIVAL_DAY, FESTIVAL_DAY).amount_paise
    cf = sim.counterfactual(FESTIVAL_DAY, FESTIVAL_DAY).amount_paise
    z9 = list(small_city.zone_rows("Z9"))
    assert 0.6 < act[z9].sum() / cf[z9].sum() < 0.8  # 30 % scripted slow day
    closed = small_city.row(next(iter(scripted._overrides.closures)))  # noqa: SLF001
    assert act[closed].sum() == 0 and cf[closed].sum() > 0
    z12 = [r for r in small_city.zone_rows("Z12") if r != closed]
    np.testing.assert_array_equal(act[z12], cf[z12])  # no shock in Z12 -> identical noise and txns


def test_zero_outside_hours_weekly_off_and_txns_rule(full_city: City, data_dir: Path) -> None:
    shocks = build_shocks(full_city, data_dir, SEED)
    sim = SalesSimulator(full_city, shocks, SEED)
    first, last = date(2025, 2, 3), date(2025, 2, 9)
    panel = sim.generate(first, last)
    amount = panel.amount_paise.reshape(len(full_city.merchants), 7, 24)
    txns = panel.txns.reshape(len(full_city.merchants), 7, 24)
    assert panel.amount_paise.dtype == np.int64 and panel.txns.dtype == np.int32
    assert not amount[txns == 0].any() and (amount >= 0).all()
    for row, m in enumerate(full_city.merchants):
        p = full_city.profiles[m.id]
        closed_hours = [h for h in range(24) if not p.is_business_hour(h)]
        assert not amount[row][:, closed_hours].any()
        if m.weekly_off is not None:
            assert not amount[row, m.weekly_off].any()
    tickets = np.array([full_city.profiles[m.id].avg_ticket_paise for m in full_city.merchants], dtype=float)
    expected_txns = (panel.amount_paise / tickets[:, None]).sum()
    assert abs(panel.txns.sum() / expected_txns - 1) < 0.02


def test_slice_consistency_and_determinism(small_city: City, small_shocks: ShockCalendar) -> None:
    sim = SalesSimulator(small_city, small_shocks, SEED)
    long = sim.generate(date(2025, 7, 1), date(2025, 7, 31))
    short = sim.generate(date(2025, 7, 11), date(2025, 7, 13))
    window = long.window(at(date(2025, 7, 11), 0), at(date(2025, 7, 14), 0))
    np.testing.assert_array_equal(window.amount_paise, short.amount_paise)
    np.testing.assert_array_equal(window.txns, short.txns)
    again = SalesSimulator(small_city, small_shocks, SEED).generate(date(2025, 7, 11), date(2025, 7, 13))
    np.testing.assert_array_equal(again.amount_paise, short.amount_paise)
    other = SalesSimulator(small_city, small_shocks, SEED + 1).generate(date(2025, 7, 11), date(2025, 7, 13))
    assert not np.array_equal(other.amount_paise, short.amount_paise)
    assert short.start == at(date(2025, 7, 11), 0) and short.hours == 72
    assert short.merchant_ids == tuple(m.id for m in small_city.merchants)


def test_rain_and_bandh_reduce_sales(small_city: City, small_shocks: ShockCalendar) -> None:
    sim = SalesSimulator(small_city, small_shocks, SEED)
    bandh = date(2025, 9, 9)
    act = sim.generate(bandh, bandh).amount_paise.sum()
    cf = sim.counterfactual(bandh, bandh).amount_paise.sum()
    assert act / cf < 0.26
    days = [date(2025, 6, 1) + timedelta(days=i) for i in range(122)]
    rain = np.array([small_shocks.rain_for_day(d)[small_shocks.zone_ids.index("Z7")].sum() for d in days])
    wettest = days[int(rain.argmax())]
    wet_ratio = (
        sim.generate(wettest, wettest).amount_paise.sum()
        / sim.counterfactual(wettest, wettest).amount_paise.sum()
    )
    assert wet_ratio < 0.9


def test_argument_validation(
    small_city: City, full_city: City, small_shocks: ShockCalendar, data_dir: Path
) -> None:
    sim = SalesSimulator(small_city, small_shocks, SEED)
    with pytest.raises(ValueError, match="before"):
        sim.generate(date(2025, 7, 2), date(2025, 7, 1))
    with pytest.raises(ValueError, match="before"):
        sim.daily_totals(date(2025, 7, 2), date(2025, 7, 1), shocked=True)
    other_city = build_city(SEED, data_dir, scale="small")
    SalesSimulator(other_city, small_shocks, SEED)  # same zones -> accepted
    wrong = type("Fake", (), {"zone_ids": ("Z1",)})()
    with pytest.raises(ValueError, match="different city"):
        SalesSimulator(full_city, wrong, SEED)  # type: ignore[arg-type]


def test_daily_totals_match_panel(small_city: City, small_shocks: ShockCalendar) -> None:
    sim = SalesSimulator(small_city, small_shocks, SEED)
    panel = sim.generate(date(2025, 8, 1), date(2025, 8, 3))
    totals = sim.daily_totals(date(2025, 8, 1), date(2025, 8, 3), shocked=True)
    np.testing.assert_array_equal(
        totals, panel.amount_paise.reshape(len(small_city.merchants), 3, 24).sum(axis=2)
    )


@pytest.mark.slow
def test_full_city_year_performance(full_city: City, data_dir: Path) -> None:
    sim = SalesSimulator(full_city, build_shocks(full_city, data_dir, SEED), SEED)
    started = time.perf_counter()
    panel = sim.generate(date(2025, 1, 1), date(2025, 12, 31))
    year = time.perf_counter() - started
    started = time.perf_counter()
    sim.generate(date(2025, 8, 19), date(2025, 8, 19))
    one_day = time.perf_counter() - started
    assert panel.hours == 8760 and year < 15.0 and one_day < 0.1
