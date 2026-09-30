"""Live Sarvam speech adapters — Saaras STT and Bulbul TTS (SPEC §14.1).

STT: `client.speech_to_text.transcribe(file=(name, bytes, mime), model="saaras:v3", mode="transcribe",
language_code="unknown"|"hi-IN", input_audio_codec=…)` → `.transcript`, `.language_code`,
`.language_probability`. Accepts OGG/Opus (WhatsApp voice notes) and WebM (browser MediaRecorder).

TTS: `client.text_to_speech.convert(text=…, language_code="hi-IN", model="bulbul:v3", speaker="ritu",
pace=1.0, output_audio_codec="mp3"|"opus")` → `.audios[0]` base64. Max 2,500 characters (v3), no
pitch/loudness in v3, speakers lowercase. WhatsApp voice notes use opus sent as `audio/ogg`; the
browser gets mp3.
"""

from __future__ import annotations

import base64
import binascii
import re
from typing import Any

from chhatri.domain.enums import Language
from chhatri.integrations.base import IntegrationError, SynthesizedAudio, Transcript
from chhatri.integrations.retry import DEFAULT_TIMEOUT_S
from chhatri.integrations.sarvam_client import (
    SARVAM_LANGUAGE_CODES,
    UNKNOWN_LANGUAGE,
    ClientFactory,
    SarvamCaller,
    default_client_factory,
    field_of,
)

STT_MODE = "transcribe"
TTS_PACE = 1.0
TTS_MAX_CHARS = 2500  # SPEC §14.1: bulbul:v3 limit
MIME_TO_CODEC: dict[str, str] = {
    "audio/ogg": "ogg",
    "audio/opus": "opus",
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/mp4": "mp4",
    "audio/m4a": "x-m4a",
    "audio/x-m4a": "x-m4a",
}
_LANGUAGE_CODE = re.compile(r"^[a-z]{2}-IN$")
WHATSAPP_AUDIO = ("opus", "audio/ogg")  # SPEC §14.1: opus, sent as audio/ogg
BROWSER_AUDIO = ("mp3", "audio/mpeg")


def audio_codec_for(mime_type: str) -> str:
    """Map an upload MIME type (parameters ignored) to Sarvam's `input_audio_codec`."""
    base = mime_type.split(";", 1)[0].strip().lower()
    codec = MIME_TO_CODEC.get(base)
    if codec is None:
        raise IntegrationError("sarvam_stt", "unsupported audio type")
    return codec


def stt_language(language_hint: str | None) -> str:
    """`hi-IN`-style hints pass through; anything else asks Saaras to detect ("unknown")."""
    if language_hint and _LANGUAGE_CODE.match(language_hint):
        return language_hint
    return UNKNOWN_LANGUAGE


class LiveSarvamSTT:
    """SpeechToText backed by Sarvam Saaras (SPEC §14.1)."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "saaras:v3",
        caller: SarvamCaller | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for live Sarvam STT")
        self.model = model
        self._caller = caller or SarvamCaller(
            "sarvam_stt", client_factory or default_client_factory(api_key, DEFAULT_TIMEOUT_S)
        )

    async def transcribe(
        self, audio: bytes, mime_type: str, *, language_hint: str | None = None
    ) -> Transcript:
        if not audio:
            raise IntegrationError("sarvam_stt", "empty audio")
        codec = audio_codec_for(mime_type)
        language = stt_language(language_hint)
        options = self._caller.request_options()

        def run(client: Any) -> Any:
            return client.speech_to_text.transcribe(
                file=(f"voice.{codec}", audio, mime_type),
                model=self.model,
                mode=STT_MODE,
                language_code=language,
                input_audio_codec=codec,
                request_options=options,
            )

        response = await self._caller.call(run)
        text = field_of(response, "transcript")
        if not isinstance(text, str):
            raise IntegrationError("sarvam_stt", "response had no transcript")
        probability = field_of(response, "language_probability")
        return Transcript(
            text=text.strip(),
            language_code=field_of(response, "language_code"),
            confidence=float(probability) if isinstance(probability, int | float) else None,
            source=f"sarvam:{self.model}",
        )


class LiveSarvamTTS:
    """TextToSpeech backed by Sarvam Bulbul (SPEC §14.1)."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "bulbul:v3",
        speaker: str = "ritu",
        caller: SarvamCaller | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for live Sarvam TTS")
        self.model = model
        self.speaker = speaker.lower()  # SPEC §14.1: speakers are lowercase
        self._caller = caller or SarvamCaller(
            "sarvam_tts", client_factory or default_client_factory(api_key, DEFAULT_TIMEOUT_S)
        )

    async def synthesize(
        self, text: str, language: Language, *, for_whatsapp: bool = False
    ) -> SynthesizedAudio:
        cleaned = text.strip()
        if not cleaned:
            raise IntegrationError("sarvam_tts", "empty text")
        if len(cleaned) > TTS_MAX_CHARS:
            raise IntegrationError("sarvam_tts", f"text longer than {TTS_MAX_CHARS} characters")
        codec, mime = WHATSAPP_AUDIO if for_whatsapp else BROWSER_AUDIO
        language_code = SARVAM_LANGUAGE_CODES[language]
        options = self._caller.request_options()

        def run(client: Any) -> Any:
            return client.text_to_speech.convert(
                text=cleaned,
                language_code=language_code,
                model=self.model,
                speaker=self.speaker,
                pace=TTS_PACE,
                output_audio_codec=codec,
                request_options=options,
            )

        response = await self._caller.call(run)
        return SynthesizedAudio(audio=_first_audio(response), mime_type=mime, source=f"sarvam:{self.model}")


def _first_audio(response: Any) -> bytes:
    audios = field_of(response, "audios")
    if not isinstance(audios, list | tuple) or not audios or not isinstance(audios[0], str):
        raise IntegrationError("sarvam_tts", "response had no audio")
    try:
        audio = base64.b64decode(audios[0], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise IntegrationError("sarvam_tts", "audio was not valid base64") from exc
    if not audio:
        raise IntegrationError("sarvam_tts", "response had empty audio")
    return audio
