"""Cases for claims officers: personal-claim reviews and disputes (SPEC §12, §13.5, §13.6, §16).

- `open_review`: a REFERRED personal claim opens a PERSONAL_CLAIM_REVIEW case with the evidence
  bundle (expected vs actual on the first silent day, the slip, KYC name and score, silent days,
  precedents of past cases), then starts ``human-review`` and ``follow-up`` (B1).
- `open_dispute` (deck test EXPLAINED): a DISPUTE case about the merchant's latest settled decision, one that was
  paid (credited) or declined (expected vs actual on its event date, the merchant's words, precedents of past
  disputes); after a fresh load it is C-2291. The disputed decision and its checks are linked via ``decision_id``.
  With no settled decision there is nothing to dispute and no case is opened; a second dispute for a decision
  that has an open case gets that case back (K5).
Both publish a ``case`` event, add a feed item and write a memory fact (SPEC §16).
"""

from __future__ import annotations

import logging
from typing import Any, Final

from chhatri.conversation.ports import DisputeOutcome
from chhatri.domain.enums import CaseKind, CaseStatus, DecisionOutcome
from chhatri.domain.models import Case, Claim, Decision
from chhatri.money import format_inr
from chhatri.replay.evidence import hourly_evidence, iso_days, name_evidence, precedents, slip_evidence
from chhatri.replay.fmt import weekday_day_month
from chhatri.replay.memory_facts import dispute_fact
from chhatri.replay.publish import Publisher, RuntimeLink
from chhatri.replay.runs import start_case_workflows

__all__ = ["CaseFlow"]

logger = logging.getLogger(__name__)

REVIEW_PRECEDENTS: Final = "case"
DISPUTE_PRECEDENTS: Final = "dispute"


class CaseFlow:
    """Opens officer cases with their evidence."""

    def __init__(self, link: RuntimeLink, publisher: Publisher) -> None:
        self._link = link
        self._publisher = publisher

    async def open_review(self, claim: Claim, decision: Decision) -> Case:
        """PERSONAL_CLAIM_REVIEW for a REFERRED personal decision (SPEC §12)."""
        rt = self._link.rt
        now = rt.clock.now()
        merchant = rt.static.city.merchant(claim.merchant_id)
        first_day = claim.silent_dates[0] if claim.silent_dates else claim.event_date
        evidence: dict[str, Any] = {
            "expected_vs_actual": hourly_evidence(rt, merchant.id, first_day, now),
            "silent_days": iso_days(claim.silent_dates),
            "precedents": await precedents(rt, merchant.id, REVIEW_PRECEDENTS),
        }
        if claim.slip is not None and claim.slip_media_id is not None:
            evidence |= {"slip": slip_evidence(claim.slip, claim.slip_media_id)}
            evidence |= name_evidence(claim.slip, merchant.kyc_name)
        days = ", ".join(weekday_day_month(d) for d in claim.silent_dates) or weekday_day_month(first_day)
        case = rt.cases.open(
            kind=CaseKind.PERSONAL_CLAIM_REVIEW,
            merchant_id=merchant.id,
            at=now,
            summary_en=f"Personal claim of {format_inr(decision.amount_paise)} for {days}: "
            f"{decision.referral_reason or 'needs a claims officer'}",
            summary_hi=None,
            evidence=evidence,
            claim_id=claim.id,
            decision_id=decision.id,
        )
        await self._announce(
            case, f"{merchant.shop_name}: personal claim sent to a claims officer · case {case.id}"
        )
        return case

    async def open_dispute(self, merchant_id: str, text: str) -> DisputeOutcome:
        """DISPUTE about the latest settled decision (SPEC §13.5 DISPUTE_AMOUNT, §13.6 EXPLAINED; K5).

        Settled is APPROVED and credited, or DECLINED. With none there is nothing to dispute and no case is opened;
        a case that is still open for the same decision is returned instead of a second one.
        """
        rt = self._link.rt
        decision = rt.store.latest_final_decision(merchant_id)
        if decision is None:
            logger.info("dispute from %s has no settled decision to dispute; no case opened", merchant_id)
            return DisputeOutcome(case=None)
        already = next(
            (
                c
                for c in rt.store.cases(CaseStatus.OPEN)
                if c.kind is CaseKind.DISPUTE and c.decision_id == decision.id
            ),
            None,
        )
        if already is not None:
            return DisputeOutcome(case=already, already_open=True)
        now = rt.clock.now()
        merchant = rt.static.city.merchant(merchant_id)
        claim = rt.store.claim(decision.claim_id)
        day = claim.event_date
        evidence = {
            "expected_vs_actual": hourly_evidence(rt, merchant_id, day, now),
            "merchant_text": text,
            "precedents": await precedents(rt, merchant_id, DISPUTE_PRECEDENTS),
        }
        about = (
            f"a declined {claim.kind.value.lower()} claim"
            if decision.outcome is DecisionOutcome.DECLINED
            else f"the {format_inr(decision.amount_paise)} {claim.kind.value.lower()} payout"
        )
        summary = f"{merchant.shop_name} disputes {about} for {weekday_day_month(day)}"
        case = rt.cases.open(
            kind=CaseKind.DISPUTE,
            merchant_id=merchant_id,
            at=now,
            summary_en=summary,
            summary_hi=None,
            evidence=evidence,
            claim_id=claim.id,
            decision_id=decision.id,
        )
        await rt.integrations.memory.remember(dispute_fact(case, merchant.zone_id, decision))
        await self._announce(case, f"{summary} · case {case.id}")
        return DisputeOutcome(case=case)

    async def _announce(self, case: Case, text: str) -> None:
        rt = self._link.rt
        self._publisher.case(case)
        rt.feed.add(case.opened_at, "case", text, merchant_id=case.merchant_id)
        await start_case_workflows(rt, case.id, case.merchant_id)
