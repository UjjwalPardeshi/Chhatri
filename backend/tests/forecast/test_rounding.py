"""Half-up rounding of model paise (SPEC §4.1)."""

from __future__ import annotations

import numpy as np
import pytest

from chhatri.forecast.rounding import round_half_up, round_paise


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, 0), (0.5, 1), (1.5, 2), (2.5, 3), (1.49999, 1), (0.49999999999999994, 0), (438_000.5, 438_001)],
)
def test_scalar(value: float, expected: int) -> None:
    assert round_paise(value) == expected


def test_vector() -> None:
    assert round_half_up(np.array([0.5, 2.4, 2.6])).tolist() == [1, 2, 3]


@pytest.mark.parametrize("bad", [-0.1, float("nan"), float("inf")])
def test_rejects_invalid(bad: float) -> None:
    with pytest.raises(ValueError):
        round_paise(bad)
