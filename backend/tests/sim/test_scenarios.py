"""Tests for scenarios (SPEC §17.2, §24.1)."""

from datetime import date
from pathlib import Path

import pytest

from chhatri.sim.city import build_city
from chhatri.sim.calibration import load_calibration
from chhatri.sim.scenarios import get_scenario, MONSOON_ALERT


@pytest.fixture
def data_dir():
    """Path to test data directory."""
    return Path(__file__).resolve().parent.parent.parent / "data"


@pytest.fixture
def small_city(data_dir):
    """Small city for fast tests."""
    return build_city(20251019, data_dir, scale="small")


@pytest.fixture
def calibration(data_dir):
    """Load calibration."""
    return load_calibration(data_dir)


def test_monsoon_scenario(small_city, calibration):
    """Test monsoon scenario definition (SPEC §17.2)."""
    scenario = get_scenario("monsoon", small_city, calibration)

    assert scenario.name == "monsoon"
    assert scenario.day == date(2025, 8, 19)
    assert scenario.demo_merchant_id == "S-0142"  # Anil

    # Check alert
    assert len(scenario.overrides.alerts) == 1
    alert = scenario.overrides.alerts[0]
    assert alert.id == "A-20250818-01"
    assert set(alert.zone_ids) == {"Z3", "Z7", "Z12"}


def test_monsoon_alert(small_city, calibration):
    """Test monsoon alert is consistent across scenarios (SPEC §17.2)."""
    monsoon = get_scenario("monsoon", small_city, calibration)
    buy_cover = get_scenario("buy_cover", small_city, calibration)

    # Both should have the same alert object
    monsoon_alert = monsoon.overrides.alerts[0]
    buy_cover_alert = buy_cover.overrides.alerts[0]

    assert monsoon_alert.id == buy_cover_alert.id == "A-20250818-01"
    assert monsoon_alert.zone_ids == buy_cover_alert.zone_ids


def test_illness_scenario(small_city, calibration):
    """Test illness scenario (SPEC §17.2)."""
    scenario = get_scenario("illness", small_city, calibration)

    assert scenario.name == "illness"
    assert scenario.day == date(2025, 8, 21)
    assert scenario.demo_merchant_id == "S-0142"  # Anil
    assert scenario.slip_sample == "anil_admission_slip.png"

    # Check Anil is closed
    assert "S-0142" in scenario.overrides.closures


def test_illness_mismatch_scenario(small_city, calibration):
    """Test illness mismatch scenario (SPEC §17.2)."""
    scenario = get_scenario("illness_mismatch", small_city, calibration)

    assert scenario.name == "illness_mismatch"
    assert scenario.day == date(2025, 8, 21)
    assert scenario.demo_merchant_id == "S-0142"  # Anil
    assert scenario.slip_sample == "mismatch_admission_slip.png"

    # Check Anil is closed
    assert "S-0142" in scenario.overrides.closures


def test_buy_cover_scenario(small_city, calibration):
    """Test buy cover scenario (SPEC §17.2)."""
    scenario = get_scenario("buy_cover", small_city, calibration)

    assert scenario.name == "buy_cover"
    assert scenario.day == date(2025, 8, 18)
    assert scenario.demo_merchant_id == "S-0907"  # Ramesh

    # Check alert is present
    assert len(scenario.overrides.alerts) == 1
    assert scenario.overrides.alerts[0].id == "A-20250818-01"


def test_scenario_quiet_days(small_city, calibration):
    """Test that scenarios have quiet_days (no random shocks) (SPEC §17.2)."""
    for scenario_name in ["monsoon", "illness", "illness_mismatch", "buy_cover"]:
        scenario = get_scenario(scenario_name, small_city, calibration)

        # Should have quiet_days
        assert len(scenario.overrides.quiet_days) > 0

        # Quiet days should be dates
        for day in scenario.overrides.quiet_days:
            assert isinstance(day, date)


def test_monsoon_rain_schedule(small_city, calibration):
    """Test monsoon has scripted rain (SPEC §17.2)."""
    scenario = get_scenario("monsoon", small_city, calibration)

    # Should have rain schedule for Z3, Z7, Z12
    rain_mm = scenario.overrides.rain_mm

    monsoon_day = date(2025, 8, 19)
    for zone_id in ["Z3", "Z7", "Z12"]:
        assert (zone_id, monsoon_day) in rain_mm
        hourly_rain = rain_mm[(zone_id, monsoon_day)]

        # Should be 24 hourly values
        assert len(hourly_rain) == 24

        # Should have non-zero values (rain during the scenario)
        assert max(hourly_rain) > 0


def test_z9_slow_day(small_city, calibration):
    """Test monsoon Z9 has slow day (SPEC §17.2)."""
    scenario = get_scenario("monsoon", small_city, calibration)

    # Z9 should have a slow day on the monsoon day
    slow_days = scenario.overrides.slow_days
    monsoon_day = date(2025, 8, 19)

    assert ("Z9", monsoon_day) in slow_days


def test_scenario_not_found():
    """Test that unknown scenario raises ValueError."""
    city = build_city(20251019, Path(__file__).resolve().parent.parent.parent / "data", scale="small")
    calibration = load_calibration(Path(__file__).resolve().parent.parent.parent / "data")

    with pytest.raises(ValueError):
        get_scenario("unknown_scenario", city, calibration)


def test_all_scenarios_exist(small_city, calibration):
    """Test that all documented scenarios can be loaded (SPEC §17.2)."""
    scenario_names = ["monsoon", "illness", "illness_mismatch", "buy_cover"]

    for name in scenario_names:
        scenario = get_scenario(name, small_city, calibration)
        assert scenario.name == name
