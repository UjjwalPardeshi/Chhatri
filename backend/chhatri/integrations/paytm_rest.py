"""Paytm payment links through the direct REST API (SPEC §14.3 fallback; same payload as the MCP server).

`POST {PAYTM_BASE_URL}/link/create` with JSON
`{"body": {mid, linkType: "FIXED", linkDescription, linkName, sendSms, sendEmail, maxPaymentsAllowed: 1,
amount, customerContact: {customerName, customerEmail, customerMobile}}, "head": {"tokenType": "AES",
"signature": PaytmChecksum.generateSignature(json.dumps(body), PAYTM_KEY_SECRET)}}`.
The request is sent with the exact `json.dumps(body)` text that was signed, so Paytm verifies the same
bytes. Staging base `https://securestage.paytmpayments.com` (configurable). The key never leaves the
backend and is never logged.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

import httpx
from paytmchecksum import PaytmChecksum

from chhatri.domain.models import Merchant
from chhatri.integrations.base import IntegrationError, LinkPayment, PaymentLink
from chhatri.integrations.paytm_common import (
    INTEGRATION,
    format_amount,
    link_name,
    parse_link_payment,
    parse_rest_link,
    validate_link_id,
)
from chhatri.integrations.retry import (
    DEFAULT_RETRY,
    DEFAULT_TIMEOUT_S,
    RetryPolicy,
    Sleep,
    http_request,
    json_object,
)

logger = logging.getLogger(__name__)

SOURCE = "paytm-rest"
CREATE_PATH = "/link/create"
FETCH_PATH = "/link/fetchTransaction"
TOKEN_TYPE = "AES"  # noqa: S105 — Paytm token type label, not a secret


def signed_request(body: Mapping[str, Any], key_secret: str) -> bytes:
    """Serialise `{"body": …, "head": …}` embedding the exact signed `json.dumps(body)` text."""
    body_text = json.dumps(body)
    try:
        signature = PaytmChecksum.generateSignature(body_text, key_secret)
    except Exception as exc:
        raise IntegrationError(INTEGRATION, "could not sign the request") from exc
    head_text = json.dumps({"tokenType": TOKEN_TYPE, "signature": signature})
    return f'{{"body": {body_text}, "head": {head_text}}}'.encode()


class RestPaytmLinks:
    """PaymentLinks via Paytm's link API with checksum-signed requests."""

    def __init__(
        self,
        *,
        mid: str,
        key_secret: str,
        base_url: str,
        clock: Callable[[], datetime],
        timeout_s: float = DEFAULT_TIMEOUT_S,
        transport: httpx.AsyncBaseTransport | None = None,
        policy: RetryPolicy = DEFAULT_RETRY,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if not mid or not key_secret:
            raise ValueError("PAYTM_MID and PAYTM_KEY_SECRET are required")
        if not base_url.startswith("https://"):
            raise ValueError("PAYTM_BASE_URL must be https")
        self._mid = mid
        self._key = key_secret
        self._base = base_url.rstrip("/")
        self._clock = clock
        self._timeout_s = timeout_s
        self._transport = transport
        self._policy = policy
        self._sleep = sleep

    def create_body(self, merchant: Merchant, amount_paise: int, purpose: str) -> dict[str, Any]:
        return {
            "mid": self._mid,
            "linkType": "FIXED",
            "linkDescription": purpose,
            "linkName": link_name(f"Chhatri cover {merchant.id}"),
            "sendSms": False,
            "sendEmail": False,
            "maxPaymentsAllowed": 1,
            "amount": format_amount(amount_paise),
            "customerContact": {
                "customerName": merchant.owner_name,
                "customerEmail": None,
                "customerMobile": None,
            },
        }

    async def create_premium_link(self, merchant: Merchant, amount_paise: int, purpose: str) -> PaymentLink:
        data = await self._post(CREATE_PATH, self.create_body(merchant, amount_paise, purpose))
        url, link_id = parse_rest_link(data)
        logger.info("paytm-rest: link %s created for %s", link_id, merchant.id)
        return PaymentLink(
            link_id=link_id, url=url, amount_paise=amount_paise, source=SOURCE, created_at=self._clock()
        )

    async def link_payment(self, link_id: str) -> LinkPayment:
        data = await self._post(FETCH_PATH, {"mid": self._mid, "linkId": validate_link_id(link_id)})
        return parse_link_payment(link_id, data)

    async def _post(self, path: str, body: Mapping[str, Any]) -> Mapping[str, Any]:
        content = signed_request(body, self._key)
        async with httpx.AsyncClient(timeout=self._timeout_s, transport=self._transport) as client:
            response = await http_request(
                client,
                "POST",
                f"{self._base}{path}",
                integration=INTEGRATION,
                policy=self._policy,
                sleep=self._sleep,
                content=content,
                headers={"Content-Type": "application/json"},
            )
        return json_object(response, integration=INTEGRATION)
