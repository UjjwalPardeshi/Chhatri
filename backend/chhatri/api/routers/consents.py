"""The consent centre (N6, H23): list, withdraw, activity and "forget my slip" (data-model-and-api section 5.5).

Behind the flag ``n6_consents``: while it is off all four routes answer the ordinary 404 ``not_found``. There is no
merchant login in the prototype, so the two writes need the officer bearer token (the app borrows the console's demo
session, ADR 0005) and the audit actor is the merchant. Reads need no token. Both writes share the ``messages`` limit.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Final, Literal

from fastapi import APIRouter, Depends, Path, Query

from chhatri.api.deps import (
    RuntimeDep,
    StateDep,
    merchant_or_404,
    rate_limit,
    require_feature,
    require_officer,
)
from chhatri.api.envelope import ok, ok_list
from chhatri.api.errors import ApiError
from chhatri.consent.activity import activity_items
from chhatri.consent.errors import ConsentConflict
from chhatri.consent.forget import forget_slip
from chhatri.consent.ledger import ConsentBook, consent_book, install_consents
from chhatri.consent.service import ConsentService

router = APIRouter(
    prefix="/api/merchants", tags=["consents"], dependencies=[Depends(require_feature("n6_consents"))]
)

MERCHANT_ID_PATTERN: Final = r"^S-\d{4}$"
DEFAULT_LIMIT: Final = 50
MAX_LIMIT: Final = 500
MerchantId = Annotated[str, Path(pattern=MERCHANT_ID_PATTERN)]
ConsentId = Annotated[str, Path(pattern=r"^CN-\d{6,}$")]
SlipId = Annotated[str, Path(pattern=r"^MD-\d{6,}$")]
Purpose = Literal["SALES_DATA_FOR_CLAIM", "SLIP_DATA_FOR_HOSPITAL_CLAIM", "SETTLEMENT_DEDUCTION"]
Writes = [Depends(rate_limit("messages"))]


def _book(runtime: Any) -> ConsentBook:
    book = consent_book(runtime.store)
    if book is None:  # a runtime built outside AppState.load: seed now
        book = install_consents(runtime.store, runtime.ids, runtime.audit, runtime.static.settings)
    if book is None:
        raise ApiError(404, "not found")
    return book


def _service(runtime: Any) -> ConsentService:
    return ConsentService(
        store=runtime.store,
        audit=runtime.audit,
        book=_book(runtime),
        waiting_days=runtime.static.rules.cover.waiting_period_days,
    )


@router.get("/{merchant_id}/consents")
async def list_consents(state: StateDep, runtime: RuntimeDep, merchant_id: MerchantId) -> dict[str, Any]:
    """The three purposes with state, texts and held slips; a purpose never agreed to is NOT_GIVEN."""
    merchant_or_404(state, merchant_id)
    items = _service(runtime).list_view(merchant_id)
    return ok_list(items, total=len(items), limit=len(items), offset=0)


@router.get("/{merchant_id}/consents/activity")
async def consent_activity(
    state: StateDep,
    runtime: RuntimeDep,
    merchant_id: MerchantId,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
    purpose: Annotated[Purpose | None, Query()] = None,
) -> dict[str, Any]:
    """What was used, for what and when: a projection of the audit log, newest first."""
    merchant_or_404(state, merchant_id)
    _book(runtime).reconcile(merchant_id)
    items = activity_items(runtime.audit, merchant_id, purpose=purpose)
    return ok_list(items[offset : offset + limit], total=len(items), limit=limit, offset=offset)


@router.post("/{merchant_id}/consents/{consent_id}/withdraw", dependencies=Writes)
async def withdraw_consent(
    _officer: Annotated[str, Depends(require_officer)],
    state: StateDep,
    runtime: RuntimeDep,
    merchant_id: MerchantId,
    consent_id: ConsentId,
) -> dict[str, Any]:
    """Turn one purpose off now; the merchant gets one chat line."""
    merchant_or_404(state, merchant_id)

    async def notify(merchant: str, purpose: str, paid_through: date | None) -> None:
        await runtime.conversation.notify_consent_withdrawn(merchant, purpose, paid_through)

    try:
        result = await _service(runtime).withdraw(
            merchant_id=merchant_id, consent_id=consent_id, now=runtime.clock.now(), notify=notify
        )
    except ConsentConflict as exc:
        raise ApiError(409, str(exc), code=exc.code) from exc
    except KeyError as exc:
        raise ApiError(404, "consent not found") from exc
    return ok(result)


@router.post("/{merchant_id}/slips/{slip_id}/forget", dependencies=Writes)
async def forget_my_slip(
    _officer: Annotated[str, Depends(require_officer)],
    state: StateDep,
    runtime: RuntimeDep,
    merchant_id: MerchantId,
    slip_id: SlipId,
) -> dict[str, Any]:
    """Erase one stored slip; the answer says what stays (the decision) and what cannot be edited (the audit log)."""
    merchant_or_404(state, merchant_id)
    try:
        result = forget_slip(
            store=runtime.store,
            audit=runtime.audit,
            book=_book(runtime),
            merchant_id=merchant_id,
            slip_id=slip_id,
            now=runtime.clock.now(),
        )
    except ConsentConflict as exc:
        raise ApiError(409, str(exc), code=exc.code) from exc
    except KeyError as exc:
        raise ApiError(404, "slip not found") from exc
    return ok(result)
