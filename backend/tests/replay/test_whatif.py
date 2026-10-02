"""H24 what-if (fs-08 section 11, data-model-and-api section 5.9): the engine recomputes one zone, writes nothing.

The baseline is read from the detector's own arrays, so the first tests hold it against `evaluate_hour` itself,
zone by zone and hour by hour. The rest change one input at a time and check the verdict the shared rule
(`trigger_verdict`) gives, then the amount arithmetic of one shop, the validation and the read-only promise.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final

import pytest

from chhatri.api.schemas import WhatIfArea
from chhatri.clock import ManualClock, at, ist
from chhatri.detect.triggers import CONDITION_ORDER, evaluate_hour
from chhatri.money import format_inr
from chhatri.policy.amounts import area_breakdown
from chhatri.policy.engine import publish_expected_day
from chhatri.policy.explain import area_formulas
from chhatri.policy.rules import default_rules
from chhatri.replay import views
from chhatri.replay.board import trigger_day
from chhatri.replay.state import Runtime
from chhatri.replay.static import StaticContext
from chhatri.replay.whatif import NoCompletedWindow, Overrides, WhatIfInputError, what_if
from tests.replay.fingerprint import fingerprint
from tests.replay.helpers import ANIL, MONSOON_DAY, RAMESH, loaded, offline_settings, run_in_thread

HOUR: Final = timedelta(hours=1)
FIVE: Final = [code.value for code in CONDITION_ORDER]
NOW_1700: Final = at(MONSOON_DAY, 17)
SHAPE_KEYS: Final = {"kind", "label", "ref", "as_of", "origin", "clause"}


@pytest.fixture(scope="module")
def rt(monsoon_1705: Runtime) -> Runtime:
    """The monsoon at 17:05: the 17:00 evaluation is done, so Z3, Z7 and Z12 have fired and Z9 is a slow day."""
    return monsoon_1705


@pytest.fixture(scope="module")
def rt_1800(static: StaticContext) -> Runtime:
    """The same replay an hour later: the three zones fired at 17:00, so they have triggered earlier today."""
    return run_in_thread(lambda: loaded(static, "monsoon", seek="18:00"))


def ask(runtime: Runtime, zone: str = "Z9", **kwargs: Any) -> dict[str, Any]:
    """The JSON of one what-if call; every response is checked against the strict schema."""
    view = views.whatif_view(what_if(runtime, zone_id=zone, **kwargs))
    WhatIfArea.model_validate(view)
    return view


def condition(view: dict[str, Any], code: str) -> dict[str, Any]:
    return next(c for c in view["conditions"] if c["code"] == code)


def unmet(view: dict[str, Any], side: str) -> list[str]:
    return [c["code"] for c in view["conditions"] if not c[side]["met"]]


def detector_at(runtime: Runtime, when: datetime) -> tuple[Any, Any]:
    """`evaluate_hour` for the hour boundary `when`, called the way the replay calls it."""
    world, rules = runtime.world, runtime.static.rules
    window = rules.area.consecutive_hours * HOUR
    alerts = world.shocks.alerts_between(when - window, when)
    earlier = frozenset((t.zone_id, trigger_day(t)) for t in runtime.store.triggers() if t.fired_at < when)
    return evaluate_hour(
        when, runtime.static.city, world.visible(when), world.p50, alerts, world.lower_bounds, rules, earlier
    )


# ---------------------------------------------------------------- the baseline is the engine's own


def test_no_overrides_reproduces_the_engine_verdict_for_every_zone(rt: Runtime) -> None:
    """Every zone, every hour the replay has completed: the baseline is what `evaluate_hour` decided."""
    zones = [z.id for z in rt.static.city.zones]
    checked = 0
    for hour in range(3, 18):
        when = at(MONSOON_DAY, hour)
        triggers, states = detector_at(rt, when)
        fired = {t.zone_id for t in triggers}
        for zone in zones:
            view = ask(rt, zone, at=when)
            state, base = states[zone], view["baseline"]
            assert base["hourly_index_pct"] == list(state.hourly_pct), (zone, hour)
            assert base["window_index_pct"] == state.index_pct, (zone, hour)
            assert base["shops_in_index"] == state.shops_in_index, (zone, hour)
            assert (base["status"], base["alert_id"]) == (state.status, state.alert_id), (zone, hour)
            assert view["fixed"]["lower_bound_pct"] == state.lower_bound_pct, (zone, hour)
            assert base["fires"] is (zone in fired), (zone, hour)
            assert view["scenario"] == base and view["changed"] == [], (zone, hour)
            checked += 1
    assert checked == len(zones) * 15


def test_the_baseline_names_the_alert_and_the_day_so_far(rt: Runtime) -> None:
    z7, z9 = ask(rt, "Z7"), ask(rt, "Z9")
    assert (z7["baseline"]["alert"], z7["baseline"]["alert_id"]) == ("RAIN", "A-20250818-01")
    assert (z9["baseline"]["alert"], z9["baseline"]["alert_id"]) == ("NONE", None)
    assert z7["baseline"]["already_triggered_today"] is False  # it fires at 17:00, not before it
    assert z7["baseline"]["fires"] and z7["baseline"]["status"] == "triggered"
    assert z7["baseline"]["drop_pct"] == 100 - z7["baseline"]["window_index_pct"]
    assert "drop_pct" not in z9["baseline"]  # a side that does not fire has no drop


def test_at_defaults_to_the_last_completed_hour_and_the_response_is_labelled(rt: Runtime) -> None:
    view = ask(rt, "Z9")
    assert view["at"] == "2025-08-19T17:00:00+05:30"
    assert view["window"] == {"start": "2025-08-19T14:00:00+05:30", "end": "2025-08-19T17:00:00+05:30"}
    assert (view["zone_id"], view["zone_name"]) == ("Z9", "Chembur")
    assert (view["read_only"], view["stored"]) == (True, False)
    assert view["computed_by"] == "policy engine, deterministic"
    assert view["rules_version"] == "pilot-0.1" and "mode" not in view and "provider" not in view
    rules = default_rules().area
    assert view["fixed"] == {
        "index_floor_pct": rules.index_floor_pct,
        "consecutive_hours": rules.consecutive_hours,
        "min_shops_in_index": rules.min_shops_in_index,
        "lower_bound_pct": rt.world.lower_bounds["Z9"],
    }
    earlier = ask(rt, "Z9", at=at(MONSOON_DAY, 16))
    assert earlier["window"]["end"] == "2025-08-19T16:00:00+05:30"


def test_an_earlier_hour_does_not_see_the_zone_fire_later(rt_1800: Runtime) -> None:
    """At 17:00 Z7 fires now. From 18:00 on it has already triggered today, and the rule says so."""
    at_17 = ask(rt_1800, "Z7", at=NOW_1700)
    assert (at_17["baseline"]["fires"], at_17["baseline"]["already_triggered_today"]) == (True, False)
    at_18 = ask(rt_1800, "Z7")
    assert at_18["at"] == "2025-08-19T18:00:00+05:30"
    assert (at_18["baseline"]["fires"], at_18["baseline"]["status"]) == (False, "triggered")
    assert at_18["baseline"]["already_triggered_today"] is True
    assert unmet(at_18, "baseline")[-1] == "FIRST_TRIGGER_TODAY"
    assert condition(at_18, "FIRST_TRIGGER_TODAY")["baseline"]["observed"] == "already triggered today"
    assert condition(at_17, "FIRST_TRIGGER_TODAY")["baseline"]["observed"] == "not yet"


def test_a_second_trigger_needs_the_day_to_be_new(rt_1800: Runtime) -> None:
    """Turning 'already triggered today' off lets a window under the floor with an alert fire again."""
    storm = {"alert": "RAIN", "hourly_index_pct": (40, 40, 40)}
    blocked = ask(rt_1800, "Z7", overrides=Overrides(**storm))
    assert blocked["scenario"]["fires"] is False and unmet(blocked, "scenario") == ["FIRST_TRIGGER_TODAY"]
    again = ask(rt_1800, "Z7", overrides=Overrides(**storm, already_triggered_today=False))
    assert again["scenario"]["fires"] is True and again["scenario"]["drop_pct"] == 60
    assert again["changed"] == [
        "hourly_index_pct",
        "already_triggered_today",
    ]  # the real alert already covers it


# ---------------------------------------------------------------- one input at a time


def test_z9_baseline_is_a_slow_day_with_two_conditions_failing(rt: Runtime) -> None:
    """AC-H24-01."""
    view = ask(rt, "Z9")
    assert (view["baseline"]["fires"], view["baseline"]["status"]) == (False, "slow_day")
    assert unmet(view, "baseline") == ["ALERT_COVERS_WINDOW", "HOURS_BELOW_FLOOR"]
    assert view["changed"] == [] and view["scenario"] == view["baseline"]


def test_z9_baseline_carries_the_zone_no_trigger_counterfactual(rt: Runtime) -> None:
    """data-model 5.9: with no overrides, a zone that did not fire carries fs-09 9.4's ZONE_NO_TRIGGER object."""
    cf = ask(rt, "Z9")["counterfactual"]
    assert cf is not None and (cf["kind"], cf["actionable"], cf["verified"]) == (
        "ZONE_NO_TRIGGER",
        False,
        True,
    )
    assert [c["field"] for c in cf["changes"]] == ["alert_covers_window", "hourly_index_pct"]
    assert cf["result"] == {"outcome": None, "amount_paise": None, "amount_label": None}
    assert cf["text_en"] and cf["text_hi"] and cf["sources"]


def test_a_zone_that_fired_or_an_edited_scenario_has_no_counterfactual(rt: Runtime) -> None:
    assert ask(rt, "Z7")["counterfactual"] is None
    assert ask(rt, "Z9", overrides=Overrides(alert="RAIN"))["counterfactual"] is None


def test_z9_with_alert_and_hours_at_49_fires(rt: Runtime) -> None:
    """AC-H24-02: a rain alert and every hour at 49 give a 51% drop."""
    view = ask(rt, "Z9", overrides=Overrides(alert="RAIN", hourly_index_pct=(49, 49, 49)))
    scenario = view["scenario"]
    assert (scenario["fires"], scenario["status"], scenario["drop_pct"]) == (True, "triggered", 51)
    assert (scenario["alert"], scenario["alert_id"], scenario["window_index_pct"]) == ("RAIN", None, 49)
    assert scenario["hourly_index_pct"] == [49, 49, 49] and unmet(view, "scenario") == []
    assert view["changed"] == ["alert", "hourly_index_pct"]
    assert view["baseline"]["fires"] is False  # the baseline side never moves


def test_hour_at_50_does_not_count(rt: Runtime) -> None:
    """AC-H24-03: the floor is strict, so an hour at exactly 50 fails the condition."""
    base = ask(rt, "Z12")["baseline"]["hourly_index_pct"]
    assert base[0] < 50 and base[1] < 50 and base[2] < 50  # Z12 fired at 17:00
    at_floor = ask(rt, "Z12", overrides=Overrides(hourly_index_pct=(50, base[1], base[2])))
    assert unmet(at_floor, "scenario") == ["HOURS_BELOW_FLOOR"]
    assert (at_floor["scenario"]["fires"], at_floor["scenario"]["status"]) == (False, "watch")
    just_under = ask(rt, "Z12", overrides=Overrides(hourly_index_pct=(49, base[1], base[2])))
    assert just_under["scenario"]["fires"] is True


def test_heatwave_alert_does_not_count(rt: Runtime) -> None:
    storm = (49, 49, 49)
    heat = ask(rt, "Z9", overrides=Overrides(alert="HEATWAVE", hourly_index_pct=storm))
    assert unmet(heat, "scenario") == ["ALERT_COVERS_WINDOW"]
    assert (heat["scenario"]["alert"], heat["scenario"]["fires"]) == ("HEATWAVE", False)
    assert "heat alert" in condition(heat, "ALERT_COVERS_WINDOW")["scenario"]["observed"]
    for kind in ("RAIN", "CIVIC"):
        assert ask(rt, "Z9", overrides=Overrides(alert=kind, hourly_index_pct=storm))["scenario"]["fires"]


def test_removing_the_alert_stops_a_zone_that_fired(rt: Runtime) -> None:
    view = ask(rt, "Z7", overrides=Overrides(alert="NONE"))
    assert view["baseline"]["fires"] and view["changed"] == ["alert"]
    assert (view["scenario"]["alert"], view["scenario"]["alert_id"]) == ("NONE", None)
    assert (view["scenario"]["fires"], view["scenario"]["status"]) == (False, "slow_day")
    assert unmet(view, "scenario") == ["ALERT_COVERS_WINDOW"]


def test_quorum_below_20_blocks(rt: Runtime) -> None:
    low = ask(rt, "Z7", overrides=Overrides(shops_in_index=19))
    assert unmet(low, "scenario") == ["SHOPS_QUORUM"] and low["changed"] == ["shops_in_index"]
    assert (low["scenario"]["fires"], low["scenario"]["status"]) == (False, "no_data")
    assert ask(rt, "Z7", overrides=Overrides(shops_in_index=20))["scenario"]["fires"] is True
    assert ask(rt, "Z7", overrides=Overrides(shops_in_index=0))["scenario"]["status"] == "no_data"


def test_window_index_uses_the_zones_expected_weights(rt: Runtime) -> None:
    """Σ(index × expected) ÷ Σ expected, half up: an hour that sells more weighs more than the plain mean says."""
    outcome = what_if(rt, zone_id="Z9", overrides=Overrides(hourly_index_pct=(0, 50, 100)))
    weights = outcome.facts.expected_paise
    assert len(weights) == 3 and all(w > 0 for w in weights) and len(set(weights)) > 1
    weighted = sum(Decimal(v * w) for v, w in zip((0, 50, 100), weights, strict=True)) / sum(weights)
    expected = int(weighted.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    assert outcome.scenario.window_pct == expected != 50  # the plain mean of the three hours would say 50
    flat = what_if(rt, zone_id="Z9", overrides=Overrides(hourly_index_pct=(37, 37, 37)))
    assert flat.scenario.window_pct == 37  # equal hours leave the weights nothing to do


def test_overrides_equal_to_the_baseline_change_nothing(rt: Runtime) -> None:
    base = ask(rt, "Z7")["baseline"]
    same = Overrides(
        alert="RAIN",
        hourly_index_pct=tuple(base["hourly_index_pct"]),
        shops_in_index=base["shops_in_index"],
        already_triggered_today=False,
    )
    view = ask(rt, "Z7", overrides=same)
    assert view["changed"] == [] and view["scenario"] == view["baseline"]
    assert view["scenario"]["alert_id"] == "A-20250818-01"  # the real alert, not a made-up one


def test_the_five_conditions_come_with_words_and_sources(rt: Runtime) -> None:
    view = ask(rt, "Z9", overrides=Overrides(alert="RAIN", hourly_index_pct=(49, 49, 49)))
    assert [c["code"] for c in view["conditions"]] == FIVE
    alert, hours = condition(view, "ALERT_COVERS_WINDOW"), condition(view, "HOURS_BELOW_FLOOR")
    assert alert["label_en"] == "A rain or civic alert covers all 3 hours"
    assert alert["required"] == "a RAIN or CIVIC alert issued by 17:00 and valid for the whole window"
    assert alert["baseline"] == {"met": False, "observed": "no alert for Z9 on 19 Aug 2025"}
    assert alert["scenario"] == {"met": True, "observed": "a rain alert covering 14:00 to 17:00"}
    assert hours["label_en"] == "Every hour is below 50%" and hours["required"] == "each hour below 50"
    base_hours = ask(rt, "Z9")["baseline"]["hourly_index_pct"]
    assert hours["baseline"]["observed"] == ", ".join(str(v) for v in base_hours)
    assert hours["scenario"] == {"met": True, "observed": "49, 49, 49"}
    for item in view["conditions"]:
        assert item["sources"] and all(set(s) == SHAPE_KEYS for s in item["sources"]), item["code"]
        assert all(s["ref"] and s["origin"] in {"CONFIG", "SIMULATED", "LIVE"} for s in item["sources"])
    clause = alert["sources"][-1]
    assert clause == {
        "kind": "CLAUSE",
        "label": "Area income loss",
        "ref": "clause:C2",
        "as_of": None,
        "origin": "CONFIG",
        "clause": "C2",
    }


def test_sources_point_at_records_that_exist(rt: Runtime) -> None:
    """A Source ref resolves: the real alert and trigger for Z7, a rules key, a clause. Z9 has no trigger."""
    z7, z9 = ask(rt, "Z7"), ask(rt, "Z9")
    refs7 = {s["ref"] for c in z7["conditions"] for s in c["sources"]}
    assert {"alert:A-20250818-01", "trigger:E-Z7-20250819", "zone-bound:Z7", "clause:C2"} <= refs7
    assert (
        "rules:pilot-0.1:area.index_floor_pct" in refs7 and "rules:pilot-0.1:area.min_shops_in_index" in refs7
    )
    alert_source = next(s for c in z7["conditions"] for s in c["sources"] if s["kind"] == "ALERT")
    assert alert_source["as_of"] == "2025-08-18T17:30:00+05:30" and alert_source["origin"] == "SIMULATED"
    refs9 = {s["ref"] for c in z9["conditions"] for s in c["sources"]}
    assert not any(
        ref.startswith(("trigger:", "alert:")) for ref in refs9
    )  # nothing fired, no alert in force


def test_a_trigger_backs_only_its_own_window(rt_1800: Runtime) -> None:
    """At 18:00 the window is 15:00 to 18:00: the 17:00 trigger's index is not its source, only the day's."""

    def trigger_refs(view: dict[str, Any]) -> dict[str, list[str]]:
        return {
            c["code"]: [s["ref"] for s in c["sources"] if s["kind"] == "SALES_INDEX"]
            for c in view["conditions"]
        }

    own = ["trigger:E-Z7-20250819"]
    assert trigger_refs(ask(rt_1800, "Z7", at=NOW_1700)) == {
        "ALERT_COVERS_WINDOW": [],
        "HOURS_BELOW_FLOOR": own,
        "WINDOW_BELOW_BOUND": own,
        "SHOPS_QUORUM": own,
        "FIRST_TRIGGER_TODAY": own,
    }
    assert trigger_refs(ask(rt_1800, "Z7")) == {
        "ALERT_COVERS_WINDOW": [],
        "HOURS_BELOW_FLOOR": [],
        "WINDOW_BELOW_BOUND": [],
        "SHOPS_QUORUM": [],
        "FIRST_TRIGGER_TODAY": own,  # the trigger earlier today is why this one fails
    }


def test_no_alert_names_the_day_only_when_the_zone_had_none_that_day(rt: Runtime) -> None:
    """Z7's rain alert (issued the evening before) starts at 14:00: at 12:00 the zone had one that day."""
    early = condition(ask(rt, "Z7", at=at(MONSOON_DAY, 12)), "ALERT_COVERS_WINDOW")
    assert early["baseline"] == {"met": False, "observed": "no alert covering 09:00 to 12:00"}
    removed = condition(ask(rt, "Z7", overrides=Overrides(alert="NONE")), "ALERT_COVERS_WINDOW")
    assert removed["scenario"] == {"met": False, "observed": "no alert covering 14:00 to 17:00"}
    z9 = condition(ask(rt, "Z9", at=at(MONSOON_DAY, 12)), "ALERT_COVERS_WINDOW")
    assert z9["baseline"]["observed"] == "no alert for Z9 on 19 Aug 2025"  # no alert at all that day


def test_an_alert_that_covers_only_part_of_the_window_is_named_as_such(rt: Runtime) -> None:
    """At 16:00 the alert (valid from 14:00) covers the last two hours of 13:00 to 16:00, so it does not count."""
    view = ask(rt, "Z7", at=at(MONSOON_DAY, 16))
    alert = condition(view, "ALERT_COVERS_WINDOW")
    assert alert["baseline"] == {"met": False, "observed": "a rain alert covers only part of 13:00 to 16:00"}
    assert (view["baseline"]["alert"], view["baseline"]["alert_id"]) == ("RAIN", "A-20250818-01")
    assert alert["sources"][0]["ref"] == "alert:A-20250818-01"  # the alert in force is still the source
    whole = ask(rt, "Z7", at=at(MONSOON_DAY, 16), overrides=Overrides(alert="RAIN"))
    assert whole["changed"] == ["alert"]  # a whole-window RAIN alert is a change from a partial one
    assert whole["scenario"]["alert_id"] is None
    assert condition(whole, "ALERT_COVERS_WINDOW")["scenario"] == {
        "met": True,
        "observed": "a rain alert covering 13:00 to 16:00",
    }


def test_a_zone_with_no_covered_shop_reads_no_data(rt: Runtime) -> None:
    view = ask(rt, "Z1")
    assert (view["baseline"]["status"], view["baseline"]["shops_in_index"]) == ("no_data", 0)
    assert (
        view["baseline"]["hourly_index_pct"] == [None, None, None]
        and view["baseline"]["window_index_pct"] is None
    )
    assert condition(view, "HOURS_BELOW_FLOOR")["baseline"]["observed"] == "no data, no data, no data"
    assert condition(view, "WINDOW_BELOW_BOUND")["baseline"]["observed"] == "no sales expected in the window"
    typed = ask(rt, "Z1", overrides=Overrides(alert="RAIN", hourly_index_pct=(10, 10, 10), shops_in_index=1))
    assert condition(typed, "SHOPS_QUORUM")["scenario"]["observed"] == "1 shop"
    assert typed["scenario"]["window_index_pct"] is None and typed["scenario"]["fires"] is False  # no weights


# ---------------------------------------------------------------- one shop's amount


def anil_arithmetic(runtime: Runtime, drop_pct: int) -> Any:
    expected = runtime.world.expected_day_paise(runtime.static.city.row(ANIL), MONSOON_DAY)
    return area_breakdown(publish_expected_day(expected), drop_pct, runtime.static.rules)


def test_example_uses_area_breakdown(rt: Runtime) -> None:
    """AC-H24-05 on the test city: every hour at 45 is a 55% drop, priced by the engine's own arithmetic."""
    view = ask(rt, "Z7", overrides=Overrides(hourly_index_pct=(45, 45, 45)), example_merchant_id=ANIL)
    b = anil_arithmetic(rt, 55)
    assert view["example"] == {
        "merchant_id": ANIL,
        "shop_name": "Anil's Tea Stall",
        "expected_day_paise": b.expected_day_paise,
        "drop_pct": 55,
        "lost_paise": b.lost_paise,
        "share_paise": b.share_paise,
        "cap_paise": b.cap_paise,
        "capped": b.capped,
        "amount_paise": b.amount_paise,
        "amount_label": format_inr(b.amount_paise),
        "formula_en": area_formulas(b, rt.static.rules)[0],
        "scope": "amount arithmetic only",
    }
    assert view["scenario"]["drop_pct"] == 55 and view["example"]["amount_paise"] > 0


def test_the_example_follows_the_zone_without_overrides(rt: Runtime) -> None:
    view = ask(rt, "Z7", example_merchant_id=ANIL)  # the real 17:00 window of Z7
    drop = view["baseline"]["drop_pct"]
    assert view["example"]["drop_pct"] == drop
    assert view["example"]["amount_paise"] == anil_arithmetic(rt, drop).amount_paise
    real = next(p for p in rt.store.payouts() if p.merchant_id == ANIL)
    assert view["example"]["amount_paise"] == real.amount_paise  # what Anil was really paid


def test_no_example_when_nothing_would_be_paid(rt: Runtime) -> None:
    assert ask(rt, "Z9")["example"] is None
    view = ask(rt, "Z7", overrides=Overrides(alert="NONE"), example_merchant_id=ANIL)
    assert view["example"] is None  # it would not fire, so there is no payout to price


def test_a_capped_payout_says_so(rt: Runtime) -> None:
    """Even a total loss stays under the daily cap, and the formula says when it binds."""
    view = ask(rt, "Z7", overrides=Overrides(hourly_index_pct=(0, 0, 0)), example_merchant_id=ANIL)
    b = anil_arithmetic(rt, 100)
    assert view["example"]["capped"] is b.capped
    assert view["example"]["amount_paise"] == min(b.share_paise, b.cap_paise)


# ---------------------------------------------------------------- validation


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        ({"at": at(MONSOON_DAY, 17, 30)}, "at"),  # not an hour boundary
        ({"at": at(MONSOON_DAY, 18)}, "at"),  # after the clock's last completed hour
        ({"at": at(MONSOON_DAY, 2)}, "at"),  # the window would start the day before
        ({"at": at(MONSOON_DAY - timedelta(days=1), 17)}, "at"),
        ({"at": datetime(2025, 8, 19, 17)}, "at"),  # no time zone
        ({"overrides": Overrides(hourly_index_pct=(49, 49))}, "overrides.hourly_index_pct"),
        ({"overrides": Overrides(hourly_index_pct=(49, 49, 49, 49))}, "overrides.hourly_index_pct"),
        ({"example_merchant_id": RAMESH}, "example_merchant_id"),  # in Z3 and uncovered
        ({"example_merchant_id": "S-9999"}, "example_merchant_id"),  # not a shop of this city
        ({"zone_id": "Z3", "example_merchant_id": ANIL}, "example_merchant_id"),  # Anil is in Z7
    ],
)
def test_whatif_validation(rt: Runtime, kwargs: dict[str, Any], field: str) -> None:
    with pytest.raises(WhatIfInputError) as caught:
        what_if(rt, **{"zone_id": "Z9", **kwargs})
    assert caught.value.field == field and caught.value.reason
    assert "S-9999" not in caught.value.reason and "2025" not in caught.value.reason  # inputs are not echoed


def test_an_unknown_zone_is_a_key_error(rt: Runtime) -> None:
    with pytest.raises(KeyError):
        what_if(rt, zone_id="Z99")


def test_no_completed_window_yet_is_a_conflict() -> None:
    clock = ManualClock(ist(2025, 8, 19, 2, 30))  # only two full hours of the day are done
    early = SimpleNamespace(
        clock=clock,
        world=SimpleNamespace(day_start=at(MONSOON_DAY, 0)),
        static=SimpleNamespace(rules=default_rules()),
    )
    with pytest.raises(NoCompletedWindow, match="no completed 3-hour window yet"):
        what_if(early, zone_id="Z9")  # type: ignore[arg-type]


def test_the_earliest_and_latest_hours_are_allowed(rt: Runtime) -> None:
    assert ask(rt, "Z9", at=at(MONSOON_DAY, 3))["at"] == "2025-08-19T03:00:00+05:30"
    assert ask(rt, "Z9", at=NOW_1700)["at"] == "2025-08-19T17:00:00+05:30"
    assert ask(rt, "Z9", at=ist(2025, 8, 19, 11, 0))["window"]["start"] == "2025-08-19T08:00:00+05:30"
    utc = datetime.fromisoformat("2025-08-19T11:30:00+00:00")  # 17:00 IST written in UTC
    assert ask(rt, "Z9", at=utc)["at"] == "2025-08-19T17:00:00+05:30"


# ---------------------------------------------------------------- read-only


def test_whatif_is_read_only(rt: Runtime) -> None:
    """Many calls change nothing: audit, id counters, store, feed, event bus, board and clock."""
    before = fingerprint(rt)
    calls = 0
    for zone in ("Z3", "Z7", "Z9", "Z12", "Z1"):
        for overrides in (
            Overrides(),
            Overrides(alert="RAIN", hourly_index_pct=(49, 49, 49)),
            Overrides(alert="NONE", shops_in_index=0, already_triggered_today=True),
            Overrides(hourly_index_pct=(0, 1000, 50)),
        ):
            for hour in (None, at(MONSOON_DAY, 12)):
                ask(
                    rt, zone, at=hour, overrides=overrides, example_merchant_id=ANIL if zone == "Z7" else None
                )
                calls += 1
    assert calls == 40
    assert fingerprint(rt) == before


def test_the_same_call_gives_the_same_answer(rt: Runtime) -> None:
    kwargs = {
        "overrides": Overrides(alert="CIVIC", hourly_index_pct=(10, 20, 30)),
        "example_merchant_id": ANIL,
    }
    assert ask(rt, "Z7", **kwargs) == ask(rt, "Z7", **kwargs)


# ---------------------------------------------------------------- the full city (slow)


@pytest.mark.slow
def test_the_deck_numbers_on_the_full_city(tmp_path_factory: pytest.TempPathFactory) -> None:
    """AC-H24-01 to -05 with the demo's figures: Z9 at 61%, ₹1,205 at a 55% drop, ₹1,380 at the real 63%."""
    from chhatri.replay.static import ARTIFACTS_DIR, MODEL_DIR, PREMIUMS_FILE, load_static
    from chhatri.sim.calibration import CALIBRATION_FILE

    missing = [n for n in (MODEL_DIR, CALIBRATION_FILE, PREMIUMS_FILE) if not (ARTIFACTS_DIR / n).exists()]
    if missing:
        pytest.skip(f"artefacts missing in {ARTIFACTS_DIR}: {missing} (run make data)")
    static = load_static(offline_settings(Path(tmp_path_factory.mktemp("whatif-golden"))))
    full = run_in_thread(lambda: loaded(static, "monsoon", seek="17:05"))

    z9 = ask(full, "Z9")
    assert z9["baseline"]["hourly_index_pct"] == [59, 58, 67] and z9["baseline"]["window_index_pct"] == 61
    # 64 shops are covered in Z9, but two are off on Tuesdays, so the detector indexes 62 (the contract said 64)
    assert (z9["baseline"]["shops_in_index"], z9["fixed"]["lower_bound_pct"]) == (62, 90)
    assert (z9["baseline"]["fires"], z9["baseline"]["status"]) == (False, "slow_day")
    assert unmet(z9, "baseline") == ["ALERT_COVERS_WINDOW", "HOURS_BELOW_FLOOR"]
    fires = ask(full, "Z9", overrides=Overrides(alert="RAIN", hourly_index_pct=(49, 49, 49)))
    assert (fires["scenario"]["fires"], fires["scenario"]["drop_pct"]) == (True, 51)

    z7 = ask(full, "Z7", overrides=Overrides(hourly_index_pct=(45, 45, 45)), example_merchant_id=ANIL)
    assert z7["scenario"]["drop_pct"] == 55 and z7["example"]["amount_label"] == "₹1,205"
    assert z7["example"]["formula_en"] == "½ × ₹4,380 × 55% = ₹1,205"
    assert (z7["example"]["lost_paise"], z7["example"]["share_paise"]) == (240_900, 120_500)
    real = ask(full, "Z7", example_merchant_id=ANIL)
    assert real["baseline"]["drop_pct"] == 63 and real["example"]["amount_label"] == "₹1,380"

    z12 = ask(full, "Z12", overrides=Overrides(hourly_index_pct=(50, 47, 47)))
    assert unmet(z12, "scenario") == ["HOURS_BELOW_FLOOR"]
