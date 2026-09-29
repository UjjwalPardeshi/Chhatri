"""Replay engine for simulated time advancement (SPEC §24.6, §17.1).

ReplayEngine: manages time, speed, and background task. Supports play/pause/step/seek.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Callable

from chhatri.clock import floor_hour

if TYPE_CHECKING:
    from chhatri.replay.orchestrator import Orchestrator
    from chhatri.replay.scheduler import SimScheduler
    from chhatri.replay.state import Runtime, StaticContext

logger = logging.getLogger(__name__)


class ReplayEngine:
    """Replay engine managing simulated time (SPEC §17.1; design notes).

    Speed: sim minutes per real second, 1..120, default 6.
    The background task advances time every 250ms real time by speed*0.25 sim minutes,
    processing minute by minute. At hour boundaries, on_hour() is called.
    Hexes published at most once per simulated 15 min; tick throttled to <= 4 per real sec.
    Seeking backward = AppState reload + step.
    """

    def __init__(
        self,
        static: StaticContext,
        runtime_getter: Callable[[], Runtime],
        clock: "ManualClock",  # noqa: F821
        scheduler: SimScheduler,
        bus: "EventBus",  # noqa: F821
    ) -> None:
        self.static = static
        self.runtime_getter = runtime_getter
        self.clock = clock
        self.scheduler = scheduler
        self.bus = bus
        self.orchestrator: Orchestrator | None = None

        self._speed = 6.0  # sim min per real sec
        self._running = False
        self._background_task: asyncio.Task[None] | None = None
        self._last_hexes_publish_at: float | None = None
        self._last_tick_time = 0.0

    async def play(self, speed: float | None = None) -> None:
        """Start playback at the given speed (1..120, default 6).

        Raises:
            ValueError: speed out of range.
            RuntimeError: already playing or orchestrator not set.
        """
        if speed is not None:
            if not (1 <= speed <= 120):
                raise ValueError(f"Speed must be 1..120, got {speed}")
            self._speed = speed

        if self._running:
            logger.debug("Engine already playing at speed %.1f", self._speed)
            return

        if self.orchestrator is None:
            raise RuntimeError("Orchestrator not set")

        self._running = True
        self._background_task = asyncio.create_task(self._background_loop())
        logger.info("Engine playing at speed %.1f sim min/real sec", self._speed)

    async def pause(self) -> None:
        """Pause playback."""
        self._running = False
        if self._background_task is not None:
            await self._background_task
            self._background_task = None
        logger.info("Engine paused at %s", self.clock.now())

    async def step(self, minutes: int) -> None:
        """Advance time synchronously by `minutes` (awaits all effects).

        Used for deterministic testing and single-step debugging.
        """
        if self._running:
            raise RuntimeError("Cannot step while playing; pause first")

        if self.orchestrator is None:
            raise RuntimeError("Orchestrator not set")

        rt = self.runtime_getter()
        start = self.clock.now()
        end = start + __import__("datetime").timedelta(minutes=minutes)

        logger.debug("Stepping %d minutes from %s to %s", minutes, start, end)

        current = start
        while current < end:
            # Advance clock by 1 minute
            current = self.clock.advance(__import__("datetime").timedelta(minutes=1))

            # Run due jobs
            await self.scheduler.run_due(current)

            # On-minute hook
            await self.orchestrator.on_minute(current)

            # On-hour hook at hour boundaries
            if current.minute == 0:
                await self.orchestrator.on_hour(current)

    async def seek(self, hhmm: str) -> None:
        """Seek to time HH:MM within the scenario (SPEC §17.1).

        Forward: step deterministically.
        Backward: AppState reload + step (inject reload callback).
        """
        if self._running:
            raise RuntimeError("Cannot seek while playing; pause first")

        rt = self.runtime_getter()
        scenario = rt.scenario

        # Parse HH:MM
        try:
            hh, mm = map(int, hhmm.split(":"))
        except ValueError:
            raise ValueError(f"Invalid time format {hhmm!r}, expected HH:MM")

        import datetime
        from zoneinfo import ZoneInfo

        IST = ZoneInfo("Asia/Kolkata")
        target = datetime.datetime.combine(
            scenario.start.date(),
            datetime.time(hh, mm),
            tzinfo=IST,
        )

        if target < scenario.start:
            raise ValueError(
                f"Cannot seek before scenario start {scenario.start.time()}; "
                f"seeking backward is not yet implemented"
            )

        if target > scenario.end:
            raise ValueError(f"Cannot seek past scenario end {scenario.end.time()}")

        current = self.clock.now()
        if target == current:
            logger.debug("Already at %s", hhmm)
            return

        if target > current:
            # Forward seek: just step
            delta = (target - current).total_seconds() / 60
            await self.step(int(delta))
        else:
            # Backward seek not implemented (would need full reload)
            raise NotImplementedError("Backward seek not yet implemented")

    @property
    def running(self) -> bool:
        """True if playback is active."""
        return self._running

    @property
    def speed(self) -> float:
        """Current playback speed (sim min per real sec)."""
        return self._speed

    async def _background_loop(self) -> None:
        """Background task: advances time every 250ms and processes events."""
        import datetime

        rt = self.runtime_getter()
        real_start = time.time()
        last_hour_check = self.clock.now()

        try:
            while self._running:
                # Sleep 250ms real time
                await asyncio.sleep(0.25)

                if not self._running:
                    break

                # Advance sim time by speed * 0.25 minutes
                sim_advance_minutes = self._speed * 0.25
                sim_advance_seconds = int(sim_advance_minutes * 60)
                new_time = self.clock.advance(datetime.timedelta(seconds=sim_advance_seconds))

                # Process minute by minute from last update to now
                current = last_hour_check
                while current < new_time:
                    current += datetime.timedelta(minutes=1)
                    self.clock.set(current)

                    # Run due scheduler jobs
                    await self.scheduler.run_due(current)

                    # On-minute hook
                    await self.orchestrator.on_minute(current)

                    # On-hour hook at hour boundaries
                    if current.minute == 0 and current > last_hour_check:
                        await self.orchestrator.on_hour(current)
                        last_hour_check = current

                # Publish tick (throttled to <= 4 per real second)
                now_real = time.time()
                if now_real - self._last_tick_time >= 0.25:
                    self.bus.publish(
                        "tick",
                        self.clock.now(),
                        {"clock": {}},  # Filled by views
                    )
                    self._last_tick_time = now_real

                # Check for scenario end
                if self.clock.now() >= rt.scenario.end:
                    logger.info("Scenario reached end; pausing")
                    self._running = False
                    break

        except asyncio.CancelledError:
            logger.debug("Background loop cancelled")
            raise
        except Exception as e:
            logger.exception("Background loop error: %s", e)
            self._running = False
            raise
        finally:
            logger.debug("Background loop exiting")
