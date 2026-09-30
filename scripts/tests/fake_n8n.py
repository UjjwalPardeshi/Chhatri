# ruff: noqa: S105, S106, S310 - test fixtures: dummy secrets, local http:// URLs (same policy as backend tests/)
"""A minimal stand-in for n8n used to test the self-test harness offline.

It honours the contract the generated workflows implement (webhook -> secret check -> one callback
per step -> 200 completion answer; the first callback that stays non-2xx after 3 tries stops the run
and the webhook answers 500) so `n8n_selftest.run_checks` can be exercised without
Docker. `reverse` makes it call the steps in the wrong order; `not_ready_first` answers the first N
webhook calls with 404, like an n8n that has not registered its webhooks yet; `early` answers 200
before calling back (an outdated workflow that would let the simulated clock run ahead).
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
        early: bool = False,
    ) -> None:
        self._secret = secret
        self._base = callback_base
        self._workflows = workflows
        self._reverse = reverse
        self._not_ready = not_ready_first
        self._early = early
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

    def _run(self, workflow: str, body: Mapping[str, Any]) -> bool:
        """Call back every step; False when a step stayed non-2xx (the run stopped there)."""
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
                return False
        return True

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
                if fake._early:
                    self._reply(200, {"ok": True, "data": {"run_id": body["run_id"], "status": "completed"}})
                    threading.Thread(target=fake._run, args=(workflow, body), daemon=True).start()
                    return
                if not fake._run(workflow, body):
                    self._reply(500, {"code": 0, "message": "Error in workflow"})
                    return
                self._reply(200, {"ok": True, "data": {"run_id": body["run_id"], "status": "completed"}})

            def _reply(self, status: int, doc: Mapping[str, Any] | None = None) -> None:
                data = json.dumps(doc).encode() if doc is not None else b""
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                return

        return Handler
