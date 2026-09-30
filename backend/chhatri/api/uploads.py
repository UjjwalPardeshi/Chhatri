"""Upload validation by content, not by client headers (SPEC §19, §21).

Images: ≤ 5 MB, JPEG/PNG/WebP by magic bytes, and Pillow must be able to open and verify the file
(Pillow picks its decoder from the same magic bytes, so a verified file is the format it claims). Audio: ≤ 5 MB, OGG/Opus, WebM, MP3, WAV or M4A by magic bytes, and ≤ 30 s (see
``chhatri.api.audio`` for how the duration is measured). The MIME type passed downstream is the
one derived from the bytes; the client's ``Content-Type`` is ignored.
"""

from __future__ import annotations

import io
import logging
import struct
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal

from PIL import Image, UnidentifiedImageError
from starlette.datastructures import UploadFile

from chhatri.api.audio import AUDIO_MIME, AudioFormatError, audio_duration_seconds, sniff_audio
from chhatri.api.errors import ApiError

logger = logging.getLogger(__name__)

__all__ = [
    "MAX_AUDIO_BYTES",
    "MAX_AUDIO_SECONDS",
    "MAX_IMAGE_BYTES",
    "ValidatedAudio",
    "ValidatedImage",
    "read_limited",
    "validate_audio",
    "validate_image",
]

MEGABYTE: Final = 1024 * 1024
MAX_IMAGE_BYTES: Final = 5 * MEGABYTE
MAX_AUDIO_BYTES: Final = 5 * MEGABYTE
MAX_AUDIO_SECONDS: Final = 30.0
ImageKind = Literal["jpeg", "png", "webp"]
IMAGE_MIME: Final = MappingProxyType({"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"})
PNG_MAGIC: Final = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC: Final = b"\xff\xd8\xff"


@dataclass(frozen=True, slots=True)
class ValidatedImage:
    data: bytes
    mime: str
    kind: ImageKind


@dataclass(frozen=True, slots=True)
class ValidatedAudio:
    data: bytes
    mime: str
    kind: str
    duration_s: float


async def read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Read at most ``max_bytes`` (+1 to detect overflow) from a multipart file (SPEC §19)."""
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ApiError(413, f"file exceeds {max_bytes // MEGABYTE} MB")
    return data


def sniff_image(data: bytes) -> ImageKind | None:
    """Identify JPEG/PNG/WebP from magic bytes only."""
    if data.startswith(JPEG_MAGIC):
        return "jpeg"
    if data.startswith(PNG_MAGIC):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def validate_image(data: bytes) -> ValidatedImage:
    """Validate an image upload (SPEC §19: ≤ 5 MB, jpeg/png/webp by content)."""
    if len(data) > MAX_IMAGE_BYTES:
        raise ApiError(413, f"image exceeds {MAX_IMAGE_BYTES // MEGABYTE} MB")
    kind = sniff_image(data)
    if kind is None:
        raise ApiError(415, "image must be JPEG, PNG or WebP")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        logger.warning("rejected unreadable %s upload: %s", kind, type(exc).__name__)
        raise ApiError(415, "image file is damaged or unreadable") from exc
    return ValidatedImage(data=data, mime=IMAGE_MIME[kind], kind=kind)


def validate_audio(data: bytes) -> ValidatedAudio:
    """Validate an audio upload (SPEC §19: ≤ 5 MB and ≤ 30 s; ogg/opus/webm/mp3/wav/m4a)."""
    if len(data) > MAX_AUDIO_BYTES:
        raise ApiError(413, f"audio exceeds {MAX_AUDIO_BYTES // MEGABYTE} MB")
    kind = sniff_audio(data)
    if kind is None:
        raise ApiError(415, "audio must be OGG/Opus, WebM, MP3, WAV or M4A")
    try:
        duration = audio_duration_seconds(data, kind)
    except (AudioFormatError, struct.error) as exc:
        logger.warning("rejected unreadable %s audio: %s", kind, exc)
        raise ApiError(415, "audio file is damaged or unreadable") from exc
    if duration > MAX_AUDIO_SECONDS:
        raise ApiError(413, f"audio is longer than {MAX_AUDIO_SECONDS:.0f} seconds")
    return ValidatedAudio(data=data, mime=AUDIO_MIME[kind], kind=kind, duration_s=round(duration, 2))
