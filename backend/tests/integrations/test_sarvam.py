"""Live Sarvam STT/TTS/chat against a fake SDK client (SPEC §14.1: exact calls and parameters)."""

from __future__ import annotations

import base64
import threading
import time
from types import SimpleNamespace

import httpx
import pytest

from chhatri.domain.enums import Language
from chhatri.integrations import sarvam
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.sarvam_chat import check_schema, parse_json_reply
from chhatri.integrations.sarvam_client import SarvamCaller, default_client_factory, field_of, map_sdk_error
from chhatri.integrations.sarvam_speech import audio_codec_for, stt_language

from .conftest import SleepRecorder, no_sleep
from .fake_sarvam import ScriptedCall, api_error, fake_client

INTENT_SCHEMA = {
    "type": "object",
    "properties": {"intent": {"type": "string", "enum": ["WHY_AMOUNT", "UNKNOWN"]}},
    "required": ["intent"],
}


def caller(name: str, client: object, sleep=no_sleep) -> SarvamCaller:  # type: ignore[no-untyped-def]
    return SarvamCaller(name, lambda: client, sleep=sleep)


def stt_with(outcomes: list[object], sleep=no_sleep) -> tuple[sarvam.LiveSarvamSTT, ScriptedCall]:  # type: ignore[no-untyped-def]
    call = ScriptedCall(outcomes)
    client = fake_client(speech_to_text={"transcribe": call})
    return sarvam.LiveSarvamSTT("key", caller=caller("sarvam_stt", client, sleep)), call


async def test_stt_uses_exact_sdk_call() -> None:
    response = SimpleNamespace(
        transcript=" मुझे इतने ही पैसे क्यों मिले? ", language_code="hi-IN", language_probability=0.97
    )
    stt, call = stt_with([response])
    result = await stt.transcribe(b"OggS...", "audio/ogg; codecs=opus", language_hint="hi-IN")
    assert result.text == "मुझे इतने ही पैसे क्यों मिले?"
    assert (result.language_code, result.confidence, result.source) == ("hi-IN", 0.97, "sarvam:saaras:v3")
    _, kwargs = call.calls[0]
    assert kwargs["file"] == ("voice.ogg", b"OggS...", "audio/ogg; codecs=opus")
    assert kwargs["model"] == "saaras:v3" and kwargs["mode"] == "transcribe"
    assert kwargs["language_code"] == "hi-IN" and kwargs["input_audio_codec"] == "ogg"
    assert kwargs["request_options"] == {"timeout_in_seconds": 10, "max_retries": 0}


async def test_stt_detects_language_when_hint_is_not_a_code() -> None:
    stt, call = stt_with([{"transcript": "hello", "language_code": None, "language_probability": None}])
    result = await stt.transcribe(b"webm", "audio/webm", language_hint="why")
    assert call.calls[0][1]["language_code"] == "unknown"
    assert call.calls[0][1]["input_audio_codec"] == "webm"
    assert result.confidence is None


async def test_stt_retries_429_then_succeeds(sleeps: SleepRecorder) -> None:
    stt, call = stt_with([api_error(429), api_error(503), {"transcript": "ok"}], sleep=sleeps)
    assert (await stt.transcribe(b"a", "audio/ogg")).text == "ok"
    assert len(call.calls) == 3 and sleeps.delays == [0.5, 1.0]


async def test_stt_gives_up_after_three_attempts(sleeps: SleepRecorder) -> None:
    stt, call = stt_with([api_error(500)], sleep=sleeps)
    with pytest.raises(IntegrationError, match="provider error"):
        await stt.transcribe(b"a", "audio/ogg")
    assert len(call.calls) == 3


async def test_stt_auth_failure_is_not_retried_and_is_safe(sleeps: SleepRecorder) -> None:
    stt, call = stt_with([api_error(403)], sleep=sleeps)
    with pytest.raises(IntegrationError) as info:
        await stt.transcribe(b"a", "audio/ogg")
    assert len(call.calls) == 1
    assert "authentication failed" in info.value.safe_message and "sk_live" not in str(info.value)


async def test_stt_rejects_bad_input_and_bad_response() -> None:
    stt, _ = stt_with([{"no": "transcript"}])
    with pytest.raises(IntegrationError, match="empty audio"):
        await stt.transcribe(b"", "audio/ogg")
    with pytest.raises(IntegrationError, match="unsupported audio"):
        await stt.transcribe(b"x", "application/pdf")
    with pytest.raises(IntegrationError, match="no transcript"):
        await stt.transcribe(b"x", "audio/mpeg")


async def test_sdk_call_is_bounded_by_timeout() -> None:
    release = threading.Event()

    def slow(*_: object, **__: object) -> object:
        release.wait(2)
        return {"transcript": "late"}

    client = fake_client(speech_to_text={"transcribe": slow})
    stt = sarvam.LiveSarvamSTT(
        "key", caller=SarvamCaller("sarvam_stt", lambda: client, timeout_s=0.05, sleep=no_sleep)
    )
    started = time.monotonic()
    with pytest.raises(IntegrationError, match="timed out"):
        await stt.transcribe(b"x", "audio/ogg")
    release.set()
    assert time.monotonic() - started < 1.5


def test_codec_and_language_helpers() -> None:
    assert audio_codec_for("audio/x-m4a") == "x-m4a"
    assert audio_codec_for("AUDIO/WAV") == "wav"
    assert stt_language("mr-IN") == "mr-IN"
    assert stt_language(None) == "unknown"


def test_error_mapping() -> None:
    assert map_sdk_error("s", TimeoutError()).safe_message == "request timed out"
    assert map_sdk_error("s", httpx.ConnectError("x")).safe_message == "transport error (ConnectError)"
    assert map_sdk_error("s", api_error(429)).retryable is True
    assert map_sdk_error("s", KeyError("k")).safe_message == "unexpected failure (KeyError)"


def test_client_factory_failures_are_safe() -> None:
    def boom() -> object:
        raise RuntimeError("bad key sk_live_x")

    with pytest.raises(IntegrationError, match="could not create"):
        SarvamCaller("s", boom).client()
    client = default_client_factory("test-key", 10)()
    assert type(client).__name__ == "SarvamAI"


def test_field_of_reads_models_and_mappings() -> None:
    assert field_of({"a": 1}, "a") == 1
    assert field_of(SimpleNamespace(a=2), "a") == 2
    assert field_of(object(), "a") is None


def test_constructors_validate() -> None:
    for cls in (
        sarvam.LiveSarvamSTT,
        sarvam.LiveSarvamTTS,
        sarvam.LiveSarvamChat,
        sarvam.LiveSarvamSlipReader,
    ):
        with pytest.raises(ValueError):
            cls("")
    with pytest.raises(ValueError):
        sarvam.LiveSarvamChat("k", max_tokens=0)


def tts_with(outcomes: list[object]) -> tuple[sarvam.LiveSarvamTTS, ScriptedCall]:
    call = ScriptedCall(outcomes)
    client = fake_client(text_to_speech={"convert": call})
    return sarvam.LiveSarvamTTS("key", speaker="Ritu", caller=caller("sarvam_tts", client)), call


async def test_tts_browser_mp3_and_whatsapp_opus() -> None:
    audio = base64.b64encode(b"ID3audio").decode()
    tts, call = tts_with([SimpleNamespace(audios=[audio])])
    browser = await tts.synthesize("Paytm par ₹1,380 prapt hue", Language.HI)
    whatsapp = await tts.synthesize("नमस्ते", Language.HI, for_whatsapp=True)
    assert browser.audio == b"ID3audio" and browser.mime_type == "audio/mpeg"
    assert whatsapp.mime_type == "audio/ogg" and whatsapp.source == "sarvam:bulbul:v3"
    first, second = call.calls[0][1], call.calls[1][1]
    assert first["language_code"] == "hi-IN" and first["model"] == "bulbul:v3"
    assert first["speaker"] == "ritu" and first["pace"] == 1.0 and first["output_audio_codec"] == "mp3"
    assert second["output_audio_codec"] == "opus"
    assert "pitch" not in first and "loudness" not in first


async def test_tts_validates_text_and_audio() -> None:
    tts, _ = tts_with([SimpleNamespace(audios=[])])
    with pytest.raises(IntegrationError, match="empty text"):
        await tts.synthesize("  ", Language.EN)
    with pytest.raises(IntegrationError, match="2500"):
        await tts.synthesize("a" * 2501, Language.EN)
    with pytest.raises(IntegrationError, match="no audio"):
        await tts.synthesize("hi", Language.EN)
    bad, _ = tts_with([{"audios": ["***not base64***"]}])
    with pytest.raises(IntegrationError, match="base64"):
        await bad.synthesize("hi", Language.MR)
    empty, _ = tts_with([{"audios": [""]}])
    with pytest.raises(IntegrationError, match="empty audio"):
        await empty.synthesize("hi", Language.EN)


def chat_with(outcomes: list[object]) -> tuple[sarvam.LiveSarvamChat, ScriptedCall]:
    call = ScriptedCall(outcomes)
    client = fake_client(chat={"completions": call})
    return sarvam.LiveSarvamChat("key", caller=caller("sarvam_chat", client)), call


def reply(content: object) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


async def test_chat_uses_json_schema_response_format() -> None:
    chat, call = chat_with([reply('{"intent": "WHY_AMOUNT"}')])
    result = await chat.complete_json("sys", "user", INTENT_SCHEMA, schema_name="intent")
    assert result == {"intent": "WHY_AMOUNT"}
    kwargs = call.calls[0][1]
    assert kwargs["model"] == "sarvam-105b" and kwargs["temperature"] == 0.1
    assert kwargs["messages"] == [{"role": "system", "content": "sys"}, {"role": "user", "content": "user"}]
    assert kwargs["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "intent", "schema": INTENT_SCHEMA},
    }
    assert kwargs["max_tokens"] == 512


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (reply('{"intent": "APPROVE_PAYOUT"}'), "did not match"),
        (reply("not json"), "not JSON"),
        (reply("[1]"), "not a JSON object"),
        (reply(None), "empty"),
        (SimpleNamespace(choices=[]), "no choices"),
        (SimpleNamespace(choices=[SimpleNamespace(message=None)]), "no message"),
    ],
)
async def test_chat_rejects_anything_off_schema(response: object, message: str) -> None:
    chat, _ = chat_with([response])
    with pytest.raises(IntegrationError, match=message):
        await chat.complete_json("s", "u", INTENT_SCHEMA, schema_name="intent")


async def test_chat_validates_schema_before_calling() -> None:
    chat, call = chat_with([reply("{}")])
    with pytest.raises(ValueError):
        await chat.complete_json("s", "u", {"type": "nonsense"}, schema_name="x")
    with pytest.raises(ValueError):
        await chat.complete_json("s", "u", INTENT_SCHEMA, schema_name=" ")
    assert call.calls == []
    check_schema(INTENT_SCHEMA)
    assert parse_json_reply('{"intent": "UNKNOWN"}', INTENT_SCHEMA) == {"intent": "UNKNOWN"}


async def test_integration_errors_from_the_call_pass_through() -> None:
    def refuse(_: object) -> object:
        raise IntegrationError("sarvam_stt", "already safe")

    with pytest.raises(IntegrationError, match="already safe"):
        await SarvamCaller("sarvam_stt", lambda: object(), sleep=no_sleep).call(refuse)
