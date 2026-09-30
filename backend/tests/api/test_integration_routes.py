"""Every §19 route on the REAL AppState (small city + quick model), validated against §19.2 schemas.

The fake-state tests pin the HTTP contract route by route; these prove the real integration core
(``chhatri.replay``) satisfies it: `create_app(state=AppState(static))` with the SPEC §24.6 lifespan,
a monsoon replay driven to 17:10, and every GET answering its schema (SPEC §19, §19.2, §24.6).
"""

from __future__ import annotations

from typing import Any, Final

from httpx import AsyncClient
from pydantic import BaseModel

from chhatri.api.schemas import (
    AuditEntry,
    AuditVerify,
    Case,
    ClockState,
    Decision,
    FeatureCollection,
    Health,
    IntegrationStatus,
    MerchantDetail,
    MerchantSummary,
    Message,
    OfficerActionResult,
    Payout,
    PolicyView,
    PreflightItem,
    Session,
    StateSnapshot,
    ZonePanel,
)
from tests.api.helpers import data_of, error_of, list_of

ANIL: Final = "S-0142"
MONSOON_DAY: Final = "2025-08-19"
TRIGGERED: Final = ("Z3", "Z7", "Z12")

SINGLE: Final[tuple[tuple[str, type[BaseModel]], ...]] = (
    ("/api/health", Health),
    ("/api/session", Session),
    ("/api/geo/zones", FeatureCollection),
    ("/api/geo/hexes", FeatureCollection),
    ("/api/state", StateSnapshot),
    ("/api/zones/Z7", ZonePanel),
    ("/api/zones/Z9", ZonePanel),
    (f"/api/merchants/{ANIL}", MerchantDetail),
    ("/api/audit/verify", AuditVerify),
    ("/api/policy", PolicyView),
)
LISTS: Final[tuple[tuple[str, type[BaseModel]], ...]] = (
    ("/api/integrations", IntegrationStatus),
    ("/api/preflight", PreflightItem),
    ("/api/merchants?zone_id=Z7", MerchantSummary),
    (f"/api/merchants/{ANIL}/messages", Message),
    ("/api/cases", Case),
    (f"/api/payouts?zone_id=Z7&date={MONSOON_DAY}", Payout),
    ("/api/audit?after=0&limit=500", AuditEntry),
)


async def load(http: AsyncClient, scenario: str, to: str) -> ClockState:
    data_of(await http.post("/api/replay/load", json={"scenario": scenario}), ClockState)
    return data_of(await http.post("/api/replay/seek", json={"to": to}), ClockState)


async def test_every_get_route_answers_its_schema_after_the_storm(real_client: AsyncClient) -> None:
    clock = await load(real_client, "monsoon", "17:10")
    assert (clock.now, clock.running, clock.label) == (
        "2025-08-19T17:10:00+05:30",
        False,
        "Mumbai · monsoon replay · 17:10 · simulated",
    )
    for path, model in SINGLE:
        data_of(await real_client.get(path), model)
    for path, model in LISTS:
        items, meta = list_of(await real_client.get(path), model)
        assert meta.total >= len(items)
    state = data_of(await real_client.get("/api/state"), StateSnapshot)
    assert sorted((t.zone_id for t in state.triggers), key=lambda z: int(z[1:])) == list(TRIGGERED)
    assert state.kpis.zones_triggered == 3 and state.kpis.trigger_to_money_min == 4
    assert state.demo_merchant_id == ANIL and state.rain_band is not None  # SPEC §17.2 rain 14:00-17:00+
    assert {f.properties["id"] for f in state.rain_band.features} <= set(TRIGGERED)
    payouts, meta = list_of(await real_client.get(f"/api/payouts?zone_id=Z7&date={MONSOON_DAY}"), Payout)
    assert meta.total == len(payouts) == 46 and {p.credited_at for p in payouts} == {
        "2025-08-19T17:04:00+05:30"
    }
    decision_id = payouts[0].decision_id
    decision = data_of(await real_client.get(f"/api/decisions/{decision_id}"), Decision)
    assert decision.outcome == "APPROVED" and decision.explanation is not None


async def test_the_rain_band_covers_the_alerted_wards_while_it_rains(real_client: AsyncClient) -> None:
    await load(real_client, "monsoon", "15:30")
    state = data_of(await real_client.get("/api/state"), StateSnapshot)
    assert state.rain_band is not None
    assert {f.properties["id"] for f in state.rain_band.features} == set(TRIGGERED)
    hexes = state.hexes
    assert hexes and all(value is None or 0 <= value <= 1000 for value in hexes.values())
    z7 = next(z for z in state.zones if z.zone_id == "Z7")
    assert z7.status == "watch" and z7.alert is not None and z7.alert.id == "A-20250818-01"


async def test_voice_note_media_is_served_back(real_client: AsyncClient) -> None:
    await load(real_client, "monsoon", "17:10")
    voice, _ = list_of(
        await real_client.post(f"/api/merchants/{ANIL}/voice-demo", json={"key": "why"}), Message
    )
    assert voice[0].kind == "VOICE" and voice[0].audio_url is not None
    media = await real_client.get(voice[0].audio_url)
    assert media.status_code == 200 and media.headers["content-type"].startswith("audio/")
    assert media.headers["cache-control"] == "no-store"
    assert "Your usual Tuesday" in (voice[1].text_en or "")


async def test_nothing_loaded_is_a_409_and_preflight_says_so(real_client: AsyncClient) -> None:
    error_of(await real_client.get("/api/state"), 409, "no_scenario")
    rows, _ = list_of(await real_client.get("/api/preflight"), PreflightItem)
    by_name = {row.name: row for row in rows}
    assert by_name["model"].ok is True and by_name["scenario"].ok is False
    assert by_name["backtest"].ok is False  # the small static context has no report
    error_of(await real_client.get("/api/backtest"), 404, "not_found")


async def test_unknown_scenario_is_422(real_client: AsyncClient) -> None:
    error = error_of(
        await real_client.post("/api/replay/load", json={"scenario": "tsunami"}), 422, "validation_error"
    )
    assert "scenario" in error.fields


async def test_dispute_case_and_the_officer_closes_it(
    real_client: AsyncClient, real_officer: dict[str, str]
) -> None:
    await load(real_client, "monsoon", "17:10")
    reply, _ = list_of(
        await real_client.post(f"/api/merchants/{ANIL}/messages", json={"text": "मेरा नुकसान ज़्यादा हुआ।"}),
        Message,
    )
    assert [m.kind for m in reply] == ["TEXT", "TEXT", "CASE_CHIP"] and reply[2].meta.case_id == "C-2291"
    case = data_of(await real_client.get("/api/cases/C-2291"), Case)
    assert (case.kind, case.status, case.merchant_name) == ("DISPUTE", "OPEN", "Anil's Tea Stall")
    assert case.evidence.expected_vs_actual and case.decision is not None
    error_of(await real_client.post("/api/cases/C-2291/approve", json={"note": "x"}), 401, "unauthorized")
    wrong = {"Authorization": "Bearer nope"}
    error_of(
        await real_client.post("/api/cases/C-2291/approve", json={"note": "x"}, headers=wrong),
        403,
        "forbidden",
    )
    closed = data_of(
        await real_client.post(
            "/api/cases/C-2291/decline", json={"note": "numbers are right"}, headers=real_officer
        ),
        OfficerActionResult,
    )
    assert closed.case.status == "CLOSED"
    again = await real_client.post("/api/cases/C-2291/approve", json={"note": "x"}, headers=real_officer)
    error_of(again, 409, "conflict")
    error_of(
        await real_client.post("/api/cases/C-9999/approve", json={"note": "x"}, headers=real_officer),
        404,
        "not_found",
    )
    messages, _ = list_of(await real_client.get(f"/api/merchants/{ANIL}/messages"), Message)
    assert "our team reviewed your claim" in (messages[-1].text_en or "")


async def test_n8n_callback_for_a_step_already_run_in_process_is_skipped(
    real_client: AsyncClient, real_state: Any
) -> None:
    await load(real_client, "monsoon", "17:05")
    payouts, _ = list_of(await real_client.get(f"/api/payouts?zone_id=Z7&date={MONSOON_DAY}"), Payout)
    payload = {"decision_id": payouts[0].decision_id, "merchant_id": payouts[0].merchant_id}
    body = {"run_id": f"payout:{payload['decision_id']}", "workflow": "payout", "step": "credit_payout"}
    secret = {"X-Chhatri-Secret": real_state.static.settings.chhatri_internal_secret.get_secret_value()}
    response = await real_client.post(
        "/internal/workflows/credit_payout", json=body | {"payload": payload}, headers=secret
    )
    assert response.status_code == 200 and response.json()["data"] == {
        "step": "credit_payout",
        "status": "skipped",
    }
    bad = await real_client.post(
        "/internal/workflows/credit_payout",
        json=body | {"payload": payload | {"merchant_id": "S-0907"}},
        headers=secret,
    )
    error_of(bad, 409, "conflict")
    error_of(
        await real_client.post("/internal/workflows/credit_payout", json=body | {"payload": payload}),
        401,
        "unauthorized",
    )


async def test_a_reloaded_scenario_accepts_its_premium_payment_again(
    real_client: AsyncClient, real_officer: dict[str, str]
) -> None:
    """SPEC §3: a load starts afresh, so the same simulated link and txn id pay again after a reload."""
    for _ in range(2):
        await load(real_client, "buy_cover", "18:10")
        link = await real_client.post(
            "/api/premium/link", json={"merchant_id": "S-0907"}, headers=real_officer
        )
        premium = link.json()["data"]["premium"]
        form = {"linkId": premium["link_id"], "STATUS": "TXN_SUCCESS", "TXNID": "DEMO-TXN-1"}
        paid = await real_client.post("/api/webhooks/paytm", data=form)
        assert paid.json()["data"]["status"] == "paid"
        again = await real_client.post("/api/webhooks/paytm", data=form)
        assert again.json()["data"]["status"] == "duplicate"
        ramesh = data_of(await real_client.get("/api/merchants/S-0907"), MerchantDetail)
        assert ramesh.cover is not None and (ramesh.cover.status, ramesh.cover.starts_on) == (
            "WAITING",
            "2025-08-25",
        )
