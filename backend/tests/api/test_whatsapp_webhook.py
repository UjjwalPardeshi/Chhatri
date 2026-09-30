"""WhatsApp Cloud API webhook (SPEC §14.2, §19, §21)."""

from __future__ import annotations

import logging
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from chhatri.api.schemas import WhatsAppAck
from chhatri.api.whatsapp_inbox import WhatsAppInbox
from chhatri.integrations.base import InboundMedia
from tests.api import media_samples as media
from tests.api.conftest import signed
from tests.api.fakes import DEMO_RECIPIENT, WA_VERIFY_TOKEN, FakeAppState
from tests.api.helpers import data_of, error_of

ANIL_PHONE = DEMO_RECIPIENT.lstrip("+")
STRANGER = "919812345678"


def message(msg_id: str, kind: str, body: dict[str, Any], sender: str = ANIL_PHONE) -> dict[str, Any]:
    return {"from": sender, "id": msg_id, "timestamp": "1755605100", "type": kind, kind: body}


def webhook(*messages: dict[str, Any], statuses: tuple[dict[str, Any], ...] = ()) -> dict[str, Any]:
    value = {"messaging_product": "whatsapp", "messages": list(messages), "statuses": list(statuses)}
    return {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{"value": value}]}]}


async def post(client: AsyncClient, payload: dict[str, Any]) -> WhatsAppAck:
    raw, headers = signed(payload)
    return data_of(await client.post("/webhooks/whatsapp", content=raw, headers=headers), WhatsAppAck)


async def drained(app: FastAPI) -> None:
    inbox: WhatsAppInbox = app.state.whatsapp_inbox
    await inbox.drain()


async def test_challenge_handshake(client: AsyncClient) -> None:
    params = {"hub.mode": "subscribe", "hub.verify_token": WA_VERIFY_TOKEN, "hub.challenge": "1158201444"}
    response = await client.get("/webhooks/whatsapp", params=params)
    assert (response.status_code, response.text) == (200, "1158201444")
    assert response.headers["content-type"].startswith("text/plain")
    error_of(
        await client.get("/webhooks/whatsapp", params=params | {"hub.verify_token": "x"}), 403, "forbidden"
    )
    error_of(await client.get("/webhooks/whatsapp", params={"hub.challenge": "1"}), 403, "forbidden")


async def test_signature_is_checked_on_raw_bytes(client: AsyncClient) -> None:
    raw, headers = signed(webhook(message("wamid.1", "text", {"body": "hi"})))
    error_of(await client.post("/webhooks/whatsapp", content=raw + b" ", headers=headers), 403, "forbidden")
    error_of(await client.post("/webhooks/whatsapp", content=raw), 403, "forbidden")
    _, other = signed(webhook(), secret="not-the-secret")
    error_of(await client.post("/webhooks/whatsapp", content=raw, headers=other), 403, "forbidden")


async def test_text_from_the_demo_recipient_reaches_the_demo_merchant(
    client: AsyncClient, app: FastAPI, fake_state: FakeAppState
) -> None:
    ack = await post(client, webhook(message("wamid.1", "text", {"body": "मुझे इतने ही पैसे क्यों मिले?"})))
    assert (ack.accepted, ack.duplicates, ack.ignored) == (1, 0, 0)
    await drained(app)
    assert fake_state.runtime.conversation.calls == [("text", ("S-0142", "मुझे इतने ही पैसे क्यों मिले?"))]


async def test_duplicate_deliveries_are_processed_once(
    client: AsyncClient, app: FastAPI, fake_state: FakeAppState
) -> None:
    payload = webhook(message("wamid.dup", "text", {"body": "hi"}))
    await post(client, payload)
    again = await post(client, payload)
    assert (again.accepted, again.duplicates) == (0, 1)
    await drained(app)
    assert len(fake_state.runtime.conversation.calls) == 1


async def test_statuses_are_acknowledged_but_ignored(
    client: AsyncClient, app: FastAPI, fake_state: FakeAppState
) -> None:
    status = {"id": "wamid.9", "recipient_id": ANIL_PHONE, "status": "delivered", "timestamp": "1755605100"}
    ack = await post(client, webhook(statuses=(status,)))
    assert (ack.accepted, ack.ignored) == (0, 1)
    await drained(app)
    assert fake_state.runtime.conversation.calls == []


async def test_other_numbers_get_the_demo_notice(
    client: AsyncClient, app: FastAPI, fake_state: FakeAppState
) -> None:
    await post(client, webhook(message("wamid.2", "text", {"body": "hello"}, sender=STRANGER)))
    await drained(app)
    assert fake_state.runtime.conversation.calls == []
    assert [phone for phone, _ in fake_state.runtime.integrations.channel.notices] == [STRANGER]


async def test_voice_image_and_button_are_dispatched_in_order(
    client: AsyncClient, app: FastAPI, fake_state: FakeAppState
) -> None:
    channel = fake_state.runtime.integrations.channel
    channel.media["m-audio"] = InboundMedia(media.ogg_opus_bytes(5), "audio/ogg; codecs=opus")
    channel.media["m-image"] = InboundMedia(media.image_bytes("JPEG"), "image/jpeg")
    await post(
        client,
        webhook(
            message("wamid.a", "audio", {"id": "m-audio", "mime_type": "audio/ogg", "voice": True}),
            message("wamid.b", "image", {"id": "m-image", "mime_type": "image/jpeg"}),
            message(
                "wamid.c",
                "interactive",
                {"type": "button_reply", "button_reply": {"id": "yes", "title": "हाँ"}},
            ),
        ),
    )
    await drained(app)
    calls = fake_state.runtime.conversation.calls
    assert [kind for kind, _ in calls] == ["voice", "image", "text"]
    assert calls[0][1][2] == "audio/ogg"
    assert calls[1][1][2:] == ("image/jpeg", "MD-000001")
    assert calls[2][1] == ("S-0142", "हाँ")


async def test_bad_media_is_logged_and_the_worker_continues(
    client: AsyncClient, app: FastAPI, fake_state: FakeAppState, caplog: pytest.LogCaptureFixture
) -> None:
    fake_state.runtime.integrations.channel.media["too-long"] = InboundMedia(
        media.ogg_opus_bytes(40), "audio/ogg"
    )
    await post(
        client,
        webhook(
            message("wamid.x", "audio", {"id": "too-long", "mime_type": "audio/ogg"}),
            message("wamid.y", "image", {"id": "missing", "mime_type": "image/jpeg"}),
            message("wamid.z", "sticker", {"id": "s1"}),
            message("wamid.t", "text", {"body": "still here"}),
        ),
    )
    with caplog.at_level(logging.INFO):
        await drained(app)
    assert fake_state.runtime.conversation.calls == [("text", ("S-0142", "still here"))]
    assert "wamid.x failed: ApiError" in caplog.text and "wamid.y failed: IntegrationError" in caplog.text
    assert ANIL_PHONE not in caplog.text


@pytest.mark.parametrize("raw", [b"{not json", b"[1, 2]"])
async def test_unparseable_bodies_are_422(client: AsyncClient, raw: bytes) -> None:
    import hashlib
    import hmac

    from tests.api.fakes import WA_APP_SECRET

    signature = "sha256=" + hmac.new(WA_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    response = await client.post(
        "/webhooks/whatsapp", content=raw, headers={"X-Hub-Signature-256": signature}
    )
    error_of(response, 422, "validation_error")


async def test_without_a_scenario_messages_are_acknowledged_and_dropped(bare_client: AsyncClient) -> None:
    ack = await post(bare_client, webhook(message("wamid.1", "text", {"body": "hi"})))
    assert (ack.accepted, ack.ignored) == (0, 1)


async def test_non_live_channel_is_503(client: AsyncClient, fake_state: FakeAppState) -> None:
    fake_state.runtime.integrations.channel = object()  # type: ignore[assignment]
    raw, headers = signed(webhook(message("wamid.1", "text", {"body": "hi"})))
    error_of(await client.post("/webhooks/whatsapp", content=raw, headers=headers), 503, "unavailable")


async def test_worker_survives_a_reload_and_close_is_clean(
    client: AsyncClient, app: FastAPI, fake_state: FakeAppState
) -> None:
    await post(client, webhook(message("wamid.1", "text", {"body": "one"})))
    await drained(app)
    inbox: WhatsAppInbox = app.state.whatsapp_inbox
    await inbox.close()
    await inbox.close()
    await post(client, webhook(message("wamid.2", "text", {"body": "two"})))
    await drained(app)
    assert [args[1] for _, args in fake_state.runtime.conversation.calls] == ["one", "two"]
    await inbox.close()


async def test_webhook_rate_limit(client: AsyncClient) -> None:
    for _ in range(60):
        await client.get("/webhooks/whatsapp")
    limited = await client.post("/api/webhooks/paytm", json={})
    error_of(limited, 429, "rate_limited")
    assert int(limited.headers["retry-after"]) >= 1
