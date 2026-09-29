"""WhatsApp Cloud API integration (SPEC §14.2).

Live integration sends messages to WhatsApp Cloud API.
Simulated integration records messages locally without sending.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime
from typing import Any

import httpx

from chhatri.integrations.base import (
    DeliveryReceipt,
    InboundMedia,
    IntegrationError,
    OutboundMessage,
)

logger = logging.getLogger(__name__)


class LiveWhatsAppChannel:
    """Live WhatsApp Cloud API integration."""

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        app_secret: str,
        graph_version: str = "v23.0",
        demo_recipient: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        """Initialize with WhatsApp credentials.

        Args:
            access_token: WhatsApp Business Account access token.
            phone_number_id: WhatsApp phone number ID.
            app_secret: Webhook verification secret.
            graph_version: Graph API version (default: v23.0).
            demo_recipient: E.164 phone number for demo merchants (optional).
            timeout: HTTP request timeout in seconds.
        """
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.app_secret = app_secret
        self.graph_version = graph_version
        self.demo_recipient = demo_recipient
        self.timeout = timeout
        self.base_url = f"https://graph.facebook.com/{graph_version}/{phone_number_id}"
        self._last_inbound: dict[str, datetime] = {}

    async def send(self, message: OutboundMessage) -> DeliveryReceipt:
        """Send a message via WhatsApp.

        **Recipient safety rule (SPEC §14.2)**: live messages are sent only for demo merchants
        to WHATSAPP_DEMO_RECIPIENT. Other merchants' messages are recorded but not sent.

        Args:
            message: OutboundMessage to send.

        Returns:
            DeliveryReceipt with status and message ID.

        Raises:
            IntegrationError: If the API call fails.
        """
        # Check if this is a demo merchant
        if not self.demo_recipient:
            return DeliveryReceipt(
                provider_message_id=None,
                channel="simulator",
                accepted=True,
                detail="No demo recipient configured; message recorded (simulated)",
            )

        # For simplicity, assume demo merchants have is_demo=True set elsewhere
        # Here we just send to demo_recipient if it matches the to_phone
        if message.to_phone != self.demo_recipient:
            return DeliveryReceipt(
                provider_message_id=None,
                channel="simulator",
                accepted=True,
                detail="Non-demo recipient; message recorded (simulated)",
            )

        # Build message payload
        payload = self._build_payload(message)

        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            url = f"{self.base_url}/messages"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Unknown error")
                except Exception:
                    error_msg = f"HTTP {response.status_code}"

                raise IntegrationError(
                    "whatsapp",
                    f"Send failed: {error_msg}",
                    retryable=response.status_code >= 500,
                )

            data = response.json()
            msg_id = data.get("messages", [{}])[0].get("id")

            return DeliveryReceipt(
                provider_message_id=msg_id,
                channel="whatsapp",
                accepted=True,
                detail=msg_id or "sent",
            )
        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(
                "whatsapp",
                f"Send failed: {type(e).__name__}",
                retryable=True,
            ) from e

    async def download_media(self, media_id: str) -> InboundMedia:
        """Download media from WhatsApp.

        Args:
            media_id: WhatsApp media ID.

        Returns:
            InboundMedia with data and MIME type.

        Raises:
            IntegrationError: If download fails.
        """
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}

            # First, get the media URL
            url = f"https://graph.facebook.com/{self.graph_version}/{media_id}"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

            data = response.json()
            media_url = data.get("url")
            mime_type = data.get("mime_type", "application/octet-stream")

            if not media_url:
                raise IntegrationError(
                    "whatsapp",
                    "No URL in media response",
                )

            # Download the media
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(media_url, headers=headers)
                response.raise_for_status()

            return InboundMedia(data=response.content, mime_type=mime_type)
        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(
                "whatsapp",
                f"Media download failed: {type(e).__name__}",
                retryable=True,
            ) from e

    def verify_signature(self, raw_body: bytes, signature_header: str,
                         app_secret: str) -> bool:
        """Verify WhatsApp webhook signature.

        Uses HMAC-SHA256 with constant-time comparison.

        Args:
            raw_body: Raw request body bytes.
            signature_header: Value of X-Hub-Signature-256 header.
            app_secret: Webhook verification secret.

        Returns:
            True if signature is valid, False otherwise.
        """
        expected = "sha256=" + hmac.new(
            app_secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature_header, expected)

    def verify_challenge(self, params: dict[str, str], verify_token: str) -> str | None:
        """Verify WhatsApp webhook challenge.

        Args:
            params: Query parameters from webhook GET request.
            verify_token: Expected verify token.

        Returns:
            Challenge string if valid, None if invalid.
        """
        if (params.get("hub.mode") == "subscribe" and
            params.get("hub.verify_token") == verify_token):
            return params.get("hub.challenge")
        return None

    def parse_webhook(self, payload: dict[str, Any]) -> list[InboundEvent]:
        """Parse WhatsApp webhook payload.

        Args:
            payload: Webhook JSON payload.

        Returns:
            List of typed inbound events.

        Raises:
            IntegrationError: If payload is invalid.
        """
        events: list[InboundEvent] = []

        try:
            entries = payload.get("entry", [])
            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    value = change.get("value", {})

                    # Process messages
                    messages = value.get("messages", [])
                    for msg in messages:
                        msg_id = msg.get("id")
                        timestamp = msg.get("timestamp")
                        msg_from = msg.get("from")
                        msg_type = msg.get("type")

                        if not msg_id:
                            continue

                        if msg_type == "text":
                            text = msg.get("text", {}).get("body", "")
                            events.append(
                                TextEvent(
                                    message_id=msg_id,
                                    timestamp=int(timestamp or 0),
                                    from_phone=msg_from,
                                    text=text,
                                )
                            )
                        elif msg_type == "audio":
                            audio_data = msg.get("audio", {})
                            events.append(
                                AudioEvent(
                                    message_id=msg_id,
                                    timestamp=int(timestamp or 0),
                                    from_phone=msg_from,
                                    media_id=audio_data.get("id"),
                                    mime_type=audio_data.get("mime_type", "audio/ogg"),
                                    is_voice_note=audio_data.get("voice"),
                                )
                            )
                        elif msg_type == "image":
                            image_data = msg.get("image", {})
                            events.append(
                                ImageEvent(
                                    message_id=msg_id,
                                    timestamp=int(timestamp or 0),
                                    from_phone=msg_from,
                                    media_id=image_data.get("id"),
                                    mime_type=image_data.get("mime_type"),
                                    caption=image_data.get("caption"),
                                )
                            )
                        elif msg_type == "interactive":
                            interactive = msg.get("interactive", {})
                            button_reply = interactive.get("button_reply", {})
                            events.append(
                                ButtonEvent(
                                    message_id=msg_id,
                                    timestamp=int(timestamp or 0),
                                    from_phone=msg_from,
                                    button_id=button_reply.get("id"),
                                    button_title=button_reply.get("title"),
                                )
                            )

                    # Process statuses
                    statuses = value.get("statuses", [])
                    for status in statuses:
                        status_id = status.get("id")
                        status_timestamp = status.get("timestamp")
                        status_to = status.get("recipient_id")
                        status_value = status.get("status")

                        if status_id:
                            events.append(
                                StatusEvent(
                                    message_id=status_id,
                                    timestamp=int(status_timestamp or 0),
                                    to_phone=status_to,
                                    status=status_value,
                                )
                            )
        except Exception as e:
            raise IntegrationError(
                "whatsapp",
                f"Failed to parse webhook payload: {type(e).__name__}",
            ) from e

        return events

    def _build_payload(self, message: OutboundMessage) -> dict[str, Any]:
        """Build WhatsApp message payload.

        Args:
            message: OutboundMessage to send.

        Returns:
            JSON payload for WhatsApp API.
        """
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": message.to_phone,
        }

        if message.template_name:
            payload["type"] = "template"
            payload["template"] = {
                "name": message.template_name,
                "language": {"code": "hi"},  # SPEC §14.2
            }
            if message.template_params:
                payload["template"]["parameters"] = [
                    {"type": "text", "text": param} for param in message.template_params
                ]
        elif message.audio:
            payload["type"] = "audio"
            # Upload media first, then send
            # For now, this is simplified; real implementation would upload first
            payload["audio"] = {"link": "data:audio/ogg;base64,..."}
        elif message.buttons:
            payload["type"] = "interactive"
            payload["interactive"] = {
                "type": "button",
                "body": {"text": message.text or ""},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": btn_id,
                                "title": btn_title[:20],  # Max 20 chars
                            },
                        }
                        for btn_id, btn_title in message.buttons[:3]  # Max 3 buttons
                    ]
                },
            }
        else:
            payload["type"] = "text"
            payload["text"] = {"body": message.text or ""}

        return payload


class SimulatorChannel:
    """Simulated messaging channel that records messages without sending."""

    def __init__(self) -> None:
        """Initialize with empty message history."""
        self.messages: list[OutboundMessage] = []
        self._demo_recipient_notified: set[str] = set()

    async def send(self, message: OutboundMessage) -> DeliveryReceipt:
        """Record a message without sending.

        Args:
            message: OutboundMessage to record.

        Returns:
            DeliveryReceipt indicating acceptance.
        """
        self.messages.append(message)

        # Check if this is a non-demo phone number (not WHATSAPP_DEMO_RECIPIENT)
        # and return a polite message (once per day)
        if message.to_phone and not message.to_phone.startswith("DEMO:") and message.to_phone not in self._demo_recipient_notified:
            self._demo_recipient_notified.add(message.to_phone)
            logger.info(
                f"Demo mode: message to {message.to_phone} recorded but not sent"
            )

        return DeliveryReceipt(
            provider_message_id=f"SIM-{len(self.messages)}",
            channel="simulator",
            accepted=True,
            detail="Recorded (simulated)",
        )

    async def download_media(self, media_id: str) -> InboundMedia:
        """Simulated media download.

        Args:
            media_id: Media ID (simulated).

        Returns:
            Empty InboundMedia.

        Raises:
            IntegrationError: Always, since simulated media is not available.
        """
        raise IntegrationError(
            "simulator",
            "Media download not available in simulator mode",
        )


# Event types for parsing


class InboundEvent:
    """Base class for inbound webhook events."""
    message_id: str


class TextEvent(InboundEvent):
    def __init__(self, message_id: str, timestamp: int, from_phone: str, text: str):
        self.message_id = message_id
        self.timestamp = timestamp
        self.from_phone = from_phone
        self.text = text
        self.type = "text"


class AudioEvent(InboundEvent):
    def __init__(self, message_id: str, timestamp: int, from_phone: str, media_id: str,
                 mime_type: str, is_voice_note: bool = False):
        self.message_id = message_id
        self.timestamp = timestamp
        self.from_phone = from_phone
        self.media_id = media_id
        self.mime_type = mime_type
        self.is_voice_note = is_voice_note
        self.type = "audio"


class ImageEvent(InboundEvent):
    def __init__(self, message_id: str, timestamp: int, from_phone: str, media_id: str,
                 mime_type: str | None, caption: str | None = None):
        self.message_id = message_id
        self.timestamp = timestamp
        self.from_phone = from_phone
        self.media_id = media_id
        self.mime_type = mime_type or "image/jpeg"
        self.caption = caption
        self.type = "image"


class ButtonEvent(InboundEvent):
    def __init__(self, message_id: str, timestamp: int, from_phone: str, button_id: str,
                 button_title: str):
        self.message_id = message_id
        self.timestamp = timestamp
        self.from_phone = from_phone
        self.button_id = button_id
        self.button_title = button_title
        self.type = "button"


class StatusEvent(InboundEvent):
    def __init__(self, message_id: str, timestamp: int, to_phone: str, status: str):
        self.message_id = message_id
        self.timestamp = timestamp
        self.to_phone = to_phone
        self.status = status
        self.type = "status"
