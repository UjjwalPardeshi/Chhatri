"""The S4 slip set (AI evaluation plan 4.4; AC-EVAL-08): a balanced, seeded set of synthetic slips and its manifest.

It extends `chhatri.sim.slips` with the four kinds of `chhatri.backtest.slips` (balanced, not the backtest's 82% clean
mix), the five hospitals and diagnoses, and four named degradation levels (rotation and blur). The same seed gives the
same manifest and the same image bytes. Every image keeps the SAMPLE stamp and its embedded answer key, which only the
simulated reader uses: the pre-check strips it before a live reader sees the photo (fs-02 7.3.1, AC-EVAL-09).

`human_readable` is a rule here (an UNREADABLE kind or a heavy degradation is not), and `expected_status` follows from
it. The plan asks a person to confirm it by looking at the images before a live run is scored.
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Final

import numpy as np
from PIL import Image, ImageFilter, PngImagePlugin

from chhatri.backtest.slips import DIAGNOSES, HOSPITALS, OTHER_PATIENT_NAME, SlipKind
from chhatri.sim.slips import DOCUMENT_TYPE, SLIP_KEY, render_slip, render_unreadable_slip

__all__ = ["DEGRADATIONS", "KINDS", "MANIFEST", "GeneratedSlip", "generate_slips", "write_slip_set"]

KINDS: Final = tuple(kind.value for kind in SlipKind)
# Named levels set in code (plan 4.4): rotation in degrees and Gaussian blur radius in pixels.
DEGRADATIONS: Final = {"none": (0.0, 0.0), "light": (1.5, 0.6), "medium": (3.0, 1.4), "heavy": (6.0, 4.0)}
PATIENTS: Final = ("Anil R. Jadhav", "Ramesh Kale", "Sunita Patil", "Farida Shaikh", "Vijay More")
FIRST_DAY: Final = date(2025, 8, 20)
SLIPGEN_STREAM: Final = 2501  # this generator's own RNG stream id
MANIFEST: Final = "slips_manifest.jsonl"


@dataclass(frozen=True, slots=True)
class GeneratedSlip:
    """One manifest row and its PNG bytes."""

    row: dict[str, Any]
    image: bytes


def _degrade(png: bytes, level: str) -> bytes:
    """`png` rotated and blurred by `level`, re-encoded with its embedded answer key kept."""
    angle, radius = DEGRADATIONS[level]
    if angle == 0.0 and radius == 0.0:
        return png
    with Image.open(io.BytesIO(png)) as opened:
        key = opened.text[SLIP_KEY]  # type: ignore[attr-defined]  # PngImageFile.text
        image = opened.convert("RGB").rotate(angle, expand=True, fillcolor="white")
    if radius:
        image = image.filter(ImageFilter.GaussianBlur(radius))
    info = PngImagePlugin.PngInfo()
    info.add_text(SLIP_KEY, key)
    out = io.BytesIO()
    image.save(out, format="PNG", pnginfo=info, optimize=True)
    return out.getvalue()


def _truth(kind: str, patient: str, admitted: date, hospital: str) -> dict[str, Any]:
    if kind == SlipKind.UNREADABLE:
        return {
            "patient_name": None,
            "admission_date": None,
            "discharge_date": None,
            "hospital_name": None,
            "document_type": None,
        }
    return {
        "patient_name": patient,
        "admission_date": admitted.isoformat(),
        "discharge_date": None,
        "hospital_name": hospital,
        "document_type": DOCUMENT_TYPE,
    }


def _one(rng: np.random.Generator, number: int, kind: str) -> GeneratedSlip:
    owner = PATIENTS[int(rng.integers(len(PATIENTS)))]
    hospital = HOSPITALS[int(rng.integers(len(HOSPITALS)))]
    diagnosis = DIAGNOSES[int(rng.integers(len(DIAGNOSES)))]
    level = tuple(DEGRADATIONS)[int(rng.integers(len(DEGRADATIONS)))]
    split = "held_out" if rng.random() < 0.5 else "dev"
    patient = OTHER_PATIENT_NAME if kind == SlipKind.OTHER_NAME else owner
    admitted = FIRST_DAY + timedelta(days=1) if kind == SlipKind.LATE_ADMISSION else FIRST_DAY
    if kind == SlipKind.UNREADABLE:
        png = render_unreadable_slip(owner, FIRST_DAY, hospital, diagnosis)
    else:
        png = render_slip(patient, admitted, hospital, diagnosis)
    image = _degrade(png, level)
    readable = kind != SlipKind.UNREADABLE and level != "heavy"
    slip_id = f"s-{number:03d}"
    row = {
        "id": slip_id,
        "file": f"{slip_id}.png",
        "kind": kind,
        "origin": "rendered",
        "degradation": level,
        "script": "latin",
        "owner_name": owner,
        "truth": _truth(kind, patient, admitted, hospital),
        "human_readable": readable,
        "expected_status": "READY" if readable else "RETAKE",
        "split": split,
        "synthetic": True,
        "sha256": hashlib.sha256(image).hexdigest(),
    }
    return GeneratedSlip(row, image)


def generate_slips(seed: int, *, per_kind: int = 6) -> tuple[GeneratedSlip, ...]:
    """`per_kind` slips of each of the four kinds, interleaved, from `seed`."""
    if per_kind < 1:
        raise ValueError("per_kind must be at least 1")
    rng = np.random.default_rng(np.random.SeedSequence([seed, SLIPGEN_STREAM]))
    order = [kind for _ in range(per_kind) for kind in KINDS]
    return tuple(_one(rng, number, kind) for number, kind in enumerate(order, start=1))


def write_slip_set(seed: int, out_dir: Path, *, per_kind: int = 6) -> Path:
    """Write the images and `slips_manifest.jsonl` into `out_dir` (backend/var/evals/slips/, ignored by git)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    slips = generate_slips(seed, per_kind=per_kind)
    for slip in slips:
        (out_dir / slip.row["file"]).write_bytes(slip.image)
    manifest = out_dir / MANIFEST
    manifest.write_text(
        "".join(json.dumps(s.row, ensure_ascii=False, sort_keys=True) + "\n" for s in slips), encoding="utf-8"
    )
    return manifest
