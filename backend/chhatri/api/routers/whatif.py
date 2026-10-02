"""The what-if panel's recompute (H24; fs-08 section 11, data-model-and-api section 5.9).

Behind the flag ``h24_whatif``: while it is off the route answers the ordinary 404 ``not_found``. Read-only and
public like the console's other reads: a pure function of the loaded scenario and the request, so it writes no
audit entry, id, record, feed item or event and calls no model. A slider sends several requests a second, so
the route has a rate-limit group of its own (``whatif``).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from chhatri.api.deps import RuntimeDep, StateDep, rate_limit, require_feature
from chhatri.api.envelope import ok
from chhatri.api.errors import ApiError
from chhatri.api.requests import WhatIfRequest
from chhatri.replay import views
from chhatri.replay.whatif import NoCompletedWindow, Overrides, WhatIfInputError, what_if

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/whatif",
    tags=["whatif"],
    dependencies=[Depends(require_feature("h24_whatif")), Depends(rate_limit("whatif"))],
)


@router.post("/area")
async def whatif_area(body: WhatIfRequest, state: StateDep, runtime: RuntimeDep) -> dict[str, Any]:
    """Recompute a zone's trigger and, with ``example_merchant_id``, one shop's payout arithmetic.

    404 for an unknown zone, 409 ``no_scenario`` before a load and 409 ``conflict`` before one whole window of
    hours is complete, 422 for an override out of range, an unknown key, an ``at`` that is not an hour the
    replay has completed, or a merchant that is not covered in the zone.
    """
    if body.zone_id not in {zone.id for zone in state.static.city.zones}:
        raise ApiError(404, f"zone {body.zone_id} not found")
    overrides = Overrides(
        alert=body.overrides.alert,
        hourly_index_pct=None
        if body.overrides.hourly_index_pct is None
        else tuple(body.overrides.hourly_index_pct),
        shops_in_index=body.overrides.shops_in_index,
        already_triggered_today=body.overrides.already_triggered_today,
    )
    try:
        outcome = what_if(
            runtime,
            zone_id=body.zone_id,
            at=body.at,
            overrides=overrides,
            example_merchant_id=body.example_merchant_id,
        )
    except NoCompletedWindow as exc:
        raise ApiError(409, str(exc)) from exc
    except WhatIfInputError as exc:
        logger.info("what-if refused: %s", exc)  # the field and the reason, never the value
        raise ApiError(422, "invalid request", fields={exc.field: exc.reason}) from exc
    return ok(views.whatif_view(outcome))
