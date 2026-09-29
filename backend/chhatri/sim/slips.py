"""Slip rendering and extraction (SPEC §17.2, §24.1).

Renders PNG admission slips with embedded chhatri:slip JSON metadata.
Used by simulated vision extraction in scenarios.
"""

from __future__ import annotations

import io
import json
from datetime import date

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin


def render_slip(
    patient_name: str,
    admitted: date,
    hospital: str,
    diagnosis: str,
    *,
    sample_label: bool = True,
    confidence: float = 0.94
) -> bytes:
    """Render an admission slip PNG with embedded metadata.

    Args:
        patient_name: Patient name
        admitted: Admission date
        hospital: Hospital name
        diagnosis: Diagnosis or reason for admission
        sample_label: Whether to mark as "SAMPLE" (default True)
        confidence: OCR confidence score 0.0-1.0 (default 0.94, per SPEC §17.2)

    Returns:
        PNG bytes with tEXt chunk "chhatri:slip" containing JSON
    """
    # Create image (landscape, simple document layout)
    width, height = 800, 600
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)

    # Try to use a standard font; fall back to default
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        body_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except Exception:
        title_font = header_font = body_font = ImageFont.load_default()

    # Draw content
    y_pos = 30

    # Header: Hospital name
    draw.text((30, y_pos), hospital, fill="black", font=title_font)
    y_pos += 50

    # Draw a line
    draw.line([(30, y_pos), (770, y_pos)], fill="gray", width=2)
    y_pos += 20

    # Document type and date
    draw.text((30, y_pos), "ADMISSION SLIP", fill="black", font=header_font)
    draw.text((600, y_pos), f"Date: {admitted:%d/%m/%Y}", fill="black", font=body_font)
    y_pos += 40

    # Content fields
    fields = [
        (f"Patient Name: {patient_name}", y_pos),
        (f"Admission Date: {admitted:%d-%b-%Y}", y_pos + 40),
        (f"Diagnosis: {diagnosis}", y_pos + 80),
        ("Attending Physician: Dr. N.V. Deshpande, MBBS", y_pos + 120),
        ("Hospital: KEM Hospital, Parel, Mumbai", y_pos + 160),
    ]

    for text, pos_y in fields:
        draw.text((30, pos_y), text, fill="black", font=body_font)

    y_pos += 220

    # Sample watermark if needed
    if sample_label:
        draw.text((30, y_pos), "SAMPLE", fill="red", font=header_font)

    # Embed metadata in tEXt chunk
    metadata = {
        "patient_name": patient_name,
        "admission_date": admitted.isoformat(),
        "discharge_date": None,
        "hospital_name": hospital,
        "document_type": "admission_slip",
        "confidence": confidence
    }

    metadata_json = json.dumps(metadata)

    # Create PNG with tEXt chunk
    buf = io.BytesIO()
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text("chhatri:slip", metadata_json)
    img.save(buf, format="PNG", pnginfo=pnginfo)

    return buf.getvalue()


def read_embedded_slip(png: bytes) -> dict | None:
    """Read embedded slip metadata from PNG tEXt chunk.

    Args:
        png: PNG file bytes

    Returns:
        Parsed metadata dict or None if not found/invalid
    """
    try:
        img = Image.open(io.BytesIO(png))

        # Try to read tEXt chunk
        if hasattr(img, "info") and "chhatri:slip" in img.info:
            metadata_json = img.info["chhatri:slip"]
            return json.loads(metadata_json)
    except (OSError, KeyError, json.JSONDecodeError):
        # Not a valid PNG or missing metadata
        pass

    return None
