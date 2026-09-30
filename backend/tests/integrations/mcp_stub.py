"""Local stand-in for Paytm's payment MCP server: FastMCP over SSE on a free 127.0.0.1 port."""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP

STARTUP_TIMEOUT_S = 10.0
SHORT_URL = "https://paytm.me/AbC123"
LINK_ID = "204587"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def build_server(calls: list[tuple[str, dict[str, Any]]], port: int) -> FastMCP:
    server = FastMCP("paytm-payment-stub", host="127.0.0.1", port=port, log_level="WARNING")

    @server.tool(structured_output=False)
    def create_payment_link(
        recipient_name: str,
        purpose: str,
        customer_email: str | None = None,
        customer_mobile: str | None = None,
        amount: str | None = None,
    ) -> Any:
        calls.append(
            (
                "create_payment_link",
                {
                    "recipient_name": recipient_name,
                    "purpose": purpose,
                    "customer_email": customer_email,
                    "customer_mobile": customer_mobile,
                    "amount": amount,
                },
            )
        )
        if purpose == "slow":
            time.sleep(1.5)
        if purpose == "raise":
            raise ValueError("tool crashed")
        if purpose == "no-content":
            return []
        if purpose == "error-string":
            return "Failed to create payment link: invalid amount"
        return f"url ={SHORT_URL}\nlinkId={LINK_ID}"

    @server.tool()
    def fetch_transactions_for_link(link_id: str) -> str:
        calls.append(("fetch_transactions_for_link", {"link_id": link_id}))
        orders = [{"orderId": "O1", "orderStatus": "SUCCESS", "txnId": "T-991", "txnAmount": "60.00"}]
        return json.dumps(
            {
                "body": {
                    "resultInfo": {"resultStatus": "SUCCESS"},
                    "orders": orders if link_id == LINK_ID else [],
                }
            }
        )

    return server


@contextmanager
def running_stub() -> Iterator[tuple[str, list[tuple[str, dict[str, Any]]]]]:
    """Start the stub; yields (sse_url, recorded tool calls); always stops the server."""
    calls: list[tuple[str, dict[str, Any]]] = []
    port = free_port()
    app = build_server(calls, port).sse_app()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off")
    )
    thread = threading.Thread(target=server.run, name="paytm-mcp-stub", daemon=True)
    thread.start()
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    while not server.started:
        if time.monotonic() > deadline or not thread.is_alive():
            raise RuntimeError("MCP stub server did not start")
        time.sleep(0.02)
    try:
        yield f"http://127.0.0.1:{port}/sse", calls
    finally:
        server.should_exit = True
        thread.join(STARTUP_TIMEOUT_S)
