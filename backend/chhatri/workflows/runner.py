"""Workflow execution engines (SPEC §14.5, §15).

InProcessWorkflowEngine: Schedules and executes steps in-process.
N8nWorkflowEngine: Delegates to n8n via HTTP.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from chhatri.integrations.base import IntegrationError, WorkflowRun
from chhatri.workflows.definitions import Scheduler, StepHandlers, StepSpec

logger = logging.getLogger(__name__)


class InProcessWorkflowEngine:
    """In-process workflow execution that schedules steps via Scheduler.

    Implements the WorkflowEngine protocol. Steps are scheduled at start + offset
    and executed via StepHandlers. Errors are logged with context and re-raised
    to the scheduler, never swallowed.
    """

    def __init__(self, scheduler: Scheduler, step_handlers: StepHandlers,
                 workflows: Mapping[str, tuple[StepSpec, ...]]) -> None:
        """Initialize workflow engine.

        Args:
            scheduler: Scheduler to use for scheduling steps.
            step_handlers: Step handlers to execute steps.
            workflows: Mapping of workflow name to step specs.
        """
        self.scheduler = scheduler
        self.step_handlers = step_handlers
        self.workflows = workflows

    async def start(self, workflow: str, payload: dict[str, Any]) -> WorkflowRun:
        """Start a workflow.

        Schedules all steps in the workflow at start + offset times.

        Args:
            workflow: Workflow name.
            payload: Workflow payload.

        Returns:
            WorkflowRun with engine="in-process".

        Raises:
            IntegrationError: If workflow is unknown.
        """
        if workflow not in self.workflows:
            raise IntegrationError(
                "workflows",
                f"Unknown workflow: {workflow}",
            )

        run_id = str(uuid.uuid4())
        start_time = self.scheduler.now()

        # Schedule all steps
        steps = self.workflows[workflow]
        for step_spec in steps:
            # Calculate execution time
            exec_time = self._add_minutes(start_time, step_spec.delay_minutes_from_start)

            # Create step execution closure
            async def execute_step(
                wf: str = workflow,
                step_name: str = step_spec.name,
                step_payload: dict[str, Any] = payload,
            ) -> None:
                try:
                    await self.step_handlers.run_step(wf, step_name, step_payload)
                except Exception as e:
                    logger.error(
                        f"Workflow {wf} step {step_name} failed: {e}",
                        exc_info=True,
                    )
                    raise

            # Schedule the step
            self.scheduler.schedule(exec_time, f"{workflow}:{step_spec.name}", execute_step)

        return WorkflowRun(
            workflow=workflow,
            run_id=run_id,
            engine="in-process",
            accepted=True,
            detail="Scheduled locally",
        )

    @staticmethod
    def _add_minutes(dt: datetime, minutes: int) -> datetime:
        """Add minutes to a datetime.

        Args:
            dt: Base datetime.
            minutes: Minutes to add.

        Returns:
            Datetime with minutes added.
        """
        from datetime import timedelta
        return dt + timedelta(minutes=minutes)


class N8nWorkflowEngineWrapper:
    """Wrapper around N8nWorkflowEngine from integrations module.

    Delegates workflow execution to n8n via HTTP webhooks.
    """

    def __init__(self, base_url: str, internal_secret: str, timeout: float = 5.0) -> None:
        """Initialize n8n workflow engine wrapper.

        Args:
            base_url: n8n base URL.
            internal_secret: Shared secret for callbacks.
            timeout: HTTP request timeout in seconds.
        """
        from chhatri.integrations.n8n import N8nWorkflowEngine as N8nImpl
        self._engine = N8nImpl(base_url, internal_secret, timeout)

    async def start(self, workflow: str, payload: dict[str, Any]) -> WorkflowRun:
        """Start a workflow on n8n.

        Args:
            workflow: Workflow name.
            payload: Workflow payload.

        Returns:
            WorkflowRun with engine="n8n".

        Raises:
            IntegrationError: If the request fails.
        """
        return await self._engine.start(workflow, payload)
