"""In-process workflow engine schedules each step at start + offset (B1, SPEC §15)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from chhatri.clock import ist
from chhatri.workflows import runner
from chhatri.workflows.runner import InProcessWorkflowEngine, N8nWorkflowEngine

from .fakes import FakeScheduler, RecordingHandlers

DECIDED = ist(2025, 8, 19, 17, 0)
PAYOUT = {"decision_id": "D-000001", "merchant_id": "S-0142"}


async def test_monsoon_timeline_decision_1700_credit_1704_pause_1705() -> None:
    scheduler, handlers = FakeScheduler(DECIDED), RecordingHandlers()
    run = await InProcessWorkflowEngine(scheduler, handlers).start("payout", PAYOUT)
    assert (run.run_id, run.engine, run.accepted) == ("payout:D-000001", "in-process", True)
    assert [(at.strftime("%H:%M"), name) for at, name, _ in scheduler.jobs] == [
        ("17:00", "payout:D-000001:execute_payout"),
        ("17:04", "payout:D-000001:credit_payout"),
        ("17:04", "payout:D-000001:notify_merchant"),
        ("17:05", "payout:D-000001:request_holiday"),
    ]
    await scheduler.run_all()
    assert [step for _, step, _ in handlers.calls] == [
        "execute_payout",
        "credit_payout",
        "notify_merchant",
        "request_holiday",
    ]
    assert all(dict(payload) == PAYOUT for *_, payload in handlers.calls)


async def test_follow_up_waits_for_sla_in_simulated_time() -> None:
    scheduler = FakeScheduler(DECIDED)
    await InProcessWorkflowEngine(scheduler, RecordingHandlers()).start("follow-up", {"case_id": "C-2291"})
    assert {at for at, *_ in scheduler.jobs} == {DECIDED + timedelta(hours=24)}


async def test_duplicate_start_is_ignored() -> None:
    scheduler = FakeScheduler(DECIDED)
    engine = InProcessWorkflowEngine(scheduler, RecordingHandlers())
    await engine.start("human-review", {"case_id": "C-2291", "merchant_id": "S-0142"})
    again = await engine.start("human-review", {"case_id": "C-2291", "merchant_id": "S-0142"})
    assert again.accepted is False and len(scheduler.jobs) == 2


async def test_invalid_starts_raise() -> None:
    engine = InProcessWorkflowEngine(FakeScheduler(DECIDED), RecordingHandlers())
    with pytest.raises(ValueError, match="unknown workflow"):
        await engine.start("refund", {})
    with pytest.raises(ValueError):
        await engine.start("payout", {"decision_id": "D-1"})


async def test_step_failures_propagate_to_the_scheduler() -> None:
    scheduler = FakeScheduler(DECIDED)
    await InProcessWorkflowEngine(scheduler, RecordingHandlers(fail_on="credit_payout")).start(
        "payout", PAYOUT
    )
    with pytest.raises(RuntimeError, match="credit_payout failed"):
        await scheduler.run_all()


async def test_takeover_schedules_only_steps_not_yet_reported() -> None:
    """Fallback after a partial n8n run (B1): steps n8n already reported are not scheduled twice."""
    scheduler = FakeScheduler(DECIDED)

    async def reported() -> None:
        return None

    scheduler.schedule(DECIDED, "payout:D-000001:execute_payout", reported)
    run = await InProcessWorkflowEngine(scheduler, RecordingHandlers()).start("payout", PAYOUT)
    assert run.accepted and run.detail == "3 steps scheduled from 17:00"
    assert [name for _, name, _ in scheduler.jobs] == [
        "payout:D-000001:execute_payout",
        "payout:D-000001:credit_payout",
        "payout:D-000001:notify_merchant",
        "payout:D-000001:request_holiday",
    ]


def test_n8n_engine_is_reexported() -> None:
    from chhatri.integrations.n8n import N8nWorkflowEngine as Impl

    assert N8nWorkflowEngine is Impl and "N8nWorkflowEngine" in runner.__all__
