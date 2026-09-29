"""Premium service (SPEC §10, §9.7, §24.3). Manages premium payments and cover activation."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from chhatri.audit.log import AuditLog
from chhatri.domain.enums import CoverStatus, PremiumMethod, PremiumStatus
from chhatri.domain.models import Cover, CoverQuote, Merchant, PremiumPayment
from chhatri.ids import IdFactory
from chhatri.integrations.base import PaymentLinks
from chhatri.policy.rules import PolicyRules
from chhatri.store.repositories import Store


class PremiumService:
    """Create premium payment links and manage cover activation."""

    def __init__(self, store: Store, audit: AuditLog, ids: IdFactory, rules: PolicyRules, links: PaymentLinks) -> None:
        self.store = store
        self.audit = audit
        self.ids = ids
        self.rules = rules
        self.links = links

    async def create_link(self, merchant: Merchant, quote: CoverQuote, at: datetime) -> PremiumPayment:
        """Create a premium payment link via the PaymentLinks integration.

        Args:
            merchant: The merchant buying cover.
            quote: The cover quote with starts_on and first_payment_paise.
            at: The time this link is created.

        Returns:
            A PremiumPayment with status PENDING and link_url set.
        """
        # Create payment link via integration
        payment_link = await self.links.create_premium_link(
            merchant=merchant,
            amount_paise=quote.first_payment_paise,
            purpose=f"Chhatri cover premium {quote.starts_on}",
        )

        # Create premium payment record
        premium_id = self.ids.next("premium")
        covers_to = quote.starts_on + timedelta(days=quote.days_prepaid - 1)
        premium = PremiumPayment(
            id=premium_id,
            cover_id=None,  # Set when mark_paid is called
            merchant_id=merchant.id,
            amount_paise=quote.first_payment_paise,
            method=PremiumMethod.PAYMENT_LINK,
            covers_from=quote.starts_on,
            covers_to=covers_to,
            status=PremiumStatus.PENDING,
            link_id=payment_link.link_id,
            link_url=payment_link.url,
            source=payment_link.source,
            created_at=at,
            paid_at=None,
        )

        self.store.add_premium(premium)

        # Audit
        self.audit.append(
            at=at,
            actor="workflow:buy-cover",
            action="premium-link-create",
            subject_type="premium-payment",
            subject_id=premium.id,
            data={
                "merchant_id": merchant.id,
                "amount_paise": premium.amount_paise,
                "link_id": payment_link.link_id,
                "starts_on": str(quote.starts_on),
                "days_prepaid": quote.days_prepaid,
                "source": payment_link.source,
            },
        )

        return premium

    def mark_paid(self, link_id: str, at: datetime, txn_id: str | None = None) -> PremiumPayment:
        """Mark a premium payment as paid. Activates or extends cover.

        Creates or updates the Cover record with status transitioning from WAITING to ACTIVE once
        the starts_on date is reached.

        Args:
            link_id: The payment link ID.
            at: The time payment was confirmed.
            txn_id: Transaction ID from the payment provider.

        Returns:
            The updated PremiumPayment with status PAID.

        Raises:
            KeyError: If premium with this link_id not found.
        """
        # Find the premium
        premium = self.store.premium_by_link(link_id)
        if not premium:
            raise KeyError(f"No premium for link {link_id}")

        # Mark paid
        paid_premium = premium.model_copy(update={
            "status": PremiumStatus.PAID,
            "paid_at": at,
        })
        self.store.replace_premium(paid_premium)

        # Get or create the cover
        merchant_id = premium.merchant_id
        existing_cover = self.store.cover(merchant_id)

        if existing_cover:
            # Extend existing cover
            new_cover = existing_cover.model_copy(update={
                "prepaid_through": paid_premium.covers_to,
            })
        else:
            # Create new cover
            cover_id = self.ids.next("quote")  # Reuse quote id format for cover ids

            # Determine initial status: WAITING until starts_on, then ACTIVE
            initial_status = CoverStatus.ACTIVE if paid_premium.covers_from <= at.date() else CoverStatus.WAITING

            new_cover = Cover(
                id=cover_id,
                merchant_id=merchant_id,
                purchased_at=at,
                starts_on=paid_premium.covers_from,
                premium_per_day_paise=self.rules.premium.min_per_day_rupees * 100,  # Will be updated from rules
                prepaid_through=paid_premium.covers_to,
                status=initial_status,
            )

        self.store.put_cover(new_cover)

        # Update premium with cover_id
        paid_premium_with_cover = paid_premium.model_copy(update={
            "cover_id": new_cover.id,
        })
        self.store.replace_premium(paid_premium_with_cover)

        # Audit
        self.audit.append(
            at=at,
            actor="workflow:payment-callback",
            action="premium-paid",
            subject_type="premium-payment",
            subject_id=premium.id,
            data={
                "merchant_id": merchant_id,
                "cover_id": new_cover.id,
                "amount_paise": premium.amount_paise,
                "covers_from": str(paid_premium.covers_from),
                "covers_to": str(paid_premium.covers_to),
                "txn_id": txn_id or "unknown",
            },
        )

        return paid_premium_with_cover

    def settle_evening(
        self, day: date, gross_settlement_paise: dict[str, int], at: datetime
    ) -> tuple[PremiumPayment, ...]:
        """SPEC §9.7: evening settlement — gross-settle premiums at 21:00 simulated time.

        For each merchant, if their gross settlement (Σ sales that day) ≥ their day's premium,
        extend prepaid_through by one day and create a SETTLEMENT_DEDUCTION premium payment record.

        Args:
            day: The settlement date.
            gross_settlement_paise: Dict of merchant_id → total sales that day (paise).
            at: The settlement time.

        Returns:
            Tuple of PremiumPayment records created (may be empty).
        """
        created_premiums = []

        for merchant_id, sales_paise in gross_settlement_paise.items():
            # Get the merchant's cover
            cover = self.store.cover(merchant_id)
            if not cover or cover.prepaid_through is None:
                continue

            # Calculate tomorrow's premium
            # TODO: Get premium_per_day_paise from rules or premium.json
            premium_per_day = cover.premium_per_day_paise or 200  # Fallback

            # Check if settlement is enough
            if sales_paise >= premium_per_day:
                # Extend cover by one day
                new_prepaid = cover.prepaid_through + timedelta(days=1)
                new_cover = cover.model_copy(update={
                    "prepaid_through": new_prepaid,
                })
                self.store.put_cover(new_cover)

                # Create premium payment record (settlement deduction)
                premium_id = self.ids.next("premium")
                premium = PremiumPayment(
                    id=premium_id,
                    cover_id=cover.id,
                    merchant_id=merchant_id,
                    amount_paise=premium_per_day,
                    method=PremiumMethod.SETTLEMENT_DEDUCTION,
                    covers_from=cover.prepaid_through + timedelta(days=1),
                    covers_to=new_prepaid,
                    status=PremiumStatus.PAID,
                    link_id=None,
                    link_url=None,
                    source="settlement (simulated)",
                    created_at=at,
                    paid_at=at,
                )

                self.store.add_premium(premium)
                created_premiums.append(premium)

                # Audit
                self.audit.append(
                    at=at,
                    actor="system",
                    action="premium-settle",
                    subject_type="premium-payment",
                    subject_id=premium.id,
                    data={
                        "merchant_id": merchant_id,
                        "cover_id": cover.id,
                        "amount_paise": premium_per_day,
                        "gross_settlement_paise": sales_paise,
                        "extended_through": str(new_prepaid),
                    },
                )

        return tuple(created_premiums)
