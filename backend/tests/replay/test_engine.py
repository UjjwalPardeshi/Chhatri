"""ReplayEngine with fakes: minute processing, pacing, ticks, hexes, end, errors, seek (SPEC §17.1, §24.6)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import pytest

from chhatri.clock import ManualClock
from chhatri.replay.engine import DEFAULT_SPEED, TICK_SECONDS, ReplayEngine, validate_speed
from chhatri.replay.scheduler import SimScheduler
from tests.replay.helpers import GateSleep, StepClock, monsoon_at

START, END = monsoon_at(8), monsoon_at(20)
MINUTE = timedelta(minutes=1)


class Hooks:
    def __init__(self, log: list[str], fail_at: datetime | None = None) -> None:
        self.log = log
        self.fail_at = fail_at

    async def on_minute(self, at: datetime) -> None:
        self.log.append(f"minute {at:%H:%M}")
        if at == self.fail_at:
            raise RuntimeError("detection exploded")

    async def on_hour(self, at: datetime) -> None:
        self.log.append(f"hour {at:%H:%M}")


class Events:
    def __init__(self) -> None:
        self.ticks = 0
        self.quarters: list[datetime] = []

    def tick(self) -> None:
        self.ticks += 1

    def quarter_hour(self, at: datetime) -> None:
        self.quarters.append(at)


class Failures:
    def __init__(self) -> None:
        self.stopped: list[tuple[datetime, Exception]] = []

    def replay_stopped(self, at: datetime, error: Exception) -> None:
        self.stopped.append((at, error))


class Sink:
    def step_failed(self, name: str, at: datetime, error: Exception) -> None:
        raise AssertionError(f"unexpected job failure {name}: {error}")


class Rig:
    """One engine with its fakes."""

    def __init__(self, *, start: datetime = START, end: datetime = END, **kw: Any) -> None:
        self.log: list[str] = []
        self.clock = ManualClock(start)
        self.scheduler = SimScheduler(self.clock, Sink())
        self.events = Events()
        self.failures = Failures()
        self.reloads = 0
        self.fresh: Rig | None = None
        self.engine = ReplayEngine(
            clock=self.clock,
            scheduler=self.scheduler,
            hooks=Hooks(self.log, kw.pop("fail_at", None)),
            events=self.events,
            failures=self.failures,
            start=start,
            end=end,
            reload=self._reload,
            **kw,
        )

    async def _reload(self) -> ReplayEngine:
        self.reloads += 1
        self.fresh = Rig()
        return self.fresh.engine


async def wait_until(condition: Callable[[], bool], limit: int = 10_000) -> None:
    for _ in range(limit):
        if condition():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition never became true")


@pytest.mark.parametrize("bad", [0, 0.5, 121, -6, float("nan"), float("inf"), True, "6", None])
def test_speed_must_be_a_number_from_1_to_120(bad: object) -> None:
    with pytest.raises(ValueError, match="speed"):
        validate_speed(bad)


def test_speed_bounds_and_default() -> None:
    assert (validate_speed(1), validate_speed(120), validate_speed(7.5)) == (1.0, 120.0, 7.5)
    rig = Rig()
    assert rig.engine.speed == DEFAULT_SPEED == 6.0
    assert rig.engine.running is False
    with pytest.raises(ValueError, match="ends after it starts"):
        Rig(end=START)


async def test_step_processes_each_minute_jobs_then_minute_hooks_then_hour_hooks() -> None:
    rig = Rig()

    async def due() -> None:
        rig.log.append("job 09:00")

    rig.scheduler.schedule(monsoon_at(9), "payout:D-000001:credit_payout", due)
    await rig.engine.step(90)
    assert rig.clock.now() == monsoon_at(9, 30)
    minutes = [e for e in rig.log if e.startswith("minute")]
    assert len(minutes) == 90 and minutes[0] == "minute 08:01" and minutes[-1] == "minute 09:30"
    nine = rig.log.index("job 09:00")
    assert rig.log[nine : nine + 3] == ["job 09:00", "minute 09:00", "hour 09:00"]
    assert [e for e in rig.log if e.startswith("hour")] == ["hour 09:00"]
    assert [f"{q:%H:%M}" for q in rig.events.quarters] == [
        "08:15",
        "08:30",
        "08:45",
        "09:00",
        "09:15",
        "09:30",
    ]
    assert rig.events.ticks == 2  # the pause inside step, then the step itself
    assert rig.engine.running is False


@pytest.mark.parametrize("bad", [0, -1, 1.5, True, "5"])
async def test_step_rejects_non_positive_or_non_integer_minutes(bad: object) -> None:
    with pytest.raises(ValueError, match="positive whole number"):
        await Rig().engine.step(bad)  # type: ignore[arg-type]


async def test_step_cannot_pass_the_end_but_can_reach_it() -> None:
    rig = Rig(end=monsoon_at(8, 30))
    with pytest.raises(ValueError, match="beyond the end"):
        await rig.engine.step(31)
    await rig.engine.step(30)
    assert rig.clock.now() == monsoon_at(8, 30)


async def test_play_advances_speed_quarter_minutes_per_wake_with_carry() -> None:
    sleep = GateSleep(wakes=4)
    rig = Rig(sleep=sleep, monotonic=StepClock(TICK_SECONDS))
    await rig.engine.play()
    assert rig.engine.running is True
    await asyncio.wait_for(sleep.blocked.wait(), timeout=5)
    # 6 sim minutes per real second: 1.5 per 250 ms wake → 1, 2, 1, 2 whole minutes
    assert rig.clock.now() == monsoon_at(8, 6)
    assert sleep.calls == [TICK_SECONDS] * 5
    await rig.engine.pause()
    assert rig.engine.running is False
    assert rig.events.ticks == 1 + 4 + 1  # play, one per wake, pause
    await rig.engine.pause()  # pausing a paused engine only re-publishes the clock
    assert rig.events.ticks == 7


async def test_ticks_are_throttled_to_four_per_real_second() -> None:
    sleep = GateSleep(wakes=8)
    rig = Rig(sleep=sleep, monotonic=StepClock(0.1))  # wake-ups 0.1 s apart in real time
    await rig.engine.play(1)
    await asyncio.wait_for(sleep.blocked.wait(), timeout=5)
    await rig.engine.pause()
    loop_ticks = rig.events.ticks - 2
    assert loop_ticks == 3  # at 0.1 s, 0.4 s and 0.7 s: never two within 250 ms
    assert rig.clock.now() == monsoon_at(8, 2)  # 1 sim minute per real second: 8 × 0.25 = 2


async def test_play_publishes_hexes_at_most_once_per_fifteen_sim_minutes() -> None:
    sleep = GateSleep(wakes=2)
    rig = Rig(sleep=sleep, monotonic=StepClock(TICK_SECONDS))
    await rig.engine.play(120)  # 30 sim minutes per wake
    await asyncio.wait_for(sleep.blocked.wait(), timeout=5)
    await rig.engine.pause()
    assert rig.clock.now() == monsoon_at(9)
    assert [f"{q:%H:%M}" for q in rig.events.quarters] == ["08:15", "08:30", "08:45", "09:00"]
    assert rig.engine.speed == 120.0


async def test_play_pauses_itself_at_the_scenario_end() -> None:
    rig = Rig(end=monsoon_at(8, 10), sleep=GateSleep(wakes=100), monotonic=StepClock(1.0))
    await rig.engine.play(120)
    await wait_until(lambda: not rig.engine.running)
    assert rig.clock.now() == monsoon_at(8, 10)
    ticks = rig.events.ticks
    await rig.engine.play()  # at the end: nothing to run
    assert rig.engine.running is False
    assert rig.events.ticks == ticks + 1


async def test_an_error_in_the_background_clock_pauses_it_and_is_reported() -> None:
    rig = Rig(fail_at=monsoon_at(8, 3), sleep=GateSleep(wakes=100), monotonic=StepClock(1.0))
    await rig.engine.play(6)
    await wait_until(lambda: not rig.engine.running)
    assert rig.clock.now() == monsoon_at(8, 3)
    [(when, error)] = rig.failures.stopped
    assert when == monsoon_at(8, 3) and str(error) == "detection exploded"
    await rig.engine.pause()


async def test_play_with_a_bad_speed_does_not_start() -> None:
    rig = Rig()
    with pytest.raises(ValueError, match="between 1 and 120"):
        await rig.engine.play(0)
    assert rig.engine.running is False and rig.events.ticks == 0


async def test_seek_forward_steps_and_seek_to_now_only_pauses() -> None:
    rig = Rig()
    await rig.engine.seek("09:00")
    assert rig.clock.now() == monsoon_at(9)
    assert "hour 09:00" in rig.log
    before = len(rig.log)
    await rig.engine.seek("09:00")
    assert len(rig.log) == before and rig.reloads == 0


async def test_seek_backward_reloads_and_seeks_on_the_fresh_engine() -> None:
    rig = Rig()
    await rig.engine.seek("10:00")
    await rig.engine.seek("08:30")
    assert rig.reloads == 1
    assert rig.fresh is not None and rig.fresh.clock.now() == monsoon_at(8, 30)
    assert rig.clock.now() == monsoon_at(10)  # the old engine never runs backwards


@pytest.mark.parametrize("bad", ["9:00", "24:00", "07:59", "20:01", "12:60", "noon", 1700])
async def test_seek_rejects_bad_or_out_of_window_times(bad: object) -> None:
    with pytest.raises(ValueError, match="HH:MM|outside the scenario window"):
        await Rig().engine.seek(bad)  # type: ignore[arg-type]


async def test_seek_to_the_end_is_allowed() -> None:
    rig = Rig(end=monsoon_at(8, 5))
    await rig.engine.seek("08:05")
    assert rig.clock.now() == monsoon_at(8, 5)


class Ran:
    """Records which scheduled jobs ran."""

    def __init__(self) -> None:
        self.names: list[str] = []

    def job(self, name: str) -> Callable[[], Any]:
        async def run() -> None:
            self.names.append(name)

        return run


async def test_money_decided_at_the_end_still_arrives_on_its_schedule() -> None:
    """B1 offsets survive the window's end: payout steps due within the settle horizon still run."""
    rig, ran = Rig(end=monsoon_at(8, 10), settle_minutes=5), Ran()
    await rig.engine.step(10)
    rig.scheduler.schedule(monsoon_at(8, 14), "payout:D-1:credit_payout", ran.job("credit"))
    rig.scheduler.schedule(monsoon_at(8, 15), "payout:D-1:pause_instalment", ran.job("pause"))
    rig.scheduler.schedule(
        monsoon_at(8, 10) + timedelta(hours=24), "follow-up:C-1:check_case_sla", ran.job("sla")
    )
    with pytest.raises(ValueError, match="beyond the end"):
        await rig.engine.step(6)
    await rig.engine.step(4)
    assert (rig.clock.now(), ran.names) == (monsoon_at(8, 14), ["credit"])
    await rig.engine.step(1)
    assert ran.names == ["credit", "pause"]
    with pytest.raises(ValueError, match="beyond the end"):  # only the +24 h follow-up is left
        await rig.engine.step(1)


async def test_play_at_the_end_settles_pending_payout_steps_then_pauses() -> None:
    rig, ran = (
        Rig(end=monsoon_at(8, 10), settle_minutes=5, sleep=GateSleep(wakes=100), monotonic=StepClock(1.0)),
        Ran(),
    )
    await rig.engine.step(10)
    rig.scheduler.schedule(monsoon_at(8, 13), "payout:D-1:credit_payout", ran.job("credit"))
    await rig.engine.play(120)
    await wait_until(lambda: not rig.engine.running)
    assert (rig.clock.now(), ran.names) == (monsoon_at(8, 13), ["credit"])
    await rig.engine.play()  # settled: nothing left to run
    assert rig.engine.running is False


async def test_without_a_settle_horizon_the_end_is_hard() -> None:
    rig, ran = Rig(end=monsoon_at(8, 10)), Ran()
    await rig.engine.step(10)
    rig.scheduler.schedule(monsoon_at(8, 11), "payout:D-1:credit_payout", ran.job("credit"))
    with pytest.raises(ValueError, match="beyond the end"):
        await rig.engine.step(1)
    with pytest.raises(ValueError, match="settle"):
        Rig(settle_minutes=-1)
