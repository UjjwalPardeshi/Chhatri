"""Tests for workflow engines (SPEC §14.5, §15)."""

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import pytest

from chhatri.integrations.base import IntegrationError
from chhatri.workflows.definitions import Scheduler, StepHandlers, StepSpec
from chhatri.workflows.runner import InProcessWorkflowEngine

IST = timezone(timedelta(hours=5, minutes=30))


class MockScheduler:
    """Mock scheduler for testing."""

    def __init__(self):
        self.scheduled_steps: list[tuple[datetime, str, Any]] = []
        self._now = datetime.now(tz=IST)

    def schedule(self, at: datetime, name: str, fn):
        """Record scheduled step."""
        self.scheduled_steps.append((at, name, fn))

    def now(self) -> datetime:
        """Return current time."""
        return self._now


class MockStepHandlers:
    """Mock step handlers for testing."""

    def __init__(self):
        self.executed_steps: list[tuple[str, str, dict]] = []

    async def run_step(self, workflow: str, step: str, payload: Mapping[str, Any]) -> None:
        """Record executed step."""
        self.executed_steps.append((workflow, step, dict(payload)))


class TestInProcessWorkflowEngine:
    """Tests for InProcessWorkflowEngine."""

    @pytest.mark.asyncio
    async def test_start_payout_workflow(self):
        """Test starting a payout workflow."""
        scheduler = MockScheduler()
        handlers = MockStepHandlers()

        workflows = {
            "payout": (
                StepSpec("execute_payout", 0),
                StepSpec("credit_payout", 4),
                StepSpec("notify_merchant", 4),
                StepSpec("pause_instalment", 5),
            )
        }

        engine = InProcessWorkflowEngine(scheduler, handlers, workflows)

        payload = {"decision_id": "D-000001", "merchant_id": "S-0142"}
        run = await engine.start("payout", payload)

        assert run.workflow == "payout"
        assert run.engine == "in-process"
        assert run.accepted is True
        assert len(scheduler.scheduled_steps) == 4

    @pytest.mark.asyncio
    async def test_start_workflow_with_correct_offsets(self):
        """Test that steps are scheduled with correct time offsets."""
        scheduler = MockScheduler()
        handlers = MockStepHandlers()
        base_time = scheduler.now()

        workflows = {
            "test": (
                StepSpec("step1", 0),
                StepSpec("step2", 5),
                StepSpec("step3", 10),
            )
        }

        engine = InProcessWorkflowEngine(scheduler, handlers, workflows)
        await engine.start("test", {})

        # Verify scheduling times
        times = [t for t, _, _ in scheduler.scheduled_steps]
        names = [n for _, n, _ in scheduler.scheduled_steps]

        assert len(times) == 3
        assert times[0] == base_time  # +0 min
        assert times[1] == base_time + timedelta(minutes=5)  # +5 min
        assert times[2] == base_time + timedelta(minutes=10)  # +10 min

    @pytest.mark.asyncio
    async def test_start_unknown_workflow(self):
        """Test starting an unknown workflow raises error."""
        scheduler = MockScheduler()
        handlers = MockStepHandlers()
        workflows = {}

        engine = InProcessWorkflowEngine(scheduler, handlers, workflows)

        with pytest.raises(IntegrationError, match="Unknown workflow"):
            await engine.start("unknown", {})

    @pytest.mark.asyncio
    async def test_start_human_review_workflow(self):
        """Test starting a human-review workflow."""
        scheduler = MockScheduler()
        handlers = MockStepHandlers()

        workflows = {
            "human-review": (
                StepSpec("open_case", 0),
                StepSpec("notify_officer", 0),
            )
        }

        engine = InProcessWorkflowEngine(scheduler, handlers, workflows)

        payload = {"case_id": "C-2291", "merchant_id": "S-0142"}
        run = await engine.start("human-review", payload)

        assert run.workflow == "human-review"
        assert len(scheduler.scheduled_steps) == 2

        # Both steps should be at the same time (offset 0)
        times = [t for t, _, _ in scheduler.scheduled_steps]
        assert times[0] == times[1]

    @pytest.mark.asyncio
    async def test_start_followup_workflow(self):
        """Test starting a follow-up workflow."""
        scheduler = MockScheduler()
        handlers = MockStepHandlers()

        workflows = {
            "follow-up": (
                StepSpec("check_case_sla", 24 * 60),  # 24 hours
            )
        }

        engine = InProcessWorkflowEngine(scheduler, handlers, workflows)

        payload = {"case_id": "C-2291"}
        run = await engine.start("follow-up", payload)

        assert len(scheduler.scheduled_steps) == 1

        # Verify offset is 24 hours
        exec_time = scheduler.scheduled_steps[0][0]
        expected_time = scheduler.now() + timedelta(hours=24)
        assert exec_time == expected_time

    def test_add_minutes(self):
        """Test the _add_minutes helper."""
        base = datetime(2025, 8, 19, 12, 0, 0, tzinfo=IST)

        result = InProcessWorkflowEngine._add_minutes(base, 30)

        assert result == datetime(2025, 8, 19, 12, 30, 0, tzinfo=IST)

    def test_add_minutes_crossing_day(self):
        """Test _add_minutes crossing day boundary."""
        base = datetime(2025, 8, 19, 23, 0, 0, tzinfo=IST)

        result = InProcessWorkflowEngine._add_minutes(base, 120)

        assert result == datetime(2025, 8, 20, 1, 0, 0, tzinfo=IST)
