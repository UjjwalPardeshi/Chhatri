"""Area trigger and zone status (SPEC §8.2, §17.2 demo story, §24.2)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from chhatri.clock import at, ist
from chhatri.detect.area_index import zone_window
from chhatri.detect.triggers import evaluate_hour
from chhatri.domain.enums import AlertKind
from chhatri.domain.models import Alert
from chhatri.policy.rules import PolicyRules
from chhatri.sim.types import City
from tests.detect.conftest import DAY, flat_sales, scripted
from tests.forecast.synthetic import make_alert, make_city

LOWER = {"Z3": 70, "Z7": 70, "Z9": 70, "Z12": 70}
RED = make_alert(["Z3", "Z7", "Z12"], at(DAY, 14), at(DAY, 20), issued_at=ist(2025, 8, 18, 17, 30))
STORM = {14: 0.40, 15: 0.40, 16: 0.40}


def run(
    city: City,
    rules: PolicyRules,
    hour: int,
    windows: dict,
    alerts: tuple[Alert, ...] = (RED,),
    *,
    lower: dict | None = None,
    done: frozenset[tuple[str, date]] = frozenset(),
):  # noqa: ANN202
    panel, expected = flat_sales(city, scripted(windows))
    return evaluate_hour(at(DAY, hour), city, panel, expected, alerts, lower or LOWER, rules, done)


class TestDemoStory:
    """The monsoon replay (SPEC §17.2): Z3 38 %, Z7 37 %, Z12 47 % trigger at 17:00; Z9 61 % is a slow day."""

    windows = {
        "Z3": {14: 0.38, 15: 0.38, 16: 0.38},
        "Z7": {14: 0.36, 15: 0.37, 16: 0.38},
        "Z12": {14: 0.47, 15: 0.47, 16: 0.47},
        "Z9": {14: 0.61, 15: 0.61, 16: 0.61},
    }

    def test_seventeen_hundred(self, city: City, rules: PolicyRules) -> None:
        triggers, states = run(city, rules, 17, self.windows)
        assert [t.zone_id for t in triggers] == ["Z3", "Z7", "Z12"]
        z7 = triggers[1]
        assert z7.id == "E-Z7-20250819" and z7.alert_id == RED.id
        assert (z7.index_pct, z7.drop_pct, z7.hourly_index_pct) == (37, 63, (36, 37, 38))
        assert (z7.window_start, z7.window_end, z7.fired_at) == (at(DAY, 14), at(DAY, 17), at(DAY, 17))
        assert (z7.shops_in_index, z7.lower_bound_pct) == (25, 70)
        assert triggers[0].shops_in_index == 29 and triggers[0].index_pct == 38
        assert triggers[2].index_pct == 47
        assert {z: s.status for z, s in states.items()} == {
            "Z3": "triggered",
            "Z7": "triggered",
            "Z9": "slow_day",
            "Z12": "triggered",
        }
        assert states["Z9"].index_pct == 61 and states["Z9"].alert_id is None
        assert states["Z7"].hourly_pct == (36, 37, 38) and states["Z7"].hours_below == 3

    @pytest.mark.parametrize(
        ("hour", "status", "below"), [(14, "normal", 0), (15, "watch", 1), (16, "watch", 2)]
    )
    def test_build_up(self, city: City, rules: PolicyRules, hour: int, status: str, below: int) -> None:
        triggers, states = run(city, rules, hour, self.windows)
        assert triggers == ()
        assert states["Z7"].status == status and states["Z7"].hours_below == below
        assert states["Z7"].alert_id == (RED.id if hour > 14 else None)

    def test_later_hours_stay_triggered_without_refiring(self, city: City, rules: PolicyRules) -> None:
        done = frozenset({("Z3", DAY), ("Z7", DAY), ("Z12", DAY)})
        triggers, states = run(city, rules, 18, {"Z7": {15: 0.3, 16: 0.3, 17: 0.3}}, done=done)
        assert triggers == ()
        assert states["Z7"].status == "triggered" and states["Z9"].status == "normal"


class TestConditions:
    @pytest.mark.parametrize(("pct", "fires"), [(0.49, True), (0.50, False)])
    def test_floor_is_strict(self, city: City, rules: PolicyRules, pct: float, fires: bool) -> None:
        triggers, states = run(
            city, rules, 17, {"Z7": {14: pct, 15: 0.40, 16: 0.40}}, lower={**LOWER, "Z7": 60}
        )
        assert bool(triggers) is fires
        assert states["Z7"].status == ("triggered" if fires else "watch")
        assert states["Z7"].hours_below == (3 if fires else 2)

    @pytest.mark.parametrize(("bound", "fires"), [(45, False), (46, True)])
    def test_lower_bound_is_strict(self, city: City, rules: PolicyRules, bound: int, fires: bool) -> None:
        triggers, _ = run(
            city, rules, 17, {"Z7": {14: 0.45, 15: 0.45, 16: 0.45}}, lower={**LOWER, "Z7": bound}
        )
        assert bool(triggers) is fires

    def test_alert_must_cover_whole_window(self, city: City, rules: PolicyRules) -> None:
        late = make_alert(["Z7"], at(DAY, 15), at(DAY, 20))
        triggers, states = run(city, rules, 17, {"Z7": STORM}, (late,))
        assert triggers == () and states["Z7"].status == "watch" and states["Z7"].alert_id == late.id

    def test_alert_issued_after_now_is_ignored(self, city: City, rules: PolicyRules) -> None:
        future = make_alert(["Z7"], at(DAY, 12), at(DAY, 20), issued_at=at(DAY, 18))
        triggers, states = run(city, rules, 17, {"Z7": STORM}, (future,))
        assert triggers == () and states["Z7"].status == "slow_day"

    def test_heatwave_does_not_count_but_civic_does(self, city: City, rules: PolicyRules) -> None:
        heat = make_alert(["Z7"], at(DAY, 0), at(DAY, 23), kind=AlertKind.HEATWAVE)
        assert run(city, rules, 17, {"Z7": STORM}, (heat,))[0] == ()
        civic = make_alert(["Z7"], at(DAY, 0), at(DAY, 23), kind=AlertKind.CIVIC, alert_id="A-20250818-02")
        assert run(city, rules, 17, {"Z7": STORM}, (civic,))[0][0].alert_id == civic.id

    def test_earliest_issued_alert_is_used(self, city: City, rules: PolicyRules) -> None:
        second = make_alert(
            ["Z7"], at(DAY, 10), at(DAY, 21), issued_at=ist(2025, 8, 19, 9), alert_id="A-20250819-01"
        )
        triggers, _ = run(city, rules, 17, {"Z7": STORM}, (second, RED))
        assert triggers[0].alert_id == RED.id

    def test_already_triggered_that_day(self, city: City, rules: PolicyRules) -> None:
        other_day = frozenset({("Z7", DAY - timedelta(days=1))})
        assert len(run(city, rules, 17, {"Z7": STORM}, done=other_day)[0]) == 1
        triggers, states = run(city, rules, 17, {"Z7": STORM}, done=frozenset({("Z7", DAY)}))
        assert triggers == () and states["Z7"].status == "triggered"

    def test_quorum(self, rules: PolicyRules) -> None:
        # 21 shops, S-0021 uncovered → 20 covered; weekly offs: S-0007 (0 = Mon) and S-0014 (0 = Mon) are open Tue
        city = make_city((("Z7", 21),), uncovered=frozenset({"S-0021"}), weekly_off_every=7)
        triggers, states = run(city, rules, 17, {"Z7": STORM}, lower={"Z7": 70})
        assert states["Z7"].shops_in_index == 20 and len(triggers) == 1
        smaller = make_city((("Z7", 21),), uncovered=frozenset({"S-0021", "S-0020"}))
        triggers, states = run(smaller, rules, 17, {"Z7": STORM}, lower={"Z7": 70})
        assert triggers == () and states["Z7"].status == "no_data" and states["Z7"].shops_in_index == 19

    def test_weekly_off_shops_leave_the_index(self, rules: PolicyRules) -> None:
        city = make_city((("Z7", 28),), weekly_off_every=4)  # S-0004 (off 4), S-0008 (1 = Tue), ...
        off_tuesday = sum(1 for m in city.merchants if m.weekly_off == DAY.weekday())
        _, states = run(city, rules, 17, {}, lower={"Z7": 70})
        assert off_tuesday > 0 and states["Z7"].shops_in_index == 28 - off_tuesday


class TestStatus:
    @pytest.mark.parametrize(
        ("windows", "status", "below"),
        [
            ({}, "normal", 0),
            ({"Z9": {14: 0.61, 15: 0.61, 16: 0.61}}, "slow_day", 0),
            ({"Z9": {14: 0.80, 15: 0.80, 16: 0.45}}, "slow_day", 1),
            ({"Z9": {14: 0.40, 15: 0.60, 16: 0.40}}, "slow_day", 1),
        ],
    )
    def test_no_alert(self, city: City, rules: PolicyRules, windows: dict, status: str, below: int) -> None:
        _, states = run(city, rules, 17, windows)
        assert states["Z9"].status == status and states["Z9"].hours_below == below

    def test_alert_without_drop_is_normal(self, city: City, rules: PolicyRules) -> None:
        _, states = run(city, rules, 17, {"Z7": {14: 0.65, 15: 0.65, 16: 0.65}})
        assert states["Z7"].status == "normal"

    def test_night_is_no_data(self, city: City, rules: PolicyRules) -> None:
        triggers, states = run(city, rules, 3, {})
        assert triggers == ()
        assert all(
            s.status == "no_data" and s.index_pct is None and s.hourly_pct == (None, None, None)
            for s in states.values()
        )

    def test_states_cover_every_zone_and_are_read_only(self, city: City, rules: PolicyRules) -> None:
        _, states = run(city, rules, 12, {})
        assert list(states) == ["Z3", "Z7", "Z9", "Z12"]
        with pytest.raises(TypeError):
            states["Z3"] = states["Z7"]  # type: ignore[index]

    def test_matches_zone_window(self, city: City, rules: PolicyRules) -> None:
        panel, expected = flat_sales(city, scripted({"Z3": {9: 0.9, 10: 0.7, 11: 0.8}}))
        _, states = evaluate_hour(at(DAY, 12), city, panel, expected, (), LOWER, rules, frozenset())
        window = zone_window(city, panel, expected, "Z3", at(DAY, 9), at(DAY, 12), 70)
        assert (states["Z3"].index_pct, states["Z3"].shops_in_index) == (
            window.index_pct,
            window.shops_in_index,
        )
        assert states["Z3"].hourly_pct == (90, 70, 80)
        assert window.actual_paise * 100 // window.expected_paise == 79  # fewer shops open at 09:00


class TestInputs:
    @pytest.mark.parametrize(
        "when", [ist(2025, 8, 19, 17, 30), ist(2025, 8, 19, 17, 0, 1), datetime(2025, 8, 19, 17)]
    )
    def test_hour_boundary_required(self, city: City, rules: PolicyRules, when: datetime) -> None:
        panel, expected = flat_sales(city, scripted({}))
        with pytest.raises(ValueError):
            evaluate_hour(when, city, panel, expected, (), LOWER, rules, frozenset())

    def test_missing_lower_bound(self, city: City, rules: PolicyRules) -> None:
        with pytest.raises(ValueError, match="Z9"):
            run(city, rules, 17, {}, lower={"Z3": 70, "Z7": 70, "Z12": 70})

    def test_window_outside_panel(self, city: City, rules: PolicyRules) -> None:
        panel, expected = flat_sales(city, scripted({}))
        visible = panel.window(panel.start, at(DAY, 16))
        with pytest.raises(IndexError):
            evaluate_hour(at(DAY, 17), city, visible, expected, (), LOWER, rules, frozenset())
        with pytest.raises(IndexError):
            evaluate_hour(
                panel.start + timedelta(hours=2), city, panel, expected, (), LOWER, rules, frozenset()
            )

    def test_expected_shape(self, city: City, rules: PolicyRules) -> None:
        panel, expected = flat_sales(city, scripted({}))
        with pytest.raises(ValueError, match="expected_p50"):
            evaluate_hour(at(DAY, 17), city, panel, expected[:, :10], (), LOWER, rules, frozenset())
