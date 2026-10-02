"""POST /api/merchants/{id}/ask: envelope, flag, errors, labels, voice chips and rate limit (data-model 5.2)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient

from chhatri.api.schemas.ask import AskResponse
from tests.api.helpers import data_of, error_of
from tests.ask.api_fixtures import GOOD_REPLY, Rig, ScriptedChat, build_client, make_voice
from tests.ask.fakes import TIMEOUT, make_rig

URL = "/api/merchants/S-0142/ask"
WHY = {"question": "मुझे इतने ही पैसे क्यों मिले?", "lang": "hi"}


@pytest.fixture
def rig() -> Rig:
    return make_rig(ScriptedChat(GOOD_REPLY))


@pytest.fixture
async def client(rig: Rig) -> AsyncIterator[AsyncClient]:
    async for http in build_client(rig, make_voice(rig), features="n2_ask_chhatri,n4_voice"):
        yield http


async def test_a_known_intent_is_answered_in_the_envelope(client: AsyncClient) -> None:
    response = await client.post(URL, json=WHY)
    data = data_of(response, AskResponse)
    assert set(response.json()) == {"ok", "data"} and response.json()["ok"] is True
    assert (data.ask_id, data.intent, data.intent_source, data.lang) == (
        "AQ-000001",
        "WHY_AMOUNT",
        "rules",
        "hi",
    )
    assert data.answer.startswith("आपका आम मंगलवार: ₹4,380") and data.answer_en.startswith(
        "Your usual Tuesday: ₹4,380"
    )
    assert [c.id for c in data.clauses] == ["C4.1", "C2"]
    assert data.facts_used[0].key == "decision.latest.expected_day" and data.facts_used[0].sources[0].ref
    assert data.next_action.kind == "SEE_CLAIM" and data.next_action.label_en == "See my claim"
    assert (data.mode, data.provider, data.model, data.fallback_reason, data.attempts) == (
        "LIVE",
        "rules",
        None,
        None,
        [],
    )
    assert (data.handoff, data.case_id, data.scam_warning) == (False, None, False)


async def test_a_model_answer_carries_the_label_with_every_attempt(rig: Rig) -> None:
    rig2 = make_rig(ScriptedChat(TIMEOUT), ScriptedChat(GOOD_REPLY))
    async for http in build_client(rig2, None, features="n2_ask_chhatri"):
        data = data_of(
            await http.post(URL, json={"question": "What is the yearly limit?", "lang": "en"}), AskResponse
        )
    assert (data.mode, data.provider, data.model, data.fallback_reason) == (
        "FALLBACK",
        "sarvam",
        "sarvam-105b",
        "TIMEOUT",
    )
    assert [(a.provider, a.outcome) for a in data.attempts] == [("gemini", "TIMEOUT"), ("sarvam", "OK")]
    assert data.answer == GOOD_REPLY["answer_en"] and data.clauses[0].title == "Annual limit"


async def test_with_the_flag_off_the_route_does_not_exist(rig: Rig) -> None:
    async for http in build_client(rig, None, features=""):
        error_of(await http.post(URL, json=WHY), 404, "not_found")
        error_of(await http.post(URL, json={}), 404, "not_found")


async def test_unknown_merchant_is_404_and_a_malformed_id_is_422(client: AsyncClient) -> None:
    assert (
        "S-9999"
        in error_of(await client.post("/api/merchants/S-9999/ask", json=WHY), 404, "not_found").message
    )
    error = error_of(await client.post("/api/merchants/S-12/ask", json=WHY), 422, "validation_error")
    assert error.fields and "merchant_id" in error.fields


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"question": ""}, "question"),
        ({"question": "   "}, "question"),
        ({"question": "a" * 501}, "question"),
        ({"question": "hi", "lang": "mr"}, "lang"),
        ({"question": "hi", "extra": 1}, "extra"),
        ({"question": "hi", "stt_id": "x"}, "stt_id"),
        ({"question": "hi", "confirmed_mentions": ["bad"]}, "confirmed_mentions.0"),
        ({}, "question"),
    ],
)
async def test_invalid_bodies_are_422_with_fields(
    client: AsyncClient, body: dict[str, object], field: str
) -> None:
    error = error_of(await client.post(URL, json=body), 422, "validation_error")
    assert error.fields and field in error.fields


async def test_the_question_is_trimmed(client: AsyncClient) -> None:
    data = data_of(await client.post(URL, json={"question": "  hello  ", "lang": "en"}), AskResponse)
    assert data.intent == "GREETING"


async def test_a_voice_question_with_an_unconfirmed_amount_is_409_and_answers_nothing(
    client: AsyncClient, rig: Rig
) -> None:
    stt = await client.post(
        "/api/voice/stt", json={"merchant_id": "S-0142", "transcript": "₹1,500 कब मिलेंगे", "source": "browser"}
    )
    stt_id = stt.json()["data"]["stt_id"]
    body = {"question": "₹1,500 कब मिलेंगे", "lang": "hi", "stt_id": stt_id}
    error = error_of(await client.post(URL, json=body), 409, "mentions_unconfirmed")
    assert error.fields == {"mentions": "m1"}
    assert rig.entries("ask.answered") == []
    data = data_of(await client.post(URL, json={**body, "confirmed_mentions": ["m1"]}), AskResponse)
    assert data.ask_id == "AQ-000001"
    assert len(rig.entries("voice.confirmed")) == 1


async def test_editing_the_text_to_add_an_amount_needs_a_new_chip(client: AsyncClient) -> None:
    stt = await client.post(
        "/api/voice/stt", json={"merchant_id": "S-0142", "transcript": "₹500", "source": "browser"}
    )
    body = {"question": "₹500 aur ₹700", "stt_id": stt.json()["data"]["stt_id"], "confirmed_mentions": ["m1"]}
    error = error_of(await client.post(URL, json=body), 409, "mentions_unconfirmed")
    assert error.fields == {"mentions": "m2"}


async def test_an_unknown_stt_id_is_422(client: AsyncClient) -> None:
    body = {"question": "hello", "stt_id": "ST-000077"}
    error = error_of(await client.post(URL, json=body), 422, "validation_error")
    assert error.fields and "stt_id" in error.fields


async def test_the_messages_group_limits_the_route_to_60_a_minute(client: AsyncClient) -> None:
    for _ in range(60):
        assert (await client.post(URL, json={"question": "hello", "lang": "en"})).status_code == 200
    limited = await client.post(URL, json={"question": "hello", "lang": "en"})
    error_of(limited, 429, "rate_limited")
    assert int(limited.headers["retry-after"]) >= 1


async def test_without_a_loaded_scenario_the_route_is_409() -> None:
    from httpx import ASGITransport

    from chhatri.api.app import create_app
    from tests.api.fakes import FakeAppState, make_settings

    state = FakeAppState(make_settings(chhatri_features="n2_ask_chhatri"))
    app = create_app(state.static.settings, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        error_of(await http.post(URL, json=WHY), 409, "no_scenario")
