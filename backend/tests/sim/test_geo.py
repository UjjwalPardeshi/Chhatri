"""SPEC §5.1, §5.2, §24.1: zones, hexes and zone_of."""

from __future__ import annotations

import json
from pathlib import Path

import h3
import pytest
from shapely.geometry import Point, shape

from chhatri.sim.geo import (
    OFFICIAL_WARD_ORDER,
    WardGeography,
    build_geography,
    geometry_json,
    ward_zone_ids,
    with_hex_shops,
    zone_number,
)
from chhatri.sim.types import City

EXPECTED_IDS = {
    "F/S": "Z7", "G/S": "Z3", "E": "Z12", "M/W": "Z9",
    "A": "Z1", "B": "Z2", "C": "Z4", "D": "Z5", "F/N": "Z6", "G/N": "Z8", "H/E": "Z10", "H/W": "Z11",
    "K/E": "Z13", "K/W": "Z14", "L": "Z15", "M/E": "Z16", "N": "Z17", "P/S": "Z18", "P/N": "Z19",
    "R/S": "Z20", "R/C": "Z21", "R/N": "Z22", "S": "Z23", "T": "Z24",
}  # fmt: skip


@pytest.fixture(scope="module")
def geo(data_dir: Path) -> WardGeography:
    return build_geography(data_dir / "geo" / "bmc_wards.geojson", {"Z7": 46, "Z3": 141})


def test_ward_ids_follow_the_pilot_table_and_official_order() -> None:
    assert dict(ward_zone_ids()) == EXPECTED_IDS
    assert len(OFFICIAL_WARD_ORDER) == 20
    assert sorted(zone_number(z) for z in EXPECTED_IDS.values()) == list(range(1, 25))


def test_zone_number_rejects_non_zone_ids() -> None:
    assert zone_number("Z12") == 12
    with pytest.raises(ValueError):
        zone_number("S-0142")


def test_zones_sorted_named_and_waterlogging(geo: WardGeography) -> None:
    assert [z.id for z in geo.zones] == [f"Z{i}" for i in range(1, 25)]
    by_id = {z.id: z for z in geo.zones}
    assert (by_id["Z7"].ward, by_id["Z7"].name) == ("F/S", "Parel · Lalbaug")
    assert (by_id["Z3"].ward, by_id["Z3"].name) == ("G/S", "Worli · Lower Parel")
    assert (by_id["Z12"].ward, by_id["Z12"].name) == ("E", "Byculla")
    assert (by_id["Z9"].ward, by_id["Z9"].name) == ("M/W", "Chembur")
    prone = {z.ward for z in geo.zones if z.waterlogging_prone}
    assert prone == {"F/S", "F/N", "G/N", "H/E", "K/W", "L"}


def test_zone_of_matches_ward_polygons(geo: WardGeography, data_dir: Path) -> None:
    raw = json.loads((data_dir / "geo" / "bmc_wards.geojson").read_text())
    for feature in raw["features"]:
        point = shape(feature["geometry"]).representative_point()
        assert geo.zone_of(point.y, point.x) == EXPECTED_IDS[feature["properties"]["name"]]
    assert geo.zone_of(19.0046, 72.8424) == "Z7"  # Anil, near Hindmata
    assert geo.zone_of(18.95, 72.70) is None  # Arabian Sea
    assert geo.zone_of(28.61, 77.21) is None  # Delhi


def test_hexes_are_res8_with_centre_inside_their_ward(geo: WardGeography) -> None:
    assert len({hx.h3 for hx in geo.hexes}) == len(geo.hexes) > 600
    assert [hx.h3 for hx in geo.hexes] == sorted(hx.h3 for hx in geo.hexes)
    shapes = dict(geo.ward_shapes)
    for hx in geo.hexes:
        assert h3.get_resolution(hx.h3) == 8
        lat, lng = h3.cell_to_latlng(hx.h3)
        assert (round(lat, 6), round(lng, 6)) == (hx.center_lat, hx.center_lng)
        assert shapes[hx.zone_id].covers(Point(lng, lat))
    assert {hx.zone_id for hx in geo.hexes} == {z.id for z in geo.zones}


def test_geojson_properties_lnglat_and_closed_rings(geo: WardGeography) -> None:
    zones = geo.zones_geojson["features"]
    assert [f["properties"]["id"] for f in zones] == [z.id for z in geo.zones]
    z7 = next(f for f in zones if f["properties"]["id"] == "Z7")
    assert {"id", "ward", "name", "shops", "waterlogging_prone"} <= set(z7["properties"])
    assert z7["properties"]["shops"] == 46
    assert next(f for f in zones if f["properties"]["id"] == "Z1")["properties"]["shops"] == 0
    for feature in zones + geo.hexes_geojson["features"]:
        polygons = feature["geometry"]["coordinates"]
        if feature["geometry"]["type"] == "Polygon":
            polygons = [polygons]
        for ring in (r for p in polygons for r in p):
            assert ring[0] == ring[-1] and len(ring) >= 4
            assert all(72.7 < lng < 73.1 and 18.8 < lat < 19.4 for lng, lat in ring)
    hexes = geo.hexes_geojson["features"]
    assert set(hexes[0]["properties"]) == {"h3", "zone_id", "shops"}


def test_with_hex_shops_sets_counts_and_rejects_unknown_cells(geo: WardGeography) -> None:
    cell = geo.hexes[0].h3
    updated = with_hex_shops(geo, {cell: 5})
    counts = {f["properties"]["h3"]: f["properties"]["shops"] for f in updated.hexes_geojson["features"]}
    assert counts[cell] == 5 and sum(counts.values()) == 5
    assert updated.zone_of(19.0046, 72.8424) == "Z7"
    with pytest.raises(ValueError, match="outside the grid"):
        with_hex_shops(geo, {"8f283082aa20c00": 1})


def test_build_geography_rejects_bad_inputs(tmp_path: Path, data_dir: Path) -> None:
    wards = data_dir / "geo" / "bmc_wards.geojson"
    with pytest.raises(ValueError, match="unknown zones"):
        build_geography(wards, {"Z99": 1})
    broken = tmp_path / "broken.geojson"
    broken.write_text("{not json")
    with pytest.raises(ValueError, match="cannot read"):
        build_geography(broken, {})
    raw = json.loads(wards.read_text())
    raw["features"] = raw["features"][:-1]
    partial = tmp_path / "partial.geojson"
    partial.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="ward set mismatch"):
        build_geography(partial, {})
    raw = json.loads(wards.read_text())
    raw["features"].append(raw["features"][0])
    dup = tmp_path / "dup.geojson"
    dup.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="duplicate ward"):
        build_geography(dup, {})


def test_invalid_geometry_and_geometry_json_types(tmp_path: Path, data_dir: Path) -> None:
    raw = json.loads((data_dir / "geo" / "bmc_wards.geojson").read_text())
    raw["features"][0]["geometry"] = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]],
    }
    bad = tmp_path / "bowtie.geojson"
    bad.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="invalid geometry"):
        build_geography(bad, {})
    with pytest.raises(ValueError, match="Polygon"):
        geometry_json(Point(0, 0))


def test_city_geography_counts_covered_shops_per_hex(full_city: City) -> None:
    features = full_city.geography.hexes_geojson["features"]
    per_hex = {f["properties"]["h3"]: f["properties"]["shops"] for f in features}
    assert sum(per_hex.values()) == len(full_city.covers)
    anil = full_city.merchant("S-0142")
    assert per_hex[anil.h3_cell] >= 1
    zone_shops = {
        f["properties"]["id"]: f["properties"]["shops"] for f in full_city.geography.zones_geojson["features"]
    }
    assert zone_shops["Z3"] == 141  # Ramesh (uncovered) is not counted
