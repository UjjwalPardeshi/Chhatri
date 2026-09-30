"""Memoised per-city arrays for detection (SPEC §8).

Detection runs every simulated hour (replay) and every hour of two monsoons (backtest), so the
per-merchant schedule arrays are built once per City object and reused. City objects are immutable
(SPEC §24.1), so the cache is a pure memo; it keys on identity and keeps a strong reference to the
city, so an id can never be reused while its entry is alive.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Final

import numpy as np

from chhatri.clock import require_aware
from chhatri.forecast.features import CityArrays, FeatureSchema
from chhatri.sim.types import City

CACHE_SIZE: Final = 4
HOUR: Final = timedelta(hours=1)

_cache: OrderedDict[int, tuple[City, CityArrays]] = OrderedDict()
_lock = threading.Lock()


def arrays_for(city: City) -> CityArrays:
    """CityArrays (zone codes in `city.zones` order) for `city`, built once."""
    key = id(city)
    with _lock:
        hit = _cache.get(key)
        if hit is not None and hit[0] is city:
            _cache.move_to_end(key)
            return hit[1]
    arrays = CityArrays.build(city, FeatureSchema.for_city(city))
    with _lock:
        _cache[key] = (city, arrays)
        _cache.move_to_end(key)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return arrays


def open_hours(city: City, rows: Sequence[int] | np.ndarray, start: datetime, hours: int) -> np.ndarray:
    """(len(rows), hours) bool: scheduled open (business hour, not weekly off) in each hour from `start`."""
    arrays = arrays_for(city)
    index = np.asarray(rows, dtype=np.int64)
    stamps = [require_aware(start) + k * HOUR for k in range(hours)]
    hour_of_day = np.array([ts.hour for ts in stamps], dtype=np.int64)
    weekday = np.array([ts.weekday() for ts in stamps], dtype=np.int64)
    business = arrays.business[index][:, hour_of_day]
    return business & (arrays.weekly_off[index][:, None] != weekday[None, :])
