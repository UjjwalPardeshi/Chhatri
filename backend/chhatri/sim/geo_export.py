"""The committed geography files (SPEC §5.1, §5.2, §24.1), shared by scripts/build_geo.py and the
data pipeline so both write byte-identical files.

- ``data/zones.json``: ``[{id, ward, name, centroid: {lat, lng}, shops, waterlogging_prone}]``
- ``data/geo/zones.geojson``: ward polygons with zone properties
- ``data/geo/hexes.geojson``: H3 res-8 cells with ``h3``, ``zone_id``, ``shops``

``shops`` counts covered pilot merchants of the full city (Z3 shows 141: Ramesh is not counted).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from chhatri.sim.city import build_city
from chhatri.sim.types import City

logger = logging.getLogger(__name__)

ZONES_JSON = Path("zones.json")
ZONES_GEOJSON = Path("geo") / "zones.geojson"
HEXES_GEOJSON = Path("geo") / "hexes.geojson"


def zones_table(city: City) -> list[dict[str, Any]]:
    shops = {
        f["properties"]["id"]: f["properties"]["shops"] for f in city.geography.zones_geojson["features"]
    }
    return [
        {
            "id": z.id,
            "ward": z.ward,
            "name": z.name,
            "centroid": {"lat": z.centroid_lat, "lng": z.centroid_lng},
            "shops": shops[z.id],
            "waterlogging_prone": z.waterlogging_prone,
        }
        for z in city.zones
    ]


def _dump(payload: object, *, indent: int | None) -> str:
    separators = (",", ": ") if indent else (",", ":")
    return json.dumps(payload, ensure_ascii=False, indent=indent, separators=separators) + "\n"


def geo_files(city: City) -> dict[Path, str]:
    """Path relative to the data directory -> file text."""
    return {
        ZONES_JSON: _dump(zones_table(city), indent=2),
        ZONES_GEOJSON: _dump(city.geography.zones_geojson, indent=None),
        HEXES_GEOJSON: _dump(city.geography.hexes_geojson, indent=None),
    }


def write_geo_files(seed: int, data_dir: Path, out_dir: Path | None = None) -> list[Path]:
    """Build the full city from ``data_dir`` and write the three files under ``out_dir`` (default data_dir)."""
    target = Path(out_dir) if out_dir is not None else Path(data_dir)
    city = build_city(seed, Path(data_dir), scale="full")
    written = []
    for rel, text in geo_files(city).items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        logger.info("wrote %s (%d bytes)", path, path.stat().st_size)
        written.append(path)
    return written
