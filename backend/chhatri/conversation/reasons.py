"""Which catalogue text explains a decision to the merchant (SPEC §9.2–§9.4, §13.5).

- A REFERRED personal claim gets the ``SLIP_TO_HUMAN`` variant of its SOFT issue (FAIL or UNSURE).
  When several SOFT checks are unsure the most basic one wins: an unreadable slip explains a missing
  name and dates, a wrong name comes before wrong dates, and only a clean slip that covers too many
  days is "longer than we pay automatically" (§9.4 "anything above the cap goes to a human").
- A DECLINED decision is explained by its first failing HARD check (every HARD check has a
  ``REASON_<code>`` entry); an officer's decline without a HARD failure by the case kind.
- A closed dispute is explained by what was disputed: an area payout by the area's numbers, a
  personal payout by the policy's daily cap (§4.3), a DECLINED decision by the reason it was declined (K5).
- The claim tracker (`replay.view_claims`) says why a claim is with a person with the TRACK_REFERRED line of the
  same SOFT issue that picks the SLIP_TO_HUMAN variant.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from chhatri.conversation.messages import CATALOGUE
from chhatri.domain.enums import CaseKind, CheckCode, CheckStatus, DecisionOutcome, Severity
from chhatri.domain.models import Decision

SOFT_ISSUES: Final = frozenset({CheckStatus.FAIL, CheckStatus.UNSURE})
SLIP_TO_HUMAN_BY_CHECK: Final[Mapping[CheckCode, str]] = MappingProxyType(
    {
        CheckCode.SLIP_READABLE: "SLIP_TO_HUMAN_UNREADABLE",
        CheckCode.NAME_MATCHES_KYC: "SLIP_TO_HUMAN",
        CheckCode.DATES_MATCH: "SLIP_TO_HUMAN_DATES",
        CheckCode.WITHIN_AUTO_LIMIT: "SLIP_TO_HUMAN_DAYS",
    }
)
OFFICER_REASON_BY_CASE: Final[Mapping[CaseKind, str]] = MappingProxyType(
    {
        CaseKind.PERSONAL_CLAIM_REVIEW: "REASON_OFFICER_PERSONAL",
        CaseKind.DISPUTE: "REASON_OFFICER_DISPUTE",
        CaseKind.AREA_REVIEW: "REASON_OFFICER_DISPUTE",
    }
)
TRACK_REFERRED_BY_SLIP_KEY: Final[Mapping[str, str]] = MappingProxyType(
    {
        "SLIP_TO_HUMAN_UNREADABLE": "TRACK_REFERRED_UNREADABLE",
        "SLIP_TO_HUMAN": "TRACK_REFERRED_NAME",
        "SLIP_TO_HUMAN_DATES": "TRACK_REFERRED_DATES",
        "SLIP_TO_HUMAN_DAYS": "TRACK_REFERRED_DAYS",
    }
)
REASON_PREFIX: Final = "REASON_"
DISPUTE_REASON_AREA: Final = "REASON_OFFICER_DISPUTE"
DISPUTE_REASON_PERSONAL: Final = "REASON_OFFICER_DISPUTE_PERSONAL"


def slip_to_human_key(decision: Decision) -> str:
    """The SLIP_TO_HUMAN catalogue key for a REFERRED personal decision."""
    issues = {c.code for c in decision.checks if c.severity is Severity.SOFT and c.status in SOFT_ISSUES}
    for code, key in SLIP_TO_HUMAN_BY_CHECK.items():
        if code in issues:
            return key
    raise ValueError(f"decision {decision.id} has no SOFT issue that explains a referral")


def hard_fail_reason_key(decision: Decision) -> str | None:
    """``REASON_<code>`` of the first failing HARD check, or None when no HARD check failed."""
    failed = next(
        (c for c in decision.checks if c.severity is Severity.HARD and c.status is CheckStatus.FAIL), None
    )
    if failed is None:
        return None
    key = f"{REASON_PREFIX}{failed.code.value}"
    if key not in CATALOGUE:
        raise KeyError(f"no merchant reason text for HARD check {failed.code.value}")
    return key


def declined_reason_key(decision: Decision) -> str:
    """Reason key for an automatic (policy-engine) DECLINED decision."""
    key = hard_fail_reason_key(decision)
    if key is None:
        raise ValueError(f"declined decision {decision.id} has no failing HARD check")
    return key


def officer_reason_key(decision: Decision, case_kind: CaseKind) -> str:
    """Reason key for an officer's DECLINED decision (HARD failure first, else by case kind)."""
    return hard_fail_reason_key(decision) or OFFICER_REASON_BY_CASE[case_kind]


def referred_track_key(decision: Decision) -> str:
    """The TRACK_REFERRED line (claim tracker) for the SOFT issue that sent a personal claim to a person."""
    return TRACK_REFERRED_BY_SLIP_KEY[slip_to_human_key(decision)]


def dispute_reason_key(disputed: Decision) -> str:
    """Reason key for a closed dispute about ``disputed``.

    A DECLINED decision reuses the REASON_<CHECK> text of its failing HARD check, or the officer's reason when a
    person declined it; a payout is explained by the area's numbers or the personal daily cap.
    """
    if disputed.outcome is DecisionOutcome.DECLINED:
        return hard_fail_reason_key(disputed) or OFFICER_REASON_BY_CASE[CaseKind.PERSONAL_CLAIM_REVIEW]
    explanation = disputed.explanation
    if explanation is None:
        raise ValueError(f"disputed decision {disputed.id} has no explanation to point to")
    return DISPUTE_REASON_AREA if explanation.drop_pct is not None else DISPUTE_REASON_PERSONAL
