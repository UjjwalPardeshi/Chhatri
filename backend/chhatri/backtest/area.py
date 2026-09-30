"""Area payouts of both triggers (SPEC §4.3, §9.2, §9.3, §18).

Chhatri: every trigger raises one area claim per covered merchant of its zone, decided by the real
`policy.engine.evaluate_area_claim` at the trigger time with the merchant's published expected day
(the model's P50 day sum rounded to ₹10) and the trigger's drop. Approved claims are paid on the
decision day and credited `payout_rail_delay_minutes` later (SPEC §10).

Weather-only (SPEC §18): on a trigger day every covered shop of the zone is owed
`share × expected_day × 50 %` — `policy.amounts.area_amount` with a fixed 50 % drop, so the same
published expected day, rupee rounding and daily cap apply. The daily rain total is only known once
the day is over, so the decision is taken at the next midnight. The same rolling annual limit as
Chhatri applies (SPEC §9.1); nothing else can fail since every pilot shop holds a backtest cover.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Final

from chhatri.backtest.config import WEATHER_ONLY_DROP_PCT
from chhatri.backtest.ledger import ClaimOutcome, Ledger, Payment
from chhatri.clock import at
from chhatri.domain.enums import ClaimKind, DecisionOutcome
from chhatri.domain.models import Alert, AreaTrigger, Claim, Cover
from chhatri.ids import IdFactory
from chhatri.policy.engine import area_amount, evaluate_area_claim, publish_expected_day
from chhatri.policy.facts import AreaClaimFacts
from chhatri.policy.rules import PolicyRules
from chhatri.sim.types import City

HOUR: Final = timedelta(hours=1)


def _credit(decided_at: datetime, outcome: DecisionOutcome, rules: PolicyRules) -> datetime | None:
    if outcome is not DecisionOutcome.APPROVED:
        return None
    return decided_at + timedelta(minutes=rules.payout_rail_delay_minutes)


def _area_claim(
    ids: IdFactory, merchant_id: str, trigger: AreaTrigger, event_date: date, expected_published: int
) -> Claim:
    return Claim(
        id=ids.next("claim"),
        kind=ClaimKind.AREA,
        merchant_id=merchant_id,
        created_at=trigger.fired_at,
        event_date=event_date,
        trigger_id=trigger.id,
        expected_day_paise=expected_published,
        drop_pct=trigger.drop_pct,
    )


def decide_trigger(
    trigger: AreaTrigger,
    alert: Alert,
    *,
    city: City,
    covers: Mapping[str, Cover],
    expected_day: Mapping[str, int],
    ledger: Ledger,
    rules: PolicyRules,
    ids: IdFactory,
) -> tuple[ClaimOutcome, ...]:
    """Decide the area claims of every covered merchant in the trigger's zone, in id order."""
    if alert.id != trigger.alert_id:
        raise ValueError(f"trigger {trigger.id} names alert {trigger.alert_id}, got {alert.id}")
    event_date = (trigger.window_end - HOUR).date()
    outcomes = []
    for merchant_id in sorted(expected_day):
        merchant = city.merchant(merchant_id)
        claim = _area_claim(
            ids, merchant_id, trigger, event_date, publish_expected_day(expected_day[merchant_id])
        )
        facts = AreaClaimFacts(
            claim=claim,
            merchant=merchant,
            cover=covers.get(merchant_id),
            trigger=trigger,
            alert=alert,
            paid_last_365_days_paise=ledger.paid_last_365_days(merchant_id, event_date),
            already_paid=ledger.area_paid(merchant_id, event_date),
            weekday=event_date.weekday(),
        )
        decision = evaluate_area_claim(facts, rules, decision_id=ids.next("decision"), now=trigger.fired_at)
        outcomes.append(
            _record(ledger, decision.outcome, decision.amount_paise, claim, merchant.zone_id, rules)
        )
    return tuple(outcomes)


def _record(
    ledger: Ledger, outcome: DecisionOutcome, amount: int, claim: Claim, zone_id: str, rules: PolicyRules
) -> ClaimOutcome:
    paid = outcome is DecisionOutcome.APPROVED and amount > 0
    if paid:
        ledger.record(
            Payment(
                merchant_id=claim.merchant_id,
                zone_id=zone_id,
                kind=ClaimKind.AREA,
                event_dates=(claim.event_date,),
                paid_on=claim.created_at.date(),
                amount_paise=amount,
            )
        )
    return ClaimOutcome(
        kind=ClaimKind.AREA,
        merchant_id=claim.merchant_id,
        zone_id=zone_id,
        event_date=claim.event_date,
        decided_at=claim.created_at,
        credited_at=_credit(claim.created_at, outcome, rules),
        outcome=outcome,
        amount_paise=amount if paid else 0,
    )


def decide_weather_day(
    zone_id: str,
    day: date,
    *,
    expected_day: Mapping[str, int],
    ledger: Ledger,
    rules: PolicyRules,
) -> tuple[ClaimOutcome, ...]:
    """Weather-only payouts of one zone-day (module docstring), in merchant id order."""
    decided_at = at(day + timedelta(days=1), 0)
    outcomes = []
    for merchant_id in sorted(expected_day):
        amount, _capped = area_amount(
            publish_expected_day(expected_day[merchant_id]), WEATHER_ONLY_DROP_PCT, rules
        )
        within = (
            ledger.paid_last_365_days(merchant_id, decided_at.date()) + amount <= rules.annual_limit_paise
        )
        outcome = DecisionOutcome.APPROVED if within else DecisionOutcome.DECLINED
        if within and amount > 0:
            ledger.record(Payment(merchant_id, zone_id, ClaimKind.AREA, (day,), decided_at.date(), amount))
        outcomes.append(
            ClaimOutcome(
                kind=ClaimKind.AREA,
                merchant_id=merchant_id,
                zone_id=zone_id,
                event_date=day,
                decided_at=decided_at,
                credited_at=_credit(decided_at, outcome, rules),
                outcome=outcome,
                amount_paise=amount if within else 0,
            )
        )
    return tuple(outcomes)


def alerts_by_id(alerts: Sequence[Alert]) -> Mapping[str, Alert]:
    """Alert lookup for the triggers (ids are unique in the feed)."""
    table = {a.id: a for a in alerts}
    if len(table) != len(alerts):
        raise ValueError("alert ids must be unique")
    return table
