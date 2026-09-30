"""ModelManifest (SPEC §7.4, §24.2): what a trained model was trained on and how well it did.

`train_start`..`train_end` is the whole training window (`train_end` is the argument of `train`,
e.g. 2025-08-18 for the replay model); `calib_start`..`calib_end` are its last `calib_weeks` weeks,
held out from fitting. The fitted days are therefore [train_start, calib_start). `pinball` is the
mean pinball loss in paise per shop-hour on the calibration rows; `coverage_p10_p90` the share of
those rows whose actual lies in [P10, P90]; `lower_bound_pct` the conformal bound per zone.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class ModelManifest:
    seed: int
    train_start: date
    train_end: date
    calib_start: date
    calib_end: date
    rows_train: int
    rows_calib: int
    pinball: Mapping[str, float]  # "p10" | "p50" | "p90" on the calibration set
    coverage_p10_p90: float
    lower_bound_pct: Mapping[str, int]  # per zone (SPEC §7.4)

    def __post_init__(self) -> None:
        if not self.train_start <= self.calib_start <= self.calib_end == self.train_end:
            raise ValueError(
                "manifest windows must satisfy train_start <= calib_start <= calib_end == train_end"
            )
        if self.rows_train < 0 or self.rows_calib < 0:
            raise ValueError("row counts must be non-negative")
        if not 0.0 <= self.coverage_p10_p90 <= 1.0:
            raise ValueError("coverage_p10_p90 must lie in [0, 1]")
        object.__setattr__(self, "pinball", MappingProxyType(dict(self.pinball)))
        object.__setattr__(self, "lower_bound_pct", MappingProxyType(dict(self.lower_bound_pct)))
