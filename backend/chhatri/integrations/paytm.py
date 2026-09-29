"""Paytm payment link integration (SPEC §14.3).

Three implementations:
1. McpPaytmLinks: MCP over SSE (mcp 1.30)
2. RestPaytmLinks: Direct REST API with PaytmChecksum
3. SimulatedPaytmLinks: Deterministic simulated links
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime

import httpx

from chhatri.domain.models import Merchant
from chhatri.integrations.base import IntegrationError, LinkPayment, PaymentLink

logger = logging.getLogger(__name__)


class McpPaytmLinks:
    """Paytm payment link creation via MCP SSE server."""

    def __init__(self, mcp_url: str, timeout: float = 5.0) -> None:
        """Initialize with MCP server URL.

        Args:
            mcp_url: URL to MCP server SSE endpoint (e.g., http://localhost:8080/sse).
            timeout: HTTP request timeout in seconds.
        """
        self.mcp_url = mcp_url
        self.timeout = timeout

    async def create_premium_link(self, merchant: Merchant, amount_paise: int,
                                  purpose: str) -> PaymentLink:
        """Create a payment link via MCP server.

        Args:
            merchant: Merchant object.
            amount_paise: Amount in paise.
            purpose: Purpose string for the link.

        Returns:
            PaymentLink with url and link_id.

        Raises:
            IntegrationError: If MCP call fails or response is invalid.
        """
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
        except ImportError:
            raise IntegrationError(
                "paytm",
                "mcp SDK not installed",
            ) from None

        # Format amount as string with 2 decimals
        amount_str = f"{amount_paise / 100:.2f}"

        # Strip +91 from phone to get 10-digit number
        phone_10digit = merchant.phone[3:] if merchant.phone.startswith("+91") else merchant.phone

        try:
            async with sse_client(self.mcp_url) as (read, write), ClientSession(read, write) as session:
                await session.initialize()

                response = await session.call_tool(
                    "create_payment_link",
                    {
                        "recipient_name": merchant.owner_name,
                        "purpose": purpose,
                        "customer_mobile": phone_10digit,
                        "amount": amount_str,
                    },
                )

            if response.isError:
                raise IntegrationError(
                    "paytm-mcp",
                    "MCP server returned an error",
                )

            # Parse response: "url =<shortUrl>\nlinkId=<id>"
            result_text = response.content[0].text
            url, link_id = self._parse_paytm_response(result_text)

            return PaymentLink(
                link_id=link_id,
                url=url,
                amount_paise=amount_paise,
                source="paytm-mcp",
                created_at=datetime.now(),
            )
        except IntegrationError:
            raise
        except TimeoutError:
            raise IntegrationError(
                "paytm-mcp",
                "MCP request timed out",
                retryable=True,
            ) from None
        except Exception as e:
            raise IntegrationError(
                "paytm-mcp",
                f"Failed to create payment link: {type(e).__name__}",
                retryable=True,
            ) from e

    async def link_payment(self, link_id: str) -> LinkPayment:
        """Check payment status for a link.

        Args:
            link_id: Paytm link ID.

        Returns:
            LinkPayment with payment status.

        Raises:
            IntegrationError: If the check fails.
        """
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
        except ImportError:
            raise IntegrationError(
                "paytm",
                "mcp SDK not installed",
            ) from None

        try:
            async with sse_client(self.mcp_url) as (read, write), ClientSession(read, write) as session:
                await session.initialize()

                response = await session.call_tool(
                    "fetch_transactions_for_link",
                    {"link_id": link_id},
                )

            if response.isError:
                return LinkPayment(link_id=link_id, paid=False)

            # Parse response to determine if paid
            # For now, assume if we get a successful response with transaction data, it's paid
            result_text = response.content[0].text
            data = json.loads(result_text) if isinstance(result_text, str) else result_text

            # Check if there are any successful transactions
            transactions = data.get("transactions", [])
            paid = any(t.get("status") == "success" for t in transactions)

            txn_id = None
            if transactions:
                txn_id = transactions[0].get("txn_id")

            return LinkPayment(link_id=link_id, paid=paid, txn_id=txn_id)
        except Exception as e:
            logger.warning(f"Failed to fetch link payment status: {e}")
            return LinkPayment(link_id=link_id, paid=False)

    @staticmethod
    def _parse_paytm_response(response_text: str) -> tuple[str, str]:
        """Parse Paytm response with strict regex.

        Expected format: "url =<shortUrl>\nlinkId=<id>"

        Args:
            response_text: Response text from Paytm.

        Returns:
            Tuple of (url, link_id).

        Raises:
            IntegrationError: If response format is invalid.
        """
        # Use strict regex to parse
        pattern = r'url =([^\n]+)\nlinkId=([^\n]+)'
        match = re.search(pattern, response_text)
        if not match:
            raise IntegrationError(
                "paytm-mcp",
                "Invalid response format from Paytm",
            )

        url = match.group(1).strip()
        link_id = match.group(2).strip()
        return url, link_id


class RestPaytmLinks:
    """Paytm payment link creation via REST API."""

    def __init__(self, mid: str, key_secret: str, base_url: str,
                 timeout: float = 10.0) -> None:
        """Initialize with Paytm credentials.

        Args:
            mid: Merchant ID.
            key_secret: Merchant key secret.
            base_url: Base URL (staging or production).
            timeout: HTTP request timeout in seconds.
        """
        self.mid = mid
        self.key_secret = key_secret
        self.base_url = base_url
        self.timeout = timeout

    async def create_premium_link(self, merchant: Merchant, amount_paise: int,
                                  purpose: str) -> PaymentLink:
        """Create a payment link via REST API.

        Args:
            merchant: Merchant object.
            amount_paise: Amount in paise.
            purpose: Purpose string for the link.

        Returns:
            PaymentLink with url and link_id.

        Raises:
            IntegrationError: If API call fails or signature verification fails.
        """
        try:
            from paytmchecksum import PaytmChecksum
        except ImportError:
            raise IntegrationError(
                "paytm",
                "paytmchecksum not installed",
            ) from None

        # Format amount as string with 2 decimals
        amount_str = f"{amount_paise / 100:.2f}"

        # Strip +91 from phone to get 10-digit number
        phone_10digit = merchant.phone[3:] if merchant.phone.startswith("+91") else merchant.phone

        # Build request body
        body = {
            "body": {
                "mid": self.mid,
                "linkType": "FIXED",
                "linkDescription": purpose,
                "linkName": merchant.shop_name,
                "sendSms": False,
                "sendEmail": False,
                "maxPaymentsAllowed": 1,
                "amount": amount_str,
                "customerContact": {
                    "customerName": merchant.owner_name,
                    "customerEmail": None,
                    "customerMobile": phone_10digit,
                },
            },
            "head": {
                "tokenType": "AES",
                "signature": "",
            },
        }

        # Generate signature
        body_json = json.dumps(body["body"], separators=(",", ":"), sort_keys=True)
        try:
            signature = PaytmChecksum.generateSignature(body_json, self.key_secret)
        except Exception as e:
            raise IntegrationError(
                "paytm-rest",
                "Failed to generate signature",
            ) from e

        body["head"]["signature"] = signature

        # Make request
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}/link/create"
                response = await client.post(url, json=body)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as e:
            raise IntegrationError(
                "paytm-rest",
                f"HTTP error: {type(e).__name__}",
                retryable=True,
            ) from e
        except Exception as e:
            raise IntegrationError(
                "paytm-rest",
                f"Failed to create payment link: {type(e).__name__}",
                retryable=True,
            ) from e

        # Parse response
        try:
            result_info = data.get("body", {}).get("resultInfo", {})
            status = result_info.get("resultStatus", "")

            if status != "SUCCESS":
                reason = result_info.get("resultMsg", "Unknown error")
                raise IntegrationError(
                    "paytm-rest",
                    f"Link creation failed: {reason}",
                )

            short_url = data["body"].get("shortUrl")
            link_id = data["body"].get("linkId")

            if not short_url or not link_id:
                raise IntegrationError(
                    "paytm-rest",
                    "Missing url or linkId in response",
                )

            return PaymentLink(
                link_id=link_id,
                url=short_url,
                amount_paise=amount_paise,
                source="paytm-rest",
                created_at=datetime.now(),
            )
        except IntegrationError:
            raise
        except (KeyError, TypeError) as e:
            raise IntegrationError(
                "paytm-rest",
                "Invalid response structure from Paytm",
            ) from e

    async def link_payment(self, link_id: str) -> LinkPayment:
        """Check payment status for a link.

        Args:
            link_id: Paytm link ID.

        Returns:
            LinkPayment with payment status.

        Raises:
            IntegrationError: If the check fails.
        """
        try:
            from paytmchecksum import PaytmChecksum
        except ImportError:
            raise IntegrationError(
                "paytm",
                "paytmchecksum not installed",
            ) from None

        # Build request body
        body = {
            "body": {
                "linkId": link_id,
            },
            "head": {
                "tokenType": "AES",
                "signature": "",
            },
        }

        # Generate signature
        body_json = json.dumps(body["body"], separators=(",", ":"), sort_keys=True)
        try:
            signature = PaytmChecksum.generateSignature(body_json, self.key_secret)
        except Exception as e:
            raise IntegrationError(
                "paytm-rest",
                "Failed to generate signature",
            ) from e

        body["head"]["signature"] = signature

        # Make request
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}/link/fetchTransaction"
                response = await client.post(url, json=body)
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.warning(f"Failed to fetch link payment status: {e}")
            return LinkPayment(link_id=link_id, paid=False)

        # Parse response
        try:
            transactions = data.get("body", {}).get("transactions", [])
            paid = any(t.get("status") == "SUCCESS" for t in transactions)
            txn_id = transactions[0].get("txn_id") if transactions else None
            return LinkPayment(link_id=link_id, paid=paid, txn_id=txn_id)
        except Exception as e:
            logger.warning(f"Failed to parse link payment response: {e}")
            return LinkPayment(link_id=link_id, paid=False)


class SimulatedPaytmLinks:
    """Simulated Paytm links with deterministic URLs."""

    async def create_premium_link(self, merchant: Merchant, amount_paise: int,
                                  purpose: str) -> PaymentLink:
        """Create a simulated payment link.

        Link URL is deterministic from a hash of the merchant ID.
        Format: https://paytm.me/sim-XXXXXX

        Args:
            merchant: Merchant object.
            amount_paise: Amount in paise.
            purpose: Purpose string for the link.

        Returns:
            PaymentLink with simulated URL.
        """
        # Generate deterministic link ID from merchant ID
        hash_input = f"{merchant.id}:{amount_paise}:{purpose}"
        hash_obj = hashlib.sha256(hash_input.encode())
        hash_hex = hash_obj.hexdigest()[:6].upper()

        link_id = f"SIM-{hash_hex}"
        url = f"https://paytm.me/sim-{hash_hex}"

        return PaymentLink(
            link_id=link_id,
            url=url,
            amount_paise=amount_paise,
            source="simulated",
            created_at=datetime.now(),
        )

    async def link_payment(self, link_id: str) -> LinkPayment:
        """Check payment status for a simulated link.

        Simulated links are marked as unpaid until explicitly marked via a test fixture.

        Args:
            link_id: Paytm link ID.

        Returns:
            LinkPayment with unpaid status.
        """
        return LinkPayment(link_id=link_id, paid=False)
