"""End-to-end through HTTP with the real engine (slow: needs `make data` artefacts; SPEC §13.6, §17.2, §22).

Each test starts the real app (``create_app`` lifespan: ``load_static`` + monsoon), drives the deck
story through the §19 routes only, and validates every response against ``chhatri.api.schemas``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from chhatri.api.app import create_app
from chhatri.api.schemas import (
    AuditVerify,
    Case,
    ClockState,
    Decision,
    FeatureCollection,
    MerchantDetail,
    Message,
    OfficerActionResult,
    PolicyView,
    PremiumLinkResult,
    Session,
    StateSnapshot,
    ZonePanel,
)
from tests.api.canned import Z9_EXPLANATION
from tests.api.fakes import make_settings
from tests.api.helpers import data_of, list_of

pytestmark = pytest.mark.slow

OFFLINE = {
    "whatsapp_access_token": None,
    "whatsapp_phone_number_id": None,
    "whatsapp_app_secret": None,
    "whatsapp_verify_token": None,
    "whatsapp_demo_recipient": None,
}


@pytest.fixture
async def http() -> AsyncIterator[AsyncClient]:
    app = create_app(make_settings(**OFFLINE))
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://t") as client,
    ):
        yield client


async def load(http: AsyncClient, scenario: str, seek: str) -> None:
    data_of(await http.post("/api/replay/load", json={"scenario": scenario}), ClockState)
    clock = data_of(await http.post("/api/replay/seek", json={"to": seek}), ClockState)
    assert clock.label.endswith(f"· {seek} · simulated")


async def say(http: AsyncClient, merchant_id: str, key: str) -> list[Any]:
    items, _ = list_of(
        await http.post(f"/api/merchants/{merchant_id}/voice-demo", json={"key": key}), Message
    )
    return items


def english(messages: list[Any]) -> str:
    return " ".join(m.text_en or "" for m in messages)


async def test_monsoon_storm_through_the_api(http: AsyncClient) -> None:
    await load(http, "monsoon", "17:05")
    state = data_of(await http.get("/api/state"), StateSnapshot)
    assert (state.kpis.zones_triggered, state.kpis.shops_paid, state.kpis.trigger_to_money_min) == (3, 312, 4)
    assert {z.zone_id: z.index_pct for z in state.zones if z.zone_id in {"Z3", "Z7", "Z9", "Z12"}} == {
        "Z3": 38,
        "Z7": 37,
        "Z9": 61,
        "Z12": 47,
    }
    assert state.explanations["Z9"] == Z9_EXPLANATION
    panel = data_of(await http.get("/api/zones/Z7"), ZonePanel)
    assert [row.value for row in panel.rows] == [
        "Red alert from 14:00",
        "37% of expected for 3 hours",
        "46 of 46 prepaid",
        "17:04, with the settlement",
        "₹58,900 · instalments paused",
    ]
    anil = data_of(await http.get("/api/merchants/S-0142"), MerchantDetail)
    assert [(p.amount_label, p.credited_at) for p in anil.payouts] == [
        ("₹1,380", "2025-08-19T17:04:00+05:30")
    ]
    assert data_of(await http.get("/api/audit/verify"), AuditVerify).valid is True
    for path in ("/api/geo/zones", "/api/geo/hexes"):
        data_of(await http.get(path), FeatureCollection)
    data_of(await http.get("/api/policy"), PolicyView)
    why = english(await say(http, "S-0142", "why"))
    assert "Your usual Tuesday: ₹4,380. Your area fell 63%. Chhatri pays half the lost sales." in why
    dispute = await say(http, "S-0142", "dispute")
    assert "Sent to a claims officer · case C-2291" in english(dispute)
    cases, _ = list_of(await http.get("/api/cases"), Case)
    assert [(c.id, c.kind) for c in cases] == [("C-2291", "DISPUTE")]


async def test_illness_is_paid_the_same_day(http: AsyncClient) -> None:
    await load(http, "illness", "11:21")
    assert "Please send one photo of the hospital slip." in english(await say(http, "S-0142", "ill"))
    photo, _ = list_of(await http.post("/api/merchants/S-0142/photo", json={}), Message)
    assert "your claim is approved. ₹1,500 credited" in english(photo)
    anil = data_of(await http.get("/api/merchants/S-0142"), MerchantDetail)
    assert [d.outcome for d in anil.decisions][-1] == "APPROVED"


async def test_mismatched_slip_goes_to_a_human_who_approves(http: AsyncClient) -> None:
    await load(http, "illness_mismatch", "11:21")
    await say(http, "S-0142", "ill")
    photo, _ = list_of(await http.post("/api/merchants/S-0142/photo", json={}), Message)
    assert "The name on the slip doesn't match your KYC" in english(photo)
    case = list_of(await http.get("/api/cases?status=OPEN"), Case)[0][0]
    assert (case.id, case.kind, case.decision.outcome if case.decision else None) == (
        "C-2291",
        "PERSONAL_CLAIM_REVIEW",
        "REFERRED",
    )
    token = data_of(await http.get("/api/session"), Session).officer_token
    result = data_of(
        await http.post(
            f"/api/cases/{case.id}/approve",
            json={"note": "same person"},
            headers={"Authorization": f"Bearer {token}"},
        ),
        OfficerActionResult,
    )
    assert (result.decision.outcome, result.decision.amount_label, result.case.status) == (
        "APPROVED",
        "₹1,500",
        "APPROVED",
    )
    data_of(await http.get(f"/api/decisions/{result.decision.id}"), Decision)


async def test_cover_during_an_alert_is_blocked(http: AsyncClient) -> None:
    await load(http, "buy_cover", "18:10")
    reply = english(await say(http, "S-0907", "cover"))
    assert "New cover starts after the waiting period" in reply
    token = data_of(await http.get("/api/session"), Session).officer_token
    link = data_of(
        await http.post(
            "/api/premium/link", json={"merchant_id": "S-0907"}, headers={"Authorization": f"Bearer {token}"}
        ),
        PremiumLinkResult,
    )
    assert (link.quote.outcome, link.quote.starts_on) == ("BLOCKED", "2025-08-25")
    assert link.premium is not None and link.premium.link_url
