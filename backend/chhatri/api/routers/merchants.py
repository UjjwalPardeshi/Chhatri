"""Merchant read routes: list, detail and conversation (SPEC §19, §19.2)."""

from __future__ import annotations

from typing import Annotated, Any, Final

from fastapi import APIRouter, Path, Query

from chhatri.api.deps import RuntimeDep, StateDep, merchant_or_404
from chhatri.api.envelope import ok, ok_list
from chhatri.domain.models import Merchant
from chhatri.replay import views

router = APIRouter(prefix="/api/merchants", tags=["merchants"])

DEFAULT_LIMIT: Final = 50
MAX_LIMIT: Final = 500
DEFAULT_MESSAGE_LIMIT: Final = 200
MAX_MESSAGE_LIMIT: Final = 1000
MAX_QUERY_CHARS: Final = 64
MERCHANT_ID_PATTERN: Final = r"^S-\d{4}$"
ZONE_ID_PATTERN: Final = r"^Z\d{1,2}$"

MerchantId = Annotated[str, Path(pattern=MERCHANT_ID_PATTERN)]


def _matches(merchant: Merchant, zone_id: str | None, needle: str | None) -> bool:
    if zone_id is not None and merchant.zone_id != zone_id:
        return False
    if not needle:
        return True
    haystack = (merchant.id, merchant.shop_name, merchant.owner_name)
    return any(needle in value.casefold() for value in haystack)


@router.get("")
async def list_merchants(
    state: StateDep,
    runtime: RuntimeDep,
    zone_id: Annotated[str | None, Query(pattern=ZONE_ID_PATTERN)] = None,
    q: Annotated[str | None, Query(max_length=MAX_QUERY_CHARS)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Merchants filtered by zone and a case-insensitive search over id, shop and owner name."""
    needle = q.strip().casefold() if q else None
    matching = [m for m in state.static.city.merchants if _matches(m, zone_id, needle)]
    page = matching[offset : offset + limit]
    items = [views.merchant_summary(runtime, merchant.id) for merchant in page]
    return ok_list(items, total=len(matching), limit=limit, offset=offset)


@router.get("/{merchant_id}")
async def merchant_detail(state: StateDep, runtime: RuntimeDep, merchant_id: MerchantId) -> dict[str, Any]:
    """Merchant, cover, loan, expected today, payouts and decisions (SPEC §19.2 MerchantDetail)."""
    merchant_or_404(state, merchant_id)
    return ok(views.merchant_detail(runtime, merchant_id))


@router.get("/{merchant_id}/cover")
async def merchant_cover(state: StateDep, runtime: RuntimeDep, merchant_id: MerchantId) -> dict[str, Any]:
    """The cover card (K6, data-model 5.1): derived status, dates, zone price, limit and the alert in force."""
    merchant_or_404(state, merchant_id)
    return ok(views.cover_view(runtime, merchant_id))


@router.get("/{merchant_id}/claims")
async def merchant_claims(state: StateDep, runtime: RuntimeDep, merchant_id: MerchantId) -> dict[str, Any]:
    """The claim tracker (K5, data-model 5.1): every claim with its five steps and every dispute, newest first."""
    merchant_or_404(state, merchant_id)
    items = views.claims_view(runtime, merchant_id)
    return ok_list(items, total=len(items), limit=len(items), offset=0)


@router.get("/{merchant_id}/messages")
async def merchant_messages(
    state: StateDep,
    runtime: RuntimeDep,
    merchant_id: MerchantId,
    limit: Annotated[int, Query(ge=1, le=MAX_MESSAGE_LIMIT)] = DEFAULT_MESSAGE_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """The merchant's conversation, oldest first."""
    merchant_or_404(state, merchant_id)
    messages = runtime.store.messages(merchant_id)
    items = [views.message_view(message) for message in messages[offset : offset + limit]]
    return ok_list(items, total=len(messages), limit=limit, offset=offset)
