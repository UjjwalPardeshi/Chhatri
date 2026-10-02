"""Officer queue and one-tap decisions (SPEC §19, §12, §9.4).

Approve/decline need the officer bearer token. The decision itself is made by the policy engine
through ``Orchestrator.officer_decide`` (SPEC §0.2: code decides the money); the route returns the
new decision and the resolved case so the console can show the result inline (SPEC §20).
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends, Path, Query

from chhatri.api.deps import RuntimeDep, require_officer
from chhatri.api.envelope import ok, ok_list
from chhatri.api.errors import ApiError
from chhatri.api.ports import RuntimePort
from chhatri.api.requests import OfficerNoteRequest
from chhatri.domain.enums import CaseStatus
from chhatri.domain.models import Case
from chhatri.replay import views

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cases", tags=["cases"])

CASE_ID_PATTERN: Final = r"^C-\d{1,9}$"
DEFAULT_LIMIT: Final = 100
MAX_LIMIT: Final = 500
NO_NOTE: Final = OfficerNoteRequest()
CaseId = Annotated[str, Path(pattern=CASE_ID_PATTERN)]
OfficerDep = Annotated[str, Depends(require_officer)]


def _case_or_404(runtime: RuntimePort, case_id: str) -> Case:
    try:
        return runtime.store.case(case_id)
    except KeyError as exc:
        raise ApiError(404, f"case {case_id} not found") from exc


@router.get("")
async def list_cases(
    runtime: RuntimeDep,
    status: Annotated[CaseStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Cases, optionally filtered by status (OPEN | APPROVED | DECLINED | CLOSED)."""
    cases = runtime.store.cases(status)
    items = [views.case_view(runtime, case) for case in cases[offset : offset + limit]]
    return ok_list(items, total=len(cases), limit=limit, offset=offset)


@router.get("/{case_id}")
async def get_case(runtime: RuntimeDep, case_id: CaseId) -> dict[str, Any]:
    """One case with its evidence bundle (SPEC §12)."""
    return ok(views.case_view(runtime, _case_or_404(runtime, case_id)))


async def _decide(
    runtime: RuntimePort, case_id: str, *, approve: bool, officer_id: str, note: str
) -> dict[str, Any]:
    _case_or_404(runtime, case_id)
    try:
        decision = await runtime.orchestrator.officer_decide(
            case_id, approve=approve, officer_id=officer_id, note=note
        )
    except ValueError as exc:
        logger.info("officer action on %s refused: %s", case_id, exc)
        raise ApiError(409, f"case {case_id} cannot be decided in its current state") from exc
    logger.info("case %s %s by %s", case_id, "approved" if approve else "declined", officer_id)
    case = _case_or_404(runtime, case_id)
    shown = views.decision_view(decision) if decision is not None else None
    return ok({"decision": shown, "case": views.case_view(runtime, case)})


@router.post("/{case_id}/approve")
async def approve(
    officer: OfficerDep, runtime: RuntimeDep, case_id: CaseId, body: OfficerNoteRequest = NO_NOTE
) -> dict[str, Any]:
    """Officer approves (SPEC §9.4): the engine pays within the policy limits."""
    return await _decide(runtime, case_id, approve=True, officer_id=officer, note=body.note)


@router.post("/{case_id}/decline")
async def decline(
    officer: OfficerDep, runtime: RuntimeDep, case_id: CaseId, body: OfficerNoteRequest = NO_NOTE
) -> dict[str, Any]:
    """Officer declines (SPEC §9.4)."""
    return await _decide(runtime, case_id, approve=False, officer_id=officer, note=body.note)
