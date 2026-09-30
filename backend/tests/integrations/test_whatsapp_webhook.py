"""WhatsApp webhook verification and parsing (SPEC §14.2)."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from chhatri.clock import ist
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.whatsapp import (
    AudioEvent,
    ButtonEvent,
    ImageEvent,
    StatusEvent,
    TextEvent,
    UnsupportedEvent,
    parse_webhook,
    verify_challenge,
    verify_signature,
)

SECRET = "app-secret"
TS = "1755603120"  # 2025-08-19 17:02 IST


def sign(raw: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def webhook(*messages: dict, statuses: tuple[dict, ...] = ()) -> dict:
    value = {"messaging_product": "whatsapp", "messages": list(messages), "statuses": list(statuses)}
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "1", "changes": [{"field": "messages", "value": value}]}],
    }


def msg(kind: str, body: dict, message_id: str = "wamid.1") -> dict:
    return {"from": "919812345678", "id": message_id, "timestamp": TS, "type": kind, **body}


def test_signature_over_raw_bytes() -> None:
    raw = json.dumps(webhook(msg("text", {"text": {"body": "hi"}}))).encode()
    assert verify_signature(SECRET, raw, sign(raw))
    reformatted = json.dumps(json.loads(raw), indent=2).encode()
    assert not verify_signature(SECRET, reformatted, sign(raw))
    assert not verify_signature(SECRET, raw, sign(raw, "other"))
    assert not verify_signature(SECRET, raw, sign(raw).replace("sha256=", "sha1="))
    assert not verify_signature(SECRET, raw, None)
    assert not verify_signature("", raw, sign(raw, ""))
    assert not verify_signature(SECRET, raw, "sha256=ünïcode")


def test_challenge() -> None:
    ok = {"hub.mode": "subscribe", "hub.verify_token": "tok", "hub.challenge": "12345"}
    assert verify_challenge(ok, "tok") == "12345"
    assert verify_challenge({**ok, "hub.verify_token": "bad"}, "tok") is None
    assert verify_challenge({**ok, "hub.mode": "unsubscribe"}, "tok") is None
    assert verify_challenge({**ok, "hub.challenge": ""}, "tok") is None
    assert verify_challenge(ok, "") is None


def test_parses_every_message_kind_and_statuses() -> None:
    at = ist(2025, 8, 19, 17, 2)
    events = parse_webhook(
        webhook(
            msg("text", {"text": {"body": "मुझे इतने ही पैसे क्यों मिले?"}}, "w1"),
            msg(
                "audio",
                {"audio": {"id": "m-audio", "mime_type": "audio/ogg; codecs=opus", "voice": True}},
                "w2",
            ),
            msg("image", {"image": {"id": "m-img", "mime_type": "image/jpeg", "caption": "slip"}}, "w3"),
            msg(
                "interactive",
                {"interactive": {"type": "button_reply", "button_reply": {"id": "yes", "title": "हाँ"}}},
                "w4",
            ),
            msg("sticker", {"sticker": {"id": "s"}}, "w5"),
            statuses=(
                {"id": "wamid.out", "status": "delivered", "timestamp": TS, "recipient_id": "919812345678"},
            ),
        )
    )
    assert events == (
        TextEvent("w1", at, "919812345678", "मुझे इतने ही पैसे क्यों मिले?"),
        AudioEvent("w2", at, "919812345678", "m-audio", "audio/ogg; codecs=opus", True),
        ImageEvent("w3", at, "919812345678", "m-img", "image/jpeg", "slip"),
        ButtonEvent("w4", at, "919812345678", "yes", "हाँ"),
        UnsupportedEvent("w5", at, "919812345678", "sticker"),
        StatusEvent("wamid.out", at, "919812345678", "delivered"),
    )


def test_defaults_for_missing_mime_types() -> None:
    audio, image = parse_webhook(
        webhook(msg("audio", {"audio": {"id": "a"}}, "a1"), msg("image", {"image": {"id": "i"}}, "i1"))
    )
    assert isinstance(audio, AudioEvent) and audio.mime_type == "audio/ogg" and audio.voice is False
    assert isinstance(image, ImageEvent) and image.mime_type == "image/jpeg" and image.caption is None


@pytest.mark.parametrize(
    "bad",
    [
        "not an object",
        {"id": "x", "timestamp": TS, "type": "text", "text": {"body": "no sender"}},
        msg("text", {"text": {"body": ""}}),
        msg("audio", {"audio": {}}),
        msg("image", {"image": "nope"}),
        msg("interactive", {"interactive": {"button_reply": {"id": "only-id"}}}),
        {**msg("text", {"text": {"body": "x"}}), "timestamp": "yesterday"},
    ],
)
def test_malformed_messages_are_skipped(bad: object) -> None:
    assert parse_webhook(webhook(bad)) == ()  # type: ignore[arg-type]


def test_malformed_structure_is_tolerated() -> None:
    assert parse_webhook({"entry": "x"}) == ()
    assert parse_webhook({"entry": [1, {"changes": [2, {"value": "v"}]}]}) == ()
    assert parse_webhook(webhook(statuses=("bad", {"id": "x"}))) == ()
    with pytest.raises(IntegrationError):
        parse_webhook([1, 2])
