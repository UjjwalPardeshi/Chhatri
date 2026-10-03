"""Personal claims from silent-shop detection (SPEC §8.3, §9.2, §9.3)."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from chhatri.backtest.ledger import Ledger, Payment
from chhatri.backtest.personal import (
    CLAIM_HOUR,
    PersonalClaimPlan,
    decide_personal,
    episodes,
    outreach_day,
    plan_claims,
    silent_findings,
    without_doctor_check,
    zero_trade_mask,
)
from chhatri.backtest.slips import OTHER_PATIENT_NAME, SlipKind, slip_kind
from chhatri.backtest.world import World, season_covers
from chhatri.clock import at
from chhatri.detect.silent import find_silent
from chhatri.detect.types import SilentFinding
from chhatri.domain.enums import ClaimKind, DecisionOutcome
from chhatri.domain.models import SlipExtraction
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.ids import IdFactory
from chhatri.policy.rules import PolicyRules, default_rules
from tests.backtest.conftest import TEST_CONFIG, TEST_SEASON

SEED = 20251019


@pytest.fixture(scope="module")
def plans(world: World, model: ExpectedSalesModel) -> tuple[PersonalClaimPlan, ...]:
    return plan_claims(world, model, TEST_SEASON, {}, SEED, workers=2)


def test_zero_trade_mask(world: World) -> None:
    days = TEST_SEASON.days[:3]
    mask = zero_trade_mask(world, days)
    assert mask.shape == (len(world.city.merchants), 3)
    for row in np.flatnonzero(mask[:, 0])[:5]:
        merchant = world.city.merchants[int(row)]
        assert merchant.id in world.city.covers
        assert merchant.weekly_off != days[0].weekday()
        assert world.history.day(days[0]).txns[row].sum() == 0


def test_silent_findings_match_find_silent_over_all_covered(world: World, model: ExpectedSalesModel) -> None:
    covered = world.covered_ids()
    zones = {date(2024, 7, 14): frozenset({"Z7"})}
    got = silent_findings(world, model, TEST_SEASON, zones)
    assert got
    brute: list[SilentFinding] = []
    for day in TEST_SEASON.days:
        ranges = model.day_ranges_paise(world.city, world.history, day, covered)
        brute.extend(find_silent(day, world.city, world.history, ranges, zones.get(day, frozenset())))
    assert got == tuple(brute)


def _finding(mid: str, day: date) -> SilentFinding:
    return SilentFinding(merchant_id=mid, day=day, expected_day_paise=438_000, p10_day_paise=100)


def test_episodes_bridge_weekly_off_and_area_days(world: World) -> None:
    merchant = next(m for m in world.city.merchants if m.weekly_off is not None and m.id in world.city.covers)
    monday = date(2024, 7, 1)
    off = monday + timedelta(days=(merchant.weekly_off - monday.weekday()) % 7 + 7)
    before, after = off - timedelta(days=1), off + timedelta(days=1)
    far = after + timedelta(days=3)
    area = {far - timedelta(days=1): frozenset({merchant.zone_id})}
    findings = [_finding(merchant.id, d) for d in (after, before, far - timedelta(days=2), far)]
    grouped = episodes(world, findings, area)
    assert [tuple(f.day for f in ep) for ep in grouped] == [
        (before, after, far - timedelta(days=2), far),
    ]
    split = episodes(world, [_finding(merchant.id, before), _finding(merchant.id, far)], {})
    assert len(split) == 2


def test_outreach_skips_the_weekly_off(world: World) -> None:
    merchant = next(m for m in world.city.merchants if m.weekly_off is not None)
    first = date(2024, 7, 1)
    while (first + timedelta(days=1)).weekday() != merchant.weekly_off:
        first += timedelta(days=1)
    assert outreach_day(world, merchant.id, first) == first + timedelta(days=2)
    open_every_day = next(m for m in world.city.merchants if m.weekly_off is None)
    assert outreach_day(world, open_every_day.id, first) == first + timedelta(days=1)


def test_plans_are_contacted_episodes_in_claim_order(
    world: World, plans: tuple[PersonalClaimPlan, ...]
) -> None:
    assert plans
    assert list(plans) == sorted(plans, key=lambda p: (p.claim_at, p.merchant_id))
    for plan in plans:
        assert plan.claim_at == at(plan.silent_dates[-1] + timedelta(days=1), CLAIM_HOUR)
        assert plan.expected_day_published % 1000 == 0  # published to ₹10
        assert plan.zone_id == world.city.merchant(plan.merchant_id).zone_id
        assert plan.slip.source == "simulated"
        merchant = world.city.merchant(plan.merchant_id)
        kind = slip_kind(SEED, merchant, plan.silent_dates[0])
        assert plan.doubtful_slip is (kind is not SlipKind.CLEAN)
        assert _slip_matches_kind(plan, merchant.owner_name, kind)


def _slip_matches_kind(plan: PersonalClaimPlan, owner: str, kind: SlipKind) -> bool:
    """The slip read back by the simulated reader is the one `slips.SlipKind` describes."""
    slip, first = plan.slip, plan.silent_dates[0]
    if kind is SlipKind.UNREADABLE:
        return slip.patient_name is None and slip.admission_date is None
    if kind is SlipKind.OTHER_NAME:
        return slip.patient_name == OTHER_PATIENT_NAME and slip.admission_date == first
    if kind is SlipKind.LATE_ADMISSION:
        return slip.patient_name == owner and slip.admission_date == first + timedelta(days=1)
    return slip.patient_name == owner and slip.admission_date == first


def _clean_short(world: World, plans: tuple[PersonalClaimPlan, ...], rules: PolicyRules) -> PersonalClaimPlan:
    return next(
        p
        for p in plans
        if len(p.silent_dates) <= rules.personal.max_auto_days
        and p.slip.patient_name == world.city.merchant(p.merchant_id).owner_name
        and p.slip.admission_date == p.silent_dates[0]
    )


def _decide(world: World, plan: PersonalClaimPlan, ledger: Ledger, rules: PolicyRules) -> DecisionOutcome:
    covers = season_covers(world, TEST_SEASON, rules.cover.waiting_period_days, TEST_CONFIG.history_end)
    outcome = decide_personal(plan, world=world, covers=covers, ledger=ledger, rules=rules, ids=IdFactory())
    assert outcome.kind is ClaimKind.PERSONAL and outcome.event_date == plan.silent_dates[-1]
    return outcome.outcome


def test_decisions_follow_the_policy_engine(
    world: World, plans: tuple[PersonalClaimPlan, ...], rules: PolicyRules
) -> None:
    short = _clean_short(world, plans, rules)
    long = next(p for p in plans if len(p.silent_dates) > rules.personal.max_auto_days)
    ledger = Ledger()
    assert _decide(world, short, ledger, rules) is DecisionOutcome.APPROVED
    (payment,) = ledger.payments
    assert payment.kind is ClaimKind.PERSONAL and payment.event_dates == short.silent_dates
    assert _decide(world, long, ledger, rules) is DecisionOutcome.REFERRED  # WITHIN_AUTO_LIMIT
    assert _decide(world, short, ledger, rules) is DecisionOutcome.DECLINED  # NOT_ALREADY_PAID
    blurry = PersonalClaimPlan(
        short.merchant_id,
        short.zone_id,
        short.silent_dates,
        short.claim_at,
        short.expected_day_published,
        SlipExtraction(confidence=0.22, source="simulated", raw={}),
        doubtful_slip=True,
    )
    assert _decide(world, blurry, Ledger(), rules) is DecisionOutcome.REFERRED


def test_outcomes_flag_doubtful_claims(
    world: World, plans: tuple[PersonalClaimPlan, ...], rules: PolicyRules
) -> None:
    covers = season_covers(world, TEST_SEASON, rules.cover.waiting_period_days, TEST_CONFIG.history_end)
    for plan in plans:
        outcome = decide_personal(
            plan, world=world, covers=covers, ledger=Ledger(), rules=rules, ids=IdFactory()
        )
        too_long = len(plan.silent_dates) > rules.personal.max_auto_days
        assert outcome.doubtful is (plan.doubtful_slip or too_long)
        if outcome.doubtful:
            assert outcome.outcome is DecisionOutcome.REFERRED  # deck slide 11: every doubtful claim


def test_annual_limit_declines(
    world: World, plans: tuple[PersonalClaimPlan, ...], rules: PolicyRules
) -> None:
    plan = _clean_short(world, plans, rules)
    ledger = Ledger()
    ledger.record(
        Payment(
            plan.merchant_id,
            plan.zone_id,
            ClaimKind.AREA,
            (TEST_SEASON.start,),
            TEST_SEASON.start,
            rules.annual_limit_paise,
        )
    )
    assert _decide(world, plan, ledger, rules) is DecisionOutcome.DECLINED
    after_event = Ledger()
    after_event.record(
        Payment(
            plan.merchant_id,
            plan.zone_id,
            ClaimKind.AREA,
            (plan.claim_at.date(),),
            plan.claim_at.date(),
            rules.annual_limit_paise,
        )
    )
    # SPEC §9.1: the rolling 365 days end on the event date (the last silent day), not the claim day.
    assert _decide(world, plan, after_event, rules) is DecisionOutcome.APPROVED


def test_the_backtest_decides_without_the_doctor_confirmation() -> None:
    """Two historical monsoons have no hospital register to ask, so the backtest turns the rule off.

    This is what keeps the committed report reproducible: with the rule on, every claim here would
    refer for want of a hospital, a doctor and an answer, and the published auto-paid split would
    silently mean nothing. Every other rule is left exactly as shipped.
    """
    shipped = default_rules()
    assert shipped.personal.require_doctor_confirmation is True

    measured = without_doctor_check(shipped)
    assert measured.personal.require_doctor_confirmation is False
    assert measured.version == shipped.version
    assert measured.model_dump(exclude={"personal"}) == shipped.model_dump(exclude={"personal"})
    assert measured.personal.model_dump(exclude={"require_doctor_confirmation"}) == (
        shipped.personal.model_dump(exclude={"require_doctor_confirmation"})
    )
