"""Deterministic offline stand-ins for Sarvam (SPEC §0.1 "deterministic simulator", §14.1).

- `SimulatedSTT`: recognises the canned demo voice notes (`demo_voice.demo_voice_note`) and honours
  transcript hints passed through `language_hint` — a demo key (`"why"`) or the literal words the
  console already knows (SPEC §24.4 `handle_voice(..., transcript_hint=…)`). A real language code
  (`hi-IN`) is not a hint. Anything else yields an empty transcript (the "please type" path).
- `SimulatedTTS`: no audio; the console speaks with browser `speechSynthesis`, labelled (SPEC §20).
- `SimulatedChat`: offline there is no language model, so it always declines with IntegrationError
  and callers use the deterministic rules (SPEC §13.2). The registry passes `chat=None` instead.
- `SimulatedSlipReader`: reads the `chhatri:slip` PNG tEXt JSON embedded by `sim.slips.render_slip`
  (via `read_embedded_slip`, SPEC §24.1); an image without it reads at confidence 0.3 with no fields.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from chhatri.domain.enums import Language
from chhatri.domain.models import SlipExtraction
from chhatri.integrations.base import IntegrationError, SynthesizedAudio, Transcript
from chhatri.integrations.demo_voice import DEMO_UTTERANCES, demo_key_of
from chhatri.integrations.sarvam_docai import parse_slip
from chhatri.sim.slips import read_embedded_slip

logger = logging.getLogger(__name__)

SIMULATED = "simulated"
UNREADABLE_CONFIDENCE = 0.3  # simulated vision: an image without embedded slip data
HINT_CONFIDENCE = 1.0
_LANGUAGE_CODE = re.compile(r"^(unknown|[a-z]{2}-IN)$")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def _language_of(text: str) -> str:
    return "hi-IN" if _DEVANAGARI.search(text) else "en-IN"


def _utterance_transcript(key: str) -> Transcript:
    utterance = DEMO_UTTERANCES[key]
    return Transcript(
        text=utterance.transcript,
        language_code=utterance.language_code,
        confidence=HINT_CONFIDENCE,
        source=SIMULATED,
    )


class SimulatedSTT:
    """Deterministic SpeechToText (see module docstring for the exact rules)."""

    async def transcribe(
        self, audio: bytes, mime_type: str, *, language_hint: str | None = None
    ) -> Transcript:
        key = demo_key_of(audio)
        if key is not None:
            return _utterance_transcript(key)
        hint = (language_hint or "").strip()
        if hint in DEMO_UTTERANCES:
            return _utterance_transcript(hint)
        if hint and not _LANGUAGE_CODE.match(hint):
            return Transcript(
                text=hint, language_code=_language_of(hint), confidence=HINT_CONFIDENCE, source=SIMULATED
            )
        logger.info("simulated STT: no demo clip or transcript hint (%s, %d bytes)", mime_type, len(audio))
        return Transcript(text="", language_code=None, confidence=0.0, source=SIMULATED)


class SimulatedTTS:
    """TextToSpeech without audio: the console falls back to labelled browser speech."""

    async def synthesize(
        self, text: str, language: Language, *, for_whatsapp: bool = False
    ) -> SynthesizedAudio:
        if not text.strip():
            raise IntegrationError("sarvam_tts", "empty text")
        return SynthesizedAudio(audio=None, mime_type=None, source=SIMULATED)


class SimulatedChat:
    """Offline ChatModel: always declines so callers use deterministic rules (SPEC §13.2)."""

    async def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, schema_name: str
    ) -> dict[str, Any]:
        raise IntegrationError("sarvam_chat", "no language model offline (simulated)")


def _embedded_confidence(metadata: dict[str, Any]) -> float:
    value = metadata.get("confidence")
    if isinstance(value, bool) or not isinstance(value, int | float):
        return UNREADABLE_CONFIDENCE
    return float(value)


class SimulatedSlipReader:
    """Reads slip data embedded in sample PNGs; unknown images are unreadable (confidence 0.3)."""

    async def read_slip(self, image: bytes, mime_type: str) -> SlipExtraction:
        if not image:
            raise IntegrationError("sarvam_vision", "empty image")
        try:
            metadata = read_embedded_slip(image)
        except Exception as exc:  # undecodable upload: simulated vision cannot read it either
            logger.warning("simulated vision: image could not be decoded (%s)", type(exc).__name__)
            metadata = None
        if metadata is None:
            logger.info("simulated vision: no embedded slip data in %s image", mime_type)
            return SlipExtraction(confidence=UNREADABLE_CONFIDENCE, source=SIMULATED, raw={})
        return parse_slip(metadata, _embedded_confidence(metadata), source=SIMULATED)
