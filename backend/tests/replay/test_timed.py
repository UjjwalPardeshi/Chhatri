"""Clock-driven hooks: alert announcements and the 21:00 evening settlement (SPEC §6.4, §9.7, §17.2)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from chhatri.domain.enums import PremiumMethod
from chhatri.replay import views
from chhatri.replay.publish import RuntimeLink
from chhatri.replay.static import StaticContext
from chhatri.replay.timed import EveningSettlement
from tests.replay.helpers import ANIL, BUY_COVER_DAY, MONSOON_DAY, loaded, monsoon_at

ALERT_ID = "A-20250818-01"


async def test_the_monsoon_alert_is_in_the_feed_at_load_and_goes_into_force_at_14_00(
    static: StaticContext,
) -> None:
    rt = await loaded(static, "monsoon")
    alerts = [e for e in rt.bus.history() if e.type == "alert"]
    assert [e.data["alert"]["id"] for e in alerts] == [ALERT_ID]
    assert alerts[0].data["alert"]["issued_at"] == "2025-08-18T17:30:00+05:30"
    assert views.zone_snapshot(rt, "Z7")["alert"]["id"] == ALERT_ID  # forecast shown before it starts
    assert views.zone_panel(rt, "Z7")["rows"][0] == {"label": "Alert", "value": "Red alert from 14:00"}
    assert not any("in force" in i.text_en for i in rt.feed.items())
    await rt.engine.seek("14:00")
    in_force = [i for i in rt.feed.items() if "in force" in i.text_en]
    assert [(i.at, i.text_en) for i in in_force] == [
        (monsoon_at(14), "Red alert in force for Z3, Z7, Z12 until 20:00")
    ]


async def test_buy_cover_sees_the_alert_issued_at_17_30_and_illness_sees_none(static: StaticContext) -> None:
    cover = await loaded(static, "buy_cover")
    [item] = [i for i in cover.feed.items() if i.type == "alert"]
    assert item.at.date() == BUY_COVER_DAY and ALERT_ID not in item.text_en and "Z3, Z7, Z12" in item.text_en
    assert views.zone_panel(cover, "Z3")["rows"][0]["value"] == "Red alert from Tue 14:00"
    illness = await loaded(static, "illness")
    assert not [i for i in illness.feed.items() if i.type == "alert"]
    assert views.zone_snapshot(illness, "Z7")["alert"] is None
    assert views.zone_panel(illness, "Z7")["rows"][0]["value"] == "No weather alert"


async def test_the_evening_settlement_prepays_tomorrow_from_todays_collections(static: StaticContext) -> None:
    rt = await loaded(static, "monsoon")
    cover = rt.store.cover(ANIL)
    assert cover is not None
    rt.store.put_cover(cover.model_copy(update={"prepaid_through": MONSOON_DAY}))  # due for tonight
    link = RuntimeLink()
    link.bind(rt)
    settlement = EveningSettlement(link)
    settlement.on_minute(monsoon_at(20, 59))  # not yet
    assert rt.store.premiums(ANIL) == ()
    settlement.on_minute(monsoon_at(21))
    [payment] = rt.store.premiums(ANIL)
    assert payment.method is PremiumMethod.SETTLEMENT_DEDUCTION
    assert payment.covers_from == MONSOON_DAY + timedelta(days=1)
    assert rt.store.cover(ANIL).prepaid_through == MONSOON_DAY + timedelta(days=1)  # type: ignore[union-attr]
    assert [i.text_en for i in rt.feed.items() if i.type == "premium"] == [
        "Evening settlement: 1 shops prepaid tomorrow's premium from today's collections"
    ]
    settlement.on_minute(monsoon_at(21))  # once a day
    assert len(rt.store.premiums(ANIL)) == 1
    with pytest.raises(ValueError, match="no completed hour"):
        settlement.settle(MONSOON_DAY + timedelta(days=1), monsoon_at(21))
