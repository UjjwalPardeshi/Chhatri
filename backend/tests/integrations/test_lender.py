"""The simulated lender (X4, fs-03 section 7.2): its rule order, its own ledger and its silence when forced."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date, timedelta

import pytest

from chhatri.clock import ist
from chhatri.domain.enums import HolidayReason, HolidayStatus
from chhatri.domain.models import Loan
from chhatri.integrations.base import Lender, LenderNoResponse, LenderRequest
from chhatri.integrations.lender import HOLIDAY_ALLOWANCE, LenderFixtures, SimulatedLender
from chhatri.money import rupees

REQUESTED_AT = ist(2025, 8, 19, 17, 5)
LENDER_NAME = "Simulated lender (NBFC partner)"


def loan(number: int = 142, *, outstanding: int = rupees(36000)) -> Loan:
    return Loan(
        id=f"LN-{number:04d}",
        merchant_id=f"S-{number:04d}",
        lender_name=LENDER_NAME,
        daily_instalment_paise=rupees(600),
        outstanding_paise=outstanding,
    )


def request(loan_id: str = "LN-0142", *, n: int = 1, instalment: date = date(2025, 8, 20)) -> LenderRequest:
    return LenderRequest(
        request_id=f"HR-{n:06d}",
        merchant_id=f"S-{loan_id[-4:]}",
        loan_id=loan_id,
        decision_id="D-000142",
        payout_id="P-000142",
        payout_credited_at=ist(2025, 8, 19, 17, 4),
        instalment_date=instalment,
        instalment_paise=rupees(600),
        requested_at=REQUESTED_AT,
    )


def book(*loans: Loan) -> dict[str, Loan]:
    return {item.merchant_id: item for item in loans}


async def test_lender_grants_by_default_and_moves_the_instalment_to_the_end() -> None:
    lender: Lender = SimulatedLender(book(loan()))
    answer = await lender.request_holiday(request())
    assert (answer.decision, answer.reason_code) == (HolidayStatus.GRANTED, None)
    assert (answer.moved_to, answer.penalty_paise) == ("END_OF_TENURE", 0)
    assert (answer.request_id, answer.loan_id, answer.decided_at) == ("HR-000001", "LN-0142", REQUESTED_AT)
    assert answer.lender == LENDER_NAME


async def test_lender_rule_order_and_reasons() -> None:
    """L4, L1, L2, L3 in that order: the first failing rule is the reason returned."""
    everything_fails = loan(outstanding=0)
    fixtures = LenderFixtures(
        programme_off=frozenset({everything_fails.id}),
        in_arrears=frozenset({everything_fails.id}),
        prior_holidays={everything_fails.id: HOLIDAY_ALLOWANCE},
    )
    lender = SimulatedLender(book(everything_fails), fixtures=fixtures)
    asked = request(everything_fails.id)

    expected = [
        (fixtures, HolidayReason.FLAG_OFF),
        (replace(fixtures, programme_off=frozenset()), HolidayReason.NOT_ACTIVE),
    ]
    for rule_set, reason in expected:
        answer = await SimulatedLender(book(everything_fails), fixtures=rule_set).request_holiday(asked)
        assert (answer.decision, answer.reason_code) == (HolidayStatus.REFUSED, reason)
        assert (answer.moved_to, answer.penalty_paise) == (None, 0)

    active = loan()
    arrears_and_allowance = LenderFixtures(
        in_arrears=frozenset({active.id}), prior_holidays={active.id: HOLIDAY_ALLOWANCE}
    )
    answer = await SimulatedLender(book(active), fixtures=arrears_and_allowance).request_holiday(request())
    assert answer.reason_code is HolidayReason.IN_ARREARS
    allowance_only = LenderFixtures(prior_holidays={active.id: HOLIDAY_ALLOWANCE})
    answer = await SimulatedLender(book(active), fixtures=allowance_only).request_holiday(request())
    assert answer.reason_code is HolidayReason.NO_ALLOWANCE
    assert lender.ledger == ()  # a refusal is never recorded as a holiday


async def test_a_loan_the_lender_does_not_know_is_outside_the_scheme() -> None:
    answer = await SimulatedLender({}).request_holiday(request("LN-0999"))
    assert (answer.decision, answer.reason_code) == (HolidayStatus.REFUSED, HolidayReason.FLAG_OFF)
    assert answer.lender == LENDER_NAME


async def test_lender_grant_is_recorded_and_counts_toward_allowance() -> None:
    lender = SimulatedLender(book(loan()))
    first_day = date(2025, 8, 20)
    for n in range(1, HOLIDAY_ALLOWANCE + 1):
        answer = await lender.request_holiday(request(n=n, instalment=first_day + timedelta(days=n)))
        assert answer.decision is HolidayStatus.GRANTED
    assert [grant.request_id for grant in lender.ledger] == ["HR-000001", "HR-000002", "HR-000003"]
    assert {grant.loan_id for grant in lender.ledger} == {"LN-0142"}
    over = await lender.request_holiday(request(n=4, instalment=first_day + timedelta(days=9)))
    assert (over.decision, over.reason_code) == (HolidayStatus.REFUSED, HolidayReason.NO_ALLOWANCE)
    assert len(lender.ledger) == HOLIDAY_ALLOWANCE


async def test_a_grant_older_than_a_year_no_longer_counts() -> None:
    lender = SimulatedLender(book(loan()), allowance=1)
    old = replace(request(n=1), requested_at=REQUESTED_AT - timedelta(days=366))
    assert (await lender.request_holiday(old)).decision is HolidayStatus.GRANTED
    assert (await lender.request_holiday(request(n=2))).decision is HolidayStatus.GRANTED
    assert (await lender.request_holiday(request(n=3, instalment=date(2025, 8, 21)))).reason_code is (
        HolidayReason.NO_ALLOWANCE
    )


async def test_the_same_request_id_gets_the_first_answer_and_is_recorded_once() -> None:
    lender = SimulatedLender(book(loan()))
    first = await lender.request_holiday(request())
    second = await lender.request_holiday(request())
    assert second == first
    assert len(lender.ledger) == 1


async def test_lender_fallback_gives_no_answer() -> None:
    forced = True
    lender = SimulatedLender(book(loan()), forced=lambda: forced)
    with pytest.raises(LenderNoResponse):
        await lender.request_holiday(request())
    assert lender.ledger == ()
    forced = False
    assert (await lender.request_holiday(request())).decision is HolidayStatus.GRANTED


def test_the_request_has_only_the_fields_of_the_lender_contract() -> None:
    """fs-03 section 7.3: no claim kind, no reason, no slip data and no amount of the payout."""
    assert set(asdict(request())) == {
        "request_id",
        "merchant_id",
        "loan_id",
        "decision_id",
        "payout_id",
        "payout_credited_at",
        "instalment_date",
        "instalment_paise",
        "requested_at",
        "basis",
    }


def test_a_negative_allowance_is_rejected() -> None:
    with pytest.raises(ValueError, match="allowance cannot be negative"):
        SimulatedLender({"LN-0142": loan()}, allowance=-1)
