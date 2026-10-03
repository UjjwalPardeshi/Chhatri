"""Sample hospital admission slips (SPEC §13, §17.2, §24.1).

`render_slip` draws a readable admission slip, visibly stamped "SAMPLE" and captioned as a
simulated document, and embeds what a reader would extract as a PNG ``tEXt`` chunk with keyword
``chhatri:slip`` (JSON, sorted keys). The simulated `SlipReader` reads that chunk back through
`read_embedded_slip`, so the offline demo is deterministic. `render_unreadable_slip` produces a
genuinely illegible photo (heavy blur) whose embedded extraction has no fields and low confidence.
Rendering uses Pillow's bundled scalable font, so output does not depend on system fonts.

A slip may name its treating doctor (`doctor_name`, `doctor_registration_no`): the name is printed as a table row and
again under the signature line with "Reg. No: <number>", as a hospital stamp would print it. A slip never carries the
doctor's phone or chat: the directory alone says how to reach a doctor.
"""

from __future__ import annotations

import io
import json
import logging
import struct
import zlib
from datetime import date
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, PngImagePlugin

logger = logging.getLogger(__name__)

SLIP_KEY = "chhatri:slip"
DOCUMENT_TYPE = "admission_slip"
READABLE_CONFIDENCE = 0.94
UNREADABLE_CONFIDENCE = 0.22
SIZE = (900, 700)  # tall enough for the doctor row and the signature block above the caption
MARGIN = 48
PAPER, INK, MUTED, RULE, STAMP = "#fbfaf6", "#1d2433", "#5b6475", "#c9ced8", "#c62828"
HEADER_BAND = "#e3ecf7"
ROW_TOP, ROW_STEP = 212, 56
SIGNATURE_TOP = 532
SIGNATURE_WIDTH = 330
BLUR_RADIUS = 12
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_TEXT_CHUNK = 64 * 1024


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _check_text(**fields: str) -> None:
    for name, value in fields.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")


def _check_optional_text(**fields: str | None) -> None:
    _check_text(**{name: value for name, value in fields.items() if value is not None})


def _draw_stamp(draw: ImageDraw.ImageDraw) -> None:
    """Red "SAMPLE" stamp (top right, as on deck slide 7) and a simulated-document caption."""
    box = (SIZE[0] - MARGIN - 190, 30, SIZE[0] - MARGIN, 84)
    draw.rectangle(box, outline=STAMP, width=4)
    draw.text(
        ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2), "SAMPLE", fill=STAMP, font=_font(34), anchor="mm"
    )
    caption = "SAMPLE · simulated document for the Chhatri demo · not a medical record"
    draw.text((SIZE[0] // 2, SIZE[1] - 26), caption, fill=STAMP, font=_font(17), anchor="mm")


def _draw_slip(
    patient_name: str,
    admitted: date,
    hospital: str,
    diagnosis: str,
    doctor: str | None,
    registration: str | None,
) -> Image.Image:
    image = Image.new("RGB", SIZE, PAPER)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, SIZE[0], 112), fill=HEADER_BAND)
    draw.text((MARGIN, 30), hospital, fill=INK, font=_font(36))
    draw.text((MARGIN, 76), "In-patient department", fill=MUTED, font=_font(20))
    draw.text((MARGIN, 140), "ADMISSION SLIP", fill=INK, font=_font(28))
    draw.line((MARGIN, 182, SIZE[0] - MARGIN, 182), fill=RULE, width=2)
    rows = [
        ("Patient name", patient_name),
        ("Date of admission", admitted.strftime("%d/%m/%Y")),
        ("Provisional diagnosis", diagnosis),
        ("Ward", "General medicine"),
    ]
    if doctor is not None:
        rows.append(("Treating doctor", doctor))
    for i, (label, value) in enumerate(rows):
        y = ROW_TOP + i * ROW_STEP
        draw.text((MARGIN, y), label, fill=MUTED, font=_font(20))
        draw.text((MARGIN + 260, y - 4), value, fill=INK, font=_font(28))
    _draw_signature(draw, doctor, registration)
    return image


def _draw_signature(draw: ImageDraw.ImageDraw, doctor: str | None, registration: str | None) -> None:
    """Signature line, then the doctor's name and registration number as their stamp prints them."""
    left = SIZE[0] - MARGIN - SIGNATURE_WIDTH
    draw.line((left, SIGNATURE_TOP, SIZE[0] - MARGIN, SIGNATURE_TOP), fill=INK, width=2)
    lines = [(doctor, INK, 24)] if doctor is not None else []
    if registration is not None:
        lines.append((f"Reg. No: {registration}", INK, 22))
    lines.append(("Medical officer", MUTED, 18))
    y = SIGNATURE_TOP + 10
    for text, colour, size in lines:
        draw.text((left, y), text, fill=colour, font=_font(size))
        y += size + 10


def _png(image: Image.Image, payload: dict[str, Any]) -> bytes:
    info = PngImagePlugin.PngInfo()
    info.add_text(SLIP_KEY, json.dumps(payload, sort_keys=True))  # ASCII JSON -> always tEXt
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", pnginfo=info, optimize=True)
    return buffer.getvalue()


def slip_payload(patient_name: str | None, admitted: date | None, hospital: str | None,
                 diagnosis: str | None, confidence: float, *, doctor_name: str | None = None,
                 doctor_registration_no: str | None = None) -> dict[str, Any]:  # fmt: skip
    """The embedded extraction; field names follow `SlipExtraction` (SPEC §3)."""
    return {
        "patient_name": patient_name,
        "admission_date": admitted.isoformat() if admitted else None,
        "discharge_date": None,
        "hospital_name": hospital,
        "diagnosis": diagnosis,
        "document_type": DOCUMENT_TYPE if patient_name else None,
        "doctor_name": doctor_name,
        "doctor_registration_no": doctor_registration_no,
        "confidence": confidence,
        "sample": True,
    }


def render_slip(
    patient_name: str,
    admitted: date,
    hospital: str,
    diagnosis: str,
    *,
    sample_label: bool = True,
    doctor_name: str | None = None,
    doctor_registration_no: str | None = None,
) -> bytes:
    """Readable admission slip PNG with the ``chhatri:slip`` tEXt chunk (SPEC §24.1)."""
    _check_text(patient_name=patient_name, hospital=hospital, diagnosis=diagnosis)
    _check_optional_text(doctor_name=doctor_name, doctor_registration_no=doctor_registration_no)
    image = _draw_slip(patient_name, admitted, hospital, diagnosis, doctor_name, doctor_registration_no)
    if sample_label:
        _draw_stamp(ImageDraw.Draw(image))
    payload = slip_payload(
        patient_name,
        admitted,
        hospital,
        diagnosis,
        READABLE_CONFIDENCE,
        doctor_name=doctor_name,
        doctor_registration_no=doctor_registration_no,
    )
    return _png(image, payload)


def render_unreadable_slip(
    patient_name: str,
    admitted: date,
    hospital: str,
    diagnosis: str,
    *,
    doctor_name: str | None = None,
    doctor_registration_no: str | None = None,
) -> bytes:
    """A blurred, illegible photo of the same slip (doctor included); nothing is extractable (low confidence)."""
    _check_text(patient_name=patient_name, hospital=hospital, diagnosis=diagnosis)
    _check_optional_text(doctor_name=doctor_name, doctor_registration_no=doctor_registration_no)
    image = _draw_slip(
        patient_name, admitted, hospital, diagnosis, doctor_name, doctor_registration_no
    ).filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
    _draw_stamp(ImageDraw.Draw(image))
    return _png(image, slip_payload(None, None, None, None, UNREADABLE_CONFIDENCE))


def _text_chunks(png: bytes) -> dict[str, bytes]:
    """tEXt chunks of a PNG without decoding pixels; ValueError on a malformed stream."""
    if not png.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG")
    chunks: dict[str, bytes] = {}
    offset = len(PNG_SIGNATURE)
    while offset + 12 <= len(png):
        length, kind = struct.unpack(">I4s", png[offset : offset + 8])
        body = png[offset + 8 : offset + 8 + length]
        crc = png[offset + 8 + length : offset + 12 + length]
        if len(body) != length or len(crc) != 4 or zlib.crc32(kind + body) != struct.unpack(">I", crc)[0]:
            raise ValueError("truncated or corrupt PNG chunk")
        if kind == b"IEND":
            return chunks
        if kind == b"tEXt" and length <= MAX_TEXT_CHUNK and b"\x00" in body:
            keyword, text = body.split(b"\x00", 1)
            chunks[keyword.decode("latin-1")] = text
        offset += 12 + length
    raise ValueError("PNG has no IEND chunk")


def read_embedded_slip(png: bytes) -> dict | None:
    """The embedded slip JSON, or None when the image is not a PNG or carries no valid chunk."""
    try:
        text = _text_chunks(png).get(SLIP_KEY)
        payload = json.loads(text.decode("latin-1")) if text is not None else None
    except ValueError as exc:  # includes json.JSONDecodeError
        logger.info("no readable %s chunk: %s", SLIP_KEY, exc)
        return None
    if payload is not None and not isinstance(payload, dict):
        logger.info("%s chunk is not a JSON object", SLIP_KEY)
        return None
    return payload
