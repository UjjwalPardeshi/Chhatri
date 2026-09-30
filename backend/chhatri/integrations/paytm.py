"""Paytm payment-link facade (SPEC §14.3) — keeps the historical import path stable.

Implementation lives in `paytm_mcp` (Paytm payment MCP server over SSE), `paytm_rest` (direct REST
with PaytmChecksum), `paytm_sim` (simulated links) and `paytm_common` (strict parsing, amounts).
"""

from __future__ import annotations

from chhatri.integrations.paytm_common import (
    format_amount,
    parse_link_payment,
    parse_mcp_link,
    parse_rest_link,
)
from chhatri.integrations.paytm_mcp import McpPaytmLinks
from chhatri.integrations.paytm_rest import RestPaytmLinks, signed_request
from chhatri.integrations.paytm_sim import SIM_URL_PREFIX, SimulatedPaytmLinks

__all__ = [
    "SIM_URL_PREFIX",
    "McpPaytmLinks",
    "RestPaytmLinks",
    "SimulatedPaytmLinks",
    "format_amount",
    "parse_link_payment",
    "parse_mcp_link",
    "parse_rest_link",
    "signed_request",
]
