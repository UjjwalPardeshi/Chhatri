"""N4 voice: speech to text with amount and date chips (H18) and text to speech of an earlier answer (fs-05 section 11).

Speech to text. The chain is Sarvam, then the browser's own recognition (on the client), then the text box. The route
takes audio (Sarvam) or a transcript the browser made (`source: browser`, the server never sees audio). The label is
honest: no Sarvam key gives SIMULATED with NO_KEY (a browser transcript then has provider `browser`), a closed data gate
gives SIMULATED with FREE_TIER_BLOCKED and no outbound call, a forced component gives FALLBACK with FORCED, and a Sarvam
error gives FALLBACK with the reason and an empty transcript, so the client falls back to the browser. The audio is
not stored. The audit entry `voice.transcribed` holds the id, the label, the language code, the duration and the number
of mentions, never the transcript.

Text to speech. Only the answer of an earlier ask of the same merchant can be voiced, so the route is not a speech
proxy. Sarvam speech is used for demo merchants only (the BUILT rule), for at most 2,500 characters; otherwise the client
speaks the text with `speechSynthesis` (provider `browser`).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import Final, Literal

from chhatri.ai.failures import classify_failure
from chhatri.ai.labels import AiLabel, AiMode, AiProvider, FallbackReason, mode_for
from chhatri.ask.ledger import AskLedger, SttRecord
from chhatri.ask.mentions import Mention, find_mentions
from chhatri.clock import IST, Clock
from chhatri.domain.enums import Language
from chhatri.domain.models import Merchant
from chhatri.ids import IdFactory
from chhatri.integrations.base import IntegrationError, SpeechToText, TextToSpeech
from chhatri.store.protocols import AuditSink

logger = logging.getLogger(__name__)

__all__ = [
    "MAX_TTS_CHARS",
    "MAX_TRANSCRIPT_CHARS",
    "SttResult",
    "TtsResult",
    "UnknownAsk",
    "VoiceService",
]

AI_ACTOR: Final = "ai-agent"
STT_COMPONENT: Final = "sarvam_stt"
TTS_COMPONENT: Final = "sarvam_tts"
STT_TIMEOUT_S: Final = 10.0
TTS_TIMEOUT_S: Final = 10.0
MAX_TTS_CHARS: Final = 2500
MAX_TRANSCRIPT_CHARS: Final = 500
MEDIA_URL: Final = "/api/media/{media_id}"
SARVAM_SOURCE_PREFIX: Final = "sarvam"
LanguageCode = Literal["hi-IN", "en-IN", "unknown"]


class UnknownAsk(Exception):
    """The `ask_id` is unknown, or it belongs to another merchant (404)."""


@dataclass(frozen=True, slots=True)
class SttResult:
    stt_id: str
    transcript: str
    language_code: str | None
    duration_s: float | None
    mentions: tuple[Mention, ...]
    label: AiLabel


@dataclass(frozen=True, slots=True)
class TtsResult:
    audio_url: str | None
    mime_type: str | None
    label: AiLabel


def _label(mode: AiMode, provider: AiProvider, model: str | None, reason: FallbackReason | None) -> AiLabel:
    return AiLabel(mode, provider, model, reason)


class VoiceService:
    def __init__(
        self,
        *,
        stt: SpeechToText,
        tts: TextToSpeech,
        live: Callable[[], Collection[str]],
        gate: Callable[[str], bool],
        forced: Callable[[], Collection[str]],
        put_media: Callable[[bytes, str, str], None],
        ids: IdFactory,
        audit: AuditSink,
        clock: Clock,
        ledger: AskLedger,
        stt_model: str,
        tts_model: str,
    ) -> None:
        self._stt, self._tts = stt, tts
        self._live, self._gate, self._forced = live, gate, forced
        self._put_media = put_media
        self._ids, self._audit, self._clock, self._ledger = ids, audit, clock, ledger
        self._stt_model, self._tts_model = stt_model, tts_model

    # ------------------------------------------------------------------ speech to text

    async def transcribe_audio(
        self, merchant_id: str, audio: bytes, mime: str, *, duration_s: float, lang_hint: str | None
    ) -> SttResult:
        """Audio from the microphone to a transcript and its chips (the audio is not stored)."""
        text, code, label = await self._run_stt(audio, mime, lang_hint)
        return self._result(merchant_id, text, code, duration_s, label)

    def from_browser(self, merchant_id: str, transcript: str, language_code: str | None) -> SttResult:
        """A transcript the browser made. The label says why the server did not hear the audio."""
        return self._result(merchant_id, transcript.strip(), language_code, None, self._browser_label())

    def _unavailable(self) -> FallbackReason | None:
        """Why Sarvam speech is not used now: no key, a closed data gate or the demo switch (None when it can run)."""
        if STT_COMPONENT in self._forced():
            return FallbackReason.FORCED
        if STT_COMPONENT not in self._live():
            return FallbackReason.NO_KEY
        if not self._gate(STT_COMPONENT):
            return FallbackReason.FREE_TIER_BLOCKED
        return None

    def _browser_label(self) -> AiLabel:
        reason = (
            self._unavailable() or FallbackReason.PROVIDER_ERROR
        )  # Sarvam could run: the client chose the browser
        return _label(mode_for(reason), AiProvider.BROWSER, None, reason)

    async def _run_stt(self, audio: bytes, mime: str, hint: str | None) -> tuple[str, str | None, AiLabel]:
        reason = self._unavailable()
        language_hint = None if hint in (None, "unknown") else hint
        if reason is not None:
            text, code = await self._simulated_transcript(audio, mime, language_hint, reason)
            provider = AiProvider.SIMULATED if reason is FallbackReason.NO_KEY else AiProvider.NONE
            return text, code, _label(mode_for(reason), provider, None, reason)
        try:
            heard = await asyncio.wait_for(
                self._stt.transcribe(audio, mime, language_hint=language_hint), timeout=STT_TIMEOUT_S
            )
        except Exception as exc:  # a speech failure is never an HTTP error: the label says what happened
            failure = classify_failure(exc)
            logger.warning("voice: speech to text failed (%s)", failure.value)
            return "", None, _label(mode_for(failure), AiProvider.NONE, None, failure)
        if heard.source.startswith(SARVAM_SOURCE_PREFIX):
            return (
                heard.text.strip(),
                heard.language_code,
                _label(AiMode.LIVE, AiProvider.SARVAM, self._stt_model, None),
            )
        reason = FallbackReason.NO_KEY
        return (
            heard.text.strip(),
            heard.language_code,
            _label(mode_for(reason), AiProvider.SIMULATED, None, reason),
        )

    async def _simulated_transcript(
        self, audio: bytes, mime: str, hint: str | None, reason: FallbackReason
    ) -> tuple[str, str | None]:
        """Without Sarvam the deterministic simulator reads the canned demo clips; anything else is "nothing heard"."""
        if reason is not FallbackReason.NO_KEY:
            return "", None
        try:
            heard = await self._stt.transcribe(audio, mime, language_hint=hint)
        except IntegrationError:
            return "", None
        return heard.text.strip(), heard.language_code

    def _result(
        self, merchant_id: str, text: str, code: str | None, duration_s: float | None, label: AiLabel
    ) -> SttResult:
        stt_id = self._ids.next("stt")
        mentions = find_mentions(text, today=self._clock.now().astimezone(IST).date())
        self._ledger.add_stt(SttRecord(stt_id, merchant_id, label.provider.value))
        self._audit.append(
            at=self._clock.now(),
            actor=AI_ACTOR,
            action="voice.transcribed",
            subject_type="stt",
            subject_id=stt_id,
            data={
                "merchant_id": merchant_id,
                "stt_id": stt_id,
                **label.to_wire(),
                "language_code": code,
                "duration_s": duration_s,
                "mention_count": len(mentions),
            },
        )
        return SttResult(stt_id, text, code, duration_s, mentions, label)

    # ------------------------------------------------------------------ text to speech

    async def speak(self, merchant: Merchant, ask_id: str, lang: Literal["hi", "en"]) -> TtsResult:
        """Voice the answer of `ask_id` in `lang`: Sarvam audio, or the browser speaks it (`audio_url` null)."""
        record = self._ledger.ask(ask_id)
        if record is None or record.merchant_id != merchant.id:
            raise UnknownAsk(ask_id)
        text = record.answer_hi if lang == "hi" else record.answer_en
        blocked = self._tts_unavailable(merchant, text)
        if blocked is not None:
            return TtsResult(None, None, _label(mode_for(blocked), AiProvider.BROWSER, None, blocked))
        try:
            speech = await asyncio.wait_for(
                self._tts.synthesize(text, Language.HI if lang == "hi" else Language.EN),
                timeout=TTS_TIMEOUT_S,
            )
        except Exception as exc:
            failure = classify_failure(exc)
            logger.warning("voice: text to speech failed (%s)", failure.value)
            return TtsResult(None, None, _label(mode_for(failure), AiProvider.BROWSER, None, failure))
        if speech.audio is None:
            reason = FallbackReason.NO_KEY
            return TtsResult(None, None, _label(mode_for(reason), AiProvider.BROWSER, None, reason))
        mime = speech.mime_type or "audio/mpeg"
        media_id = self._ids.next("media")
        self._put_media(speech.audio, mime, media_id)
        label = _label(AiMode.LIVE, AiProvider.SARVAM, self._tts_model, None)
        return TtsResult(MEDIA_URL.format(media_id=media_id), mime, label)

    def _tts_unavailable(self, merchant: Merchant, text: str) -> FallbackReason | None:
        if TTS_COMPONENT in self._forced():
            return FallbackReason.FORCED
        if TTS_COMPONENT not in self._live():
            return FallbackReason.NO_KEY
        if not merchant.is_demo or not self._gate(TTS_COMPONENT):
            return (
                FallbackReason.FREE_TIER_BLOCKED
            )  # only demo merchants' synthetic text may reach a free-tier service
        if len(text) > MAX_TTS_CHARS:
            return FallbackReason.PROVIDER_ERROR  # too long for Sarvam speech: the client speaks it
        return None
