"""AskService: one question in, one labelled, grounded answer out (fs-05 section 4; data-model 5.2).

The order is fixed: validate; voice chips (H18); scam check (H19); injection scan (H16); the word-list intent (a model
never chooses an intent, so one cannot open a case); a known intent is answered by the rules; only UNKNOWN text goes
down the model chain (Gemini, then Sarvam, then a template). Decoration is the server's: clause chips from the clause
table, facts from the fact sheet, the next action (H21) from the answer type, the H26 label from the chain. One
`ask.answered` audit entry holds ids, codes, counts and a hash of the answer, never the question or the answer text.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Final, Protocol

from chhatri.ai.labels import AiLabel, AiMode, AiProvider, FallbackReason
from chhatri.ask import next_action as next_actions
from chhatri.ask.answers import RuleAnswer, answer_intent
from chhatri.ask.clauses import clause_table
from chhatri.ask.copy import render_pair
from chhatri.ask.facts import Fact, FactSheet, build_fact_sheet
from chhatri.ask.injection import InjectionScan, scan_injection
from chhatri.ask.ledger import AskLedger, AskRecord, SttRecord, ledger_for
from chhatri.ask.mentions import Mention, find_mentions, unconfirmed
from chhatri.ask.model_path import ModelOutcome, ask_model
from chhatri.ask.scam import ScamCheck, check_scam
from chhatri.ask.types import MAX_QUESTION_CHARS, AskAnswer, ClauseRef, Lang, NextAction
from chhatri.clock import IST, Clock
from chhatri.conversation.explain_first import explain_first
from chhatri.conversation.intents import Intent, classify
from chhatri.conversation.messages import bilingual
from chhatri.conversation.ports import ClaimsPort, ConversationStore
from chhatri.domain.enums import CaseStatus
from chhatri.domain.models import Case, Decision, Merchant, Zone
from chhatri.ids import IdFactory
from chhatri.integrations.chat_chain import ChatChain
from chhatri.policy.rules import PolicyRules
from chhatri.store.protocols import AuditSink

logger = logging.getLogger(__name__)

__all__ = [
    "AskCity",
    "AskService",
    "AskStore",
    "MentionsUnconfirmed",
    "UnknownSpeechResult",
    "VoiceQuestion",
]

AI_ACTOR: Final = "ai-agent"
_NO_FORCED: Final[Callable[[], Collection[str]]] = frozenset


class AskCity(Protocol):
    @property
    def zones(self) -> Sequence[Zone]: ...
    def merchant(self, merchant_id: str) -> Merchant: ...


class AskStore(ConversationStore, Protocol):
    def decisions_for(self, merchant_id: str) -> tuple[Decision, ...]: ...


@dataclass(frozen=True, slots=True)
class VoiceQuestion:
    """A voice question: the `ST-` id it came from and the chips the merchant tapped (H18)."""

    stt_id: str
    confirmed_mentions: tuple[str, ...]


class MentionsUnconfirmed(Exception):
    """The question has an amount or date the merchant did not confirm (409 `mentions_unconfirmed`)."""

    def __init__(self, ids: tuple[str, ...]) -> None:
        super().__init__("unconfirmed mentions")
        self.ids = ids


class UnknownSpeechResult(Exception):
    """The `stt_id` is not a speech result of this merchant in this scenario (422)."""


@dataclass(frozen=True, slots=True)
class _Draft:
    """An answer before decoration."""

    intent: Intent
    answer_hi: str
    answer_en: str
    clause_ids: tuple[str, ...]
    facts: tuple[Fact, ...]
    next_action: NextAction
    label: AiLabel
    handoff: bool = False
    case_id: str | None = None
    guard: Mapping[str, Any] | None = None


def _label_rules() -> AiLabel:
    return AiLabel(AiMode.LIVE, AiProvider.RULES)


def _hash(answer_hi: str, answer_en: str) -> str:
    return hashlib.sha256(f"{answer_hi}\n{answer_en}".encode()).hexdigest()


class AskService:
    def __init__(
        self,
        *,
        city: AskCity,
        store: AskStore,
        claims: ClaimsPort,
        rules: PolicyRules,
        chain: ChatChain,
        audit: AuditSink,
        ids: IdFactory,
        clock: Clock,
        consents_on: bool = False,
        grievances_on: bool = False,
        forced: Callable[[], Collection[str]] = _NO_FORCED,
    ) -> None:
        self._city = city
        self._store = store
        self._claims = claims
        self._rules = rules
        self._chain = chain
        self._audit = audit
        self._ids = ids
        self._clock = clock
        self._consents_on = consents_on
        self._grievances_on = grievances_on
        self._forced = forced
        self._ledger: AskLedger = ledger_for(ids)

    # ------------------------------------------------------------------ public

    def today(self) -> date:
        return self._clock.now().astimezone(IST).date()

    def mentions_of(self, text: str) -> tuple[Mention, ...]:
        return find_mentions(text, today=self.today())

    async def answer(
        self, merchant_id: str, question: str, lang: Lang | None = None, *, voice: VoiceQuestion | None = None
    ) -> AskAnswer:
        """Answer one question. `KeyError` for an unknown merchant, `ValueError` for a bad question."""
        merchant = self._city.merchant(merchant_id)
        text = question.strip()
        if not text or len(text) > MAX_QUESTION_CHARS:
            raise ValueError(f"the question must be 1..{MAX_QUESTION_CHARS} characters")
        confirmed = self._check_voice(merchant, text, voice)
        scam, injection = check_scam(text), scan_injection(text)
        draft = await self._draft(merchant, text, scam, injection)
        answer = self._decorate(merchant, lang, draft, scam)
        self._record(merchant, answer, draft, scam, injection)
        if voice is not None:
            self._audit_confirmed(voice, confirmed)
        return answer

    # ------------------------------------------------------------------ voice chips

    def _check_voice(self, merchant: Merchant, text: str, voice: VoiceQuestion | None) -> tuple[Mention, ...]:
        if voice is None:
            return ()
        record = self._ledger.stt(voice.stt_id)
        if record is None or record.merchant_id != merchant.id:
            raise UnknownSpeechResult(voice.stt_id)
        mentions = self.mentions_of(text)
        pending = unconfirmed(mentions, voice.confirmed_mentions)
        if pending:
            raise MentionsUnconfirmed(pending)
        return mentions

    def _audit_confirmed(self, voice: VoiceQuestion, mentions: tuple[Mention, ...]) -> None:
        record = self._ledger.stt(voice.stt_id)
        self._audit.append(
            at=self._clock.now(),
            actor=AI_ACTOR,
            action="voice.confirmed",
            subject_type="stt",
            subject_id=voice.stt_id,
            data={
                "merchant_id": record.merchant_id if record else None,
                "mention_ids": [m.id for m in mentions],
                "amounts_paise": [m.value_paise for m in mentions if m.value_paise is not None],
                "dates": [m.value_date.isoformat() for m in mentions if m.value_date is not None],
            },
        )

    # ------------------------------------------------------------------ the answer path

    async def _draft(
        self, merchant: Merchant, text: str, scam: ScamCheck, injection: InjectionScan
    ) -> _Draft:
        if injection.strong:
            return self._template(
                Intent.UNKNOWN,
                scam,
                AiLabel(AiMode.FALLBACK, AiProvider.TEMPLATE, None, FallbackReason.INJECTION_SUSPECTED),
            )
        intent = classify(text)
        if intent is Intent.UNKNOWN or explain_first(
            text, intent
        ):  # N2.7: a question about a rule is grounded
            if scam.flagged:
                return self._scam_only()
            return await self._model_draft(merchant, text)
        rule = await answer_intent(
            intent,
            merchant=merchant,
            text=text,
            claims=self._claims,
            store=self._store,
            today=self.today(),
        )
        return self._rule_draft(merchant, intent, rule, scam)

    def _template(self, intent: Intent, scam: ScamCheck, label: AiLabel) -> _Draft:
        hi, en = bilingual("FALLBACK_HELP")
        if scam.flagged:
            warn_hi, warn_en = render_pair("ASK_SCAM_WARNING")
            hi, en = f"{warn_hi}\n{hi}", f"{warn_en}\n{en}"
        return _Draft(intent, hi, en, (), (), next_actions.action("ASK_AGAIN"), label)

    def _scam_only(self) -> _Draft:
        hi, en = render_pair("ASK_SCAM_WARNING")
        return _Draft(Intent.UNKNOWN, hi, en, (), (), next_actions.action("ASK_AGAIN"), _label_rules())

    def _rule_draft(self, merchant: Merchant, intent: Intent, rule: RuleAnswer, scam: ScamCheck) -> _Draft:
        hi, en = rule.answer_hi, rule.answer_en
        if scam.flagged:
            warn_hi, warn_en = render_pair("ASK_SCAM_WARNING")
            hi, en = f"{warn_hi}\n{hi}", f"{warn_en}\n{en}"
        sheet = self._sheet(merchant, rule.decision)
        facts = tuple(f for key in rule.fact_keys if (f := sheet.get(key)) is not None)
        nxt = next_actions.for_intent(
            intent,
            case_opened=rule.case_opened and rule.case_id is not None,
            check_in_open=rule.check_in_open,
        )
        if scam.flagged:
            nxt = next_actions.action("ASK_AGAIN")
        return _Draft(intent, hi, en, rule.clause_ids, facts, nxt, _label_rules(), case_id=rule.case_id)

    async def _model_draft(self, merchant: Merchant, text: str) -> _Draft:
        decisions = self._store.decisions_for(merchant.id)
        latest = max(decisions, key=lambda d: d.decided_at, default=None)
        sheet = self._sheet(merchant, latest)
        outcome = await ask_model(self._chain, text, sheet, forced=frozenset(self._forced()))
        return self._from_model(merchant, sheet, outcome)

    def _from_model(self, merchant: Merchant, sheet: FactSheet, outcome: ModelOutcome) -> _Draft:
        label = outcome.result.label
        guard = _guard_summary(outcome)
        has_decision = sheet.has_decision()
        reply = outcome.reply
        if reply is None:
            hi, en = bilingual("FALLBACK_HELP")
            return _Draft(
                Intent.UNKNOWN, hi, en, (), (), next_actions.action("ASK_AGAIN"), label, guard=guard
            )
        if not reply["can_answer"]:
            hi, en = render_pair("ASK_HANDOFF")
            handoff_label = AiLabel(AiMode.LIVE, AiProvider.TEMPLATE, None, None, label.attempts)
            nxt = next_actions.talk_to_team(has_decision=has_decision, grievances_on=self._grievances_on)
            return _Draft(Intent.UNKNOWN, hi, en, (), (), nxt, handoff_label, handoff=True, guard=guard)
        clause_ids = tuple(reply["clause_ids"])
        facts = tuple(f for key in reply["fact_keys"] if (f := sheet.get(key)) is not None)
        nxt = next_actions.for_clauses(
            clause_ids,
            has_decision=has_decision,
            check_in_open=self._claims.open_silence(merchant.id) is not None,
            consents_on=self._consents_on,
            grievances_on=self._grievances_on,
        )
        return _Draft(
            Intent.UNKNOWN, reply["answer_hi"], reply["answer_en"], clause_ids, facts, nxt, label, guard=guard
        )

    def _sheet(self, merchant: Merchant, decision: Decision | None) -> FactSheet:
        open_case = self._open_case(merchant.id)
        zone = next((z.name for z in self._city.zones if z.id == merchant.zone_id), None)
        return build_fact_sheet(
            rules=self._rules,
            decision=decision,
            cover=self._store.cover(merchant.id),
            open_case=open_case,
            zone_name=zone,
            today=self.today(),
        )

    def _open_case(self, merchant_id: str) -> Case | None:
        mine = [c for c in self._store.cases(CaseStatus.OPEN) if c.merchant_id == merchant_id]
        return max(mine, key=lambda c: c.opened_at, default=None)

    # ------------------------------------------------------------------ decorate and record

    def _decorate(self, merchant: Merchant, lang: Lang | None, draft: _Draft, scam: ScamCheck) -> AskAnswer:
        table = clause_table()
        clauses = tuple(ClauseRef(cid, table[cid].title) for cid in draft.clause_ids if cid in table)
        chosen: Lang = lang or ("en" if merchant.language.value == "en" else "hi")
        return AskAnswer(
            ask_id=self._ids.next("ask"),
            intent=draft.intent.value,
            lang=chosen,
            answer_hi=draft.answer_hi,
            answer_en=draft.answer_en,
            clauses=clauses,
            facts=draft.facts,
            next_action=draft.next_action,
            handoff=draft.handoff,
            case_id=draft.case_id,
            scam_warning=scam.flagged,
            label=draft.label,
        )

    def _record(
        self, merchant: Merchant, answer: AskAnswer, draft: _Draft, scam: ScamCheck, injection: InjectionScan
    ) -> None:
        self._ledger.add_ask(AskRecord(answer.ask_id, merchant.id, answer.answer_hi, answer.answer_en))
        guard = dict(draft.guard) if draft.guard is not None else {"verdict": "NOT_RUN", "reasons": []}
        self._audit.append(
            at=self._clock.now(),
            actor=AI_ACTOR,
            action="ask.answered",
            subject_type="ask",
            subject_id=answer.ask_id,
            data={
                "merchant_id": merchant.id,
                "ask_id": answer.ask_id,
                "intent": answer.intent,
                "intent_source": "rules",
                "lang": answer.lang,
                **answer.label.to_wire(),
                "clause_ids": [c.id for c in answer.clauses],
                "fact_keys": [f.key for f in answer.facts],
                "guard": guard,
                "injection": {"level": injection.level.value, "signals": list(injection.signals)},
                "scam": {"flagged": scam.flagged, "signals": list(scam.signals)},
                "next_action": answer.next_action.kind,
                "handoff": answer.handoff,
                "case_id": answer.case_id,
                "answer_sha256": _hash(answer.answer_hi, answer.answer_en),
            },
        )

    def record_stt(self, stt_id: str, merchant_id: str, provider: str) -> None:
        self._ledger.add_stt(SttRecord(stt_id, merchant_id, provider))


def _guard_summary(outcome: ModelOutcome) -> dict[str, Any]:
    """`PASS` when a reply that was shown passed the guard, `BLOCK` when every reply the guard saw was refused."""
    reasons = list(outcome.guard_reasons)
    reply = outcome.reply
    if reply is not None and reply["can_answer"]:
        return {"verdict": "PASS", "reasons": reasons}
    return {"verdict": "BLOCK" if outcome.guard_ran else "NOT_RUN", "reasons": reasons}
