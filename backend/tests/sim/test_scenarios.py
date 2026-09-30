"""SPEC §17.2, §17.4, §24.1: the four scenarios."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from chhatri.clock import ist
from chhatri.domain.enums import AlertKind, AlertLevel
from chhatri.sim.city import build_city
from chhatri.sim.sales import SalesSimulator
from chhatri.sim.scenarios import (
    DEMO_WEEK,
    HISTORY_WEEKS,
    MONSOON_ALERT,
    SCENARIOS,
    STORM_RAIN_MM,
    get_scenario,
)
from chhatri.sim.types import Calibration, City
from chhatri.sim.weather import build_shocks

SEED = 20251019
MONSOON = date(2025, 8, 19)


def test_scenario_names_and_unknown(small_city: City) -> None:
    assert SCENARIOS == ("monsoon", "illness", "illness_mismatch", "buy_cover")
    with pytest.raises(ValueError, match="unknown scenario"):
        get_scenario("tsunami", small_city, Calibration())


def test_monsoon_scenario(small_city: City) -> None:
    s = get_scenario("monsoon", small_city, Calibration())
    assert (s.name, s.day, s.demo_merchant_id, s.slip_sample) == ("monsoon", MONSOON, "S-0142", None)
    assert MONSOON.weekday() == 1  # Tuesday
    assert (s.start, s.end) == (ist(2025, 8, 19, 8), ist(2025, 8, 19, 20))
    assert s.overrides.alerts == (MONSOON_ALERT,)
    a = MONSOON_ALERT
    assert (a.id, a.kind, a.level, a.zone_ids) == (
        "A-20250818-01",
        AlertKind.RAIN,
        AlertLevel.RED,
        ("Z3", "Z7", "Z12"),
    )
    assert (a.issued_at, a.valid_from, a.valid_to) == (
        ist(2025, 8, 18, 17, 30),
        ist(2025, 8, 19, 14),
        ist(2025, 8, 19, 20),
    )
    assert "simulated" in a.source
    assert set(s.overrides.rain_mm) == {("Z3", MONSOON), ("Z7", MONSOON), ("Z12", MONSOON)}
    assert dict(s.overrides.slow_days) == {("Z9", MONSOON): pytest.approx(0.39)}
    assert MONSOON in s.overrides.quiet_days and s.overrides.quiet_days == DEMO_WEEK
    assert s.history_start == MONSOON - timedelta(weeks=HISTORY_WEEKS)
    assert (MONSOON - s.history_start).days >= 56 + 28


def test_storm_band_shape() -> None:
    wet_hours = [h for h, v in enumerate(STORM_RAIN_MM) if v > 0]
    assert wet_hours == [14, 15, 16, 17]  # "rain band 14:00-17:00+"
    r3 = [sum(STORM_RAIN_MM[h - 2 : h + 1]) for h in (14, 15, 16)]
    assert max(r3) - min(r3) <= 2.0 and min(r3) >= 30.0  # flat over the trigger window
    assert sum(STORM_RAIN_MM[15:18]) < 5  # the band has passed by 17:00


def test_calibration_hooks_on_scenario(small_city: City) -> None:
    calibration = Calibration(zone_rain_scale={"Z3": 1.5, "Z7": 0.5, "Z12": 1.0}, z9_slow_depth=0.33)
    s = get_scenario("monsoon", small_city, calibration)
    assert s.overrides.rain_mm[("Z3", MONSOON)][14] == pytest.approx(STORM_RAIN_MM[14] * 1.5)
    assert s.overrides.rain_mm[("Z7", MONSOON)][14] == pytest.approx(STORM_RAIN_MM[14] * 0.5)
    assert s.overrides.slow_days[("Z9", MONSOON)] == 0.33
    with pytest.raises(ValueError, match="zone_rain_scale"):
        get_scenario("monsoon", small_city, Calibration(zone_rain_scale={"Z3": 1.0}))


def test_same_alert_object_in_every_scenario(small_city: City) -> None:
    for name in SCENARIOS:
        assert get_scenario(name, small_city, Calibration()).overrides.alerts[0] is MONSOON_ALERT


def test_illness_scenarios(small_city: City) -> None:
    for name, slip in (
        ("illness", "anil_admission_slip.png"),
        ("illness_mismatch", "mismatch_admission_slip.png"),
    ):
        s = get_scenario(name, small_city, Calibration())
        assert (s.day, s.demo_merchant_id, s.slip_sample) == (date(2025, 8, 21), "S-0142", slip)
        assert (s.start, s.end) == (ist(2025, 8, 21, 10, 30), ist(2025, 8, 21, 13))
        assert dict(s.overrides.closures) == {"S-0142": ((date(2025, 8, 20), date(2025, 8, 21)),)}


def test_buy_cover_scenario(small_city: City) -> None:
    s = get_scenario("buy_cover", small_city, Calibration())
    assert (s.day, s.demo_merchant_id, s.slip_sample) == (date(2025, 8, 18), "S-0907", None)
    assert (s.start, s.end) == (ist(2025, 8, 18, 18), ist(2025, 8, 18, 19))
    assert MONSOON_ALERT.issued_at < s.start


def test_city_without_the_cast_is_rejected(data_dir: Path, small_city: City) -> None:
    city = City(
        seed=1, geography=small_city.geography,
        merchants=tuple(m for m in small_city.merchants if m.id != "S-0907"),
        profiles={k: v for k, v in small_city.profiles.items() if k != "S-0907"},
        covers=small_city.covers, loans=small_city.loans,
    )  # fmt: skip
    with pytest.raises(ValueError, match="demo merchants"):
        get_scenario("buy_cover", city, Calibration())


def test_monsoon_day_sales_story(small_city: City, data_dir: Path) -> None:
    """Storm zones collapse 14:00-17:00 and recover; Z9 dips all day; the rest of the city is normal."""
    scenario = get_scenario("monsoon", small_city, Calibration())
    sim = SalesSimulator(small_city, build_shocks(small_city, data_dir, SEED, scenario.overrides), SEED)
    act = sim.generate(MONSOON, MONSOON).amount_paise
    cf = sim.counterfactual(MONSOON, MONSOON).amount_paise
    for zone in ("Z3", "Z7", "Z12"):
        rows = list(small_city.zone_rows(zone))
        hourly = dict(
            zip(range(8, 20), act[rows, 8:20].sum(axis=0) / cf[rows, 8:20].sum(axis=0), strict=True)
        )
        assert all(hourly[h] == 1 for h in range(8, 14)) and all(hourly[h] < 0.5 for h in (14, 15, 16))
        assert hourly[18] > 0.85
    z9 = list(small_city.zone_rows("Z9"))
    assert 0.5 < act[z9].sum() / cf[z9].sum() < 0.7
    np.testing.assert_array_equal(act[[small_city.row("S-0142")], :14], cf[[small_city.row("S-0142")], :14])


def test_illness_closure_in_sales(small_city: City, data_dir: Path) -> None:
    scenario = get_scenario("illness", small_city, Calibration())
    sim = SalesSimulator(small_city, build_shocks(small_city, data_dir, SEED, scenario.overrides), SEED)
    panel = sim.generate(date(2025, 8, 19), date(2025, 8, 21))
    anil = panel.amount_paise[small_city.row("S-0142")].reshape(3, 24).sum(axis=1)
    assert anil[0] > 0 and anil[1] == 0 and anil[2] == 0


def test_full_city_scenarios_build(full_city: City) -> None:
    for name in SCENARIOS:
        assert get_scenario(name, full_city, Calibration()).name == name
    assert build_city(SEED, Path(__file__).resolve().parents[2] / "data", scale="small").zone_rows("Z1") == ()
