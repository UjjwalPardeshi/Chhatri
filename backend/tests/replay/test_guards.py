"""Input validation and small helpers of the replay package (SPEC §8.2, §17.2, §19.2; B1, B4)."""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from chhatri.audit.log import AuditLog
from chhatri.clock import ManualClock, at
from chhatri.detect.types import ZoneState
from chhatri.domain.models import AreaTrigger
from chhatri.integrations.base import WorkflowRun
from chhatri.replay import views
from chhatri.replay.board import ZoneBoard, slow_day_explanation, trigger_day, zone_number
from chhatri.replay.evidence import hourly_evidence
from chhatri.replay.feed import FeedItem, FeedLog
from chhatri.replay.fmt import day_month, hhmm, weekday_day_month, weekday_short
from chhatri.replay.live import HexIndex
from chhatri.replay.publish import RuntimeLink
from chhatri.replay.runs import start_payout
from chhatri.replay.state import Runtime
from chhatri.replay.static import StaticContext
from chhatri.replay.world import build_scenario_data, build_world, scenario_days
from chhatri.sim.types import City
from tests.replay.helpers import ANIL, MONSOON_DAY, make_static, monsoon_at


def _trigger(zone_id: str = "Z7") -> AreaTrigger:
    return AreaTrigger(
        id=f"E-{zone_id}-20250819",
        zone_id=zone_id,
        alert_id="A-20250818-01",
        window_start=monsoon_at(14),
        window_end=monsoon_at(17),
        index_pct=37,
        drop_pct=63,
        hourly_index_pct=(38, 36, 37),
        lower_bound_pct=92,
        shops_in_index=46,
        fired_at=monsoon_at(17),
    )


def test_world_validation(monsoon_1705: Runtime, static: StaticContext, tmp_path: object) -> None:
    scenario = monsoon_1705.scenario
    with pytest.raises(ValueError, match="must start on its day"):
        scenario_days(dataclasses.replace(scenario, end=scenario.start))
    assert scenario_days(dataclasses.replace(scenario, end=at(MONSOON_DAY + timedelta(days=1), 1))) == (
        MONSOON_DAY,
        MONSOON_DAY + timedelta(days=1),
    )
    early = dataclasses.replace(scenario, start=at(MONSOON_DAY, 2))
    with pytest.raises(ValueError, match="starts before 3:00"):
        build_scenario_data(
            static.city, monsoon_1705.world.model, early, monsoon_1705.shocks, seed=1, rules=static.rules
        )
    no_model = make_static(static.settings, static.city, None, static.artifacts_dir, model_error="missing")
    with pytest.raises(RuntimeError, match="missing"):
        build_world(no_model, "monsoon")
    with pytest.raises(KeyError, match="unknown alert"):
        monsoon_1705.world.alert("A-20990101-01")


def test_zone_board_rules() -> None:
    assert zone_number("Z12") == "12"
    for bad in ("12", "Z", "ZX", "Q7"):
        with pytest.raises(ValueError, match="not a zone id"):
            zone_number(bad)
    assert slow_day_explanation("Z9", 61) == (
        "Why Zone 9 got nothing: its sales fell to 61% on a day with no weather alert. "
        "That's a slow day, not a loss event, so Chhatri doesn't pay."
    )
    board, trigger = ZoneBoard(), _trigger()
    assert trigger_day(trigger) == MONSOON_DAY
    board.start_progress(trigger)
    with pytest.raises(ValueError, match="already being paid"):
        board.start_progress(trigger)
    with pytest.raises(KeyError, match="no payout progress"):
        board.count_credit("E-Z3-20250819", 100, monsoon_at(17, 4))
    assert board.mark_announced(trigger.id, "credit") and not board.mark_announced(trigger.id, "credit")
    progress = board.count_approval(trigger.id, 138_000)
    assert not progress.all_credited  # not sealed: claims may still be deciding
    progress = board.count_credit(trigger.id, 138_000, monsoon_at(17, 4))
    assert not progress.all_credited and board.seal(trigger.id).all_credited


def test_the_board_announces_watch_and_slow_day_transitions_once() -> None:
    board = ZoneBoard()

    def state(zone: str, status: str, below: int, index: int | None = 45) -> ZoneState:
        return ZoneState(zone, status, index, (index, index, index), below, None, 30, 80)  # type: ignore[arg-type]

    changes = board.record_hour(
        monsoon_at(15), {"Z7": state("Z7", "watch", 1), "Z9": state("Z9", "slow_day", 1)}, ()
    )
    assert [s.zone_id for s in changes.watch] == ["Z7"] and [s.zone_id for s in changes.slow] == ["Z9"]
    changes = board.record_hour(
        monsoon_at(16), {"Z7": state("Z7", "watch", 2), "Z9": state("Z9", "slow_day", 2)}, ()
    )
    assert [s.hours_below for s in changes.watch] == [2] and changes.slow == ()
    changes = board.record_hour(
        monsoon_at(17),
        {"Z7": state("Z7", "triggered", 3), "Z9": state("Z9", "slow_day", 3, None)},
        (_trigger(),),
    )
    assert changes.watch == () and board.triggered == frozenset({("Z7", MONSOON_DAY)})
    assert board.explanations["Z9"].startswith("Why Zone 9 got nothing: its sales fell to 45%")


def test_feed_log_validation_and_order() -> None:
    feed = FeedLog()
    with pytest.raises(ValueError, match="needs a type and a text"):
        feed.add(monsoon_at(8), "alert", "  ")
    for minute in range(3):
        feed.add(monsoon_at(8, minute), "tick", f"item {minute}", merchant_id=ANIL)
    assert [item.id for item in feed.latest(2)] == [3, 2]
    with pytest.raises(ValueError, match="at least 1"):
        feed.latest(0)
    view = views.feed_view(FeedItem(7, monsoon_at(8), "checkin", "Checked in", None, ANIL))
    assert view == {
        "id": 7,
        "at": "2025-08-19T08:00:00+05:30",
        "type": "checkin",
        "text_en": "Checked in",
        "merchant_id": ANIL,
    }


def test_english_date_words_do_not_depend_on_the_locale() -> None:
    assert (hhmm(monsoon_at(17, 4)), weekday_short(MONSOON_DAY)) == ("17:04", "Tue")
    assert (day_month(date(2025, 8, 25)), weekday_day_month(date(2025, 8, 20))) == ("25 Aug", "Wed 20 Aug")


def test_hex_index_needs_every_merchant_inside_the_grid(small_city: City) -> None:
    no_grid = dataclasses.replace(small_city, geography=dataclasses.replace(small_city.geography, hexes=()))
    with pytest.raises(ValueError, match="outside the hex grid"):
        HexIndex.build(no_grid)


def test_the_runtime_link_binds_once() -> None:
    link = RuntimeLink()
    with pytest.raises(RuntimeError, match="not assembled"):
        _ = link.rt
    link.bind(SimpleNamespace())  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="already bound"):
        link.bind(SimpleNamespace())  # type: ignore[arg-type]


def test_evidence_hours_are_only_completed_business_hours(monsoon_1705: Runtime) -> None:
    rt = monsoon_1705
    assert hourly_evidence(rt, ANIL, MONSOON_DAY, at(MONSOON_DAY, 6, 30)) == []  # opens at 06:00
    assert hourly_evidence(rt, ANIL, MONSOON_DAY + timedelta(days=1), rt.clock.now()) == []
    earlier = hourly_evidence(rt, ANIL, MONSOON_DAY - timedelta(days=1), rt.clock.now())
    profile = rt.static.city.profiles[ANIL]
    assert len(earlier) == profile.close_hour - profile.open_hour  # a past day is complete


def test_merchant_detail_has_no_expected_label_off_the_scenario_day(monsoon_1705: Runtime) -> None:
    tomorrow = dataclasses.replace(monsoon_1705, clock=ManualClock(at(MONSOON_DAY + timedelta(days=1), 9)))
    assert views.merchant_detail(tomorrow, ANIL)["expected_today_label"] is None


class NotAccepted:
    async def start(self, workflow: str, payload: dict) -> WorkflowRun:
        return WorkflowRun(
            workflow, f"{workflow}:{payload['decision_id']}", "in-process", False, "already started"
        )


async def test_a_run_the_engine_did_not_accept_is_returned_as_is() -> None:
    audit = AuditLog(None)
    rt = SimpleNamespace(
        integrations=SimpleNamespace(workflows=NotAccepted()),
        audit=audit,
        clock=ManualClock(monsoon_at(17)),
        feed=FeedLog(),
    )
    run = await start_payout(rt, "D-000001", ANIL)  # type: ignore[arg-type]
    assert run is not None and run.accepted is False and len(audit) == 0
