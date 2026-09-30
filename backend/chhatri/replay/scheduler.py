"""Simulated-time scheduler for workflow steps (SPEC §15, §24.5 ``Scheduler``, §24.6; decision B1).

A heap of ``(at, seq, name, fn)``: `run_due(now)` pops every job with ``at <= now`` in ``(at, seq)``
order and awaits it — including jobs that the running jobs schedule for ``<= now``, so a step at
offset 0 runs in the same simulated minute. A failing job never stops the replay: it is logged with
its name and due time, handed to the `FailureSink` (`FailureRecorder` audits
``workflow.step_failed`` and adds a feed item) and the next job runs. Cancellation
(``asyncio.CancelledError``) is not caught.

`was_scheduled(name)` remembers every job name ever scheduled; job names are
``{run_id}:{step}`` for workflow steps (the in-process engine's convention), which makes n8n
callbacks idempotent per ``(run_id, step)`` in both workflow modes.
"""

from __future__ import annotations

import asyncio
import heapq
import itertools
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, Protocol

from chhatri.clock import Clock, require_aware
from chhatri.replay.feed import FeedLog
from chhatri.store.protocols import AuditSink

__all__ = ["FailureRecorder", "FailureSink", "Job", "SimScheduler"]

logger = logging.getLogger(__name__)

Job = Callable[[], Awaitable[None]]
MAX_ERROR_CHARS: Final = 200
SYSTEM_ACTOR: Final = "system"


class FailureSink(Protocol):
    """Told about every failed job (after it was logged)."""

    def step_failed(self, name: str, at: datetime, error: Exception) -> None: ...


@dataclass(frozen=True, slots=True, order=True)
class _Entry:
    at: datetime
    seq: int
    name: str = field(compare=False)
    fn: Job = field(compare=False)


class SimScheduler:
    """Implements `chhatri.workflows.definitions.Scheduler` on the replay's ManualClock."""

    def __init__(self, clock: Clock, failures: FailureSink) -> None:
        self._clock = clock
        self._failures = failures
        self._heap: list[_Entry] = []
        self._seq = itertools.count(1)
        self._names: set[str] = set()

    def schedule(self, at: datetime, name: str, fn: Callable[[], Awaitable[None]]) -> None:
        """Run `fn` once simulated time reaches `at` (ValueError for a naive time or empty name)."""
        when = require_aware(at)
        if not name.strip():
            raise ValueError("a scheduled job needs a name")
        if not callable(fn):
            raise TypeError(f"job {name} is not callable")
        heapq.heappush(self._heap, _Entry(when, next(self._seq), name, fn))
        self._names.add(name)

    def now(self) -> datetime:
        return self._clock.now()

    def was_scheduled(self, name: str) -> bool:
        """True when a job with this name was ever scheduled on this scheduler."""
        return name in self._names

    def pending(self) -> int:
        return len(self._heap)

    async def run_due(self, now: datetime) -> int:
        """Run every job due at or before `now` in (at, seq) order; returns how many ran."""
        limit = require_aware(now)
        ran = 0
        while self._heap and self._heap[0].at <= limit:
            entry = heapq.heappop(self._heap)
            ran += 1
            try:
                await entry.fn()
            except Exception as exc:  # isolation is the contract (SPEC §24.6)
                logger.exception("scheduled job %s (due %s) failed", entry.name, entry.at.isoformat())
                self._failures.step_failed(entry.name, entry.at, exc)
            await asyncio.sleep(0)  # let SSE subscribers drain between jobs of a burst
        return ran


class FailureRecorder:
    """Makes failures visible: an audit entry and an ``error`` feed item (never only a log line).

    `step_failed` (the scheduler's `FailureSink`): ``workflow.step_failed``, the replay continues.
    `replay_stopped` (the engine's background clock): ``replay.stopped``, the clock is paused.
    """

    def __init__(self, audit: AuditSink, feed: FeedLog) -> None:
        self._audit = audit
        self._feed = feed

    def step_failed(self, name: str, at: datetime, error: Exception) -> None:
        kind = type(error).__name__
        self._audit.append(
            at=at,
            actor=SYSTEM_ACTOR,
            action="workflow.step_failed",
            subject_type="workflow_step",
            subject_id=name,
            data={"error_type": kind, "error": _short(error), "due_at": at.isoformat()},
        )
        self._feed.add(at, "error", f"Workflow step {name} failed ({kind}); the replay continues")

    def replay_stopped(self, at: datetime, error: Exception) -> None:
        kind = type(error).__name__
        self._audit.append(
            at=at,
            actor=SYSTEM_ACTOR,
            action="replay.stopped",
            subject_type="replay",
            subject_id=at.isoformat(),
            data={"error_type": kind, "error": _short(error)},
        )
        self._feed.add(at, "error", f"The replay clock stopped after an error ({kind}); press play to go on")


def _short(error: Exception) -> str:
    return str(error)[:MAX_ERROR_CHARS]
