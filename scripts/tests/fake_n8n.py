# ruff: noqa: S105, S106, S310 - test fixtures: dummy secrets, local http:// URLs (same policy as backend tests/)
"""A minimal stand-in for n8n used to test the self-test harness offline.

It honours the contract the generated workflows implement (webhook -> secret check -> 202 -> one
callback per step, stop on the first non-2xx) so `n8n_selftest.run_checks` can be exercised without
Docker. `reverse` makes it call the steps in the wrong order; `not_ready_first` answers the first N
webhook calls with 404, like an n8n that has not registered its webhooks yet.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class FakeN8n:
    def __init__(
        self,
        secret: str,
        callback_base: str,
        workflows: Mapping[str, Sequence[str]],
        *,
        reverse: bool = False,
        not_ready_first: int = 0,
    ) -> None:
        self._secret = secret
        self._base = callback_base
        self._workflows = workflows
        self._reverse = reverse
        self._not_ready = not_ready_first
        self._lock = threading.Lock()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def __enter__(self) -> FakeN8n:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()

    def _take_not_ready(self) -> bool:
        with self._lock:
            if self._not_ready > 0:
                self._not_ready -= 1
                return True
            return False

    def _run(self, workflow: str, body: Mapping[str, Any]) -> None:
        steps = list(self._workflows[workflow])
        for step in reversed(steps) if self._reverse else steps:
            doc = {
                "run_id": body["run_id"],
                "workflow": workflow,
                "step": step,
                "payload": body["payload"],
            }
            for _ in range(3):
                request = urllib.request.Request(
                    f"{self._base}/internal/workflows/{step}",
                    data=json.dumps(doc).encode(),
                    headers={
                        "Content-Type": "application/json",
                        "X-Chhatri-Secret": self._secret,
                    },
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(request, timeout=5):
                        break
                except urllib.error.HTTPError:
                    continue
            else:
                return

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                workflow = self.path.removeprefix("/webhook/chhatri-")
                if workflow not in fake._workflows or fake._take_not_ready():
                    self._reply(404)
                    return
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if self.headers.get("X-Chhatri-Secret") != fake._secret:
                    self._reply(403)
                    return
                self._reply(202)
                threading.Thread(target=fake._run, args=(workflow, body), daemon=True).start()

            def _reply(self, status: int) -> None:
                self.send_response(status)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                return

        return Handler
