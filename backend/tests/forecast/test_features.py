"""Feature schema, city arrays and feature frames (SPEC §7.1)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from chhatri.domain.enums import ShopType
from chhatri.forecast.features import (
    FEATURES,
    NO_WEEKLY_OFF,
    CityArrays,
    FeatureSchema,
    concat_blocks,
    day_block,
    is_festival,
    to_frame,
)
from chhatri.forecast.history import TrailingStats
from chhatri.sim.types import City
from tests.forecast.synthetic import make_city


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2024, 9, 6), False),
        (date(2024, 9, 7), True),
        (date(2024, 9, 16), True),
        (date(2024, 9, 17), False),
        (date(2025, 8, 26), False),
        (date(2025, 8, 27), True),
        (date(2025, 9, 5), True),
        (date(2025, 9, 6), False),
        (date(2025, 8, 19), False),
    ],
)
def test_festival_windows(day: date, expected: bool) -> None:
    assert is_festival(day) is expected


class TestSchema:
    def test_fixed_lists_cover_every_zone_and_shop_type(self) -> None:
        city = make_city((("Z2", 3),), extra_zones=("Z1", "Z10"))
        schema = FeatureSchema.for_city(city)
        assert schema.zone_ids == ("Z1", "Z2", "Z10")
        assert schema.shop_types == tuple(t.value for t in ShopType)
        assert schema.zone_codes(city.merchants).tolist() == [1, 1, 1]

    def test_unknown_zone_is_rejected(self, city: City) -> None:
        schema = FeatureSchema(zone_ids=("Z1", "Z2"), shop_types=tuple(t.value for t in ShopType))
        with pytest.raises(ValueError, match="Z3"):
            schema.zone_codes(city.merchants)

    def test_unknown_shop_type_is_rejected(self, city: City) -> None:
        schema = FeatureSchema(zone_ids=("Z1", "Z2", "Z3"), shop_types=("TEA_STALL",))
        with pytest.raises(ValueError, match="shop types"):
            schema.shop_type_codes(city.merchants)


class TestCityArrays:
    def test_schedule_cover_and_weekly_off(self, city: City) -> None:
        arrays = CityArrays.build(city, FeatureSchema.for_city(city))
        row = city.row("S-0005")  # weekly_off_every=5 → S-0005 has weekly off 5 % 7 = 5 (Saturday)
        profile = city.profiles["S-0005"]
        assert arrays.weekly_off[row] == 5
        assert arrays.weekly_off[city.row("S-0001")] == NO_WEEKLY_OFF
        assert arrays.business[row].tolist() == [
            profile.open_hour <= h < profile.close_hour for h in range(24)
        ]
        assert not arrays.covered[city.row("S-0003")] and arrays.covered[city.row("S-0001")]
        assert not arrays.open_mask(date(2025, 1, 4))[row].any()  # a Saturday
        assert arrays.open_mask(date(2025, 1, 3))[row].sum() == profile.close_hour - profile.open_hour

    def test_subset_rows_follow_given_order(self, city: City) -> None:
        schema = FeatureSchema.for_city(city)
        full = CityArrays.build(city, schema)
        part = CityArrays.build(city, schema, [30, 2])
        assert part.zone_code.tolist() == [full.zone_code[30], full.zone_code[2]]
        assert not part.business.flags.writeable


class TestFrames:
    def test_day_block_and_frame_encoding(self, city: City) -> None:
        schema = FeatureSchema.for_city(city)
        arrays = CityArrays.build(city, schema)
        m = len(city.merchants)
        stats = TrailingStats(np.full(m, 1000.0), np.full((m, 24), 1 / 24))
        day = date(2025, 8, 28)  # a festival Thursday
        mask = np.zeros((m, 24), dtype=bool)
        mask[0, 9] = mask[40, 17] = True
        block = day_block(arrays, stats, day, mask)
        assert block.rows.tolist() == [0, 40] and block.hours.tolist() == [9, 17]
        frame = to_frame(schema, concat_blocks([block]))
        assert list(frame.columns) == list(FEATURES)
        assert isinstance(frame["zone_id"].dtype, pd.CategoricalDtype)
        assert list(frame["zone_id"].cat.categories) == ["Z1", "Z2", "Z3"]
        assert list(frame["shop_type"].cat.categories) == [t.value for t in ShopType]
        assert frame["zone_id"].tolist() == [city.merchants[0].zone_id, city.merchants[40].zone_id]
        assert frame["dow"].tolist() == [3.0, 3.0] and frame["is_festival"].tolist() == [1.0, 1.0]
        assert frame["month"].tolist() == [8.0, 8.0] and frame["hour"].tolist() == [9.0, 17.0]
        np.testing.assert_allclose(frame["shop_level"], np.log(1000.0))
        assert all(frame[c].dtype == np.float64 for c in FEATURES[2:])

    def test_empty_blocks_give_empty_frame(self, city: City) -> None:
        frame = to_frame(FeatureSchema.for_city(city), concat_blocks([]))
        assert len(frame) == 0 and list(frame.columns) == list(FEATURES)
