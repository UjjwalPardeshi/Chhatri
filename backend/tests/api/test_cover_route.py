"""GET /api/merchants/{id}/cover (K6): the route, the envelope and the clean errors, on the fake views."""

from __future__ import annotations

from httpx import AsyncClient

from chhatri.api.schemas.miniapp import CoverView
from tests.api.helpers import data_of, error_of


async def test_cover_is_served_in_the_envelope(client: AsyncClient) -> None:
    response = await client.get("/api/merchants/S-0142/cover")
    cover = data_of(response, CoverView)
    assert (cover.merchant_id, cover.status, cover.cover_id) == ("S-0142", "ACTIVE", "CV-0142")
    assert cover.premium_per_day_label == "₹18.62" and cover.alert_id == "A-20250818-01"
    assert response.json()["ok"] is True and set(response.json()) == {"ok", "data"}


async def test_cover_unknown_merchant_is_404(client: AsyncClient) -> None:
    error = error_of(await client.get("/api/merchants/S-9999/cover"), 404, "not_found")
    assert "S-9999" in error.message


async def test_cover_malformed_id_is_422(client: AsyncClient) -> None:
    error = error_of(await client.get("/api/merchants/S-12/cover"), 422, "validation_error")
    assert error.fields and "merchant_id" in error.fields


async def test_cover_before_a_scenario_is_loaded_is_409(bare_client: AsyncClient) -> None:
    error_of(await bare_client.get("/api/merchants/S-0142/cover"), 409, "no_scenario")
