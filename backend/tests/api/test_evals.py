"""`GET /api/evals/summary` (H25; data-model-and-api section 5.10): flag, no-run answer, stored run, bad file."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from chhatri.api.app import create_app
from chhatri.evals import summary as evals_summary
from chhatri.evals.run import run_offline, write_run
from chhatri.evals.summary import no_run_summary
from tests.api.fakes import FakeAppState, make_settings
from tests.api.helpers import error_of

URL = "/api/evals/summary"


async def _client(features: str) -> AsyncIterator[AsyncClient]:
    state = FakeAppState(make_settings(chhatri_features=features))
    app = create_app(state.static.settings, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        yield http


@pytest.fixture
async def on() -> AsyncIterator[AsyncClient]:
    async for http in _client("h25_evals"):
        yield http


@pytest.fixture
async def off() -> AsyncIterator[AsyncClient]:
    async for http in _client(""):
        yield http


async def test_flag_off_is_the_ordinary_404(off: AsyncClient) -> None:
    error_of(await off.get(URL), 404, "not_found")


async def test_no_stored_run_is_200_with_six_not_measured_suites(
    on: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(evals_summary, "SUMMARY_PATH", tmp_path / "none.json")
    response = await on.get(URL)
    assert response.status_code == 200
    assert response.json() == {"ok": True, "data": no_run_summary()}
    assert "mode" not in response.json()["data"] and "provider" not in response.json()["data"]


async def test_stored_run_is_served_as_written(
    on: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    summary, items = run_offline(["guard"])
    monkeypatch.setattr(evals_summary, "SUMMARY_PATH", write_run(summary, items, tmp_path))
    data = (await on.get(URL)).json()["data"]
    assert data == summary and data["measured"] is True
    guard = data["suites"][1]
    assert guard["status"] == "MEASURED" and all(m["k"] is not None for m in guard["metrics"])
    assert data["run"]["data_origin"] == "synthetic"


async def test_unreadable_file_is_no_run_with_the_reason(
    on: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bad = tmp_path / "summary.json"
    bad.write_text(json.dumps({"measured": True, "run": None, "suites": []}))
    monkeypatch.setattr(evals_summary, "SUMMARY_PATH", bad)
    data = (await on.get(URL)).json()["data"]
    assert data["measured"] is False and {s["reason"] for s in data["suites"]} == {"result file unreadable"}


async def test_route_is_read_only(on: AsyncClient) -> None:
    assert (await on.post(URL)).status_code == 405
