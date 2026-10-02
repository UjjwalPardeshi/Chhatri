"""The consent centre's reads and the withdrawal (N6, fs-07 sections 9.4 and 9.6)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, datetime
from typing import Any, Final

from chhatri.audit.log import AuditLog
from chhatri.clock import IST, require_aware
from chhatri.consent import notice
from chhatri.consent.errors import ConsentConflict
from chhatri.consent.forget import claim_holding, is_erased, open_review
from chhatri.consent.ledger import Consent, ConsentBook
from chhatri.conversation.messages import date_en, date_hi
from chhatri.domain.enums import CaseKind, CaseStatus, CoverStatus
from chhatri.domain.models import Cover
from chhatri.policy.cover import effective_status
from chhatri.store.repositories import Store

__all__ = ["ConsentService", "WithdrawNotice"]

VIA: Final = "demo_officer_session"
EFFECT_KINDS: Final = {
    notice.SALES: ["COVER_CANCELLED", "NO_NEW_CLAIMS", "LEFT_OUT_OF_ZONE_INDEX"],
    notice.SLIP: ["SLIPS_NOT_READ"],
    notice.SETTLEMENT: ["NO_SETTLEMENT_DEDUCTION"],
}
LAST_PAID_EN: Final = "the date you have paid for"
LAST_PAID_HI: Final = "जिस तारीख़ तक आपने भुगतान किया है"
WithdrawNotice = Callable[[str, str, "date | None"], Awaitable[Any]]


def _paid_through(cover: Cover | None) -> tuple[str, str]:
    if cover is None or cover.prepaid_through is None:
        return LAST_PAID_EN, LAST_PAID_HI
    return date_en(cover.prepaid_through), date_hi(cover.prepaid_through)


class ConsentService:
    def __init__(self, *, store: Store, audit: AuditLog, book: ConsentBook, waiting_days: int) -> None:
        self._store, self._audit, self._book, self._waiting_days = store, audit, book, waiting_days

    # ------------------------------------------------------------------ reads
    def _review_open(self, merchant_id: str) -> bool:
        return any(
            c.merchant_id == merchant_id and c.kind is CaseKind.PERSONAL_CLAIM_REVIEW
            for c in self._store.cases(CaseStatus.OPEN)
        )

    def _effect(self, purpose: str, merchant_id: str) -> tuple[str, str]:
        text = notice.TEXTS[purpose]
        paid_en, paid_hi = _paid_through(self._store.cover(merchant_id))
        return (
            text.effect_en.format(waiting_days=self._waiting_days, paid_through=paid_en),
            text.effect_hi.format(waiting_days=self._waiting_days, paid_through=paid_hi),
        )

    def _held(self, merchant_id: str) -> list[dict[str, Any]]:
        rows = []
        for claim in self._store.claims_for(merchant_id):
            if claim.slip_media_id is None:
                continue
            erased = is_erased(claim)
            blocked = (
                "already_erased" if erased else "case_open" if open_review(self._store, claim.id) else None
            )
            erased_at = self._book.erased_at(claim.slip_media_id)
            rows.append(
                {
                    "slip_id": claim.slip_media_id,
                    "claim_id": claim.id,
                    "received_at": claim.created_at.isoformat(),
                    "state": "ERASED" if erased else "HELD",
                    "erased_at": erased_at.isoformat() if erased_at else None,
                    "can_erase": blocked is None,
                    "blocked_reason": blocked,
                }
            )
        return rows

    def _item(self, merchant_id: str, purpose: str) -> dict[str, Any]:
        record = self._book.latest(merchant_id, purpose)
        text = notice.TEXTS[purpose]
        status = record.status if record else "NOT_GIVEN"
        blocked = "case_open" if purpose == notice.SALES and self._review_open(merchant_id) else None
        effect_en, effect_hi = self._effect(purpose, merchant_id)
        item: dict[str, Any] = {
            "consent_id": record.id if record else None,
            "purpose": purpose,
            "purpose_label_en": text.label_en,
            "purpose_label_hi": text.label_hi,
            "status": status,
            "granted_at": record.granted_at.isoformat() if record else None,
            "withdrawn_at": record.withdrawn_at.isoformat() if record and record.withdrawn_at else None,
            "source": record.source if record else None,
            "notice_version": record.notice_version if record else None,
            "current_notice_version": notice.NOTICE_VERSION,
            "required_to_buy": purpose in notice.REQUIRED_TO_BUY,
            "data_used_en": list(text.data_used_en),
            "data_used_hi": list(text.data_used_hi),
            "withdraw_effect_en": effect_en,
            "withdraw_effect_hi": effect_hi,
            "can_withdraw": status == "ACTIVE" and blocked is None,
            "blocked_reason": blocked if status == "ACTIVE" else None,
            "regrant_en": text.regrant_en,
            "regrant_hi": text.regrant_hi,
        }
        if purpose == notice.SLIP:
            item["held"] = self._held(merchant_id)
        return item

    def list_view(self, merchant_id: str) -> list[dict[str, Any]]:
        """The three purposes in the fixed order, a NOT_GIVEN placeholder for one never agreed to."""
        return [self._item(merchant_id, purpose) for purpose in notice.PURPOSES]

    # ------------------------------------------------------------------ withdraw
    def _owned(self, merchant_id: str, consent_id: str) -> Consent:
        record = self._book.get(consent_id)
        if record.merchant_id != merchant_id:
            raise KeyError(f"unknown consent {consent_id}")
        return record

    async def withdraw(
        self, *, merchant_id: str, consent_id: str, now: datetime, notify: WithdrawNotice
    ) -> dict[str, Any]:
        now = require_aware(now)
        self._book.reconcile(merchant_id)
        record = self._owned(merchant_id, consent_id)
        if record.status == "WITHDRAWN":
            raise ConsentConflict("already_withdrawn", "this consent is already turned off")
        if record.purpose == notice.SALES and self._review_open(merchant_id):
            raise ConsentConflict("case_open", "your claim is still being checked by our team")
        effect_en, effect_hi = self._effect(record.purpose, merchant_id)  # the text the sheet showed
        cover = self._store.cover(merchant_id)
        self._book.replace(record.model_copy(update={"status": "WITHDRAWN", "withdrawn_at": now}))
        self._audit.append(
            at=now,
            actor=f"merchant:{merchant_id}",
            action="consent.withdrawn",
            subject_type="consent",
            subject_id=record.id,
            data={
                "merchant_id": merchant_id,
                "purpose": record.purpose,
                "via": VIA,
                "effects": EFFECT_KINDS[record.purpose],
            },
        )
        if record.purpose == notice.SALES and cover is not None and cover.status is not CoverStatus.CANCELLED:
            self._store.put_cover(cover.model_copy(update={"status": CoverStatus.CANCELLED}))
            self._audit.append(
                at=now,
                actor=f"merchant:{merchant_id}",
                action="cover.cancelled",
                subject_type="cover",
                subject_id=cover.id,
                data={
                    "merchant_id": merchant_id,
                    "reason": "SALES_CONSENT_WITHDRAWN",
                    "prepaid_through": cover.prepaid_through.isoformat() if cover.prepaid_through else None,
                },
            )
        await notify(merchant_id, record.purpose, cover.prepaid_through if cover else None)
        status = effective_status(self._store.cover(merchant_id), now.astimezone(IST).date())
        return {
            "consent_id": record.id,
            "purpose": record.purpose,
            "status": "WITHDRAWN",
            "withdrawn_at": now.isoformat(),
            "action_taken_en": effect_en,
            "action_taken_hi": effect_hi,
            "cover_status": status.value,
        }

    def held_claim(self, merchant_id: str, slip_id: str) -> str:
        """The claim id that holds ``slip_id`` (KeyError when it is not the merchant's)."""
        return claim_holding(self._store, merchant_id, slip_id).id
