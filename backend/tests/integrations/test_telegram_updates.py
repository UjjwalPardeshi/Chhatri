"""getUpdates items parsed into events: commands, text, the biggest photo, voice, callbacks, skipped items."""

from __future__ import annotations

from typing import Any

from chhatri.integrations.telegram_updates import (
    TgCallback,
    TgCommand,
    TgPhoto,
    TgText,
    TgUnsupported,
    TgVoice,
    parse_update,
    parse_updates,
)
from tests.fake_telegram import callback_update, photo_update, text_update, voice_update


def test_plain_text_is_text_with_the_chat_and_an_ist_time() -> None:
    event = parse_update(text_update(10, 77, "मुझे इतने ही पैसे क्यों मिले?"))
    assert isinstance(event, TgText) and (event.update_id, event.chat_id) == (10, 77)
    assert event.text == "मुझे इतने ही पैसे क्यों मिले?"
    assert event.at.utcoffset() is not None and event.at.utcoffset().total_seconds() == 19800


def test_start_with_a_deep_link_payload_is_a_command_with_its_argument() -> None:
    event = parse_update(text_update(1, 5, "/start S-0142"))
    assert isinstance(event, TgCommand) and (event.command, event.argument) == ("start", "S-0142")


def test_commands_ignore_case_botname_and_missing_argument() -> None:
    assert parse_update(text_update(1, 5, "/STOP")) == parse_update(text_update(1, 5, "/stop"))
    named = parse_update(text_update(1, 5, "/start@ChhatriDemoBot S-0907"))
    assert isinstance(named, TgCommand) and (named.command, named.argument) == ("start", "S-0907")
    bare = parse_update(text_update(1, 5, "/start"))
    assert isinstance(bare, TgCommand) and bare.argument is None


def test_a_slash_in_the_middle_of_a_sentence_is_text() -> None:
    assert isinstance(parse_update(text_update(1, 5, "1/2 of it")), TgText)
    assert isinstance(parse_update(text_update(1, 5, "/ not a command")), TgText)


def test_a_photo_event_carries_the_biggest_size() -> None:
    event = parse_update(photo_update(2, 5, ("small", "medium", "large")))
    assert isinstance(event, TgPhoto) and event.file_id == "large"


def test_voice_and_audio_carry_their_mime_type() -> None:
    voice = parse_update(voice_update(3, 5, "V1"))
    assert isinstance(voice, TgVoice) and (voice.file_id, voice.mime_type) == ("V1", "audio/ogg")
    audio = text_update(4, 5, "x")
    del audio["message"]["text"]
    audio["message"]["audio"] = {"file_id": "A1", "mime_type": "audio/mpeg"}
    parsed = parse_update(audio)
    assert isinstance(parsed, TgVoice) and parsed.mime_type == "audio/mpeg"


def test_a_button_tap_is_a_callback_with_its_data() -> None:
    event = parse_update(callback_update(8, 5, "why"))
    assert isinstance(event, TgCallback) and (event.callback_id, event.data, event.chat_id) == (
        "cb-8",
        "why",
        5,
    )


def test_other_message_types_are_unsupported_not_dropped() -> None:
    sticker = text_update(9, 5, "x")
    del sticker["message"]["text"]
    sticker["message"]["sticker"] = {"file_id": "S"}
    event = parse_update(sticker)
    assert isinstance(event, TgUnsupported) and event.kind == "sticker"


def test_group_chats_are_never_served() -> None:
    group = text_update(11, -100, "/start S-0142")
    group["message"]["chat"]["type"] = "supergroup"
    assert parse_update(group) is None
    query = callback_update(12, 5, "why")
    query["callback_query"]["message"]["chat"]["type"] = "group"
    assert parse_update(query) is None


def test_malformed_items_are_skipped_and_never_stop_the_batch() -> None:
    broken: list[Any] = [
        "not an object",
        {"message": {}},  # no update_id
        {"update_id": True, "message": {}},  # a bool is not an id
        {"update_id": 1, "message": {"chat": {"id": 1, "type": "private"}}},  # no date
        {"update_id": 2},  # neither message nor callback
        {"update_id": 3, "callback_query": {"id": "c", "data": "x"}},  # no chat
        text_update(4, 5, "ok"),
    ]
    events = parse_updates(broken)
    assert [e.update_id for e in events] == [4]
    assert parse_updates("nope") == ()


def test_an_image_sent_as_a_file_is_a_photo_and_other_files_are_unsupported() -> None:
    picture = text_update(10, 5, "x")
    del picture["message"]["text"]
    picture["message"]["document"] = {"file_id": "DOC1", "mime_type": "image/jpeg", "file_name": "slip.jpg"}
    picture["message"]["caption"] = "my slip"
    event = parse_update(picture)
    assert isinstance(event, TgPhoto) and (event.file_id, event.caption) == ("DOC1", "my slip")
    pdf = text_update(11, 5, "x")
    del pdf["message"]["text"]
    pdf["message"]["document"] = {"file_id": "DOC2", "mime_type": "application/pdf"}
    other = parse_update(pdf)
    assert isinstance(other, TgUnsupported) and other.kind == "document"
