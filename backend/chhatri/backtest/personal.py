"""Personal claims from silent-shop detection over a season (SPEC §8.3, §9.2, §13.5).

1. Silent days: for every season day, `detect.silent.find_silent` over the covered merchants with
   their model day range, excluding zones in a Chhatri area event that day. Only merchants with zero
   business-hour transactions on a working day are passed in (vectorised pre-filter); find_silent
   requires exactly that, so the result is unchanged (checked by a test).
2. Episodes: a merchant's silent days group into one episode while the days between them are all
   non-claimable for that merchant (its weekly off or an area-event day of its zone), which is
   SPEC §8.3's "every completed day from the first silent day up to yesterday".
3. Outreach (SPEC §8.3): the next working morning after the first silent day, only if the shop still
   has no transaction by 11:00 (`silent_this_morning`); a shop that reopened is never contacted.
4. Claim: the merchant answers with a slip when the episode is over (the day after its last silent
   day) and claims all of its silent days — so closures longer than `max_auto_days` reach a human
   (SPEC §9.4). The expected day is the P50 day sum of the first silent day, published to ₹10.
Decisions come from `policy.engine.evaluate_personal_claim` at `CLAIM_HOUR` of the claim day.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Final

import numpy as np

from chhatri.backtest.config import Season
from chhatri.backtest.ledger import ClaimOutcome, Ledger, Payment
from chhatri.backtest.slips import SlipKind, read_slips, render_claim_slips, slip_kind
from chhatri.backtest.world import World
from chhatri.clock import at
from chhatri.detect.city_arrays import arrays_for
from chhatri.detect.silent import find_silent, silent_this_morning
from chhatri.detect.types import SilentFinding
from chhatri.domain.enums import ClaimKind, DecisionOutcome
from chhatri.domain.models import Claim, Cover, Decision, SlipExtraction
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.ids import IdFactory
from chhatri.policy.engine import evaluate_personal_claim, publish_expected_day
from chhatri.policy.facts import PersonalClaimFacts
from chhatri.policy.rules import PolicyRules

logger = logging.getLogger(__name__)

HOURS_PER_DAY: Final = 24
CLAIM_HOUR: Final = 12  # the merchant's slip arrives around midday of the claim day
OUTREACH_UNTIL_HOUR: Final = 11  # SPEC §8.3: zero transactions by 11:00


@dataclass(frozen=True, slots=True)
class PersonalClaimPlan:
    """A claim ready for the policy engine: silent days, time, published expected day and slip."""

    merchant_id: str
    zone_id: str
    silent_dates: tuple[date, ...]
    claim_at: datetime
    expected_day_published: int
    slip: SlipExtraction
    doubtful_slip: bool  # the slip was modelled as doubtful (`slips.SlipKind`), not read as such


def zero_trade_mask(world: World, days: Sequence[date]) -> np.ndarray:
    """(M, D) bool: covered, working day and zero transactions in business hours."""
    arrays = arrays_for(world.city)
    first = world.history.hour_index(at(days[0], 0))
    txns = world.history.txns[:, first : first + HOURS_PER_DAY * len(days)]
    per_hour = txns.reshape(txns.shape[0], len(days), HOURS_PER_DAY)
    zero = np.where(arrays.business[:, None, :], per_hour, 0).sum(axis=2) == 0
    weekdays = np.array([d.weekday() for d in days], dtype=np.int64)
    working = arrays.weekly_off[:, None] != weekdays[None, :]
    return zero & working & arrays.covered[:, None]


def silent_findings(
    world: World, model: ExpectedSalesModel, season: Season, area_zones: Mapping[date, frozenset[str]]
) -> tuple[SilentFinding, ...]:
    """Every SPEC §8.3 silent merchant-day of the season among covered merchants."""
    days = season.days
    mask = zero_trade_mask(world, days)
    findings: list[SilentFinding] = []
    for index, day in enumerate(days):
        rows = np.flatnonzero(mask[:, index])
        if rows.size == 0:
            continue
        ids = [world.city.merchants[int(r)].id for r in rows]
        ranges = model.day_ranges_paise(world.city, world.history, day, ids)
        findings.extend(find_silent(day, world.city, world.history, ranges, area_zones.get(day, frozenset())))
    return tuple(findings)


def _gap_is_unclaimable(
    world: World, merchant_id: str, after: date, before: date, area_zones: Mapping[date, frozenset[str]]
) -> bool:
    merchant = world.city.merchant(merchant_id)
    day = after + timedelta(days=1)
    while day < before:
        if day.weekday() != merchant.weekly_off and merchant.zone_id not in area_zones.get(day, frozenset()):
            return False
        day += timedelta(days=1)
    return True


def episodes(
    world: World, findings: Sequence[SilentFinding], area_zones: Mapping[date, frozenset[str]]
) -> tuple[tuple[SilentFinding, ...], ...]:
    """Group each merchant's silent days into episodes (module docstring, step 2), merchant order."""
    by_merchant: dict[str, list[SilentFinding]] = {}
    for finding in sorted(findings, key=lambda f: (f.merchant_id, f.day)):
        by_merchant.setdefault(finding.merchant_id, []).append(finding)
    grouped: list[tuple[SilentFinding, ...]] = []
    for merchant_id, items in by_merchant.items():
        current = [items[0]]
        for finding in items[1:]:
            if _gap_is_unclaimable(world, merchant_id, current[-1].day, finding.day, area_zones):
                current.append(finding)
            else:
                grouped.append(tuple(current))
                current = [finding]
        grouped.append(tuple(current))
    return tuple(grouped)


def outreach_day(world: World, merchant_id: str, first_silent: date) -> date:
    """The next day after the first silent day that is not the merchant's weekly off."""
    weekly_off = world.city.merchant(merchant_id).weekly_off
    day = first_silent + timedelta(days=1)
    while day.weekday() == weekly_off:
        day += timedelta(days=1)
    return day


def plan_claims(
    world: World,
    model: ExpectedSalesModel,
    season: Season,
    area_zones: Mapping[date, frozenset[str]],
    seed: int,
    *,
    workers: int,
) -> tuple[PersonalClaimPlan, ...]:
    """Personal claims of the season in claim-time order (module docstring, steps 1–4)."""
    findings = silent_findings(world, model, season, area_zones)
    contacted = [
        ep
        for ep in episodes(world, findings, area_zones)
        if silent_this_morning(
            ep[0].merchant_id,
            outreach_day(world, ep[0].merchant_id, ep[0].day),
            world.city,
            world.history,
            OUTREACH_UNTIL_HOUR,
        )
    ]
    firsts = [(world.city.merchant(ep[0].merchant_id), ep[0].day) for ep in contacted]
    slips = read_slips(render_claim_slips(seed, firsts, workers=workers))
    doubtful = [slip_kind(seed, merchant, day) is not SlipKind.CLEAN for merchant, day in firsts]
    plans = [
        PersonalClaimPlan(
            merchant_id=ep[0].merchant_id,
            zone_id=world.city.merchant(ep[0].merchant_id).zone_id,
            silent_dates=tuple(f.day for f in ep),
            claim_at=at(ep[-1].day + timedelta(days=1), CLAIM_HOUR),
            expected_day_published=publish_expected_day(ep[0].expected_day_paise),
            slip=slip,
            doubtful_slip=bad,
        )
        for ep, slip, bad in zip(contacted, slips, doubtful, strict=True)
    ]
    logger.info("%s: %d silent merchant-days, %d episodes contacted", season.label, len(findings), len(plans))
    return tuple(sorted(plans, key=lambda p: (p.claim_at, p.merchant_id)))


def _personal_claim(plan: PersonalClaimPlan, ids: IdFactory) -> Claim:
    """The SPEC §3 Claim for a plan: event date = last silent day, published expected day."""
    return Claim(
        id=ids.next("claim"),
        kind=ClaimKind.PERSONAL,
        merchant_id=plan.merchant_id,
        created_at=plan.claim_at,
        event_date=plan.silent_dates[-1],
        silent_dates=plan.silent_dates,
        slip=plan.slip,
        expected_day_paise=plan.expected_day_published,
    )


def _record_personal(
    plan: PersonalClaimPlan, decision: Decision, ledger: Ledger, rules: PolicyRules
) -> ClaimOutcome:
    """Append an approved payment to the ledger and summarise the decision."""
    paid = decision.outcome is DecisionOutcome.APPROVED
    if paid:
        ledger.record(
            Payment(
                merchant_id=plan.merchant_id,
                zone_id=plan.zone_id,
                kind=ClaimKind.PERSONAL,
                event_dates=plan.silent_dates,
                paid_on=plan.claim_at.date(),
                amount_paise=decision.amount_paise,
            )
        )
    return ClaimOutcome(
        kind=ClaimKind.PERSONAL,
        merchant_id=plan.merchant_id,
        zone_id=plan.zone_id,
        event_date=plan.silent_dates[-1],
        decided_at=plan.claim_at,
        credited_at=plan.claim_at + timedelta(minutes=rules.payout_rail_delay_minutes) if paid else None,
        outcome=decision.outcome,
        amount_paise=decision.amount_paise if paid else 0,
        doubtful=plan.doubtful_slip or len(plan.silent_dates) > rules.personal.max_auto_days,
    )


def decide_personal(
    plan: PersonalClaimPlan,
    *,
    world: World,
    covers: Mapping[str, Cover],
    ledger: Ledger,
    rules: PolicyRules,
    ids: IdFactory,
) -> ClaimOutcome:
    """Decide one personal claim with the policy engine and record an approved payment.

    The silent dates were verified by `find_silent` (SPEC §8.3), so they are the verified dates;
    the weekday is the first silent day's, whose expected day the claim publishes (SPEC §9.6); the
    rolling annual limit ends on the event date, the last silent day (SPEC §9.1), as in the replay.
    """
    merchant = world.city.merchant(plan.merchant_id)
    facts = PersonalClaimFacts(
        claim=_personal_claim(plan, ids),
        merchant=merchant,
        cover=covers.get(plan.merchant_id),
        verified_silent_dates=plan.silent_dates,
        kyc_name=merchant.kyc_name,
        paid_last_365_days_paise=ledger.paid_last_365_days(plan.merchant_id, plan.silent_dates[-1]),
        already_paid_dates=ledger.personal_dates(plan.merchant_id),
        weekday=plan.silent_dates[0].weekday(),
    )
    decision = evaluate_personal_claim(facts, rules, decision_id=ids.next("decision"), now=plan.claim_at)
    return _record_personal(plan, decision, ledger, rules)
