"""Area index (SPEC §8.1, §24.2): zone actual / zone expected over a trailing window.

Contract for `expected_p50`: a 2-D float array of P50 paise with one row per City merchant and
column j = the hour `actual.start + j` (i.e. aligned with the actual panel; it may extend beyond
`actual.end`, never start elsewhere). Actual paise are summed exactly; expected paise are summed and
rounded half up to whole paise; `index_pct` = percent_half_up(actual, expected), None when expected
is 0. The index covers the zone's covered, open merchants: merchants with a Cover (SPEC §5.4) that
are scheduled open (business hour, not weekly off) in at least one hour of the window.
Windows must lie inside the actual panel (IndexError otherwise), which is how SPEC B4 is honoured:
callers pass a panel that ends at the last visible hour.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Final

import numpy as np

from chhatri.clock import floor_hour, require_aware
from chhatri.detect.city_arrays import arrays_for, open_hours
from chhatri.domain.models import ZoneWindowIndex
from chhatri.forecast.rounding import round_paise
from chhatri.money import percent_half_up
from chhatri.sim.types import City, SalesPanel

HOUR: Final = timedelta(hours=1)
SECONDS_PER_HOUR: Final = 3600.0


def _hour_span(actual: SalesPanel, start: datetime, end: datetime) -> tuple[int, int]:
    """Column range [i, j) of the whole hours [start, end) inside the panel."""
    start, end = require_aware(start), require_aware(end)
    if floor_hour(start) != start or floor_hour(end) != end:
        raise ValueError("window bounds must be on hour boundaries")
    if end <= start:
        raise ValueError("window end must be after start")
    i = actual.hour_index(start)
    j = i + int((end - start) // HOUR)
    if j > actual.hours:
        raise IndexError(f"window ends at {end.isoformat()}, after the panel end {actual.end.isoformat()}")
    return i, j


def check_expected(actual: SalesPanel, expected_p50: np.ndarray) -> None:
    """Validate the alignment contract of `expected_p50` (see module docstring)."""
    if expected_p50.ndim != 2 or expected_p50.shape[0] != len(actual.merchant_ids):
        raise ValueError(
            f"expected_p50 must be 2-D with {len(actual.merchant_ids)} rows, got shape {expected_p50.shape}"
        )
    if expected_p50.shape[1] < actual.hours:
        raise ValueError(f"expected_p50 covers {expected_p50.shape[1]} hours, the panel {actual.hours}")


def hourly_sums(
    actual: SalesPanel, expected_p50: np.ndarray, rows: Sequence[int], i: int, j: int
) -> tuple[np.ndarray, np.ndarray]:
    """Per-hour (actual int64, expected float64) sums over `rows` for panel columns [i, j)."""
    index = np.asarray(rows, dtype=np.int64)
    act = actual.amount_paise[index, i:j].sum(axis=0, dtype=np.int64)
    exp = np.asarray(expected_p50[index, i:j], dtype=np.float64).sum(axis=0)
    return act, exp


def ratio(actual_paise: int, expected_paise: int) -> int | None:
    """Integer percent half up, None when nothing was expected."""
    return None if expected_paise == 0 else percent_half_up(actual_paise, expected_paise)


def window_index(
    actual: SalesPanel,
    expected_p50: np.ndarray,
    rows: Sequence[int],
    start: datetime,
    end: datetime,
) -> tuple[int, int, int | None]:
    """(actual_paise, expected_paise, index_pct half-up or None when expected == 0) for [start, end)."""
    check_expected(actual, expected_p50)
    i, j = _hour_span(actual, start, end)
    act, exp = hourly_sums(actual, expected_p50, rows, i, j)
    actual_paise, expected_paise = int(act.sum()), round_paise(float(exp.sum()))
    return actual_paise, expected_paise, ratio(actual_paise, expected_paise)


def index_rows(city: City, zone_id: str, start: datetime, end: datetime) -> tuple[int, ...]:
    """Rows of the zone's covered merchants that are scheduled open in at least one hour of [start, end)."""
    arrays = arrays_for(city)
    candidates = np.asarray(city.zone_rows(zone_id), dtype=np.int64)
    candidates = candidates[arrays.covered[candidates]]
    hours = int((require_aware(end) - require_aware(start)) // HOUR)
    if candidates.size == 0 or hours < 1:
        return ()
    keep = open_hours(city, candidates, start, hours).any(axis=1)
    return tuple(int(r) for r in candidates[keep])


def zone_window(
    city: City,
    actual: SalesPanel,
    expected_p50: np.ndarray,
    zone_id: str,
    start: datetime,
    end: datetime,
    lower_bound_pct: int,
) -> ZoneWindowIndex:
    """ZoneWindowIndex over the zone's covered, open merchants (SPEC §8.1)."""
    rows = index_rows(city, zone_id, start, end)
    actual_paise, expected_paise, index_pct = window_index(actual, expected_p50, rows, start, end)
    return ZoneWindowIndex(
        zone_id=zone_id,
        window_start=require_aware(start),
        window_end=require_aware(end),
        actual_paise=actual_paise,
        expected_paise=expected_paise,
        index_pct=index_pct,
        lower_bound_pct=lower_bound_pct,
        shops_in_index=len(rows),
    )


def live_window_index(
    actual: SalesPanel,
    expected_p50: np.ndarray,
    rows: Sequence[int],
    now: datetime,
    hours: int,
) -> tuple[int, int, int | None]:
    """Sliding `hours`-hour index ending at `now` (SPEC §8.1 live partial value; decision B3).

    With t = floor_hour(now) and f = (now - t) / 1 h, the completed hours [t - hours, t) count fully
    except the oldest, weighted (1 - f), and the current hour [t, t + 1) is weighted f — in both
    actual and expected. At f = 0 this is exactly `window_index(..., t - hours, t)` and the current
    hour is not read. Returns (actual paise, expected paise, index) rounded as in `window_index`.
    """
    check_expected(actual, expected_p50)
    t = floor_hour(now)
    f = (require_aware(now) - t).total_seconds() / SECONDS_PER_HOUR
    if f == 0.0:
        return window_index(actual, expected_p50, rows, t - hours * HOUR, t)
    i, j = _hour_span(actual, t - hours * HOUR, t + HOUR)
    weights = np.ones(j - i)
    weights[0], weights[-1] = 1.0 - f, f
    act, exp = hourly_sums(actual, expected_p50, rows, i, j)
    actual_paise = round_paise(float(np.dot(act.astype(np.float64), weights)))
    expected_paise = round_paise(float(np.dot(exp, weights)))
    return actual_paise, expected_paise, ratio(actual_paise, expected_paise)
