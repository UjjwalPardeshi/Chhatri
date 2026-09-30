"""Simulated Paytm payment links (SPEC §14.3, §0.1): `https://paytm.me/sim-XXXXXX`, marked SIMULATED.

Link codes are a deterministic function of (merchant, amount, purpose, per-instance sequence), and
`created_at` comes from the injected (simulated) clock, so the same scenario always produces the same
links. Payment is confirmed by the Paytm webhook route (`POST /api/webhooks/paytm`), so a simulated
link reports "unpaid" here; an unknown link id is an error, never a silent "unpaid".
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable
from datetime import datetime

from chhatri.domain.models import Merchant
from chhatri.integrations.base import IntegrationError, LinkPayment, PaymentLink
from chhatri.integrations.paytm_common import format_amount

SOURCE = "simulated"
SIM_URL_PREFIX = "https://paytm.me/sim-"
CODE_LENGTH = 6


class SimulatedPaytmLinks:
    """PaymentLinks that never touch the network."""

    def __init__(self, *, clock: Callable[[], datetime]) -> None:
        self._clock = clock
        self._links: dict[str, PaymentLink] = {}
        self._lock = threading.Lock()

    async def create_premium_link(self, merchant: Merchant, amount_paise: int, purpose: str) -> PaymentLink:
        amount = format_amount(amount_paise)
        with self._lock:
            sequence = len(self._links)
            code = ""
            while not code or f"sim-{code}" in self._links:
                sequence += 1
                digest = hashlib.sha256(f"{merchant.id}|{amount}|{purpose}|{sequence}".encode()).hexdigest()
                code = digest[:CODE_LENGTH].upper()
            link = PaymentLink(
                link_id=f"sim-{code}",
                url=f"{SIM_URL_PREFIX}{code}",
                amount_paise=amount_paise,
                source=SOURCE,
                created_at=self._clock(),
            )
            self._links[link.link_id] = link
        return link

    async def link_payment(self, link_id: str) -> LinkPayment:
        with self._lock:
            known = link_id in self._links
        if not known:
            raise IntegrationError("paytm", "unknown simulated payment link")
        return LinkPayment(link_id=link_id, paid=False)
