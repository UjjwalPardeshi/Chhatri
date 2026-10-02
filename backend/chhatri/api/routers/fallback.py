"""The X6 fallback switch (card 4.5; fs-08 section 9.3, data-model-and-api section 5.6).

`POST /api/integrations/{component}/fallback` forces a component into its fallback path (`{"force": true}`) or releases
it (`{"force": false}`). It is a demo control: it needs flag `x6_provider_panel`, `CHHATRI_DEMO_MODE` and the officer
token, in that order of answers (404, 404, 401 or 403). The component must exist (404) and, to be forced, have a
fallback path and be LIVE, the lender excepted (409). The forced set is process-wide (`integrations/switch.py`).
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends

from chhatri.api.deps import OFFICER_ID, RuntimeDep, SettingsDep, require_feature, require_officer
from chhatri.api.envelope import ok
from chhatri.api.errors import ApiError
from chhatri.api.schemas.base import Schema
from chhatri.integrations.panel import panel_rows
from chhatri.integrations.switch import PROCESS_SWITCH

logger = logging.getLogger(__name__)

AUDIT_ACTION: Final = "integration.fallback_set"
CANNOT_FORCE: Final = "this component cannot be forced"


async def require_demo_mode(settings: SettingsDep) -> None:
    """404 like `GET /api/session` outside demo mode: the switch is a stage control, not a production one."""
    if not settings.chhatri_demo_mode:
        raise ApiError(404, "not found")


router = APIRouter(
    prefix="/api/integrations",
    tags=["integrations"],
    dependencies=[Depends(require_feature("x6_provider_panel")), Depends(require_demo_mode)],
)


class ForceBody(Schema):
    force: bool


@router.post("/{component}/fallback")
async def set_fallback(
    component: str,
    body: ForceBody,
    settings: SettingsDep,
    runtime: RuntimeDep,
    officer: Annotated[str, Depends(require_officer)],
) -> dict[str, Any]:
    """Force or release `component`; answers its updated row. Idempotent: a repeat changes and audits nothing."""
    switch = PROCESS_SWITCH
    rows = {row["name"]: row for row in panel_rows(runtime.integrations, settings, switch)}
    row = rows.get(component)
    if row is None:
        raise ApiError(404, f"component {component} not found")
    if body.force and not row["switchable"]:
        raise ApiError(409, CANNOT_FORCE, code="conflict")
    changed = switch.force(component) if body.force else switch.release(component)
    if changed:
        runtime.audit.append(
            at=runtime.clock.now(),
            actor=f"officer:{officer or OFFICER_ID}",
            action=AUDIT_ACTION,
            subject_type="integration",
            subject_id=component,
            data={"forced": body.force},
        )
        logger.info("integration %s %s", component, "forced to fallback" if body.force else "released")
    updated = {r["name"]: r for r in panel_rows(runtime.integrations, settings, switch)}
    return ok(updated[component])
