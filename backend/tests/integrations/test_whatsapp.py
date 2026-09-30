"""Live WhatsApp Cloud API channel against httpx.MockTransport (SPEC §14.2)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import httpx
import pytest

from chhatri.clock import IST, ist
from chhatri.integrations.base import IntegrationError, OutboundMessage
from chhatri.integrations.whatsapp import MAX_MEDIA_BYTES, LiveWhatsAppChannel, TextEvent

from .conftest import no_sleep

DEMO_PHONE = "+919812345678"
NOW = ist(2025, 8, 19, 17, 4)
GRAPH = "https://graph.facebook.com/v25.0"


class Graph:
    """Minimal Graph API double that records requests."""

    def __init__(self, *, fail_first: int = 0, media_size: int = 10) -> None:
        self.requests: list[httpx.Request] = []
        self.fail_first = fail_first
        self.media_size = media_size

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail_first:
            self.fail_first -= 1
            return httpx.Response(503)
        path = request.url.path
        if path.endswith("/messages"):
            return httpx.Response(200, json={"messages": [{"id": f"wamid.{len(self.requests)}"}]})
        if path.endswith("/media"):
            return httpx.Response(200, json={"id": "media-77"})
        if path == "/v25.0/1234567890":
            return httpx.Response(
                200, json={"url": "https://lookaside.fbsbx.com/x?id=1", "mime_type": "audio/ogg; codecs=opus"}
            )
        if request.url.host == "lookaside.fbsbx.com":
            return httpx.Response(200, content=b"O" * self.media_size)
        return httpx.Response(404)

    def bodies(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests if r.url.path.endswith("/messages")]


def channel(graph: Graph, *, recipient: str | None = DEMO_PHONE, now: datetime = NOW) -> LiveWhatsAppChannel:
    return LiveWhatsAppChannel(
        access_token="EAAG-token",
        phone_number_id="PNID",
        demo_recipient=recipient,
        transport=httpx.MockTransport(graph),
        sleep=no_sleep,
        now=lambda: now,
    )


def open_window(ch: LiveWhatsAppChannel, at: datetime = NOW - timedelta(minutes=5)) -> None:
    assert ch.accept_inbound(TextEvent("wamid.in", at, "919812345678", "hi"))


async def test_non_demo_merchant_is_recorded_not_sent() -> None:
    graph = Graph()
    receipt = await channel(graph).send(OutboundMessage("S-0001", "+919900000001", text="x"))
    assert receipt.channel == "simulator" and receipt.provider_message_id is None and graph.requests == []


async def test_no_demo_recipient_means_nothing_is_sent() -> None:
    graph = Graph()
    receipt = await channel(graph, recipient=None).send(OutboundMessage("S-0142", "+919900012345", text="x"))
    assert receipt.channel == "simulator" and graph.requests == []


async def test_inside_window_sends_text_to_demo_recipient_only() -> None:
    graph = Graph()
    ch = channel(graph)
    open_window(ch)
    receipt = await ch.send(
        OutboundMessage(
            "S-0142", "+919900012345", text="अनिल जी…\nAnil ji…", template_name="chhatri_area_payout"
        )
    )
    assert receipt.accepted and receipt.channel == "whatsapp" and receipt.provider_message_id == "wamid.1"
    request = graph.requests[0]
    assert str(request.url) == f"{GRAPH}/PNID/messages"
    assert request.headers["Authorization"] == "Bearer EAAG-token"
    body = graph.bodies()[0]
    assert body == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "919812345678",
        "type": "text",
        "text": {"preview_url": False, "body": "अनिल जी…\nAnil ji…"},
    }


async def test_outside_window_sends_template() -> None:
    graph = Graph()
    ch = channel(graph)
    message = OutboundMessage(
        "S-0142",
        "+919900012345",
        text="free text",
        template_name="chhatri_area_payout",
        template_params=("अनिल", "63", "₹1,380"),
    )
    await ch.send(message)
    assert graph.bodies()[0]["template"] == {
        "name": "chhatri_area_payout",
        "language": {"code": "hi"},
        "components": [
            {"type": "body", "parameters": [{"type": "text", "text": p} for p in ("अनिल", "63", "₹1,380")]}
        ],
    }


async def test_outside_window_without_template_is_not_sent() -> None:
    graph = Graph()
    ch = channel(graph)
    open_window(ch, NOW - timedelta(hours=25))
    receipt = await ch.send(OutboundMessage("S-0142", "+91", text="free text", audio=b"OggS"))
    assert receipt.accepted is False and "24-hour" in receipt.detail and graph.requests == []


async def test_voice_note_is_uploaded_then_sent_as_audio() -> None:
    graph = Graph()
    ch = channel(graph)
    open_window(ch)
    receipt = await ch.send(
        OutboundMessage("S-0142", "+91", text="नमस्ते", audio=b"OggS-opus", audio_mime="audio/ogg")
    )
    upload = graph.requests[1]
    assert str(upload.url) == f"{GRAPH}/PNID/media"
    form = upload.content.decode("latin-1")
    assert 'name="messaging_product"' in form and "whatsapp" in form
    assert 'name="type"' in form and "audio/ogg" in form and 'name="file"' in form
    assert graph.bodies()[-1]["audio"] == {"id": "media-77"}
    assert receipt.detail == "sent 2 message(s)"


async def test_audio_only_message_inside_window() -> None:
    graph = Graph()
    ch = channel(graph)
    open_window(ch)
    receipt = await ch.send(OutboundMessage("S-0142", "+91", audio=b"OggS"))
    assert receipt.provider_message_id == "wamid.2" and graph.bodies()[0]["type"] == "audio"


async def test_buttons_payload_and_limits() -> None:
    graph = Graph()
    ch = channel(graph)
    open_window(ch)
    await ch.send(OutboundMessage("S-0907", "+91", text="Cover?", buttons=(("yes", "हाँ"), ("no", "नहीं"))))
    interactive = graph.bodies()[0]["interactive"]
    assert interactive["type"] == "button" and interactive["body"] == {"text": "Cover?"}
    assert interactive["action"]["buttons"][0] == {"type": "reply", "reply": {"id": "yes", "title": "हाँ"}}
    with pytest.raises(ValueError):
        await ch.send(
            OutboundMessage("S-0907", "+91", text="x", buttons=tuple((str(n), "t") for n in range(4)))
        )
    with pytest.raises(ValueError):
        await ch.send(OutboundMessage("S-0907", "+91", text="x", buttons=(("a", "x" * 21),)))
    with pytest.raises(ValueError):
        await ch.send(OutboundMessage("S-0907", "+91"))


async def test_send_retries_5xx_and_raises_on_bad_response() -> None:
    graph = Graph(fail_first=2)
    ch = channel(graph)
    open_window(ch)
    assert (await ch.send(OutboundMessage("S-0142", "+91", text="x"))).accepted
    assert len(graph.requests) == 3

    def no_id(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"messages": []})

    broken = LiveWhatsAppChannel(
        access_token="t",
        phone_number_id="P",
        demo_recipient=DEMO_PHONE,
        transport=httpx.MockTransport(no_id),
        now=lambda: NOW,
    )
    open_window(broken)
    with pytest.raises(IntegrationError, match="no message id"):
        await broken.send(OutboundMessage("S-0142", "+91", text="x"))


async def test_download_media_two_step_with_bearer() -> None:
    graph = Graph()
    media = await channel(graph).download_media("1234567890")
    assert media.data == b"O" * 10 and media.mime_type == "audio/ogg"
    assert all(r.headers["Authorization"] == "Bearer EAAG-token" for r in graph.requests)
    assert str(graph.requests[0].url) == f"{GRAPH}/1234567890"


async def test_download_media_rejects_bad_ids_and_oversize() -> None:
    with pytest.raises(IntegrationError, match="invalid media id"):
        await channel(Graph()).download_media("../../me")
    with pytest.raises(IntegrationError, match="5 MB"):
        await channel(Graph(media_size=MAX_MEDIA_BYTES + 1)).download_media("1234567890")
    with pytest.raises(IntegrationError, match="empty"):
        await channel(Graph(media_size=0)).download_media("1234567890")
    with pytest.raises(IntegrationError, match="HTTP 404"):
        await channel(Graph()).download_media("999")


async def test_demo_notice_once_per_day() -> None:
    graph = Graph()
    ch = channel(graph)
    first = await ch.send_demo_notice("919800000001", NOW)
    again = await ch.send_demo_notice("+919800000001", NOW + timedelta(hours=1))
    assert first is not None and first.detail == "demo notice" and again is None
    assert graph.bodies()[0]["to"] == "919800000001"
    assert "demo" in graph.bodies()[0]["text"]["body"]


async def test_upload_validation() -> None:
    ch = channel(Graph())
    with pytest.raises(ValueError):
        await ch.upload_media(b"x", "video/mp4")

    def no_id(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    bad = LiveWhatsAppChannel(
        access_token="t", phone_number_id="P", demo_recipient=DEMO_PHONE, transport=httpx.MockTransport(no_id)
    )
    with pytest.raises(IntegrationError, match="no id"):
        await bad.upload_media(b"x", "audio/ogg")
    with pytest.raises(ValueError):
        LiveWhatsAppChannel(access_token="", phone_number_id="P", demo_recipient=None)


async def test_media_lookup_without_url_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"url": "http://insecure", "mime_type": "image/jpeg"})

    ch = LiveWhatsAppChannel(
        access_token="t",
        phone_number_id="P",
        demo_recipient=DEMO_PHONE,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(IntegrationError, match="no url"):
        await ch.download_media("123")


async def test_window_uses_real_whatsapp_time_by_default() -> None:
    """Meta enforces the 24 h window in wall-clock time, so the default clock is the real one."""
    graph = Graph()
    ch = LiveWhatsAppChannel(
        access_token="EAAG-token",
        phone_number_id="PNID",
        demo_recipient=DEMO_PHONE,
        transport=httpx.MockTransport(graph),
        sleep=no_sleep,
    )
    ch.gate.note_inbound(DEMO_PHONE, datetime.now(tz=IST) - timedelta(minutes=1))
    await ch.send(OutboundMessage("S-0142", "+91", text="free text"))
    assert graph.bodies()[0]["type"] == "text"
