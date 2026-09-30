"""Workflow engines (SPEC §15, §24.5; binding decision B1).

`InProcessWorkflowEngine` schedules every step of a workflow on the simulated `Scheduler` at
start + offset (start = `scheduler.now()`, i.e. the decision time) and runs it through
`StepHandlers.run_step`. `N8nWorkflowEngine` (implemented in `chhatri.integrations.n8n`, re-exported
here) hands the same workflow to n8n. Run ids are deterministic (`{workflow}:{subject}`) and a run is
started at most once per engine, so a repeated start never double-pays or double-notifies.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Awaitable, Callable, Mapping
from datetime import timedelta
from typing import Any

from chhatri.integrations.base import WorkflowRun
from chhatri.integrations.n8n import N8nWorkflowEngine
from chhatri.workflows.definitions import (
    WORKFLOWS,
    Scheduler,
    StepHandlers,
    StepSpec,
    run_id_for,
    validate_payload,
)

logger = logging.getLogger(__name__)

ENGINE = "in-process"

__all__ = ["ENGINE", "InProcessWorkflowEngine", "N8nWorkflowEngine"]


class InProcessWorkflowEngine:
    """WorkflowEngine running steps on the simulated scheduler (same steps as n8n)."""

    def __init__(
        self,
        scheduler: Scheduler,
        step_handlers: StepHandlers,
        workflows: Mapping[str, tuple[StepSpec, ...]] = WORKFLOWS,
    ) -> None:
        self._scheduler = scheduler
        self._handlers = step_handlers
        self._workflows = workflows
        self._started: set[str] = set()
        self._lock = threading.Lock()

    async def start(self, workflow: str, payload: dict[str, Any]) -> WorkflowRun:
        steps = self._workflows.get(workflow)
        if steps is None:
            raise ValueError(f"unknown workflow {workflow!r}")
        checked = validate_payload(workflow, payload)
        run_id = run_id_for(workflow, checked)
        with self._lock:
            if run_id in self._started:
                logger.info("workflow %s already started; ignored", run_id)
                return WorkflowRun(workflow, run_id, ENGINE, False, "already started")
            self._started.add(run_id)
        start = self._scheduler.now()
        for spec in steps:
            at = start + timedelta(minutes=spec.delay_minutes_from_start)
            self._scheduler.schedule(
                at, f"{run_id}:{spec.name}", self._job(workflow, run_id, spec.name, checked)
            )
        return WorkflowRun(workflow, run_id, ENGINE, True, f"{len(steps)} steps scheduled from {start:%H:%M}")

    def _job(
        self, workflow: str, run_id: str, step: str, payload: Mapping[str, Any]
    ) -> Callable[[], Awaitable[None]]:
        async def run() -> None:
            try:
                await self._handlers.run_step(workflow, step, payload)
            except Exception:
                logger.exception("workflow %s step %s failed", run_id, step)
                raise

        return run
