"""Feature schema and vectorised feature frames for the expected-sales model (SPEC §7.1).

Features per shop-hour row: categorical `zone_id` and `shop_type` (pandas Categorical with FIXED
category lists — every zone of the city and every `ShopType` — persisted with the model so training
and prediction encode identically), numeric `hour`, `dow`, `is_festival`, `month`, `shop_level`
(log median normal-day sales, see `history.py`) and `shop_hour_share`. Target = amount / level.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from types import MappingProxyType
from typing import Final

import numpy as np
import pandas as pd

from chhatri.domain.enums import ShopType
from chhatri.domain.models import Merchant
from chhatri.forecast.history import HOURS_PER_DAY, TrailingStats
from chhatri.sim.types import City

CATEGORICAL: Final = ("zone_id", "shop_type")
FEATURES: Final = (
    "zone_id",
    "shop_type",
    "hour",
    "dow",
    "is_festival",
    "month",
    "shop_level",
    "shop_hour_share",
)
NO_WEEKLY_OFF: Final = -1
FESTIVAL_DAYS: Final = 10  # SPEC §6.3: Ganesh Chaturthi 10-day window
FESTIVAL_STARTS: Final = (date(2024, 9, 7), date(2025, 8, 27))  # SPEC §6.3


def is_festival(day: date) -> bool:
    """True inside a Ganesh Chaturthi window (start day + 9 following days, SPEC §6.3)."""
    return any(start <= day < start + timedelta(days=FESTIVAL_DAYS) for start in FESTIVAL_STARTS)


@dataclass(frozen=True, slots=True)
class FeatureSchema:
    """Fixed category lists for the categorical features; persisted with the model."""

    zone_ids: tuple[str, ...]
    shop_types: tuple[str, ...]

    @classmethod
    def for_city(cls, city: City) -> FeatureSchema:
        zone_ids = tuple(zone.id for zone in city.zones)
        schema = cls(zone_ids=zone_ids, shop_types=tuple(t.value for t in ShopType))
        schema.zone_codes(city.merchants)
        return schema

    def zone_codes(self, merchants: Sequence[Merchant]) -> np.ndarray:
        """Category code of each merchant's zone; ValueError for zones outside the schema."""
        lookup = {zone_id: i for i, zone_id in enumerate(self.zone_ids)}
        missing = sorted({m.zone_id for m in merchants if m.zone_id not in lookup})
        if missing:
            raise ValueError(f"zones {missing} were not in the model's training schema")
        return np.array([lookup[m.zone_id] for m in merchants], dtype=np.int64)

    def shop_type_codes(self, merchants: Sequence[Merchant]) -> np.ndarray:
        """Category code of each merchant's shop type; ValueError for types outside the schema."""
        lookup = {shop_type: i for i, shop_type in enumerate(self.shop_types)}
        missing = sorted({m.shop_type.value for m in merchants if m.shop_type.value not in lookup})
        if missing:
            raise ValueError(f"shop types {missing} were not in the model's training schema")
        return np.array([lookup[m.shop_type.value] for m in merchants], dtype=np.int64)


@dataclass(frozen=True, slots=True)
class CityArrays:
    """Per-merchant static arrays in City row order (SPEC §24.1)."""

    zone_code: np.ndarray  # (M,) int64
    shop_type_code: np.ndarray  # (M,) int64
    business: np.ndarray  # (M, 24) bool — hour inside [open_hour, close_hour)
    weekly_off: np.ndarray  # (M,) int64, NO_WEEKLY_OFF when none
    covered: np.ndarray  # (M,) bool — merchant has a Cover (SPEC §5.4)

    @classmethod
    def build(cls, city: City, schema: FeatureSchema, rows: Sequence[int] | None = None) -> CityArrays:
        """Arrays for all City rows, or for `rows` in the given order."""
        merchants = city.merchants if rows is None else tuple(city.merchants[r] for r in rows)
        hours = np.arange(HOURS_PER_DAY)
        opens = np.array([city.profiles[m.id].open_hour for m in merchants], dtype=np.int64)
        closes = np.array([city.profiles[m.id].close_hour for m in merchants], dtype=np.int64)
        business = (hours[None, :] >= opens[:, None]) & (hours[None, :] < closes[:, None])
        off = [NO_WEEKLY_OFF if m.weekly_off is None else m.weekly_off for m in merchants]
        covered = np.array([m.id in city.covers for m in merchants], dtype=bool)
        arrays = (
            schema.zone_codes(merchants),
            schema.shop_type_codes(merchants),
            business,
            np.array(off, dtype=np.int64),
            covered,
        )
        for array in arrays:
            array.setflags(write=False)
        return cls(*arrays)

    def open_mask(self, day: date) -> np.ndarray:
        """(M, 24) scheduled-open hours on `day`: business hours and not the weekly off (SPEC §5.3)."""
        return self.business & (self.weekly_off != day.weekday())[:, None]


@dataclass(frozen=True, slots=True)
class FeatureBlock:
    """Numeric feature columns for selected (row, hour) cells of one day, plus the cell coordinates."""

    rows: np.ndarray  # (N,) int64 row index
    hours: np.ndarray  # (N,) int64 hour of day
    columns: Mapping[str, np.ndarray]


def day_block(arrays: CityArrays, stats: TrailingStats, day: date, mask: np.ndarray) -> FeatureBlock:
    """Feature columns for the cells where `mask` (M, 24) is true on `day` (fully vectorised)."""
    rows, hours = np.nonzero(mask)
    n = rows.shape[0]
    columns = {
        "zone_id": arrays.zone_code[rows],
        "shop_type": arrays.shop_type_code[rows],
        "hour": hours.astype(np.float64),
        "dow": np.full(n, day.weekday(), dtype=np.float64),
        "is_festival": np.full(n, float(is_festival(day))),
        "month": np.full(n, day.month, dtype=np.float64),
        "shop_level": stats.shop_level[rows],
        "shop_hour_share": stats.hour_share[rows, hours],
    }
    return FeatureBlock(
        rows=rows.astype(np.int64), hours=hours.astype(np.int64), columns=MappingProxyType(columns)
    )


def concat_blocks(blocks: Sequence[FeatureBlock]) -> Mapping[str, np.ndarray]:
    """Concatenate the feature columns of several blocks."""
    if not blocks:
        return MappingProxyType({name: np.empty(0) for name in FEATURES})
    return MappingProxyType({name: np.concatenate([b.columns[name] for b in blocks]) for name in FEATURES})


def to_frame(schema: FeatureSchema, columns: Mapping[str, np.ndarray]) -> pd.DataFrame:
    """DataFrame with the categorical columns encoded against the schema's fixed category lists."""
    data: dict[str, object] = {}
    for name in FEATURES:
        values = columns[name]
        if name == "zone_id":
            data[name] = pd.Categorical.from_codes(values, categories=list(schema.zone_ids))
        elif name == "shop_type":
            data[name] = pd.Categorical.from_codes(values, categories=list(schema.shop_types))
        else:
            data[name] = np.asarray(values, dtype=np.float64)
    return pd.DataFrame(data, columns=list(FEATURES))
