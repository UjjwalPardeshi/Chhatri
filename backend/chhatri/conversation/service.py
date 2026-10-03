"""ConversationService — talks to merchants in Hindi + English (SPEC §13, §24.4).

One service serves WhatsApp (live) and the console phone simulator (``channel_name``). Inbound text,
voice (→ STT) and slip photos are recorded, classified (``nlu.detect_intent``, audited as
``intent.detected``) and answered by the §13.5 flows (``replies``, ``slip_flow``); the orchestrator
calls the ``notify_*`` / ``checkin_silent`` methods from its workflow steps (``notifications``).
Every message goes through ``outbox.Outbox``: stored in the MessageLog, published as a §19.1
``message`` event, voiced, sent via the channel and audited.

Voice notes: the transcript comes from the SpeechToText (``transcript_hint`` is passed as its
``language_hint``, which the simulator uses as the words). When the STT hears nothing or fails
(logged) and the caller supplied ``transcript_hint`` — the console's canned deck voice notes, which
are silent WAV clips — the hint is used, labelled ``voice_source: "browser-simulated"``; without a
hint the merchant is asked to repeat or type (VOICE_UNCLEAR). The audio is kept as media so the
console can play it; ``meta.duration_s`` is read from WAV headers.

The open next step (``pending``): before any intent, a yes / no / "team" that answers the step that waits for the
merchant (the doctor question, a read slip, a slip for the team) runs that step's action on the pre-check, exactly as
the app's buttons and the Telegram buttons (``handle_choice``) do. A message that is not about the step and would get
the generic help line gets the step's own line instead, also when Ask Chhatri fell back to its template (its label is
kept as the chain reported it). The doctor check: ``ask_doctor_consent`` (the pre-check service sends the question),
``notify_doctor_asked`` / ``notify_doctor_answered`` / ``notify_personal_decided`` (the claim pipeline).
"""

from __future__ import annotations

import io
import logging
import wave
from collections.abc import Callable
from datetime import date
from typing import Final

from chhatri.clock import Clock
from chhatri.conversation.ask_port import UnknownResolver
from chhatri.conversation.consent_text import CONSENT_WITHDRAWN_KEYS
from chhatri.conversation.doctor_notices import DoctorNotices
from chhatri.conversation.explain_first import explain_first
from chhatri.conversation.intents import Intent, classify
from chhatri.conversation.message_guard import MessageGuard
from chhatri.conversation.messages import bilingual, date_en, date_hi, name_facts
from chhatri.conversation.nlu import IntentChain, IntentResult, detect_intent, detect_intent_chain
from chhatri.conversation.notifications import Notifications
from chhatri.conversation.outbox import (
    AI_ACTOR,
    MEDIA_URL,
    VOICE_BROWSER,
    VOICE_SARVAM,
    Outbox,
    Outgoing,
)
from chhatri.conversation.pending import (
    CHOICE_ACTIONS,
    Choice,
    PendingStep,
    StepKind,
    choice_label,
    resolve_step,
    step_reminder,
    wants_team,
    yes_no,
)
from chhatri.conversation.ports import ClaimsPort, ConversationStore, DoctorCheckPort, MerchantDirectory
from chhatri.conversation.replies import Replies
from chhatri.conversation.slip_flow import FiledSlip, PrecheckResolver, SlipFlow
from chhatri.domain.enums import Channel, MessageKind, PreferredChannel, VerificationStatus
from chhatri.domain.models import (
    AreaTrigger,
    Case,
    Cover,
    Decision,
    HolidayRequest,
    InstalmentPause,
    Merchant,
    Message,
    Payout,
    PremiumPayment,
    SlipExtraction,
)
from chhatri.events import EventBus
from chhatri.ids import IdFactory
from chhatri.integrations.base import (
    ChatModel,
    IntegrationError,
    MessagingChannel,
    SlipReader,
    Soundbox,
    SpeechToText,
    TextToSpeech,
)
from chhatri.precheck.chat import consent_outgoing
from chhatri.precheck.consent_step import ConsentQuestion
from chhatri.precheck.model import Action
from chhatri.precheck.service import PrecheckConflict, PrecheckNotFound
from chhatri.store.protocols import AuditSink

__all__ = ["ClaimsPort", "ConversationService"]

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS: Final = 2000
SARVAM_SOURCE_PREFIX: Final = "sarvam"
MODEL_BLOCKED_INTENTS: Final = frozenset({Intent.DISPUTE_AMOUNT, Intent.BUY_COVER})
STEP_SOURCE: Final = "pending-step"
# A refused button or word: what the merchant is told instead (an answer already counted, or a step that is gone).
DONE_CODES: Final = frozenset({"already_confirmed", "no_checkin"})


def wav_duration_s(audio: bytes) -> float | None:
    """Duration of a RIFF/WAVE clip in seconds; None for any other container."""
    try:
        with wave.open(io.BytesIO(audio), "rb") as clip:
            rate = clip.getframerate()
            return round(clip.getnframes() / rate, 2) if rate else None
    except (wave.Error, EOFError):
        return None


def _no_precheck() -> None:
    return None


def _require_bytes(data: bytes, what: str) -> None:
    if not data:
        raise ValueError(f"{what} is empty")


class ConversationService:
    """SPEC §24.4 surface; see the module docstring."""

    def __init__(
        self,
        *,
        city: MerchantDirectory,
        store: ConversationStore,
        audit: AuditSink,
        ids: IdFactory,
        clock: Clock,
        bus: EventBus,
        channel: MessagingChannel,
        stt: SpeechToText,
        tts: TextToSpeech,
        chat: ChatModel | None,
        slips: SlipReader,
        soundbox: Soundbox,
        claims: ClaimsPort,
        channel_name: Channel,
        precheck: PrecheckResolver | None = None,
        unknown: UnknownResolver | None = None,
        message_guard: MessageGuard | None = None,
        slip_consent: Callable[[str], bool] | None = None,
        intent_chain: IntentChain | None = None,
        telegram: MessagingChannel | None = None,
        preferred_channel: Callable[[str], PreferredChannel] | None = None,
    ) -> None:
        self._city = city
        self._audit = audit
        self._stt = stt
        self._chat = chat
        self._intent_chain = intent_chain
        self._unknown = unknown
        self._outbox = Outbox(
            store=store,
            audit=audit,
            ids=ids,
            clock=clock,
            bus=bus,
            channel=channel,
            tts=tts,
            soundbox=soundbox,
            channel_name=channel_name,
            guard=message_guard,
            telegram=telegram,
            preferred=preferred_channel,
        )
        self._store = store
        self._claims = claims
        self._precheck: PrecheckResolver = precheck if precheck is not None else _no_precheck
        self._replies = Replies(
            outbox=self._outbox, claims=claims, store=store, next_step=self._step_reminder
        )
        self._doctor = DoctorNotices(outbox=self._outbox, directory=city)
        self._slips = SlipFlow(
            outbox=self._outbox,
            claims=claims,
            store=store,
            reader=slips,
            audit=audit,
            doctor=self._doctor,
            **({} if precheck is None else {"precheck": precheck}),
            **({} if slip_consent is None else {"slip_consent": slip_consent}),
        )
        self._notices = Notifications(outbox=self._outbox, directory=city)

    # ------------------------------------------------------------------ inbound

    async def handle_text(self, merchant_id: str, text: str) -> tuple[Message, ...]:
        """Inbound text → (inbound, *replies)."""
        merchant = self._city.merchant(merchant_id)
        clean = text.strip()
        if not clean or len(clean) > MAX_TEXT_CHARS:
            raise ValueError(f"text must be 1..{MAX_TEXT_CHARS} characters")
        inbound = self._outbox.receive(merchant, kind=MessageKind.TEXT, text=clean)
        return (inbound, *await self._answer(merchant, inbound, clean))

    async def handle_voice(
        self, merchant_id: str, audio: bytes, mime: str, *, transcript_hint: str | None = None
    ) -> tuple[Message, ...]:
        """Inbound voice note → STT → (inbound, *replies)."""
        merchant = self._city.merchant(merchant_id)
        _require_bytes(audio, "voice note")
        transcript, source = await self._transcribe(audio, mime, transcript_hint)
        media_id = self._outbox.store_media(audio, mime)
        meta: dict[str, object] = {
            "voice_source": VOICE_SARVAM if source.startswith(SARVAM_SOURCE_PREFIX) else VOICE_BROWSER
        }
        duration = wav_duration_s(audio)
        if duration is not None:
            meta["duration_s"] = duration
        if transcript:
            meta["transcript"] = transcript
        inbound = self._outbox.receive(
            merchant,
            kind=MessageKind.VOICE,
            text=transcript or None,
            audio_url=MEDIA_URL.format(media_id=media_id),
            meta=meta,
        )
        if not transcript:
            return inbound, await self._outbox.send(merchant, Outgoing.text("VOICE_UNCLEAR"))
        return (inbound, *await self._answer(merchant, inbound, transcript))

    async def handle_image(
        self, merchant_id: str, image: bytes, mime: str, media_id: str
    ) -> tuple[Message, ...]:
        """Inbound slip photo → personal claim → (inbound, *replies)."""
        merchant = self._city.merchant(merchant_id)
        _require_bytes(image, "image")
        if not media_id.strip():
            raise ValueError("media_id is required")
        self._store.put_media(image, mime, media_id)
        inbound = self._outbox.receive(
            merchant, kind=MessageKind.IMAGE, media_url=MEDIA_URL.format(media_id=media_id)
        )
        return (inbound, *await self._slips.reply(merchant, image, mime, media_id))

    async def file_slip(self, merchant_id: str, slip: SlipExtraction, media_id: str) -> FiledSlip:
        """File a personal claim for a slip the merchant confirmed or sent to the team (N3, the pre-check's confirm)."""
        return await self._slips.file(self._city.merchant(merchant_id), slip, media_id)

    async def _transcribe(self, audio: bytes, mime: str, hint: str | None) -> tuple[str, str]:
        try:
            heard = await self._stt.transcribe(audio, mime, language_hint=hint)
            text, source = heard.text.strip(), heard.source
        except IntegrationError as exc:
            logger.warning("conversation: STT failed (%s)", exc.safe_message)
            text, source = "", "failed"
        if not text and hint and hint.strip():
            logger.info("conversation: using the console's transcript hint for a canned voice note")
            return hint.strip(), "hint"
        return text, source

    # ------------------------------------------------------------------ the open next step

    def pending_step(self, merchant_id: str) -> PendingStep | None:
        """What waits for the merchant now (``pending`` module docstring), or None."""
        service = self._precheck()
        claims: object = self._claims
        return resolve_step(
            merchant_id,
            precheck=None if service is None else service.open_for(merchant_id),
            checkin_open=self._claims.open_silence(merchant_id) is not None,
            store=self._store,
            doctor=claims if isinstance(claims, DoctorCheckPort) else None,
            latest_decision_id=self._latest_decision_id,
        )

    def _latest_decision_id(self, merchant_id: str) -> str | None:
        decisions = getattr(self._store, "decisions_for", None)
        found = decisions(merchant_id) if callable(decisions) else ()
        return found[-1].id if found else None

    def _step_reminder(self, merchant_id: str) -> Outgoing | None:
        step = self.pending_step(merchant_id)
        return None if step is None else step_reminder(step)

    async def handle_choice(self, merchant_id: str, choice: Choice) -> tuple[Message, ...]:
        """A tapped pre-check or doctor-question button: recorded as the button's words, then the action runs."""
        merchant = self._city.merchant(merchant_id)
        _, label_en = choice_label(choice)
        inbound = self._outbox.receive(merchant, kind=MessageKind.TEXT, text=label_en)
        action = CHOICE_ACTIONS[(choice.kind, choice.answer)]
        return (inbound, *await self._run_action(merchant, choice.precheck_id, action))

    async def _run_action(self, merchant: Merchant, precheck_id: str, action: Action) -> tuple[Message, ...]:
        service = self._precheck()
        if service is None:
            return (await self._outbox.send(merchant, Outgoing.text("SLIP_ACTION_EXPIRED")),)
        try:
            done = await service.confirm(merchant.id, precheck_id, action, source="CHAT")
        except PrecheckNotFound:
            return (await self._outbox.send(merchant, Outgoing.text("SLIP_ACTION_EXPIRED")),)
        except PrecheckConflict as exc:
            step = self.pending_step(merchant.id)
            if exc.code == "consent_pending" and step is not None:
                return (await self._outbox.send(merchant, step_reminder(step)),)
            key = "SLIP_ACTION_DONE" if exc.code in DONE_CODES else "SLIP_ACTION_EXPIRED"
            return (await self._outbox.send(merchant, Outgoing.text(key)),)
        return done.messages

    async def _answer_step(
        self, merchant: Merchant, inbound: Message, text: str
    ) -> tuple[Message, ...] | None:
        """The open step's answer (L2), or None when `text` does not answer it."""
        step = self.pending_step(merchant.id)
        if step is None or step.precheck_id is None:
            return None
        said = yes_no(text)
        action: Action | None = None
        if step.kind is StepKind.CONSENT and said is not None:
            action = Action.CONSENT_YES if said else Action.CONSENT_NO
        elif step.kind is StepKind.PRECHECK_READY and said is True:
            action = Action.CONFIRM
        elif step.kind is StepKind.PRECHECK_TEAM and wants_team(text):
            action = Action.SEND_TO_TEAM
        elif not (step.kind is StepKind.PRECHECK_READY and said is False):
            return None
        self._audit.append(
            at=inbound.created_at,
            actor=AI_ACTOR,
            action="intent.detected",
            subject_type="message",
            subject_id=inbound.id,
            data={
                "merchant_id": merchant.id,
                "intent": classify(text).value,
                "source": STEP_SOURCE,
                "step": step.kind.value,
            },
        )
        if action is None:  # "no" to a read slip: nothing is filed, a clearer photo is asked for
            return (await self._outbox.send(merchant, Outgoing.text("SLIP_PRECHECK_SAID_NO")),)
        return await self._run_action(merchant, step.precheck_id, action)

    def _ask_fallback(self, merchant: Merchant, out: Outgoing) -> Outgoing:
        """Ask Chhatri's template answer (a timeout, a refusal) becomes the open step's line; the label is kept."""
        if (out.text_hi, out.text_en) != bilingual("FALLBACK_HELP"):
            return out
        reminder = self._step_reminder(merchant.id)
        if reminder is None:
            return out
        return Outgoing(
            key=out.key,
            kind=out.kind,
            text_hi=reminder.text_hi,
            text_en=reminder.text_en,
            meta=out.meta,
            buttons=reminder.buttons,
        )

    async def _answer(self, merchant: Merchant, inbound: Message, text: str) -> tuple[Message, ...]:
        stepped = await self._answer_step(merchant, inbound, text)
        if stepped is not None:
            return stepped
        answerer = self._unknown() if self._unknown is not None else None
        if answerer is None:
            if (
                self._intent_chain is not None
            ):  # Gemini, then Sarvam: a labelled model intent for free Hindi/Hinglish
                detected = await detect_intent_chain(text, self._intent_chain)
            else:
                detected = await detect_intent(text, self._chat)
        else:  # N2 is on: the word lists alone choose the intent, so a model can never open a case (fs-05 N2.15)
            detected = IntentResult(classify(text), "rules")
        self._audit.append(
            at=inbound.created_at,
            actor=AI_ACTOR,
            action="intent.detected",
            subject_type="message",
            subject_id=inbound.id,
            data={
                "merchant_id": merchant.id,
                "intent": detected.intent.value,
                "source": detected.source,
                **({"ai": detected.label.to_wire()} if detected.label is not None else {}),
            },
        )
        grounded = detected.intent is Intent.UNKNOWN or explain_first(text, detected.intent)  # N2.7
        if answerer is not None and grounded:
            reply = await answerer.answer_unknown(merchant.id, text)
            out = Outgoing(
                key="ASK_ANSWER",
                kind=MessageKind.TEXT,
                text_hi=reply.text_hi,
                text_en=reply.text_en,
                meta=reply.meta,
            )
            return (await self._outbox.send(merchant, self._ask_fallback(merchant, out)),)
        if detected.source == "llm" and detected.intent in MODEL_BLOCKED_INTENTS:
            # N2.15: with N2 off, a model-chosen intent never runs a handler that writes (a case, a payment link)
            return await self._replies.respond(merchant, Intent.UNKNOWN, text)
        return await self._replies.respond(merchant, detected.intent, text)

    # ------------------------------------------------------------------ the doctor check

    async def ask_doctor_consent(self, merchant_id: str, question: ConsentQuestion) -> Message:
        """DOCTOR_CONSENT_ASK[_GENERIC] with its Yes / No card and buttons (the pre-check service calls this)."""
        return await self._outbox.send(self._city.merchant(merchant_id), consent_outgoing(question))

    async def notify_doctor_asked(
        self, merchant_id: str, *, doctor_name: str, hospital_name: str, mode: str
    ) -> Message:
        """DOCTOR_ASKED once the question is out (`mode` LIVE, SIMULATED or FALLBACK)."""
        return await self._doctor.asked(
            merchant_id, doctor_name=doctor_name, hospital_name=hospital_name, mode=mode
        )

    async def notify_doctor_answered(
        self, merchant_id: str, *, status: VerificationStatus, doctor_name: str, mode: str
    ) -> Message | None:
        """DOCTOR_CONFIRMED_VISIT for CONFIRMED; nothing for DENIED or NO_ANSWER (the decision message explains)."""
        return await self._doctor.answered(merchant_id, status=status, doctor_name=doctor_name, mode=mode)

    async def notify_personal_decided(self, decision: Decision) -> tuple[Message, ...]:
        """The outcome lines of a personal decision made after the doctor answered (APPROVED: nothing yet)."""
        return await self._slips.outcome_messages(self._city.merchant(decision.merchant_id), decision)

    # ------------------------------------------------------------------ business-initiated

    async def notify_area_payout(
        self, decision: Decision, payout: Payout, trigger: AreaTrigger
    ) -> tuple[Message, ...]:
        """AREA_PAYOUT_INTRO → PAYOUT_CARD → SOUNDBOX, at credit time (SPEC §13.5)."""
        return await self._notices.area_payout(decision, payout, trigger)

    async def notify_instalment_paused(self, pause: InstalmentPause) -> Message:
        """INSTALMENT_PAUSED at pause time (SPEC §13.5)."""
        return await self._notices.instalment_paused(pause)

    async def notify_holiday_decided(self, request: HolidayRequest) -> Message:
        """HOLIDAY_GRANTED* / HOLIDAY_REFUSED / HOLIDAY_NO_RESPONSE once the lender has answered (X4)."""
        return await self._notices.holiday_decided(request)

    async def notify_personal_paid(self, decision: Decision, payout: Payout) -> tuple[Message, ...]:
        """PERSONAL_PAID / OFFICER_APPROVED → PAYOUT_CARD → SOUNDBOX, at credit time."""
        return await self._notices.personal_paid(decision, payout)

    async def notify_premium_paid(self, premium: PremiumPayment, cover: Cover) -> Message:
        """PREMIUM_PAID_STARTS / _ACTIVE after Paytm's paid callback (SPEC §10, §14.3)."""
        return await self._notices.premium_paid(premium, cover)

    async def checkin_silent(self, merchant_id: str, first_silent_day: date) -> Message:
        """CHECKIN_SILENT, business-initiated (template outside the 24 h window, SPEC §13.7)."""
        return await self._notices.checkin_silent(merchant_id, first_silent_day)

    async def notify_dispute_opened(self, case: Case, *, already_open: bool = False) -> tuple[Message, ...]:
        """DISPUTE_ACK (or DISPUTE_ALREADY_OPEN) and the case chip, for a dispute opened from the app (N5)."""
        merchant = self._city.merchant(case.merchant_id)
        return await self._replies.dispute_opened(merchant, case, already_open=already_open)

    async def notify_consent_withdrawn(
        self, merchant_id: str, purpose: str, paid_through: date | None = None
    ) -> Message:
        """CONSENT_WITHDRAWN_SALES, _SLIP or _SETTLEMENT: one chat line after a withdrawal (N6, fs-07 9.4)."""
        merchant = self._city.merchant(merchant_id)
        key = CONSENT_WITHDRAWN_KEYS[purpose]
        facts: dict[str, str] = dict(name_facts(merchant))
        if key == "CONSENT_WITHDRAWN_SETTLEMENT":
            facts |= {
                "paid_to_en": "the date you have paid for" if paid_through is None else date_en(paid_through),
                "paid_to_hi": "जिस तारीख़ तक आपने भुगतान किया है"
                if paid_through is None
                else date_hi(paid_through),
            }
        else:
            facts = {k: v for k, v in facts.items() if k in ("name_hi", "name_en")}
        return await self._outbox.send(merchant, Outgoing.text(key, **facts))

    async def notify_officer_result(self, decision: Decision | None, case: Case) -> tuple[Message, ...]:
        """OFFICER_DECLINED now; an approval is told at credit time by ``notify_personal_paid``.

        A dispute that names no decision (``None``) is answered with DISPUTE_NO_PAYOUT.
        """
        return await self._notices.officer_result(decision, case)
