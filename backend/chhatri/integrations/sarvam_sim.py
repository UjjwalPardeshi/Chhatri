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
  A photo app or Telegram re-encodes a sample slip as a JPEG and drops that chunk, so an image without it is compared
  with a small grayscale thumbnail of each committed sample (`data/slips/*.png`): it reads as that sample only when
  the shape agrees, the picture is close on average and no part of it differs (a different patient name does), and
  the next-closest sample is clearly further. Anything else is never guessed.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final

import numpy as np
from PIL import Image

from chhatri.config import DATA_DIR
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
SAMPLE_SLIPS_DIR: Final = DATA_DIR / "slips"
THUMBNAIL_SIZE: Final = (90, 62)
MAX_ASPECT_GAP: Final = 0.02  # width/height within 2 % of the sample's
MAX_MEAN_GAP: Final = 0.15  # mean absolute difference of the thumbnails, 0..1
MAX_WORST_GAP: Final = (
    0.12  # no thumbnail pixel further than this (a JPEG stays under 0.06, a new name is over 0.2)
)
RUNNER_UP_FACTOR: Final = 2.0  # the next-closest sample must be at least twice as far


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


@dataclass(frozen=True, slots=True)
class _Sample:
    name: str
    aspect: float
    thumbnail: np.ndarray
    metadata: dict[str, Any]


def _thumbnail(image: Image.Image) -> np.ndarray:
    gray = image.convert("L").resize(THUMBNAIL_SIZE, Image.Resampling.BILINEAR)
    return np.asarray(gray, dtype=np.float64) / 255.0


@cache
def _samples(directory: Path) -> tuple[_Sample, ...]:
    """Thumbnails and answer keys of the committed sample slips, read once per directory."""
    samples = []
    for path in sorted(directory.glob("*.png")):
        data = path.read_bytes()
        metadata = read_embedded_slip(data)
        if metadata is None:
            continue
        with Image.open(io.BytesIO(data)) as opened:
            samples.append(_Sample(path.name, opened.width / opened.height, _thumbnail(opened), metadata))
    return tuple(samples)


def match_sample(image: bytes, directory: Path = SAMPLE_SLIPS_DIR) -> dict[str, Any] | None:
    """The answer key of the sample slip `image` is a re-encoded copy of, or None (see the module docstring)."""
    with Image.open(io.BytesIO(image)) as opened:
        aspect = opened.width / opened.height
        thumbnail = _thumbnail(opened)
    gaps = []
    for sample in _samples(directory):
        if abs(aspect - sample.aspect) > MAX_ASPECT_GAP * sample.aspect:
            continue
        diff = np.abs(thumbnail - sample.thumbnail)
        gaps.append((float(diff.max()), float(diff.mean()), sample))
    if not gaps:
        return None
    gaps.sort(key=lambda gap: gap[0])
    worst, mean, best = gaps[0]
    runner_up = gaps[1][0] if len(gaps) > 1 else float("inf")
    if mean > MAX_MEAN_GAP or worst > MAX_WORST_GAP or worst * RUNNER_UP_FACTOR >= runner_up:
        return None
    logger.info("simulated vision: image matches the sample %s", best.name)
    return best.metadata


class SimulatedSlipReader:
    """Reads slip data embedded in sample PNGs (or a re-encoded copy of one); unknown images read at 0.3."""

    def __init__(self, *, samples_dir: Path = SAMPLE_SLIPS_DIR) -> None:
        self._samples_dir = samples_dir

    async def read_slip(self, image: bytes, mime_type: str) -> SlipExtraction:
        if not image:
            raise IntegrationError("sarvam_vision", "empty image")
        try:
            metadata = read_embedded_slip(image)
            if metadata is None:
                metadata = match_sample(image, self._samples_dir)
        except Exception as exc:  # undecodable upload: simulated vision cannot read it either
            logger.warning("simulated vision: image could not be decoded (%s)", type(exc).__name__)
            metadata = None
        if metadata is None:
            logger.info("simulated vision: no embedded slip data in %s image", mime_type)
            return SlipExtraction(confidence=UNREADABLE_CONFIDENCE, source=SIMULATED, raw={})
        return parse_slip(metadata, _embedded_confidence(metadata), source=SIMULATED)
