"""GET /api/media/{id} serves a metadata-free copy of every stored image (design D4, finding: EXIF/GPS served openly).

The route has no token (the console's `<img>` uses the URL), so what it serves must carry nothing beyond the pixels:
no EXIF (a phone photo's place and time), no XMP, no ICC profile and no PNG text chunk (a sample slip's answer key).
Audio is served exactly as stored. An image that cannot be decoded is not served at all.
"""

from __future__ import annotations

import io

import numpy as np
from httpx import AsyncClient
from PIL import Image, PngImagePlugin

from tests.api import media_samples as media
from tests.api.fakes import FakeAppState
from tests.api.helpers import error_of

GPS_IFD = 0x8825
DATETIME_ORIGINAL = 0x9003
EXIF_IFD = 0x8769
MAKE = 0x010F
HEADERS = {"cache-control": "no-store", "x-content-type-options": "nosniff", "content-disposition": "inline"}


def _jpeg_with_exif_and_gps() -> bytes:
    image = Image.new("RGB", (64, 48), (30, 120, 200))
    exif = Image.Exif()
    exif[MAKE] = "PhoneCo"
    exif.get_ifd(EXIF_IFD)[DATETIME_ORIGINAL] = "2025:08:20 11:21:00"
    exif.get_ifd(GPS_IFD).update({1: "N", 2: (19.0, 0.0, 0.0), 3: "E", 4: (72.0, 50.0, 0.0)})
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif.tobytes(), icc_profile=b"\x00" * 128)
    return out.getvalue()


def _png_with_text_chunk() -> bytes:
    info = PngImagePlugin.PngInfo()
    info.add_text("chhatri:slip", '{"patient_name": "Anil R. Jadhav"}')
    info.add_text("Comment", "taken at home")
    out = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 30, 30)).save(out, format="PNG", pnginfo=info)
    return out.getvalue()


async def _served(client: AsyncClient, state: FakeAppState, data: bytes, mime: str) -> bytes:
    state.runtime.store.put_media(data, mime, "MD-000001")
    response = await client.get("/api/media/MD-000001")
    assert response.status_code == 200 and response.headers["content-type"] == mime
    assert {k: response.headers[k] for k in HEADERS} == HEADERS
    return response.content


async def test_a_jpeg_comes_back_without_exif_gps_or_icc(
    client: AsyncClient, fake_state: FakeAppState
) -> None:
    original = _jpeg_with_exif_and_gps()
    with Image.open(io.BytesIO(original)) as before:
        assert before.getexif().get_ifd(GPS_IFD) and before.info.get("icc_profile")
    served = await _served(client, fake_state, original, "image/jpeg")
    assert b"PhoneCo" not in served and b"Exif" not in served
    with Image.open(io.BytesIO(served)) as after:
        assert after.format == "JPEG" and after.size == (64, 48)
        assert not after.getexif() and "icc_profile" not in after.info and "exif" not in after.info
        assert np.abs(np.asarray(after, float) - (30, 120, 200)).mean() < 4  # the same picture


async def test_a_png_comes_back_without_text_chunks(client: AsyncClient, fake_state: FakeAppState) -> None:
    original = _png_with_text_chunk()
    served = await _served(client, fake_state, original, "image/png")
    assert b"tEXt" not in served and b"chhatri:slip" not in served and b"Anil" not in served
    with Image.open(io.BytesIO(served)) as after, Image.open(io.BytesIO(original)) as before:
        assert after.format == "PNG" and not after.text  # type: ignore[attr-defined]  # PngImageFile.text
        assert np.array_equal(np.asarray(after), np.asarray(before))


async def test_audio_is_served_as_stored(client: AsyncClient, fake_state: FakeAppState) -> None:
    audio = media.ogg_opus_bytes(3)
    assert await _served(client, fake_state, audio, "audio/ogg") == audio


async def test_an_image_that_cannot_be_decoded_is_not_served(
    client: AsyncClient, fake_state: FakeAppState
) -> None:
    fake_state.runtime.store.put_media(b"\xff\xd8\xff\xe0 not really a jpeg", "image/jpeg", "MD-000001")
    error_of(await client.get("/api/media/MD-000001"), 404, "not_found")
    fake_state.runtime.store.put_media(
        media.image_bytes("GIF"), "image/gif", "MD-000002"
    )  # cannot be cleaned
    error_of(await client.get("/api/media/MD-000002"), 404, "not_found")


async def test_a_cleaned_copy_is_reused(client: AsyncClient, fake_state: FakeAppState) -> None:
    original = _jpeg_with_exif_and_gps()
    first = await _served(client, fake_state, original, "image/jpeg")
    assert (await client.get("/api/media/MD-000001")).content == first
