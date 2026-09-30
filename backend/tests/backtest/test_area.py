"""Area payouts of Chhatri and the weather-only baseline (SPEC §4.3, §9.2, §18)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta

import pytest

from chhatri.backtest.area import alerts_by_id, decide_trigger, decide_weather_day
from chhatri.backtest.config import WEATHER_ONLY_DROP_PCT
from chhatri.backtest.ledger import Ledger, Payment
from chhatri.backtest.world import World, backtest_cover, season_covers
from chhatri.clock import at
from chhatri.domain.enums import AlertKind, AlertLevel, ClaimKind, CoverStatus, DecisionOutcome
from chhatri.domain.models import Alert, AreaTrigger, Cover
from chhatri.ids import IdFactory
from chhatri.policy.engine import area_amount, publish_expected_day
from chhatri.policy.rules import PolicyRules
from tests.backtest.conftest import TEST_CONFIG, TEST_SEASON

DAY = date(2024, 7, 9)


def _alert(issued_hour: int = 12) -> Alert:
    return Alert(
        id="A-20240709-01",
        kind=AlertKind.RAIN,
        level=AlertLevel.RED,
        zone_ids=("Z7",),
        issued_at=at(DAY, issued_hour),
        valid_from=at(DAY, 13),
        valid_to=at(DAY, 20),
        source="test",
        headline_en="t",
        headline_hi="t",
    )


def _trigger(index_pct: int = 37) -> AreaTrigger:
    return AreaTrigger(
        id="E-Z7-20240709",
        zone_id="Z7",
        alert_id="A-20240709-01",
        window_start=at(DAY, 14),
        window_end=at(DAY, 17),
        index_pct=index_pct,
        drop_pct=100 - index_pct,
        hourly_index_pct=(40, 35, 36),
        lower_bound_pct=80,
        shops_in_index=46,
        fired_at=at(DAY, 17),
    )


@pytest.fixture(scope="module")
def expected(world: World) -> dict[str, int]:
    ids = world.covered_ids("Z7")
    return {mid: 438_000 + 1_000 * i for i, mid in enumerate(ids)}


def _covers(world: World, rules: PolicyRules) -> Mapping[str, Cover]:
    return season_covers(world, TEST_SEASON, rules.cover.waiting_period_days, TEST_CONFIG.history_end)


def test_backtest_cover_is_active_prepaid_and_bought_before_the_season(
    world: World, rules: PolicyRules
) -> None:
    pilot = next(iter(world.city.covers.values()))
    cover = backtest_cover(pilot, TEST_SEASON, rules.cover.waiting_period_days, TEST_CONFIG.history_end)
    assert cover.status is CoverStatus.ACTIVE
    assert cover.purchased_at.date() < cover.starts_on <= TEST_SEASON.start
    assert cover.prepaid_through == TEST_CONFIG.history_end
    assert (cover.id, cover.merchant_id, cover.premium_per_day_paise) == (
        pilot.id,
        pilot.merchant_id,
        pilot.premium_per_day_paise,
    )
    assert set(_covers(world, rules)) == set(world.city.covers)


def test_chhatri_pays_every_covered_shop_the_policy_amount(
    world: World, rules: PolicyRules, expected: dict[str, int]
) -> None:
    ledger = Ledger()
    outcomes = decide_trigger(
        _trigger(),
        _alert(),
        city=world.city,
        covers=_covers(world, rules),
        expected_day=expected,
        ledger=ledger,
        rules=rules,
        ids=IdFactory(),
    )
    assert [o.merchant_id for o in outcomes] == sorted(expected)
    for o in outcomes:
        amount, _ = area_amount(publish_expected_day(expected[o.merchant_id]), 63, rules)
        assert o.outcome is DecisionOutcome.APPROVED and o.amount_paise == amount
        assert o.credited_at == at(DAY, 17) + timedelta(minutes=4) and o.event_date == DAY
    assert outcomes[0].amount_paise == 138_000  # ½ × ₹4,380 × 63% = ₹1,380 (SPEC §4.3)
    assert len(ledger.payments) == len(expected)
    assert all(p.kind is ClaimKind.AREA and p.paid_on == DAY for p in ledger.payments)


def test_chhatri_declines_cover_bought_after_the_alert_and_repeat_payments(
    world: World, rules: PolicyRules, expected: dict[str, int]
) -> None:
    ledger = Ledger()
    kwargs = dict(city=world.city, expected_day=expected, ledger=ledger, rules=rules, ids=IdFactory())
    early = _alert(issued_hour=12).model_copy(update={"issued_at": at(date(2024, 1, 1), 9)})
    declined = decide_trigger(_trigger(), early, covers=_covers(world, rules), **kwargs)
    assert {o.outcome for o in declined} == {DecisionOutcome.DECLINED}  # COVER_BEFORE_ALERT
    assert not ledger.payments
    decide_trigger(_trigger(), _alert(), covers=_covers(world, rules), **kwargs)
    again = decide_trigger(_trigger(), _alert(), covers=_covers(world, rules), **kwargs)
    assert {o.outcome for o in again} == {DecisionOutcome.DECLINED}  # NOT_ALREADY_PAID
    assert all(o.amount_paise == 0 and o.credited_at is None for o in again)
    uncovered = decide_trigger(_trigger(), _alert(), covers={}, **{**kwargs, "ledger": Ledger()})
    assert {o.outcome for o in uncovered} == {DecisionOutcome.DECLINED}  # COVER_IN_FORCE


def test_chhatri_rejects_a_mismatched_alert(
    world: World, rules: PolicyRules, expected: dict[str, int]
) -> None:
    other = _alert().model_copy(update={"id": "A-20240709-02"})
    with pytest.raises(ValueError, match="names alert"):
        decide_trigger(
            _trigger(),
            other,
            city=world.city,
            covers={},
            expected_day=expected,
            ledger=Ledger(),
            rules=rules,
            ids=IdFactory(),
        )


def test_weather_only_pays_half_of_half_the_expected_day(
    rules: PolicyRules, expected: dict[str, int]
) -> None:
    ledger = Ledger()
    outcomes = decide_weather_day("Z7", DAY, expected_day=expected, ledger=ledger, rules=rules)
    first = outcomes[0]
    assert first.amount_paise == 109_500  # ½ × ₹4,380 × 50% = ₹1,095
    for o in outcomes:
        amount, _ = area_amount(publish_expected_day(expected[o.merchant_id]), WEATHER_ONLY_DROP_PCT, rules)
        assert o.amount_paise == amount and o.outcome is DecisionOutcome.APPROVED
        assert o.decided_at == at(DAY + timedelta(days=1), 0)
        assert o.credited_at is not None and o.credited_at.date() == DAY + timedelta(days=1)
    assert {p.paid_on for p in ledger.payments} == {DAY + timedelta(days=1)}


def test_weather_only_respects_the_annual_limit(rules: PolicyRules, expected: dict[str, int]) -> None:
    ledger = Ledger()
    mid = sorted(expected)[0]
    ledger.record(Payment(mid, "Z7", ClaimKind.AREA, (DAY,), DAY, rules.annual_limit_paise - 1))
    outcomes = decide_weather_day("Z7", DAY, expected_day={mid: expected[mid]}, ledger=ledger, rules=rules)
    assert outcomes[0].outcome is DecisionOutcome.DECLINED and outcomes[0].amount_paise == 0
    assert outcomes[0].credited_at is None


def test_alerts_by_id(world: World) -> None:
    table = alerts_by_id(world.shocks.alerts)
    assert len(table) == len(world.shocks.alerts)
    with pytest.raises(ValueError, match="unique"):
        alerts_by_id([_alert(), _alert()])


def test_nothing_expected_pays_nothing(rules: PolicyRules, expected: dict[str, int]) -> None:
    ledger = Ledger()
    mid = sorted(expected)[0]
    (outcome,) = decide_weather_day("Z7", DAY, expected_day={mid: 0}, ledger=ledger, rules=rules)
    assert outcome.amount_paise == 0 and not outcome.paid
    assert not ledger.payments
