"""Geo endpoints (SPEC §19).

GET /api/geo/zones — GeoJSON with ward polygons
GET /api/geo/hexes — GeoJSON with H3 cells
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from chhatri.api.deps import get_state
from chhatri.api.envelope import ok

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/geo/zones")
async def zones(state: Annotated = Depends(get_state)) -> dict[str, Any]:
    """GeoJSON with ward polygons and properties (SPEC §19).

    Properties: id, ward, name, shops, waterlogging_prone.
    """
    zones_geojson = state.static.zones_geojson
    if not zones_geojson:
        # Load from data if not cached
        try:
            zones_path = state.static.data_dir / "geo" / "zones.geojson"
            if zones_path.exists():
                zones_geojson = json.loads(zones_path.read_text())
        except Exception as e:
            logger.error(f"Failed to load zones geojson: {e}")
            zones_geojson = {"type": "FeatureCollection", "features": []}
    return ok(zones_geojson)


@router.get("/geo/hexes")
async def hexes(state: Annotated = Depends(get_state)) -> dict[str, Any]:
    """GeoJSON with H3 resolution 8 cells (SPEC §19).

    Properties: h3, zone_id, shops.
    """
    hexes_geojson = state.static.hexes_geojson
    if not hexes_geojson:
        # Load from data if not cached
        try:
            hexes_path = state.static.data_dir / "geo" / "hexes.geojson"
            if hexes_path.exists():
                hexes_geojson = json.loads(hexes_path.read_text())
        except Exception as e:
            logger.error(f"Failed to load hexes geojson: {e}")
            hexes_geojson = {"type": "FeatureCollection", "features": []}
    return ok(hexes_geojson)
