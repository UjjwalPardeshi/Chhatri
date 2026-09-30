"""Premium collection: payment links and evening settlement (SPEC §9.7, §10, §24.3).

- `create_link` asks the `PaymentLinks` integration for a link for the quote's first payment
  (`first_payment_days` of premium) and records a PENDING `PremiumPayment`.
- `mark_paid` (paid callback) is idempotent. For a merchant without a live cover it creates the new
  cover (WAITING until `starts_on`, then ACTIVE) prepaid through the paid period; for a live cover it
  extends `prepaid_through` by the days paid for, contiguously after the current prepaid date
  (documented interpretation of SPEC §10 "extend prepaid_through").
- `settle_evening` (21:00 simulated) applies the gross-settlement rule of SPEC §9.7: when the day's
  own collections ≥ the cover's premium and the cover is prepaid exactly through `day`, the next day
  is prepaid and a SETTLEMENT_DEDUCTION payment is recorded; otherwise nothing advances and the
  shortfall is audited.
Premium amounts per zone come from backend/artifacts/premiums.json (`premium_table`).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from typing import Final

from chhatri.audit.log import AuditLog
from chhatri.clock import require_aware
from chhatri.domain.enums import CoverStatus, PremiumMethod, PremiumStatus
from chhatri.domain.models import Cover, CoverQuote, Merchant, PremiumPayment
from chhatri.ids import IdFactory
from chhatri.integrations.base import IntegrationError, PaymentLinks
from chhatri.ledger.premium_table import load_premiums, premium_per_day_paise
from chhatri.policy.rules import PolicyRules
from chhatri.store.repositories import Store

logger = logging.getLogger(__name__)

ACTOR: Final = "system"
ONE_DAY: Final = timedelta(days=1)
LIVE_COVER: Final = frozenset({CoverStatus.ACTIVE, CoverStatus.WAITING, CoverStatus.PENDING_PAYMENT})
SETTLING_COVER: Final = frozenset({CoverStatus.ACTIVE, CoverStatus.WAITING})
SETTLEMENT_SOURCE: Final = "settlement (simulated)"


def _live(cover: Cover | None) -> Cover | None:
    return cover if cover is not None and cover.status in LIVE_COVER else None


class PremiumService:
    """Premium links, paid callbacks and evening settlement (SPEC §10, §9.7)."""

    def __init__(
        self,
        store: Store,
        audit: AuditLog,
        ids: IdFactory,
        rules: PolicyRules,
        links: PaymentLinks,
        *,
        premiums: Mapping[str, int] | None = None,
    ) -> None:
        self._store = store
        self._audit = audit
        self._ids = ids
        self._rules = rules
        self._links = links
        self._premiums = premiums if premiums is not None else load_premiums(rules)

    def premium_per_day(self, zone_id: str) -> int:
        """Daily premium in paise for a zone (premiums.json, else the SPEC §9.1 minimum)."""
        return premium_per_day_paise(zone_id, self._premiums, self._rules)

    async def create_link(self, merchant: Merchant, quote: CoverQuote, at: datetime) -> PremiumPayment:
        """Payment link for the quote's first payment; records a PENDING PremiumPayment (SPEC §10)."""
        at = require_aware(at)
        if quote.merchant_id != merchant.id:
            raise ValueError(f"quote {quote.id} is for {quote.merchant_id}, not {merchant.id}")
        if quote.first_payment_paise != quote.premium_per_day_paise * quote.days_prepaid:
            raise ValueError(f"quote {quote.id}: first payment must be premium × days prepaid")
        purpose = f"Chhatri cover premium, {quote.days_prepaid} days from {quote.starts_on.isoformat()}"
        try:
            link = await self._links.create_premium_link(merchant, quote.first_payment_paise, purpose)
        except IntegrationError:
            logger.exception("payment link failed for quote %s", quote.id)
            raise
        if link.amount_paise != quote.first_payment_paise:
            raise ValueError(f"payment link {link.link_id} amount differs from quote {quote.id}")
        existing = _live(self._store.cover(merchant.id))
        payment = PremiumPayment(
            id=self._ids.next("premium"),
            cover_id=existing.id if existing is not None else None,
            merchant_id=merchant.id,
            amount_paise=quote.first_payment_paise,
            method=PremiumMethod.PAYMENT_LINK,
            covers_from=quote.starts_on,
            covers_to=quote.starts_on + timedelta(days=quote.days_prepaid - 1),
            status=PremiumStatus.PENDING,
            link_id=link.link_id,
            link_url=link.url,
            source=link.source,
            created_at=at,
        )
        self._store.add_premium(payment)
        self._record(at, "premium.link_created", payment, {"quote_id": quote.id, "link_id": link.link_id})
        return payment

    def mark_paid(self, link_id: str, at: datetime, txn_id: str | None) -> PremiumPayment:
        """Paid callback: marks the payment PAID and activates or extends the cover (idempotent)."""
        at = require_aware(at)
        payment = self._store.premium_by_link(link_id)
        if payment is None:
            raise KeyError(f"unknown payment link {link_id}")
        if payment.status is PremiumStatus.PAID:
            return payment
        if payment.status is not PremiumStatus.PENDING:
            raise ValueError(f"payment {payment.id} is {payment.status}; only PENDING links can be paid")
        days = (payment.covers_to - payment.covers_from).days + 1
        existing = _live(self._store.cover(payment.merchant_id))
        if existing is None:
            first, cover = payment.covers_from, self._new_cover(payment, days, at)
        else:
            first = existing.prepaid_through + ONE_DAY if existing.prepaid_through else existing.starts_on
            cover = self._extend(existing, first + timedelta(days=days - 1), at)
        self._store.put_cover(cover)
        paid = payment.model_copy(
            update={
                "status": PremiumStatus.PAID,
                "paid_at": at,
                "cover_id": cover.id,
                "covers_from": first,
                "covers_to": first + timedelta(days=days - 1),
            }
        )
        self._store.replace_premium(paid)
        self._record(at, "premium.paid", paid, {"txn_id": txn_id, "cover_status": cover.status.value})
        return paid

    def _status_on(self, starts_on: date, at: datetime) -> CoverStatus:
        return CoverStatus.ACTIVE if at.date() >= starts_on else CoverStatus.WAITING

    def _new_cover(self, payment: PremiumPayment, days: int, at: datetime) -> Cover:
        per_day, remainder = divmod(payment.amount_paise, days)
        if remainder:
            raise ValueError(f"payment {payment.id} is not a whole number of daily premiums")
        return Cover(
            id=f"CV-{payment.merchant_id}-{payment.covers_from:%Y%m%d}",
            merchant_id=payment.merchant_id,
            purchased_at=at,
            starts_on=payment.covers_from,
            premium_per_day_paise=per_day,
            prepaid_through=payment.covers_to,
            status=self._status_on(payment.covers_from, at),
        )

    def _extend(self, cover: Cover, prepaid_through: date, at: datetime) -> Cover:
        status = (
            self._status_on(cover.starts_on, at)
            if cover.status is CoverStatus.PENDING_PAYMENT
            else cover.status
        )
        return cover.model_copy(update={"prepaid_through": prepaid_through, "status": status})

    def settle_evening(
        self, day: date, gross_settlement_paise: Mapping[str, int], at: datetime
    ) -> tuple[PremiumPayment, ...]:
        """Evening gross settlement prepays day + 1 where collections cover the premium (SPEC §9.7)."""
        at = require_aware(at)
        created: list[PremiumPayment] = []
        for merchant_id in sorted(gross_settlement_paise):
            gross = gross_settlement_paise[merchant_id]
            if isinstance(gross, bool) or not isinstance(gross, int) or gross < 0:
                raise ValueError(f"gross settlement for {merchant_id} must be non-negative integer paise")
            payment = self._settle_one(merchant_id, day, gross, at)
            if payment is not None:
                created.append(payment)
        return tuple(created)

    def _settle_one(self, merchant_id: str, day: date, gross: int, at: datetime) -> PremiumPayment | None:
        cover = self._store.cover(merchant_id)
        if cover is None or cover.status not in SETTLING_COVER:
            return None
        if cover.prepaid_through is not None and cover.prepaid_through > day:
            return None
        premium = cover.premium_per_day_paise
        if cover.prepaid_through != day or gross < premium:
            reason = (
                "cover lapsed before this day"
                if cover.prepaid_through != day
                else "collections below premium"
            )
            data = {
                "merchant_id": merchant_id,
                "cover_id": cover.id,
                "day": day.isoformat(),
                "reason": reason,
            }
            data |= {"gross_settlement_paise": gross, "premium_paise": premium}
            self._audit.append(
                at=at,
                actor=ACTOR,
                action="premium.not_settled",
                subject_type="cover",
                subject_id=cover.id,
                data=data,
            )
            return None
        next_day = day + ONE_DAY
        self._store.put_cover(cover.model_copy(update={"prepaid_through": next_day}))
        payment = PremiumPayment(
            id=self._ids.next("premium"),
            cover_id=cover.id,
            merchant_id=merchant_id,
            amount_paise=premium,
            method=PremiumMethod.SETTLEMENT_DEDUCTION,
            covers_from=next_day,
            covers_to=next_day,
            status=PremiumStatus.PAID,
            source=SETTLEMENT_SOURCE,
            created_at=at,
            paid_at=at,
        )
        self._store.add_premium(payment)
        self._record(at, "premium.settled", payment, {"gross_settlement_paise": gross})
        return payment

    def _record(
        self, at: datetime, action: str, payment: PremiumPayment, extra: Mapping[str, object]
    ) -> None:
        data = {
            "merchant_id": payment.merchant_id,
            "cover_id": payment.cover_id,
            "amount_paise": payment.amount_paise,
            "method": payment.method.value,
            "status": payment.status.value,
            "covers_from": payment.covers_from.isoformat(),
            "covers_to": payment.covers_to.isoformat(),
            "source": payment.source,
            **extra,
        }
        self._audit.append(
            at=at,
            actor=ACTOR,
            action=action,
            subject_type="premium_payment",
            subject_id=payment.id,
            data=data,
        )
