#!/usr/bin/env python3
"""Build geography data files (SPEC §5, scripts section).

Generates:
- backend/data/zones.json: zone metadata
- backend/data/geo/zones.geojson: zone polygons
- backend/data/geo/hexes.geojson: H3 cells
"""

import json
from pathlib import Path

from chhatri.sim.city import build_city
from chhatri.sim.geo import build_geography


def main():
    backend_dir = Path(__file__).resolve().parent.parent
    data_dir = backend_dir / "data"
    artifacts_dir = backend_dir / "artifacts"

    # Create artifacts directory if needed
    artifacts_dir.mkdir(exist_ok=True)

    # Build city to get shop counts per zone
    city = build_city(20251019, data_dir, scale="full")

    # Create shops_per_zone mapping
    shops_per_zone = {}
    for zone in city.zones:
        count = sum(1 for m in city.merchants if m.zone_id == zone.id and not m.is_demo) + (1 if any(m.zone_id == zone.id and m.is_demo for m in city.merchants) else 0)
        shops_per_zone[zone.id] = count

    # Build geography
    geography = build_geography(data_dir / "geo" / "bmc_wards.geojson", shops_per_zone)

    # Write zones.json
    zones_json = []
    for zone in geography.zones:
        zones_json.append({
            "id": zone.id,
            "ward": zone.ward,
            "name": zone.name,
            "centroid": {
                "lat": zone.centroid_lat,
                "lng": zone.centroid_lng
            },
            "shops": shops_per_zone.get(zone.id, 0),
            "waterlogging_prone": zone.waterlogging_prone
        })

    zones_path = data_dir / "zones.json"
    with open(zones_path, "w") as f:
        json.dump(zones_json, f, indent=2)
    print(f"Wrote {zones_path}")

    # Write zones.geojson
    zones_geojson_path = data_dir / "geo" / "zones.geojson"
    with open(zones_geojson_path, "w") as f:
        json.dump(geography.zones_geojson, f)
    print(f"Wrote {zones_geojson_path}")

    # Write hexes.geojson
    hexes_geojson_path = data_dir / "geo" / "hexes.geojson"
    with open(hexes_geojson_path, "w") as f:
        json.dump(geography.hexes_geojson, f)
    print(f"Wrote {hexes_geojson_path}")

    print("Geography files generated successfully!")


if __name__ == "__main__":
    main()
