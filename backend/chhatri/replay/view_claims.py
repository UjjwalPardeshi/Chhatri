"""GET /api/merchants/{id}/claims: the claim tracker the mini-app reads (K5; data-model-and-api 5.1, fs-04 section 9).

One item for each claim of the merchant, with its five steps (`replay.view_steps`), and one DISPUTE item for each
dispute case, newest first. Everything is read from what the engine recorded: the first decision of a claim says what
the checks found and the last one is the decision that stands (an officer's decision supersedes the referral it
resolves, so a claim appears once). The amount is the decision's amount, never recomputed. A DISPUTE item names the
case and the decision it is about and has no steps; the amount it shows is the disputed decision's, which a dispute never
changes.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import TYPE_CHECKING, Any, Final

from chhatri.domain.enums import CaseKind, ClaimKind
from chhatri.domain.models import Case, Claim, Decision
from chhatri.money import format_inr
from chhatri.replay.view_records import iso
from chhatri.replay.view_steps import ClaimFacts, claim_steps

if TYPE_CHECKING:
    from chhatri.replay.state import Runtime

__all__ = ["claims_view"]

CHECK_IN_ACTION: Final = "silence.detected"
DISPUTE: Final = "DISPUTE"


def _detected_at(rt: Runtime, claim: Claim) -> datetime:
    """An area claim is detected when its trigger fires (the claim's own time); a personal one when Chhatri checks in."""
    if claim.kind is ClaimKind.AREA:
        return claim.created_at
    checked_in = rt.audit.latest(
        action=CHECK_IN_ACTION, subject_id=claim.merchant_id, at_or_before=claim.created_at
    )
    return checked_in.at if checked_in is not None else claim.created_at


def _review_case(cases: Iterable[Case], claim: Claim) -> Case | None:
    """The officer case a REFERRED claim opened (the newest, if a claim ever had two)."""
    reviews = [c for c in cases if c.claim_id == claim.id and c.kind is not CaseKind.DISPUTE]
    return reviews[-1] if reviews else None


def _case_fields(case: Case | None) -> dict[str, Any]:
    if case is None:
        return {"case_id": None, "case_status": None, "due_by": None, "resolution": None}
    return {
        "case_id": case.id,
        "case_status": case.status.value,
        "due_by": iso(case.due_by),
        "resolution": case.resolution,
    }


def _amount(decision: Decision | None) -> dict[str, Any]:
    if decision is None:
        return {"amount_paise": None, "amount_label": None}
    return {"amount_paise": decision.amount_paise, "amount_label": format_inr(decision.amount_paise)}


def _claim_item(rt: Runtime, claim: Claim, cases: Iterable[Case]) -> tuple[datetime, dict[str, Any]] | None:
    decisions = rt.store.decisions_for_claim(claim.id)
    if not decisions:
        return None  # a claim is recorded together with its decision; nothing to show until then
    first, effective = decisions[0], decisions[-1]
    case = _review_case(cases, claim)
    facts = ClaimFacts(rt, claim, first, effective, rt.store.payout_for_decision(effective.id), case)
    detected = _detected_at(rt, claim)
    area = claim.kind is ClaimKind.AREA
    item: dict[str, Any] = {
        "claim_id": claim.id,
        "disputed_claim_id": None,
        "kind": claim.kind.value,
        "claim_at": iso(detected),
        "zone_id": rt.static.city.merchant(claim.merchant_id).zone_id if area else None,
        "trigger_id": claim.trigger_id,
        "decision_id": effective.id,
        "outcome": effective.outcome.value,
        **_amount(effective),
        "steps": claim_steps(facts, detected),
        **_case_fields(case),
    }
    return detected, item


def _dispute_item(rt: Runtime, case: Case) -> tuple[datetime, dict[str, Any]]:
    decision = rt.store.decision(case.decision_id) if case.decision_id is not None else None
    claim = rt.store.claim(case.claim_id) if case.claim_id is not None else None
    area = claim is not None and claim.kind is ClaimKind.AREA
    item: dict[str, Any] = {
        "claim_id": None,
        "disputed_claim_id": claim.id if claim is not None else None,
        "kind": DISPUTE,
        "claim_at": iso(case.opened_at),
        "zone_id": rt.static.city.merchant(case.merchant_id).zone_id if area else None,
        "trigger_id": None,
        "decision_id": decision.id if decision is not None else None,
        "outcome": decision.outcome.value if decision is not None else None,
        **_amount(decision),
        "steps": [],
        **_case_fields(case),
    }
    return case.opened_at, item


def claims_view(rt: Runtime, merchant_id: str) -> list[dict[str, Any]]:
    """The merchant's claims and disputes, newest first; KeyError for an unknown merchant."""
    rt.static.city.merchant(merchant_id)
    cases = tuple(c for c in rt.store.cases() if c.merchant_id == merchant_id)
    built = [_claim_item(rt, claim, cases) for claim in rt.store.claims_for(merchant_id)]
    rows = [row for row in built if row is not None]
    rows += [_dispute_item(rt, case) for case in cases if case.kind is CaseKind.DISPUTE]
    rows.sort(
        key=lambda row: (row[0], row[1]["kind"] == DISPUTE), reverse=True
    )  # a dispute is newer than its claim
    return [item for _, item in rows]
