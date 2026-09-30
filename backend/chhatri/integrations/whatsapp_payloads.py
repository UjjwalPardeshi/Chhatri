"""WhatsApp Cloud API request bodies (SPEC §14.2, §13.7).

`POST /{phone-number-id}/messages` with `messaging_product: "whatsapp"`, `to` and one of
`text | template | interactive | audio`. Reply buttons: at most 3, titles ≤ 20 characters.
Templates are UTILITY templates in language `hi` with body parameters (`chhatri_area_payout`:
name, drop, amount; `chhatri_checkin`: name).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

MESSAGING_PRODUCT = "whatsapp"
MAX_BUTTONS = 3
MAX_BUTTON_TITLE = 20
MAX_TEXT_CHARS = 4096
VOICE_NOTE_MIME = "audio/ogg"  # SPEC §14.2: voice note = OGG/Opus
UPLOADABLE_AUDIO = frozenset({"audio/ogg", "audio/mpeg", "audio/aac", "audio/amr", "audio/mp4"})


def _envelope(to: str, kind: str, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "messaging_product": MESSAGING_PRODUCT,
        "recipient_type": "individual",
        "to": to,
        "type": kind,
        kind: body,
    }


def _checked_text(text: str | None) -> str:
    if text is None or not text.strip():
        raise ValueError("message text is empty")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(f"message text longer than {MAX_TEXT_CHARS} characters")
    return text


def text_payload(to: str, text: str | None) -> dict[str, Any]:
    return _envelope(to, "text", {"preview_url": False, "body": _checked_text(text)})


def template_payload(to: str, name: str, params: Sequence[str], language: str) -> dict[str, Any]:
    if not name:
        raise ValueError("template name is empty")
    template: dict[str, Any] = {"name": name, "language": {"code": language}}
    if params:
        template["components"] = [
            {"type": "body", "parameters": [{"type": "text", "text": str(param)} for param in params]}
        ]
    return _envelope(to, "template", template)


def buttons_payload(to: str, text: str | None, buttons: Sequence[tuple[str, str]]) -> dict[str, Any]:
    if not buttons or len(buttons) > MAX_BUTTONS:
        raise ValueError(f"reply buttons must number 1..{MAX_BUTTONS}")
    replies = []
    for button_id, title in buttons:
        if not button_id or not title or len(title) > MAX_BUTTON_TITLE:
            raise ValueError(f"button titles must be 1..{MAX_BUTTON_TITLE} characters with an id")
        replies.append({"type": "reply", "reply": {"id": button_id, "title": title}})
    interactive = {"type": "button", "body": {"text": _checked_text(text)}, "action": {"buttons": replies}}
    return _envelope(to, "interactive", interactive)


def audio_payload(to: str, media_id: str) -> dict[str, Any]:
    if not media_id:
        raise ValueError("media id is empty")
    return _envelope(to, "audio", {"id": media_id})


def upload_form(mime_type: str) -> dict[str, str]:
    """Multipart fields for `POST /{phone-number-id}/media` (the file part is added separately)."""
    base = mime_type.split(";", 1)[0].strip().lower()
    if base not in UPLOADABLE_AUDIO:
        raise ValueError("unsupported audio type for WhatsApp upload")
    return {"messaging_product": MESSAGING_PRODUCT, "type": base}
