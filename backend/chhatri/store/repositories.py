"""In-memory Store (SPEC §24.3, §10). Thread-safe, stores frozen models, satisfies Store + MessageLog + AuditSink protocols."""

from __future__ import annotations

import threading
from datetime import date

from chhatri.domain.models import (
    AreaTrigger,
    Case,
    Claim,
    Cover,
    CoverQuote,
    Decision,
    InstalmentPause,
    Message,
    Payout,
    PayoutStatus,
    PremiumPayment,
)
from chhatri.sim.types import City


class Store:
    """In-memory, thread-safe repository of domain objects. All models are frozen (immutable).

    Changes use replace_* (requires existing id) or add_* (rejects duplicates).
    """

    def __init__(self, city: City) -> None:
        self.city = city
        self._lock = threading.RLock()

        # Domains
        self._covers: dict[str, Cover] = {}  # by merchant_id
        self._claims: dict[str, Claim] = {}  # by claim_id
        self._decisions: dict[str, Decision] = {}  # by decision_id
        self._decisions_by_merchant: dict[str, list[str]] = {}  # merchant_id → [decision_id, ...]
        self._payouts: dict[str, Payout] = {}  # by payout_id
        self._payouts_by_decision: dict[str, str] = {}  # decision_id → payout_id
        self._pauses: dict[str, InstalmentPause] = {}  # by pause_id
        self._premiums: dict[str, PremiumPayment] = {}  # by premium_id
        self._premiums_by_link: dict[str, str] = {}  # link_id → premium_id
        self._quotes: dict[str, CoverQuote] = {}  # by quote_id
        self._cases: dict[str, Case] = {}  # by case_id
        self._cases_by_status: dict[str, list[str]] = {}  # status → [case_id, ...]
        self._messages: dict[str, list[str]] = {}  # merchant_id → [message_id, ...]
        self._message_by_id: dict[str, Message] = {}  # message_id → Message
        self._media: dict[str, tuple[bytes, str]] = {}  # media_id → (data, mime)
        self._triggers: dict[str, AreaTrigger] = {}  # trigger_id → AreaTrigger

    # Cover operations

    def cover(self, merchant_id: str) -> Cover | None:
        """Get cover for a merchant, or None."""
        with self._lock:
            return self._covers.get(merchant_id)

    def put_cover(self, cover: Cover) -> None:
        """Add or replace a cover."""
        with self._lock:
            self._covers[cover.merchant_id] = cover

    # Claim operations

    def add_claim(self, claim: Claim) -> None:
        """Add a claim. Raises ValueError if claim_id already exists."""
        with self._lock:
            if claim.id in self._claims:
                raise ValueError(f"Claim {claim.id} already exists")
            self._claims[claim.id] = claim

    def claim(self, claim_id: str) -> Claim:
        """Get a claim by id. Raises KeyError if not found."""
        with self._lock:
            return self._claims[claim_id]

    # Decision operations

    def add_decision(self, d: Decision) -> None:
        """Add a decision. Raises ValueError if decision_id already exists."""
        with self._lock:
            if d.id in self._decisions:
                raise ValueError(f"Decision {d.id} already exists")
            self._decisions[d.id] = d
            if d.merchant_id not in self._decisions_by_merchant:
                self._decisions_by_merchant[d.merchant_id] = []
            self._decisions_by_merchant[d.merchant_id].append(d.id)

    def decision(self, decision_id: str) -> Decision:
        """Get a decision by id. Raises KeyError if not found."""
        with self._lock:
            return self._decisions[decision_id]

    def decisions_for(self, merchant_id: str) -> tuple[Decision, ...]:
        """Get all decisions for a merchant, oldest first."""
        with self._lock:
            ids = self._decisions_by_merchant.get(merchant_id, [])
            return tuple(self._decisions[id] for id in ids)

    def latest_paid_decision(self, merchant_id: str) -> Decision | None:
        """Get the latest APPROVED decision with a CREDITED payout, or None."""
        with self._lock:
            decisions = self.decisions_for(merchant_id)
            for d in reversed(decisions):
                if d.outcome != "APPROVED":
                    continue
                payout = self._payouts_by_decision.get(d.id)
                if payout and self._payouts[payout].status == PayoutStatus.CREDITED:
                    return d
            return None

    # Payout operations

    def add_payout(self, p: Payout) -> None:
        """Add a payout. Raises ValueError if payout_id already exists."""
        with self._lock:
            if p.id in self._payouts:
                raise ValueError(f"Payout {p.id} already exists")
            self._payouts[p.id] = p
            if p.decision_id in self._payouts_by_decision:
                raise ValueError(f"Decision {p.decision_id} already has a payout")
            self._payouts_by_decision[p.decision_id] = p.id

    def replace_payout(self, p: Payout) -> None:
        """Replace an existing payout. Raises KeyError if not found."""
        with self._lock:
            if p.id not in self._payouts:
                raise KeyError(f"Payout {p.id} not found")
            self._payouts[p.id] = p
            # Payout-decision mapping should not change

    def payout_for_decision(self, decision_id: str) -> Payout | None:
        """Get payout for a decision, or None."""
        with self._lock:
            payout_id = self._payouts_by_decision.get(decision_id)
            if payout_id:
                return self._payouts.get(payout_id)
            return None

    def payouts(self, *, zone_id: str | None = None, day: date | None = None) -> tuple[Payout, ...]:
        """Get payouts, optionally filtered by zone_id and/or day."""
        with self._lock:
            result = list(self._payouts.values())

            if zone_id:
                # Filter by zone (via merchant lookup)
                zone_payouts = []
                for p in result:
                    try:
                        merchant = self.city.merchant(p.merchant_id)
                        if merchant.zone_id == zone_id:
                            zone_payouts.append(p)
                    except KeyError:
                        pass
                result = zone_payouts

            if day:
                # Filter by day (via decision lookup)
                day_payouts = []
                for p in result:
                    if p.decision_id in self._decisions:
                        decision = self._decisions[p.decision_id]
                        if decision.decided_at.date() == day:
                            day_payouts.append(p)
                result = day_payouts

            return tuple(result)

    def paid_last_365_days_paise(self, merchant_id: str, on: date) -> int:
        """SPEC §4.3: sum of PENDING+CREDITED payouts whose decision's claim event_date is in (on-365d, on]."""
        from datetime import timedelta

        with self._lock:
            start_date = on - timedelta(days=365)
            total = 0

            # Look at all payouts for this merchant
            for payout in self._payouts.values():
                if payout.merchant_id != merchant_id:
                    continue
                if payout.status not in (PayoutStatus.PENDING, PayoutStatus.CREDITED):
                    continue

                # Find the decision
                decision = self._decisions.get(payout.decision_id)
                if not decision:
                    continue

                # Find the claim
                claim = self._claims.get(decision.claim_id)
                if not claim:
                    continue

                # Check if event_date is in (start_date, on]
                if start_date < claim.event_date <= on:
                    total += payout.amount_paise

            return total

    # Instalment pause operations

    def add_pause(self, pause: InstalmentPause) -> None:
        """Add a pause. Raises ValueError if pause_id already exists."""
        with self._lock:
            if pause.id in self._pauses:
                raise ValueError(f"Pause {pause.id} already exists")
            self._pauses[pause.id] = pause

    def pauses(self, merchant_id: str | None = None) -> tuple[InstalmentPause, ...]:
        """Get pauses, optionally filtered by merchant_id."""
        with self._lock:
            result = list(self._pauses.values())
            if merchant_id:
                result = [p for p in result if p.merchant_id == merchant_id]
            return tuple(result)

    # Premium payment operations

    def add_premium(self, p: PremiumPayment) -> None:
        """Add a premium. Raises ValueError if premium_id already exists."""
        with self._lock:
            if p.id in self._premiums:
                raise ValueError(f"Premium {p.id} already exists")
            self._premiums[p.id] = p
            if p.link_id:
                self._premiums_by_link[p.link_id] = p.id

    def replace_premium(self, p: PremiumPayment) -> None:
        """Replace an existing premium. Raises KeyError if not found."""
        with self._lock:
            if p.id not in self._premiums:
                raise KeyError(f"Premium {p.id} not found")
            old = self._premiums[p.id]
            self._premiums[p.id] = p
            # Update link mapping
            if old.link_id and old.link_id in self._premiums_by_link:
                del self._premiums_by_link[old.link_id]
            if p.link_id:
                self._premiums_by_link[p.link_id] = p.id

    def premium_by_link(self, link_id: str) -> PremiumPayment | None:
        """Get premium by link_id, or None."""
        with self._lock:
            premium_id = self._premiums_by_link.get(link_id)
            if premium_id:
                return self._premiums.get(premium_id)
            return None

    # Quote operations

    def add_quote(self, q: CoverQuote) -> None:
        """Add a quote. Raises ValueError if quote_id already exists."""
        with self._lock:
            if q.id in self._quotes:
                raise ValueError(f"Quote {q.id} already exists")
            self._quotes[q.id] = q

    # Case operations

    def add_case(self, c: Case) -> None:
        """Add a case. Raises ValueError if case_id already exists."""
        with self._lock:
            if c.id in self._cases:
                raise ValueError(f"Case {c.id} already exists")
            self._cases[c.id] = c
            if c.status not in self._cases_by_status:
                self._cases_by_status[c.status] = []
            self._cases_by_status[c.status].append(c.id)

    def replace_case(self, c: Case) -> None:
        """Replace a case. Raises KeyError if not found."""
        with self._lock:
            if c.id not in self._cases:
                raise KeyError(f"Case {c.id} not found")
            old = self._cases[c.id]
            self._cases[c.id] = c
            # Update status mapping
            if old.status in self._cases_by_status and c.id in self._cases_by_status[old.status]:
                self._cases_by_status[old.status].remove(c.id)
            if c.status not in self._cases_by_status:
                self._cases_by_status[c.status] = []
            self._cases_by_status[c.status].append(c.id)

    def case(self, case_id: str) -> Case:
        """Get a case by id. Raises KeyError if not found."""
        with self._lock:
            return self._cases[case_id]

    def cases(self, status: str | None = None) -> tuple[Case, ...]:
        """Get all cases, optionally filtered by status."""
        with self._lock:
            if status:
                ids = self._cases_by_status.get(status, [])
                return tuple(self._cases[id] for id in ids)
            return tuple(self._cases.values())

    # Message operations

    def add_message(self, m: Message) -> None:
        """Add a message. Raises ValueError if message_id already exists."""
        with self._lock:
            if m.id in self._message_by_id:
                raise ValueError(f"Message {m.id} already exists")
            self._message_by_id[m.id] = m
            if m.merchant_id not in self._messages:
                self._messages[m.merchant_id] = []
            self._messages[m.merchant_id].append(m.id)

    def messages(self, merchant_id: str) -> tuple[Message, ...]:
        """Get all messages for a merchant."""
        with self._lock:
            ids = self._messages.get(merchant_id, [])
            return tuple(self._message_by_id[id] for id in ids)

    # Media operations

    def put_media(self, data: bytes, mime: str, media_id: str) -> None:
        """Store media (image/audio)."""
        with self._lock:
            self._media[media_id] = (data, mime)

    def media(self, media_id: str) -> tuple[bytes, str]:
        """Get media by id. Raises KeyError if not found."""
        with self._lock:
            return self._media[media_id]

    # Area trigger operations

    def area_trigger(self, trigger_id: str) -> AreaTrigger | None:
        """Get area trigger by id, or None."""
        with self._lock:
            return self._triggers.get(trigger_id)

    def add_trigger(self, t: AreaTrigger) -> None:
        """Add a trigger. Raises ValueError if trigger_id already exists."""
        with self._lock:
            if t.id in self._triggers:
                raise ValueError(f"Trigger {t.id} already exists")
            self._triggers[t.id] = t

    def triggers(self) -> tuple[AreaTrigger, ...]:
        """Get all triggers."""
        with self._lock:
            return tuple(self._triggers.values())
