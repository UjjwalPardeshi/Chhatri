"""POST /api/voice/stt and /api/voice/tts: flag, uploads, chips, labels, errors and limits (data-model 5.11)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient

from chhatri.api.schemas.ask import SttResponse, TtsResponse
from chhatri.integrations.base import SynthesizedAudio
from tests.api import media_samples as media
from tests.api.helpers import data_of, error_of
from tests.ask.api_fixtures import GOOD_REPLY, Rig, ScriptedChat, build_client, make_voice
from tests.ask.fakes import make_rig
from tests.ask.test_voice_service import SARVAM, FakeStt, FakeTts

BROWSER = {
    "merchant_id": "S-0142",
    "transcript": "डेढ़ हज़ार रुपये कब मिलेंगे",
    "source": "browser",
    "language_code": "hi-IN",
}


@pytest.fixture
def rig() -> Rig:
    return make_rig(ScriptedChat(GOOD_REPLY))


@pytest.fixture
async def client(rig: Rig) -> AsyncIterator[AsyncClient]:
    async for http in build_client(rig, make_voice(rig), features="n2_ask_chhatri,n4_voice"):
        yield http


async def test_a_browser_transcript_gives_the_documented_response(client: AsyncClient) -> None:
    data = data_of(await client.post("/api/voice/stt", json=BROWSER), SttResponse)
    assert (data.stt_id, data.transcript, data.language_code, data.language_probability) == (
        "ST-000001",
        "डेढ़ हज़ार रुपये कब मिलेंगे",
        "hi-IN",
        None,
    )
    assert data.duration_s is None
    assert [m.model_dump() for m in data.mentions] == [
        {"id": "m1", "kind": "amount", "heard": "डेढ़ हज़ार", "value": "₹1,500", "value_paise": 150000,
         "value_date": None, "chip_hi": "₹1,500 — सही है?", "chip_en": "₹1,500 — is that right?"}
    ]  # fmt: skip
    assert (data.mode, data.provider, data.model, data.fallback_reason, data.attempts) == (
        "SIMULATED",
        "browser",
        None,
        "NO_KEY",
        [],
    )


async def test_audio_is_validated_by_content_and_the_audio_is_not_kept(rig: Rig) -> None:
    voice = make_voice(rig, stt=FakeStt(SARVAM), live={"sarvam_stt"})
    async for http in build_client(rig, voice, features="n4_voice"):
        files = {"file": ("note.ogg", media.ogg_opus_bytes(3), "audio/ogg")}
        response = await http.post(
            "/api/voice/stt", data={"merchant_id": "S-0142", "lang_hint": "hi-IN"}, files=files
        )
    data = data_of(response, SttResponse)
    assert (data.mode, data.provider, data.model) == ("LIVE", "sarvam", "saaras:v3")
    assert data.duration_s is not None and 2.5 < data.duration_s < 3.5
    assert data.mentions[0].value == "₹1,500"


@pytest.mark.parametrize(
    ("payload", "status", "code"),
    [
        (media.ogg_opus_bytes(45), 413, "payload_too_large"),
        (b"MZ\x90\x00 not audio", 415, "unsupported_media_type"),
        (b"OggS" + b"\x00" * (5 * 1024 * 1024), 413, "payload_too_large"),
    ],
    ids=["too-long", "not-audio", "too-big"],
)
async def test_audio_rejections(client: AsyncClient, payload: bytes, status: int, code: str) -> None:
    files = {"file": ("note.ogg", payload, "audio/ogg")}
    error_of(await client.post("/api/voice/stt", data={"merchant_id": "S-0142"}, files=files), status, code)


async def test_the_audio_form_needs_a_file_a_merchant_and_a_known_hint(client: AsyncClient) -> None:
    ok = {"file": ("n.ogg", media.ogg_opus_bytes(2), "audio/ogg")}
    assert (
        "file"
        in error_of(
            await client.post("/api/voice/stt", files={"merchant_id": (None, "S-0142")}),
            422,
            "validation_error",
        ).fields
    )
    assert (
        "merchant_id"
        in error_of(await client.post("/api/voice/stt", files=ok), 422, "validation_error").fields
    )
    bad_hint = await client.post(
        "/api/voice/stt", data={"merchant_id": "S-0142", "lang_hint": "fr-FR"}, files=ok
    )
    assert "lang_hint" in error_of(bad_hint, 422, "validation_error").fields
    unknown = await client.post("/api/voice/stt", data={"merchant_id": "S-9999"}, files=ok)
    error_of(unknown, 404, "not_found")


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({**BROWSER, "transcript": ""}, "transcript"),
        ({**BROWSER, "transcript": "a" * 501}, "transcript"),
        ({**BROWSER, "source": "sarvam"}, "source"),
        ({**BROWSER, "language_code": "hindi"}, "language_code"),
        ({**BROWSER, "merchant_id": "x"}, "merchant_id"),
        ({**BROWSER, "extra": 1}, "extra"),
    ],
)
async def test_invalid_browser_transcripts_are_422(
    client: AsyncClient, body: dict[str, object], field: str
) -> None:
    error = error_of(await client.post("/api/voice/stt", json=body), 422, "validation_error")
    assert error.fields and field in error.fields


async def test_a_body_that_is_neither_json_nor_multipart_is_415(client: AsyncClient) -> None:
    error_of(
        await client.post("/api/voice/stt", content=b"x", headers={"content-type": "text/plain"}),
        415,
        "unsupported_media_type",
    )


async def test_unknown_merchant_on_a_browser_transcript_is_404(client: AsyncClient) -> None:
    error_of(await client.post("/api/voice/stt", json={**BROWSER, "merchant_id": "S-9999"}), 404, "not_found")


async def test_with_the_flag_off_both_routes_do_not_exist(rig: Rig) -> None:
    async for http in build_client(rig, make_voice(rig), features="n2_ask_chhatri"):
        error_of(await http.post("/api/voice/stt", json=BROWSER), 404, "not_found")
        error_of(
            await http.post(
                "/api/voice/tts", json={"merchant_id": "S-0142", "ask_id": "AQ-000001", "lang": "hi"}
            ),
            404,
            "not_found",
        )


async def test_tts_voices_only_an_earlier_answer_of_the_same_merchant(client: AsyncClient) -> None:
    asked = await client.post(
        "/api/merchants/S-0142/ask", json={"question": "मुझे इतने ही पैसे क्यों मिले?", "lang": "hi"}
    )
    ask_id = asked.json()["data"]["ask_id"]
    data = data_of(
        await client.post("/api/voice/tts", json={"merchant_id": "S-0142", "ask_id": ask_id, "lang": "hi"}),
        TtsResponse,
    )
    assert (data.audio_url, data.mime_type, data.mode, data.provider, data.model, data.fallback_reason) == (
        None,
        None,
        "SIMULATED",
        "browser",
        None,
        "NO_KEY",
    )
    error_of(
        await client.post("/api/voice/tts", json={"merchant_id": "S-0907", "ask_id": ask_id, "lang": "hi"}),
        404,
        "not_found",
    )
    error_of(
        await client.post(
            "/api/voice/tts", json={"merchant_id": "S-0142", "ask_id": "AQ-000099", "lang": "hi"}
        ),
        404,
        "not_found",
    )
    error_of(
        await client.post("/api/voice/tts", json={"merchant_id": "S-9999", "ask_id": ask_id, "lang": "hi"}),
        404,
        "not_found",
    )


async def test_tts_with_sarvam_returns_a_media_url(rig: Rig) -> None:
    tts = FakeTts(SynthesizedAudio(b"mp3", "audio/mpeg", "sarvam"))
    voice = make_voice(rig, tts=tts, live={"sarvam_tts"})
    async for http in build_client(rig, voice, features="n2_ask_chhatri,n4_voice"):
        asked = await http.post("/api/merchants/S-0142/ask", json={"question": "hello", "lang": "en"})
        body = {"merchant_id": "S-0142", "ask_id": asked.json()["data"]["ask_id"], "lang": "en"}
        data = data_of(await http.post("/api/voice/tts", json=body), TtsResponse)
    assert data.audio_url and data.audio_url.startswith("/api/media/MD-") and data.mime_type == "audio/mpeg"
    assert (data.mode, data.provider, data.model) == ("LIVE", "sarvam", "bulbul:v3")


@pytest.mark.parametrize(
    "body",
    [
        {"merchant_id": "S-0142", "ask_id": "bad", "lang": "hi"},
        {"merchant_id": "S-0142", "ask_id": "AQ-000001", "lang": "mr"},
        {"merchant_id": "S-0142", "lang": "hi"},
    ],
)
async def test_invalid_tts_bodies_are_422(client: AsyncClient, body: dict[str, str]) -> None:
    error_of(await client.post("/api/voice/tts", json=body), 422, "validation_error")


async def test_the_uploads_group_limits_voice_to_20_a_minute(client: AsyncClient) -> None:
    for _ in range(20):
        assert (await client.post("/api/voice/stt", json=BROWSER)).status_code == 200
    limited = await client.post("/api/voice/stt", json=BROWSER)
    error_of(limited, 429, "rate_limited")
    assert int(limited.headers["retry-after"]) >= 1
