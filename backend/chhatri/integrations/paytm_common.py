"""Paytm payment-link parsing and formatting shared by the MCP and REST clients (SPEC §14.3).

- MCP tool `create_payment_link` returns exactly `"url =<shortUrl>\\nlinkId=<id>"` on success or an
  error string; anything that does not match the strict pattern is an error.
- REST `POST /link/create` succeeds only when `body.resultInfo.resultStatus == "SUCCESS"`, with the
  link at `body.shortUrl` and id `body.linkId`.
- Link payment status (MCP `fetch_transactions_for_link` / REST `POST /link/fetchTransaction`) is read
  from `body.orders[]`: paid when an order has `orderStatus == "SUCCESS"`; `txnId` and `txnAmount`
  (rupees) are taken from it. Anything else raises instead of reporting "unpaid".
Amounts are rupee strings with two decimals ("60.00"). Merchant phone numbers are never sent to Paytm
(the simulated city's numbers are fake), so SMS/e-mail delivery is off; the link goes out on WhatsApp.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from chhatri.integrations.base import IntegrationError, LinkPayment

INTEGRATION = "paytm"
PAISE_PER_RUPEE = 100
RUPEE_QUANTUM = Decimal("0.01")
SUCCESS = "SUCCESS"
MAX_LINK_NAME = 50
_MCP_REPLY = re.compile(r"\Aurl =(?P<url>https://[^\s]+)\nlinkId=(?P<link_id>[A-Za-z0-9_-]+)\Z")
_SHORT_URL = re.compile(r"\Ahttps://[^\s]+\Z")
_LINK_ID = re.compile(r"\A[A-Za-z0-9_-]{1,64}\Z")
_NAME_UNSAFE = re.compile(r"[^A-Za-z0-9 ]+")


def format_amount(amount_paise: int) -> str:
    """Integer paise → Paytm rupee string with two decimals (SPEC §4: money is integer paise)."""
    if isinstance(amount_paise, bool) or not isinstance(amount_paise, int) or amount_paise <= 0:
        raise ValueError("amount_paise must be a positive integer")
    return str((Decimal(amount_paise) / PAISE_PER_RUPEE).quantize(RUPEE_QUANTUM, rounding=ROUND_HALF_UP))


def rupees_to_paise(value: Any) -> int | None:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite():
        return None
    return int((amount * PAISE_PER_RUPEE).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def link_name(text: str) -> str:
    """Paytm link names: letters, digits and spaces only, bounded length."""
    cleaned = " ".join(_NAME_UNSAFE.sub(" ", text).split())[:MAX_LINK_NAME].strip()
    return cleaned or "Chhatri cover"


def parse_mcp_link(text: Any) -> tuple[str, str]:
    """Strictly parse the MCP tool's success string into (url, link_id)."""
    match = _MCP_REPLY.match(text.strip()) if isinstance(text, str) else None
    if match is None:
        raise IntegrationError(INTEGRATION, "unexpected reply from the payment link tool")
    return match.group("url"), match.group("link_id")


def _body(data: Mapping[str, Any]) -> Mapping[str, Any]:
    body = data.get("body")
    if not isinstance(body, Mapping):
        raise IntegrationError(INTEGRATION, "response had no body")
    return body


def _require_success(body: Mapping[str, Any]) -> None:
    info = body.get("resultInfo")
    status = info.get("resultStatus") if isinstance(info, Mapping) else None
    if status != SUCCESS:
        code = info.get("resultCode") if isinstance(info, Mapping) else None
        safe_code = code if isinstance(code, str) and code.isalnum() else "unknown"
        raise IntegrationError(INTEGRATION, f"Paytm did not accept the request (code {safe_code})")


def parse_rest_link(data: Mapping[str, Any]) -> tuple[str, str]:
    """`/link/create` response → (shortUrl, linkId)."""
    body = _body(data)
    _require_success(body)
    url, link_id = body.get("shortUrl"), body.get("linkId")
    link_text = str(link_id) if isinstance(link_id, int | str) and not isinstance(link_id, bool) else ""
    if not isinstance(url, str) or not _SHORT_URL.match(url) or not _LINK_ID.match(link_text):
        raise IntegrationError(INTEGRATION, "response had no link url or id")
    return url, link_text


def parse_link_payment(link_id: str, data: Mapping[str, Any]) -> LinkPayment:
    """`body.orders[]` → LinkPayment (paid when any order succeeded)."""
    body = _body(data)
    _require_success(body)
    orders = body.get("orders")
    if not isinstance(orders, list):
        raise IntegrationError(INTEGRATION, "response had no orders list")
    for order in orders:
        if isinstance(order, Mapping) and order.get("orderStatus") == SUCCESS:
            txn = order.get("txnId")
            return LinkPayment(
                link_id=link_id,
                paid=True,
                txn_id=str(txn) if isinstance(txn, str | int) and not isinstance(txn, bool) else None,
                paid_amount_paise=rupees_to_paise(order.get("txnAmount")),
            )
    return LinkPayment(link_id=link_id, paid=False)


def parse_json_text(text: Any) -> Mapping[str, Any]:
    """Tool replies that carry a JSON document (MCP `fetch_transactions_for_link`)."""
    try:
        data = json.loads(text) if isinstance(text, str) else None
    except json.JSONDecodeError as exc:
        raise IntegrationError(INTEGRATION, "payment status reply was not JSON") from exc
    if not isinstance(data, Mapping):
        raise IntegrationError(INTEGRATION, "payment status reply was not a JSON object")
    return data


def validate_link_id(link_id: str) -> str:
    if not isinstance(link_id, str) or not _LINK_ID.match(link_id):
        raise ValueError("invalid payment link id")
    return link_id
