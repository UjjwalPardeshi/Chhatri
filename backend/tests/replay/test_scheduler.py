"""SimScheduler: (at, seq) order, same-minute chaining, failure isolation (SPEC §24.6, B1)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from chhatri.audit.log import AuditLog
from chhatri.clock import ManualClock
from chhatri.replay.feed import FeedLog
from chhatri.replay.scheduler import FailureRecorder, SimScheduler
from tests.replay.helpers import monsoon_at

T0 = monsoon_at(17)
MINUTE = timedelta(minutes=1)


class Sink:
    def __init__(self) -> None:
        self.failures: list[tuple[str, datetime, str]] = []

    def step_failed(self, name: str, at: datetime, error: Exception) -> None:
        self.failures.append((name, at, str(error)))


def make() -> tuple[SimScheduler, Sink, list[str]]:
    sink = Sink()
    return SimScheduler(ManualClock(T0), sink), sink, []


def job(log: list[str], name: str):
    async def run() -> None:
        log.append(name)

    return run


async def test_jobs_run_in_at_then_seq_order_and_only_when_due() -> None:
    scheduler, _, log = make()
    scheduler.schedule(T0 + 4 * MINUTE, "credit-1", job(log, "credit-1"))
    scheduler.schedule(T0, "execute-1", job(log, "execute-1"))
    scheduler.schedule(T0 + 4 * MINUTE, "notify-1", job(log, "notify-1"))
    scheduler.schedule(T0 + 5 * MINUTE, "pause-1", job(log, "pause-1"))
    scheduler.schedule(T0 + 4 * MINUTE, "credit-2", job(log, "credit-2"))
    assert scheduler.pending() == 5

    assert await scheduler.run_due(T0 + 3 * MINUTE) == 1
    assert log == ["execute-1"]
    assert await scheduler.run_due(T0 + 4 * MINUTE) == 3
    assert log == ["execute-1", "credit-1", "notify-1", "credit-2"]
    assert await scheduler.run_due(T0 + 10 * MINUTE) == 1
    assert log[-1] == "pause-1"
    assert scheduler.pending() == 0
    assert await scheduler.run_due(T0 + 11 * MINUTE) == 0


async def test_a_job_scheduled_for_now_by_a_running_job_runs_in_the_same_call() -> None:
    scheduler, _, log = make()

    async def parent() -> None:
        log.append("parent")
        scheduler.schedule(T0, "child", job(log, "child"))

    scheduler.schedule(T0, "parent", parent)
    assert await scheduler.run_due(T0) == 2
    assert log == ["parent", "child"]


async def test_a_failing_job_is_reported_and_the_next_job_still_runs() -> None:
    scheduler, sink, log = make()

    async def boom() -> None:
        raise ValueError("decision D-000009 has no payout")

    scheduler.schedule(T0, "payout:D-000009:credit_payout", boom)
    scheduler.schedule(T0, "after", job(log, "after"))
    assert await scheduler.run_due(T0) == 2
    assert log == ["after"]
    assert sink.failures == [("payout:D-000009:credit_payout", T0, "decision D-000009 has no payout")]


async def test_scheduler_remembers_names_and_reports_the_clock() -> None:
    scheduler, _, log = make()
    scheduler.schedule(T0, "payout:D-000001:execute_payout", job(log, "x"))
    assert scheduler.was_scheduled("payout:D-000001:execute_payout")
    assert not scheduler.was_scheduled("payout:D-000002:execute_payout")
    assert scheduler.now() == T0
    await scheduler.run_due(T0)
    assert scheduler.was_scheduled("payout:D-000001:execute_payout")


def test_schedule_rejects_naive_times_empty_names_and_non_callables() -> None:
    scheduler, _, log = make()
    with pytest.raises(ValueError, match="timezone-aware"):
        scheduler.schedule(datetime(2025, 8, 19, 17), "x", job(log, "x"))  # noqa: DTZ001
    with pytest.raises(ValueError, match="needs a name"):
        scheduler.schedule(T0, "  ", job(log, "x"))
    with pytest.raises(TypeError, match="not callable"):
        scheduler.schedule(T0, "x", "not a job")  # type: ignore[arg-type]


def test_failure_recorder_audits_and_feeds_step_failures_and_replay_stops() -> None:
    audit, feed = AuditLog(None), FeedLog()
    recorder = FailureRecorder(audit, feed)
    recorder.step_failed("payout:D-000001:credit_payout", T0, KeyError("x" * 500))
    recorder.replay_stopped(T0 + MINUTE, RuntimeError("boom"))
    first, second = audit.entries()
    assert (first.action, first.actor, first.subject_type, first.subject_id) == (
        "workflow.step_failed",
        "system",
        "workflow_step",
        "payout:D-000001:credit_payout",
    )
    assert first.data["error_type"] == "KeyError"
    assert len(first.data["error"]) == 200
    assert first.data["due_at"] == T0.isoformat()
    assert (second.action, second.data) == ("replay.stopped", {"error_type": "RuntimeError", "error": "boom"})
    texts = [item.text_en for item in feed.items()]
    assert texts == [
        "Workflow step payout:D-000001:credit_payout failed (KeyError); the replay continues",
        "The replay clock stopped after an error (RuntimeError); press play to go on",
    ]
    assert {item.type for item in feed.items()} == {"error"}
