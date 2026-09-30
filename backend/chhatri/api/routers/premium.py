"""POST /api/premium/link — quote cover and create the premium payment link (SPEC §19, §14.3, §9.7).

Officer-authenticated. The policy engine produces the quote (a BLOCKED quote still carries the
future start date and, when a link is issued, the link for later cover — SPEC §13.5 BUY_COVER).
``CoverQuote`` and ``PremiumPayment`` have no §19.2 shape, so they are rendered here; money fields
carry ``format_inr`` labels like every §19.2 type. The Paytm key never leaves the server.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from chhatri.api.deps import RuntimeDep, StateDep, merchant_or_404, require_officer
from chhatri.api.envelope import ok
from chhatri.api.errors import ApiError
from chhatri.api.requests import PremiumLinkRequest
from chhatri.domain.models import CoverQuote, PremiumPayment
from chhatri.integrations.base import IntegrationError
from chhatri.money import format_inr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/premium", tags=["premium"])


def quote_view(quote: CoverQuote) -> dict[str, Any]:
    """JSON for a cover quote (schema ``CoverQuoteView``)."""
    return {
        "id": quote.id,
        "merchant_id": quote.merchant_id,
        "outcome": quote.outcome.value,
        "requested_at": quote.requested_at.isoformat(),
        "starts_on": quote.starts_on.isoformat(),
        "premium_per_day_paise": quote.premium_per_day_paise,
        "premium_per_day_label": format_inr(quote.premium_per_day_paise),
        "first_payment_paise": quote.first_payment_paise,
        "first_payment_label": format_inr(quote.first_payment_paise),
        "days_prepaid": quote.days_prepaid,
        "reason_en": quote.reason_en,
        "reason_hi": quote.reason_hi,
        "blocking_alert_id": quote.blocking_alert_id,
    }


def premium_view(premium: PremiumPayment) -> dict[str, Any]:
    """JSON for a premium payment (schema ``PremiumPaymentView``)."""
    return {
        "id": premium.id,
        "merchant_id": premium.merchant_id,
        "amount_paise": premium.amount_paise,
        "amount_label": format_inr(premium.amount_paise),
        "method": premium.method.value,
        "covers_from": premium.covers_from.isoformat(),
        "covers_to": premium.covers_to.isoformat(),
        "status": premium.status.value,
        "link_id": premium.link_id,
        "link_url": premium.link_url,
        "source": premium.source,
        "created_at": premium.created_at.isoformat(),
        "paid_at": premium.paid_at.isoformat() if premium.paid_at else None,
    }


@router.post("/link")
async def premium_link(
    _officer: Annotated[str, Depends(require_officer)],
    state: StateDep,
    runtime: RuntimeDep,
    body: PremiumLinkRequest,
) -> dict[str, Any]:
    """Quote cover for ``merchant_id`` and return the Paytm link (staging when live)."""
    merchant_or_404(state, body.merchant_id)
    try:
        quote, premium = await runtime.orchestrator.quote_cover(body.merchant_id)
    except IntegrationError as exc:
        logger.warning("payment link failed: %s", exc.safe_message)
        raise ApiError(502, "payment link service unavailable") from exc
    return ok({"quote": quote_view(quote), "premium": premium_view(premium) if premium else None})
