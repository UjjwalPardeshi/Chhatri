"""Paytm payment links through Paytm's payment MCP server over SSE (SPEC §14.3, mcp 1.30 client API).

```
async with sse_client(url) as (r, w):
    async with ClientSession(r, w) as s:
        await s.initialize()
        res = await s.call_tool("create_payment_link", {...})   # res.isError, res.content[0].text
```
Tool signature: `create_payment_link(recipient_name, purpose, customer_email, customer_mobile,
amount) -> str` and `fetch_transactions_for_link(link_id) -> str`. Each call opens one short SSE
session bounded by the timeout; the MCP server holds the Paytm key, never the browser.

No retries here: the SPEC §14 retry rule is about HTTP 429/5xx, which the MCP server absorbs (it
returns an error string, surfaced as IntegrationError), and a blind retry of `create_payment_link`
over a broken session could create a second payable link for the same premium.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client

from chhatri.domain.models import Merchant
from chhatri.integrations.base import IntegrationError, LinkPayment, PaymentLink
from chhatri.integrations.paytm_common import (
    INTEGRATION,
    format_amount,
    parse_json_text,
    parse_link_payment,
    parse_mcp_link,
    validate_link_id,
)
from chhatri.integrations.retry import DEFAULT_TIMEOUT_S

logger = logging.getLogger(__name__)

SOURCE = "paytm-mcp"
CREATE_TOOL = "create_payment_link"
FETCH_TOOL = "fetch_transactions_for_link"


class McpPaytmLinks:
    """PaymentLinks via the Paytm payment MCP server (SSE transport, path `/sse`)."""

    def __init__(
        self, url: str, *, clock: Callable[[], datetime], timeout_s: float = DEFAULT_TIMEOUT_S
    ) -> None:
        if not url.startswith(("http://", "https://")):
            raise ValueError("PAYTM_MCP_URL must be an http(s) URL")
        self._url = url
        self._clock = clock
        self._timeout_s = timeout_s

    async def create_premium_link(self, merchant: Merchant, amount_paise: int, purpose: str) -> PaymentLink:
        arguments = {
            "recipient_name": merchant.owner_name,
            "purpose": purpose,
            "customer_email": None,
            "customer_mobile": None,
            "amount": format_amount(amount_paise),
        }
        url, link_id = parse_mcp_link(await self._call_tool(CREATE_TOOL, arguments))
        logger.info("paytm-mcp: link %s created for %s", link_id, merchant.id)
        return PaymentLink(
            link_id=link_id, url=url, amount_paise=amount_paise, source=SOURCE, created_at=self._clock()
        )

    async def link_payment(self, link_id: str) -> LinkPayment:
        text = await self._call_tool(FETCH_TOOL, {"link_id": validate_link_id(link_id)})
        return parse_link_payment(link_id, parse_json_text(text))

    async def _call_tool(self, name: str, arguments: Mapping[str, Any]) -> str:
        try:
            async with asyncio.timeout(self._timeout_s):
                return await self._session_call(name, dict(arguments))
        except IntegrationError:
            raise
        except TimeoutError as exc:
            raise IntegrationError(INTEGRATION, "payment MCP server timed out") from exc
        except Exception as exc:
            logger.error("paytm-mcp: %s failed (%s)", name, type(exc).__name__)
            raise IntegrationError(INTEGRATION, "payment MCP server unreachable") from exc

    async def _session_call(self, name: str, arguments: dict[str, Any]) -> str:
        async with (
            sse_client(self._url, timeout=self._timeout_s, sse_read_timeout=self._timeout_s) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            result = await session.call_tool(name, arguments)
        if result.isError:
            raise IntegrationError(INTEGRATION, f"payment tool {name} returned an error")
        content = result.content[0] if result.content else None
        text = getattr(content, "text", None)
        if not isinstance(text, str):
            raise IntegrationError(INTEGRATION, f"payment tool {name} returned no text")
        return text
