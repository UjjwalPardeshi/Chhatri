"""Harness for conversation tests: real Store, AuditLog, EventBus, IdFactory, simulated integrations and
a small ClaimsPort (``WorldClaims``) that decides with the real policy engine, ledger and cases, so the
SPEC §13.6 live tests run end to end at service level without a trained model.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from types import MappingProxyType
from typing import Any

import pytest

from chhatri.audit.log import AuditLog
from chhatri.cases.service import CaseService
from chhatri.clock import ManualClock, ist
from chhatri.conversation.ports import DisputeOutcome
from chhatri.conversation.service import ConversationService
from chhatri.domain.enums import (
    AlertKind,
    AlertLevel,
    CaseKind,
    CaseStatus,
    Channel,
    ClaimKind,
    DecisionOutcome,
    Language,
    ShopType,
)
from chhatri.domain.models import (
    Alert,
    AreaTrigger,
    Claim,
    Cover,
    CoverQuote,
    Decision,
    Loan,
    Merchant,
    Payout,
    PremiumPayment,
    SlipExtraction,
)
from chhatri.events import Event, EventBus
from chhatri.ids import IdFactory
from chhatri.integrations.base import (
    DeliveryReceipt,
    InboundMedia,
    IntegrationError,
    OutboundMessage,
    SynthesizedAudio,
)
from chhatri.integrations.paytm_sim import SimulatedPaytmLinks
from chhatri.integrations.sarvam_sim import SimulatedSlipReader, SimulatedSTT, SimulatedTTS
from chhatri.integrations.soundbox import SimulatedSoundbox
from chhatri.integrations.whatsapp_sim import SimulatorChannel
from chhatri.ledger.payouts import PayoutService
from chhatri.ledger.premiums import PremiumService
from chhatri.policy.engine import evaluate_area_claim, evaluate_cover_purchase, evaluate_personal_claim
from chhatri.policy.facts import AreaClaimFacts, PersonalClaimFacts
from chhatri.policy.rules import PolicyRules, default_rules
from chhatri.sim.city import ANIL, RAMESH
from chhatri.sim.merchants import cover_for, loan_for, phone_for
from chhatri.store.repositories import Store

RULES = default_rules()
MONSOON_DAY = date(2025, 8, 19)  # Tue (SPEC §17.2)
ILLNESS_DAY = date(2025, 8, 21)  # Thu; Anil silent all of Wed 2025-08-20
SILENT_DAY = date(2025, 8, 20)
EXPECTED_DAY_PAISE = 438_000  # published "usual Tuesday" ₹4,380 (SPEC §4.3)
PREMIUM_PER_DAY_PAISE = 200
SUNITA = Merchant(
    id="S-0150",
    shop_name="Sunita Kirana",
    owner_name="Sunita Shinde",
    owner_name_hi="सुनीता",
    kyc_name="SUNITA RAJU SHINDE",
    phone=phone_for(150),
    language=Language.HI,
    zone_id="Z7",
    lat=19.005,
    lng=72.843,
    h3_cell="",
    shop_type=ShopType.KIRANA,
    weekly_off=None,
    is_demo=False,
)
ANIL_COVER = cover_for(142, date(2025, 3, 10), 11, RULES)
SUNITA_COVER = cover_for(150, date(2025, 3, 10), 11, RULES)
ANIL_LOAN = loan_for(142, 60_000, 120)
RED_ALERT = Alert(
    id="A-20250818-01",
    kind=AlertKind.RAIN,
    level=AlertLevel.RED,
    zone_ids=("Z3", "Z7", "Z12"),
    issued_at=ist(2025, 8, 18, 17, 30),
    valid_from=ist(2025, 8, 19, 14),
    valid_to=ist(2025, 8, 19, 20),
    source="IMD (simulated)",
    headline_en="Red alert: extremely heavy rain",
    headline_hi="रेड अलर्ट: बहुत भारी बारिश",
)


def z7_trigger(drop_pct: int = 63) -> AreaTrigger:
    return AreaTrigger(
        id="E-Z7-20250819",
        zone_id="Z7",
        alert_id=RED_ALERT.id,
        window_start=ist(2025, 8, 19, 14),
        window_end=ist(2025, 8, 19, 17),
        index_pct=100 - drop_pct,
        drop_pct=drop_pct,
        hourly_index_pct=(36, 37, 38),
        lower_bound_pct=72,
        shops_in_index=46,
        fired_at=ist(2025, 8, 19, 17),
    )


@dataclass(frozen=True)
class MiniCity:
    """The slice of ``sim.types.City`` that Store, ledger, cases and the conversation read."""

    merchants: tuple[Merchant, ...] = (ANIL, RAMESH, SUNITA)
    covers: Mapping[str, Cover] = field(
        default_factory=lambda: MappingProxyType({ANIL.id: ANIL_COVER, SUNITA.id: SUNITA_COVER})
    )
    loans: Mapping[str, Loan] = field(default_factory=lambda: MappingProxyType({ANIL.id: ANIL_LOAN}))

    def merchant(self, merchant_id: str) -> Merchant:
        for merchant in self.merchants:
            if merchant.id == merchant_id:
                return merchant
        raise KeyError(f"unknown merchant {merchant_id}")


class AudioTTS:
    """TextToSpeech returning real-looking audio (as live Sarvam does), or failing."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, Language, bool]] = []

    async def synthesize(
        self, text: str, language: Language, *, for_whatsapp: bool = False
    ) -> SynthesizedAudio:
        self.calls.append((text, language, for_whatsapp))
        if self.fail:
            raise IntegrationError("sarvam_tts", "service unavailable", retryable=True)
        mime = "audio/ogg" if for_whatsapp else "audio/mpeg"
        return SynthesizedAudio(audio=b"AUDIO:" + text.encode(), mime_type=mime, source="sarvam:bulbul:v3")


class FailingChannel:
    """MessagingChannel whose provider is down."""

    def __init__(self) -> None:
        self.sent: list[OutboundMessage] = []

    async def send(self, message: OutboundMessage) -> DeliveryReceipt:
        self.sent.append(message)
        raise IntegrationError("whatsapp", "graph API 503", retryable=True)

    async def download_media(self, media_id: str) -> InboundMedia:
        raise IntegrationError("whatsapp", "no media")


class WorldClaims:
    """ClaimsPort (SPEC §24.4) over the real policy engine, PayoutService, CaseService and PremiumService."""

    def __init__(
        self, *, store: Store, audit: AuditLog, ids: IdFactory, clock: ManualClock, rules: PolicyRules
    ):
        self.store, self.ids, self.clock, self.rules = store, ids, clock, rules
        self.payouts = PayoutService(store, audit, ids, rules)
        self.cases = CaseService(store, audit, ids, rules)
        links = SimulatedPaytmLinks(clock=clock.now)
        self.premiums = PremiumService(store, audit, ids, rules, links, premiums={})
        self.silence: date | None = None
        self.alerts: tuple[Alert, ...] = (RED_ALERT,)
        self.link_fails = False
        self.open_case_on_referral = True
        self.submitted: list[tuple[str, SlipExtraction, str]] = []

    async def submit_personal_claim(self, merchant_id: str, slip: SlipExtraction, media_id: str) -> Decision:
        self.submitted.append((merchant_id, slip, media_id))
        if self.silence is None:
            raise AssertionError("the conversation filed a claim without an open silence")
        merchant, now, day = self.store.city.merchant(merchant_id), self.clock.now(), self.silence
        claim = Claim(
            id=self.ids.next("claim"),
            kind=ClaimKind.PERSONAL,
            merchant_id=merchant_id,
            created_at=now,
            event_date=day,
            silent_dates=(day,),
            slip=slip,
            slip_media_id=media_id,
            expected_day_paise=EXPECTED_DAY_PAISE,
        )
        facts = PersonalClaimFacts(
            claim=claim,
            merchant=merchant,
            cover=self.store.cover(merchant_id),
            verified_silent_dates=(day,),
            kyc_name=merchant.kyc_name,
            paid_last_365_days_paise=self.store.paid_last_365_days_paise(merchant_id, now.date()),
            already_paid_dates=(),
            weekday=day.weekday(),
        )
        decision = evaluate_personal_claim(facts, self.rules, decision_id=self.ids.next("decision"), now=now)
        self.store.add_claim(claim)
        self.store.add_decision(decision)
        if decision.outcome is DecisionOutcome.REFERRED and self.open_case_on_referral:
            self.cases.open(
                kind=CaseKind.PERSONAL_CLAIM_REVIEW,
                merchant_id=merchant_id,
                at=now,
                summary_en="Slip needs a claims officer",
                summary_hi=None,
                evidence={},
                claim_id=claim.id,
                decision_id=decision.id,
            )
        self.silence = None
        return decision

    async def open_dispute(self, merchant_id: str, text: str) -> DisputeOutcome:
        disputed = self.store.latest_final_decision(merchant_id)
        if disputed is None:
            return DisputeOutcome(case=None)
        open_case = next(
            (
                c
                for c in self.store.cases(CaseStatus.OPEN)
                if c.kind is CaseKind.DISPUTE and c.decision_id == disputed.id
            ),
            None,
        )
        if open_case is not None:
            return DisputeOutcome(case=open_case, already_open=True)
        case = self.cases.open(
            kind=CaseKind.DISPUTE,
            merchant_id=merchant_id,
            at=self.clock.now(),
            summary_en="Merchant disputes the payout",
            summary_hi=None,
            evidence={"merchant_text": text},
            claim_id=disputed.claim_id,
            decision_id=disputed.id,
        )
        return DisputeOutcome(case=case)

    async def quote_cover(self, merchant_id: str) -> tuple[CoverQuote, PremiumPayment | None]:
        merchant, now = self.store.city.merchant(merchant_id), self.clock.now()
        quote = evaluate_cover_purchase(
            merchant,
            self.store.cover(merchant_id),
            now=now,
            alerts=self.alerts,
            premium_per_day_paise=PREMIUM_PER_DAY_PAISE,
            rules=self.rules,
            quote_id=self.ids.next("quote"),
        )
        self.store.add_quote(quote)
        if self.link_fails:
            return quote, None
        return quote, await self.premiums.create_link(merchant, quote, now)

    def latest_paid_decision(self, merchant_id: str) -> Decision | None:
        return self.store.latest_paid_decision(merchant_id)

    def open_silence(self, merchant_id: str) -> date | None:
        return self.silence

    # ---- test helpers (what the orchestrator's workflow steps would do) ----

    def decide_area(self, merchant: Merchant, trigger: AreaTrigger) -> Decision:
        claim = Claim(
            id=self.ids.next("claim"),
            kind=ClaimKind.AREA,
            merchant_id=merchant.id,
            created_at=trigger.fired_at,
            event_date=trigger.fired_at.date(),
            trigger_id=trigger.id,
            expected_day_paise=EXPECTED_DAY_PAISE,
            drop_pct=trigger.drop_pct,
        )
        facts = AreaClaimFacts(
            claim=claim,
            merchant=merchant,
            cover=self.store.cover(merchant.id),
            trigger=trigger,
            alert=RED_ALERT,
            paid_last_365_days_paise=0,
            already_paid=False,
            weekday=claim.event_date.weekday(),
        )
        decision = evaluate_area_claim(
            facts, self.rules, decision_id=self.ids.next("decision"), now=trigger.fired_at
        )
        self.store.add_claim(claim)
        self.store.add_decision(decision)
        return decision

    def pay(self, decision: Decision) -> Payout:
        self.payouts.execute(decision)
        credit_at = decision.decided_at + timedelta(minutes=self.rules.payout_rail_delay_minutes)
        return self.payouts.credit(decision.id, credit_at)


@dataclass
class World:
    clock: ManualClock
    ids: IdFactory
    store: Store
    audit: AuditLog
    bus: EventBus
    channel: Any
    tts: Any
    claims: WorldClaims
    service: ConversationService
    city: MiniCity

    def events(self, type_: str) -> list[Event]:
        return [e for e in self.bus.history() if e.type == type_]

    def actions(self) -> list[str]:
        return [e.action for e in self.audit.entries(limit=5000)]

    def at(self, moment: datetime) -> None:
        self.clock.set(moment)


def make_world(
    *,
    start: datetime | None = None,
    channel: Any = None,
    tts: Any = None,
    channel_name: Channel = Channel.SIMULATOR,
    chat: Any = None,
) -> World:
    clock = ManualClock(start or ist(2025, 8, 19, 17, 0))
    ids, bus, audit, city = IdFactory(), EventBus(history_size=5000), AuditLog(), MiniCity()
    store = Store(city)  # type: ignore[arg-type]  # MiniCity is the City slice Store reads
    channel = channel if channel is not None else SimulatorChannel()
    tts = tts if tts is not None else SimulatedTTS()
    claims = WorldClaims(store=store, audit=audit, ids=ids, clock=clock, rules=RULES)
    service = ConversationService(
        city=city,
        store=store,
        audit=audit,
        ids=ids,
        clock=clock,
        bus=bus,
        channel=channel,
        stt=SimulatedSTT(),
        tts=tts,
        chat=chat,
        slips=SimulatedSlipReader(),
        soundbox=SimulatedSoundbox(tts),
        claims=claims,
        channel_name=channel_name,
    )
    return World(clock, ids, store, audit, bus, channel, tts, claims, service, city)


@pytest.fixture
def world() -> World:
    return make_world()
