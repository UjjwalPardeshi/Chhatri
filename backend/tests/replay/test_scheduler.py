"""Tests for SimScheduler (SPEC §24.6)."""

import asyncio
from datetime import datetime, timedelta

import pytest

from chhatri.clock import ist
from chhatri.replay.scheduler import SimScheduler


class MockRuntime:
    """Mock runtime for testing scheduler."""

    def __init__(self, start_time: datetime):
        self.clock_time = start_time


@pytest.fixture
def scheduler():
    """Create a scheduler with mock runtime."""
    s = SimScheduler()

    # Create a mock runtime with a clock
    class MockClock:
        def __init__(self):
            self.time = ist(2025, 8, 19, 8, 0)

        def now(self):
            return self.time

    class MockRuntime:
        def __init__(self):
            self.clock = MockClock()

    s.runtime_getter = lambda: MockRuntime()
    return s


@pytest.mark.asyncio
async def test_schedule_and_run_due(scheduler: SimScheduler):
    """Test scheduling and running jobs."""
    executed = []

    async def job():
        executed.append("done")

    at = ist(2025, 8, 19, 8, 5)
    scheduler.schedule(at, "test_job", job)

    # Before the scheduled time, nothing runs
    count = await scheduler.run_due(ist(2025, 8, 19, 8, 4))
    assert count == 0
    assert len(executed) == 0

    # At or after the scheduled time, job runs
    count = await scheduler.run_due(ist(2025, 8, 19, 8, 5))
    assert count == 1
    assert executed == ["done"]


@pytest.mark.asyncio
async def test_job_order(scheduler: SimScheduler):
    """Test jobs run in time order, then seq order."""
    executed = []

    async def job(name):
        executed.append(name)

    # Schedule multiple jobs
    scheduler.schedule(ist(2025, 8, 19, 8, 5), "first", lambda: job("first"))
    scheduler.schedule(ist(2025, 8, 19, 8, 3), "early", lambda: job("early"))
    scheduler.schedule(ist(2025, 8, 19, 8, 5), "second", lambda: job("second"))

    await scheduler.run_due(ist(2025, 8, 19, 8, 6))

    # Should run early first, then first and second in seq order
    assert executed == ["early", "first", "second"]


@pytest.mark.asyncio
async def test_failing_job_does_not_stop_loop(scheduler: SimScheduler):
    """Test that a failing job does not stop subsequent jobs."""
    executed = []

    async def failing_job():
        raise ValueError("test error")

    async def good_job():
        executed.append("ok")

    scheduler.schedule(ist(2025, 8, 19, 8, 5), "fail", failing_job)
    scheduler.schedule(ist(2025, 8, 19, 8, 5), "ok", good_job)

    # Mock audit so it doesn't actually try to audit
    class MockAudit:
        def append(self, **kwargs):
            pass

    class MockClock:
        def now(self):
            return ist(2025, 8, 19, 8, 0)

    class MockRuntime:
        def __init__(self):
            self.clock = MockClock()
            self.audit = MockAudit()

    scheduler.runtime_getter = lambda: MockRuntime()

    count = await scheduler.run_due(ist(2025, 8, 19, 8, 6))

    # Both jobs attempted
    assert count == 2
    # Good job should have run despite the failure
    assert executed == ["ok"]


@pytest.mark.asyncio
async def test_pending(scheduler: SimScheduler):
    """Test pending job count."""
    async def job():
        pass

    assert scheduler.pending() == 0

    scheduler.schedule(ist(2025, 8, 19, 8, 5), "job1", job)
    assert scheduler.pending() == 1

    scheduler.schedule(ist(2025, 8, 19, 8, 6), "job2", job)
    assert scheduler.pending() == 2

    await scheduler.run_due(ist(2025, 8, 19, 8, 7))
    assert scheduler.pending() == 0
