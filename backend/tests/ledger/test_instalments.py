"""SPEC §10 InstalmentService: pause event_date + 1 with the simulated lender, once, audited.

The BUILT unconditional pause (`pause_next`, the flag-off path) is tested first; the X4 request to the lender
(`request_holiday`, fs-03 sections 7 and 12) follows.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import date, timedelta

import pytest

from chhatri.audit.log import AuditLog
from chhatri.clock import ist
from chhatri.domain.enums import DecisionOutcome, HolidayReason, HolidayStatus, PayoutStatus
from chhatri.domain.models import Decision, HolidayRequest, Payout
from chhatri.ids import IdFactory
from chhatri.integrations.base import LenderAnswer, LenderNoResponse, LenderRequest
from chhatri.integrations.lender import HOLIDAY_ALLOWANCE, LenderFixtures, SimulatedLender
from chhatri.ledger.instalments import LENDER, InstalmentService
from chhatri.money import rupees
from chhatri.policy.engine import evaluate_area_claim
from chhatri.policy.rules import default_rules
from chhatri.store.repositories import Store
from tests.policy import builders as b

PAUSE_AT = ist(2025, 8, 19, 17, 5)
CREDITED_AT = ist(2025, 8, 19, 17, 4)
EVENT = date(2025, 8, 19)


@pytest.fixture
def service(store: Store, audit: AuditLog, ids: IdFactory) -> InstalmentService:
    return InstalmentService(store, audit, ids)


def decision(**kw: object) -> Decision:
    d = evaluate_area_claim(b.area_facts(), default_rules(), decision_id="D-000001", now=ist(2025, 8, 19, 17))
    return d.model_copy(update=kw) if kw else d


def test_pauses_tomorrows_instalment(service: InstalmentService, store: Store, audit: AuditLog) -> None:
    pause = service.pause_next("S-0142", EVENT, decision(), PAUSE_AT)
    assert pause is not None
    assert (pause.id, pause.loan_id, pause.instalment_date) == ("IP-000001", "L-S-0142", date(2025, 8, 20))
    assert (pause.amount_paise, pause.decision_id, pause.created_at) == (rupees(600), "D-000001", PAUSE_AT)
    assert LENDER == "Simulated lender (NBFC partner)"
    assert LENDER in pause.reason and "end of the tenure" in pause.reason and "₹600" in pause.reason
    assert store.pauses("S-0142") == (pause,)
    [entry] = audit.entries()
    assert (entry.action, entry.actor, entry.at) == ("instalment.pause", "workflow:payout", PAUSE_AT)
    assert entry.data["lender"] == LENDER and entry.data["instalment_date"] == "2025-08-20"
    assert entry.data["penalty_paise"] == 0


def test_second_pause_for_same_day_is_none(service: InstalmentService, store: Store) -> None:
    assert service.pause_next("S-0142", EVENT, decision(), PAUSE_AT) is not None
    assert service.pause_next("S-0142", EVENT, decision(), PAUSE_AT) is None
    assert len(store.pauses()) == 1


def test_no_loan_means_no_pause(service: InstalmentService, store: Store) -> None:
    d = decision(merchant_id="S-0907")
    assert service.pause_next("S-0907", EVENT, d, PAUSE_AT) is None
    assert store.pauses() == ()


def test_rejects_other_merchant_or_unapproved(service: InstalmentService) -> None:
    with pytest.raises(ValueError, match="is for"):
        service.pause_next("S-0907", EVENT, decision(), PAUSE_AT)
    with pytest.raises(ValueError, match="only APPROVED"):
        service.pause_next("S-0142", EVENT, decision(outcome=DecisionOutcome.REFERRED), PAUSE_AT)


# ----------------------------------------------------------------------------- X4: the lender decides


def payout_for(d: Decision, status: PayoutStatus = PayoutStatus.CREDITED) -> Payout:
    return Payout(
        id="P-000001",
        decision_id=d.id,
        merchant_id=d.merchant_id,
        amount_paise=d.amount_paise,
        status=status,
        rail="Paytm settlement (simulated)",
        created_at=ist(2025, 8, 19, 17, 0),
        credited_at=CREDITED_AT if status is PayoutStatus.CREDITED else None,
        reference="SIM-D-000001",
    )


@pytest.fixture
def paid(store: Store) -> Decision:
    """Anil's APPROVED decision with its CREDITED payout in the store."""
    d = decision()
    store.add_payout(payout_for(d))
    return d


def holiday_service(
    store: Store, audit: AuditLog, ids: IdFactory, lender: object | None = None, **kw: float
) -> InstalmentService:
    chosen = lender if lender is not None else SimulatedLender(store.city.loans)
    return InstalmentService(store, audit, ids, lender=chosen, **kw)  # type: ignore[arg-type]


class RecordingLender:
    """A lender that records what it was asked and answers through `reply`."""

    def __init__(self, reply: object = None) -> None:
        self.asked: list[LenderRequest] = []
        self._reply = reply

    async def request_holiday(self, request: LenderRequest) -> LenderAnswer:
        self.asked.append(request)
        if callable(self._reply):
            return await self._reply(request)  # type: ignore[no-any-return]
        return await SimulatedLender(b.city().loans).request_holiday(request)


async def test_a_grant_records_the_request_the_pause_and_three_audit_entries(
    store: Store, audit: AuditLog, ids: IdFactory, paid: Decision
) -> None:
    outcome = await holiday_service(store, audit, ids).request_holiday("S-0142", EVENT, paid, PAUSE_AT)
    assert outcome is not None and outcome.pause is not None
    request, pause = outcome.request, outcome.pause
    assert (request.id, request.status, request.reason_code) == ("HR-000001", HolidayStatus.GRANTED, None)
    assert (request.merchant_id, request.loan_id, request.decision_id) == ("S-0142", "L-S-0142", paid.id)
    assert (request.payout_id, request.instalment_date, request.instalment_paise) == (
        "P-000001",
        date(2025, 8, 20),
        rupees(600),
    )
    assert (request.requested_at, request.decided_at) == (PAUSE_AT, PAUSE_AT)
    assert (pause.id, pause.request_id, pause.instalment_date) == ("IP-000001", request.id, date(2025, 8, 20))
    assert LENDER in pause.reason and "end of the tenure" in pause.reason
    assert store.holiday_requests("S-0142") == (request,) and store.pauses("S-0142") == (pause,)
    assert [e.action for e in audit.entries()] == [
        "instalment.holiday_request",
        "instalment.holiday_decision",
        "instalment.pause",
    ]
    asked, decided, paused = audit.entries()
    assert {e.actor for e in (asked, decided, paused)} == {"workflow:payout"}
    assert (asked.subject_type, asked.subject_id, decided.subject_id, paused.subject_id) == (
        "holiday_request",
        request.id,
        request.id,
        pause.id,
    )
    assert decided.data["decision"] == "GRANTED" and decided.data["reason_code"] is None
    assert (decided.data["moved_to"], decided.data["penalty_paise"]) == ("END_OF_TENURE", 0)
    assert paused.data["request_id"] == request.id and paused.data["lender"] == LENDER
    assert audit.verify()["valid"]


async def test_request_waits_for_a_credited_payout(store: Store, audit: AuditLog, ids: IdFactory) -> None:
    """G2: a PENDING payout, or none yet, means no request. The skip is audited and nothing else is."""
    d = decision()
    lender = RecordingLender()
    service = holiday_service(store, audit, ids, lender)
    assert await service.request_holiday("S-0142", EVENT, d, PAUSE_AT) is None  # no payout record at all
    store.add_payout(payout_for(d, PayoutStatus.PENDING))
    assert await service.request_holiday("S-0142", EVENT, d, PAUSE_AT) is None
    assert lender.asked == [] and store.holiday_requests() == () and store.pauses() == ()
    skipped = audit.entries()
    assert [e.action for e in skipped] == ["instalment.holiday_skipped"] * 2
    assert skipped[1].data == {
        "merchant_id": "S-0142",
        "decision_id": d.id,
        "reason": "PAYOUT_NOT_CREDITED",
        "payout_status": "PENDING",
    }
    assert skipped[0].data["payout_status"] is None
    store.replace_payout(payout_for(d))  # credited: the same step now goes through
    assert await service.request_holiday("S-0142", EVENT, d, PAUSE_AT) is not None


async def test_request_is_idempotent_per_instalment(
    store: Store, audit: AuditLog, ids: IdFactory, paid: Decision
) -> None:
    """G4: one request per loan and instalment date, so one lender call and one request id."""
    lender = RecordingLender()
    service = holiday_service(store, audit, ids, lender)
    first = await service.request_holiday("S-0142", EVENT, paid, PAUSE_AT)
    assert first is not None
    assert await service.request_holiday("S-0142", EVENT, paid, PAUSE_AT) is None
    assert [r.request_id for r in lender.asked] == ["HR-000001"]
    assert len(store.holiday_requests()) == 1 and len(store.pauses()) == 1
    assert [e.action for e in audit.entries()].count("instalment.holiday_request") == 1
    next_day = await service.request_holiday("S-0142", EVENT + timedelta(days=1), paid, PAUSE_AT)
    assert next_day is not None and next_day.request.id == "HR-000002"  # another instalment, another request


async def test_no_loan_means_no_request(store: Store, audit: AuditLog, ids: IdFactory) -> None:
    """G3: a merchant without a loan gets nothing, not even a skip entry."""
    d = decision(merchant_id="S-0907")
    store.add_payout(payout_for(d))
    lender = RecordingLender()
    assert (
        await holiday_service(store, audit, ids, lender).request_holiday("S-0907", EVENT, d, PAUSE_AT) is None
    )
    assert lender.asked == [] and store.holiday_requests() == () and audit.entries() == ()


async def test_request_rejects_other_merchant_or_unapproved(
    store: Store, audit: AuditLog, ids: IdFactory, paid: Decision
) -> None:
    """G1: only an APPROVED decision of that merchant can lead to a request."""
    service = holiday_service(store, audit, ids)
    with pytest.raises(ValueError, match="is for"):
        await service.request_holiday("S-0907", EVENT, paid, PAUSE_AT)
    with pytest.raises(ValueError, match="only APPROVED"):
        await service.request_holiday("S-0142", EVENT, decision(outcome=DecisionOutcome.REFERRED), PAUSE_AT)
    assert store.holiday_requests() == ()


REFUSALS = [
    (HolidayReason.FLAG_OFF, LenderFixtures(programme_off=frozenset({"L-S-0142"}))),
    (HolidayReason.IN_ARREARS, LenderFixtures(in_arrears=frozenset({"L-S-0142"}))),
    (HolidayReason.NO_ALLOWANCE, LenderFixtures(prior_holidays={"L-S-0142": HOLIDAY_ALLOWANCE})),
]


@pytest.mark.parametrize(("reason", "fixtures"), REFUSALS, ids=[r.value for r, _ in REFUSALS])
async def test_refusal_creates_no_pause(
    store: Store,
    audit: AuditLog,
    ids: IdFactory,
    paid: Decision,
    reason: HolidayReason,
    fixtures: LenderFixtures,
) -> None:
    lender = SimulatedLender(store.city.loans, fixtures=fixtures)
    outcome = await holiday_service(store, audit, ids, lender).request_holiday(
        "S-0142", EVENT, paid, PAUSE_AT
    )
    assert outcome is not None and outcome.pause is None
    assert (outcome.request.status, outcome.request.reason_code) == (HolidayStatus.REFUSED, reason)
    assert outcome.request.decided_at == PAUSE_AT
    assert store.pauses() == () and store.holiday_requests("S-0142") == (outcome.request,)
    assert [e.action for e in audit.entries()] == [
        "instalment.holiday_request",
        "instalment.holiday_decision",
    ]
    assert (
        audit.entries()[1].data["decision"] == "REFUSED"
        and audit.entries()[1].data["reason_code"] == reason.value
    )
    assert store.payout_for_decision(paid.id) == payout_for(paid)  # the payout is untouched, still CREDITED


async def test_a_loan_that_is_not_active_is_refused_not_active(
    store: Store, audit: AuditLog, ids: IdFactory, paid: Decision
) -> None:
    settled = {"S-0142": b.loan().model_copy(update={"outstanding_paise": 0})}
    outcome = await holiday_service(store, audit, ids, SimulatedLender(settled)).request_holiday(
        "S-0142", EVENT, paid, PAUSE_AT
    )
    assert outcome is not None and outcome.request.reason_code is HolidayReason.NOT_ACTIVE
    assert store.pauses() == ()


class SilentLender:
    async def request_holiday(self, request: LenderRequest) -> LenderAnswer:
        raise LenderNoResponse()


class BrokenLender:
    async def request_holiday(self, request: LenderRequest) -> LenderAnswer:
        raise RuntimeError("lender exploded")


class SlowLender:
    async def request_holiday(self, request: LenderRequest) -> LenderAnswer:
        await asyncio.sleep(5)
        raise AssertionError("the time limit should have cut this off")


class WrongAnswerLender:
    """Answers another request's id: not an answer to this request."""

    async def request_holiday(self, request: LenderRequest) -> LenderAnswer:
        answer = await SimulatedLender(b.city().loans).request_holiday(request)
        return LenderAnswer(**{**asdict(answer), "request_id": "HR-999999"})


@pytest.mark.parametrize(
    "lender",
    [SilentLender(), BrokenLender(), SlowLender(), WrongAnswerLender()],
    ids=["forced to fallback", "error", "time limit", "answer to another request"],
)
async def test_no_answer_is_never_a_grant(
    store: Store, audit: AuditLog, ids: IdFactory, paid: Decision, lender: object
) -> None:
    service = holiday_service(store, audit, ids, lender, timeout_seconds=0.05)
    outcome = await service.request_holiday("S-0142", EVENT, paid, PAUSE_AT)
    assert outcome is not None and outcome.pause is None
    assert (outcome.request.status, outcome.request.reason_code) == (HolidayStatus.NO_RESPONSE, None)
    assert outcome.request.decided_at == PAUSE_AT
    assert store.pauses() == () and store.payout_for_decision(paid.id) == payout_for(paid)
    decided = audit.entries()[1]
    assert (decided.action, decided.data["decision"]) == ("instalment.holiday_decision", "NO_RESPONSE")
    # one attempt, no retry: asking again for the same instalment sends nothing
    assert await service.request_holiday("S-0142", EVENT, paid, PAUSE_AT) is None


async def test_request_carries_no_claim_reason_or_amount(
    store: Store, audit: AuditLog, ids: IdFactory, paid: Decision
) -> None:
    lender = RecordingLender()
    await holiday_service(store, audit, ids, lender).request_holiday("S-0142", EVENT, paid, PAUSE_AT)
    [sent] = lender.asked
    assert asdict(sent) == {
        "request_id": "HR-000001",
        "merchant_id": "S-0142",
        "loan_id": "L-S-0142",
        "decision_id": paid.id,
        "payout_id": "P-000001",
        "payout_credited_at": CREDITED_AT,
        "instalment_date": date(2025, 8, 20),
        "instalment_paise": rupees(600),
        "requested_at": PAUSE_AT,
        "basis": "Pre-agreed rule: one instalment holiday after a credited Chhatri payout",
    }
    assert paid.amount_paise not in asdict(sent).values()  # the payout amount never reaches the lender
    audited = [e.data for e in audit.entries()]
    assert all("slip" not in str(data) and "claim" not in str(data) for data in audited)


def test_a_holiday_request_that_contradicts_its_status_is_rejected() -> None:
    base = {
        "id": "HR-000001",
        "merchant_id": "S-0142",
        "loan_id": "L-S-0142",
        "decision_id": "D-000001",
        "payout_id": "P-000001",
        "instalment_date": date(2025, 8, 20),
        "instalment_paise": rupees(600),
        "requested_at": PAUSE_AT,
    }
    HolidayRequest(**base, status=HolidayStatus.REQUESTED)
    with pytest.raises(ValueError, match="REFUSED needs a reason code"):
        HolidayRequest(**base, status=HolidayStatus.REFUSED, decided_at=PAUSE_AT)
    with pytest.raises(ValueError, match="only a refusal has a reason code"):
        HolidayRequest(
            **base, status=HolidayStatus.GRANTED, reason_code=HolidayReason.FLAG_OFF, decided_at=PAUSE_AT
        )
    with pytest.raises(ValueError, match="needs a decision time"):
        HolidayRequest(**base, status=HolidayStatus.NO_RESPONSE)
    with pytest.raises(ValueError, match="REQUESTED has no decision yet"):
        HolidayRequest(**base, status=HolidayStatus.REQUESTED, decided_at=PAUSE_AT)


async def test_request_holiday_needs_a_lender_and_a_positive_time_limit(
    store: Store, audit: AuditLog, ids: IdFactory, paid: Decision
) -> None:
    """The service refuses a nonsense set-up loudly: asking without a lender, or a time limit of zero."""
    with pytest.raises(RuntimeError, match="needs a lender"):
        await InstalmentService(store, audit, ids).request_holiday("S-0142", EVENT, paid, PAUSE_AT)
    with pytest.raises(ValueError, match="time limit must be positive"):
        InstalmentService(store, audit, ids, lender=RecordingLender(), timeout_seconds=0)
