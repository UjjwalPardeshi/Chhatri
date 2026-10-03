"""GET /api/pricing: the pricing simulator (business model §3; part of the what-if flag ``h24_whatif``).

Read-only and deterministic: it prices the cover for the levers in the query from the committed pricing table
(``backend/artifacts/pricing/events.json``, written by ``python -m chhatri.backtest.pricing``) and today's zone
premiums. No scenario, no provider, no write. 404 ``not_found`` while the flag is off or before the table is built.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends, Query

from chhatri.api.deps import StateDep, require_feature
from chhatri.api.envelope import ok
from chhatri.api.errors import ApiError
from chhatri.backtest.pricing import PRICING_FILE
from chhatri.backtest.pricing_model import Levers, levers_from_rules, price
from chhatri.config import BACKEND_DIR
from chhatri.ledger.premium_table import PREMIUMS_PATH

logger = logging.getLogger(__name__)

TABLE_PATH: Final = BACKEND_DIR / "artifacts" / PRICING_FILE

router = APIRouter(
    prefix="/api/pricing", tags=["pricing"], dependencies=[Depends(require_feature("h24_whatif"))]
)


@lru_cache(maxsize=1)
def _load(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        logger.error("pricing: cannot read %s: %s", path, exc)
        return None


def _current(path: Path = PREMIUMS_PATH) -> dict[str, int]:
    table = _load(path)
    return {str(k): int(v) for k, v in table.items()} if isinstance(table, dict) else {}


@router.get("")
async def get_pricing(
    state: StateDep,
    floor: Annotated[int | None, Query(ge=1, le=100)] = None,
    share: Annotated[
        int | None, Query(ge=10, le=100, description="payout share, % of the lost sales")
    ] = None,
    cap: Annotated[int | None, Query(ge=500, le=10_000, description="area daily cap, ₹")] = None,
    loading: Annotated[int | None, Query(ge=0, le=60, description="loading, % of the premium")] = None,
) -> dict[str, Any]:
    """Every zone's premium, expected payout and loss ratio at today's price, and the trigger's quality. A lever left
    out of the query is the published rules' value."""
    table = _load(TABLE_PATH)
    if table is None:
        raise ApiError(
            404, "the pricing table is not built yet (python -m chhatri.backtest.pricing)", code="not_found"
        )
    rules = state.static.rules
    defaults = levers_from_rules(rules)
    floor = defaults.floor_pct if floor is None else floor
    share = defaults.share_pct if share is None else share
    cap = defaults.cap_rupees if cap is None else cap
    loading = defaults.loading_pct if loading is None else loading
    if floor not in table["floors"]:
        raise ApiError(422, "invalid request", fields={"floor": f"one of {table['floors']}"})
    levers = Levers(floor, share, cap, loading, rules.premium.min_per_day_rupees)
    names = {z.id: z.name for z in state.static.city.zones}
    result = price(table, levers, _current())
    return ok(
        {
            **result,
            "zones": [{**z, "name": names.get(z["zone_id"], z["zone_id"])} for z in result["zones"]],
            "levers": {"floor_pct": floor, "share_pct": share, "cap_rupees": cap, "loading_pct": loading},
            "rules": {
                "version": rules.version,
                "floor_pct": defaults.floor_pct,
                "share_pct": defaults.share_pct,
                "cap_rupees": defaults.cap_rupees,
                "loading_pct": defaults.loading_pct,
                "min_per_day_rupees": defaults.min_per_day_rupees,
            },
        }
    )
