"""McpPaytmLinks end to end against a local FastMCP SSE server (SPEC §14.3, mcp 1.30 client)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from chhatri.domain.models import Merchant
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.paytm import McpPaytmLinks

from .conftest import SIM_NOW
from .mcp_stub import LINK_ID, SHORT_URL, free_port, running_stub

Stub = tuple[str, list[tuple[str, dict[str, Any]]]]


@pytest.fixture(scope="module")
def stub() -> Iterator[Stub]:
    with running_stub() as server:
        yield server


def links(url: str, timeout_s: float = 10.0) -> McpPaytmLinks:
    return McpPaytmLinks(url, clock=lambda: SIM_NOW, timeout_s=timeout_s)


async def test_create_premium_link_over_sse(stub: Stub, anil: Merchant) -> None:
    url, calls = stub
    link = await links(url).create_premium_link(anil, 6000, "Chhatri cover · 30 days")
    assert (link.url, link.link_id, link.amount_paise, link.source) == (SHORT_URL, LINK_ID, 6000, "paytm-mcp")
    assert link.created_at == SIM_NOW
    assert calls[-1] == (
        "create_payment_link",
        {
            "recipient_name": "Anil Jadhav",
            "purpose": "Chhatri cover · 30 days",
            "customer_email": None,
            "customer_mobile": None,
            "amount": "60.00",
        },
    )


async def test_link_payment_over_sse(stub: Stub) -> None:
    url, calls = stub
    paid = await links(url).link_payment(LINK_ID)
    assert paid.paid and paid.txn_id == "T-991" and paid.paid_amount_paise == 6000
    unpaid = await links(url).link_payment("999")
    assert unpaid.paid is False
    assert calls[-1] == ("fetch_transactions_for_link", {"link_id": "999"})


async def test_error_string_is_rejected_by_strict_parser(stub: Stub, anil: Merchant) -> None:
    with pytest.raises(IntegrationError, match="unexpected reply"):
        await links(stub[0]).create_premium_link(anil, 6000, "error-string")


async def test_reply_without_text_content_is_rejected(stub: Stub, anil: Merchant) -> None:
    with pytest.raises(IntegrationError, match="returned no text"):
        await links(stub[0]).create_premium_link(anil, 6000, "no-content")


async def test_tool_exception_is_is_error(stub: Stub, anil: Merchant) -> None:
    with pytest.raises(IntegrationError, match="returned an error"):
        await links(stub[0]).create_premium_link(anil, 6000, "raise")


async def test_slow_server_times_out(stub: Stub, anil: Merchant) -> None:
    with pytest.raises(IntegrationError, match="timed out"):
        await links(stub[0], timeout_s=0.5).create_premium_link(anil, 6000, "slow")


async def test_unreachable_server_raises_safely(anil: Merchant) -> None:
    with pytest.raises(IntegrationError, match="unreachable|timed out"):
        await links(f"http://127.0.0.1:{free_port()}/sse", timeout_s=3).create_premium_link(anil, 6000, "x")


def test_validation() -> None:
    with pytest.raises(ValueError):
        McpPaytmLinks("ftp://x", clock=lambda: SIM_NOW)
