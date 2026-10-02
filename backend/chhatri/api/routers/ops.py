"""Operations counts for the console's ops strip (H8; fs-08 section 10, data-model-and-api section 5.7).

Behind the flag ``h8_ops_strip``: while it is off the route answers the ordinary 404 ``not_found``. Read-only,
no token (counts and ids only, no personal data), 409 ``no_scenario`` before a scenario is loaded.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from chhatri.api.deps import RuntimeDep, require_feature
from chhatri.api.envelope import ok
from chhatri.replay import views

router = APIRouter(prefix="/api/ops", tags=["ops"], dependencies=[Depends(require_feature("h8_ops_strip"))])


@router.get("/summary")
async def ops_summary(runtime: RuntimeDep) -> dict[str, Any]:
    """Open cases, the next due one, claims decided by the engine, money paid today and holiday requests."""
    return ok(views.ops_summary(runtime))
