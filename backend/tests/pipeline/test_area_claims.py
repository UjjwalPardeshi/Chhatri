"""Area claims for fired triggers, decided by the policy engine (SPEC §4.3, §9.2, §9.3)."""

from __future__ import annotations

from chhatri.domain.enums import CheckCode, CheckStatus, ClaimKind, DecisionOutcome
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.pipeline.area_claims import area_decisions, area_facts
from chhatri.pipeline.scenario_eval import DayFrame, evaluate_hours, expected_days
from chhatri.policy.engine import evaluate_area_claim, publish_expected_day
from chhatri.policy.rules import PolicyRules

RAMESH = "S-0907"


def _triggers(frame: DayFrame, model: ExpectedSalesModel, rules: PolicyRules):
    (result,) = evaluate_hours(frame, model, rules, [17])
    return result.triggers


def test_every_covered_shop_of_a_triggered_zone_is_decided(
    frame: DayFrame, model: ExpectedSalesModel, rules: PolicyRules
) -> None:
    triggers = _triggers(frame, model, rules)
    decisions = area_decisions(frame, model, rules, triggers)
    city = frame.world.city
    covered = [m.id for t in triggers for m in city.merchants_in_zone(t.zone_id) if m.id in city.covers]
    assert [d.decision.merchant_id for d in decisions] == covered
    assert RAMESH not in {d.decision.merchant_id for d in decisions}
    assert all(d.decision.outcome is DecisionOutcome.APPROVED for d in decisions)
    assert [d.decision.id for d in decisions[:2]] == ["D-000001", "D-000002"]
    assert [d.decision.claim_id for d in decisions[:2]] == ["CL-000001", "CL-000002"]
    assert all(d.decision.decided_at == d.trigger.fired_at for d in decisions)


def test_claims_use_the_published_expectation(
    frame: DayFrame, model: ExpectedSalesModel, rules: PolicyRules
) -> None:
    triggers = _triggers(frame, model, rules)
    z7 = next(t for t in triggers if t.zone_id == "Z7")
    decision = next(
        d.decision for d in area_decisions(frame, model, rules, [z7]) if d.decision.merchant_id == "S-0142"
    )
    raw = expected_days(frame, model, ["S-0142"])["S-0142"]
    assert decision.explanation is not None
    assert decision.explanation.expected_day_paise == publish_expected_day(raw)
    assert decision.explanation.drop_pct == z7.drop_pct


def test_facts_without_the_alert_decline(
    frame: DayFrame, model: ExpectedSalesModel, rules: PolicyRules
) -> None:
    trigger = _triggers(frame, model, rules)[0]
    merchant = frame.world.city.merchants_in_zone(trigger.zone_id)[0]
    facts = area_facts(frame, merchant, trigger, None, expected_published=400_000, claim_id="CL-9")
    assert facts.claim.kind is ClaimKind.AREA and facts.claim.event_date == frame.day
    assert facts.weekday == frame.day.weekday() and facts.paid_last_365_days_paise == 0
    decision = evaluate_area_claim(facts, rules, decision_id="D-9", now=trigger.fired_at)
    assert decision.outcome is DecisionOutcome.DECLINED
    alert_check = next(c for c in decision.checks if c.code is CheckCode.ALERT_ACTIVE)
    assert alert_check.status is CheckStatus.FAIL


def test_uncovered_merchant_facts_carry_no_cover(
    frame: DayFrame, model: ExpectedSalesModel, rules: PolicyRules
) -> None:
    trigger = next(t for t in _triggers(frame, model, rules) if t.zone_id == "Z3")
    ramesh = frame.world.city.merchant(RAMESH)
    alert = next(a for a in frame.alerts() if a.id == trigger.alert_id)
    facts = area_facts(frame, ramesh, trigger, alert, expected_published=500_000, claim_id="CL-1")
    assert facts.cover is None
    decision = evaluate_area_claim(facts, rules, decision_id="D-1", now=trigger.fired_at)
    assert decision.outcome is DecisionOutcome.DECLINED and decision.amount_paise == 0
