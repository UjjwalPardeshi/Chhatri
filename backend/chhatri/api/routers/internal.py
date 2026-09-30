"""POST /internal/workflows/{step} — n8n step callbacks (SPEC §14.5, §15, §21; binding decision B1).

Authenticated with ``X-Chhatri-Secret``. The body is ``{run_id, workflow, step, payload}`` and the
path step must equal the body step. ``Orchestrator.handle_callback`` schedules the step effect at
decision time + the step's offset on the simulated scheduler and is idempotent per
``(run_id, step)``; it re-validates everything (n8n never decides, SPEC §14.5). The answer is
``{"ok": true, "data": {"step", "status": "done" | "skipped"}}``; any non-2xx stops the n8n run.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends, Path
from pydantic import ValidationError

from chhatri.api.deps import RuntimeDep, require_internal
from chhatri.api.envelope import ok
from chhatri.api.errors import ApiError
from chhatri.api.requests import WorkflowCallbackRequest
from chhatri.api.schemas import WorkflowCallbackResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(require_internal)])

STEP_PATTERN: Final = r"^[a-z_]{1,32}$"


@router.post("/workflows/{step}")
async def workflow_callback(
    runtime: RuntimeDep, body: WorkflowCallbackRequest, step: Annotated[str, Path(pattern=STEP_PATTERN)]
) -> dict[str, Any]:
    """Apply one workflow step reported by n8n."""
    if step != body.step:
        raise ApiError(422, "invalid request", fields={"step": "path step and body step differ"})
    try:
        result = await runtime.orchestrator.handle_callback(
            body.run_id, body.workflow, body.step, body.payload
        )
    except KeyError as exc:
        raise ApiError(404, "workflow subject not found") from exc
    except ValueError as exc:
        logger.warning("workflow callback %s/%s rejected: %s", body.workflow, body.step, exc)
        raise ApiError(409, f"step {body.step} is not valid for this run") from exc
    return ok(_result_view(result))


def _result_view(result: Mapping[str, Any]) -> dict[str, Any]:
    try:
        view = WorkflowCallbackResult.model_validate(
            {"step": result.get("step"), "status": result.get("status")}
        )
    except ValidationError as exc:
        logger.error("orchestrator returned a malformed callback result: %s", exc.errors())
        raise ApiError(500, "internal error") from exc
    return view.model_dump()
