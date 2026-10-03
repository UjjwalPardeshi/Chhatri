#!/usr/bin/env python3
"""Regenerate the sample admission slips in backend/data/slips (SPEC §17.2).

- anil_admission_slip.png: "Anil R. Jadhav", admitted 2025-08-20, "Viral fever", KEM Hospital, Parel,
  treating doctor "Dr S. Rao", "Reg. No: MMC-2011-45817" (the directory's doctor at KEM)
- mismatch_admission_slip.png: "Sunil Pawar", same dates, hospital and doctor (the HUMAN live test, §13.6)
- blurry_slip.png: the Anil slip photographed out of focus; unreadable, low confidence

Deterministic: re-running produces byte-identical files.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

from chhatri.config import DATA_DIR
from chhatri.sim.scenarios import SLIP_ANIL, SLIP_BLURRY, SLIP_MISMATCH
from chhatri.sim.slips import render_slip, render_unreadable_slip

logger = logging.getLogger("make_slips")

ADMITTED = date(2025, 8, 20)
HOSPITAL = "KEM Hospital, Parel"
DIAGNOSIS = "Viral fever"
ANIL_PATIENT = "Anil R. Jadhav"
MISMATCH_PATIENT = "Sunil Pawar"
DOCTOR_NAME = "Dr S. Rao"
DOCTOR_REG = "MMC-2011-45817"


def build_slips() -> dict[str, bytes]:
    """File name -> PNG bytes for the three sample slips."""
    doctor, reg = DOCTOR_NAME, DOCTOR_REG
    return {
        SLIP_ANIL: render_slip(
            ANIL_PATIENT, ADMITTED, HOSPITAL, DIAGNOSIS, doctor_name=doctor, doctor_registration_no=reg
        ),
        SLIP_MISMATCH: render_slip(
            MISMATCH_PATIENT, ADMITTED, HOSPITAL, DIAGNOSIS, doctor_name=doctor, doctor_registration_no=reg
        ),
        SLIP_BLURRY: render_unreadable_slip(
            ANIL_PATIENT, ADMITTED, HOSPITAL, DIAGNOSIS, doctor_name=doctor, doctor_registration_no=reg
        ),
    }


def write_slips(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, png in build_slips().items():
        path = out_dir / name
        path.write_bytes(png)
        logger.info("wrote %s (%d bytes)", path, len(png))
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DATA_DIR / "slips", help="output directory")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    write_slips(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
