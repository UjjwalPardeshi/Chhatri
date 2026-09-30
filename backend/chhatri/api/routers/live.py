"""Live map routes: geography, full snapshot and zone panel (SPEC §19, §17.2, §20)."""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Path

from chhatri.api.deps import RuntimeDep, StateDep
from chhatri.api.envelope import ok
from chhatri.api.errors import ApiError
from chhatri.replay import views

router = APIRouter(prefix="/api", tags=["live"])

ZONE_ID_PATTERN: Final = r"^Z\d{1,2}$"


@router.get("/geo/zones")
async def geo_zones(state: StateDep) -> dict[str, Any]:
    """Ward polygons with zone properties (id, ward, name, shops, waterlogging_prone)."""
    return ok(state.static.zones_geojson)


@router.get("/geo/hexes")
async def geo_hexes(state: StateDep) -> dict[str, Any]:
    """H3 r8 cells with ``h3``, ``zone_id`` and ``shops``."""
    return ok(state.static.hexes_geojson)


@router.get("/state")
async def state_snapshot(runtime: RuntimeDep) -> dict[str, Any]:
    """Full ``StateSnapshot`` (clock, zones, hexes, kpis, triggers, feed); 409 before a load."""
    return ok(views.snapshot(runtime))


@router.get("/zones/{zone_id}")
async def zone_panel(
    state: StateDep, runtime: RuntimeDep, zone_id: str = Path(pattern=ZONE_ID_PATTERN)
) -> dict[str, Any]:
    """``ZonePanel`` with the exact deck strings (SPEC §17.2); 404 for an unknown zone."""
    if zone_id not in {zone.id for zone in state.static.city.zones}:
        raise ApiError(404, f"zone {zone_id} not found")
    return ok(views.zone_panel(runtime, zone_id))
