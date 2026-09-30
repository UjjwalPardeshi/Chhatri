"""Service and live-map routes (SPEC §19, §0.1, §14.4, §17.2)."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import chhatri.api.routers.meta as meta_module
from chhatri.api.app import create_app
from chhatri.api.schemas import (
    FeatureCollection,
    IntegrationStatus,
    PreflightItem,
    Session,
    StateSnapshot,
    WeatherNow,
    ZonePanel,
)
from chhatri.clock import IST
from tests.api import canned
from tests.api.fakes import INTEGRATION_NAMES, OFFICER_TOKEN, FakeAppState, make_settings
from tests.api.helpers import data_of, error_of, list_of


async def test_integrations_lists_every_component(client: AsyncClient) -> None:
    items, meta = list_of(await client.get("/api/integrations"), IntegrationStatus)
    assert tuple(item.name for item in items) == INTEGRATION_NAMES
    assert (meta.total, meta.limit, meta.offset) == (15, 15, 0)
    assert {item.name: item.mode for item in items}["whatsapp"] == "LIVE"


async def test_session_hands_out_the_officer_token_in_demo_mode(client: AsyncClient) -> None:
    assert data_of(await client.get("/api/session"), Session).officer_token == OFFICER_TOKEN


async def test_session_is_404_outside_demo_mode(patched_views: None) -> None:
    state = FakeAppState(make_settings(chhatri_demo_mode=False))
    app = create_app(state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
        response = await http.get("/api/session")
    error_of(response, 404, "not_found")
    assert OFFICER_TOKEN not in response.text


async def test_preflight_lists_checks(client: AsyncClient) -> None:
    items, meta = list_of(await client.get("/api/preflight"), PreflightItem)
    assert [item.name for item in items] == ["artefacts", "scenario", "integrations", "clock"]
    assert meta.total == 4


async def test_weather_is_404_when_live_weather_is_off(client: AsyncClient) -> None:
    error_of(await client.get("/api/weather/now"), 404, "not_found")


@pytest.fixture
async def weather_client(fake_state: FakeAppState, patched_views: None) -> AsyncClient:
    app = create_app(make_settings(openmeteo_live=True), state=fake_state)
    await fake_state.load("monsoon")
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def test_weather_returns_this_hours_rain(
    weather_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Frozen:
        def now(self) -> datetime:
            return datetime(2026, 9, 30, 15, 42, tzinfo=IST)

    monkeypatch.setattr(meta_module, "SystemClock", Frozen)
    async with weather_client as http:
        weather = data_of(await http.get("/api/weather/now"), WeatherNow)
    assert weather.hour == "2026-09-30T15:00:00+05:30"
    assert weather.rain_mm == 7.5
    assert weather.attribution == "Weather data by Open-Meteo.com"


async def test_weather_upstream_failure_is_502(weather_client: AsyncClient, fake_state: FakeAppState) -> None:
    fake_state.runtime.integrations.weather.fail = True
    async with weather_client as http:
        error_of(await http.get("/api/weather/now"), 502, "upstream_error")


def test_weather_without_the_current_hour_is_502() -> None:
    hour = datetime(2026, 9, 30, 15, tzinfo=IST)
    with pytest.raises(meta_module.ApiError) as raised:
        meta_module._rain_at((datetime(2026, 9, 30, 14, tzinfo=IST),), (1.0,), hour, "open-meteo")
    assert raised.value.status == 502


@pytest.mark.parametrize("kind", ["zones", "hexes"])
async def test_geo_layers_are_feature_collections(client: AsyncClient, kind: str) -> None:
    layer = data_of(await client.get(f"/api/geo/{kind}"), FeatureCollection)
    assert layer.features[0].properties == canned.geojson(kind)["features"][0]["properties"]


async def test_state_snapshot_matches_the_schema(client: AsyncClient) -> None:
    snapshot = data_of(await client.get("/api/state"), StateSnapshot)
    assert snapshot.clock.scenario == "monsoon"
    assert snapshot.kpis.shops_paid == 312
    assert snapshot.demo_merchant_id == "S-0142"
    assert [zone.label for zone in snapshot.zones][1] == "Z7 · 37% · 46 shops"


async def test_zone_panel_uses_the_deck_strings(client: AsyncClient) -> None:
    panel = data_of(await client.get("/api/zones/Z7"), ZonePanel)
    assert [(row.label, row.value) for row in panel.rows] == [
        ("Alert", "Red alert from 14:00"),
        ("Sales", "37% of expected for 3 hours"),
        ("Cover", "46 of 46 prepaid"),
        ("Paid", "17:04, with the settlement"),
        ("Total", "₹58,900 · instalments paused"),
    ]
    z9 = data_of(await client.get("/api/zones/Z9"), ZonePanel)
    assert z9.explanation == canned.Z9_EXPLANATION


async def test_unknown_zone_is_404_and_bad_id_is_422(client: AsyncClient) -> None:
    error_of(await client.get("/api/zones/Z99"), 404, "not_found")
    error_of(await client.get("/api/zones/seven"), 422, "validation_error")


async def test_geo_and_policy_work_before_any_load(bare_client: AsyncClient, app: FastAPI) -> None:
    assert (await bare_client.get("/api/geo/zones")).status_code == 200
    assert (await bare_client.get("/api/policy")).status_code == 200
    error_of(await bare_client.get("/api/integrations"), 409, "no_scenario")
