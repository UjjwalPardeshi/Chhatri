"""The simulated lender (X4, fs-03 sections 4 and 7, ADR 0006): it decides an EDI holiday by its own rule.

Chhatri only *requests*. The lender answers from its own records (a copy of the city's loan book plus the
holidays it granted itself) and applies four conditions in a fixed order. The first one that fails is the
reason it returns:

| order | id | condition                                            | reason code     |
|-------|----|------------------------------------------------------|-----------------|
| 1     | L4 | the programme flag is on for this loan                | ``FLAG_OFF``     |
| 2     | L1 | the loan is active (outstanding above zero)           | ``NOT_ACTIVE``   |
| 3     | L2 | the loan is not in arrears                            | ``IN_ARREARS``   |
| 4     | L3 | the holiday allowance is not used up                  | ``NO_ALLOWANCE`` |

A loan the lender has no record of is outside its scheme (``FLAG_OFF``). A grant moves the instalment to the
end of the tenure with penalty 0 and is written to the lender's own ledger, which is what L3 counts over a
rolling 365 days. Nothing is set by default, so every loan of the storm run is granted and the KPI "instalments
paused" stays at 123; tests and the stage set fixtures to force a refusal.

The request id is the idempotency key: asking twice returns the first answer and records one grant. While the
lender component is forced to FALLBACK (card 4.5) it gives no answer at all and raises ``LenderNoResponse``.
The allowance count is the lender's own board-approved policy, an illustrative number here, not a Chhatri rule.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from types import MappingProxyType
from typing import Final

from chhatri.domain.enums import HolidayReason, HolidayStatus
from chhatri.domain.models import Loan
from chhatri.integrations.base import MOVED_TO_END_OF_TENURE, LenderAnswer, LenderNoResponse, LenderRequest

__all__ = [
    "ALLOWANCE_WINDOW",
    "HOLIDAY_ALLOWANCE",
    "LENDER_NAME",
    "NO_FIXTURES",
    "LenderFixtures",
    "LenderGrant",
    "SimulatedLender",
]

LENDER_NAME: Final = "Simulated lender (NBFC partner)"
HOLIDAY_ALLOWANCE: Final = 3  # holidays per loan in a rolling year: illustrative (fs-03 section 4)
ALLOWANCE_WINDOW: Final = timedelta(days=365)


@dataclass(frozen=True, slots=True)
class LenderFixtures:
    """Facts only the lender knows. Nothing is set by default, so every loan is granted."""

    programme_off: frozenset[str] = frozenset()  # loan ids outside the holiday scheme (L4)
    in_arrears: frozenset[str] = frozenset()  # loan ids with an amount overdue (L2)
    prior_holidays: Mapping[str, int] = field(default_factory=dict)  # holidays already taken this year (L3)

    def __post_init__(self) -> None:
        object.__setattr__(self, "prior_holidays", MappingProxyType(dict(self.prior_holidays)))


NO_FIXTURES: Final = LenderFixtures()


@dataclass(frozen=True, slots=True)
class LenderGrant:
    """One line of the lender's own ledger: a holiday it granted."""

    request_id: str
    loan_id: str
    instalment_date: date
    granted_at: datetime


def _never() -> bool:
    return False


class SimulatedLender:
    """The `Lender` port with its own book, ledger and rule (see the module docstring)."""

    def __init__(
        self,
        loans: Mapping[str, Loan],
        *,
        allowance: int = HOLIDAY_ALLOWANCE,
        fixtures: LenderFixtures = NO_FIXTURES,
        forced: Callable[[], bool] = _never,
    ) -> None:
        if allowance < 0:
            raise ValueError("the holiday allowance cannot be negative")
        self._loans: Mapping[str, Loan] = MappingProxyType({loan.id: loan for loan in loans.values()})
        self._allowance = allowance
        self._fixtures = fixtures
        self._forced = forced
        self._answers: dict[str, LenderAnswer] = {}
        self._grants: list[LenderGrant] = []

    @property
    def ledger(self) -> tuple[LenderGrant, ...]:
        """The holidays this lender granted, oldest first."""
        return tuple(self._grants)

    async def request_holiday(self, request: LenderRequest) -> LenderAnswer:
        if self._forced():
            raise LenderNoResponse("no answer: the lender is forced to FALLBACK")
        known = self._answers.get(request.request_id)
        if known is not None:
            return known
        reason = self._refusal(request)
        answer = self._answer(request, reason)
        self._answers[request.request_id] = answer
        if reason is None:
            self._grants.append(
                LenderGrant(
                    request.request_id, request.loan_id, request.instalment_date, request.requested_at
                )
            )
        return answer

    def _refusal(self, request: LenderRequest) -> HolidayReason | None:
        """The first failing condition in the order L4, L1, L2, L3; None when all hold."""
        loan = self._loans.get(request.loan_id)
        if loan is None or loan.id in self._fixtures.programme_off:
            return HolidayReason.FLAG_OFF
        if loan.outstanding_paise <= 0:
            return HolidayReason.NOT_ACTIVE
        if loan.id in self._fixtures.in_arrears:
            return HolidayReason.IN_ARREARS
        if self._holidays_taken(loan.id, request.requested_at) >= self._allowance:
            return HolidayReason.NO_ALLOWANCE
        return None

    def _holidays_taken(self, loan_id: str, at: datetime) -> int:
        recent = sum(
            1 for g in self._grants if g.loan_id == loan_id and at - ALLOWANCE_WINDOW < g.granted_at <= at
        )
        return self._fixtures.prior_holidays.get(loan_id, 0) + recent

    def _answer(self, request: LenderRequest, reason: HolidayReason | None) -> LenderAnswer:
        loan = self._loans.get(request.loan_id)
        granted = reason is None
        return LenderAnswer(
            request_id=request.request_id,
            loan_id=request.loan_id,
            decision=HolidayStatus.GRANTED if granted else HolidayStatus.REFUSED,
            reason_code=reason,
            moved_to=MOVED_TO_END_OF_TENURE if granted else None,
            penalty_paise=0,
            decided_at=request.requested_at,
            lender=loan.lender_name if loan is not None else LENDER_NAME,
        )
