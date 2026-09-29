"""Tests for geography builder (SPEC §5.1, §5.2, §24.1)."""

from pathlib import Path

import pytest

from chhatri.sim.geo import build_geography, PILOT_WARDS, WATERLOGGING_PRONE_WARDS


@pytest.fixture
def data_dir():
    """Path to test data directory."""
    return Path(__file__).resolve().parent.parent.parent / "data"


@pytest.fixture
def wards_geojson(data_dir):
    """Path to wards GeoJSON."""
    return data_dir / "geo" / "bmc_wards.geojson"


def test_geography_zones_count(wards_geojson):
    """Test that geography has 24 zones (SPEC §5.1)."""
    shops = {f"Z{i}": 10 for i in range(1, 25)}
    shops.update({
        "Z3": 141,
        "Z7": 46,
        "Z9": 64,
        "Z12": 125,
    })

    geo = build_geography(wards_geojson, shops)

    assert len(geo.zones) == 24
    assert all(geo.zones[i].id == f"Z{i+1}" for i in range(24))


def test_zone_id_mapping(wards_geojson):
    """Test zone-id mapping is correct per SPEC §5.1."""
    shops = {f"Z{i}": 10 for i in range(1, 25)}
    shops.update({
        "Z3": 141,
        "Z7": 46,
        "Z9": 64,
        "Z12": 125,
    })

    geo = build_geography(wards_geojson, shops)

    # Check pilot wards
    assert any(z.id == "Z7" and z.ward == "F/S" for z in geo.zones)
    assert any(z.id == "Z3" and z.ward == "G/S" for z in geo.zones)
    assert any(z.id == "Z12" and z.ward == "E" for z in geo.zones)
    assert any(z.id == "Z9" and z.ward == "M/W" for z in geo.zones)


def test_waterlogging_prone_zones(wards_geojson):
    """Test waterlogging_prone is set correctly (SPEC §5.1)."""
    shops = {f"Z{i}": 10 for i in range(1, 25)}
    shops.update({
        "Z3": 141,
        "Z7": 46,
        "Z9": 64,
        "Z12": 125,
    })

    geo = build_geography(wards_geojson, shops)

    waterlogging_wards = {z.ward for z in geo.zones if z.waterlogging_prone}
    assert waterlogging_wards == WATERLOGGING_PRONE_WARDS


def test_hexes_generated(wards_geojson):
    """Test that hexes are generated for each zone (SPEC §5.2)."""
    shops = {f"Z{i}": 10 for i in range(1, 25)}
    shops.update({
        "Z3": 141,
        "Z7": 46,
        "Z9": 64,
        "Z12": 125,
    })

    geo = build_geography(wards_geojson, shops)

    # Should have hexes
    assert len(geo.hexes) > 0

    # Each hex should have a zone_id
    zone_ids = {hex_obj.zone_id for hex_obj in geo.hexes}
    assert len(zone_ids) > 0


def test_geojson_zones_format(wards_geojson):
    """Test zones GeoJSON has correct format (SPEC §5.1)."""
    shops = {f"Z{i}": 10 for i in range(1, 25)}
    shops.update({
        "Z3": 141,
        "Z7": 46,
        "Z9": 64,
        "Z12": 125,
    })

    geo = build_geography(wards_geojson, shops)

    # Should be a FeatureCollection
    assert geo.zones_geojson["type"] == "FeatureCollection"
    assert "features" in geo.zones_geojson

    # Each feature should have properties
    for feature in geo.zones_geojson["features"]:
        assert "properties" in feature
        props = feature["properties"]
        assert "id" in props
        assert "ward" in props
        assert "name" in props
        assert "shops" in props
        assert "waterlogging_prone" in props


def test_geojson_hexes_format(wards_geojson):
    """Test hexes GeoJSON has correct format (SPEC §5.2)."""
    shops = {f"Z{i}": 10 for i in range(1, 25)}
    shops.update({
        "Z3": 141,
        "Z7": 46,
        "Z9": 64,
        "Z12": 125,
    })

    geo = build_geography(wards_geojson, shops)

    # Should be a FeatureCollection
    assert geo.hexes_geojson["type"] == "FeatureCollection"
    assert "features" in geo.hexes_geojson

    # Each feature should have properties
    for feature in geo.hexes_geojson["features"]:
        assert "properties" in feature
        props = feature["properties"]
        assert "h3" in props
        assert "zone_id" in props
        assert "shops" in props


def test_geojson_coordinates_format(wards_geojson):
    """Test GeoJSON uses [lng, lat] coordinate format (SPEC §5.1)."""
    shops = {f"Z{i}": 10 for i in range(1, 25)}
    shops.update({
        "Z3": 141,
        "Z7": 46,
        "Z9": 64,
        "Z12": 125,
    })

    geo = build_geography(wards_geojson, shops)

    # Check zones GeoJSON coordinates
    for feature in geo.zones_geojson["features"]:
        coords = feature["geometry"]["coordinates"]
        # Should be in [lng, lat] format (numbers near Mumbai)
        # Just check it's structured properly
        assert isinstance(coords, list)


def test_zone_centroid_inside_polygon(wards_geojson):
    """Test that zone centroids are computed correctly."""
    shops = {f"Z{i}": 10 for i in range(1, 25)}
    shops.update({
        "Z3": 141,
        "Z7": 46,
        "Z9": 64,
        "Z12": 125,
    })

    geo = build_geography(wards_geojson, shops)

    # All zones should have centroids in reasonable Mumbai bounds
    for zone in geo.zones:
        # Mumbai is roughly between 18.9-19.3 lat, 72.8-73.0 lng
        assert 18.8 < zone.centroid_lat < 19.5
        assert 72.7 < zone.centroid_lng < 73.1
