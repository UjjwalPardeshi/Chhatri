"""The open next step wins over generic intents (demo-day L2, L3) and the pre-check buttons (L1), in the chat.

A typed "yes" while a read slip waits confirms it (never CHECKIN_OK); a yes or no while the doctor question waits answers
it; "team" sends a slip that needs a retake to the team; a message that is not about the step gets the step's own line
instead of the generic help, also when Ask Chhatri timed out (its label kept).
"""

from __future__ import annotations

import io
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import pytest
from PIL import Image

from chhatri.ai.chain import ChainResult
from chhatri.ai.labels import AiLabel, AiMode, AiProvider, FallbackReason
from chhatri.clock import ist
from chhatri.conversation.ask_port import UnknownReply
from chhatri.conversation.messages import bilingual
from chhatri.conversation.pending import (
    Choice,
    ChoiceKind,
    PendingStep,
    StepKind,
    choice_button,
    choice_data,
    parse_choice,
    resolve_step,
    step_reminder,
    wants_team,
    yes_no,
)
from chhatri.conversation.service import ConversationService
from chhatri.domain.enums import CaseKind, CaseStatus, Direction
from chhatri.domain.models import Case, Message, SlipExtraction
from chhatri.integrations.sarvam_sim import SimulatedSlipReader, SimulatedSTT
from chhatri.integrations.soundbox import SimulatedSoundbox
from chhatri.precheck.consent_step import ConsentQuestion
from chhatri.precheck.model import PrecheckStatus
from chhatri.precheck.service import Filed, SlipPrecheckService
from chhatri.sim.city import ANIL
from tests.conversation.conftest import SILENT_DAY, World, make_world

ILLNESS_DAY_AT = ist(2025, 8, 21, 11, 21)
LABEL = AiLabel(AiMode.SIMULATED, AiProvider.SIMULATED, fallback_reason=FallbackReason.NO_KEY)
SLIP = SlipExtraction(
    patient_name="Anil R. Jadhav",
    admission_date=SILENT_DAY,
    hospital_name="KEM Hospital, Parel",
    document_type="admission_slip",
    doctor_name="Dr S. Rao",
    doctor_registration_no="MMC-2011-45817",
    confidence=0.94,
    source="simulated",
)


# ------------------------------------------------------------------------------------------------ words and buttons


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("yes", True),
        ("haan", True),
        ("हाँ", True),
        ("Yes, this is right", True),
        ("हाँ, सही है", True),
        ("Yes, ask them", True),
        ("ji", True),
        ("no", False),
        ("nahi", False),
        ("नहीं", False),
        ("No", False),
        ("yes why did I get only 1500", None),
        ("help me with my claim", None),
        ("मुझे इतने पैसे क्यों मिले?", None),
    ],
)
def test_yes_no(text: str, answer: bool | None) -> None:
    assert yes_no(text) is answer


@pytest.mark.parametrize(
    ("text", "team"),
    [("team", True), ("टीम", True), ("send to team", True), ("हमारी टीम को भेजें", True), ("yes", False)],
)
def test_wants_team(text: str, team: bool) -> None:
    assert wants_team(text) is team


def test_button_data_round_trips_and_fits_telegram() -> None:
    for kind, answer in (
        (ChoiceKind.PRECHECK, "confirm"),
        (ChoiceKind.PRECHECK, "team"),
        (ChoiceKind.CONSENT, "yes"),
        (ChoiceKind.CONSENT, "no"),
    ):
        choice = Choice(kind, "PC-000001", answer)
        data = choice_data(choice)
        assert parse_choice(data) == choice and len(data.encode()) <= 64
    data, title = choice_button(ChoiceKind.CONSENT, "PC-000001", "yes")
    assert data == "cs:PC-000001:yes" and title == "हाँ, पूछ लीजिए / Yes, ask them"
    for junk in ("why", "pc:PC-1:confirm", "cs:PC-000001:maybe", "dr:0123abcd:yes", "pc:PC-000001:confirm:x"):
        assert parse_choice(junk) is None


def test_the_reminder_of_each_step() -> None:
    lines = {
        StepKind.CONSENT: "DOCTOR_CONSENT_REMIND",
        StepKind.PRECHECK_READY: "SLIP_PRECHECK_REMIND",
        StepKind.SLIP_WANTED: "ASK_SLIP",
        StepKind.DOCTOR_WAITING: "DOCTOR_WAITING",
    }
    for kind, key in lines.items():
        assert step_reminder(PendingStep(kind, "PC-000001")).key == key
    assert (
        step_reminder(PendingStep(StepKind.PRECHECK_TEAM, "PC-000001", retakes_left=1)).key
        == "SLIP_TEAM_REMIND"
    )
    assert step_reminder(PendingStep(StepKind.PRECHECK_TEAM, "PC-000001")).key == "SLIP_TEAM_ONLY_REMIND"
    chip = step_reminder(PendingStep(StepKind.CLAIM_WITH_TEAM, case_id="C-2291"))
    assert chip.key == "CLAIM_WITH_TEAM" and "C-2291" in (chip.text_en or "")
    ready = step_reminder(PendingStep(StepKind.PRECHECK_READY, "PC-000001"))
    assert [data for data, _ in ready.buttons] == ["pc:PC-000001:confirm"]


# ------------------------------------------------------------------------------------------------ a chat with a pre-check


@dataclass
class FakeChain:
    reads: list[SlipExtraction | None]

    async def read_with_label(self, image: bytes, mime: str, **_: Any) -> ChainResult[SlipExtraction]:
        return ChainResult(self.reads.pop(0) if self.reads else SLIP, LABEL)


@dataclass
class FakeAsk:
    """Ask Chhatri whose model timed out: the template answer with an honest label."""

    asked: list[str] = field(default_factory=list)

    async def answer_unknown(self, merchant_id: str, text: str) -> UnknownReply:
        self.asked.append(text)
        hi, en = bilingual("FALLBACK_HELP")
        meta: Mapping[str, Any] = {
            "mode": "FALLBACK",
            "provider": "template",
            "model": None,
            "fallback_reason": "TIMEOUT",
        }
        return UnknownReply(hi, en, meta)


@dataclass
class Rig:
    world: World
    chat: ConversationService
    precheck: SlipPrecheckService
    consents: list[dict[str, Any]]


def rig(
    reads: list[SlipExtraction | None] | None = None,
    *,
    require_doctor: bool = True,
    ask: FakeAsk | None = None,
) -> Rig:
    world = make_world(start=ILLNESS_DAY_AT)
    world.claims.silence = SILENT_DAY
    consents: list[dict[str, Any]] = []
    holder: dict[str, SlipPrecheckService] = {}

    class Recorder:
        def record(self, **kwargs: Any) -> object:
            consents.append(kwargs)
            return object()

    chat = ConversationService(
        city=world.city,
        store=world.store,
        audit=world.audit,
        ids=world.ids,
        clock=world.clock,
        bus=world.bus,
        channel=world.channel,
        stt=SimulatedSTT(),
        tts=world.tts,
        chat=None,
        slips=SimulatedSlipReader(),
        soundbox=SimulatedSoundbox(world.tts),
        claims=world.claims,
        channel_name=world.service._outbox._channel_name,
        precheck=lambda: holder["service"],
        unknown=(lambda: ask) if ask is not None else None,
    )

    async def filer(merchant_id: str, slip: SlipExtraction, media_id: str) -> Filed:
        filed = await chat.file_slip(merchant_id, slip, media_id)
        return Filed(filed.decision, filed.messages, filed.doctor_pending)

    async def asker(merchant_id: str, question: ConsentQuestion) -> Message:
        return await chat.ask_doctor_consent(merchant_id, question)

    holder["service"] = SlipPrecheckService(
        ids=world.ids,
        clock=world.clock,
        audit=world.audit,
        store=world.store,
        claims=world.claims,
        chain=FakeChain(list(reads or [SLIP])),  # type: ignore[arg-type]
        minimum=0.80,
        filer=filer,
        require_doctor=require_doctor,
        asker=asker,
        consents=Recorder(),
    )
    return Rig(world, chat, holder["service"], consents)


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(out, format="PNG")
    return out.getvalue()


async def photo(r: Rig) -> str:
    replies = await r.chat.handle_image(ANIL.id, png(), "image/png", r.world.ids.next("media"))
    return str(replies[-1].meta["precheck_id"])


def keys(r: Rig) -> list[str]:
    return [str(e.data["key"]) for e in r.world.audit.entries(limit=5000) if e.action == "message.outbound"]


async def test_no_step_without_a_check_in() -> None:
    r = rig()
    r.world.claims.silence = None
    assert r.chat.pending_step(ANIL.id) is None


async def test_the_step_order() -> None:
    r = rig([SLIP.model_copy(update={"patient_name": None}), SLIP])
    assert r.chat.pending_step(ANIL.id) == PendingStep(StepKind.SLIP_WANTED)
    retake = await photo(r)
    assert r.chat.pending_step(ANIL.id) == PendingStep(StepKind.PRECHECK_TEAM, retake, retakes_left=2)
    ready = await photo(r)
    assert r.chat.pending_step(ANIL.id) == PendingStep(StepKind.PRECHECK_READY, ready)
    await r.chat.handle_text(ANIL.id, "yes")
    assert r.chat.pending_step(ANIL.id) == PendingStep(StepKind.CONSENT, ready)


async def test_a_typed_yes_confirms_the_read_slip_not_the_old_check_in() -> None:
    r = rig()
    pc_id = await photo(r)
    replies = await r.chat.handle_text(ANIL.id, "yes")
    assert replies[0].direction is Direction.INBOUND
    assert "CHECKIN_OK" not in keys(r)
    assert keys(r)[-1] == "DOCTOR_CONSENT_ASK"
    assert r.precheck.get(ANIL.id, pc_id).status is PrecheckStatus.AWAITING_CONSENT
    step = next(e for e in r.world.audit.entries(limit=5000) if e.data.get("source") == "pending-step")
    assert step.data["step"] == "PRECHECK_READY"


async def test_with_the_rule_off_a_typed_yes_files_the_claim() -> None:
    r = rig(require_doctor=False)
    pc_id = await photo(r)
    await r.chat.handle_text(ANIL.id, "haan")
    assert r.precheck.get(ANIL.id, pc_id).status is PrecheckStatus.CONFIRMED
    assert len(r.world.claims.submitted) == 1


async def test_a_typed_no_to_the_read_slip_asks_for_a_clearer_photo() -> None:
    r = rig()
    pc_id = await photo(r)
    await r.chat.handle_text(ANIL.id, "nahi")
    assert keys(r)[-1] == "SLIP_PRECHECK_SAID_NO"
    assert r.precheck.get(ANIL.id, pc_id).status is PrecheckStatus.READY and r.world.claims.submitted == []


@pytest.mark.parametrize(("text", "granted"), [("हाँ", True), ("Yes", True), ("no", False), ("नहीं", False)])
async def test_a_typed_answer_to_the_doctor_question_records_it_and_files(text: str, granted: bool) -> None:
    r = rig()
    pc_id = await photo(r)
    await r.chat.handle_text(ANIL.id, "yes")
    await r.chat.handle_text(ANIL.id, text)
    [answer] = r.consents
    assert answer["granted"] is granted and answer["source"] == "CHAT" and answer["precheck_id"] == pc_id
    assert r.precheck.get(ANIL.id, pc_id).status is PrecheckStatus.CONFIRMED
    assert len(r.world.claims.submitted) == 1


async def test_team_while_a_retake_is_open_sends_it_to_the_team() -> None:
    r = rig([SLIP.model_copy(update={"patient_name": None})])
    pc_id = await photo(r)
    await r.chat.handle_text(ANIL.id, "send to team")
    assert r.precheck.get(ANIL.id, pc_id).status is PrecheckStatus.CONFIRMED
    assert r.precheck.get(ANIL.id, pc_id).confirmed_as is not None
    assert r.precheck.get(ANIL.id, pc_id).confirmed_as.value == "SENT_TO_TEAM"


async def test_a_question_while_a_slip_is_read_is_answered_with_the_step() -> None:
    r = rig()
    await photo(r)
    await r.chat.handle_text(ANIL.id, "hello")
    assert keys(r)[-1] == "SLIP_PRECHECK_REMIND"


async def test_a_timed_out_ask_becomes_the_step_line_with_its_label_kept() -> None:
    ask = FakeAsk()
    r = rig(ask=ask)
    await photo(r)
    replies = await r.chat.handle_text(ANIL.id, "help me with my claim")
    assert ask.asked == ["help me with my claim"]
    reply = replies[-1]
    assert (reply.text_hi, reply.text_en) == bilingual("SLIP_PRECHECK_REMIND")
    assert reply.meta["mode"] == "FALLBACK" and reply.meta["fallback_reason"] == "TIMEOUT"
    assert reply.meta["provider"] == "template"


async def test_buttons_run_the_same_actions() -> None:
    r = rig()
    pc_id = await photo(r)
    replies = await r.chat.handle_choice(ANIL.id, Choice(ChoiceKind.PRECHECK, pc_id, "confirm"))
    assert replies[0].direction is Direction.INBOUND and replies[0].text_en == "Yes, this is right"
    assert replies[-1].card is not None and replies[-1].card["consent_for"] == pc_id
    replies = await r.chat.handle_choice(ANIL.id, Choice(ChoiceKind.CONSENT, pc_id, "yes"))
    assert replies[0].text_en == "Yes, ask them" and r.consents[0]["granted"] is True
    again = await r.chat.handle_choice(ANIL.id, Choice(ChoiceKind.CONSENT, pc_id, "yes"))
    assert again[-1].text_en == bilingual("SLIP_ACTION_DONE")[1]
    gone = await r.chat.handle_choice(ANIL.id, Choice(ChoiceKind.PRECHECK, "PC-000999", "confirm"))
    assert gone[-1].text_en == bilingual("SLIP_ACTION_EXPIRED")[1]


async def test_an_old_confirm_button_while_the_question_waits_repeats_the_question() -> None:
    r = rig()
    pc_id = await photo(r)
    await r.chat.handle_choice(ANIL.id, Choice(ChoiceKind.PRECHECK, pc_id, "confirm"))
    replies = await r.chat.handle_choice(ANIL.id, Choice(ChoiceKind.PRECHECK, pc_id, "confirm"))
    assert replies[-1].text_en == bilingual("DOCTOR_CONSENT_REMIND")[1]


async def test_an_open_review_case_is_the_step_after_filing() -> None:
    r = rig()
    r.world.claims.silence = None
    case = Case(
        id="C-2291",
        kind=CaseKind.DISPUTE,
        merchant_id=ANIL.id,
        status=CaseStatus.OPEN,
        opened_at=r.world.clock.now(),
        due_by=r.world.clock.now() + timedelta(hours=24),
        summary_en="dispute",
    )
    r.world.store.add_case(case)
    assert resolve_step(ANIL.id, precheck=None, checkin_open=False, store=r.world.store) == PendingStep(
        StepKind.CLAIM_WITH_TEAM, case_id=case.id
    )
    r.world.clock.advance(timedelta(minutes=1))
    await r.chat.handle_text(ANIL.id, "hello")
    assert keys(r)[-1] == "CLAIM_WITH_TEAM"
