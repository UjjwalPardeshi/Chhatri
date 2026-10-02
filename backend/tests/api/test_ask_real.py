"""Ask Chhatri and voice on the REAL runtime (small city, monsoon replay): the wiring the doubles cannot prove."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from chhatri.api.app import create_app
from chhatri.api.schemas.ask import AskResponse, SttResponse, TtsResponse
from chhatri.events import EventBus
from chhatri.replay.state import AppState
from chhatri.replay.static import StaticContext
from tests.api.helpers import data_of, error_of
from tests.replay import small_world
from tests.replay.helpers import make_static, offline_settings

ANIL = "S-0142"
SETTINGS: dict[str, Any] = {
    "chhatri_features": "n2_ask_chhatri,n4_voice",
    "google_api_key": None,
    "gemini_model": "",
    "chhatri_data_is_synthetic": True,
}


@pytest.fixture(scope="module")
def ask_static(tmp_path_factory: pytest.TempPathFactory) -> StaticContext:
    var_dir = tmp_path_factory.mktemp("ask-real")
    settings = offline_settings(var_dir, **SETTINGS)
    return make_static(settings, small_world.small_city(), small_world.small_model(), var_dir / "artifacts")


@pytest.fixture
async def http(ask_static: StaticContext) -> AsyncIterator[AsyncClient]:
    state = AppState(ask_static, bus=EventBus(history_size=50_000))
    app: FastAPI = create_app(ask_static.settings, state=state)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t", timeout=60.0) as client,
    ):
        await client.post("/api/replay/load", json={"scenario": "monsoon"})
        yield client


async def seek(http: AsyncClient, to: str) -> None:
    assert (await http.post("/api/replay/seek", json={"to": to})).status_code == 200


async def ask(http: AsyncClient, question: str, lang: str = "en") -> Any:
    return data_of(
        await http.post(f"/api/merchants/{ANIL}/ask", json={"question": question, "lang": lang}), AskResponse
    )


async def test_with_no_keys_an_unknown_question_is_a_simulated_template_and_is_audited(
    http: AsyncClient,
) -> None:
    data = await ask(http, "What is the yearly limit?")
    assert (data.mode, data.provider, data.fallback_reason) == ("SIMULATED", "template", "NO_KEY")
    assert data.next_action.kind == "ASK_AGAIN" and data.answer.startswith("I'm Chhatri.")
    audit = (await http.get("/api/audit", params={"limit": 500})).json()["data"]
    entries = [e for e in audit if e["action"] == "ask.answered"]
    assert entries and entries[-1]["subject_id"] == data.ask_id
    assert (
        "yearly limit" not in str(entries[-1]["data"])
        and (await http.get("/api/audit/verify")).json()["data"]["valid"]
    )


async def test_why_after_the_payout_is_answered_by_the_rules_from_the_real_decision(
    http: AsyncClient,
) -> None:
    await seek(http, "17:10")
    data = await ask(http, "Why did I get this amount?")
    assert (data.mode, data.provider, data.intent) == ("LIVE", "rules", "WHY_AMOUNT")
    assert (
        data.answer.startswith("Your usual Tuesday: ₹") and "Chhatri pays half the lost sales." in data.answer
    )
    assert [c.id for c in data.clauses] == ["C4.1", "C2"]
    keys = [f.key for f in data.facts_used]
    assert keys == ["decision.latest.expected_day", "decision.latest.drop_pct", "decision.latest.share_pct"]
    kinds = {s.kind for f in data.facts_used for s in f.sources}
    assert "FORECAST" in kinds and all(
        s.origin in {"SIMULATED", "CONFIG", "LIVE"} for f in data.facts_used for s in f.sources
    )
    assert data.next_action.kind == "SEE_CLAIM"


async def test_a_dispute_asked_here_opens_the_case_by_rule(http: AsyncClient) -> None:
    await seek(http, "17:10")
    data = await ask(http, "मेरा नुकसान ज़्यादा हुआ", "hi")
    assert data.intent == "DISPUTE_AMOUNT" and data.case_id and data.next_action.kind == "TRACK_CASE"
    again = await ask(http, "मेरा नुकसान ज़्यादा हुआ", "hi")
    assert again.case_id == data.case_id  # a second dispute for the same decision returns the open case


async def test_the_chat_route_sends_unknown_text_through_ask(http: AsyncClient) -> None:
    sent = await http.post(f"/api/merchants/{ANIL}/messages", json={"text": "What is the yearly limit?"})
    items = sent.json()["data"]
    assert (
        len(items) == 2
        and items[-1]["meta"]["provider"] == "template"
        and items[-1]["meta"]["mode"] == "SIMULATED"
    )
    assert items[-1]["meta"]["next_action"] == "ASK_AGAIN" and items[-1]["meta"]["scam_warning"] is False


async def test_a_voice_question_flows_from_stt_to_ask_to_tts(http: AsyncClient) -> None:
    stt = data_of(
        await http.post(
            "/api/voice/stt",
            json={
                "merchant_id": ANIL,
                "transcript": "₹1,500 कब मिलेंगे",
                "source": "browser",
                "language_code": "hi-IN",
            },
        ),
        SttResponse,
    )
    assert stt.mentions[0].value == "₹1,500" and stt.provider == "browser"
    body = {"question": stt.transcript, "lang": "hi", "stt_id": stt.stt_id}
    error_of(await http.post(f"/api/merchants/{ANIL}/ask", json=body), 409, "mentions_unconfirmed")
    answered = data_of(
        await http.post(f"/api/merchants/{ANIL}/ask", json={**body, "confirmed_mentions": ["m1"]}),
        AskResponse,
    )
    spoken = data_of(
        await http.post(
            "/api/voice/tts", json={"merchant_id": ANIL, "ask_id": answered.ask_id, "lang": "hi"}
        ),
        TtsResponse,
    )
    assert spoken.audio_url is None and spoken.provider == "browser"
    actions = [e["action"] for e in (await http.get("/api/audit", params={"limit": 500})).json()["data"]]
    assert {"voice.transcribed", "voice.confirmed", "ask.answered"} <= set(actions)


async def test_a_reload_starts_new_ids_and_forgets_earlier_asks(http: AsyncClient) -> None:
    first = await ask(http, "hello")
    assert first.ask_id == "AQ-000001"
    await http.post("/api/replay/load", json={"scenario": "monsoon"})
    assert (await ask(http, "hello")).ask_id == "AQ-000001"
    error_of(
        await http.post("/api/voice/tts", json={"merchant_id": ANIL, "ask_id": "AQ-000009", "lang": "hi"}),
        404,
        "not_found",
    )
