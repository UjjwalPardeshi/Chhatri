"""The Bot API client against the fake Bot API: calls, validation, safe errors, retries, files."""

from __future__ import annotations

import logging

import httpx
import pytest

from chhatri.integrations.base import IntegrationError
from chhatri.integrations.retry import HttpStatusError, RetryPolicy
from chhatri.integrations.telegram_api import (
    MAX_FILE_BYTES,
    TelegramBotClient,
    inline_keyboard,
)
from tests.fake_telegram import BOT_USERNAME, TOKEN, FakeBotApi, text_update
from tests.integrations.conftest import SleepRecorder


def client_for(api: FakeBotApi, sleeps: SleepRecorder | None = None, **kwargs: object) -> TelegramBotClient:
    return TelegramBotClient(
        TOKEN,
        transport=api.transport(),
        sleep=sleeps or SleepRecorder(),
        **kwargs,  # type: ignore[arg-type]
    )


async def test_get_me_names_the_bot() -> None:
    bot = await client_for(FakeBotApi()).get_me()
    assert (bot.id, bot.username) == (42, BOT_USERNAME)


async def test_get_updates_sends_offset_and_long_poll_timeout_and_waits_longer_than_the_poll() -> None:
    api = FakeBotApi()
    api.queue(text_update(5, 1, "a"), text_update(6, 1, "b"))
    client = client_for(api)
    first = await client.get_updates(offset=None, timeout_s=25)
    assert [u["update_id"] for u in first] == [5, 6]
    second = await client.get_updates(offset=7, timeout_s=25)
    assert second == []
    call_one, call_two = api.sent("getUpdates")
    assert "offset" not in call_one.payload and call_one.payload["timeout"] == 25
    assert call_one.payload["allowed_updates"] == ["message", "callback_query"]
    assert call_two.payload["offset"] == 7
    assert call_two.timeout is not None and call_two.timeout > 25  # the HTTP timeout outlasts the long poll


async def test_get_updates_makes_a_single_attempt_so_the_poller_owns_the_backoff() -> None:
    api = FakeBotApi()
    api.fail("getUpdates", 502, 502, 502)
    sleeps = SleepRecorder()
    with pytest.raises(HttpStatusError):
        await client_for(api, sleeps).get_updates(offset=None, timeout_s=1)
    assert len(api.sent("getUpdates")) == 1 and sleeps.delays == []


async def test_send_message_is_plain_text_with_an_inline_keyboard_for_quick_replies() -> None:
    api = FakeBotApi()
    message_id = await client_for(api).send_message(
        9, "नमस्ते\nHello", buttons=[("why", "Why?"), ("ill", "I am ill")]
    )
    (call,) = api.sent("sendMessage")
    assert message_id == 101
    assert call.payload["chat_id"] == 9 and call.payload["text"] == "नमस्ते\nHello"
    assert "parse_mode" not in call.payload  # a merchant's words can never be read as markup
    assert call.payload["reply_markup"] == {
        "inline_keyboard": [
            [{"text": "Why?", "callback_data": "why"}],
            [{"text": "I am ill", "callback_data": "ill"}],
        ]
    }


@pytest.mark.parametrize("text", [None, "", "   ", "x" * 4097])
async def test_send_message_rejects_empty_or_oversized_text_before_any_call(text: str | None) -> None:
    api = FakeBotApi()
    with pytest.raises(ValueError, match="text"):
        await client_for(api).send_message(9, text)
    assert api.calls == []


@pytest.mark.parametrize(
    "buttons",
    [[], [("a", "A")] * 4, [("", "A")], [("a", "")], [("é" * 33, "too long id")]],
)
def test_inline_keyboard_checks_the_button_rules(buttons: list[tuple[str, str]]) -> None:
    with pytest.raises(ValueError, match="quick repl"):
        inline_keyboard(buttons)


async def test_send_voice_and_photo_are_multipart_uploads() -> None:
    api = FakeBotApi()
    client = client_for(api)
    await client.send_voice(9, b"OggS-voice")
    await client.send_photo(9, b"\xff\xd8\xff-photo", caption="slip")
    voice, photo = api.sent("sendVoice")[0], api.sent("sendPhoto")[0]
    assert "voice" in voice.fields and voice.payload["chat_id"] == 9
    assert "photo" in photo.fields and "caption" in photo.fields
    with pytest.raises(ValueError, match="empty"):
        await client.send_voice(9, b"")
    with pytest.raises(ValueError, match="empty"):
        await client.send_photo(9, b"")


async def test_download_file_resolves_the_path_then_fetches_the_bytes() -> None:
    api = FakeBotApi(files={"F1": b"IMAGEBYTES"})
    media = await client_for(api).download_file("F1", mime_type="image/jpeg; charset=x")
    assert (media.data, media.mime_type) == (b"IMAGEBYTES", "image/jpeg")
    assert api.sent("getFile")[0].payload == {"file_id": "F1"}


async def test_download_refuses_big_empty_and_unknown_files() -> None:
    api = FakeBotApi(files={"BIG": b"x", "EMPTY": b""}, file_sizes={"BIG": MAX_FILE_BYTES + 1})
    client = client_for(api)
    with pytest.raises(IntegrationError, match="larger than 5 MB"):
        await client.download_file("BIG", mime_type="image/png")
    with pytest.raises(IntegrationError, match="empty"):
        await client.download_file("EMPTY", mime_type="image/png")
    with pytest.raises(IntegrationError, match="getFile rejected"):
        await client.download_file("NOPE", mime_type="image/png")


async def test_a_path_that_climbs_out_is_not_followed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": {"file_path": "../../etc/passwd"}})

    client = TelegramBotClient(TOKEN, transport=httpx.MockTransport(handler), sleep=SleepRecorder())
    with pytest.raises(IntegrationError, match="no usable path"):
        await client.get_file("F")


async def test_429_and_5xx_are_retried_with_backoff_then_succeed() -> None:
    api = FakeBotApi()
    api.fail("sendMessage", 429, 503)
    sleeps = SleepRecorder()
    message_id = await client_for(
        api, sleeps, policy=RetryPolicy(max_attempts=3, base_delay_s=0.5)
    ).send_message(1, "hi")
    assert message_id == 101 and len(api.sent("sendMessage")) == 3 and sleeps.delays == [0.5, 1.0]


async def test_a_client_error_is_not_retried_and_its_message_is_safe(
    caplog: pytest.LogCaptureFixture,
) -> None:
    api = FakeBotApi()
    api.fail("sendMessage", 400)
    with caplog.at_level(logging.DEBUG), pytest.raises(IntegrationError) as caught:
        await client_for(api).send_message(1, "hi")
    assert len(api.sent("sendMessage")) == 1
    assert "400" in caught.value.safe_message and "boom" not in str(caught.value)
    assert TOKEN not in str(caught.value) and TOKEN not in caplog.text


async def test_a_wrong_token_answers_401_without_leaking_the_token() -> None:
    client = TelegramBotClient("999:wrong", transport=FakeBotApi().transport(), sleep=SleepRecorder())
    with pytest.raises(IntegrationError) as caught:
        await client.get_me()
    assert "authentication failed" in caught.value.safe_message
    assert "999:wrong" not in str(caught.value) and "999:wrong" not in repr(client)


async def test_a_not_ok_answer_with_http_200_is_still_an_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "error_code": 403, "description": "bot was blocked"})

    client = TelegramBotClient(TOKEN, transport=httpx.MockTransport(handler), sleep=SleepRecorder())
    with pytest.raises(IntegrationError, match=r"sendMessage rejected \(error 403\)") as caught:
        await client.send_message(1, "hi")
    assert "blocked" not in str(caught.value)


def test_the_client_needs_a_token_and_never_shows_it() -> None:
    with pytest.raises(ValueError, match="token"):
        TelegramBotClient("  ")
    assert TOKEN not in repr(client_for(FakeBotApi()))


def test_httpx_request_logging_is_kept_below_info_because_urls_carry_the_token() -> None:
    assert logging.getLogger("httpx").level >= logging.WARNING
