"""Policy engine — the only layer that can approve money (SPEC §0.2, §9, §24.3). Pure: no I/O.

Outcome (SPEC §9.3): any HARD fail ⇒ DECLINED (amount 0, reason = first failing check); else any
SOFT FAIL/UNSURE ⇒ REFERRED (amount = the computed amount, not paid; a Case is opened by the
caller); else APPROVED. APPROVED and REFERRED decisions carry their §9.6 Explanation; a DECLINED
decision pays nothing and carries none. `decided_by` is "policy-engine".

Officer decisions (SPEC §9.4): only a REFERRED decision can be resolved. Every check is re-run from
fresh facts; any HARD fail ⇒ DECLINED even when the officer approves (no paying an uncovered or
unpaid-premium merchant, no paying twice). Approval records every SOFT check as WAIVED_BY_OFFICER.

Inputs are validated (fail fast, ValueError): claim kind, merchant/claim/trigger consistency and a
published (₹10-rounded) expected day. Public names of the former single-module engine are
re-exported here (`publish_expected_day`, `area_amount`, `personal_amount`, `name_match_score`,
`evaluate_cover_purchase`, `AreaClaimFacts`, `PersonalClaimFacts`).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from chhatri.clock import require_aware
from chhatri.domain.enums import CheckStatus, ClaimKind, DecisionOutcome, Severity
from chhatri.domain.models import CheckResult, Cover, Decision, Explanation
from chhatri.policy import checks as ck
from chhatri.policy.amounts import (
    area_amount,
    area_breakdown,
    personal_amount,
    personal_breakdown,
    publish_expected_day,
)
from chhatri.policy.cover import evaluate_cover_purchase
from chhatri.policy.explain import explain_area, explain_personal
from chhatri.policy.facts import AreaClaimFacts, PersonalClaimFacts
from chhatri.policy.names import name_match_score
from chhatri.policy.rules import PolicyRules

__all__ = [
    "AreaClaimFacts",
    "PersonalClaimFacts",
    "apply_officer_decision",
    "area_amount",
    "evaluate_area_claim",
    "evaluate_cover_purchase",
    "evaluate_personal_claim",
    "name_match_score",
    "personal_amount",
    "publish_expected_day",
]

POLICY_ENGINE_ACTOR: Final = "policy-engine"
OFFICER_ACTOR_PREFIX: Final = "officer:"
OFFICER_ID_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,63}$")
OFFICER_DECLINE_DEFAULT: Final = "Declined by a claims officer."
MAX_PCT: Final = 100
SOFT_ISSUES: Final = frozenset({CheckStatus.FAIL, CheckStatus.UNSURE})


@dataclass(frozen=True, slots=True)
class Evaluation:
    """Checks, the computed amount and its explanation for one claim (internal)."""

    checks: tuple[CheckResult, ...]
    amount_paise: int
    explanation: Explanation


def _validate_area(facts: AreaClaimFacts) -> None:
    claim, trigger = facts.claim, facts.trigger
    if claim.kind is not ClaimKind.AREA:
        raise ValueError(f"claim {claim.id} is {claim.kind}, not AREA")
    if claim.merchant_id != facts.merchant.id or facts.merchant.zone_id != trigger.zone_id:
        raise ValueError(f"claim {claim.id} merchant/zone does not match trigger {trigger.id}")
    if claim.trigger_id != trigger.id:
        raise ValueError(f"claim {claim.id} names trigger {claim.trigger_id}, facts carry {trigger.id}")
    if trigger.drop_pct != MAX_PCT - trigger.index_pct:
        raise ValueError(f"trigger {trigger.id}: drop_pct must be 100 − index_pct (SPEC §4.3)")
    if claim.drop_pct is not None and claim.drop_pct != trigger.drop_pct:
        raise ValueError(f"claim {claim.id} drop_pct {claim.drop_pct} ≠ trigger {trigger.drop_pct}")
    _validate_common(facts.cover, facts.merchant.id, facts.paid_last_365_days_paise)


def _validate_personal(facts: PersonalClaimFacts) -> None:
    claim = facts.claim
    if claim.kind is not ClaimKind.PERSONAL:
        raise ValueError(f"claim {claim.id} is {claim.kind}, not PERSONAL")
    if claim.merchant_id != facts.merchant.id:
        raise ValueError(f"claim {claim.id} belongs to {claim.merchant_id}, not {facts.merchant.id}")
    if len(set(claim.silent_dates)) != len(claim.silent_dates):
        raise ValueError(f"claim {claim.id} lists a silent day twice")
    _validate_common(facts.cover, facts.merchant.id, facts.paid_last_365_days_paise)


def _validate_common(cover: Cover | None, merchant_id: str, paid_365: int) -> None:
    if cover is not None and cover.merchant_id != merchant_id:
        raise ValueError(f"cover {cover.id} belongs to {cover.merchant_id}, not {merchant_id}")
    if paid_365 < 0:
        raise ValueError("paid_last_365_days_paise must be non-negative")


def _evaluate_area(facts: AreaClaimFacts, rules: PolicyRules) -> Evaluation:
    _validate_area(facts)
    claim, trigger, event_date = facts.claim, facts.trigger, facts.claim.event_date
    breakdown = area_breakdown(claim.expected_day_paise, trigger.drop_pct, rules)
    checks = (
        ck.cover_in_force(facts.cover, event_date),
        ck.premium_prepaid(facts.cover, event_date),
        ck.cover_before_alert(facts.cover, facts.alert),
        ck.alert_active(facts.alert, trigger),
        ck.index_quorum(trigger, rules),
        ck.below_floor(trigger, rules),
        ck.below_model_range(trigger),
        ck.not_already_paid_area(facts.already_paid, event_date),
        ck.within_annual_limit(facts.paid_last_365_days_paise, breakdown.amount_paise, rules),
    )
    return Evaluation(checks, breakdown.amount_paise, explain_area(breakdown, facts.weekday, rules))


def _evaluate_personal(facts: PersonalClaimFacts, rules: PolicyRules) -> Evaluation:
    _validate_personal(facts)
    claimed, slip = facts.claim.silent_dates, facts.claim.slip
    breakdown = personal_breakdown(facts.claim.expected_day_paise, len(claimed), rules)
    checks = (
        ck.cover_in_force(facts.cover, facts.claim.event_date),
        ck.premium_prepaid(facts.cover, facts.claim.event_date),
        ck.silence_verified(claimed, facts.verified_silent_dates),
        ck.slip_readable(slip, rules),
        ck.name_matches_kyc(slip, facts.kyc_name, rules),
        ck.dates_match(slip, claimed),
        ck.within_auto_limit(claimed, rules),
        ck.not_already_paid_personal(claimed, facts.already_paid_dates),
        ck.within_annual_limit(facts.paid_last_365_days_paise, breakdown.amount_paise, rules),
    )
    return Evaluation(checks, breakdown.amount_paise, explain_personal(breakdown, facts.weekday, rules))


def first_hard_fail(checks: Sequence[CheckResult]) -> CheckResult | None:
    """The first HARD check that failed, in check order (SPEC §9.3)."""
    return next((c for c in checks if c.severity is Severity.HARD and c.status is CheckStatus.FAIL), None)


def first_soft_issue(checks: Sequence[CheckResult]) -> CheckResult | None:
    """The first SOFT check that is FAIL or UNSURE, in check order (SPEC §9.3)."""
    return next((c for c in checks if c.severity is Severity.SOFT and c.status in SOFT_ISSUES), None)


def _decide(
    ev: Evaluation, *, claim_id: str, merchant_id: str, rules: PolicyRules, decision_id: str, now: datetime
) -> Decision:
    hard, soft = first_hard_fail(ev.checks), first_soft_issue(ev.checks)
    base = Decision(
        id=decision_id,
        claim_id=claim_id,
        merchant_id=merchant_id,
        outcome=DecisionOutcome.APPROVED,
        amount_paise=ev.amount_paise,
        checks=ev.checks,
        rules_version=rules.version,
        decided_at=require_aware(now),
        decided_by=POLICY_ENGINE_ACTOR,
        explanation=ev.explanation,
    )
    if hard is not None:
        return base.model_copy(
            update={
                "outcome": DecisionOutcome.DECLINED,
                "amount_paise": 0,
                "explanation": None,
                "referral_reason": hard.detail_en,
            }
        )
    if soft is not None:
        return base.model_copy(
            update={"outcome": DecisionOutcome.REFERRED, "referral_reason": soft.detail_en}
        )
    return base


def evaluate_area_claim(
    facts: AreaClaimFacts, rules: PolicyRules, *, decision_id: str, now: datetime
) -> Decision:
    """Decide an area claim from its facts (SPEC §9.2 area checks, §9.3 outcome, §9.6 explanation)."""
    ev = _evaluate_area(facts, rules)
    return _decide(
        ev,
        claim_id=facts.claim.id,
        merchant_id=facts.merchant.id,
        rules=rules,
        decision_id=decision_id,
        now=now,
    )


def evaluate_personal_claim(
    facts: PersonalClaimFacts, rules: PolicyRules, *, decision_id: str, now: datetime
) -> Decision:
    """Decide a personal claim from its facts (SPEC §9.2 personal checks, §9.3, §9.6)."""
    ev = _evaluate_personal(facts, rules)
    return _decide(
        ev,
        claim_id=facts.claim.id,
        merchant_id=facts.merchant.id,
        rules=rules,
        decision_id=decision_id,
        now=now,
    )


def _waive(check: CheckResult, officer_id: str) -> CheckResult:
    if check.severity is not Severity.SOFT:
        return check
    detail = f"Waived by officer {officer_id} (was {check.status.value}): {check.detail_en}"
    return check.model_copy(update={"status": CheckStatus.WAIVED_BY_OFFICER, "detail_en": detail})


def apply_officer_decision(
    referred: Decision,
    facts: PersonalClaimFacts | AreaClaimFacts,
    *,
    approve: bool,
    officer_id: str,
    note: str,
    rules: PolicyRules,
    decision_id: str,
    now: datetime,
) -> Decision:
    """Resolve a REFERRED decision as a claims officer (SPEC §9.4); returns a new superseding Decision."""
    if referred.outcome is not DecisionOutcome.REFERRED:
        raise ValueError(f"decision {referred.id} is {referred.outcome}; only REFERRED can be resolved")
    if facts.claim.id != referred.claim_id or facts.merchant.id != referred.merchant_id:
        raise ValueError(f"facts are for claim {facts.claim.id}, decision {referred.id} is not")
    if not OFFICER_ID_PATTERN.fullmatch(officer_id):
        raise ValueError("officer_id must be a short token of letters, digits, '.', '_', '@' or '-'")
    if isinstance(facts, AreaClaimFacts):
        ev = _evaluate_area(facts, rules)
    else:
        ev = _evaluate_personal(facts, rules)
    engine = _decide(
        ev,
        claim_id=referred.claim_id,
        merchant_id=referred.merchant_id,
        rules=rules,
        decision_id=decision_id,
        now=now,
    )
    officer = {"decided_by": f"{OFFICER_ACTOR_PREFIX}{officer_id}", "supersedes": referred.id}
    if engine.outcome is DecisionOutcome.DECLINED:
        return engine.model_copy(update=officer)
    if not approve:
        reason = note.strip() or OFFICER_DECLINE_DEFAULT
        declined = {"outcome": DecisionOutcome.DECLINED, "amount_paise": 0, "explanation": None}
        return engine.model_copy(update={**officer, **declined, "referral_reason": reason})
    waived = tuple(_waive(c, officer_id) for c in engine.checks)
    approved = {"outcome": DecisionOutcome.APPROVED, "checks": waived, "referral_reason": None}
    return engine.model_copy(update={**officer, **approved})
