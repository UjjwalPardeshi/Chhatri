"""A fake Telegram Bot API behind `httpx.MockTransport`: no test ever calls the real one.

Serves `/bot<token>/<method>` (getMe, getUpdates with offset semantics, sendMessage, sendVoice, sendPhoto,
getFile, answerCallbackQuery, deleteWebhook) and `/file/bot<token>/<path>`; records every call, and can be told to fail a
method with an HTTP status a given number of times.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Final

import httpx

TOKEN: Final = "123456:TEST-token-never-print-me"  # noqa: S105 - a fixture, not a credential
BOT_USERNAME: Final = "ChhatriDemoBot"
_BOT_PATH = re.compile(r"^/bot(?P<token>[^/]+)/(?P<method>[A-Za-z]+)$")
_FILE_PATH = re.compile(r"^/file/bot(?P<token>[^/]+)/(?P<path>.+)$")


@dataclass(frozen=True)
class Call:
    method: str
    payload: dict[str, Any]
    fields: tuple[str, ...] = ()  # multipart part names (sendVoice, sendPhoto)
    timeout: float | None = None


@dataclass
class FakeBotApi:
    updates: list[dict[str, Any]] = field(default_factory=list)
    files: dict[str, bytes] = field(default_factory=dict)  # file_id -> bytes
    file_sizes: dict[str, int] = field(default_factory=dict)  # file_id -> size told by getFile
    calls: list[Call] = field(default_factory=list)
    failures: dict[str, list[int]] = field(default_factory=dict)  # method -> HTTP statuses, consumed in order
    next_message_id: int = 100

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def sent(self, method: str) -> list[Call]:
        return [call for call in self.calls if call.method == method]

    def fail(self, method: str, *statuses: int) -> None:
        self.failures.setdefault(method, []).extend(statuses)

    def queue(self, *updates: dict[str, Any]) -> None:
        self.updates.extend(updates)

    # ------------------------------------------------------------------ server

    def _handle(self, request: httpx.Request) -> httpx.Response:
        file_match = _FILE_PATH.match(request.url.path)
        if file_match:
            return self._download(file_match["token"], file_match["path"])
        match = _BOT_PATH.match(request.url.path)
        if match is None or match["token"] != TOKEN:
            return httpx.Response(401, json={"ok": False, "error_code": 401, "description": "Unauthorized"})
        method = match["method"]
        payload, names = self._payload(request)
        timeout = request.extensions.get("timeout", {}).get("read")
        self.calls.append(Call(method, payload, names, timeout))
        queued = self.failures.get(method)
        if queued:
            status = queued.pop(0)
            return httpx.Response(status, json={"ok": False, "error_code": status, "description": "boom"})
        return httpx.Response(200, json=self._result(method, payload))

    @staticmethod
    def _payload(request: httpx.Request) -> tuple[dict[str, Any], tuple[str, ...]]:
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/json") and request.content:
            return json.loads(request.content), ()
        names = tuple(re.findall(rb'name="([a-z_]+)"', request.content))
        decoded = tuple(name.decode() for name in names)
        chat = re.search(rb'name="chat_id"\r\n\r\n(-?\d+)', request.content)
        return ({"chat_id": int(chat.group(1))} if chat else {}), decoded

    def _result(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if method == "getMe":
            return {
                "ok": True,
                "result": {"id": 42, "is_bot": True, "first_name": "Chhatri", "username": BOT_USERNAME},
            }
        if method == "getUpdates":
            offset = payload.get("offset")
            batch = [u for u in self.updates if offset is None or u["update_id"] >= offset]
            self.updates = batch  # Telegram forgets updates below the offset
            return {"ok": True, "result": batch}
        if method in {"sendMessage", "sendVoice", "sendPhoto"}:
            self.next_message_id += 1
            return {"ok": True, "result": {"message_id": self.next_message_id}}
        if method == "getFile":
            file_id = payload["file_id"]
            if file_id not in self.files:
                return {"ok": False, "error_code": 400, "description": "wrong file_id"}
            size = self.file_sizes.get(file_id, len(self.files[file_id]))
            return {
                "ok": True,
                "result": {"file_id": file_id, "file_path": f"files/{file_id}.bin", "file_size": size},
            }
        return {"ok": True, "result": True}

    def _download(self, token: str, path: str) -> httpx.Response:
        if token != TOKEN:
            return httpx.Response(401)
        file_id = path.removeprefix("files/").removesuffix(".bin")
        data = self.files.get(file_id)
        return httpx.Response(200, content=data) if data is not None else httpx.Response(404)


def text_update(update_id: int, chat_id: int, text: str, *, date: int = 1_760_000_000) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "from": {"id": chat_id, "is_bot": False, "first_name": "Tester"},
            "chat": {"id": chat_id, "type": "private", "first_name": "Tester"},
            "date": date,
            "text": text,
        },
    }


def photo_update(update_id: int, chat_id: int, file_ids: tuple[str, ...]) -> dict[str, Any]:
    update = text_update(update_id, chat_id, "x")
    del update["message"]["text"]
    update["message"]["photo"] = [
        {"file_id": fid, "width": 100 * (i + 1), "height": 100 * (i + 1)} for i, fid in enumerate(file_ids)
    ]
    return update


def voice_update(update_id: int, chat_id: int, file_id: str, mime: str = "audio/ogg") -> dict[str, Any]:
    update = text_update(update_id, chat_id, "x")
    del update["message"]["text"]
    update["message"]["voice"] = {"file_id": file_id, "duration": 2, "mime_type": mime}
    return update


def callback_update(update_id: int, chat_id: int, data: str) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"cb-{update_id}",
            "from": {"id": chat_id, "is_bot": False, "first_name": "Tester"},
            "message": {
                "message_id": 7,
                "chat": {"id": chat_id, "type": "private"},
                "date": 1_760_000_000,
            },
            "data": data,
        },
    }
