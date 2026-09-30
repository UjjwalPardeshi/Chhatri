"""Deterministic root search used by the calibration (SPEC §17.4)."""

from __future__ import annotations

import math

import pytest

from chhatri.pipeline.search import Probe, SearchError, solve


class Counter:
    """Wraps f and records every argument it is called with."""

    def __init__(self, f):
        self.f = f
        self.calls: list[float] = []

    def __call__(self, x: float) -> float:
        self.calls.append(x)
        return self.f(x)


def test_linear_float_reaches_tolerance_quickly() -> None:
    f = Counter(lambda x: 3.0 * x + 1.0)
    probe = solve(f, 10.0, 0.0, 10.0, tolerance=1e-9, max_evals=10)
    assert probe.x == pytest.approx(3.0)
    assert abs(probe.value - 10.0) <= 1e-9
    assert len(f.calls) <= 4  # secant is exact on a line after the two bounds


def test_decreasing_function_is_supported() -> None:
    probe = solve(lambda x: 100.0 * math.exp(-x), 37.0, 0.0, 5.0, tolerance=1e-6, max_evals=60)
    assert probe.value == pytest.approx(37.0, abs=1e-6)
    assert probe.x == pytest.approx(math.log(100 / 37), abs=1e-6)


def test_integer_search_probes_only_integers_inside_the_bracket() -> None:
    f = Counter(lambda x: 0.8667 * x)
    probe = solve(f, 438_000, 300_000, 700_000, tolerance=100, max_evals=30, integer=True)
    assert abs(probe.value - 438_000) <= 100
    assert all(x == int(x) and 300_000 <= x <= 700_000 for x in f.calls)
    assert probe.x == int(probe.x)


def test_bound_within_tolerance_is_returned_without_iterating() -> None:
    f = Counter(lambda x: x)
    assert solve(f, 1.0, 1.0, 5.0, tolerance=0.0, max_evals=5) == Probe(1.0, 1.0)
    assert len(f.calls) == 2


def test_unbracketed_target_raises_with_best_probe() -> None:
    with pytest.raises(SearchError, match="not bracketed") as info:
        solve(lambda x: x, 50.0, 0.0, 10.0, tolerance=0.1, max_evals=10)
    assert info.value.best == Probe(10.0, 10.0)


def test_jump_over_the_target_raises_with_closest_probe() -> None:
    step = lambda x: 0.0 if x < 2.5 else 10.0  # noqa: E731 - a step function for the test
    with pytest.raises(SearchError, match="no x in") as info:
        solve(step, 5.0, 0.0, 5.0, tolerance=0.1, max_evals=200, x_tolerance=1e-9)
    assert info.value.best.value in (0.0, 10.0)


def test_integer_bracket_collapse_raises() -> None:
    with pytest.raises(SearchError):
        solve(lambda x: 10.0 * x, 15.0, 0.0, 10.0, tolerance=1.0, max_evals=100, integer=True)


def test_budget_exhaustion_raises() -> None:
    with pytest.raises(SearchError, match="after 3 evaluations"):
        solve(lambda x: x**3, 0.5, 0.0, 1.0, tolerance=1e-12, max_evals=3)


def test_flat_segments_fall_back_to_bisection() -> None:
    # f is flat at the bracket ends, so the secant slope is zero there; bisection must take over.
    f = Counter(lambda x: min(max(x, 4.0), 6.0))
    probe = solve(f, 5.0, 0.0, 10.0, tolerance=1e-6, max_evals=50)
    assert probe.value == pytest.approx(5.0)


def test_illinois_keeps_converging_on_a_convex_function() -> None:
    f = Counter(lambda x: x**10)
    probe = solve(f, 0.5, 0.0, 1.0, tolerance=1e-10, max_evals=60)
    assert probe.value == pytest.approx(0.5, abs=1e-10)
    assert len(f.calls) < 60


def test_deterministic_probe_sequence() -> None:
    first, second = Counter(lambda x: x**3 - 2), Counter(lambda x: x**3 - 2)
    solve(first, 0.0, 0.0, 3.0, tolerance=1e-9, max_evals=60)
    solve(second, 0.0, 0.0, 3.0, tolerance=1e-9, max_evals=60)
    assert first.calls == second.calls


@pytest.mark.parametrize(
    ("lo", "hi", "tolerance", "max_evals", "integer"),
    [(1.0, 1.0, 0.1, 5, False), (2.0, 1.0, 0.1, 5, False), (0.0, 1.0, -1.0, 5, False),
     (0.0, 1.0, 0.1, 1, False), (0.5, 3.0, 0.1, 5, True)],
)  # fmt: skip
def test_invalid_arguments(lo: float, hi: float, tolerance: float, max_evals: int, integer: bool) -> None:
    with pytest.raises(ValueError):
        solve(lambda x: x, 1.0, lo, hi, tolerance=tolerance, max_evals=max_evals, integer=integer)
