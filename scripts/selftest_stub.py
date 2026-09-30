"""Stub of the backend's n8n callback endpoint for `scripts/n8n_selftest.py` (SPEC §14.5, §19).

`POST /internal/workflows/{step}` with header `X-Chhatri-Secret` and body
`{"run_id", "workflow", "step", "payload"}` is recorded and answered like the real route:
`200 {"ok": true, "data": {"step", "status": "done"}}`. A wrong secret gets 403, a malformed body 422,
another path 404, and a (run_id, step) listed in `fail_steps` gets 500 (to prove that n8n stops a run
on a non-2xx answer).
"""

from __future__ import annotations

import hmac
import json
import logging
import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import MappingProxyType
from typing import Any, Final

logger = logging.getLogger("n8n_selftest.stub")

CALLBACK_PREFIX: Final = "/internal/workflows/"
SECRET_HEADER: Final = "X-Chhatri-Secret"  # noqa: S105 - header name, not a secret
CALLBACK_KEYS: Final = frozenset({"run_id", "workflow", "step", "payload"})
MAX_BODY_BYTES: Final = 64 * 1024


@dataclass(frozen=True, slots=True)
class Callback:
    """One callback as received: path step, header secret match, and the parsed body."""

    path_step: str
    secret_ok: bool
    body: Mapping[str, Any]
    status: int

    @property
    def run_id(self) -> str:
        return str(self.body.get("run_id", ""))


class Recorder:
    """Thread-safe, append-only log of callbacks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: list[Callback] = []

    def add(self, call: Callback) -> None:
        with self._lock:
            self._calls.append(call)

    def for_run(self, run_id: str) -> tuple[Callback, ...]:
        with self._lock:
            return tuple(c for c in self._calls if c.run_id == run_id)

    def all(self) -> tuple[Callback, ...]:
        with self._lock:
            return tuple(self._calls)


def body_problem(path_step: str, body: Any) -> str | None:
    """Why a callback body is invalid for SPEC §14.5, or None when it is well formed."""
    if not isinstance(body, dict):
        return "body is not a JSON object"
    if set(body) != CALLBACK_KEYS:
        return f"body keys {sorted(body)} != {sorted(CALLBACK_KEYS)}"
    if body["step"] != path_step:
        return f"body step {body['step']!r} != path step {path_step!r}"
    if not isinstance(body["payload"], dict):
        return "payload is not an object"
    return None


def make_handler(
    recorder: Recorder, secret: str, fail_steps: frozenset[tuple[str, str]]
) -> type[BaseHTTPRequestHandler]:
    """Request handler class bound to one recorder, secret and failure set."""

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - http.server API
            if not self.path.startswith(CALLBACK_PREFIX):
                self._reply(HTTPStatus.NOT_FOUND, {"ok": False, "error": {"code": "not_found"}})
                return
            step = self.path[len(CALLBACK_PREFIX) :]
            presented = self.headers.get(SECRET_HEADER, "")
            secret_ok = bool(presented) and hmac.compare_digest(presented.encode(), secret.encode())
            body = self._read_json()
            status = self._status(step, secret_ok, body)
            recorder.add(
                Callback(
                    step,
                    secret_ok,
                    MappingProxyType(body) if isinstance(body, dict) else {},
                    status,
                )
            )
            if status == HTTPStatus.OK:
                self._reply(status, {"ok": True, "data": {"step": step, "status": "done"}})
            else:
                self._reply(
                    HTTPStatus(status),
                    {"ok": False, "error": {"code": HTTPStatus(status).phrase}},
                )

        def _status(self, step: str, secret_ok: bool, body: Any) -> int:
            if not secret_ok:
                return HTTPStatus.FORBIDDEN
            problem = body_problem(step, body)
            if problem:
                logger.warning("stub: invalid callback for %s: %s", step, problem)
                return HTTPStatus.UNPROCESSABLE_ENTITY
            if (body["run_id"], step) in fail_steps:
                return HTTPStatus.INTERNAL_SERVER_ERROR
            return HTTPStatus.OK

        def _read_json(self) -> Any:
            length = min(int(self.headers.get("Content-Length") or 0), MAX_BODY_BYTES)
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None

        def _reply(self, status: HTTPStatus, doc: Mapping[str, Any]) -> None:
            data = json.dumps(doc).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - http.server API
            logger.debug("stub: " + format, *args)

    return Handler


class StubBackend:
    """Context manager running the stub on (host, port) in a daemon thread."""

    def __init__(
        self,
        host: str,
        port: int,
        secret: str,
        fail_steps: Iterable[tuple[str, str]] = (),
    ) -> None:
        if not secret:
            raise ValueError("the stub needs a non-empty secret")
        self.recorder = Recorder()
        handler = make_handler(self.recorder, secret, frozenset(fail_steps))
        self._server = ThreadingHTTPServer((host, port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, name="n8n-stub", daemon=True)

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def __enter__(self) -> StubBackend:
        self._thread.start()
        logger.info("stub backend listening on port %d", self.port)
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
