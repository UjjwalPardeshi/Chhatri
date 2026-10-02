"""GET /api/decisions/{id}/receipt: the receipt of one decision (H2, H3, H13, H14; data-model-and-api 5.8, fs-09 section 10).

The decision as it was recorded, its checks and money numbers each with their sources, the counterfactuals the engine
confirmed, and what followed: the payout, the lender's answer, the case, the position in the audit chain and the
grievance path. The sources and counterfactuals are the ones built when the decision was made and stored with it
(`Decision.sources`, `Decision.counterfactuals`); this view only arranges them, so after the payout nothing is rebuilt
from facts that have since changed. The receipt carries no phone number and shows the KYC name masked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from chhatri.consent.forget import ERASED_TEXT, SLIP_CHECKS
from chhatri.domain.enums import ClaimKind, DecisionOutcome, PayoutStatus
from chhatri.domain.models import (
    Case,
    Counterfactual,
    Decision,
    HolidayRequest,
    Merchant,
    Source,
    SourcedLine,
)
from chhatri.money import format_inr
from chhatri.policy.provenance import CHECK_CLAUSE
from chhatri.replay.view_records import iso, iso_date, iso_or_none, mask_name

if TYPE_CHECKING:
    from chhatri.replay.state import Runtime

__all__ = ["GRIEVANCE_LADDER", "counterfactual_view", "receipt_view"]

GRIEVANCE_LADDER: Final = ("PAYTM_DISPUTE", "INSURER_GRO", "BIMA_BHAROSA", "OMBUDSMAN")  # fs-06 section 5.4
VERIFY_PATH: Final = "/api/audit/verify"
HASH_SHORT_CHARS: Final = 12
OFFICER_PREFIX: Final = "officer:"
AMOUNT_CLAUSE: Final = "C4"


def _source(source: Source) -> dict[str, Any]:
    return {
        "kind": source.kind.value,
        "label": source.label,
        "ref": source.ref,
        "as_of": iso_or_none(source.as_of),
        "origin": source.origin.value,
        "clause": source.clause,
    }


def _hide_kyc(text: str | None, merchant: Merchant) -> str | None:
    """The KYC name appears masked, as in the merchant file (SPEC section 21)."""
    return None if text is None else text.replace(merchant.kyc_name, mask_name(merchant.kyc_name))


def _check(check: Any, lines: dict[tuple[str, str], SourcedLine], merchant: Merchant) -> dict[str, Any]:
    line = lines.get(("CHECK", check.code.value))
    return {
        "code": check.code.value,
        "severity": check.severity.value,
        "status": check.status.value,
        "label_en": check.label_en,
        "detail_en": _hide_kyc(check.detail_en, merchant),
        "observed": _hide_kyc(check.observed, merchant),
        "required": _hide_kyc(check.required, merchant),
        "clause": line.clause if line is not None else CHECK_CLAUSE[check.code],
        # fs-07 rule 5: true on the three slip checks once the merchant erased the slip (their text was replaced)
        "erased": check.code in SLIP_CHECKS and check.observed == ERASED_TEXT,
        "sources": [_source(s) for s in line.sources] if line is not None else [],
    }


def _explanation(decision: Decision, lines: dict[tuple[str, str], SourcedLine]) -> dict[str, Any] | None:
    explanation = decision.explanation
    if explanation is None:
        return None
    facts = [
        {
            "key": line.key,
            "label_en": line.label_en,
            "value": line.value,
            "sources": [_source(s) for s in line.sources],
        }
        for line in decision.sources
        if line.kind == "FACT"
    ]
    return {
        "formula_en": explanation.formula_en,
        "formula_hi": explanation.formula_hi,
        "clause": AMOUNT_CLAUSE,
        "facts": facts,
    }


def counterfactual_view(cf: Counterfactual) -> dict[str, Any]:
    """One verified counterfactual as JSON (the receipt and the what-if zone explanation share it)."""
    paise = cf.result.amount_paise
    return {
        "id": cf.id,
        "kind": cf.kind.value,
        "actionable": cf.actionable,
        "changes": [
            {
                "check_code": c.check_code.value if c.check_code is not None else None,
                "field": c.field,
                "observed": c.observed,
                "needed": c.needed,
            }
            for c in cf.changes
        ],
        "result": {
            "outcome": cf.result.outcome.value if cf.result.outcome is not None else None,
            "amount_paise": paise,
            "amount_label": format_inr(paise) if paise is not None else None,
        },
        "verified": cf.verified,
        "text_en": cf.text_en,
        "text_hi": cf.text_hi,
        "sources": [_source(s) for s in cf.sources],
    }


def _payout(rt: Runtime, decision: Decision) -> dict[str, Any] | None:
    payout = rt.store.payout_for_decision(decision.id)
    if payout is None:
        return None
    return {
        "id": payout.id,
        "status": payout.status.value,
        "amount_label": format_inr(payout.amount_paise),
        "credited_at": iso_or_none(payout.credited_at),
    }


def _edi(rt: Runtime, decision: Decision) -> dict[str, Any] | None:
    """The lender's request for this decision (X4); None when no request was made (no loan, or the flag is off)."""
    requests: list[HolidayRequest] = [
        r for r in rt.store.holiday_requests(decision.merchant_id) if r.decision_id == decision.id
    ]
    if not requests:
        return None
    request = requests[-1]
    loan = rt.static.city.loans.get(decision.merchant_id)
    return {
        "request_id": request.id,
        "status": request.status.value,
        "reason_code": request.reason_code.value if request.reason_code is not None else None,
        "instalment_date": iso_date(request.instalment_date),
        "instalment_label": format_inr(request.instalment_paise),
        "decided_at": iso_or_none(request.decided_at),
        "lender": loan.lender_name if loan is not None else "",
    }


def _case(rt: Runtime, decision: Decision) -> dict[str, Any] | None:
    """The newest case about this decision, or about the referred decision an officer decision replaces."""
    about = {decision.id, decision.supersedes} - {None}
    cases: list[Case] = [c for c in rt.store.cases() if c.decision_id in about]
    if not cases:
        return None
    case = cases[-1]
    return {"id": case.id, "kind": case.kind.value, "status": case.status.value, "due_by": iso(case.due_by)}


def _audit(rt: Runtime, decision: Decision, kind: ClaimKind) -> dict[str, Any] | None:
    if decision.decided_by.startswith(OFFICER_PREFIX):
        action = "decision.officer"
    else:
        action = "decision.area" if kind is ClaimKind.AREA else "decision.personal"
    entry = rt.audit.latest(action=action, subject_id=decision.id, at_or_before=decision.decided_at)
    if entry is None:
        return None
    return {"seq": entry.seq, "hash_short": entry.hash[:HASH_SHORT_CHARS], "verify_path": VERIFY_PATH}


def _dispute_allowed(rt: Runtime, decision: Decision) -> bool:
    """A dispute is about a settled decision: declined, or approved and credited (K5)."""
    if decision.outcome is DecisionOutcome.DECLINED:
        return True
    payout = rt.store.payout_for_decision(decision.id)
    return (
        decision.outcome is DecisionOutcome.APPROVED
        and payout is not None
        and payout.status is PayoutStatus.CREDITED
    )


def receipt_view(rt: Runtime, decision_id: str) -> dict[str, Any]:
    """The receipt of one decision; KeyError for an unknown id."""
    decision = rt.store.decision(decision_id)
    claim = rt.store.claim(decision.claim_id)
    merchant = rt.static.city.merchant(decision.merchant_id)
    lines = {(line.kind, line.key): line for line in decision.sources}
    return {
        "decision": {
            "id": decision.id,
            "claim_id": decision.claim_id,
            "merchant_id": decision.merchant_id,
            "outcome": decision.outcome.value,
            "amount_paise": decision.amount_paise,
            "amount_label": format_inr(decision.amount_paise),
            "rules_version": decision.rules_version,
            "decided_at": iso(decision.decided_at),
            "decided_by": decision.decided_by,
            "supersedes": decision.supersedes,
            "referral_reason": _hide_kyc(decision.referral_reason, merchant),
        },
        "explanation": _explanation(decision, lines),
        "checks": [_check(check, lines, merchant) for check in decision.checks],
        "counterfactuals": [counterfactual_view(cf) for cf in decision.counterfactuals],
        "payout": _payout(rt, decision),
        "edi": _edi(rt, decision),
        "case": _case(rt, decision),
        "audit": _audit(rt, decision, claim.kind),
        "grievance": {
            "dispute_allowed": _dispute_allowed(rt, decision),
            "ladder": list(GRIEVANCE_LADDER),
            "first_step_hours": rt.static.rules.dispute_sla_hours,
        },
    }
