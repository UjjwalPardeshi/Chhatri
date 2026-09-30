"""Half-up rounding of model outputs to whole paise (SPEC §4.1).

Model outputs are float64 paise; every integer the rest of the system sees is rounded half up.
`x - floor(x)` is exact in binary floating point, so the comparison with 0.5 is exact too (unlike
`floor(x + 0.5)`, which misrounds 0.49999999999999994).
"""

from __future__ import annotations

from typing import Final

import numpy as np

HALF: Final = 0.5


def round_half_up(values: np.ndarray | float) -> np.ndarray:
    """Element-wise half-up rounding of non-negative float paise to int64. ValueError on NaN/inf/negatives."""
    array = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(array)) or np.any(array < 0):
        raise ValueError("round_half_up expects finite non-negative paise")
    floor = np.floor(array)
    return (floor + ((array - floor) >= HALF)).astype(np.int64)


def round_paise(value: float) -> int:
    """Scalar form of `round_half_up`."""
    return int(round_half_up(value))
