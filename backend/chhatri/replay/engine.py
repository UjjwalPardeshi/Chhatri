"""The replay clock: play, pause, step and seek on simulated time (SPEC §17.1, §24.6).

- Time advances in 1-minute simulated steps. For every minute ``t``: the clock is set to ``t``, the
  workflow steps due by ``t`` run (in ``(at, seq)`` order), the minute hooks run
  (`Orchestrator.on_minute`), at hour boundaries the hour hooks run (detection → claims,
  `Orchestrator.on_hour`), and every 15 simulated minutes the hex values are published — so hexes
  go out at most once per 15 simulated minutes whatever the speed.
- ``play``: a background task wakes every 250 ms of real time and advances ``speed × 0.25``
  simulated minutes (``speed`` = simulated minutes per real second, 1..120, default 6; fractions
  carry over). ``tick`` events follow the wake-ups, at most 4 per real second. The engine pauses
  itself at the scenario's end. An unexpected error in the background clock is logged, reported
  to the `ReplayFailureSink` (audit ``replay.stopped`` and a feed item) and pauses the clock; the
  minute that failed may be partly applied (workflow-step failures never get here: the scheduler
  isolates them).
- ``pause`` waits for the minute being processed to finish, so no half-processed minute remains.
- ``step(minutes)``: pauses, then advances synchronously awaiting every effect; ValueError for a
  non-positive or non-integer count or past the scenario's end.
- Settling (B1, B2; SPEC §17.1 is silent on money decided in the window's last minutes): money
  decided inside the window still arrives on its B1 schedule. At or after the scenario's end the
  clock may keep advancing — by ``play`` or ``step`` — up to the latest pending workflow step that
  is due within ``settle_minutes`` (the payout workflow's last offset, 5) of the later of now and
  the end; then it pauses as usual. Only those steps extend the window: the follow-up SLA check a
  day later never does, and ``seek`` stays inside the scenario window.
- ``seek("HH:MM")`` on the scenario day: forward = step; backward = reload the scenario (fresh ids,
  store, audit; SPEC §3) and seek on the new engine; ValueError for a bad time or one outside the
  scenario window. `sleep` and `monotonic` are injectable so tests control pacing.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import re
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Final, Protocol

from chhatri.clock import IST, ManualClock, at
from chhatri.replay.scheduler import SimScheduler

__all__ = [
    "DEFAULT_SPEED",
    "MAX_SPEED",
    "MIN_SPEED",
    "TICK_SECONDS",
    "EngineEvents",
    "ReplayEngine",
    "ReplayFailureSink",
    "ReplayHooks",
    "validate_speed",
]

logger = logging.getLogger(__name__)

MIN_SPEED: Final = 1.0
MAX_SPEED: Final = 120.0
DEFAULT_SPEED: Final = 6.0
TICK_SECONDS: Final = 0.25
MINUTE: Final = timedelta(minutes=1)
HEX_EVERY_MINUTES: Final = 15
SEEK_PATTERN: Final = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class ReplayHooks(Protocol):
    async def on_minute(self, at: datetime) -> None: ...

    async def on_hour(self, at: datetime) -> None: ...


class EngineEvents(Protocol):
    def tick(self) -> None: ...

    def quarter_hour(self, at: datetime) -> None: ...


class ReplayFailureSink(Protocol):
    def replay_stopped(self, at: datetime, error: Exception) -> None: ...


def validate_speed(speed: object) -> float:
    """A finite number in [1, 120] (booleans are not numbers here); ValueError otherwise."""
    if isinstance(speed, bool) or not isinstance(speed, int | float) or not math.isfinite(speed):
        raise ValueError("speed must be a number of simulated minutes per real second")
    if not MIN_SPEED <= speed <= MAX_SPEED:
        raise ValueError(f"speed must be between {MIN_SPEED:g} and {MAX_SPEED:g}")
    return float(speed)


class ReplayEngine:
    """SPEC §24.6 replay engine of one loaded scenario."""

    def __init__(
        self,
        *,
        clock: ManualClock,
        scheduler: SimScheduler,
        hooks: ReplayHooks,
        events: EngineEvents,
        failures: ReplayFailureSink,
        start: datetime,
        end: datetime,
        reload: Callable[[], Awaitable[ReplayEngine]],
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        speed: float = DEFAULT_SPEED,
        settle_minutes: int = 0,
    ) -> None:
        if end <= start:
            raise ValueError("a scenario ends after it starts")
        if settle_minutes < 0:
            raise ValueError("settle_minutes must not be negative")
        self._clock = clock
        self._scheduler = scheduler
        self._hooks = hooks
        self._events = events
        self._failures = failures
        self._start = start
        self._end = end
        self._settle = settle_minutes * MINUTE
        self._reload = reload
        self._sleep = sleep
        self._monotonic = monotonic
        self._speed = validate_speed(speed)
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._carry = 0.0
        self._last_tick: float | None = None

    @property
    def running(self) -> bool:
        return self._running

    def _limit(self) -> datetime:
        """The scenario's end, extended to the last payout step still settling (see module docstring)."""
        horizon = max(self._clock.now(), self._end) + self._settle
        due = self._scheduler.latest_due(horizon) if self._settle else None
        return self._end if due is None else max(self._end, due)

    @property
    def speed(self) -> float:
        return self._speed

    async def play(self, speed: float | None = None) -> None:
        """Run the clock at `speed` (or the current speed); a no-op at the scenario's end."""
        if speed is not None:
            self._speed = validate_speed(speed)
        if self._clock.now() >= self._limit():
            logger.info("replay is at its end; play ignored")
        elif not self._running:
            self._running = True
            self._carry = 0.0
            self._task = asyncio.create_task(self._loop(), name="chhatri-replay")
        self._events.tick()

    async def pause(self) -> None:
        """Stop the clock after the minute being processed."""
        self._running = False
        async with self._lock:
            task, self._task = self._task, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._events.tick()

    async def step(self, minutes: int) -> None:
        """Advance `minutes` simulated minutes now, awaiting every effect."""
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 1:
            raise ValueError("minutes must be a positive whole number")
        if self._clock.now() + minutes * MINUTE > self._limit():
            raise ValueError("cannot step beyond the end of the scenario")
        await self.pause()
        async with self._lock:
            for _ in range(minutes):
                await self._minute(self._clock.now() + MINUTE)
        self._events.tick()

    async def seek(self, hhmm: str) -> None:
        """Jump to HH:MM of the scenario day (forward: step; backward: reload then step)."""
        target = self._parse(hhmm)
        now = self._clock.now()
        if target > now:
            await self.step(int((target - now) / MINUTE))
        elif target < now:
            await self.pause()
            fresh = await self._reload()
            await fresh.seek(hhmm)
        else:
            await self.pause()

    def _parse(self, hhmm: str) -> datetime:
        match = SEEK_PATTERN.fullmatch(hhmm) if isinstance(hhmm, str) else None
        if match is None:
            raise ValueError("seek takes a time as HH:MM")
        target = at(self._start.astimezone(IST).date(), int(match[1]), int(match[2]))
        if not self._start <= target <= self._end:
            raise ValueError(f"{hhmm} is outside the scenario window")
        return target

    async def _minute(self, t: datetime) -> None:
        self._clock.set(t)
        await self._scheduler.run_due(t)
        await self._hooks.on_minute(t)
        if t.minute == 0:
            await self._hooks.on_hour(t)
        if t.minute % HEX_EVERY_MINUTES == 0:
            self._events.quarter_hour(t)

    async def _loop(self) -> None:
        """Background clock: wake every TICK_SECONDS, advance speed × TICK_SECONDS minutes."""
        while self._running:
            await self._sleep(TICK_SECONDS)
            self._carry += self._speed * TICK_SECONDS
            whole = int(self._carry)
            self._carry -= whole
            if not await self._advance_guarded(whole):
                return
            self._maybe_tick()
            if self._clock.now() >= self._limit() and self._running:
                logger.info("replay reached its end at %s; paused", self._clock.now().isoformat())
                self._running = False
                self._events.tick()

    async def _advance_guarded(self, minutes: int) -> bool:
        """Process up to `minutes` minutes; False (clock paused, failure reported) on an error."""
        try:
            async with self._lock:
                for _ in range(minutes):
                    if not self._running or self._clock.now() >= self._limit():
                        break
                    await self._minute(self._clock.now() + MINUTE)
        except Exception as exc:  # the background clock must surface, not die silently (SPEC §24.6)
            now = self._clock.now()
            logger.exception("replay stopped at %s after an error", now.isoformat())
            self._running = False
            self._failures.replay_stopped(now, exc)
            self._events.tick()
            return False
        return True

    def _maybe_tick(self) -> None:
        """At most one tick per TICK_SECONDS of real time (≤ 4 per second)."""
        now = self._monotonic()
        if self._last_tick is None or now - self._last_tick >= TICK_SECONDS:
            self._last_tick = now
            self._events.tick()
