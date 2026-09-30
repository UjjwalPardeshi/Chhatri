"""Area claims and decisions for fired triggers, straight from the policy engine (SPEC §4.3, §9).

For every trigger, each covered merchant of the zone gets an AREA claim for the scenario day whose
``expected_day_paise`` is the published model expectation (`publish_expected_day` of the P50 day
sum, SPEC §4.3) and whose ``drop_pct`` is the trigger's; the facts carry the merchant's cover, the
trigger's alert and a fresh ledger (nothing paid in the last 365 days, the demo world has no
earlier payouts), and `evaluate_area_claim` decides. Uncovered merchants (Ramesh, SPEC §5.4) are
never in a zone index and get no area claim. Ids come from a fresh `IdFactory` in trigger and
merchant order, as on a scenario load (SPEC §3).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from chhatri.domain.enums import ClaimKind
from chhatri.domain.models import Alert, AreaTrigger, Claim, Decision, Merchant
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.ids import IdFactory
from chhatri.pipeline.scenario_eval import DayFrame, expected_days
from chhatri.policy.engine import AreaClaimFacts, evaluate_area_claim, publish_expected_day
from chhatri.policy.rules import PolicyRules

__all__ = ["AreaDecision", "area_decisions", "area_facts"]


@dataclass(frozen=True, slots=True)
class AreaDecision:
    """One merchant's area decision with the trigger it answers."""

    trigger: AreaTrigger
    decision: Decision


def area_facts(
    frame: DayFrame,
    merchant: Merchant,
    trigger: AreaTrigger,
    alert: Alert | None,
    *,
    expected_published: int,
    claim_id: str,
) -> AreaClaimFacts:
    """Facts for one merchant's area claim on the frame's day (SPEC §9.2 area checks)."""
    claim = Claim(
        id=claim_id,
        kind=ClaimKind.AREA,
        merchant_id=merchant.id,
        created_at=trigger.fired_at,
        event_date=frame.day,
        trigger_id=trigger.id,
        expected_day_paise=expected_published,
        drop_pct=trigger.drop_pct,
    )
    return AreaClaimFacts(
        claim=claim,
        merchant=merchant,
        cover=frame.world.city.covers.get(merchant.id),
        trigger=trigger,
        alert=alert,
        paid_last_365_days_paise=0,
        already_paid=False,
        weekday=frame.day.weekday(),
    )


def _covered_merchants(frame: DayFrame, zone_id: str) -> tuple[Merchant, ...]:
    city = frame.world.city
    return tuple(m for m in city.merchants_in_zone(zone_id) if m.id in city.covers)


def area_decisions(
    frame: DayFrame, model: ExpectedSalesModel, rules: PolicyRules, triggers: Sequence[AreaTrigger]
) -> tuple[AreaDecision, ...]:
    """Decide every covered merchant of every triggered zone (SPEC §9.3), in trigger then id order."""
    alerts: Mapping[str, Alert] = MappingProxyType({a.id: a for a in frame.alerts()})
    ids = IdFactory()
    out: list[AreaDecision] = []
    for trigger in triggers:
        merchants = _covered_merchants(frame, trigger.zone_id)
        expected = expected_days(frame, model, [m.id for m in merchants])
        for merchant in merchants:
            facts = area_facts(
                frame,
                merchant,
                trigger,
                alerts.get(trigger.alert_id),
                expected_published=publish_expected_day(expected[merchant.id]),
                claim_id=ids.next("claim"),
            )
            decision = evaluate_area_claim(
                facts, rules, decision_id=ids.next("decision"), now=trigger.fired_at
            )
            out.append(AreaDecision(trigger=trigger, decision=decision))
    return tuple(out)
