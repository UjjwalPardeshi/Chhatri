"""Calibration loading (SPEC §17.4, §24.1).

``scripts/calibrate.py`` writes ``backend/artifacts/calibration.json`` with exactly the six fields
of `Calibration`. `load_calibration` returns the documented defaults (the `Calibration()` field
defaults in ``chhatri.sim.types``) when the file is absent, and raises `ValueError` when it exists
but is malformed, so a broken artefact can never silently fall back to uncalibrated numbers.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from chhatri.sim.types import Calibration

__all__ = ["CALIBRATION_FILE", "MONSOON_ZONES", "Calibration", "load_calibration"]

logger = logging.getLogger(__name__)

CALIBRATION_FILE = "calibration.json"
MONSOON_ZONES: tuple[str, ...] = ("Z3", "Z7", "Z12")  # SPEC §17.2 triggered zones


class _CalibrationFile(BaseModel):
    """Schema of calibration.json; every key required, no extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    anil_base_day_paise: int = Field(gt=0)
    zone_rain_scale: dict[str, float]
    z9_slow_depth: float = Field(ge=0.0, lt=1.0)
    z7_other_scale: float = Field(gt=0.0)
    z7_tune_merchant_id: str | None = Field(pattern=r"^S-\d{4}$")
    z7_tune_base_day_paise: int | None = Field(gt=0)

    @field_validator("zone_rain_scale", mode="before")
    @classmethod
    def _coerce_scales(cls, value: object) -> object:
        if isinstance(value, dict):
            return {
                k: float(v) if isinstance(v, int) and not isinstance(v, bool) else v for k, v in value.items()
            }
        return value

    @field_validator("zone_rain_scale")
    @classmethod
    def _check_scales(cls, value: dict[str, float]) -> dict[str, float]:
        if set(value) != set(MONSOON_ZONES):
            raise ValueError(f"zone_rain_scale must have exactly {MONSOON_ZONES}, got {sorted(value)}")
        if any(not math.isfinite(v) or v <= 0 for v in value.values()):
            raise ValueError("zone_rain_scale values must be finite and > 0")
        return value

    @field_validator("z9_slow_depth", "z7_other_scale", mode="before")
    @classmethod
    def _int_to_float(cls, value: object) -> object:
        return float(value) if isinstance(value, int) and not isinstance(value, bool) else value


def load_calibration(data_dir: Path, *, artifacts_dir: Path | None = None) -> Calibration:
    """Read ``<artifacts_dir>/calibration.json`` (default ``data_dir.parent / "artifacts"``, B6).

    Missing file -> `Calibration()` defaults (logged). Unreadable or invalid file -> ValueError.
    The tune fields must be both set or both null.
    """
    directory = artifacts_dir if artifacts_dir is not None else Path(data_dir).parent / "artifacts"
    path = directory / CALIBRATION_FILE
    if not path.exists():
        logger.warning("calibration file %s missing; using pre-calibration defaults", path)
        return Calibration()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        parsed = _CalibrationFile.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"malformed calibration file {path}: {exc}") from exc
    if (parsed.z7_tune_merchant_id is None) != (parsed.z7_tune_base_day_paise is None):
        raise ValueError(f"{path}: z7_tune_merchant_id and z7_tune_base_day_paise must be set together")
    return Calibration(
        anil_base_day_paise=parsed.anil_base_day_paise,
        zone_rain_scale=MappingProxyType(dict(sorted(parsed.zone_rain_scale.items()))),
        z9_slow_depth=parsed.z9_slow_depth,
        z7_other_scale=parsed.z7_other_scale,
        z7_tune_merchant_id=parsed.z7_tune_merchant_id,
        z7_tune_base_day_paise=parsed.z7_tune_base_day_paise,
    )
