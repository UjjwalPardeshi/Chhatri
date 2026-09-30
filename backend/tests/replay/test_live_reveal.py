"""Map values (B3) and the reveal rule (B4): nothing at or after floor_hour(now) leaks (SPEC §8.1, §19.2)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import numpy as np
import pytest

from chhatri.clock import ManualClock
from chhatri.money import percent_half_up
from chhatri.replay import views
from chhatri.replay.evidence import hourly_evidence
from chhatri.replay.live import MIN_HEX_SHOPS
from chhatri.replay.state import Runtime
from chhatri.sim.types import SalesPanel
from tests.replay.helpers import ANIL, MONSOON_DAY, monsoon_at

ZONES = ("Z3", "Z7", "Z9", "Z12")
HOURS = 3


def at_time(rt: Runtime, when: datetime) -> Runtime:
    """The same runtime seen at another minute of the same hour-evaluated state (views only)."""
    return replace(rt, clock=ManualClock(when))


def tampered(rt: Runtime, from_hour: datetime, factor: int) -> Runtime:
    """The runtime with every sale from `from_hour` on multiplied by `factor` (0 wipes them)."""
    history = rt.world.history
    i = history.hour_index(from_hour)
    amount, txns = history.amount_paise.copy(), history.txns.copy()
    amount[:, i:] *= factor
    txns[:, i:] *= factor
    panel = SalesPanel(history.merchant_ids, history.start, history.hours, amount, txns)
    return replace(rt, world=replace(rt.world, history=panel))


def everything(rt: Runtime) -> dict:
    return {
        "snapshot": views.snapshot(rt),
        "panels": {z: views.zone_panel(rt, z) for z in ZONES},
        "anil": views.merchant_detail(rt, ANIL),
        "evidence": hourly_evidence(rt, ANIL, MONSOON_DAY, rt.clock.now()),
    }


@pytest.mark.parametrize("factor", [0, 7])
def test_future_hours_never_change_any_view(monsoon_1705: Runtime, factor: int) -> None:
    rt = monsoon_1705
    assert everything(tampered(rt, monsoon_at(18), factor)) == everything(rt)


def test_the_hour_in_progress_only_moves_the_live_values(monsoon_1705: Runtime) -> None:
    rt = monsoon_1705
    other = tampered(rt, monsoon_at(17), 0)
    for zone in ZONES:
        mine, theirs = views.zone_snapshot(rt, zone), views.zone_snapshot(other, zone)
        assert {k: v for k, v in mine.items() if k != "live_index_pct"} == {
            k: v for k, v in theirs.items() if k != "live_index_pct"
        }
        assert views.zone_panel(rt, zone)["rows"] == views.zone_panel(other, zone)["rows"]
    assert (
        views.zone_snapshot(other, "Z7")["live_index_pct"] < views.zone_snapshot(rt, "Z7")["live_index_pct"]
    )
    assert hourly_evidence(other, ANIL, MONSOON_DAY, rt.clock.now()) == hourly_evidence(
        rt, ANIL, MONSOON_DAY, rt.clock.now()
    )


def test_on_the_hour_the_live_index_is_the_trailing_index_and_reads_nothing_new(
    monsoon_1705: Runtime,
) -> None:
    rt = at_time(monsoon_1705, monsoon_at(17))
    for zone in ZONES:
        snap = views.zone_snapshot(rt, zone)
        assert snap["live_index_pct"] == snap["index_pct"] is not None
    assert everything(tampered(rt, monsoon_at(17), 0)) == everything(rt)


def test_visible_panels_end_at_the_last_completed_hour(monsoon_1705: Runtime) -> None:
    world = monsoon_1705.world
    assert world.visible(monsoon_at(17, 5)).end == monsoon_at(17)
    assert world.live_panel(monsoon_at(17, 5)).end == monsoon_at(18)
    assert world.live_panel(monsoon_at(17)).end == monsoon_at(17)
    assert world.completed_history(monsoon_at(17, 5)).start == world.history.start
    assert monsoon_1705.board.evaluated_at == monsoon_at(17)


def _open_rows(rt: Runtime, rows: list[int], start: datetime, hours: int) -> list[int]:
    city, weekday = rt.static.city, start.weekday()
    keep = []
    for row in rows:
        merchant = city.merchants[row]
        profile = city.profiles[merchant.id]
        open_hours = any(profile.is_business_hour(start.hour + k) for k in range(hours))
        if merchant.id in city.covers and open_hours and merchant.weekly_off != weekday:
            keep.append(row)
    return keep


def _live_index(rt: Runtime, rows: list[int], weights: np.ndarray, first: int) -> int | None:
    day = rt.world.history.day(MONSOON_DAY)
    span = slice(first, first + len(weights))
    actual = Decimal(repr(float(day.amount_paise[rows, span].sum(axis=0) @ weights)))
    expected = Decimal(repr(float(rt.world.p50[rows, span].sum(axis=0) @ weights)))
    actual_paise = int(actual.quantize(Decimal(1), rounding="ROUND_HALF_UP"))
    expected_paise = int(expected.quantize(Decimal(1), rounding="ROUND_HALF_UP"))
    return None if expected_paise == 0 else percent_half_up(actual_paise, expected_paise)


def test_the_live_index_prorates_the_oldest_and_the_current_hour(monsoon_1705: Runtime) -> None:
    """B3 at 17:05: hours 14, 15, 16 and 17 weighted (1 − f), 1, 1, f with f = 5/60."""
    rt, f = monsoon_1705, 5 / 60
    weights = np.array([1 - f, 1.0, 1.0, f])
    for zone in ("Z7", "Z9"):
        rows = _open_rows(rt, list(rt.static.city.zone_rows(zone)), monsoon_at(14), HOURS + 1)
        assert views.zone_snapshot(rt, zone)["live_index_pct"] == _live_index(rt, rows, weights, 14)


def test_hex_values_follow_the_three_shop_rule(monsoon_1705: Runtime) -> None:
    rt, city, f = monsoon_1705, monsoon_1705.static.city, 5 / 60
    weights = np.array([1 - f, 1.0, 1.0, f])
    hexes = views.snapshot(rt)["hexes"]
    members = _open_rows(rt, list(range(len(city.merchants))), monsoon_at(14), HOURS + 1)
    by_hex: dict[str, list[int]] = {}
    for row in members:
        by_hex.setdefault(city.merchants[row].h3_cell, []).append(row)
    zone_of = {hx.h3: hx.zone_id for hx in city.geography.hexes}
    own = [h for h, rows in by_hex.items() if len(rows) >= MIN_HEX_SHOPS]
    few = [h for h, rows in by_hex.items() if 0 < len(rows) < MIN_HEX_SHOPS]
    assert own and few
    for h3 in own:
        assert hexes[h3] == _live_index(rt, by_hex[h3], weights, 14)
    for h3 in few:
        assert hexes[h3] == views.zone_snapshot(rt, zone_of[h3])["live_index_pct"]
    empty_zone = next(z.id for z in city.zones if not city.zone_rows(z.id))
    assert {hexes[h] for h, z in zone_of.items() if z == empty_zone} == {None}
    assert set(hexes) == {hx.h3 for hx in city.geography.hexes}


def test_the_rain_band_covers_the_wards_raining_now(monsoon_1705: Runtime) -> None:
    band = views.snapshot(monsoon_1705)["rain_band"]
    assert band["type"] == "FeatureCollection"
    assert sorted(f["properties"]["id"] for f in band["features"]) == ["Z12", "Z3", "Z7"]
    assert views.snapshot(at_time(monsoon_1705, monsoon_at(18, 30)))["rain_band"] is None
    assert views.snapshot(at_time(monsoon_1705, monsoon_at(8)))["rain_band"] is None
