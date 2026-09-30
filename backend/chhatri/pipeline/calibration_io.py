"""Writing ``backend/artifacts/calibration.json`` (SPEC §17.4, §24.1; decision B6).

The file holds exactly the six `Calibration` fields, read back by `chhatri.sim.calibration
.load_calibration`. The text is stable: sorted keys, two-space indent, ASCII, a trailing newline,
floats as Python's shortest round-trip repr, so an unchanged calibration rewrites identical bytes
and `write_calibration` leaves an identical file untouched.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

from chhatri.sim.types import Calibration

__all__ = ["calibration_json", "calibration_text", "write_calibration"]

logger = logging.getLogger(__name__)

INDENT = 2


def calibration_json(calibration: Calibration) -> dict[str, Any]:
    """The JSON object of `calibration` (ValueError for non-finite or non-positive numbers)."""
    scales = {zone: float(scale) for zone, scale in sorted(calibration.zone_rain_scale.items())}
    numbers = [*scales.values(), float(calibration.z9_slow_depth), float(calibration.z7_other_scale)]
    if any(not math.isfinite(v) for v in numbers):
        raise ValueError("calibration values must be finite")
    if calibration.anil_base_day_paise <= 0:
        raise ValueError("anil_base_day_paise must be positive")
    return {
        "anil_base_day_paise": int(calibration.anil_base_day_paise),
        "z7_other_scale": float(calibration.z7_other_scale),
        "z7_tune_base_day_paise": calibration.z7_tune_base_day_paise,
        "z7_tune_merchant_id": calibration.z7_tune_merchant_id,
        "z9_slow_depth": float(calibration.z9_slow_depth),
        "zone_rain_scale": scales,
    }


def calibration_text(calibration: Calibration) -> str:
    return json.dumps(calibration_json(calibration), indent=INDENT, sort_keys=True) + "\n"


def write_calibration(path: Path, calibration: Calibration) -> bool:
    """Write the file when its text changes; True when written. The write is atomic (rename)."""
    text = calibration_text(calibration)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        logger.info("calibration unchanged: %s", path)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    logger.info("wrote %s", path)
    return True
