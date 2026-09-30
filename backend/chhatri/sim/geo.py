"""Zones and hex grid from the real BMC ward polygons (SPEC §5.1, §5.2, §24.1).

`build_geography` maps the 24 wards to pilot zone ids with the fixed table of §5.1, builds the
H3 resolution-8 cells whose centre lies inside a ward (§5.2) and renders both as GeoJSON with
``[lng, lat]`` coordinates (rounded to 6 decimals, ~0.1 m) and closed rings.

The scaffold `Geography` (``chhatri.sim.types``) has no ``zone_of``; §24.1 requires it, so this
module returns `WardGeography`, a subclass that also keeps the exact ward shapes.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

import h3
import numpy as np
import shapely
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.geometry.base import BaseGeometry

from chhatri.domain.models import Zone
from chhatri.sim.types import Geography, Hex

logger = logging.getLogger(__name__)

HEX_RESOLUTION = 8
COORD_DECIMALS = 6

# SPEC §5.1: pilot wards have fixed ids so the demo map matches the deck.
PILOT_WARDS: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        "F/S": ("Z7", "Parel · Lalbaug"),
        "G/S": ("Z3", "Worli · Lower Parel"),
        "E": ("Z12", "Byculla"),
        "M/W": ("Z9", "Chembur"),
    }
)
# SPEC §5.1: every other ward, in official BMC order, takes the remaining ids in order.
OFFICIAL_WARD_ORDER: tuple[str, ...] = (
    "A", "B", "C", "D", "F/N", "G/N", "H/E", "H/W", "K/E", "K/W",
    "L", "M/E", "N", "P/S", "P/N", "R/S", "R/C", "R/N", "S", "T",
)  # fmt: skip
WARD_NAMES: Mapping[str, str] = MappingProxyType({
    "A": "Colaba · Fort", "B": "Dongri · Sandhurst Road", "C": "Kalbadevi · Marine Lines",
    "D": "Malabar Hill · Grant Road", "F/N": "Matunga · Sion", "G/N": "Dadar · Mahim",
    "H/E": "Bandra East · Santacruz East", "H/W": "Bandra West · Khar West",
    "K/E": "Andheri East", "K/W": "Andheri West · Juhu", "L": "Kurla", "M/E": "Govandi · Mankhurd",
    "N": "Ghatkopar", "P/S": "Goregaon", "P/N": "Malad", "R/S": "Kandivali",
    "R/C": "Borivali", "R/N": "Dahisar", "S": "Bhandup · Powai", "T": "Mulund",
})  # fmt: skip
WATERLOGGING_PRONE_WARDS: frozenset[str] = frozenset({"F/S", "F/N", "G/N", "H/E", "K/W", "L"})
N_ZONES = len(PILOT_WARDS) + len(OFFICIAL_WARD_ORDER)


def zone_number(zone_id: str) -> int:
    """Numeric part of a zone id (``"Z12"`` -> 12); the sort key of SPEC §24.1."""
    if not zone_id.startswith("Z") or not zone_id[1:].isdigit():
        raise ValueError(f"not a zone id: {zone_id!r}")
    return int(zone_id[1:])


def ward_zone_ids() -> Mapping[str, str]:
    """Ward code -> zone id per SPEC §5.1 (pilot table, then official order skipping pilot ids)."""
    mapping = {ward: zid for ward, (zid, _name) in PILOT_WARDS.items()}
    taken = {zone_number(z) for z in mapping.values()}
    free = (n for n in range(1, N_ZONES + 1) if n not in taken)
    for ward in OFFICIAL_WARD_ORDER:
        mapping[ward] = f"Z{next(free)}"
    return MappingProxyType(mapping)


@dataclass(frozen=True, slots=True)
class WardGeography(Geography):
    """`Geography` plus the exact ward shapes, so `zone_of` is exact (SPEC §24.1)."""

    ward_shapes: tuple[tuple[str, BaseGeometry], ...] = field(default=(), repr=False, compare=False)

    def zone_of(self, lat: float, lng: float) -> str | None:
        """Zone whose ward polygon covers the point (boundary included), else None (sea, elsewhere)."""
        return next((zid for zid, geom in self.ward_shapes if shapely.intersects_xy(geom, lng, lat)), None)


def _round(value: float) -> float:
    return round(value, COORD_DECIMALS)


Ring = tuple[tuple[float, float], ...]


def _ring(coords: Any) -> Ring:
    """Rounded [lng, lat] positions, explicitly closed. Immutable, so cached rings can be shared."""
    ring = tuple((_round(x), _round(y)) for x, y, *_ in coords)
    return ring if ring[0] == ring[-1] else (*ring, ring[0])


def _polygon_coords(poly: Polygon) -> tuple[Ring, ...]:
    return (_ring(poly.exterior.coords), *(_ring(i.coords) for i in poly.interiors))


def geometry_json(geom: BaseGeometry) -> dict[str, Any]:
    """GeoJSON geometry with [lng, lat] rounded coordinates and explicitly closed rings."""
    if isinstance(geom, Polygon):
        return {"type": "Polygon", "coordinates": _polygon_coords(geom)}
    if isinstance(geom, MultiPolygon):
        return {"type": "MultiPolygon", "coordinates": tuple(_polygon_coords(p) for p in geom.geoms)}
    raise ValueError(f"ward geometry must be a (Multi)Polygon, got {geom.geom_type}")


def _load_wards(wards_geojson: Path) -> dict[str, BaseGeometry]:
    try:
        raw = json.loads(wards_geojson.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read ward polygons from {wards_geojson}: {exc}") from exc
    wards: dict[str, BaseGeometry] = {}
    for feature in raw.get("features", ()):
        name = feature.get("properties", {}).get("name")
        geom = shape(feature["geometry"])
        if not geom.is_valid or geom.is_empty:
            raise ValueError(f"ward {name!r} has an invalid geometry")
        if name in wards:
            raise ValueError(f"duplicate ward {name!r}")
        wards[name] = geom
    expected = set(ward_zone_ids())
    if set(wards) != expected:
        raise ValueError(
            f"ward set mismatch: missing {sorted(expected - set(wards))}, extra {sorted(set(wards) - expected)}"
        )
    return wards


def _zone(ward: str, zone_id: str, geom: BaseGeometry) -> Zone:
    name = PILOT_WARDS[ward][1] if ward in PILOT_WARDS else WARD_NAMES[ward]
    centroid = geom.centroid
    return Zone(
        id=zone_id,
        ward=ward,
        name=name,
        centroid_lat=_round(centroid.y),
        centroid_lng=_round(centroid.x),
        waterlogging_prone=ward in WATERLOGGING_PRONE_WARDS,
    )


def _hexes(shapes: tuple[tuple[str, BaseGeometry], ...], resolution: int) -> tuple[Hex, ...]:
    """Cells whose centre lies inside a ward; zone = the first ward (numeric order) covering it."""
    candidates: set[str] = set()
    for _zid, geom in shapes:
        candidates.update(h3.geo_to_cells(geom.__geo_interface__, resolution))
    cells = sorted(candidates)
    centres = np.array([h3.cell_to_latlng(c) for c in cells], dtype=np.float64).reshape(-1, 2)
    owner = np.full(len(cells), -1)
    for i, (_zid, geom) in enumerate(shapes):
        owner = np.where((owner < 0) & shapely.intersects_xy(geom, centres[:, 1], centres[:, 0]), i, owner)
    return tuple(
        Hex(h3=c, zone_id=shapes[o][0], center_lat=_round(lat), center_lng=_round(lng))
        for c, o, (lat, lng) in zip(cells, owner.tolist(), centres.tolist(), strict=True)
        if o >= 0
    )


@dataclass(frozen=True, slots=True)
class _WardGrid:
    """Everything derived from the ward file alone (cached: pure function of file + resolution)."""

    zones: tuple[Zone, ...]
    shapes: tuple[tuple[str, BaseGeometry], ...]
    hexes: tuple[Hex, ...]
    zone_geometry: Mapping[str, dict[str, Any]]
    hex_rings: Mapping[str, Ring]


@lru_cache(maxsize=4)
def _ward_grid(path: str, mtime_ns: int, size: int, resolution: int) -> _WardGrid:
    """Parse wards, number zones and build the grid; keyed on the file's identity and stat."""
    wards = _load_wards(Path(path))
    ids = ward_zone_ids()
    zones = tuple(sorted((_zone(w, ids[w], g) for w, g in wards.items()), key=lambda z: zone_number(z.id)))
    shapes = tuple((z.id, wards[z.ward]) for z in zones)
    for _zid, geom in shapes:
        shapely.prepare(geom)
    hexes = _hexes(shapes, resolution)
    missing = {z.id for z in zones} - {hx.zone_id for hx in hexes}
    if missing:
        raise ValueError(f"zones without any hex at resolution {resolution}: {sorted(missing)}")
    logger.info(
        "geography: %d zones, %d hexes at resolution %d from %s", len(zones), len(hexes), resolution, path
    )
    return _WardGrid(
        zones=zones,
        shapes=shapes,
        hexes=hexes,
        zone_geometry=MappingProxyType({zid: geometry_json(g) for zid, g in shapes}),
        hex_rings=MappingProxyType({hx.h3: hex_ring(hx.h3) for hx in hexes}),
    )


def zones_feature_collection(
    zones: tuple[Zone, ...], geometry: Mapping[str, dict[str, Any]], shops_per_zone: Mapping[str, int]
) -> dict[str, Any]:
    """Ward polygons with zone properties (SPEC §5.1, §24.1)."""
    features = [
        {
            "type": "Feature",
            "properties": {
                "id": z.id,
                "ward": z.ward,
                "name": z.name,
                "shops": int(shops_per_zone.get(z.id, 0)),
                "waterlogging_prone": z.waterlogging_prone,
                "centroid_lat": z.centroid_lat,
                "centroid_lng": z.centroid_lng,
            },
            "geometry": dict(geometry[z.id]),
        }
        for z in zones
    ]
    return {"type": "FeatureCollection", "features": features}


def hexes_feature_collection(
    hexes: tuple[Hex, ...], rings: Mapping[str, Ring], hex_shops: Mapping[str, int]
) -> dict[str, Any]:
    """H3 cells with h3, zone_id and covered-shop count (SPEC §5.2, §24.1)."""
    features = [
        {
            "type": "Feature",
            "properties": {"h3": hx.h3, "zone_id": hx.zone_id, "shops": int(hex_shops.get(hx.h3, 0))},
            "geometry": {"type": "Polygon", "coordinates": (rings[hx.h3],)},
        }
        for hx in hexes
    ]
    return {"type": "FeatureCollection", "features": features}


def build_geography(
    wards_geojson: Path, shops_per_zone: Mapping[str, int], resolution: int = HEX_RESOLUTION
) -> WardGeography:
    """Zones (sorted Z1..Z24), their polygons and the H3 grid (SPEC §5.1, §5.2, §24.1).

    ``shops_per_zone`` feeds the ``shops`` property of the zone features (covered shops only,
    §5.4); hex shop counts start at 0 and are filled by `with_hex_shops` once merchants exist.
    """
    unknown = set(shops_per_zone) - set(ward_zone_ids().values())
    if unknown:
        raise ValueError(f"shops_per_zone has unknown zones: {sorted(unknown)}")
    path = Path(wards_geojson).resolve()
    try:
        stat = path.stat()
    except OSError as exc:
        raise ValueError(f"cannot read ward polygons from {path}: {exc}") from exc
    grid = _ward_grid(str(path), stat.st_mtime_ns, stat.st_size, resolution)
    return WardGeography(
        zones=grid.zones,
        zones_geojson=zones_feature_collection(grid.zones, grid.zone_geometry, shops_per_zone),
        hexes=grid.hexes,
        hexes_geojson=hexes_feature_collection(grid.hexes, grid.hex_rings, {}),
        ward_shapes=grid.shapes,
    )


def hex_ring(cell: str) -> Ring:
    """Closed [lng, lat] boundary ring of an H3 cell, rounded like every other coordinate."""
    return _ring((lng, lat) for lat, lng in h3.cell_to_boundary(cell))


def with_hex_shops(geography: WardGeography, hex_shops: Mapping[str, int]) -> WardGeography:
    """A copy whose hex features carry covered-shop counts per cell (SPEC §24.1 ``shops``)."""
    unknown = set(hex_shops) - {hx.h3 for hx in geography.hexes}
    if unknown:
        raise ValueError(f"hex_shops has cells outside the grid: {sorted(unknown)[:5]}")
    rings = {
        f["properties"]["h3"]: f["geometry"]["coordinates"][0] for f in geography.hexes_geojson["features"]
    }
    return WardGeography(
        zones=geography.zones,
        zones_geojson=geography.zones_geojson,
        hexes=geography.hexes,
        hexes_geojson=hexes_feature_collection(geography.hexes, rings, hex_shops),
        ward_shapes=geography.ward_shapes,
    )
