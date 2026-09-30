"""WhatsApp Cloud API webhook: verification and parsing (SPEC §14.2).

- GET: `hub.mode == "subscribe"` and `hub.verify_token == WHATSAPP_VERIFY_TOKEN` → echo `hub.challenge`
  (text/plain 200), else 403 — `verify_challenge` returns the challenge or None.
- POST: `X-Hub-Signature-256 == "sha256=" + hmac_sha256(app_secret, raw_body)` checked with
  `hmac.compare_digest` on the **raw bytes** before parsing — `verify_signature`.
- Messages at `entry[].changes[].value.messages[]` (text, audio, image, interactive button reply);
  statuses at `value.statuses[]`. Malformed items are skipped with a warning so the route can always
  answer 200 quickly; a body that is not a JSON object raises IntegrationError.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from chhatri.clock import IST
from chhatri.integrations.base import IntegrationError

logger = logging.getLogger(__name__)

SIGNATURE_PREFIX = "sha256="
SUBSCRIBE_MODE = "subscribe"
DEFAULT_AUDIO_MIME = "audio/ogg"
DEFAULT_IMAGE_MIME = "image/jpeg"


@dataclass(frozen=True, slots=True)
class InboundEvent:
    """Base of every parsed webhook item; `message_id` is WhatsApp's `wamid…`."""

    message_id: str
    at: datetime


@dataclass(frozen=True, slots=True)
class TextEvent(InboundEvent):
    from_phone: str
    text: str


@dataclass(frozen=True, slots=True)
class AudioEvent(InboundEvent):
    from_phone: str
    media_id: str
    mime_type: str
    voice: bool


@dataclass(frozen=True, slots=True)
class ImageEvent(InboundEvent):
    from_phone: str
    media_id: str
    mime_type: str
    caption: str | None


@dataclass(frozen=True, slots=True)
class ButtonEvent(InboundEvent):
    from_phone: str
    button_id: str
    title: str


@dataclass(frozen=True, slots=True)
class UnsupportedEvent(InboundEvent):
    """A message type Chhatri does not handle (sticker, location, …); the merchant gets help text."""

    from_phone: str
    kind: str


@dataclass(frozen=True, slots=True)
class StatusEvent(InboundEvent):
    recipient: str
    status: str  # sent | delivered | read | failed


MessageEvent = TextEvent | AudioEvent | ImageEvent | ButtonEvent | UnsupportedEvent


def verify_signature(app_secret: str, raw_body: bytes, signature_header: str | None) -> bool:
    """Constant-time check of `X-Hub-Signature-256` over the raw request bytes."""
    if not app_secret or not signature_header or not signature_header.startswith(SIGNATURE_PREFIX):
        return False
    expected = SIGNATURE_PREFIX + hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_header.encode("utf-8", "replace"), expected.encode())


def verify_challenge(params: Mapping[str, str], verify_token: str) -> str | None:
    """Return `hub.challenge` for a valid subscription request, else None (→ HTTP 403)."""
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token") or ""
    challenge = params.get("hub.challenge") or ""
    if mode != SUBSCRIBE_MODE or not verify_token or not challenge:
        return None
    if not hmac.compare_digest(token.encode("utf-8", "replace"), verify_token.encode()):
        return None
    return challenge


def _timestamp(raw: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(raw), tz=IST)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _str(mapping: Mapping[str, Any], key: str) -> str | None:
    value = mapping.get(key)
    return value if isinstance(value, str) and value else None


def _dict(mapping: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = mapping.get(key)
    return value if isinstance(value, Mapping) else {}


def _message_body(kind: str, head: tuple[str, datetime, str], msg: Mapping[str, Any]) -> MessageEvent | None:
    message_id, at, sender = head
    if kind == "text":
        body = _str(_dict(msg, "text"), "body")
        return TextEvent(message_id, at, sender, body) if body else None
    if kind == "audio":
        audio = _dict(msg, "audio")
        media_id = _str(audio, "id")
        mime = _str(audio, "mime_type") or DEFAULT_AUDIO_MIME
        return (
            AudioEvent(message_id, at, sender, media_id, mime, audio.get("voice") is True)
            if media_id
            else None
        )
    if kind == "image":
        image = _dict(msg, "image")
        media_id = _str(image, "id")
        mime = _str(image, "mime_type") or DEFAULT_IMAGE_MIME
        return (
            ImageEvent(message_id, at, sender, media_id, mime, _str(image, "caption")) if media_id else None
        )
    if kind == "interactive":
        reply = _dict(_dict(msg, "interactive"), "button_reply")
        button_id, title = _str(reply, "id"), _str(reply, "title")
        return ButtonEvent(message_id, at, sender, button_id, title) if button_id and title else None
    return UnsupportedEvent(message_id, at, sender, kind)


def parse_message(msg: Any) -> MessageEvent | None:
    """One `value.messages[]` item → event, or None (logged) when malformed."""
    if not isinstance(msg, Mapping):
        logger.warning("whatsapp webhook: message item is not an object; skipped")
        return None
    message_id, sender, kind = _str(msg, "id"), _str(msg, "from"), _str(msg, "type")
    at = _timestamp(msg.get("timestamp"))
    if not (message_id and sender and kind and at):
        logger.warning("whatsapp webhook: message missing id/from/type/timestamp; skipped")
        return None
    event = _message_body(kind, (message_id, at, sender), msg)
    if event is None:
        logger.warning("whatsapp webhook: %s message %s missing its payload; skipped", kind, message_id)
    return event


def parse_status(item: Any) -> StatusEvent | None:
    """One `value.statuses[]` item → StatusEvent, or None (logged) when malformed."""
    if not isinstance(item, Mapping):
        logger.warning("whatsapp webhook: status item is not an object; skipped")
        return None
    message_id, recipient, status = _str(item, "id"), _str(item, "recipient_id"), _str(item, "status")
    at = _timestamp(item.get("timestamp"))
    if not (message_id and recipient and status and at):
        logger.warning("whatsapp webhook: status missing fields; skipped")
        return None
    return StatusEvent(message_id, at, recipient, status)


def _list(mapping: Mapping[str, Any], key: str) -> list[Any]:
    value = mapping.get(key)
    return value if isinstance(value, list) else []


def _values(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values: list[Mapping[str, Any]] = []
    for entry in _list(payload, "entry"):
        changes = _list(entry, "changes") if isinstance(entry, Mapping) else []
        values.extend(_dict(change, "value") for change in changes if isinstance(change, Mapping))
    return [value for value in values if value]


def parse_webhook(payload: Any) -> tuple[MessageEvent | StatusEvent, ...]:
    """All messages and statuses in a webhook body, in delivery order."""
    if not isinstance(payload, Mapping):
        raise IntegrationError("whatsapp", "webhook body is not a JSON object")
    events: list[MessageEvent | StatusEvent] = []
    for value in _values(payload):
        for msg in _list(value, "messages"):
            parsed = parse_message(msg)
            if parsed is not None:
                events.append(parsed)
        for item in _list(value, "statuses"):
            status = parse_status(item)
            if status is not None:
                events.append(status)
    return tuple(events)
