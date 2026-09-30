"""Live WhatsApp Cloud API channel (SPEC §14.2) over httpx.

Base `https://graph.facebook.com/{WHATSAPP_GRAPH_VERSION}` (default v25.0), Bearer auth.
- Send: `POST /{phone-number-id}/messages`; voice notes are uploaded first via
  `POST /{phone-number-id}/media` (multipart `messaging_product=whatsapp`, `type=audio/ogg`, `file`)
  and then sent as `{"type": "audio", "audio": {"id": …}}`.
- Media download: `GET /{media-id}` → `{url, mime_type}` → `GET url` with the same Bearer token.
- Recipient safety: only demo merchants are ever sent, and only to `WHATSAPP_DEMO_RECIPIENT`; other
  merchants' messages are recorded (receipt channel "simulator") and never leave the process.
- 24-hour window: free-form (text, buttons, voice) only within 24 h of the recipient's last inbound
  message; otherwise the approved template, and if the message has none it is not sent.
The window uses real WhatsApp time (injectable `now`), not simulated replay time, because it is
enforced by Meta's servers.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

import httpx

from chhatri.clock import IST
from chhatri.integrations.base import DeliveryReceipt, InboundMedia, IntegrationError, OutboundMessage
from chhatri.integrations.retry import (
    DEFAULT_RETRY,
    DEFAULT_TIMEOUT_S,
    RetryPolicy,
    Sleep,
    http_request,
    json_object,
    mask_phone,
)
from chhatri.integrations.whatsapp_payloads import (
    VOICE_NOTE_MIME,
    audio_payload,
    buttons_payload,
    template_payload,
    text_payload,
    upload_form,
)
from chhatri.integrations.whatsapp_state import (
    DEMO_MERCHANT_IDS,
    DEMO_NOTICE_TEXT,
    InboundGate,
    phone_digits,
)
from chhatri.integrations.whatsapp_webhook import InboundEvent

logger = logging.getLogger(__name__)

INTEGRATION = "whatsapp"
GRAPH_BASE = "https://graph.facebook.com"
MAX_MEDIA_BYTES = 5 * 1024 * 1024  # SPEC §19: uploads ≤ 5 MB
_MEDIA_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _wall_clock() -> datetime:
    return datetime.now(tz=IST)


class LiveWhatsAppChannel:
    """MessagingChannel for the WhatsApp Cloud API with the SPEC §14.2 safety rules."""

    def __init__(
        self,
        *,
        access_token: str,
        phone_number_id: str,
        demo_recipient: str | None,
        graph_version: str = "v25.0",
        template_language: str = "hi",
        demo_merchant_ids: frozenset[str] = DEMO_MERCHANT_IDS,
        gate: InboundGate | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        transport: httpx.AsyncBaseTransport | None = None,
        policy: RetryPolicy = DEFAULT_RETRY,
        sleep: Sleep = asyncio.sleep,
        now: Callable[[], datetime] = _wall_clock,
    ) -> None:
        if not access_token or not phone_number_id:
            raise ValueError("access_token and phone_number_id are required")
        self._token = access_token
        self._phone_number_id = phone_number_id
        self._base = f"{GRAPH_BASE}/{graph_version}"
        self._recipient = phone_digits(demo_recipient) if demo_recipient else None
        self._template_language = template_language
        self._demo_ids = demo_merchant_ids
        self.gate = gate or InboundGate()
        self._timeout_s = timeout_s
        self._transport = transport
        self._policy = policy
        self._sleep = sleep
        self._now = now

    # ------------------------------------------------------------------ inbound

    def accept_inbound(self, event: InboundEvent) -> bool:
        """Idempotency + window bookkeeping; False for a duplicate delivery."""
        return self.gate.accept(event)

    async def send_demo_notice(self, phone: str, at: datetime) -> DeliveryReceipt | None:
        """Polite "this is a demo" reply to a non-demo number, at most once per IST day."""
        if not self.gate.claim_demo_notice(phone, at.astimezone(IST).date()):
            return None
        message_id = await self._post_message(text_payload(phone_digits(phone), DEMO_NOTICE_TEXT))
        logger.info("whatsapp: demo notice sent to %s", mask_phone(phone))
        return DeliveryReceipt(message_id, INTEGRATION, True, "demo notice")

    # ------------------------------------------------------------------ outbound

    async def send(self, message: OutboundMessage) -> DeliveryReceipt:
        if message.merchant_id not in self._demo_ids or self._recipient is None:
            return DeliveryReceipt(None, "simulator", True, "recorded only: not a demo merchant (SPEC §14.2)")
        in_window = self.gate.within_window(self._recipient, self._now())
        primary = self._primary_payload(message, in_window)
        if primary is None and not (message.audio and in_window):
            logger.info("whatsapp: %s outside the 24 h window and no template; not sent", message.merchant_id)
            return DeliveryReceipt(None, INTEGRATION, False, "outside the 24-hour window and no template")
        ids: list[str] = []
        if primary is not None:
            ids.append(await self._post_message(primary))
        if message.audio and in_window:
            media_id = await self.upload_media(message.audio, message.audio_mime or VOICE_NOTE_MIME)
            ids.append(await self._post_message(audio_payload(self._recipient, media_id)))
        return DeliveryReceipt(ids[0], INTEGRATION, True, f"sent {len(ids)} message(s)")

    def _primary_payload(self, message: OutboundMessage, in_window: bool) -> dict[str, Any] | None:
        to = self._recipient or ""
        if in_window and message.buttons:
            return buttons_payload(to, message.text, message.buttons)
        if in_window and message.text:
            return text_payload(to, message.text)
        if message.template_name:
            return template_payload(
                to, message.template_name, message.template_params, self._template_language
            )
        if not (message.text or message.audio or message.buttons):
            raise ValueError("outbound message has no text, template or audio")
        return None

    async def upload_media(self, data: bytes, mime_type: str) -> str:
        form = upload_form(mime_type)
        files = {"file": ("voice.ogg", data, form["type"])}
        body = await self._request(
            "POST", f"{self._base}/{self._phone_number_id}/media", data=form, files=files
        )
        media_id = json_object(body, integration=INTEGRATION).get("id")
        if not isinstance(media_id, str) or not media_id:
            raise IntegrationError(INTEGRATION, "media upload returned no id")
        return media_id

    async def _post_message(self, payload: dict[str, Any]) -> str:
        response = await self._request("POST", f"{self._base}/{self._phone_number_id}/messages", json=payload)
        messages = json_object(response, integration=INTEGRATION).get("messages")
        first = messages[0] if isinstance(messages, list) and messages else None
        message_id = first.get("id") if isinstance(first, dict) else None
        if not isinstance(message_id, str) or not message_id:
            raise IntegrationError(INTEGRATION, "send returned no message id")
        return message_id

    # ------------------------------------------------------------------ media

    async def download_media(self, media_id: str) -> InboundMedia:
        if not _MEDIA_ID.match(media_id):
            raise IntegrationError(INTEGRATION, "invalid media id")
        meta = json_object(await self._request("GET", f"{self._base}/{media_id}"), integration=INTEGRATION)
        url, mime = meta.get("url"), meta.get("mime_type")
        if not isinstance(url, str) or not url.startswith("https://") or not isinstance(mime, str):
            raise IntegrationError(INTEGRATION, "media lookup returned no url")
        response = await self._request("GET", url)
        if len(response.content) > MAX_MEDIA_BYTES:
            raise IntegrationError(INTEGRATION, "media larger than 5 MB")
        if not response.content:
            raise IntegrationError(INTEGRATION, "media was empty")
        return InboundMedia(data=response.content, mime_type=mime.split(";", 1)[0].strip())

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._token}"}
        async with httpx.AsyncClient(timeout=self._timeout_s, transport=self._transport) as client:
            return await http_request(
                client,
                method,
                url,
                integration=INTEGRATION,
                policy=self._policy,
                sleep=self._sleep,
                headers=headers,
                **kwargs,
            )
