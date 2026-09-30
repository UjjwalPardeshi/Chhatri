"""SPEC §5.1, §5.2: the committed geo files equal a fresh deterministic build."""

from __future__ import annotations

import json
from pathlib import Path

import h3

from chhatri.sim.geo_export import HEXES_GEOJSON, ZONES_GEOJSON, ZONES_JSON, geo_files
from chhatri.sim.types import City

from .conftest import load_script

MAX_BYTES = 1_500_000


def test_committed_geo_files_match_a_fresh_build(full_city: City, data_dir: Path) -> None:
    for rel, text in geo_files(full_city).items():
        committed = (data_dir / rel).read_bytes()
        assert committed == text.encode("utf-8"), f"{rel} is stale: run scripts/build_geo.py"
        assert len(committed) < MAX_BYTES


def test_zones_json_contents(data_dir: Path) -> None:
    zones = json.loads((data_dir / ZONES_JSON).read_text())
    assert [z["id"] for z in zones] == [f"Z{i}" for i in range(1, 25)]
    assert set(zones[0]) == {"id", "ward", "name", "centroid", "shops", "waterlogging_prone"}
    shops = {z["id"]: z["shops"] for z in zones}
    assert (shops["Z7"], shops["Z3"], shops["Z12"], shops["Z9"]) == (46, 141, 125, 64)


def test_geojson_files_are_valid(data_dir: Path) -> None:
    zones = json.loads((data_dir / ZONES_GEOJSON).read_text())
    hexes = json.loads((data_dir / HEXES_GEOJSON).read_text())
    assert zones["type"] == hexes["type"] == "FeatureCollection"
    assert len(zones["features"]) == 24
    for feature in hexes["features"]:
        props = feature["properties"]
        assert set(props) == {"h3", "zone_id", "shops"} and h3.get_resolution(props["h3"]) == 8
        ring = feature["geometry"]["coordinates"][0]
        lat, lng = h3.cell_to_latlng(props["h3"])
        assert ring[0] == ring[-1] and abs(ring[0][0] - lng) < 0.01 and abs(ring[0][1] - lat) < 0.01


def test_build_geo_script_is_byte_identical(tmp_path: Path, data_dir: Path) -> None:
    script = load_script("build_geo")
    assert script.main(["--data-dir", str(data_dir), "--out", str(tmp_path / "a")]) == 0
    for rel in (ZONES_JSON, ZONES_GEOJSON, HEXES_GEOJSON):
        assert (tmp_path / "a" / rel).read_bytes() == (data_dir / rel).read_bytes()
