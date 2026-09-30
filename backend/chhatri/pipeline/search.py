"""Deterministic one-dimensional root search for the calibration (SPEC §17.4).

`solve` finds x in [lo, hi] with |f(x) − target| <= tolerance for a monotone f (increasing or
decreasing): a bracketed secant search (the Illinois variant of regula falsi) with a bisection
safeguard whenever a step fails to halve the bracket. On integers (paise) every probe is rounded and
kept strictly inside the bracket. No randomness: the same f gives the same probes. Failures raise
`SearchError` carrying the best probe seen, so a caller can accept a looser band explicitly.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

__all__ = ["Probe", "SearchError", "solve"]

logger = logging.getLogger(__name__)

HALF: Final = 0.5
ILLINOIS_FACTOR: Final = 0.5


@dataclass(frozen=True, slots=True)
class Probe:
    """One evaluation: the argument and f's value there."""

    x: float
    value: float


class SearchError(RuntimeError):
    """The search could not reach its tolerance; `best` is the closest probe."""

    def __init__(self, message: str, best: Probe) -> None:
        super().__init__(message)
        self.best = best


@dataclass(slots=True)
class _Bracket:
    """Mutable search state local to one `solve` call."""

    lo: float
    hi: float
    f_lo: float  # f(lo) − target, possibly Illinois-scaled
    f_hi: float
    side: int = 0
    halve_next: bool = False

    @property
    def width(self) -> float:
        return self.hi - self.lo


def _next_x(b: _Bracket, integer: bool) -> float:
    if b.halve_next or b.f_hi == b.f_lo:
        x = (b.lo + b.hi) * HALF
    else:
        x = (b.lo * b.f_hi - b.hi * b.f_lo) / (b.f_hi - b.f_lo)
    if integer:
        return float(min(max(round(x), b.lo + 1), b.hi - 1))
    return x if b.lo < x < b.hi else (b.lo + b.hi) * HALF


def _update(b: _Bracket, x: float, fx: float) -> None:
    before = b.width
    if (fx > 0) == (b.f_hi > 0):
        b.hi, b.f_hi = x, fx
        if b.side == -1:
            b.f_lo *= ILLINOIS_FACTOR
        b.side = -1
    else:
        b.lo, b.f_lo = x, fx
        if b.side == 1:
            b.f_hi *= ILLINOIS_FACTOR
        b.side = 1
    b.halve_next = b.width > before * HALF


def solve(
    f: Callable[[float], float],
    target: float,
    lo: float,
    hi: float,
    *,
    tolerance: float,
    max_evals: int,
    integer: bool = False,
    x_tolerance: float = 0.0,
) -> Probe:
    """Return a probe with |f(x) − target| <= tolerance; f is evaluated at lo and hi first.

    ValueError for an empty interval or bad budgets; SearchError when [lo, hi] does not bracket the
    target, when the bracket collapses (width <= 1 on integers, <= x_tolerance on floats) or after
    `max_evals` evaluations without reaching the tolerance.
    """
    if not lo < hi or tolerance < 0 or max_evals < 2:
        raise ValueError(
            f"need lo < hi, tolerance >= 0 and max_evals >= 2 (got {lo}, {hi}, {tolerance}, {max_evals})"
        )
    if integer and (lo != round(lo) or hi != round(hi)):
        raise ValueError("integer search needs integer bounds")
    probes = [Probe(lo, f(lo)), Probe(hi, f(hi))]
    best = min(probes, key=lambda p: abs(p.value - target))
    if abs(best.value - target) <= tolerance:
        return best
    b = _Bracket(lo, hi, probes[0].value - target, probes[1].value - target)
    if (b.f_lo > 0) == (b.f_hi > 0):
        raise SearchError(
            f"target {target} not bracketed: f({lo})={probes[0].value}, f({hi})={probes[1].value}", best
        )
    evals = len(probes)
    while evals < max_evals and b.width > (1 if integer else x_tolerance):
        x = _next_x(b, integer)
        probe = Probe(x, f(x))
        evals += 1
        if abs(probe.value - target) < abs(best.value - target):
            best = probe
        if abs(probe.value - target) <= tolerance:
            logger.debug("solve: x=%s f=%s after %d evaluations", probe.x, probe.value, evals)
            return probe
        _update(b, x, probe.value - target)
    raise SearchError(
        f"no x in [{lo}, {hi}] within {tolerance} of {target} after {evals} evaluations "
        f"(best f({best.x})={best.value})",
        best,
    )
