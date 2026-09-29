#!/usr/bin/env python3
"""Generate sample admission slips (SPEC §17.2, scripts section).

Creates:
- backend/data/slips/anil_admission_slip.png
- backend/data/slips/mismatch_admission_slip.png
- backend/data/slips/blurry_slip.png
"""

from datetime import date
from pathlib import Path

from chhatri.sim.slips import render_slip


def main():
    backend_dir = Path(__file__).resolve().parent.parent
    slips_dir = backend_dir / "data" / "slips"
    slips_dir.mkdir(parents=True, exist_ok=True)

    # Anil's admission slip
    anil_slip = render_slip(
        patient_name="Anil R. Jadhav",
        admitted=date(2025, 8, 20),
        hospital="KEM Hospital, Parel",
        diagnosis="Viral fever",
        sample_label=True
    )
    anil_path = slips_dir / "anil_admission_slip.png"
    anil_path.write_bytes(anil_slip)
    print(f"Wrote {anil_path}")

    # Mismatch slip (Sunil Pawar, but sent by Anil)
    mismatch_slip = render_slip(
        patient_name="Sunil Pawar",
        admitted=date(2025, 8, 20),
        hospital="KEM Hospital, Parel",
        diagnosis="Viral fever",
        sample_label=True
    )
    mismatch_path = slips_dir / "mismatch_admission_slip.png"
    mismatch_path.write_bytes(mismatch_slip)
    print(f"Wrote {mismatch_path}")

    # Blurry slip (low confidence - harder to read)
    blurry_slip = render_slip(
        patient_name="Anil R. Jadhav",
        admitted=date(2025, 8, 20),
        hospital="KEM Hospital, Parel",
        diagnosis="Viral fever",
        sample_label=True,
        confidence=0.55
    )
    blurry_path = slips_dir / "blurry_slip.png"
    blurry_path.write_bytes(blurry_slip)
    print(f"Wrote {blurry_path}")

    print("Admission slips generated successfully!")


if __name__ == "__main__":
    main()
