"""SPEC §17.2, §24.1: sample slips, their embedded extraction and the committed PNGs."""

from __future__ import annotations

import inspect
import io
import struct
import zlib
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from chhatri.sim.slips import (
    READABLE_CONFIDENCE,
    SLIP_KEY,
    UNREADABLE_CONFIDENCE,
    read_embedded_slip,
    render_slip,
    render_unreadable_slip,
    slip_payload,
)

from .conftest import load_script

ADMITTED = date(2025, 8, 20)


def test_render_and_read_round_trip() -> None:
    png = render_slip("Anil R. Jadhav", ADMITTED, "KEM Hospital, Parel", "Viral fever")
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert read_embedded_slip(png) == {
        "patient_name": "Anil R. Jadhav",
        "admission_date": "2025-08-20",
        "discharge_date": None,
        "hospital_name": "KEM Hospital, Parel",
        "diagnosis": "Viral fever",
        "document_type": "admission_slip",
        "doctor_name": None,
        "doctor_registration_no": None,
        "confidence": READABLE_CONFIDENCE,
        "sample": True,
    }
    assert png == render_slip("Anil R. Jadhav", ADMITTED, "KEM Hospital, Parel", "Viral fever")
    assert Image.open(__import__("io").BytesIO(png)).text[SLIP_KEY]  # a real tEXt chunk PIL can read


def test_sample_label_is_drawn() -> None:
    labelled = np.asarray(Image.open(__import__("io").BytesIO(render_slip("A B", ADMITTED, "H", "D"))))
    plain = np.asarray(
        Image.open(__import__("io").BytesIO(render_slip("A B", ADMITTED, "H", "D", sample_label=False)))
    )
    red = (labelled[..., 0] > 150) & (labelled[..., 1] < 90) & (labelled[..., 2] < 90)
    assert red.sum() > 500 and not ((plain[..., 0] > 150) & (plain[..., 1] < 90) & (plain[..., 2] < 90)).any()


def test_unreadable_slip_is_blurred_and_empty() -> None:
    sharp = np.asarray(
        Image.open(__import__("io").BytesIO(render_slip("Anil R. Jadhav", ADMITTED, "H", "D"))), float
    )
    png = render_unreadable_slip("Anil R. Jadhav", ADMITTED, "H", "D")
    blurred = np.asarray(Image.open(__import__("io").BytesIO(png)), float)
    body = (slice(200, 440), slice(40, 700))  # the field rows, away from the SAMPLE stamp
    assert (
        np.abs(np.diff(blurred[body].mean(axis=2), axis=1)).max()
        < 0.2 * np.abs(np.diff(sharp[body].mean(axis=2), axis=1)).max()
    )
    data = read_embedded_slip(png)
    assert data is not None and data["patient_name"] is None and data["confidence"] < 0.5


def test_render_validates_inputs() -> None:
    with pytest.raises(ValueError, match="patient_name"):
        render_slip(" ", ADMITTED, "KEM", "fever")
    with pytest.raises(ValueError, match="hospital"):
        render_unreadable_slip("A", ADMITTED, "", "fever")


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


def test_read_embedded_slip_rejects_bad_input() -> None:
    signature = b"\x89PNG\r\n\x1a\n"
    assert read_embedded_slip(b"GIF89a....") is None
    assert read_embedded_slip(signature + _chunk(b"IEND", b"")) is None  # no chunk
    assert (
        read_embedded_slip(
            signature + _chunk(b"tEXt", SLIP_KEY.encode() + b"\x00{bad") + _chunk(b"IEND", b"")
        )
        is None
    )
    assert (
        read_embedded_slip(signature + _chunk(b"tEXt", SLIP_KEY.encode() + b"\x00[1]") + _chunk(b"IEND", b""))
        is None
    )
    good = signature + _chunk(b"tEXt", SLIP_KEY.encode() + b'\x00{"a": 1}') + _chunk(b"IEND", b"")
    assert read_embedded_slip(good) == {"a": 1}
    assert read_embedded_slip(good[:-3]) is None  # truncated
    corrupt = bytearray(good)
    corrupt[20] ^= 0xFF
    assert read_embedded_slip(bytes(corrupt)) is None
    assert read_embedded_slip(signature + _chunk(b"tEXt", b"other\x00x")) is None  # no IEND


def test_committed_slips_are_regenerated_by_make_slips(tmp_path: Path, data_dir: Path) -> None:
    make_slips = load_script("make_slips")
    assert make_slips.main(["--out", str(tmp_path)]) == 0
    sizes = set()
    for name in ("anil_admission_slip.png", "mismatch_admission_slip.png", "blurry_slip.png"):
        committed = (data_dir / "slips" / name).read_bytes()
        assert committed == (tmp_path / name).read_bytes(), f"{name} is stale: run scripts/make_slips.py"
        sizes.add(len(committed))
    assert len(sizes) == 3
    anil = read_embedded_slip((data_dir / "slips" / "anil_admission_slip.png").read_bytes())
    mismatch = read_embedded_slip((data_dir / "slips" / "mismatch_admission_slip.png").read_bytes())
    assert anil is not None and mismatch is not None
    assert (anil["patient_name"], anil["admission_date"], anil["diagnosis"], anil["hospital_name"]) == (
        "Anil R. Jadhav", "2025-08-20", "Viral fever", "KEM Hospital, Parel",
    )  # fmt: skip
    assert (mismatch["patient_name"], mismatch["admission_date"]) == ("Sunil Pawar", "2025-08-20")
    for key in (anil, mismatch):
        assert (key["doctor_name"], key["doctor_registration_no"]) == ("Dr S. Rao", "MMC-2011-45817")
        assert (key["hospital_name"], key["confidence"]) == ("KEM Hospital, Parel", READABLE_CONFIDENCE)
    blurry = read_embedded_slip((data_dir / "slips" / "blurry_slip.png").read_bytes())
    assert blurry is not None and blurry["confidence"] == UNREADABLE_CONFIDENCE
    assert not [k for k in FIELDS if blurry[k] is not None]


FIELDS = (
    "patient_name",
    "admission_date",
    "hospital_name",
    "document_type",
    "doctor_name",
    "doctor_registration_no",
)
DOCTOR = {"doctor_name": "Dr S. Rao", "doctor_registration_no": "MMC-2011-45817"}


def _pixels(png: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(png)).convert("L"), float)


def test_the_doctor_is_drawn_and_carried_in_the_answer_key() -> None:
    plain = render_slip("Anil R. Jadhav", ADMITTED, "KEM Hospital, Parel", "Viral fever")
    signed = render_slip("Anil R. Jadhav", ADMITTED, "KEM Hospital, Parel", "Viral fever", **DOCTOR)
    key = read_embedded_slip(signed)
    assert key is not None and {k: key[k] for k in DOCTOR} == DOCTOR
    assert key["patient_name"] == "Anil R. Jadhav" and key["admission_date"] == "2025-08-20"
    assert signed == render_slip("Anil R. Jadhav", ADMITTED, "KEM Hospital, Parel", "Viral fever", **DOCTOR)
    changed = np.abs(_pixels(signed) - _pixels(plain)) > 40
    rows, cols = np.nonzero(changed)
    assert changed.sum() > 1500  # two printed lines at least, not a speck
    height, width = _pixels(signed).shape
    assert (
        rows.min() > 120 and rows.max() < height - 40 and cols.max() < width
    )  # below the stamp, above the caption


def test_the_unreadable_slip_draws_the_doctor_blurred_and_keeps_no_fields() -> None:
    png = render_unreadable_slip("Anil R. Jadhav", ADMITTED, "KEM Hospital, Parel", "Viral fever", **DOCTOR)
    key = read_embedded_slip(png)
    assert key is not None and key["confidence"] == UNREADABLE_CONFIDENCE
    assert not [k for k in FIELDS if key[k] is not None]


def test_the_doctor_keywords_default_to_none() -> None:
    for function in (render_slip, render_unreadable_slip):
        params = inspect.signature(function).parameters
        assert params["doctor_name"].default is None and params["doctor_registration_no"].default is None
        assert params["doctor_name"].kind is inspect.Parameter.KEYWORD_ONLY
    payload = slip_payload("A", ADMITTED, "H", "D", 0.5)
    assert payload["doctor_name"] is None and payload["doctor_registration_no"] is None
    with pytest.raises(ValueError, match="doctor_name"):
        render_slip("A", ADMITTED, "H", "D", doctor_name=" ")
    with pytest.raises(ValueError, match="doctor_registration_no"):
        render_unreadable_slip("A", ADMITTED, "H", "D", doctor_registration_no="")
