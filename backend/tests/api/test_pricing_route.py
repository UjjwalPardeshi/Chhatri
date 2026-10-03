"""GET /api/pricing (the pricing simulator, behind h24_whatif): levers in, every zone's price out, read-only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from chhatri.api.app import create_app
from chhatri.api.routers import pricing
from chhatri.replay.state import AppState

BASE: Final = "http://testserver"
FLAG: Final = "h24_whatif"


def app_for(state: AppState, *, features: str = FLAG) -> FastAPI:
    return create_app(state.static.settings.model_copy(update={"chhatri_features": features}), state=state)


async def get(app: FastAPI, path: str) -> Any:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE, timeout=30.0) as http:
        return await http.get(path)


@pytest.fixture
def small_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "events.json"
    zones = {f"Z{i}": 2 for i in range(1, 25)}
    events = {"40": [], "50": [["Z7", "2025-08-19", 63, 1, [4380, 4380]]]}
    path.write_text(
        json.dumps(
            {
                "label": "t",
                "seasons": ["s"],
                "floors": [40, 50],
                "shops": zones,
                "real_drops": 1,
                "events": events,
            }
        )
    )
    monkeypatch.setattr(pricing, "TABLE_PATH", path)
    pricing._load.cache_clear()
    yield path
    pricing._load.cache_clear()


async def test_the_rules_levers_price_every_zone_and_name_it(real_state: AppState, small_table: Path) -> None:
    body = (await get(app_for(real_state), "/api/pricing")).json()["data"]
    assert body["levers"] == {"floor_pct": 50, "share_pct": 50, "cap_rupees": 2500, "loading_pct": 35}
    assert body["rules"]["version"] == real_state.static.rules.version
    z7 = next(z for z in body["zones"] if z["zone_id"] == "Z7")
    assert z7["name"] and z7["triggers"] == 1 and z7["premium_per_day_paise"] > 200
    assert body["city"]["recall"] == 1.0


async def test_the_levers_come_from_the_query(real_state: AppState, small_table: Path) -> None:
    lean = (await get(app_for(real_state), "/api/pricing?floor=50&share=30&cap=1500&loading=30")).json()[
        "data"
    ]
    full = (await get(app_for(real_state), "/api/pricing")).json()["data"]
    price = lambda body: next(z for z in body["zones"] if z["zone_id"] == "Z7")["premium_per_day_paise"]  # noqa: E731
    assert lean["levers"]["share_pct"] == 30 and price(lean) < price(full)


@pytest.mark.parametrize("query", ["floor=45", "share=5", "cap=100", "loading=90"])
async def test_a_lever_out_of_range_is_422(real_state: AppState, small_table: Path, query: str) -> None:
    assert (await get(app_for(real_state), f"/api/pricing?{query}")).status_code == 422


async def test_the_route_is_404_while_the_flag_is_off(real_state: AppState, small_table: Path) -> None:
    assert (await get(app_for(real_state, features=""), "/api/pricing")).status_code == 404


async def test_the_route_is_404_before_the_table_is_built(
    real_state: AppState, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pricing, "TABLE_PATH", tmp_path / "missing.json")
    pricing._load.cache_clear()
    response = await get(app_for(real_state), "/api/pricing")
    pricing._load.cache_clear()
    assert response.status_code == 404
