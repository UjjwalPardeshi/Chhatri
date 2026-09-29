"""Simulated time scheduler for replay workflows (SPEC §24.6, design notes).

SimScheduler: heap of (at, seq, name, fn) tuples; processes jobs in time order.
Jobs are awaited; if a job fails it's logged and audited but does not kill the loop.
"""

from __future__ import annotations

import heapq
import itertools
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Awaitable, Callable

if TYPE_CHECKING:
    from chhatri.replay.state import Runtime

logger = logging.getLogger(__name__)


class SimScheduler:
    """Heap-based scheduler for replay jobs (SPEC §24.6; design notes).

    Jobs are scheduled at a simulated datetime with a callback (async function).
    run_due() pops and awaits all jobs with at <= now in (at, seq) order.
    A failing job is logged with context, audited as "workflow.step_failed", and
    the loop continues (SPEC design notes: failing step never kills replay).
    """

    def __init__(self) -> None:
        self._heap: list[tuple[datetime, int, str, Callable[[], Awaitable[None]]]] = []
        self._seq = itertools.count(1)
        self.runtime_getter: Callable[[], Runtime] | None = None

    def schedule(self, at: datetime, name: str, fn: Callable[[], Awaitable[None]]) -> None:
        """Schedule a job to run at simulated time `at`.

        Args:
            at: Simulated datetime when the job should run.
            name: Human-readable job name for logging.
            fn: Async function to call (takes no arguments).
        """
        seq = next(self._seq)
        heapq.heappush(self._heap, (at, seq, name, fn))

    def now(self) -> datetime:
        """Current simulated time from the ManualClock."""
        if self.runtime_getter is None:
            raise RuntimeError("SimScheduler.runtime_getter not set")
        return self.runtime_getter().clock.now()

    async def run_due(self, now: datetime) -> int:
        """Pop and await all jobs with at <= now in (at, seq) order.

        Failing jobs are logged and audited but do not stop the loop.

        Args:
            now: Current simulated time.

        Returns:
            Number of jobs executed.
        """
        count = 0
        rt = self.runtime_getter()
        while self._heap and self._heap[0][0] <= now:
            at, seq, name, fn = heapq.heappop(self._heap)
            count += 1
            try:
                await fn()
                logger.debug("Scheduler: job %s (%s) completed", name, at)
            except Exception as e:
                logger.exception("Scheduler: job %s failed at %s: %s", name, at, e)
                # Audit the failure
                try:
                    rt.audit.append(
                        at=at,
                        actor="system",
                        action="workflow.step_failed",
                        subject_type="workflow",
                        subject_id=name,
                        data={"error": str(e), "seq": seq},
                    )
                except Exception as audit_error:
                    logger.warning("Failed to audit job failure: %s", audit_error)
                # Do not re-raise; continue with next job
        return count

    def pending(self) -> int:
        """Return the number of pending jobs in the heap."""
        return len(self._heap)
