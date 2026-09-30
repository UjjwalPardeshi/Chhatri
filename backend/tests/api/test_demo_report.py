"""The demo rehearsal's HTTP client and report (SPEC §22 ``scripts/demo_check.py``), without a backend.

`DemoApi` must turn every non-envelope or error answer into `DemoHttpError` naming the route; the
report must show a broken flow as a failed row and still run the next scenario; SKIP rows never
fail the check. The full flows run against the real app in ``tests/test_demo_flows.py``.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from chhatri.api.demo import (
    CheckRow,
    DemoApi,
    DemoHttpError,
    all_passed,
    compare,
    rehearse,
    render_json,
    render_table,
)
from chhatri.api.demo.flows import buy_cover, flow_names
from chhatri.api.demo.observe import SKIPPED, Observed

Handler = Any


def api_for(handler: Handler, *, token: str | None = None) -> DemoApi:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://demo.test")
    return DemoApi(client, officer_token=token)


def envelope(data: Any, status: int = 200, **extra: Any) -> httpx.Response:
    return httpx.Response(status, json={"ok": True, "data": data, **extra})


async def test_error_envelope_names_route_status_and_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409, json={"ok": False, "error": {"code": "no_scenario", "message": "load first"}}
        )

    with pytest.raises(DemoHttpError) as raised:
        await api_for(handler).get("/api/state")
    error = raised.value
    assert (error.method, error.path, error.status, error.detail) == (
        "GET",
        "/api/state",
        409,
        "no_scenario: load first",
    )
    assert str(error) == "GET /api/state answered 409: no_scenario: load first"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(502, text="<html>bad gateway</html>"),
        httpx.Response(200, json=["not", "an", "envelope"]),
        httpx.Response(200, json={"ok": False}),
    ],
)
async def test_anything_but_an_ok_envelope_is_an_error(response: httpx.Response) -> None:
    with pytest.raises(DemoHttpError):
        await api_for(lambda request: response).post("/api/replay/load", {"scenario": "monsoon"})


async def test_officer_token_comes_from_the_session_once() -> None:
    seen: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, request.headers.get("authorization")))
        if request.url.path == "/api/session":
            return envelope({"officer_token": "demo-token"})
        return envelope({"done": True})

    api = api_for(handler)
    await api.post("/api/cases/C-2291/approve", {"note": "ok"}, officer=True)
    await api.post("/api/cases/C-2292/approve", {"note": "ok"}, officer=True)
    assert seen == [
        ("/api/session", None),
        ("/api/cases/C-2291/approve", "Bearer demo-token"),
        ("/api/cases/C-2292/approve", "Bearer demo-token"),
    ]
    configured = api_for(handler, token="configured")
    assert await configured.officer_token() == "configured"


async def test_paging_helpers_read_every_page() -> None:
    items = list(range(7))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/audit":
            after = int(request.url.params["after"])
            page = [{"seq": s} for s in items if s > after][:3]
            return envelope(page)
        offset = int(request.url.params["offset"])
        return envelope(items[offset : offset + 3], meta={"total": len(items), "limit": 3, "offset": offset})

    api = api_for(handler)
    assert await api.get_all("/api/cases") == items
    assert [e["seq"] for e in await api.audit()] == items[1:]
    form = await api_for(lambda r: envelope({"status": r.content.decode()})).post_form("/x", {"a": "1"})
    assert form == {"status": "a=1"}


async def test_a_broken_flow_is_a_failed_row_and_the_next_flow_still_runs() -> None:
    async def broken(api: DemoApi) -> Observed:
        raise DemoHttpError("GET", "/api/state", 503, "unavailable")

    async def fine(api: DemoApi) -> Observed:
        return {"answer": 42, "live link": SKIPPED}

    runs = await rehearse(api_for(lambda r: envelope({})), {"monsoon": broken, "buy_cover": fine})
    expected = {"monsoon": {"answer": 1}, "buy_cover": {"answer": 42, "live link": True, "missing": "x"}}
    rows = compare(runs, expected)
    assert [(r.scenario, r.check, r.status) for r in rows] == [
        ("monsoon", "flow completed", "FAIL"),
        ("monsoon", "answer", "FAIL"),
        ("buy_cover", "answer", "PASS"),
        ("buy_cover", "live link", "SKIP"),
        ("buy_cover", "missing", "FAIL"),
    ]
    assert rows[0].actual == "DemoHttpError: GET /api/state answered 503: unavailable"
    assert rows[4].actual == "<not observed>" and not all_passed(rows)
    table = render_table(rows).splitlines()
    assert table[-1] == "FAIL: 1 passed, 3 failed, 1 skipped"
    assert "expected 1 ; got <not observed>" in table[2]
    payload = json.loads(render_json(rows))
    assert payload["passed"] is False and payload["rows"][2] == {
        "scenario": "buy_cover",
        "check": "answer",
        "status": "PASS",
        "expected": 42,
        "actual": 42,
    }


def test_all_passed_needs_at_least_one_row_and_skips_are_not_failures() -> None:
    assert all_passed(()) is False
    rows = (CheckRow("s", "a", 1, 1, "PASS"), CheckRow("s", "b", True, SKIPPED, "SKIP"))
    assert all_passed(rows) is True
    assert render_table(rows).splitlines()[-1] == "PASS: 1 passed, 0 failed, 1 skipped"
    assert "(none)" in render_table((CheckRow("s", "empty", [], [], "PASS"),))


async def test_a_live_paytm_link_is_not_paid_by_the_rehearsal() -> None:
    """Paying a staging link needs a real payment: the premium checks are SKIP, not FAIL."""
    live = {"id": "PR-1", "link_id": "L1", "link_url": "https://paytm.me/abc"}
    answers = {
        "/api/replay/load": {},
        "/api/replay/seek": {"label": "Mumbai · buy cover replay · 18:10 · simulated"},
        "/api/state": {"demo_merchant_id": "S-0907", "zones": [{"zone_id": "Z3", "alert": None}]},
        "/api/merchants/S-0907": {"covered": False},
        "/api/merchants/S-0907/messages": [{"text_en": "hi"}, {"text_en": "blocked"}],
        "/api/premium/link": {
            "quote": {"outcome": "BLOCKED", "starts_on": "2025-08-25", "first_payment_label": "₹426"},
            "premium": live,
        },
        "/api/audit/verify": {"valid": True},
        "/api/session": {"officer_token": "t"},
    }
    observed = await buy_cover(api_for(lambda r: envelope(answers[r.url.path])))
    assert observed["premium paid"] == observed["cover after payment"] == SKIPPED
    assert observed["premium confirmation"] == SKIPPED and observed["premium link"] is True
    assert flow_names() == ("monsoon", "illness", "illness_mismatch", "buy_cover")
