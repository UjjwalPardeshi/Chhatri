"""Facts the orchestrator hands to the pure policy engine (SPEC §9, §24.3 `policy.facts`).

Documented choices:
- NOT_ALREADY_PAID uses `Store.paid_event_dates`: the event date for area claims, the silent dates
  for personal claims (SPEC §9.2 "no approved payout for (merchant, date, kind)").
- The rolling 365-day sum ends on the claim's event date (SPEC §9.1).
- ``weekday`` (for the explanation) is the weekday of the day whose expectation is paid: the event
  date for area claims, the first claimed silent day for personal claims (SPEC §4.3 "Your usual
  Tuesday"; §17.2 illness: Anil's usual Wednesday).
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from chhatri.domain.enums import ClaimKind
from chhatri.domain.models import Alert, AreaTrigger, Claim, Merchant
from chhatri.policy.facts import AreaClaimFacts, PersonalClaimFacts

if TYPE_CHECKING:
    from chhatri.replay.state import Runtime

__all__ = ["area_facts", "expected_day_of", "personal_facts"]


def expected_day_of(claim: Claim) -> date:
    """The day whose expected sales the claim pays (first silent day for personal claims)."""
    if claim.kind is ClaimKind.PERSONAL and claim.silent_dates:
        return claim.silent_dates[0]
    return claim.event_date


def area_facts(
    rt: Runtime, claim: Claim, merchant: Merchant, trigger: AreaTrigger, alert: Alert | None
) -> AreaClaimFacts:
    return AreaClaimFacts(
        claim=claim,
        merchant=merchant,
        cover=rt.store.cover(merchant.id),
        trigger=trigger,
        alert=alert,
        paid_last_365_days_paise=rt.store.paid_last_365_days_paise(merchant.id, claim.event_date),
        already_paid=claim.event_date in rt.store.paid_event_dates(merchant.id, ClaimKind.AREA),
        weekday=expected_day_of(claim).weekday(),
    )


def personal_facts(
    rt: Runtime, claim: Claim, merchant: Merchant, verified: tuple[date, ...]
) -> PersonalClaimFacts:
    return PersonalClaimFacts(
        claim=claim,
        merchant=merchant,
        cover=rt.store.cover(merchant.id),
        verified_silent_dates=verified,
        kyc_name=merchant.kyc_name,
        paid_last_365_days_paise=rt.store.paid_last_365_days_paise(merchant.id, claim.event_date),
        already_paid_dates=rt.store.paid_event_dates(merchant.id, ClaimKind.PERSONAL),
        weekday=expected_day_of(claim).weekday(),
    )
