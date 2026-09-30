"""Starting workflows from the orchestrator (SPEC §14.5, §15; binding decision B1).

Payloads are exactly SPEC §14.5: ``payout {decision_id, merchant_id}``, ``human-review {case_id,
merchant_id}``, ``follow-up {case_id}``. A workflow engine failure (n8n unreachable with no
fallback, or a timeout) must not abort the claims around it: it is logged, audited as
``workflow.start_failed`` and shown in the feed, and the caller continues.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

from chhatri.integrations.base import IntegrationError, WorkflowRun
from chhatri.workflows import definitions as wf

if TYPE_CHECKING:
    from chhatri.replay.state import Runtime

__all__ = ["start_case_workflows", "start_payout", "start_workflow"]

logger = logging.getLogger(__name__)

SYSTEM_ACTOR: Final = "system"


async def start_workflow(rt: Runtime, workflow: str, payload: Mapping[str, str]) -> WorkflowRun | None:
    """Start `workflow`; None (logged, audited, fed) when the workflow engine failed."""
    try:
        run = await rt.integrations.workflows.start(workflow, dict(payload))
    except IntegrationError as exc:
        subject = next(iter(payload.values()))
        logger.error("workflow %s for %s could not start: %s", workflow, subject, exc.safe_message)
        rt.audit.append(
            at=rt.clock.now(),
            actor=SYSTEM_ACTOR,
            action="workflow.start_failed",
            subject_type="workflow",
            subject_id=f"{workflow}:{subject}",
            data={"workflow": workflow, "payload": dict(payload), "error": exc.safe_message},
        )
        rt.feed.add(rt.clock.now(), "error", f"Workflow {workflow} for {subject} could not start")
        return None
    if not run.accepted:
        logger.warning("workflow run %s not accepted: %s", run.run_id, run.detail)
    return run


async def start_payout(rt: Runtime, decision_id: str, merchant_id: str) -> WorkflowRun | None:
    return await start_workflow(rt, wf.PAYOUT, {"decision_id": decision_id, "merchant_id": merchant_id})


async def start_case_workflows(rt: Runtime, case_id: str, merchant_id: str) -> None:
    """human-review now (open_case, notify_officer) and follow-up at the SLA (SPEC §12, B1)."""
    await start_workflow(rt, wf.HUMAN_REVIEW, {"case_id": case_id, "merchant_id": merchant_id})
    await start_workflow(rt, wf.FOLLOW_UP, {"case_id": case_id})
