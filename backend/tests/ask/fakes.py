"""Doubles for the Ask tests: a scripted chat model, a store, a claims port and a service factory."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from chhatri.ai.labels import AiProvider, FallbackReason
from chhatri.ask.service import AskService
from chhatri.audit.log import AuditLog
from chhatri.clock import ManualClock, at
from chhatri.conversation.ports import DisputeOutcome
from chhatri.domain.enums import CaseKind, CaseStatus, CoverQuoteOutcome, CoverStatus
from chhatri.domain.models import Case, Cover, CoverQuote, Decision, PremiumPayment
from chhatri.ids import IdFactory
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.chat_chain import ChatChain, ChatLink
from chhatri.policy.rules import default_rules
from tests.api.fake_services import DAY, area_decision
from tests.api.fakes import FakeCity

MERCHANT = "S-0142"
GEMINI_MODEL = "test-gemini"
SARVAM_MODEL = "sarvam-105b"
GOOD_REPLY: dict[str, Any] = {
    "can_answer": True,
    "answer_hi": "सालाना सीमा ₹30,000 है, किसी भी 365 दिन में सभी दावों को मिलाकर।",
    "answer_en": "The yearly limit is ₹30,000 across all claims in any rolling 365 days.",
    "clause_ids": ["C4.3"],
    "fact_keys": ["rules.annual_limit"],
}


class ScriptedChat:
    """A ChatModel that replays outcomes in order (a dict is a reply, an exception is raised) and records calls."""

    def __init__(self, *outcomes: dict[str, Any] | Exception) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[tuple[str, str]] = []

    async def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, schema_name: str
    ) -> dict[str, Any]:
        self.calls.append((system, user))
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return dict(outcome)


def chain_of(
    gemini: ScriptedChat | None = None, sarvam: ScriptedChat | None = None, *, gate: bool = True
) -> ChatChain:
    return ChatChain(
        links=(
            ChatLink(
                AiProvider.GEMINI,
                "gemini_chat",
                GEMINI_MODEL if gemini else None,
                gemini,
                None if gemini else FallbackReason.NO_KEY,
            ),
            ChatLink(
                AiProvider.SARVAM,
                "sarvam_chat",
                SARVAM_MODEL if sarvam else None,
                sarvam,
                None if sarvam else FallbackReason.NO_KEY,
            ),
        ),
        gate=lambda _component: gate,
    )


@dataclass
class FakeStore:
    cover_by_merchant: dict[str, Cover] = field(default_factory=dict)
    case_list: list[Case] = field(default_factory=list)
    decision_list: list[Decision] = field(default_factory=list)

    def cover(self, merchant_id: str) -> Cover | None:
        return self.cover_by_merchant.get(merchant_id)

    def cases(self, status: CaseStatus | None = None) -> tuple[Case, ...]:
        return tuple(c for c in self.case_list if status is None or c.status == status)

    def decisions_for(self, merchant_id: str) -> tuple[Decision, ...]:
        return tuple(d for d in self.decision_list if d.merchant_id == merchant_id)


@dataclass
class FakeClaims:
    paid: Decision | None = None
    silence: date | None = None
    disputes: list[str] = field(default_factory=list)
    quotes: int = 0
    store: FakeStore | None = None

    def latest_paid_decision(self, merchant_id: str) -> Decision | None:
        return self.paid

    def open_silence(self, merchant_id: str) -> date | None:
        return self.silence

    async def open_dispute(self, merchant_id: str, text: str) -> DisputeOutcome:
        if self.paid is None:
            return DisputeOutcome(None)
        self.disputes.append(merchant_id)
        case = Case(
            id="C-2291",
            kind=CaseKind.DISPUTE,
            merchant_id=merchant_id,
            decision_id=self.paid.id,
            status=CaseStatus.OPEN,
            opened_at=at(DAY, 17, 10),
            due_by=at(DAY, 17, 10) + timedelta(hours=24),
            summary_en="Dispute",
        )
        if self.store is not None:
            self.store.case_list.append(case)
        return DisputeOutcome(case)

    async def quote_cover(self, merchant_id: str) -> tuple[CoverQuote, PremiumPayment | None]:
        self.quotes += 1
        quote = CoverQuote(
            id="Q-000001",
            merchant_id=merchant_id,
            outcome=CoverQuoteOutcome.OK,
            requested_at=at(DAY, 17),
            starts_on=DAY + timedelta(days=7),
            premium_per_day_paise=1862,
            first_payment_paise=13034,
            days_prepaid=7,
            reason_en="ok",
            reason_hi="ठीक",
        )
        return quote, None

    async def unused_submit(self) -> None:  # pragma: no cover - the Ask service never files a claim
        raise AssertionError


def make_cover(status: CoverStatus = CoverStatus.ACTIVE) -> Cover:
    return Cover(
        id="CV-0142",
        merchant_id=MERCHANT,
        purchased_at=at(DAY - timedelta(days=30), 10),
        starts_on=DAY - timedelta(days=23),
        premium_per_day_paise=1862,
        prepaid_through=DAY + timedelta(days=5),
        status=status,
    )


@dataclass
class Rig:
    service: AskService
    store: FakeStore
    claims: FakeClaims
    audit: AuditLog
    clock: ManualClock
    ids: IdFactory
    gemini: ScriptedChat | None
    sarvam: ScriptedChat | None

    def entries(self, action: str) -> list[Any]:
        return [e for e in self.audit.entries() if e.action == action]


def make_rig(
    gemini: ScriptedChat | None = None,
    sarvam: ScriptedChat | None = None,
    *,
    gate: bool = True,
    decided_day: date = DAY,
    with_decision: bool = True,
    check_in_open: bool = False,
    forced: Callable[[], Sequence[str]] = tuple,
) -> Rig:
    store = FakeStore(cover_by_merchant={MERCHANT: make_cover()})
    decision = area_decision() if with_decision else None
    if decision is not None:
        decision = decision.model_copy(update={"decided_at": at(decided_day, 17)})
        store.decision_list.append(decision)
    claims = FakeClaims(paid=decision, store=store, silence=DAY if check_in_open else None)
    audit = AuditLog()
    clock = ManualClock(at(DAY, 17, 30))
    ids = IdFactory()
    service = AskService(
        city=FakeCity(),
        store=store,
        claims=claims,
        rules=default_rules(),
        chain=chain_of(gemini, sarvam, gate=gate),
        audit=audit,
        ids=ids,
        clock=clock,
        forced=forced,
    )
    return Rig(service, store, claims, audit, clock, ids, gemini, sarvam)


TIMEOUT = IntegrationError("gemini_chat", "request timed out")
