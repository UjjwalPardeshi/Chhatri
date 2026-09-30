"""The 11:20 check-in round on edited worlds: long silences and nobody covered (SPEC §8.3, §17.1)."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import date, timedelta
from types import MappingProxyType

import pytest

from chhatri.replay import world
from chhatri.replay.state import Runtime
from chhatri.replay.static import StaticContext
from chhatri.sim.types import Calibration, City, Scenario
from tests.replay.helpers import ANIL, ILLNESS_DAY, MONSOON_DAY, loaded, make_static

WORKING_DAYS = {MONSOON_DAY.weekday(), (MONSOON_DAY + timedelta(days=1)).weekday(), ILLNESS_DAY.weekday()}


def closed_from(merchant_id: str, first: date) -> Callable[[str, City, Calibration], Scenario]:
    """`get_scenario` with one more shop closed from `first` through the illness day."""
    real = world.get_scenario

    def scenario(name: str, city: City, calibration: Calibration) -> Scenario:
        base = real(name, city, calibration)
        closures = {**base.overrides.closures, merchant_id: ((first, ILLNESS_DAY),)}
        overrides = dataclasses.replace(base.overrides, closures=MappingProxyType(closures))
        return dataclasses.replace(base, overrides=overrides)

    return scenario


def silent_zone9_shop(city: City) -> str:
    """A covered Z9 shop that trades Tuesday to Thursday (Z9 has no alert on the monsoon day)."""
    return next(
        m.id
        for m in city.merchants_in_zone("Z9")
        if m.id in city.covers and not m.is_demo and m.weekly_off not in WORKING_DAYS
    )


def checked_in(rt: Runtime) -> dict[str, str]:
    entries = rt.audit.entries(limit=5000)
    return {e.subject_id: e.data["first_silent_day"] for e in entries if e.action == "silence.detected"}


async def test_a_shop_shut_since_tuesday_is_checked_in_from_its_first_silent_day(
    static: StaticContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    shop = silent_zone9_shop(static.city)
    monkeypatch.setattr(world, "get_scenario", closed_from(shop, MONSOON_DAY))
    rt = await loaded(static, "illness", seek="11:21")
    assert checked_in(rt) == {ANIL: "2025-08-20", shop: "2025-08-19"}
    assert rt.orchestrator.open_silence(shop) == MONSOON_DAY
    name = static.city.merchant(shop).shop_name
    texts = [i.text_en for i in rt.feed.items() if i.type == "checkin"]
    assert f"Checked in with {name} on WhatsApp · no sales since Tue 19 Aug" in texts


async def test_nobody_covered_means_nobody_is_checked_in(static: StaticContext) -> None:
    uncovered = dataclasses.replace(static.city, covers=MappingProxyType({}))
    bare = make_static(static.settings, uncovered, static.model, static.artifacts_dir)
    rt = await loaded(bare, "illness", seek="11:21")
    assert checked_in(rt) == {} and rt.store.messages(ANIL) == ()
    assert rt.orchestrator.open_silence(ANIL) is None
