"""Geography builder (SPEC §5.1, §5.2, §24.1).

Zone-id mapping is fixed by the pilot assignment table (§5.1). Non-pilot wards get ids
in official BMC order. H3 resolution-8 cells whose centre lies inside a ward polygon.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path

import h3
import shapely.geometry as geom
from h3 import LatLngPoly

from chhatri.domain.models import Zone
from chhatri.sim.types import Geography, Hex

# Fixed zone-id mapping for pilot wards (SPEC §5.1)
PILOT_WARDS = {
    "F/S": ("Z7", "Parel · Lalbaug"),
    "G/S": ("Z3", "Worli · Lower Parel"),
    "E": ("Z12", "Byculla"),
    "M/W": ("Z9", "Chembur"),
}

# Official BMC ward order for remaining zones (SPEC §5.1)
OFFICIAL_WARD_ORDER = [
    "A", "B", "C", "D", "F/N", "G/N", "H/E", "H/W", "K/E", "K/W", "L", "M/E", "N",
    "P/S", "P/N", "R/S", "R/C", "R/N", "S", "T"
]

# Waterlogging-prone zones (SPEC §5.1)
WATERLOGGING_PRONE_WARDS = {"F/S", "F/N", "G/N", "H/E", "K/W", "L"}


def build_geography(
    wards_geojson: Path,
    shops_per_zone: Mapping[str, int],
    resolution: int = 8
) -> Geography:
    """Build geography from BMC wards GeoJSON.

    Args:
        wards_geojson: Path to bmc_wards.geojson (MultiPolygon features with 'name' property)
        shops_per_zone: Mapping from zone_id to pilot shop count
        resolution: H3 resolution (default 8 per SPEC §5.2)

    Returns:
        Geography with zones, hexes, and GeoJSON representations.

    Raises:
        ValueError: If any ward is missing or zone-id mapping fails.
    """
    with open(wards_geojson) as f:
        geojson_data = json.load(f)

    features = geojson_data["features"]

    # Build ward → geometry + zone mapping
    ward_to_geom: dict[str, dict] = {}
    ward_to_zone_id: dict[str, str] = {}

    for feature in features:
        ward_name = feature["properties"]["name"]
        ward_to_geom[ward_name] = feature

        if ward_name in PILOT_WARDS:
            zone_id, display_name = PILOT_WARDS[ward_name]
            ward_to_zone_id[ward_name] = zone_id

    # Assign zone ids to remaining wards in official order
    used_zone_ids = set(PILOT_WARDS[w][0] for w in PILOT_WARDS)
    next_zone_idx = 1
    for ward in OFFICIAL_WARD_ORDER:
        if ward not in PILOT_WARDS:
            # Find next available zone id (skip pilot ids)
            while f"Z{next_zone_idx}" in used_zone_ids:
                next_zone_idx += 1
            ward_to_zone_id[ward] = f"Z{next_zone_idx}"
            used_zone_ids.add(f"Z{next_zone_idx}")
            next_zone_idx += 1

    # Verify all wards have zone ids
    missing_wards = [w for w in ward_to_geom if w not in ward_to_zone_id]
    if missing_wards:
        raise ValueError(f"Wards without zone mapping: {missing_wards}")

    # Build Zone objects
    zones_list: list[Zone] = []
    zone_to_feature: dict[str, dict] = {}

    for ward_name, feature in ward_to_geom.items():
        zone_id = ward_to_zone_id[ward_name]

        # Parse geometry and compute centroid
        coords = feature["geometry"]["coordinates"]
        # MultiPolygon: [[[exterior ring], [hole1], ...], ...]
        all_rings = []
        for polygon in coords:
            for ring in polygon:
                all_rings.append(ring)

        # Create shapely geometry from all rings
        if all_rings:
            exterior = all_rings[0]
            holes = all_rings[1:] if len(all_rings) > 1 else []
            polygon = geom.Polygon(exterior, holes=holes)
        else:
            continue

        centroid = polygon.centroid

        # Get display name
        display_name = PILOT_WARDS[ward_name][1] if ward_name in PILOT_WARDS else ward_name

        waterlogging = ward_name in WATERLOGGING_PRONE_WARDS

        zone = Zone(
            id=zone_id,
            ward=ward_name,
            name=display_name,
            centroid_lat=centroid.y,
            centroid_lng=centroid.x,
            waterlogging_prone=waterlogging
        )
        zones_list.append(zone)
        zone_to_feature[zone_id] = (feature, polygon)

    # Sort zones by numeric id (Z1, Z2, ..., Z24)
    zones_list.sort(key=lambda z: int(z.id[1:]))
    zones_tuple = tuple(zones_list)

    # Build H3 hexes
    hexes_list: list[Hex] = []
    hex_to_zone: dict[str, str] = {}
    hex_to_shops: dict[str, int] = defaultdict(int)

    for zone in zones_tuple:
        feature, polygon = zone_to_feature[zone.id]

        # Get H3 cells whose center lies in the polygon
        # Convert shapely polygon to LatLngPoly (expects [(lat, lng), ...])
        exterior_coords = list(polygon.exterior.coords)
        lat_lng_coords = [(lat, lng) for lng, lat in exterior_coords]

        # Create LatLngPoly and get cells
        try:
            lat_lng_poly = LatLngPoly(lat_lng_coords)
            # geo_to_cells returns an iterator
            cells = list(h3.geo_to_cells(lat_lng_poly, resolution))
        except Exception:
            # If polygon conversion fails, use empty list
            cells = []

        for h3_cell in cells:
            center = h3.cell_to_latlng(h3_cell)
            # Verify that center actually lies in the polygon
            point = geom.Point(center[1], center[0])  # h3 returns (lat, lng), shapely uses (lng, lat)

            if polygon.contains(point):
                hex_obj = Hex(
                    h3=h3_cell,
                    zone_id=zone.id,
                    center_lat=center[0],
                    center_lng=center[1]
                )
                hexes_list.append(hex_obj)
                hex_to_zone[h3_cell] = zone.id

    hexes_tuple = tuple(hexes_list)

    # Build GeoJSON for zones (with simplified geometry for browser)
    zones_geojson_features = []
    for zone in zones_tuple:
        feature, polygon = zone_to_feature[zone.id]

        # Simplify polygon for browser (preserve topology)
        simplified = polygon.simplify(0.0002, preserve_topology=True)

        # Convert back to GeoJSON format
        if simplified.is_empty:
            simplified = polygon

        # Handle both Polygon and MultiPolygon
        if isinstance(simplified, geom.Polygon):
            geom_coords = [list(simplified.exterior.coords)]
            for interior in simplified.interiors:
                geom_coords.append(list(interior.coords))
            geom_type = "Polygon"
        elif isinstance(simplified, geom.MultiPolygon):
            geom_coords = []
            for poly in simplified.geoms:
                poly_coords = [list(poly.exterior.coords)]
                for interior in poly.interiors:
                    poly_coords.append(list(interior.coords))
                geom_coords.append(poly_coords)
            geom_type = "MultiPolygon"
        else:
            geom_type = "Polygon"
            geom_coords = [[]]

        # Convert to [lng, lat] order for GeoJSON
        if geom_type == "Polygon":
            geom_coords = [[[lng, lat] for lat, lng in ring] for ring in geom_coords]
        else:
            geom_coords = [
                [[[lng, lat] for lat, lng in ring] for ring in poly]
                for poly in geom_coords
            ]

        geojson_feature = {
            "type": "Feature",
            "properties": {
                "id": zone.id,
                "ward": zone.ward,
                "name": zone.name,
                "shops": shops_per_zone.get(zone.id, 0),
                "waterlogging_prone": zone.waterlogging_prone
            },
            "geometry": {
                "type": geom_type,
                "coordinates": geom_coords
            }
        }
        zones_geojson_features.append(geojson_feature)

    zones_geojson = {
        "type": "FeatureCollection",
        "features": zones_geojson_features
    }

    # Build GeoJSON for hexes
    hexes_geojson_features = []
    for hex_obj in hexes_tuple:
        # Get hex boundary (returns tuple of (lat, lng) tuples)
        boundary_coords = h3.cell_to_boundary(hex_obj.h3)
        # Convert to [lng, lat] order and close the ring
        hex_coords = [[lng, lat] for lat, lng in boundary_coords]
        hex_coords.append(hex_coords[0])  # Close the ring

        geojson_feature = {
            "type": "Feature",
            "properties": {
                "h3": hex_obj.h3,
                "zone_id": hex_obj.zone_id,
                "shops": hex_to_shops.get(hex_obj.h3, 0)
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [hex_coords]
            }
        }
        hexes_geojson_features.append(geojson_feature)

    hexes_geojson = {
        "type": "FeatureCollection",
        "features": hexes_geojson_features
    }

    return Geography(
        zones=zones_tuple,
        zones_geojson=zones_geojson,
        hexes=hexes_tuple,
        hexes_geojson=hexes_geojson
    )
