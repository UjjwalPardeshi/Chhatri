#!/usr/bin/env python3
"""Calibration script for golden numbers (SPEC §17.4, §24).

Deterministic search (bisection/secant on integers/bounded floats, no randomness)
to find calibration values that match:

(a) Anil's expected Tuesday = ₹4,380 (±₹10)
(b) Zone indices: Z7 37%, Z3 38%, Z12 47% (within ±1%)
(c) Z9 shows 61% with no trigger (slow_day)
(d) Z7 total paid = ₹58,900 (exact, after scaling other merchants + tune)

Writes artifacts/calibration.json (sorted keys, stable formatting).
If a calibration value changes training history, retrain and iterate to fixed point
(bounded iterations; fail loudly if not convergent).
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def ensure_backend_dir() -> Path:
    """Return backend directory."""
    script_dir = Path(__file__).resolve().parent
    backend_dir = script_dir.parent
    if not (backend_dir / "chhatri").exists():
        raise RuntimeError(f"Cannot find chhatri package in {backend_dir}")
    return backend_dir


def main():
    """Main calibration flow."""
    backend_dir = ensure_backend_dir()
    data_dir = backend_dir / "data"
    artifacts_dir = backend_dir / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    logger.info("Calibration: This is a placeholder that will be filled by D1")
    logger.info("Default calibration values are used from chhatri/sim/calibration.py")

    # For now, just ensure the default calibration is saved
    from chhatri.sim.calibration import load_calibration

    calibration = load_calibration(data_dir)

    # Save to artifacts
    calib_json = {
        "anil_base_day_paise": calibration.anil_base_day_paise,
        "zone_rain_scale": dict(calibration.zone_rain_scale),
        "z9_slow_depth": calibration.z9_slow_depth,
        "z7_other_scale": calibration.z7_other_scale,
        "z7_tune_merchant_id": calibration.z7_tune_merchant_id,
        "z7_tune_base_day_paise": calibration.z7_tune_base_day_paise,
    }

    calib_path = artifacts_dir / "calibration.json"
    with open(calib_path, "w") as f:
        json.dump(calib_json, f, indent=2, sort_keys=True)

    logger.info(f"Wrote {calib_path}")
    logger.info(
        f"Calibration: Anil={calib_json['anil_base_day_paise']}, "
        f"Z9 depth={calib_json['z9_slow_depth']}"
    )


if __name__ == "__main__":
    main()
