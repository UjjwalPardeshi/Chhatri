"""In-memory, thread-safe store of frozen domain models (SPEC §24.3).

Contract (SPEC §24.3): stores frozen models and returns them unchanged; `add_*` rejects a duplicate id
(ValueError), `replace_*` requires an existing id (KeyError), getters that return a model raise
KeyError for an unknown id, while `cover`, `payout_for_decision`, `premium_by_link` and
`area_trigger` return None. Listings keep insertion order (oldest first). One re-entrant lock guards
every read and write. The store is recreated on every scenario load (SPEC §3) and is seeded with the
City's pilot covers so `cover(merchant_id)` is the merchant's current cover from the start.

Documented interpretations:
- `payouts(day=...)` and `paid_last_365_days_paise` date a payout by its `created_at` in IST (the
  decision time); the 365-day window is (on − 365 days, on] and counts CREDITED and PENDING payouts.
- `latest_paid_decision` = the most recently added APPROVED decision whose payout is CREDITED.
- Extensions beyond §24.3 (used by ledger/replay): `payouts(merchant_id=...)`, `payout`, `covers`,
  `quote`, `premiums`, `claims` and `decisions` (the whole run, for the H8 ops counts), `claims_for`, `decisions_for_claim`,
  `paid_event_dates` (NOT_ALREADY_PAID facts) and the EDI holiday
  requests of X4 (`add_holiday_request`, `replace_holiday_request`, `holiday_requests`).
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from datetime import date, timedelta
from types import MappingProxyType
from typing import Final

from chhatri.clock import IST
from chhatri.domain.enums import CaseStatus, ClaimKind, DecisionOutcome, PayoutStatus, PreferredChannel
from chhatri.domain.models import (
    AreaTrigger,
    Case,
    Claim,
    Cover,
    CoverQuote,
    Decision,
    HolidayRequest,
    InstalmentPause,
    Message,
    Payout,
    PremiumPayment,
)
from chhatri.sim.types import City

ANNUAL_WINDOW: Final = timedelta(days=365)
COUNTED_STATUSES: Final = frozenset({PayoutStatus.PENDING, PayoutStatus.CREDITED})


def _insert[T](table: dict[str, T], key: str, value: T, kind: str) -> None:
    if key in table:
        raise ValueError(f"{kind} {key} already exists")
    table[key] = value


def _get[T](table: Mapping[str, T], key: str, kind: str) -> T:
    try:
        return table[key]
    except KeyError:
        raise KeyError(f"unknown {kind} {key}") from None


def _matches(p: Payout, zone_id: str | None, day: date | None, city: City) -> bool:
    in_zone = zone_id is None or city.merchant(p.merchant_id).zone_id == zone_id
    return in_zone and (day is None or p.created_at.astimezone(IST).date() == day)


class Store:
    """Repository for one scenario run (SPEC §24.3); satisfies `store.protocols.MessageLog`."""

    def __init__(self, city: City) -> None:
        self.city = city
        self._lock = threading.RLock()
        self._covers: dict[str, Cover] = dict(city.covers)
        self._claims: dict[str, Claim] = {}
        self._decisions: dict[str, Decision] = {}
        self._payouts: dict[str, Payout] = {}
        self._payout_by_decision: dict[str, str] = {}
        self._payout_ids_by_merchant: dict[str, list[str]] = {}
        self._pauses: dict[str, InstalmentPause] = {}
        self._holiday_requests: dict[str, HolidayRequest] = {}
        self._premiums: dict[str, PremiumPayment] = {}
        self._premium_by_link: dict[str, str] = {}
        self._quotes: dict[str, CoverQuote] = {}
        self._cases: dict[str, Case] = {}
        self._messages: dict[str, Message] = {}
        self._media: dict[str, tuple[bytes, str]] = {}
        self._triggers: dict[str, AreaTrigger] = {}
        self._channels: dict[str, PreferredChannel] = {}

    def _select[T](self, table: Mapping[str, T], keep: Callable[[T], bool] | None = None) -> tuple[T, ...]:
        with self._lock:
            return tuple(v for v in table.values() if keep is None or keep(v))

    # covers ----------------------------------------------------------------------------------
    def cover(self, merchant_id: str) -> Cover | None:
        with self._lock:
            return self._covers.get(merchant_id)

    def put_cover(self, cover: Cover) -> None:
        """Add or replace the merchant's current cover (the merchant must exist in the City)."""
        self.city.merchant(cover.merchant_id)
        with self._lock:
            self._covers[cover.merchant_id] = cover

    def covers(self) -> Mapping[str, Cover]:
        """Snapshot of current covers by merchant id (read-only)."""
        with self._lock:
            return MappingProxyType(dict(self._covers))

    # claims + decisions ----------------------------------------------------------------------
    def add_claim(self, claim: Claim) -> None:
        with self._lock:
            _insert(self._claims, claim.id, claim, "claim")

    def claim(self, claim_id: str) -> Claim:
        with self._lock:
            return _get(self._claims, claim_id, "claim")

    def add_decision(self, d: Decision) -> None:
        with self._lock:
            _insert(self._decisions, d.id, d, "decision")

    def decision(self, decision_id: str) -> Decision:
        with self._lock:
            return _get(self._decisions, decision_id, "decision")

    def claims(self) -> tuple[Claim, ...]:
        """Every claim of the run, oldest first (read-only; the ops summary counts them, H8)."""
        return self._select(self._claims)

    def claims_for(self, merchant_id: str) -> tuple[Claim, ...]:
        """A merchant's claims, oldest first (the tracker, K5)."""
        return self._select(self._claims, lambda c: c.merchant_id == merchant_id)

    def decisions(self) -> tuple[Decision, ...]:
        """Every decision of the run in the order it was made, officer decisions after the ones they supersede."""
        return self._select(self._decisions)

    def decisions_for(self, merchant_id: str) -> tuple[Decision, ...]:
        """Decisions for a merchant, oldest first."""
        return self._select(self._decisions, lambda d: d.merchant_id == merchant_id)

    def decisions_for_claim(self, claim_id: str) -> tuple[Decision, ...]:
        return self._select(self._decisions, lambda d: d.claim_id == claim_id)

    def latest_paid_decision(self, merchant_id: str) -> Decision | None:
        """Latest APPROVED decision whose payout is CREDITED (SPEC §24.3)."""
        with self._lock:
            for d in reversed(self.decisions_for(merchant_id)):
                payout = self.payout_for_decision(d.id)
                if (
                    d.outcome is DecisionOutcome.APPROVED
                    and payout
                    and payout.status is PayoutStatus.CREDITED
                ):
                    return d
            return None

    def latest_final_decision(self, merchant_id: str) -> Decision | None:
        """Latest decision that settled a claim: DECLINED, or APPROVED with its payout CREDITED (what a dispute is about).

        A REFERRED decision is still open and an approved one whose money has not landed is not settled, so
        neither can be disputed yet (K5).
        """
        with self._lock:
            for d in reversed(self.decisions_for(merchant_id)):
                if d.outcome is DecisionOutcome.DECLINED:
                    return d
                payout = self.payout_for_decision(d.id)
                if (
                    d.outcome is DecisionOutcome.APPROVED
                    and payout
                    and payout.status is PayoutStatus.CREDITED
                ):
                    return d
            return None

    # payouts ---------------------------------------------------------------------------------
    def add_payout(self, p: Payout) -> None:
        """Add a payout for a City merchant; one payout per decision."""
        self.city.merchant(p.merchant_id)
        with self._lock:
            if p.decision_id in self._payout_by_decision:
                raise ValueError(f"decision {p.decision_id} already has a payout")
            _insert(self._payouts, p.id, p, "payout")
            self._payout_by_decision[p.decision_id] = p.id
            self._payout_ids_by_merchant.setdefault(p.merchant_id, []).append(p.id)

    def replace_payout(self, p: Payout) -> None:
        with self._lock:
            old = _get(self._payouts, p.id, "payout")
            if old.decision_id != p.decision_id or old.merchant_id != p.merchant_id:
                raise ValueError(f"payout {p.id} cannot move to another decision or merchant")
            self._payouts[p.id] = p

    def payout(self, payout_id: str) -> Payout:
        with self._lock:
            return _get(self._payouts, payout_id, "payout")

    def payout_for_decision(self, decision_id: str) -> Payout | None:
        with self._lock:
            payout_id = self._payout_by_decision.get(decision_id)
            return self._payouts[payout_id] if payout_id is not None else None

    def payouts(
        self, *, zone_id: str | None = None, day: date | None = None, merchant_id: str | None = None
    ) -> tuple[Payout, ...]:
        """Payouts in creation order, filtered by merchant zone, IST creation day and/or merchant."""
        if merchant_id is not None:
            return tuple(
                p for p in self._merchant_payouts(merchant_id) if _matches(p, zone_id, day, self.city)
            )
        return self._select(self._payouts, lambda p: _matches(p, zone_id, day, self.city))

    def _merchant_payouts(self, merchant_id: str) -> tuple[Payout, ...]:
        with self._lock:
            return tuple(self._payouts[pid] for pid in self._payout_ids_by_merchant.get(merchant_id, ()))

    def paid_last_365_days_paise(self, merchant_id: str, on: date) -> int:
        """Σ CREDITED + PENDING payouts created in (on − 365 days, on] (SPEC §9.1 rolling limit)."""
        start = on - ANNUAL_WINDOW
        return sum(
            p.amount_paise
            for p in self._merchant_payouts(merchant_id)
            if p.status in COUNTED_STATUSES and start < p.created_at.astimezone(IST).date() <= on
        )

    def paid_event_dates(self, merchant_id: str, kind: ClaimKind) -> tuple[date, ...]:
        """Days already paid for (merchant, kind): area event dates / personal silent dates (§9.2)."""
        with self._lock:
            days: set[date] = set()
            for d in self.decisions_for(merchant_id):
                payout = self.payout_for_decision(d.id)
                claim = self._claims.get(d.claim_id)
                if payout is None or payout.status not in COUNTED_STATUSES or claim is None:
                    continue
                if claim.kind == kind:
                    days.update(claim.silent_dates if kind == ClaimKind.PERSONAL else (claim.event_date,))
            return tuple(sorted(days))

    # instalment pauses -----------------------------------------------------------------------
    def add_pause(self, pause: InstalmentPause) -> None:
        with self._lock:
            _insert(self._pauses, pause.id, pause, "pause")

    def pauses(self, merchant_id: str | None = None) -> tuple[InstalmentPause, ...]:
        return self._select(self._pauses, lambda p: merchant_id is None or p.merchant_id == merchant_id)

    # EDI holiday requests (X4) ---------------------------------------------------------------
    def add_holiday_request(self, request: HolidayRequest) -> None:
        with self._lock:
            _insert(self._holiday_requests, request.id, request, "holiday request")

    def replace_holiday_request(self, request: HolidayRequest) -> None:
        """Move a request on to its decision; the loan, the instalment and the merchant never change."""
        with self._lock:
            old = _get(self._holiday_requests, request.id, "holiday request")
            if (old.merchant_id, old.loan_id, old.instalment_date) != (
                request.merchant_id,
                request.loan_id,
                request.instalment_date,
            ):
                raise ValueError(
                    f"holiday request {request.id} cannot change its merchant, loan or instalment"
                )
            self._holiday_requests[request.id] = request

    def holiday_requests(self, merchant_id: str | None = None) -> tuple[HolidayRequest, ...]:
        """Every request, whatever its outcome, oldest first (``pauses`` holds the grants only)."""
        return self._select(
            self._holiday_requests, lambda r: merchant_id is None or r.merchant_id == merchant_id
        )

    # premiums + quotes -----------------------------------------------------------------------
    def add_premium(self, p: PremiumPayment) -> None:
        with self._lock:
            if p.link_id is not None and p.link_id in self._premium_by_link:
                raise ValueError(f"payment link {p.link_id} already recorded")
            _insert(self._premiums, p.id, p, "premium")
            if p.link_id is not None:
                self._premium_by_link[p.link_id] = p.id

    def replace_premium(self, p: PremiumPayment) -> None:
        with self._lock:
            old = _get(self._premiums, p.id, "premium")
            if old.link_id != p.link_id or old.merchant_id != p.merchant_id:
                raise ValueError(f"premium {p.id} cannot change its link or merchant")
            self._premiums[p.id] = p

    def premium_by_link(self, link_id: str) -> PremiumPayment | None:
        with self._lock:
            premium_id = self._premium_by_link.get(link_id)
            return self._premiums[premium_id] if premium_id is not None else None

    def premiums(self, merchant_id: str | None = None) -> tuple[PremiumPayment, ...]:
        return self._select(self._premiums, lambda p: merchant_id is None or p.merchant_id == merchant_id)

    def add_quote(self, q: CoverQuote) -> None:
        with self._lock:
            _insert(self._quotes, q.id, q, "quote")

    def quote(self, quote_id: str) -> CoverQuote:
        with self._lock:
            return _get(self._quotes, quote_id, "quote")

    # cases -----------------------------------------------------------------------------------
    def add_case(self, c: Case) -> None:
        with self._lock:
            _insert(self._cases, c.id, c, "case")

    def replace_case(self, c: Case) -> None:
        with self._lock:
            old = _get(self._cases, c.id, "case")
            if old.merchant_id != c.merchant_id or old.kind is not c.kind:
                raise ValueError(f"case {c.id} cannot change its merchant or kind")
            self._cases[c.id] = c

    def case(self, case_id: str) -> Case:
        with self._lock:
            return _get(self._cases, case_id, "case")

    def cases(self, status: CaseStatus | None = None) -> tuple[Case, ...]:
        return self._select(self._cases, lambda c: status is None or c.status == status)

    # preferred channel (Telegram channel): a per-run choice on top of the merchant's default ------
    def preferred_channel(self, merchant_id: str) -> PreferredChannel:
        """Where this merchant's notifications go: the choice made in this run, else the merchant's own default."""
        with self._lock:
            return self._channels.get(merchant_id) or self.city.merchant(merchant_id).preferred_channel

    def set_preferred_channel(self, merchant_id: str, channel: PreferredChannel) -> None:
        """Choose the channel for `merchant_id` (KeyError for an unknown merchant); recreated with the store on a load."""
        self.city.merchant(merchant_id)
        with self._lock:
            self._channels[merchant_id] = PreferredChannel(channel)

    # messages + media ------------------------------------------------------------------------
    def add_message(self, m: Message) -> None:
        with self._lock:
            _insert(self._messages, m.id, m, "message")

    def messages(self, merchant_id: str) -> tuple[Message, ...]:
        return self._select(self._messages, lambda m: m.merchant_id == merchant_id)

    def put_media(self, data: bytes, mime: str, media_id: str) -> None:
        """Store bytes once per id; re-putting identical content is a no-op, different content fails."""
        if not data or not mime.strip() or not media_id.strip():
            raise ValueError("media needs non-empty bytes, mime type and id")
        with self._lock:
            existing = self._media.get(media_id)
            if existing is not None and existing != (data, mime):
                raise ValueError(f"media {media_id} already stored with different content")
            self._media[media_id] = (bytes(data), mime)

    def media(self, media_id: str) -> tuple[bytes, str]:
        with self._lock:
            return _get(self._media, media_id, "media")

    # erase (N6/H23): a merchant's "forget my slip" replaces records with erased copies; nothing else edits them ----
    def replace_claim(self, c: Claim) -> None:
        with self._lock:
            _get(self._claims, c.id, "claim")
            self._claims[c.id] = c

    def replace_decision(self, d: Decision) -> None:
        with self._lock:
            _get(self._decisions, d.id, "decision")
            self._decisions[d.id] = d

    def replace_message(self, m: Message) -> None:
        with self._lock:
            _get(self._messages, m.id, "message")
            self._messages[m.id] = m

    def delete_media(self, media_id: str) -> bool:
        """Remove stored bytes; True when there were any (the id then answers KeyError like an unknown one)."""
        with self._lock:
            return self._media.pop(media_id, None) is not None

    # area triggers ---------------------------------------------------------------------------
    def area_trigger(self, trigger_id: str) -> AreaTrigger | None:
        with self._lock:
            return self._triggers.get(trigger_id)

    def add_trigger(self, t: AreaTrigger) -> None:
        with self._lock:
            _insert(self._triggers, t.id, t, "trigger")

    def triggers(self) -> tuple[AreaTrigger, ...]:
        return self._select(self._triggers)
