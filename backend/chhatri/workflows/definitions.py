"""Workflow definitions (SPEC §15).

Step lists with simulated-time offsets from the policy rules.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class StepSpec:
    """Workflow step specification.

    SPEC §24.5:
    - name: step name (e.g., "execute_payout")
    - delay_minutes_from_start: simulated-time offset from workflow start in minutes
    """

    name: str
    delay_minutes_from_start: int


class Scheduler(Protocol):
    """Scheduler protocol for workflow steps.

    Implemented by the orchestrator to schedule step execution at specific times.
    """

    def schedule(self, at: datetime, name: str, fn: Callable[[], Awaitable[None]]) -> None:
        """Schedule a step for execution at a specific time.

        Args:
            at: Datetime when the step should execute (IST-aware).
            name: Step name for logging.
            fn: Async function to execute.
        """
        ...

    def now(self) -> datetime:
        """Get the current simulated time.

        Returns:
            Current datetime (IST-aware).
        """
        ...


class StepHandlers(Protocol):
    """Step execution handler protocol.

    Implemented by the orchestrator to handle workflow step execution.
    """

    async def run_step(self, workflow: str, step: str, payload: Mapping[str, Any]) -> None:
        """Execute a workflow step.

        Args:
            workflow: Workflow name (e.g., "payout").
            step: Step name (e.g., "execute_payout").
            payload: Step payload.

        Raises:
            Exception: If the step execution fails.
        """
        ...


def _build_payout_workflow(payout_rail_delay_minutes: int,
                           instalment_pause_delay_minutes: int) -> tuple[StepSpec, ...]:
    """Build payout workflow steps from policy rules.

    SPEC §15, §24.5:
    - execute_payout: offset +0
    - credit_payout: offset +payout_rail_delay_minutes
    - notify_merchant: offset +payout_rail_delay_minutes
    - pause_instalment: offset +instalment_pause_delay_minutes

    Args:
        payout_rail_delay_minutes: Delay from policy rules.
        instalment_pause_delay_minutes: Delay from policy rules.

    Returns:
        Tuple of StepSpec objects.
    """
    return (
        StepSpec(name="execute_payout", delay_minutes_from_start=0),
        StepSpec(name="credit_payout", delay_minutes_from_start=payout_rail_delay_minutes),
        StepSpec(name="notify_merchant", delay_minutes_from_start=payout_rail_delay_minutes),
        StepSpec(name="pause_instalment", delay_minutes_from_start=instalment_pause_delay_minutes),
    )


def _build_human_review_workflow() -> tuple[StepSpec, ...]:
    """Build human review workflow steps.

    SPEC §15:
    - open_case: offset +0
    - notify_officer: offset +0

    Returns:
        Tuple of StepSpec objects.
    """
    return (
        StepSpec(name="open_case", delay_minutes_from_start=0),
        StepSpec(name="notify_officer", delay_minutes_from_start=0),
    )


def _build_followup_workflow(dispute_sla_hours: int) -> tuple[StepSpec, ...]:
    """Build follow-up workflow steps.

    SPEC §15:
    - check_case_sla: offset +dispute_sla_hours*60

    Args:
        dispute_sla_hours: SLA hours from policy rules.

    Returns:
        Tuple of StepSpec objects.
    """
    return (
        StepSpec(name="check_case_sla", delay_minutes_from_start=dispute_sla_hours * 60),
    )


def build_workflows(payout_rail_delay_minutes: int, instalment_pause_delay_minutes: int,
                    dispute_sla_hours: int) -> Mapping[str, tuple[StepSpec, ...]]:
    """Build all workflow definitions from policy rules.

    Args:
        payout_rail_delay_minutes: Delay from policy rules.
        instalment_pause_delay_minutes: Delay from policy rules.
        dispute_sla_hours: SLA hours from policy rules.

    Returns:
        Mapping of workflow name to step specs.
    """
    return {
        "payout": _build_payout_workflow(payout_rail_delay_minutes, instalment_pause_delay_minutes),
        "human-review": _build_human_review_workflow(),
        "follow-up": _build_followup_workflow(dispute_sla_hours),
    }


# Default workflow definitions for immediate use
# These will be populated by the registry based on policy rules
WORKFLOWS: Mapping[str, tuple[StepSpec, ...]] = {}
