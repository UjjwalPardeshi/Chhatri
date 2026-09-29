"""Conversation service (SPEC §13, §24.4). Talk to merchants in Hindi + English.

ConversationService implements the flows of §13.5:
- Area payout (intro + payout card + soundbox)
- WHY_AMOUNT (explain area)
- DISPUTE_AMOUNT (open case + dispute ack)
- Silent check-in (CHECKIN_SILENT)
- REPORT_ILLNESS (ask for slip → slip reader → personal claim → policy)
- BUY_COVER (evaluate → COVER_BLOCKED or COVER_LINK)
- Officer results (OFFICER_APPROVED / OFFICER_DECLINED)
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Protocol

from chhatri.clock import Clock
from chhatri.conversation.intents import Intent
from chhatri.conversation.messages import bilingual, render
from chhatri.conversation.nlu import classify_with_llm
from chhatri.domain.enums import (
    Channel,
    DecisionOutcome,
    Direction,
    Language,
    MessageKind,
)
from chhatri.domain.models import (
    AreaTrigger,
    Case,
    CoverQuote,
    Decision,
    InstalmentPause,
    Message,
    Merchant,
    Payout,
    SlipExtraction,
)
from chhatri.events import EventBus
from chhatri.ids import IdFactory
from chhatri.integrations.base import (
    ChatModel,
    MessagingChannel,
    OutboundMessage,
    SlipReader,
    Soundbox,
    SpeechToText,
    TextToSpeech,
)
from chhatri.money import format_inr
from chhatri.sim.city import City
from chhatri.store.protocols import AuditSink, MessageLog

logger = logging.getLogger(__name__)


class ClaimsPort(Protocol):
    """Implemented by the orchestrator; conversation never touches policy directly."""

    async def submit_personal_claim(
        self, merchant_id: str, slip: SlipExtraction, media_id: str
    ) -> Decision: ...

    async def open_dispute(self, merchant_id: str, text: str) -> Case: ...

    async def quote_cover(self, merchant_id: str) -> tuple[CoverQuote, Any | None]: ...

    def latest_paid_decision(self, merchant_id: str) -> Decision | None: ...

    def open_silence(self, merchant_id: str) -> date | None: ...


class ConversationService:
    """Conversation service (SPEC §24.4).

    Stores every message in MessageLog, audits each action, publishes events, sends via channel.
    """

    def __init__(
        self,
        *,
        city: City,
        store: MessageLog,
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
    ) -> None:
        self.city = city
        self.store = store
        self.audit = audit
        self.ids = ids
        self.clock = clock
        self.bus = bus
        self.channel = channel
        self.stt = stt
        self.tts = tts
        self.chat = chat
        self.slips = slips
        self.soundbox = soundbox
        self.claims = claims
        self.channel_name = channel_name

    async def handle_text(
        self, merchant_id: str, text: str
    ) -> tuple[Message, ...]:
        """Process inbound text message. Returns (inbound, *replies)."""
        merchant = self.city.merchant(merchant_id)
        now = self.clock.now()

        # Store inbound
        inbound = Message(
            id=self.ids.next("message"),
            merchant_id=merchant_id,
            direction=Direction.INBOUND,
            channel=self.channel_name,
            kind=MessageKind.TEXT,
            text_hi=text if self._is_hindi(text) else None,
            text_en=text if not self._is_hindi(text) else None,
            created_at=now,
        )
        self.store.add_message(inbound)
        self.audit.append(
            at=now,
            actor=f"merchant:{merchant_id}",
            action="message_inbound",
            subject_type="message",
            subject_id=inbound.id,
            data={"kind": "text"},
        )

        # Classify intent
        intent = await classify_with_llm(text, self.chat)

        # Process by intent
        replies = []
        if intent == Intent.WHY_AMOUNT:
            replies = await self._handle_why_amount(merchant, now)
        elif intent == Intent.DISPUTE_AMOUNT:
            replies = await self._handle_dispute(merchant, text, now)
        elif intent == Intent.REPORT_ILLNESS:
            replies = await self._handle_report_illness(merchant, now)
        elif intent == Intent.BUY_COVER:
            replies = await self._handle_buy_cover(merchant, now)
        elif intent == Intent.COVER_STATUS:
            replies = await self._handle_cover_status(merchant, now)
        elif intent in (Intent.GREETING, Intent.AFFIRM, Intent.DENY):
            replies = await self._handle_acknowledge(merchant, intent, now)
        else:
            replies = await self._send_fallback_help(merchant, now)

        return (inbound,) + tuple(replies)

    async def handle_voice(
        self,
        merchant_id: str,
        audio: bytes,
        mime: str,
        *,
        transcript_hint: str | None = None,
    ) -> tuple[Message, ...]:
        """Process inbound voice (STT → treat as text). Returns (voice_inbound, *replies)."""
        merchant = self.city.merchant(merchant_id)
        now = self.clock.now()

        # Transcribe
        try:
            transcript_obj = await self.stt.transcribe(
                audio, mime, language_hint=transcript_hint
            )
            transcript = transcript_obj.text
        except Exception:
            logger.exception("STT error")
            transcript = ""

        # Store voice inbound
        voice_msg = Message(
            id=self.ids.next("message"),
            merchant_id=merchant_id,
            direction=Direction.INBOUND,
            channel=self.channel_name,
            kind=MessageKind.VOICE,
            text_hi=transcript if transcript and self._is_hindi(transcript) else None,
            text_en=transcript if transcript and not self._is_hindi(transcript) else None,
            created_at=now,
            meta={"transcript": transcript, "voice_source": "sarvam"}
            if transcript
            else {"voice_source": "sarvam"},
        )
        self.store.add_message(voice_msg)
        self.audit.append(
            at=now,
            actor=f"merchant:{merchant_id}",
            action="message_inbound",
            subject_type="message",
            subject_id=voice_msg.id,
            data={"kind": "voice", "transcript": transcript},
        )

        # If no transcript, send polite "couldn't hear" reply
        if not transcript:
            reply = await self._send_message(
                merchant,
                "माफ कीजिए, आप की बात समझ नहीं आई। कृपया लिखकर भेजें।",
                "I didn't catch that. Could you please type your message?",
                now
            )
            return (voice_msg, reply)

        # Treat transcript as text
        return await self.handle_text(merchant_id, transcript)

    async def handle_image(
        self, merchant_id: str, image: bytes, mime: str, media_id: str
    ) -> tuple[Message, ...]:
        """Process inbound image (slip → SlipReader → submit_personal_claim)."""
        merchant = self.city.merchant(merchant_id)
        now = self.clock.now()

        # Store inbound image message
        image_msg = Message(
            id=self.ids.next("message"),
            merchant_id=merchant_id,
            direction=Direction.INBOUND,
            channel=self.channel_name,
            kind=MessageKind.IMAGE,
            media_url=f"/api/media/{media_id}",
            created_at=now,
        )
        self.store.add_message(image_msg)
        self.store.put_media(image, mime, media_id)
        self.audit.append(
            at=now,
            actor=f"merchant:{merchant_id}",
            action="message_inbound",
            subject_type="message",
            subject_id=image_msg.id,
            data={"kind": "image", "media_id": media_id},
        )

        # Read slip
        try:
            slip = await self.slips.read_slip(image, mime)
        except Exception:
            logger.exception("Slip reading error")
            reply = await self._send_message(
                merchant,
                "मैं पर्ची को स्पष्ट नहीं पढ़ सका। कृपया फिर से कोशिश करें।",
                "I couldn't read the slip clearly. Please try again.",
                now,
            )
            return (image_msg, reply)

        # Submit personal claim
        decision = await self.claims.submit_personal_claim(
            merchant_id, slip, media_id
        )

        # Respond based on decision
        replies = []
        if decision.outcome == DecisionOutcome.APPROVED:
            # PERSONAL_PAID + payout card
            replies = await self._send_personal_paid(
                merchant, decision, now
            )
        elif decision.outcome == DecisionOutcome.REFERRED:
            # SLIP_TO_HUMAN variant
            replies = await self._send_slip_to_human(
                merchant, decision, now
            )
        else:
            # DECLINED
            declined_msg = await self._send_message(
                merchant,
                "आपके दावे को स्वीकृत नहीं किया जा सका। कृपया सहायता के लिए संपर्क करें।",
                "Your claim could not be approved. Please contact support.",
                now,
            )
            replies = [declined_msg]

        return (image_msg,) + tuple(replies)

    async def notify_area_payout(
        self,
        decision: Decision,
        payout: Payout,
        trigger: AreaTrigger,
    ) -> tuple[Message, ...]:
        """Notify area payout (SPEC §13.5 area payout flow)."""
        merchant = self.city.merchant(decision.merchant_id)
        now = self.clock.now()

        messages = []

        # AREA_PAYOUT_INTRO (bilingual)
        hi_text, en_text = bilingual(
            "AREA_PAYOUT_INTRO",
            name_hi=merchant.owner_name_hi,
            name_en=merchant.owner_name,
            drop=trigger.drop_pct,
        )
        intro_msg = await self._send_message(
            merchant,
            hi_text,
            en_text,
            now,
        )
        messages.append(intro_msg)

        # PAYOUT_CARD
        payout_msg = Message(
            id=self.ids.next("message"),
            merchant_id=merchant.id,
            direction=Direction.OUTBOUND,
            channel=self.channel_name,
            kind=MessageKind.PAYOUT_CARD,
            created_at=now,
            card={
                "amount_label": format_inr(payout.amount_paise),
                "subtitle_hi": "आज के सेटलमेंट के साथ जमा",
                "subtitle_en": "Credited with today's settlement",
                "badge": "No claim needed",
            },
        )
        self.store.add_message(payout_msg)
        self.audit.append(
            at=now,
            actor="ai-agent",
            action="message_outbound",
            subject_type="message",
            subject_id=payout_msg.id,
            data={"kind": "payout_card", "amount": payout.amount_paise},
        )
        messages.append(payout_msg)

        # Soundbox event
        await self._soundbox_announce(
            merchant,
            render("SOUNDBOX", "en", amount=format_inr(payout.amount_paise)),
            payout.amount_paise,
            now,
        )

        return tuple(messages)

    async def notify_instalment_paused(
        self, pause: InstalmentPause
    ) -> Message:
        """Notify instalment paused (SPEC §13.5)."""
        merchant = self.city.merchant(pause.merchant_id)
        now = self.clock.now()

        hi_text, en_text = bilingual(
            "INSTALMENT_PAUSED",
            instalment=format_inr(pause.amount_paise),
        )
        msg = await self._send_message(
            merchant,
            hi_text,
            en_text,
            now,
        )
        return msg

    async def notify_personal_paid(
        self, decision: Decision, payout: Payout
    ) -> tuple[Message, ...]:
        """Notify personal claim approved + paid."""
        merchant = self.city.merchant(decision.merchant_id)
        now = self.clock.now()

        messages = []

        # PERSONAL_PAID (bilingual)
        hi_text, en_text = bilingual(
            "PERSONAL_PAID",
            name_hi=merchant.owner_name_hi,
            name_en=merchant.owner_name,
            amount=format_inr(payout.amount_paise),
        )
        msg = await self._send_message(
            merchant,
            hi_text,
            en_text,
            now,
        )
        messages.append(msg)

        # Soundbox
        await self._soundbox_announce(
            merchant,
            render("SOUNDBOX", "en", amount=format_inr(payout.amount_paise)),
            payout.amount_paise,
            now,
        )

        return tuple(messages)

    async def checkin_silent(
        self, merchant_id: str, first_silent_day: date
    ) -> Message:
        """Check in on silent merchant (SPEC §13.5, §13.7).

        On live WhatsApp outside 24-hour window, use template; otherwise free-form.
        """
        merchant = self.city.merchant(merchant_id)
        now = self.clock.now()

        # Check if outside 24-hour window (SPEC §13.7)
        # Note: Template selection is handled by the MessagingChannel implementation
        _ = self._get_last_inbound_time(merchant_id)

        # Render bilingual check-in message
        hi_text, en_text = bilingual(
            "CHECKIN_SILENT",
            name_hi=merchant.owner_name_hi,
            name_en=merchant.owner_name,
        )

        # On live WhatsApp outside 24h, send via template; otherwise free-form
        # (Template sending is handled by channel implementation; we send the message normally)
        msg = await self._send_message(
            merchant,
            hi_text,
            en_text,
            now,
        )
        return msg

    async def notify_officer_result(
        self, decision: Decision, case: Case
    ) -> tuple[Message, ...]:
        """Notify officer decision result (SPEC §13.5)."""
        merchant = self.city.merchant(decision.merchant_id)
        now = self.clock.now()

        messages = []

        if decision.outcome == DecisionOutcome.APPROVED:
            # OFFICER_APPROVED
            hi_text, en_text = bilingual(
                "OFFICER_APPROVED",
                name_hi=merchant.owner_name_hi,
                name_en=merchant.owner_name,
                amount=format_inr(decision.amount_paise),
            )
            msg = await self._send_message(
                merchant,
                hi_text,
                en_text,
                now,
            )
            messages.append(msg)
        else:
            # OFFICER_DECLINED with reason
            reason_hi = decision.referral_reason or "आपके दावे को स्वीकृत नहीं किया जा सका।"
            reason_en = decision.referral_reason or "Your claim could not be approved."
            hi_text, en_text = bilingual(
                "OFFICER_DECLINED",
                name_hi=merchant.owner_name_hi,
                name_en=merchant.owner_name,
                reason_hi=reason_hi,
                reason_en=reason_en,
            )
            msg = await self._send_message(
                merchant,
                hi_text,
                en_text,
                now,
            )
            messages.append(msg)

        # CASE_CHIP (English only per spec)
        case_chip = Message(
            id=self.ids.next("message"),
            merchant_id=merchant.id,
            direction=Direction.OUTBOUND,
            channel=self.channel_name,
            kind=MessageKind.CASE_CHIP,
            text_en=render("CASE_CHIP", "en", case_id=case.id),
            created_at=now,
        )
        self.store.add_message(case_chip)
        self.audit.append(
            at=now,
            actor="ai-agent",
            action="message_outbound",
            subject_type="message",
            subject_id=case_chip.id,
            data={"kind": "case_chip", "case_id": case.id},
        )
        messages.append(case_chip)

        return tuple(messages)

    # ---- Helpers ----

    async def _handle_why_amount(
        self, merchant: Merchant, now: datetime
    ) -> list[Message]:
        """WHY_AMOUNT flow: show explanation."""
        latest = self.claims.latest_paid_decision(merchant.id)
        if latest is None:
            return await self._send_fallback_help(merchant, now)

        # EXPLAIN_AREA with decision facts
        if latest.explanation:
            exp = latest.explanation
            hi_text, en_text = bilingual(
                "EXPLAIN_AREA",
                weekday_hi=exp.weekday_hi,
                weekday_en=exp.weekday_en,
                expected=format_inr(exp.expected_day_paise),
                drop=exp.drop_pct or 0,
            )
        else:
            return await self._send_fallback_help(merchant, now)

        msg = await self._send_message(merchant, hi_text, en_text, now)
        return [msg]

    async def _handle_dispute(
        self, merchant: Merchant, text: str, now: datetime
    ) -> list[Message]:
        """DISPUTE_AMOUNT flow: open case."""
        case = await self.claims.open_dispute(merchant.id, text)

        messages = []

        # DISPUTE_ACK
        hi_text, en_text = bilingual("DISPUTE_ACK")
        ack_msg = await self._send_message(
            merchant,
            hi_text,
            en_text,
            now,
        )
        messages.append(ack_msg)

        # CASE_CHIP
        chip_msg = Message(
            id=self.ids.next("message"),
            merchant_id=merchant.id,
            direction=Direction.OUTBOUND,
            channel=self.channel_name,
            kind=MessageKind.CASE_CHIP,
            text_en=render("CASE_CHIP", "en", case_id=case.id),
            created_at=now,
        )
        self.store.add_message(chip_msg)
        self.audit.append(
            at=now,
            actor="ai-agent",
            action="message_outbound",
            subject_type="message",
            subject_id=chip_msg.id,
            data={"kind": "case_chip", "case_id": case.id},
        )
        messages.append(chip_msg)

        # Publish case event
        self.bus.publish(
            "case",
            now,
            {"case": case.model_dump(mode="json")},
        )

        return messages

    async def _handle_report_illness(
        self, merchant: Merchant, now: datetime
    ) -> list[Message]:
        """REPORT_ILLNESS flow: check if outreach is open, ask for slip."""
        silence = self.claims.open_silence(merchant.id)
        if silence is None:
            # No outreach open, send fallback
            return await self._send_fallback_help(merchant, now)

        # ASK_SLIP
        hi_text, en_text = bilingual("ASK_SLIP")
        msg = await self._send_message(
            merchant, hi_text, en_text, now
        )
        return [msg]

    async def _handle_buy_cover(
        self, merchant: Merchant, now: datetime
    ) -> list[Message]:
        """BUY_COVER flow: get quote, send link or blocked."""
        quote, payment = await self.claims.quote_cover(merchant.id)

        messages = []

        if quote.outcome.value == "BLOCKED":
            # COVER_BLOCKED
            hi_text, en_text = bilingual(
                "COVER_BLOCKED",
                starts_on_hi=self._format_date_hi(quote.starts_on),
                starts_on_en=self._format_date_en(quote.starts_on),
            )
            msg = await self._send_message(
                merchant,
                hi_text,
                en_text,
                now,
            )
            messages.append(msg)
        else:
            # COVER_LINK
            hi_text, en_text = bilingual(
                "COVER_LINK",
                first_payment=format_inr(quote.first_payment_paise),
                per_day=format_inr(quote.premium_per_day_paise),
                url=payment.link_url or "https://paytm.me/chhatri",
            )
            msg = await self._send_message(
                merchant,
                hi_text,
                en_text,
                now,
            )
            messages.append(msg)

        return messages

    async def _handle_cover_status(
        self, merchant: Merchant, now: datetime
    ) -> list[Message]:
        """COVER_STATUS flow: provide information."""
        # For now, use fallback help as no specific COVER_STATUS template
        return await self._send_fallback_help(merchant, now)

    async def _handle_acknowledge(
        self,
        merchant: Merchant,
        intent: Intent,
        now: datetime,
    ) -> list[Message]:
        """Handle GREETING, AFFIRM, DENY."""
        if intent == Intent.GREETING:
            hi_text = "नमस्ते! मैं छतरी हूँ।"
            en_text = "Hello! I'm Chhatri."
        elif intent == Intent.AFFIRM:
            hi_text = "ठीक है!"
            en_text = "Great!"
        else:  # DENY
            hi_text = "समझा।"
            en_text = "Okay."

        msg = await self._send_message(merchant, hi_text, en_text, now)
        return [msg]

    async def _send_personal_paid(
        self,
        merchant: Merchant,
        decision: Decision,
        now: datetime,
    ) -> list[Message]:
        """Send PERSONAL_PAID message."""
        messages = []

        hi_text, en_text = bilingual(
            "PERSONAL_PAID",
            name_hi=merchant.owner_name_hi,
            name_en=merchant.owner_name,
            amount=format_inr(decision.amount_paise),
        )
        msg = await self._send_message(
            merchant,
            hi_text,
            en_text,
            now,
        )
        messages.append(msg)

        # Soundbox (if amount > 0)
        if decision.amount_paise > 0:
            await self._soundbox_announce(
                merchant,
                render(
                    "SOUNDBOX", "en", amount=format_inr(decision.amount_paise)
                ),
                decision.amount_paise,
                now,
            )

        return messages

    async def _send_slip_to_human(
        self,
        merchant: Merchant,
        decision: Decision,
        now: datetime,
    ) -> list[Message]:
        """Send SLIP_TO_HUMAN variant based on failing check (SPEC §13.5)."""
        messages = []

        # Select message variant based on the failing SOFT check
        message_key = "SLIP_TO_HUMAN"  # default
        for check in decision.checks:
            if check.status == "FAIL" and check.severity == "SOFT":
                if check.code == "DATES_MATCH":
                    message_key = "SLIP_TO_HUMAN_DATES"
                    break
                elif check.code == "SLIP_READABLE":
                    message_key = "SLIP_TO_HUMAN_UNREADABLE"
                    break
                elif check.code == "NAME_MATCHES_KYC":
                    message_key = "SLIP_TO_HUMAN"
                    break

        hi_text, en_text = bilingual(message_key)
        msg = await self._send_message(
            merchant,
            hi_text,
            en_text,
            now,
        )
        messages.append(msg)

        return messages

    async def _send_fallback_help(
        self, merchant: Merchant, now: datetime
    ) -> list[Message]:
        """Send FALLBACK_HELP."""
        hi_text, en_text = bilingual("FALLBACK_HELP")
        msg = await self._send_message(
            merchant, hi_text, en_text, now
        )
        return [msg]

    async def _send_message(
        self, merchant: Merchant, hi_text: str, en_text: str, now: datetime
    ) -> Message:
        """Send a bilingual text message via channel, store, audit, publish."""
        msg = Message(
            id=self.ids.next("message"),
            merchant_id=merchant.id,
            direction=Direction.OUTBOUND,
            channel=self.channel_name,
            kind=MessageKind.TEXT,
            text_hi=hi_text,
            text_en=en_text,
            created_at=now,
        )

        # Generate TTS for Hindi text
        try:
            audio_obj = await self.tts.synthesize(
                hi_text, Language.HI
            )
            if audio_obj.audio:
                media_id = self.ids.next("media")
                msg = msg.model_copy(
                    update={
                        "audio_url": f"/api/media/{media_id}",
                        "meta": {
                            "voice_source": audio_obj.source or "browser-simulated"
                        },
                    }
                )
                self.store.put_media(audio_obj.audio, audio_obj.mime_type or "audio/mpeg", media_id)
            else:
                msg = msg.model_copy(
                    update={"meta": {"voice_source": "browser-simulated"}}
                )
        except Exception:
            logger.exception("TTS error")
            msg = msg.model_copy(update={"meta": {"voice_source": "browser-simulated"}})

        # Store
        self.store.add_message(msg)
        self.audit.append(
            at=now,
            actor="ai-agent",
            action="message_outbound",
            subject_type="message",
            subject_id=msg.id,
            data={"kind": "text"},
        )

        # Send via channel (bilingual: Hindi + English)
        try:
            await self.channel.send(
                OutboundMessage(
                    merchant_id=merchant.id,
                    to_phone=merchant.phone,
                    text=f"{hi_text}\n{en_text}",
                )
            )
        except Exception:
            logger.exception("Channel send error")

        # Publish event
        self.bus.publish(
            "message",
            now,
            {"message": msg.model_dump(mode="json")},
        )

        return msg

    async def _soundbox_announce(
        self, merchant: Merchant, text: str, amount_paise: int, now: datetime
    ) -> None:
        """Send soundbox announcement."""
        try:
            await self.soundbox.announce(merchant.id, text, amount_paise)
            self.bus.publish(
                "soundbox",
                now,
                {
                    "merchant_id": merchant.id,
                    "text": text,
                    "amount_label": format_inr(amount_paise),
                    "audio_url": None,
                },
            )
        except Exception:
            logger.exception("Soundbox error")

    def _get_last_inbound_time(self, merchant_id: str) -> datetime | None:
        """Get the most recent inbound message time for a merchant (SPEC §13.7).

        Returns None if no inbound messages exist.
        """
        messages = self.store.messages(merchant_id)
        for msg in reversed(messages):
            if msg.direction == Direction.INBOUND:
                return msg.created_at
        return None

    @staticmethod
    def _is_hindi(text: str) -> bool:
        """Check if text contains Devanagari characters."""
        import re

        return bool(re.search(r"[ऀ-ॿ]", text))

    @staticmethod
    def _format_date_hi(d: date) -> str:
        """Format date for Hindi: '27 अगस्त'."""
        months_hi = [
            "जनवरी",
            "फरवरी",
            "मार्च",
            "अप्रैल",
            "मई",
            "जून",
            "जुलाई",
            "अगस्त",
            "सितंबर",
            "अक्तूबर",
            "नवंबर",
            "दिसंबर",
        ]
        return f"{d.day} {months_hi[d.month - 1]}"

    @staticmethod
    def _format_date_en(d: date) -> str:
        """Format date for English: '25 Aug'."""
        months_en = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]
        return f"{d.day} {months_en[d.month - 1]}"
