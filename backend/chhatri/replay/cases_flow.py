"""Cases for claims officers: personal-claim reviews and disputes (SPEC §12, §13.5, §13.6, §16).

- `open_review`: a REFERRED personal claim opens a PERSONAL_CLAIM_REVIEW case with the evidence
  bundle (expected vs actual on the first silent day, the slip, KYC name and score, silent days,
  precedents of past cases), then starts ``human-review`` and ``follow-up`` (B1).
- `open_dispute` (deck test EXPLAINED): a DISPUTE case about the merchant's latest paid decision
  (expected vs actual on its event date, the merchant's words, precedents of past disputes); after
  a fresh load it is C-2291. The disputed decision and its checks are linked via ``decision_id``.
Both publish a ``case`` event, add a feed item and write a memory fact (SPEC §16).
"""

from __future__ import annotations

from typing import Any, Final

from chhatri.domain.enums import CaseKind
from chhatri.domain.models import Case, Claim, Decision
from chhatri.money import format_inr
from chhatri.replay.evidence import hourly_evidence, iso_days, name_evidence, precedents, slip_evidence
from chhatri.replay.fmt import weekday_day_month
from chhatri.replay.memory_facts import dispute_fact
from chhatri.replay.publish import Publisher, RuntimeLink
from chhatri.replay.runs import start_case_workflows

__all__ = ["CaseFlow"]

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

    async def open_dispute(self, merchant_id: str, text: str) -> Case:
        """DISPUTE about the latest paid decision (SPEC §13.5 DISPUTE_AMOUNT, §13.6 EXPLAINED)."""
        rt = self._link.rt
        now = rt.clock.now()
        merchant = rt.static.city.merchant(merchant_id)
        decision = rt.store.latest_paid_decision(merchant_id)
        claim = rt.store.claim(decision.claim_id) if decision is not None else None
        day = claim.event_date if claim is not None else now.date()
        evidence = {
            "expected_vs_actual": hourly_evidence(rt, merchant_id, day, now),
            "merchant_text": text,
            "precedents": await precedents(rt, merchant_id, DISPUTE_PRECEDENTS),
        }
        if decision is not None and claim is not None:
            summary = (
                f"{merchant.shop_name} disputes the {format_inr(decision.amount_paise)} "
                f"{claim.kind.value.lower()} payout for {weekday_day_month(day)}"
            )
        else:
            summary = f"{merchant.shop_name} disputes a payout amount; no paid claim on record"
        case = rt.cases.open(
            kind=CaseKind.DISPUTE,
            merchant_id=merchant_id,
            at=now,
            summary_en=summary,
            summary_hi=None,
            evidence=evidence,
            claim_id=claim.id if claim is not None else None,
            decision_id=decision.id if decision is not None else None,
        )
        await rt.integrations.memory.remember(dispute_fact(case, merchant.zone_id, decision))
        await self._announce(case, f"{summary} · case {case.id}")
        return case

    async def _announce(self, case: Case, text: str) -> None:
        rt = self._link.rt
        self._publisher.case(case)
        rt.feed.add(case.opened_at, "case", text, merchant_id=case.merchant_id)
        await start_case_workflows(rt, case.id, case.merchant_id)
