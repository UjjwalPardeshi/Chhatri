"""What the conversation package needs from the rest of the app (SPEC §24.4).

``ClaimsPort`` is the exact §24.4 protocol, implemented by the orchestrator: the conversation never
touches the policy engine, ledger or cases directly. ``ConversationStore`` and ``MerchantDirectory``
are the slices of ``store.repositories.Store`` and ``sim.types.City`` the service reads; both are
satisfied structurally by the real classes (SPEC §24.4 passes ``store: Store`` and ``city: City``).
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from chhatri.domain.enums import CaseStatus
from chhatri.domain.models import Case, Cover, CoverQuote, Decision, Merchant, PremiumPayment, SlipExtraction
from chhatri.store.protocols import MessageLog


@runtime_checkable
class ClaimsPort(Protocol):
    """Implemented by the orchestrator (SPEC §24.4, §24.6)."""

    async def submit_personal_claim(self, merchant_id: str, slip: SlipExtraction, media_id: str) -> Decision:
        """Build the personal claim from the slip, decide it; for REFERRED open the review case."""
        ...

    async def open_dispute(self, merchant_id: str, text: str) -> Case:
        """Open a DISPUTE case for the merchant's latest payout (SPEC §12)."""
        ...

    async def quote_cover(self, merchant_id: str) -> tuple[CoverQuote, PremiumPayment | None]:
        """Quote cover (SPEC §9.5) and create the premium link; None when no link could be made."""
        ...

    def latest_paid_decision(self, merchant_id: str) -> Decision | None:
        """Latest APPROVED decision whose payout is CREDITED."""
        ...

    def open_silence(self, merchant_id: str) -> date | None:
        """First silent day if a check-in is open (no claim filed for it yet)."""
        ...


@runtime_checkable
class ConversationStore(MessageLog, Protocol):
    """Messages + media (``MessageLog``), plus the cover and cases the replies read."""

    def cover(self, merchant_id: str) -> Cover | None: ...

    def cases(self, status: CaseStatus | None = None) -> tuple[Case, ...]: ...


@runtime_checkable
class MerchantDirectory(Protocol):
    """``City.merchant`` — KeyError for an unknown merchant id."""

    def merchant(self, merchant_id: str) -> Merchant: ...
