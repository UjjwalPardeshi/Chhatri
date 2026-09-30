"""Upload validation by magic bytes, size and audio duration (SPEC §19, §21)."""

from __future__ import annotations

import io

import pytest
from fastapi import UploadFile

from chhatri.api.audio import AudioFormatError, audio_duration_seconds, sniff_audio
from chhatri.api.errors import ApiError
from chhatri.api.uploads import (
    MAX_AUDIO_BYTES,
    MAX_IMAGE_BYTES,
    read_limited,
    sniff_image,
    validate_audio,
    validate_image,
)
from tests.api import media_samples as media


@pytest.mark.parametrize(
    ("fmt", "kind", "mime"),
    [("PNG", "png", "image/png"), ("JPEG", "jpeg", "image/jpeg"), ("WEBP", "webp", "image/webp")],
)
def test_images_are_accepted_by_content(fmt: str, kind: str, mime: str) -> None:
    image = validate_image(media.image_bytes(fmt))
    assert (image.kind, image.mime) == (kind, mime)


def expect(status: int, fn: object, *args: object) -> ApiError:
    with pytest.raises(ApiError) as raised:
        fn(*args)  # type: ignore[operator]
    assert raised.value.status == status
    return raised.value


def test_image_with_wrong_magic_is_415() -> None:
    expect(415, validate_image, b"GIF89a" + b"\x00" * 64)
    assert sniff_image(b"%PDF-1.7") is None


def test_damaged_image_is_415() -> None:
    png = media.image_bytes("PNG")
    assert "damaged" in expect(415, validate_image, png[:40] + b"\x00" * 20).message


def test_image_whose_signature_lies_is_415() -> None:
    webp = media.image_bytes("WEBP")
    forged = webp[:8] + b"WEBP" + media.image_bytes("PNG")
    expect(415, validate_image, forged)


def test_image_over_five_megabytes_is_413() -> None:
    expect(413, validate_image, b"\x89PNG\r\n\x1a\n" + b"\x00" * MAX_IMAGE_BYTES)


def test_exact_audio_durations() -> None:
    assert audio_duration_seconds(media.wav_bytes(4), "wav") == 4.0
    assert audio_duration_seconds(media.ogg_opus_bytes(6), "ogg") == 6.0
    assert audio_duration_seconds(media.ogg_vorbis_bytes(2.5), "ogg") == 2.5


def test_webm_duration_from_info_or_blocks_or_size() -> None:
    assert audio_duration_seconds(media.webm_bytes(duration_ms=4200.0), "webm") == pytest.approx(4.2)
    blocks = media.webm_bytes(duration_ms=None, cluster_ms=3000, last_block_ms=1500)
    assert audio_duration_seconds(blocks, "webm") == pytest.approx(4.5)
    no_timing = media.webm_bytes(duration_ms=None, blocks=False)
    assert audio_duration_seconds(no_timing, "webm") == pytest.approx(len(no_timing) * 8 / 24_000)
    cut = media.webm_bytes(duration_ms=None, cluster_ms=3000, last_block_ms=1500)
    assert audio_duration_seconds(cut[: len(cut) - 3], "webm") == pytest.approx(3.0)


def test_mp3_and_m4a_are_estimated_as_an_upper_bound() -> None:
    assert audio_duration_seconds(media.mp3_bytes(40_000), "mp3") == 10.0
    assert audio_duration_seconds(media.m4a_bytes(40_000), "m4a") == 10.0


@pytest.mark.parametrize(
    ("data", "kind"),
    [
        (media.wav_bytes(1), "wav"),
        (media.ogg_opus_bytes(1), "ogg"),
        (media.webm_bytes(duration_ms=10.0), "webm"),
        (media.mp3_bytes(100), "mp3"),
        (b"\xff\xfb\x90\x00" + b"\x00" * 10, "mp3"),
        (media.m4a_bytes(100), "m4a"),
        (b"hello world!", None),
    ],
    ids=["wav", "ogg", "webm", "mp3-id3", "mp3-sync", "m4a", "text"],
)
def test_sniff_audio(data: bytes, kind: str | None) -> None:
    assert sniff_audio(data) == kind


@pytest.mark.parametrize(
    ("data", "mime", "seconds"),
    [
        (media.wav_bytes(4), "audio/wav", 4.0),
        (media.ogg_opus_bytes(6), "audio/ogg", 6.0),
        (media.webm_bytes(duration_ms=5000.0), "audio/webm", 5.0),
    ],
    ids=["wav", "opus", "webm"],
)
def test_valid_audio(data: bytes, mime: str, seconds: float) -> None:
    audio = validate_audio(data)
    assert (audio.mime, audio.duration_s) == (mime, seconds)


def test_audio_longer_than_thirty_seconds_is_413() -> None:
    assert "30 seconds" in expect(413, validate_audio, media.ogg_opus_bytes(31)).message
    expect(413, validate_audio, media.mp3_bytes(130_000))


def test_audio_over_five_megabytes_is_413() -> None:
    expect(413, validate_audio, b"OggS" + b"\x00" * MAX_AUDIO_BYTES)


def test_unknown_audio_is_415() -> None:
    expect(415, validate_audio, b"not audio at all")


@pytest.mark.parametrize(
    "data",
    [
        media.ogg_opus_bytes(2)[:50],
        b"OggS" + b"\x00" * 10,
        media.ogg_page(1, 0, 0, b"FLAC....", header_type=2),
        media.ogg_page(1, 0, 0, media.opus_head(), header_type=2),
        media.wav_bytes(1)[:20],
        b"RIFF\x10\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00",
        b"\x1a\x45\xdf\xa3\x00",
    ],
    ids=[
        "ogg-cut-header",
        "ogg-garbage",
        "ogg-flac",
        "ogg-no-audio",
        "wav-cut-fmt",
        "wav-short-fmt",
        "ebml-zero",
    ],
)
def test_damaged_audio_is_415(data: bytes) -> None:
    assert "damaged" in expect(415, validate_audio, data).message


def test_ogg_without_pages_is_an_audio_format_error() -> None:
    with pytest.raises(AudioFormatError):
        audio_duration_seconds(b"", "ogg")


async def test_read_limited_stops_after_the_limit() -> None:
    upload = UploadFile(io.BytesIO(b"x" * 11))
    with pytest.raises(ApiError) as raised:
        await read_limited(upload, 10)
    assert raised.value.status == 413
    assert await read_limited(UploadFile(io.BytesIO(b"x" * 10)), 10) == b"x" * 10


def test_wav_without_a_data_chunk_is_rejected() -> None:
    fmt = (
        b"fmt "
        + (16).to_bytes(4, "little")
        + b"\x01\x00\x01\x00"
        + (8000).to_bytes(4, "little") * 2
        + b"\x01\x00\x08\x00"
    )
    data = b"RIFF" + (4 + len(fmt)).to_bytes(4, "little") + b"WAVE" + fmt
    assert "damaged" in expect(415, validate_audio, data).message


def test_ogg_page_cut_inside_its_body_is_rejected() -> None:
    assert "damaged" in expect(415, validate_audio, media.ogg_opus_bytes(2)[:40]).message


@pytest.mark.parametrize(
    "data", [media.EBML_MAGIC, media.EBML_MAGIC + b"\x01\x00"], ids=["id-only", "cut-size"]
)
def test_webm_cut_inside_a_header_falls_back_to_the_size_estimate(data: bytes) -> None:
    assert audio_duration_seconds(data, "webm") == pytest.approx(len(data) * 8 / 24_000)


def test_webm_block_shorter_than_its_header_is_rejected() -> None:
    cluster = media.ebml(0x1F43B675, media.ebml(0xE7, b"\x00") + media.ebml(0xA3, b"\x81\x00"))
    assert "damaged" in expect(415, validate_audio, media.EBML_MAGIC + b"\x80" + cluster).message
