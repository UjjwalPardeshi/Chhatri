"""JSON for the H8 ops strip: `GET /api/ops/summary` (fs-08 section 10, data-model-and-api section 5.7).

Counts only, read from the in-memory store of the loaded scenario: no projection, no model, no write. "Now" is
the replay clock and "today" is its IST calendar date. Money is integer paise with a `format_inr` label.

Definitions (fs-08 section 10.2):
- **Open cases**: status OPEN; by kind with every kind listed, zeros included. **Overdue**: OPEN and `due_by`
  before now. **Next due**: the OPEN case with the earliest `due_by` (ties: earlier `opened_at`, then the lower
  case number); `due_in_minutes` is whole minutes (rounded down, so negative once overdue).
- **Claims today**: each claim created today counts once, by its last decision. `automatic`: APPROVED or DECLINED
  by the policy engine. `human`: decided by an officer. `waiting`: REFERRED, no officer has decided yet. A
  dispute is no claim and never changes a claim's final decision. `automatic_share_pct` rounds down, so 100
  means every claim was automatic; null when there are no claims.
- **Payouts today**: payouts created today (the day rule of `GET /api/payouts?date=`). Credited ones are grouped
  by the merchant's zone, zones in number order; PENDING ones are in flight and FAILED ones are counted apart.
- **Holiday requests today** (X4): requests made today by status, null while the flag `x4_lender_request` is off.

`summarise` is the pure part (hand it records, get the dict); `ops_summary` gathers them from a runtime.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Final

from chhatri.clock import IST
from chhatri.domain.enums import CaseKind, CaseStatus, DecisionOutcome, HolidayStatus, PayoutStatus
from chhatri.domain.models import Case, Claim, Decision, HolidayRequest, Payout
from chhatri.features import is_enabled
from chhatri.money import format_inr
from chhatri.policy.engine import OFFICER_ACTOR_PREFIX, POLICY_ENGINE_ACTOR
from chhatri.replay.board import zone_number
from chhatri.replay.view_records import iso

if TYPE_CHECKING:
    from chhatri.replay.state import Runtime

__all__ = ["ops_summary", "summarise"]

LENDER_FLAG: Final = "x4_lender_request"
MINUTE: Final = timedelta(minutes=1)
CASE_PREFIX: Final = "C-"
HOLIDAY_ORDER: Final = (
    HolidayStatus.GRANTED,
    HolidayStatus.REFUSED,
    HolidayStatus.NO_RESPONSE,
    HolidayStatus.REQUESTED,
)
AUTOMATIC, HUMAN, WAITING = "automatic", "human", "waiting"


def _ist_day(value: datetime) -> date:
    return value.astimezone(IST).date()


def _due_order(case: Case) -> tuple[datetime, datetime, int]:
    return case.due_by, case.opened_at, int(case.id.removeprefix(CASE_PREFIX))


def _next_due(case: Case, now: datetime) -> dict[str, Any]:
    return {
        "id": case.id,
        "kind": case.kind.value,
        "merchant_id": case.merchant_id,
        "opened_at": iso(case.opened_at),
        "due_by": iso(case.due_by),
        "due_in_minutes": (case.due_by - now) // MINUTE,
    }


def _cases_part(now: datetime, cases: Sequence[Case]) -> dict[str, Any]:
    open_cases = [c for c in cases if c.status is CaseStatus.OPEN]
    by_kind = Counter(c.kind for c in open_cases)
    next_due = min(open_cases, key=_due_order, default=None)
    return {
        "open_cases": len(open_cases),
        "cases_by_kind": {kind.value: by_kind[kind] for kind in CaseKind},
        "overdue_cases": sum(1 for c in open_cases if c.due_by < now),
        "next_due_case": None if next_due is None else _next_due(next_due, now),
    }


def _who_decided(decision: Decision) -> str | None:
    """`human` for an officer, `waiting` while REFERRED, `automatic` for the engine; None for anyone else."""
    if decision.decided_by.startswith(OFFICER_ACTOR_PREFIX):
        return HUMAN
    if decision.outcome is DecisionOutcome.REFERRED:
        return WAITING
    return AUTOMATIC if decision.decided_by == POLICY_ENGINE_ACTOR else None


def _claims_part(today: date, claims: Sequence[Claim], decisions: Sequence[Decision]) -> dict[str, Any]:
    final = {d.claim_id: d for d in decisions}  # decisions come oldest first: the last one of a claim wins
    kinds = Counter(
        _who_decided(final[c.id]) for c in claims if c.id in final and _ist_day(c.created_at) == today
    )
    automatic, human, waiting = kinds[AUTOMATIC], kinds[HUMAN], kinds[WAITING]
    total = automatic + human + waiting
    return {
        "automatic": automatic,
        "human": human,
        "waiting": waiting,
        "automatic_share_pct": None if total == 0 else 100 * automatic // total,
    }


def _payouts_part(payouts: Sequence[Payout], zone_of: Callable[[str], str]) -> dict[str, Any]:
    credited = [p for p in payouts if p.status is PayoutStatus.CREDITED]
    counts: Counter[str] = Counter()
    paise: Counter[str] = Counter()
    for payout in credited:
        zone = zone_of(payout.merchant_id)
        counts[zone] += 1
        paise[zone] += payout.amount_paise
    total = sum(paise.values())
    return {
        "credited_count": len(credited),
        "credited_paise": total,
        "credited_label": format_inr(total),
        "pending_count": sum(1 for p in payouts if p.status is PayoutStatus.PENDING),
        "failed_count": sum(1 for p in payouts if p.status is PayoutStatus.FAILED),
        "by_zone": {
            zone: {"count": counts[zone], "paise": paise[zone], "label": format_inr(paise[zone])}
            for zone in sorted(counts, key=lambda z: int(zone_number(z)))
        },
    }


def _holiday_part(today: date, requests: Sequence[HolidayRequest] | None) -> dict[str, int] | None:
    if requests is None:
        return None
    counts = Counter(r.status for r in requests if _ist_day(r.requested_at) == today)
    return {status.value: counts[status] for status in HOLIDAY_ORDER}


def summarise(
    *,
    now: datetime,
    cases: Sequence[Case],
    claims: Sequence[Claim],
    decisions: Sequence[Decision],
    payouts: Sequence[Payout],
    zone_of: Callable[[str], str],
    holiday_requests: Sequence[HolidayRequest] | None,
) -> dict[str, Any]:
    """The OpsSummary of the records at `now`. `payouts` are today's (the caller applies the day rule)."""
    today = _ist_day(now)
    return {
        "as_of": iso(now),
        "day": today.isoformat(),
        **_cases_part(now, cases),
        "claims_today": _claims_part(today, claims, decisions),
        "payouts_today": _payouts_part(payouts, zone_of),
        "holiday_requests_today": _holiday_part(today, holiday_requests),
    }


def ops_summary(rt: Runtime) -> dict[str, Any]:
    """OpsSummary (data-model-and-api 5.7) of the loaded scenario at the replay clock; writes nothing."""
    now = rt.clock.now()
    city = rt.static.city
    lender_on = is_enabled(LENDER_FLAG, rt.static.settings)
    return summarise(
        now=now,
        cases=rt.store.cases(),
        claims=rt.store.claims(),
        decisions=rt.store.decisions(),
        payouts=rt.store.payouts(day=_ist_day(now)),
        zone_of=lambda merchant_id: city.merchant(merchant_id).zone_id,
        holiday_requests=rt.store.holiday_requests() if lender_on else None,
    )
