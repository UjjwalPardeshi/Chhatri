"""Read-only records: decisions, payouts, audit log, policy and backtest (SPEC §19, §11, §9, §18)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Final

from fastapi import APIRouter, Path, Query

from chhatri.api.deps import RuntimeDep, StateDep
from chhatri.api.envelope import ok, ok_list
from chhatri.api.errors import ApiError
from chhatri.replay import views

router = APIRouter(prefix="/api", tags=["records"])

DECISION_ID_PATTERN: Final = r"^D-\d{6,}$"
ZONE_ID_PATTERN: Final = r"^Z\d{1,2}$"
DEFAULT_LIMIT: Final = 200
MAX_LIMIT: Final = 1000


@router.get("/decisions/{decision_id}")
async def get_decision(
    runtime: RuntimeDep, decision_id: Annotated[str, Path(pattern=DECISION_ID_PATTERN)]
) -> dict[str, Any]:
    """One decision with its checks and explanation (SPEC §19.2 Decision)."""
    try:
        decision = runtime.store.decision(decision_id)
    except KeyError as exc:
        raise ApiError(404, f"decision {decision_id} not found") from exc
    return ok(views.decision_view(decision))


@router.get("/payouts")
async def list_payouts(
    runtime: RuntimeDep,
    zone_id: Annotated[str | None, Query(pattern=ZONE_ID_PATTERN)] = None,
    day: Annotated[date | None, Query(alias="date")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Payouts filtered by zone and/or day (``date=YYYY-MM-DD``)."""
    payouts = runtime.store.payouts(zone_id=zone_id, day=day)
    items = [views.payout_view(payout) for payout in payouts[offset : offset + limit]]
    return ok_list(items, total=len(payouts), limit=limit, offset=offset)


@router.get("/audit")
async def list_audit(
    runtime: RuntimeDep,
    after: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Audit entries with ``seq > after``; ``meta.offset`` is ``after`` (seqs are contiguous from 1)."""
    entries = runtime.audit.entries(after=after, limit=limit)
    items = [views.audit_view(entry) for entry in entries]
    return ok_list(items, total=len(runtime.audit), limit=limit, offset=after)


@router.get("/audit/verify")
async def verify_audit(runtime: RuntimeDep) -> dict[str, Any]:
    """Recompute the hash chain: ``{valid, entries, head_hash, first_bad_seq}`` (SPEC §11)."""
    return ok(runtime.audit.verify())


@router.get("/policy")
async def policy(state: StateDep) -> dict[str, Any]:
    """Rules and the payout authority table (SPEC §9.4, deck slide 8)."""
    return ok(views.policy_view(state.static.rules))


@router.get("/backtest")
async def backtest(state: StateDep) -> dict[str, Any]:
    """The committed backtest report (SPEC §18); 404 until ``make data`` has produced it."""
    report = state.static.backtest_report
    if report is None:
        raise ApiError(404, "backtest report has not been generated (run make data)")
    return ok(report)
