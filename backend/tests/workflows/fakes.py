"""Scheduler / StepHandlers doubles for workflow tests (simulated time, no real waiting)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from typing import Any


class FakeScheduler:
    """Records scheduled jobs; `run_all` runs them in (at, insertion) order like SimScheduler."""

    def __init__(self, now: datetime) -> None:
        self._now = now
        self.jobs: list[tuple[datetime, str, Callable[[], Awaitable[None]]]] = []

    def now(self) -> datetime:
        return self._now

    def schedule(self, at: datetime, name: str, fn: Callable[[], Awaitable[None]]) -> None:
        self.jobs.append((at, name, fn))

    def was_scheduled(self, name: str) -> bool:
        return any(job_name == name for _, job_name, _ in self.jobs)

    async def run_all(self) -> None:
        for _, _, fn in sorted(self.jobs, key=lambda job: job[0]):
            await fn()


class RecordingHandlers:
    def __init__(self, *, fail_on: str | None = None) -> None:
        self.calls: list[tuple[str, str, Mapping[str, Any]]] = []
        self.fail_on = fail_on

    async def run_step(self, workflow: str, step: str, payload: Mapping[str, Any]) -> None:
        self.calls.append((workflow, step, payload))
        if step == self.fail_on:
            raise RuntimeError(f"{step} failed")
