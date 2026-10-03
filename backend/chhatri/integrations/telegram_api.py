"""Telegram Bot API client over httpx (long polling, no webhook, no public URL).

Base `https://api.telegram.org/bot<token>/<method>`; every call is a JSON POST (multipart for files) answered with
`{"ok": true, "result": …}`. Methods: `getMe`, `getUpdates` (offset + long-poll timeout), `sendMessage` (plain text, with an
inline keyboard for quick replies), `sendPhoto`, `sendVoice` (OGG/Opus), `answerCallbackQuery`, `getFile` and the file
download, `deleteWebhook` (a leftover webhook would make `getUpdates` answer 409).

The token is part of every URL, so it is guarded in three ways: `IntegrationError` messages hold the method name and an HTTP
status or exception type only (never a URL or a Telegram description), `repr()` of the client shows nothing, and the
`httpx` loggers, which print each request URL at INFO, are raised to WARNING when this module is imported.
Retries follow SPEC §14 (429 and 5xx only, via `chhatri.integrations.retry`); `getUpdates` makes one attempt, because the
poller owns its backoff. A 429's `retry_after` is waited for, up to `RETRY_AFTER_CAP_S` (10 s).
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

import httpx

from chhatri.integrations.base import InboundMedia, IntegrationError
from chhatri.integrations.retry import (
    DEFAULT_RETRY,
    DEFAULT_TIMEOUT_S,
    RetryPolicy,
    Sleep,
    http_request,
    json_object,
)

for _noisy in ("httpx", "httpcore"):  # their INFO lines carry the request URL, and the URL carries the token
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

__all__ = [
    "API_BASE",
    "INTEGRATION",
    "MAX_BUTTONS",
    "FileTooLarge",
    "MAX_CALLBACK_BYTES",
    "MAX_FILE_BYTES",
    "MAX_TEXT_CHARS",
    "TelegramBotClient",
    "TelegramBotInfo",
    "TelegramFile",
    "inline_keyboard",
]

INTEGRATION: Final = "telegram"
API_BASE: Final = "https://api.telegram.org"
MAX_TEXT_CHARS: Final = 4096
MAX_CAPTION_CHARS: Final = 1024
MAX_BUTTONS: Final = 3
MAX_CALLBACK_BYTES: Final = 64  # Telegram's limit for `callback_data`
MAX_FILE_BYTES: Final = 5 * 1024 * 1024  # SPEC §19: uploads <= 5 MB, like WhatsApp media
RETRY_AFTER_CAP_S: Final = (
    10.0  # a 429's retry_after is honoured up to this; a longer ban fails the send instead
)
LONG_POLL_MARGIN_S: Final = 10.0  # the HTTP timeout of a long poll is the poll timeout plus this
ALLOWED_UPDATES: Final = ("message", "callback_query")
_FILE_PATH: Final = re.compile(r"^[A-Za-z0-9_./-]{1,256}$")
_NO_RETRY: Final = RetryPolicy(max_attempts=1)


@dataclass(frozen=True, slots=True)
class TelegramBotInfo:
    """`getMe`: who the token belongs to."""

    id: int
    username: str
    first_name: str


@dataclass(frozen=True, slots=True)
class TelegramFile:
    """`getFile`: where a file can be downloaded from, and how big it is when Telegram says."""

    path: str
    size: int | None


class FileTooLarge(IntegrationError):
    """The merchant sent a file over `MAX_FILE_BYTES`: nothing was downloaded (the inbox says so)."""


def inline_keyboard(buttons: Sequence[tuple[str, str]]) -> dict[str, Any]:
    """`reply_markup` with one quick-reply button per row; each button is `(callback id, title)`."""
    if not buttons or len(buttons) > MAX_BUTTONS:
        raise ValueError(f"quick replies must number 1..{MAX_BUTTONS}")
    rows = []
    for callback_id, title in buttons:
        if not callback_id or not title or len(callback_id.encode()) > MAX_CALLBACK_BYTES:
            raise ValueError(f"a quick reply needs a title and an id of at most {MAX_CALLBACK_BYTES} bytes")
        rows.append([{"text": title, "callback_data": callback_id}])
    return {"inline_keyboard": rows}


def _checked_text(text: str | None, limit: int = MAX_TEXT_CHARS) -> str:
    if text is None or not text.strip():
        raise ValueError("message text is empty")
    if len(text) > limit:
        raise ValueError(f"message text longer than {limit} characters")
    return text


def _result(body: Mapping[str, Any], method: str) -> Any:
    if body.get("ok") is not True:
        code = body.get("error_code")
        raise IntegrationError(
            INTEGRATION, f"{method} rejected" + (f" (error {code})" if isinstance(code, int) else "")
        )
    return body.get("result")


def _message_id(result: Any, method: str) -> int:
    message_id = result.get("message_id") if isinstance(result, Mapping) else None
    if not isinstance(message_id, int):
        raise IntegrationError(INTEGRATION, f"{method} returned no message id")
    return message_id


class TelegramBotClient:
    """The Bot API calls Chhatri needs, with the SPEC §14 timeout and retry rules."""

    def __init__(
        self,
        token: str,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        transport: httpx.AsyncBaseTransport | None = None,
        policy: RetryPolicy = DEFAULT_RETRY,
        sleep: Sleep = asyncio.sleep,
        api_base: str = API_BASE,
    ) -> None:
        if not token or not token.strip():
            raise ValueError("a bot token is required")
        self._token = token.strip()
        self._timeout_s = timeout_s
        self._transport = transport
        self._policy = policy
        self._sleep = sleep
        self._api_base = api_base.rstrip("/")

    def __repr__(self) -> str:
        return "TelegramBotClient()"

    # ------------------------------------------------------------------ identity and polling

    async def get_me(self) -> TelegramBotInfo:
        result = _result(await self._call("getMe"), "getMe")
        if not isinstance(result, Mapping) or not isinstance(result.get("id"), int):
            raise IntegrationError(INTEGRATION, "getMe returned no bot")
        username, first_name = result.get("username"), result.get("first_name")
        return TelegramBotInfo(
            id=result["id"],
            username=username if isinstance(username, str) else "",
            first_name=first_name if isinstance(first_name, str) else "",
        )

    async def delete_webhook(self) -> None:
        """Make sure no webhook is set, or `getUpdates` answers 409. Pending updates are kept."""
        _result(await self._call("deleteWebhook", {"drop_pending_updates": False}), "deleteWebhook")

    async def get_updates(self, *, offset: int | None, timeout_s: int) -> list[dict[str, Any]]:
        """One long poll: updates with `update_id >= offset`, waiting up to `timeout_s` seconds for the first one."""
        if timeout_s < 0:
            raise ValueError("timeout_s must not be negative")
        payload: dict[str, Any] = {"timeout": timeout_s, "allowed_updates": list(ALLOWED_UPDATES)}
        if offset is not None:
            payload["offset"] = offset
        body = await self._call(
            "getUpdates", payload, http_timeout_s=timeout_s + LONG_POLL_MARGIN_S, policy=_NO_RETRY
        )
        result = _result(body, "getUpdates")
        if not isinstance(result, list):
            raise IntegrationError(INTEGRATION, "getUpdates returned no list")
        return [item for item in result if isinstance(item, dict)]

    # ------------------------------------------------------------------ sending

    async def send_message(
        self, chat_id: int, text: str | None, *, buttons: Sequence[tuple[str, str]] = ()
    ) -> int:
        """Plain text (no parse mode, so a merchant's text can never be read as markup); returns the message id."""
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": _checked_text(text),
            "disable_web_page_preview": True,
        }
        if buttons:
            payload["reply_markup"] = inline_keyboard(buttons)
        return _message_id(_result(await self._call("sendMessage", payload), "sendMessage"), "sendMessage")

    async def send_photo(
        self, chat_id: int, photo: bytes, *, mime_type: str = "image/jpeg", caption: str | None = None
    ) -> int:
        if not photo:
            raise ValueError("photo is empty")
        data: dict[str, Any] = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = _checked_text(caption, MAX_CAPTION_CHARS)
        files = {"photo": ("photo.jpg", photo, mime_type)}
        body = await self._call("sendPhoto", data=data, files=files)
        return _message_id(_result(body, "sendPhoto"), "sendPhoto")

    async def send_voice(self, chat_id: int, audio: bytes) -> int:
        """A voice note; Telegram wants OGG with the Opus codec."""
        if not audio:
            raise ValueError("voice note is empty")
        files = {"voice": ("voice.ogg", audio, "audio/ogg")}
        body = await self._call("sendVoice", data={"chat_id": str(chat_id)}, files=files)
        return _message_id(_result(body, "sendVoice"), "sendVoice")

    async def answer_callback_query(self, callback_query_id: str) -> None:
        """Stop the button's spinner; nothing is shown to the merchant."""
        _result(
            await self._call("answerCallbackQuery", {"callback_query_id": callback_query_id}),
            "answerCallbackQuery",
        )

    # ------------------------------------------------------------------ files

    async def get_file(self, file_id: str) -> TelegramFile:
        result = _result(await self._call("getFile", {"file_id": file_id}), "getFile")
        path = result.get("file_path") if isinstance(result, Mapping) else None
        if not isinstance(path, str) or not _FILE_PATH.match(path) or ".." in path.split("/"):
            raise IntegrationError(INTEGRATION, "getFile returned no usable path")
        size = result.get("file_size") if isinstance(result, Mapping) else None
        return TelegramFile(path=path, size=size if isinstance(size, int) else None)

    async def download_file(self, file_id: str, *, mime_type: str) -> InboundMedia:
        """`getFile`, then the bytes (at most 5 MB). `mime_type` is what the update said; the caller validates by content."""
        meta = await self.get_file(file_id)
        if meta.size is not None and meta.size > MAX_FILE_BYTES:
            raise FileTooLarge(INTEGRATION, "file larger than 5 MB")
        response = await self._request("GET", f"{self._api_base}/file/bot{self._token}/{meta.path}")
        if len(response.content) > MAX_FILE_BYTES:
            raise FileTooLarge(INTEGRATION, "file larger than 5 MB")
        if not response.content:
            raise IntegrationError(INTEGRATION, "file was empty")
        return InboundMedia(data=response.content, mime_type=mime_type.split(";", 1)[0].strip())

    # ------------------------------------------------------------------ plumbing

    async def _call(
        self,
        method: str,
        payload: Mapping[str, Any] | None = None,
        *,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, Any] | None = None,
        http_timeout_s: float | None = None,
        policy: RetryPolicy | None = None,
    ) -> Mapping[str, Any]:
        kwargs: dict[str, Any] = {}
        if files is not None:
            kwargs.update(data=dict(data or {}), files=dict(files))
        else:
            kwargs["json"] = dict(payload or {})
        response = await self._request(
            "POST",
            f"{self._api_base}/bot{self._token}/{method}",
            http_timeout_s=http_timeout_s,
            policy=policy,
            **kwargs,
        )
        return json_object(response, integration=INTEGRATION)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        http_timeout_s: float | None = None,
        policy: RetryPolicy | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        timeout = self._timeout_s if http_timeout_s is None else http_timeout_s
        async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
            return await http_request(
                client,
                method,
                url,
                integration=INTEGRATION,
                policy=policy or self._policy,
                sleep=self._sleep,
                retry_after_cap_s=RETRY_AFTER_CAP_S,
                **kwargs,
            )
