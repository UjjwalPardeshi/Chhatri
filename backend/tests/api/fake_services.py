"""Fake runtime services for API tests: store, audit, engine, orchestrator, conversation, channel.

They implement exactly the SPEC §24.3–§24.6 members the API calls (``chhatri.api.ports``) and record
every call so tests can assert what the HTTP layer asked for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from chhatri.clock import IST, at
from chhatri.domain.enums import (
    CaseKind,
    CaseStatus,
    Channel,
    CheckCode,
    CheckStatus,
    CoverQuoteOutcome,
    DecisionOutcome,
    Direction,
    MessageKind,
    PayoutStatus,
    PremiumMethod,
    PremiumStatus,
    Severity,
)
from chhatri.domain.models import (
    AuditEntry,
    Case,
    CheckResult,
    CoverQuote,
    Decision,
    Explanation,
    Message,
    Payout,
    PremiumPayment,
)
from chhatri.integrations.base import DeliveryReceipt, InboundMedia, IntegrationError, OutboundMessage
from tests.api.canned import sha

DAY = date(2025, 8, 19)
SIM_LINK = "https://paytm.me/sim-000001"


def area_decision(decision_id: str = "D-000001", merchant_id: str = "S-0142") -> Decision:
    explanation = Explanation(
        weekday_en="Tuesday",
        weekday_hi="मंगलवार",
        expected_day_paise=438_000,
        drop_pct=63,
        share_pct=50,
        days=1,
        cap_paise=250_000,
        capped=False,
        amount_paise=138_000,
        formula_en="50% × ₹4,380 × 63% = ₹1,379.70 → ₹1,380",
        formula_hi="50% × ₹4,380 × 63% = ₹1,380",
    )
    check = CheckResult(
        code=CheckCode.COVER_IN_FORCE,
        status=CheckStatus.PASS,
        severity=Severity.HARD,
        label_en="Cover active",
        detail_en="Prepaid through 2025-08-19",
        observed="ACTIVE",
        required="ACTIVE",
    )
    return Decision(
        id=decision_id,
        claim_id="CL-000001",
        merchant_id=merchant_id,
        outcome=DecisionOutcome.APPROVED,
        amount_paise=138_000,
        checks=(check,),
        rules_version="2025.08-pilot",
        decided_at=at(DAY, 17),
        decided_by="policy-engine",
        explanation=explanation,
    )


def payout(payout_id: str = "P-000001", merchant_id: str = "S-0142") -> Payout:
    return Payout(
        id=payout_id,
        decision_id="D-000001",
        merchant_id=merchant_id,
        amount_paise=138_000,
        status=PayoutStatus.CREDITED,
        rail="settlement (simulated)",
        created_at=at(DAY, 17),
        credited_at=at(DAY, 17, 4),
        reference="SIM-UTR-000001",
    )


def dispute_case(case_id: str = "C-2291") -> Case:
    return Case(
        id=case_id,
        kind=CaseKind.DISPUTE,
        merchant_id="S-0142",
        decision_id="D-000001",
        status=CaseStatus.OPEN,
        opened_at=at(DAY, 17, 12),
        due_by=at(DAY, 17, 12) + timedelta(hours=24),
        summary_en="Anil says his loss was bigger than ₹1,380.",
        evidence={"merchant_text": "मेरा नुकसान ज़्यादा हुआ।", "silent_days": []},
    )


@dataclass
class FakeStore:
    """In-memory records with the §24.3 read API the routes use."""

    zone_of: dict[str, str]
    cases_by_id: dict[str, Case] = field(default_factory=dict)
    decisions_by_id: dict[str, Decision] = field(default_factory=dict)
    payout_list: list[Payout] = field(default_factory=list)
    message_log: dict[str, list[Message]] = field(default_factory=dict)
    media_by_id: dict[str, tuple[bytes, str]] = field(default_factory=dict)

    def case(self, case_id: str) -> Case:
        return self.cases_by_id[case_id]

    def cases(self, status: CaseStatus | None = None) -> tuple[Case, ...]:
        return tuple(c for c in self.cases_by_id.values() if status is None or c.status == status)

    def replace_case(self, case: Case) -> None:
        self.cases_by_id[case.id] = case

    def decision(self, decision_id: str) -> Decision:
        return self.decisions_by_id[decision_id]

    def payouts(self, *, zone_id: str | None = None, day: date | None = None) -> tuple[Payout, ...]:
        return tuple(
            p
            for p in self.payout_list
            if (zone_id is None or self.zone_of[p.merchant_id] == zone_id)
            and (day is None or p.created_at.date() == day)
        )

    def add_message(self, message: Message) -> None:
        self.message_log.setdefault(message.merchant_id, []).append(message)

    def messages(self, merchant_id: str) -> tuple[Message, ...]:
        return tuple(self.message_log.get(merchant_id, ()))

    def put_media(self, data: bytes, mime: str, media_id: str) -> None:
        self.media_by_id[media_id] = (data, mime)

    def media(self, media_id: str) -> tuple[bytes, str]:
        return self.media_by_id[media_id]


class FakeAudit:
    def __init__(self, count: int = 3) -> None:
        self._entries = tuple(
            AuditEntry(
                seq=seq,
                at=at(DAY, 17, seq),
                recorded_at=datetime(2026, 9, 30, 10, seq, tzinfo=IST),
                actor="policy-engine",
                action="decision",
                subject_type="decision",
                subject_id=f"D-{seq:06d}",
                data={"outcome": "APPROVED"},
                prev_hash=sha(str(seq - 1)),
                hash=sha(str(seq)),
            )
            for seq in range(1, count + 1)
        )

    def entries(self, *, after: int = 0, limit: int = 200) -> tuple[AuditEntry, ...]:
        return tuple(e for e in self._entries if e.seq > after)[:limit]

    def verify(self) -> dict[str, Any]:
        head = self._entries[-1].hash if self._entries else "0" * 64
        return {"valid": True, "entries": len(self._entries), "head_hash": head, "first_bad_seq": None}

    def __len__(self) -> int:
        return len(self._entries)


@dataclass
class FakeEngine:
    """Replay engine double: ``seek`` backwards asks the state to reload, as SPEC §17.1 says."""

    runtime: Any
    state: Any
    running: bool = False
    speed: float = 6.0
    calls: list[tuple[str, Any]] = field(default_factory=list)

    async def play(self, speed: float | None = None) -> None:
        self.calls.append(("play", speed))
        self.running, self.speed = True, speed if speed is not None else self.speed

    async def pause(self) -> None:
        self.calls.append(("pause", None))
        self.running = False

    async def step(self, minutes: int) -> None:
        self.calls.append(("step", minutes))
        target = self.runtime.clock.now() + timedelta(minutes=minutes)
        if target > self.runtime.scenario.end:
            raise ValueError("beyond the scenario end")
        self.runtime.clock.set(target)

    async def seek(self, hhmm: str) -> None:
        self.calls.append(("seek", hhmm))
        hours, minutes = (int(part) for part in hhmm.split(":"))
        target = at(self.runtime.scenario.day, hours, minutes)
        if not self.runtime.scenario.start <= target <= self.runtime.scenario.end:
            raise ValueError("outside the scenario")
        runtime = self.runtime
        if target < runtime.clock.now():
            runtime = await self.state.load(runtime.scenario.name)
        runtime.clock.set(target)


@dataclass
class FakeOrchestrator:
    runtime: Any
    fail_links: bool = False
    calls: list[tuple[str, Any]] = field(default_factory=list)
    done_steps: set[tuple[str, str]] = field(default_factory=set)

    async def officer_decide(self, case_id: str, *, approve: bool, officer_id: str, note: str) -> Decision:
        self.calls.append(("officer_decide", (case_id, approve, officer_id, note)))
        store = self.runtime.store
        case = store.case(case_id)
        if case.status != CaseStatus.OPEN:
            raise ValueError("case already resolved")
        decision = area_decision(self.runtime.ids.next("decision")).model_copy(
            update={
                "outcome": DecisionOutcome.APPROVED if approve else DecisionOutcome.DECLINED,
                "decided_by": officer_id,
                "supersedes": case.decision_id,
                "amount_paise": 138_000 if approve else 0,
                "explanation": None,
            }
        )
        store.decisions_by_id[decision.id] = decision
        status = CaseStatus.APPROVED if approve else CaseStatus.DECLINED
        store.replace_case(
            case.model_copy(
                update={
                    "status": status,
                    "resolution": note or status.value,
                    "resolved_by": officer_id,
                    "resolved_at": self.runtime.clock.now(),
                }
            )
        )
        return decision

    async def paytm_paid(self, link_id: str, txn_id: str | None) -> PremiumPayment:
        self.calls.append(("paytm_paid", (link_id, txn_id)))
        if link_id != "sim-000001":
            raise KeyError(link_id)
        return premium(PremiumStatus.PAID)

    async def handle_callback(self, run_id: str, workflow: str, step: str, payload: Any) -> dict[str, Any]:
        self.calls.append(("handle_callback", (run_id, workflow, step, dict(payload))))
        if payload.get("decision_id") == "D-999999":
            raise KeyError("D-999999")
        if workflow == "human-review" and step == "execute_payout":
            raise ValueError("execute_payout is not a human-review step")
        key = (run_id, step)
        status = "skipped" if key in self.done_steps else "done"
        self.done_steps.add(key)
        return {"step": step, "status": status}

    async def quote_cover(self, merchant_id: str) -> tuple[CoverQuote, PremiumPayment | None]:
        self.calls.append(("quote_cover", merchant_id))
        if self.fail_links:
            raise IntegrationError("paytm", "link service timed out")
        quote = CoverQuote(
            id="Q-000001",
            merchant_id=merchant_id,
            outcome=CoverQuoteOutcome.BLOCKED,
            requested_at=at(date(2025, 8, 18), 18, 10),
            starts_on=date(2025, 8, 25),
            premium_per_day_paise=180,
            first_payment_paise=5_400,
            days_prepaid=30,
            reason_en="New cover starts after the waiting period",
            reason_hi="नया कवर वेटिंग पीरियड के बाद शुरू होता है",
            blocking_alert_id="A-20250818-01",
        )
        return quote, premium(PremiumStatus.PENDING)


def premium(status: PremiumStatus) -> PremiumPayment:
    return PremiumPayment(
        id="PR-000001",
        cover_id=None,
        merchant_id="S-0907",
        amount_paise=5_400,
        method=PremiumMethod.PAYMENT_LINK,
        covers_from=date(2025, 8, 25),
        covers_to=date(2025, 9, 23),
        status=status,
        link_id="sim-000001",
        link_url=SIM_LINK,
        source="simulated",
        created_at=at(date(2025, 8, 18), 18, 10),
        paid_at=at(date(2025, 8, 18), 18, 20) if status == PremiumStatus.PAID else None,
    )


@dataclass
class FakeConversation:
    """Records inbound calls and answers like the real service: inbound message first, then a reply."""

    runtime: Any
    calls: list[tuple[str, Any]] = field(default_factory=list)

    def _message(self, merchant_id: str, direction: Direction, kind: MessageKind, **extra: Any) -> Message:
        message = Message(
            id=self.runtime.ids.next("message"),
            merchant_id=merchant_id,
            direction=direction,
            channel=Channel.SIMULATOR,
            kind=kind,
            created_at=self.runtime.clock.now(),
            **extra,
        )
        self.runtime.store.add_message(message)
        return message

    def _reply(self, merchant_id: str) -> Message:
        return self._message(
            merchant_id,
            Direction.OUTBOUND,
            MessageKind.TEXT,
            text_hi="आपका आम मंगलवार: ₹4,380।",
            text_en="Your usual Tuesday: ₹4,380.",
        )

    async def handle_text(self, merchant_id: str, text: str) -> tuple[Message, ...]:
        self.calls.append(("text", (merchant_id, text)))
        inbound = self._message(merchant_id, Direction.INBOUND, MessageKind.TEXT, text_en=text)
        return inbound, self._reply(merchant_id)

    async def handle_voice(
        self, merchant_id: str, audio: bytes, mime: str, *, transcript_hint: str | None = None
    ) -> tuple[Message, ...]:
        self.calls.append(("voice", (merchant_id, audio, mime, transcript_hint)))
        meta = {"transcript": transcript_hint or "", "voice_source": "browser-simulated"}
        inbound = self._message(
            merchant_id, Direction.INBOUND, MessageKind.VOICE, text_hi=transcript_hint, meta=meta
        )
        return inbound, self._reply(merchant_id)

    async def handle_image(
        self, merchant_id: str, image: bytes, mime: str, media_id: str
    ) -> tuple[Message, ...]:
        self.calls.append(("image", (merchant_id, image, mime, media_id)))
        self.runtime.store.put_media(image, mime, media_id)
        inbound = self._message(
            merchant_id, Direction.INBOUND, MessageKind.IMAGE, media_url=f"/api/media/{media_id}"
        )
        return inbound, self._reply(merchant_id)

    async def handle_choice(self, merchant_id: str, choice: Any) -> tuple[Message, ...]:
        """A tapped pre-check or doctor-question button (`conversation.pending.Choice`)."""
        self.calls.append(("choice", (merchant_id, choice)))
        inbound = self._message(merchant_id, Direction.INBOUND, MessageKind.TEXT, text_en=choice.answer)
        return inbound, self._reply(merchant_id)


@dataclass
class FakeChannel:
    """Live-WhatsApp-channel double with the inbound bookkeeping the webhook route relies on."""

    media: dict[str, InboundMedia] = field(default_factory=dict)
    seen: set[tuple[str, str]] = field(default_factory=set)
    notices: list[tuple[str, datetime]] = field(default_factory=list)
    sent: list[OutboundMessage] = field(default_factory=list)

    def accept_inbound(self, event: Any) -> bool:
        key = (event.message_id, getattr(event, "status", "message"))
        if key in self.seen:
            return False
        self.seen.add(key)
        return True

    async def send_demo_notice(self, phone: str, at_time: datetime) -> DeliveryReceipt | None:
        self.notices.append((phone, at_time))
        return DeliveryReceipt("wamid.notice", "whatsapp", True, "demo notice")

    async def send(self, message: OutboundMessage) -> DeliveryReceipt:
        self.sent.append(message)
        return DeliveryReceipt(None, "simulator", True)

    async def download_media(self, media_id: str) -> InboundMedia:
        if media_id not in self.media:
            raise IntegrationError("whatsapp", "media not found")
        return self.media[media_id]
