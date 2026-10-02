"""Forget my slip (N6/H23, fs-07 section 9.8): erase one stored slip, and say plainly what that cannot remove.

Erased: the stored photo, the slip fields on the claim, the slip text inside the checks of every decision of that
claim, the slip fields and summary on the review case, and the photo message in the thread. Kept: the decision, the
amount and which checks passed or failed. Never edited: the audit log, which is append-only and hash-chained, so
entries written before the erase can still show the name and dates (the answer says so).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

from chhatri.audit.log import AuditLog
from chhatri.clock import require_aware
from chhatri.consent import notice
from chhatri.consent.errors import ConsentConflict
from chhatri.consent.ledger import ConsentBook
from chhatri.domain.enums import CaseKind, CaseStatus, CheckCode, MessageKind
from chhatri.domain.models import Claim, Decision, SlipExtraction
from chhatri.store.repositories import Store

__all__ = ["ERASED_SOURCE", "ERASED_TEXT", "KEPT", "forget_slip"]

ERASED_SOURCE: Final = "erased"
ERASED_TEXT: Final = "Erased at the merchant's request"
PHOTO_ERASED_EN: Final = "Photo erased"
PHOTO_ERASED_HI: Final = "फ़ोटो मिटा दी गई"
KEPT: Final = ["DECISION_OUTCOME", "AMOUNT", "CHECK_CODES_AND_RESULTS", "AUDIT_ENTRIES"]
SLIP_CHECKS: Final = frozenset({CheckCode.SLIP_READABLE, CheckCode.NAME_MATCHES_KYC, CheckCode.DATES_MATCH})
VIA: Final = "demo_officer_session"


def claim_holding(store: Store, merchant_id: str, slip_id: str) -> Claim:
    """The merchant's claim whose stored photo is ``slip_id``; KeyError when it is not this merchant's."""
    for claim in store.claims_for(merchant_id):
        if claim.slip_media_id == slip_id:
            return claim
    raise KeyError(f"unknown slip {slip_id}")


def is_erased(claim: Claim) -> bool:
    return claim.slip is not None and claim.slip.source == ERASED_SOURCE


def open_review(store: Store, claim_id: str) -> bool:
    return any(
        c.claim_id == claim_id and c.kind is CaseKind.PERSONAL_CLAIM_REVIEW
        for c in store.cases(CaseStatus.OPEN)
    )


def _erase_decision(decision: Decision) -> Decision | None:
    changed = False
    checks = []
    for check in decision.checks:
        if check.code in SLIP_CHECKS:
            check = check.model_copy(update={"observed": ERASED_TEXT, "detail_en": ERASED_TEXT})
            changed = True
        checks.append(check)
    slip_text = {c.observed for c in decision.checks if c.code in SLIP_CHECKS and c.observed}
    slip_text |= {c.detail_en for c in decision.checks if c.code in SLIP_CHECKS}
    reason = decision.referral_reason
    if reason and any(text and text in reason for text in slip_text):
        reason, changed = ERASED_TEXT, True
    if not changed:
        return None
    return decision.model_copy(update={"checks": tuple(checks), "referral_reason": reason})


def _erase_cases(store: Store, claim: Claim, at: datetime) -> int:
    count = 0
    for case in (c for c in store.cases() if c.claim_id == claim.id):
        evidence = {k: v for k, v in case.evidence.items() if k not in ("slip", "name_score")}
        evidence["slip"] = {"erased": True, "erased_at": at.isoformat()}
        summary = ERASED_TEXT if case.kind is CaseKind.PERSONAL_CLAIM_REVIEW else case.summary_en
        store.replace_case(case.model_copy(update={"evidence": evidence, "summary_en": summary}))
        count += 1
    return count


def _erase_messages(store: Store, merchant_id: str, slip_id: str) -> int:
    count = 0
    for message in store.messages(merchant_id):
        if message.kind is MessageKind.IMAGE and message.media_url and message.media_url.endswith(slip_id):
            store.replace_message(
                message.model_copy(
                    update={"media_url": None, "text_en": PHOTO_ERASED_EN, "text_hi": PHOTO_ERASED_HI}
                )
            )
            count += 1
    return count


def forget_slip(
    *, store: Store, audit: AuditLog, book: ConsentBook, merchant_id: str, slip_id: str, now: datetime
) -> dict[str, Any]:
    """Erase one slip. KeyError (404) for a slip that is not the merchant's; ConsentConflict for 409."""
    now = require_aware(now)
    claim = claim_holding(store, merchant_id, slip_id)
    if is_erased(claim):
        raise ConsentConflict("already_erased", "this slip was already erased")
    if open_review(store, claim.id):
        raise ConsentConflict("case_open", "your claim is still being checked by our team")
    photo = store.delete_media(slip_id)
    store.replace_claim(
        claim.model_copy(update={"slip": SlipExtraction(confidence=0.0, source=ERASED_SOURCE)})
    )
    erased_ids: list[str] = []
    for decision in store.decisions_for_claim(claim.id):
        erased = _erase_decision(decision)
        if erased is not None:
            store.replace_decision(erased)
            erased_ids.append(decision.id)
    case_fields = _erase_cases(store, claim, now)
    messages = _erase_messages(store, merchant_id, slip_id)
    book.mark_erased(slip_id, now)
    counts = {
        "photo": photo,
        "claim_fields": True,
        "decisions": len(erased_ids),
        "case_fields": case_fields,
        "messages": messages,
    }
    audit.append(
        at=now,
        actor=f"merchant:{merchant_id}",
        action="slip.erased",
        subject_type="media",
        subject_id=slip_id,
        data={
            "merchant_id": merchant_id,
            "claim_id": claim.id,
            "decision_ids": erased_ids,
            "counts": counts,
            "via": VIA,
        },
    )
    return {
        "slip_id": slip_id,
        "claim_id": claim.id,
        "erased_at": now.isoformat(),
        "erased": counts,
        "kept": list(KEPT),
        "audit_note_en": notice.ERASE_AUDIT_NOTE_EN,
        "audit_note_hi": notice.ERASE_AUDIT_NOTE_HI,
    }
