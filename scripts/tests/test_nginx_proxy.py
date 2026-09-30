# ruff: noqa: S310 - local http:// URLs only
"""The console's nginx template, run for real (SPEC §19.1, §20, §21, §23; decision B7).

Starts the pinned unprivileged nginx image with `frontend/nginx.conf` as its template, a tiny
`index.html`, and `CHHATRI_BACKEND_UPSTREAM` pointing at a stub upstream on the Docker host. Proves:
SSE events are flushed one by one (no proxy buffering) and never gzipped; JSON is gzipped; SPA routes
fall back to index.html; `/internal/` is never proxied; `/healthz` answers.
"""

from __future__ import annotations

import gzip
import re
import secrets
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Final

import pytest

from selftest_docker import bridge_gateway, run_docker, wait_ready

SSE_GAP_S: Final = 2.0  # the stub waits this long between the two events
FIRST_EVENT_BUDGET_S: Final = 1.0  # a buffering proxy would hold event 1 until event 2 (or EOF)
JSON_BODY: Final = b'{"ok": true, "data": "' + b"x" * 4096 + b'"}'
INDEX_HTML: Final = "<!doctype html><title>Chhatri</title><div id=root>console</div>\n"
READY_TIMEOUT_S: Final = 30.0


class _Upstream(BaseHTTPRequestHandler):
    seen: list[str]

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        self.seen.append(f"GET {self.path}")
        if self.path == "/api/stream":
            self._stream()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(JSON_BODY)))
        self.end_headers()
        self.wfile.write(JSON_BODY)

    def do_POST(self) -> None:  # noqa: N802  # pragma: no cover - reaching it is the failure under test
        self.seen.append(f"POST {self.path}")
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        for n in (1, 2):
            self.wfile.write(f'id: {n}\nevent: tick\ndata: {{"n": {n}}}\n\n'.encode())
            self.wfile.flush()
            if n == 1:
                time.sleep(SSE_GAP_S)
        self.close_connection = True

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - http.server API
        return


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def console(repo_root: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[str, list[str]]]:
    """(console base URL, upstream request log) for one nginx container."""
    gateway = bridge_gateway()
    handler = type("Upstream", (_Upstream,), {"seen": []})
    server = ThreadingHTTPServer((gateway, 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    html = tmp_path_factory.mktemp("html")
    (html / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (html / "index.html").chmod(0o644)
    name, port = f"chhatri-nginx-test-{secrets.token_hex(4)}", _free_port()
    image = re.search(
        r"^FROM (nginxinc/\S+)$",
        (repo_root / "frontend" / "Dockerfile").read_text(),
        re.M,
    )
    assert image, "frontend/Dockerfile has no nginx stage"
    # index.html goes in with `docker cp`: the daemon may not see the host's /tmp (systemd PrivateTmp).
    run_docker([
        "create", "--name", name, "--publish", f"127.0.0.1:{port}:8080",
        "--env", f"CHHATRI_BACKEND_UPSTREAM={gateway}:{server.server_address[1]}",
        "--volume", f"{repo_root / 'frontend' / 'nginx.conf'}:/etc/nginx/templates/default.conf.template:ro",
        image.group(1),
    ])  # fmt: skip
    run_docker(["cp", str(html / "index.html"), f"{name}:/usr/share/nginx/html/index.html"])
    run_docker(["start", name])
    base = f"http://127.0.0.1:{port}"
    try:
        wait_ready(base, READY_TIMEOUT_S, probe=lambda _url: _status(base + "/healthz") == 200)
        yield base, handler.seen
    finally:
        run_docker(["rm", "--force", name])
        server.shutdown()
        server.server_close()


def _status(url: str, method: str = "GET") -> int:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method=method), timeout=5) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except (urllib.error.URLError, OSError):
        return 0


def test_sse_is_flushed_event_by_event_and_never_gzipped(
    console: tuple[str, list[str]],
) -> None:
    base, _ = console
    request = urllib.request.Request(base + "/api/stream", headers={"Accept-Encoding": "gzip"})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=10) as resp:
        assert resp.headers.get("Content-Type", "").startswith("text/event-stream")
        assert resp.headers.get("Content-Encoding") is None
        first = [resp.readline().decode() for _ in range(4)]
        first_at = time.monotonic() - started
        rest = resp.read().decode()
    assert first == ["id: 1\n", "event: tick\n", 'data: {"n": 1}\n', "\n"]
    assert first_at < FIRST_EVENT_BUDGET_S < SSE_GAP_S, f"event 1 arrived after {first_at:.2f} s"
    assert 'data: {"n": 2}' in rest


def test_json_api_is_proxied_and_gzipped(console: tuple[str, list[str]]) -> None:
    base, seen = console
    request = urllib.request.Request(base + "/api/health?x=1", headers={"Accept-Encoding": "gzip"})
    with urllib.request.urlopen(request, timeout=5) as resp:
        assert resp.headers.get("Content-Encoding") == "gzip"
        assert gzip.decompress(resp.read()) == JSON_BODY
    assert "GET /api/health?x=1" in seen


def test_spa_routes_fall_back_to_index_html(console: tuple[str, list[str]]) -> None:
    base, _ = console
    for route in ("/", "/live", "/claims", "/merchant/S-0142", "/audit"):
        with urllib.request.urlopen(base + route, timeout=5) as resp:
            assert resp.read().decode() == INDEX_HTML, route
    assert _status(base + "/assets/missing.js") == 404


def test_internal_routes_are_not_proxied(console: tuple[str, list[str]]) -> None:
    base, seen = console
    assert _status(base + "/internal/workflows/execute_payout", method="POST") in {
        404,
        405,
    }
    assert not [line for line in seen if "/internal/" in line]
