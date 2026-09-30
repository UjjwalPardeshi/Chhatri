"""SPEC §6.3 rain field and §6.4 alerts feed."""

from __future__ import annotations

import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from chhatri.clock import at, ist
from chhatri.domain.enums import AlertKind, AlertLevel
from chhatri.domain.models import Zone
from chhatri.sim.alerts import (
    CIVIC_SOURCE,
    RAIN_SOURCE,
    alert_zone_days,
    bandh_alert_draft,
    number_alerts,
    outside_quiet_days,
    overlapping,
    rain_alert_drafts,
    trailing_sum,
)
from chhatri.sim.rainfall import (
    CONVECTIVE_PROB,
    RainField,
    load_fixtures,
    season_days,
    station_for,
)
from chhatri.sim.scenarios import MONSOON_ALERT
from chhatri.sim.types import City

ZONE = Zone(id="Z5", ward="D", name="Malabar Hill", centroid_lat=18.96, centroid_lng=72.81)


@pytest.fixture(scope="module")
def fixtures(data_dir: Path):
    return load_fixtures(data_dir / "weather")


def test_fixtures_load_all_four_seasons(fixtures) -> None:
    assert set(fixtures) == {("santacruz", 2024), ("colaba", 2024), ("santacruz", 2025), ("colaba", 2025)}
    for series in fixtures.values():
        assert series.shape == (122, 24) and (series >= 0).all() and series.sum() > 500
        assert not series.flags.writeable


def test_fixture_validation(tmp_path: Path, data_dir: Path) -> None:
    with pytest.raises(ValueError, match="no Open-Meteo fixtures"):
        load_fixtures(tmp_path)
    shutil.copy(data_dir / "weather" / "openmeteo_colaba_2024.json", tmp_path)
    with pytest.raises(ValueError, match="missing Open-Meteo fixtures"):
        load_fixtures(tmp_path)
    (tmp_path / "openmeteo_Bad.json").write_text("{}")
    with pytest.raises(ValueError, match="unexpected weather file"):
        load_fixtures(tmp_path)
    (tmp_path / "openmeteo_Bad.json").unlink()
    raw = json.loads((data_dir / "weather" / "openmeteo_santacruz_2024.json").read_text())
    raw["hourly"]["precipitation"][5] = -1
    (tmp_path / "openmeteo_santacruz_2024.json").write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="non-negative"):
        load_fixtures(tmp_path)
    raw["hourly"]["time"] = raw["hourly"]["time"][1:]
    (tmp_path / "openmeteo_santacruz_2024.json").write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="hourly"):
        load_fixtures(tmp_path)
    (tmp_path / "openmeteo_santacruz_2024.json").write_text("[]")
    with pytest.raises(ValueError, match="unreadable"):
        load_fixtures(tmp_path)


def test_station_choice_by_centroid_latitude(full_city: City) -> None:
    stations = {z.ward: station_for(z) for z in full_city.zones}
    assert stations["F/S"] == stations["G/S"] == stations["E"] == stations["F/N"] == "colaba"
    assert stations["M/W"] == stations["G/N"] == stations["R/N"] == "santacruz"


def test_rain_field_season_spatial_factor_and_determinism(full_city: City, fixtures) -> None:
    field = RainField(full_city.zones, fixtures, 7)
    assert field.years == (2024, 2025)
    assert not field.day_rain(date(2025, 5, 31)).any() and not field.day_rain(date(2025, 10, 1)).any()
    day = date(2025, 7, 7)
    rain = field.day_rain(day)
    np.testing.assert_array_equal(rain, RainField(full_city.zones, fixtures, 7).day_rain(day))
    assert not np.array_equal(rain, RainField(full_city.zones, fixtures, 8).day_rain(day))
    with pytest.raises(ValueError, match="no Open-Meteo fixture"):
        field.day_rain(date(2026, 7, 1))


def test_spatial_factor_is_mean_one_lognormal_045(full_city: City, fixtures) -> None:
    field = RainField(full_city.zones, fixtures, 11)
    ratios = []
    for day in season_days(2025):
        station = field._station_rows(day)  # noqa: SLF001 - test of the documented factor
        total = station.sum(axis=1)
        wet = total > 5
        convective = field._convective(day).sum(axis=1)  # noqa: SLF001
        ratios.extend(((field.day_rain(day).sum(axis=1) - convective)[wet] / total[wet]).tolist())
    logs = np.log(ratios)
    assert abs(np.std(logs) - 0.45) < 0.03 and abs(np.mean(ratios) - 1) < 0.05


def test_convective_cells_are_rare_afternoon_bursts(full_city: City, fixtures) -> None:
    field = RainField(full_city.zones, fixtures, 3)
    cells = np.stack([field._convective(d) for d in season_days(2024) + season_days(2025)])  # noqa: SLF001
    hits = (cells.sum(axis=2) > 0).mean()
    assert 0.3 * CONVECTIVE_PROB < hits < 3 * CONVECTIVE_PROB
    assert not cells[:, :, :12].any()


def test_trailing_sum_is_three_hours() -> None:
    np.testing.assert_array_equal(trailing_sum(np.array([1.0, 2.0, 4.0, 8.0])), [1, 3, 7, 14])


def test_rain_alert_orange_then_red_timing() -> None:
    start = at(date(2025, 7, 1), 0)
    rain = np.zeros(48)
    rain[10:13] = 12.0  # r3 at 11 = 24, at 12 = 36 (>=30), at 13 = 24
    rain[20:23] = 25.0  # r3: 20->25, 21->50, 22->75 (>=60), 23->50, 24->25
    drafts = rain_alert_drafts(ZONE, start, rain)
    orange = [d for d in drafts if d.level is AlertLevel.ORANGE]
    red = [d for d in drafts if d.level is AlertLevel.RED]
    assert [(d.valid_from, d.valid_to) for d in orange] == [
        (start + timedelta(hours=12), start + timedelta(hours=16)),
        (start + timedelta(hours=21), start + timedelta(hours=27)),
    ]
    assert red[0].issued_at == start + timedelta(hours=21) and red[0].valid_to == start + timedelta(hours=26)
    assert all(d.issued_at == d.valid_from - timedelta(minutes=60) for d in drafts)
    assert all(d.source == RAIN_SOURCE and d.zone_ids == ("Z5",) for d in drafts)
    assert "Red alert" in red[0].headline_en and "रेड अलर्ट" in red[0].headline_hi


def test_rain_alert_episodes_merge_within_tail() -> None:
    start = at(date(2025, 7, 1), 0)
    rain = np.zeros(30)
    rain[2], rain[7] = 31.0, 31.0  # second crossing at 7 < 3 + 3 + ... expiry at 5 + 3 = 8
    drafts = rain_alert_drafts(ZONE, start, rain)
    assert len(drafts) == 1 and drafts[0].valid_to == start + timedelta(hours=13)


def test_numbering_per_issue_day_skips_scripted_ids() -> None:
    day = date(2025, 8, 18)
    first = rain_alert_drafts(ZONE, at(day, 0), np.array([0] * 10 + [31] + [0] * 13))
    other = rain_alert_drafts(
        ZONE.model_copy(update={"id": "Z2"}), at(day, 0), np.array([0] * 20 + [31, 0, 0, 0])
    )
    alerts = number_alerts(first + other, (MONSOON_ALERT,))
    assert [a.id for a in alerts] == ["A-20250818-02", "A-20250818-01", "A-20250818-03"]
    assert alerts[1] is MONSOON_ALERT
    with pytest.raises(ValueError, match="unique"):
        number_alerts([], (MONSOON_ALERT, MONSOON_ALERT))


def test_bandh_alert_and_quiet_day_clipping() -> None:
    draft = bandh_alert_draft(date(2025, 9, 9), ("Z1", "Z2"))
    assert draft.kind is AlertKind.CIVIC and draft.source == CIVIC_SOURCE
    assert draft.issued_at == ist(2025, 9, 8, 19) and draft.valid_from == ist(2025, 9, 9)
    assert draft.valid_to == ist(2025, 9, 10)
    start = at(date(2025, 8, 17), 0)
    rain = np.zeros(72)
    rain[20] = 31.0  # valid 17th 20:00 -> 18th 00:00 (+3h tail = 01:00 on the 18th)
    rain[40] = 31.0  # on the 18th: dropped
    kept = outside_quiet_days(rain_alert_drafts(ZONE, start, rain), [date(2025, 8, 18)])
    assert len(kept) == 1 and kept[0].valid_to == ist(2025, 8, 18)


def test_overlap_and_alert_zone_days() -> None:
    alerts = (MONSOON_ALERT,)
    assert overlapping(alerts, ist(2025, 8, 19, 13), ist(2025, 8, 19, 14)) == ()
    assert overlapping(alerts, ist(2025, 8, 19, 19, 59), ist(2025, 8, 19, 21)) == alerts
    assert overlapping(alerts, ist(2025, 8, 18, 18), ist(2025, 8, 21)) == alerts
    with pytest.raises(ValueError):
        overlapping(alerts, ist(2025, 8, 19, 14), ist(2025, 8, 19, 14))
    assert alert_zone_days(alerts) == {
        ("Z3", date(2025, 8, 19)),
        ("Z7", date(2025, 8, 19)),
        ("Z12", date(2025, 8, 19)),
    }
