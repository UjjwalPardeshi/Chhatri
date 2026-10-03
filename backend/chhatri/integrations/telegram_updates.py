"""Telegram `getUpdates` items parsed into events (the counterpart of `whatsapp_webhook`).

Only private chats are served: a group or channel message is skipped, so Chhatri never binds a group or answers in one.
A text that starts with `/` is a command (`/start S-0142`, `/stop`, `/help`, with or without `@botname`); a photo is the
largest size Telegram made (an image sent "as a file", a document with an `image/*` type, counts as a photo: the content
is validated after download anyway); a voice note or audio file carries its MIME type (`audio/ogg` for a voice note); a tap on an
inline quick-reply button is a callback. Anything else (sticker, location, document) is `TgUnsupported` and gets help text.
A malformed item is skipped with a warning and never stops the batch.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from chhatri.clock import IST

logger = logging.getLogger(__name__)

__all__ = [
    "TgCallback",
    "TgCommand",
    "TgEvent",
    "TgPhoto",
    "TgText",
    "TgUnsupported",
    "TgVoice",
    "parse_update",
    "parse_updates",
]

DEFAULT_VOICE_MIME: Final = "audio/ogg"
_COMMAND: Final = re.compile(r"^/([A-Za-z0-9_]{1,32})(?:@[A-Za-z0-9_]{1,64})?(?:\s+(.*))?$", re.DOTALL)


@dataclass(frozen=True, slots=True)
class TgEvent:
    """Base of every parsed update: Telegram's `update_id`, the private chat it came from and when."""

    update_id: int
    chat_id: int
    at: datetime


@dataclass(frozen=True, slots=True)
class TgText(TgEvent):
    text: str


@dataclass(frozen=True, slots=True)
class TgCommand(TgEvent):
    command: str  # lowercase, without the slash
    argument: str | None


@dataclass(frozen=True, slots=True)
class TgPhoto(TgEvent):
    file_id: str
    caption: str | None


@dataclass(frozen=True, slots=True)
class TgVoice(TgEvent):
    file_id: str
    mime_type: str


@dataclass(frozen=True, slots=True)
class TgCallback(TgEvent):
    callback_id: str
    data: str


@dataclass(frozen=True, slots=True)
class TgUnsupported(TgEvent):
    kind: str


def _mapping(source: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = source.get(key)
    return value if isinstance(value, Mapping) else {}


def _str(source: Mapping[str, Any], key: str) -> str | None:
    value = source.get(key)
    return value if isinstance(value, str) and value else None


def _int(source: Mapping[str, Any], key: str) -> int | None:
    value = source.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _at(raw: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(raw), tz=IST)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _largest_photo(sizes: Any) -> str | None:
    """The `file_id` of the biggest size of a photo (Telegram lists them smallest first)."""
    if not isinstance(sizes, list):
        return None
    best: tuple[int, str] | None = None
    for size in sizes:
        file_id = _str(size, "file_id") if isinstance(size, Mapping) else None
        area = (_int(size, "width") or 0) * (_int(size, "height") or 0) if file_id else -1
        if file_id and (best is None or area >= best[0]):
            best = (area, file_id)
    return best[1] if best else None


def _image_document(message: Mapping[str, Any]) -> str | None:
    document = _mapping(message, "document")
    mime = (_str(document, "mime_type") or "").lower()
    return _str(document, "file_id") if mime.startswith("image/") else None


def _message_event(update_id: int, message: Mapping[str, Any]) -> TgEvent | None:
    chat = _mapping(message, "chat")
    chat_id, at = _int(chat, "id"), _at(message.get("date"))
    if chat_id is None or at is None:
        return None
    if chat.get("type") != "private":
        logger.info("telegram: update %d is not from a private chat; skipped", update_id)
        return None
    head = (update_id, chat_id, at)
    text = _str(message, "text")
    if text is not None:
        command = _COMMAND.match(text.strip())
        if command:
            argument = (command.group(2) or "").strip() or None
            return TgCommand(*head, command.group(1).lower(), argument)
        return TgText(*head, text)
    photo = _largest_photo(message.get("photo")) or _image_document(message)
    if photo is not None:
        return TgPhoto(*head, photo, _str(message, "caption"))
    for kind in ("voice", "audio"):
        media = _mapping(message, kind)
        file_id = _str(media, "file_id")
        if file_id:
            return TgVoice(*head, file_id, _str(media, "mime_type") or DEFAULT_VOICE_MIME)
    kind = next((key for key in message if key not in {"message_id", "from", "chat", "date"}), "unknown")
    return TgUnsupported(*head, str(kind))


def _callback_event(update_id: int, query: Mapping[str, Any]) -> TgEvent | None:
    callback_id, data = _str(query, "id"), _str(query, "data")
    message = _mapping(query, "message")
    chat = _mapping(message, "chat")
    chat_id = _int(chat, "id") if chat.get("type") == "private" else None
    at = _at(message.get("date")) or datetime.now(tz=IST)
    if callback_id is None or data is None or chat_id is None:
        return None
    return TgCallback(update_id, chat_id, at, callback_id, data)


def parse_update(update: Any) -> TgEvent | None:
    """One `getUpdates` item → event, or None (logged) when it is malformed or not for Chhatri."""
    if not isinstance(update, Mapping):
        logger.warning("telegram: update is not an object; skipped")
        return None
    update_id = _int(update, "update_id")
    if update_id is None:
        logger.warning("telegram: update has no update_id; skipped")
        return None
    if "callback_query" in update:
        event = _callback_event(update_id, _mapping(update, "callback_query"))
    else:
        event = _message_event(update_id, _mapping(update, "message"))
    if event is None:
        logger.info("telegram: update %d carries nothing Chhatri handles; skipped", update_id)
    return event


def parse_updates(updates: Any) -> tuple[TgEvent, ...]:
    """Every handled event of a `getUpdates` result, in delivery order."""
    if not isinstance(updates, list):
        return ()
    return tuple(event for event in map(parse_update, updates) if event is not None)
