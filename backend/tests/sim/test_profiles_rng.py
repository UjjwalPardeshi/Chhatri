"""SPEC §5.3 shop-type table and the counter-based RNG contract."""

from __future__ import annotations

import numpy as np
import pytest

from chhatri.domain.enums import ShopType
from chhatri.money import rupees
from chhatri.sim.profiles import FESTIVAL_SHOP_TYPES, SHOP_TYPE_SPECS, ShopTypeSpec
from chhatri.sim.rng import Stream, generator

TABLE = {  # SPEC §5.3: median Rs, sensitivity, ticket Rs, hours
    ShopType.TEA_STALL: (4000, 0.85, 18, 6, 22),
    ShopType.STREET_FOOD: (6000, 0.90, 45, 10, 23),
    ShopType.FRUIT_VEG: (5000, 0.90, 60, 7, 21),
    ShopType.KIRANA: (9000, 0.55, 120, 7, 22),
    ShopType.PHARMACY: (12000, 0.35, 250, 8, 23),
    ShopType.SALON: (3500, 0.80, 150, 9, 21),
    ShopType.MOBILE_RECHARGE: (3000, 0.70, 100, 9, 21),
}


def test_shop_type_table_matches_spec() -> None:
    for shop_type, (median, sens, ticket, open_h, close_h) in TABLE.items():
        spec = SHOP_TYPE_SPECS[shop_type]
        assert spec.median_day_paise == rupees(median) and spec.avg_ticket_paise == rupees(ticket)
        assert (spec.rain_sensitivity, spec.open_hour, spec.close_hour) == (sens, open_h, close_h)
        weights = spec.hour_weights
        assert abs(sum(weights) - 1) < 1e-12 and all(w == 0 for w in weights[:open_h] + weights[close_h:])


def test_peaks_and_weekly_patterns() -> None:
    tea = SHOP_TYPE_SPECS[ShopType.TEA_STALL].hour_weights
    assert max(range(24), key=tea.__getitem__) in (7, 8, 9)
    assert tea[17] > tea[13]  # evening peak 16-19
    food = SHOP_TYPE_SPECS[ShopType.STREET_FOOD]
    assert food.dow_mult[6] == 1.10  # Sunday +10 % food (SPEC §5.3)
    assert SHOP_TYPE_SPECS[ShopType.MOBILE_RECHARGE].dow_mult[6] == 0.70
    assert {
        ShopType.TEA_STALL,
        ShopType.STREET_FOOD,
        ShopType.FRUIT_VEG,
        ShopType.KIRANA,
    } == FESTIVAL_SHOP_TYPES


def test_spec_validation() -> None:
    with pytest.raises(ValueError, match="curve"):
        ShopTypeSpec(ShopType.SALON, "x", 1, 0.5, 1, 9, 12, (1.0, 1.0), (1.0,) * 7, False, 0.1)
    with pytest.raises(ValueError, match="dow_mult"):
        ShopTypeSpec(ShopType.SALON, "x", 1, 0.5, 1, 9, 11, (1.0, 1.0), (1.0,) * 6, False, 0.1)


def test_generator_is_keyed_and_independent_of_history() -> None:
    a = generator(1, Stream.SALES_NOISE, 739_000).standard_normal(5)
    b = generator(1, Stream.SALES_NOISE, 739_000).standard_normal(5)
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, generator(1, Stream.SALES_NOISE, 739_001).standard_normal(5))
    assert not np.array_equal(a, generator(1, Stream.SALES_TXNS, 739_000).standard_normal(5))
    assert not np.array_equal(a, generator(2, Stream.SALES_NOISE, 739_000).standard_normal(5))
    with pytest.raises(ValueError, match="non-negative"):
        generator(-1, Stream.SALES_NOISE)


def test_poisson_from_uniform_is_the_exact_inverse_cdf() -> None:
    from math import exp, factorial

    from chhatri.sim.rng import poisson_from_uniform

    lam = np.array([[0.0, 0.5, 3.0, 40.0]])
    u = np.array([[0.99, 0.5, 0.2, 0.7]])
    counts = poisson_from_uniform(u, lam)
    for lam_i, u_i, k in zip(lam.ravel(), u.ravel(), counts.ravel(), strict=True):
        cdf = [sum(exp(-lam_i) * lam_i**j / factorial(j) for j in range(n + 1)) for n in range(int(k) + 1)]
        assert cdf[-1] >= u_i and (k == 0 or cdf[-2] < u_i)
    draws = poisson_from_uniform(np.random.default_rng(0).random(100_000), np.full(100_000, 12.5))
    assert abs(draws.mean() - 12.5) < 0.05 and abs(draws.var() - 12.5) < 0.3
    assert poisson_from_uniform(np.array([1.0 - 1e-17]), np.array([2.0]))[0] > 5  # terminates at the tail


def test_poisson_from_uniform_validation() -> None:
    from chhatri.sim.rng import poisson_from_uniform

    with pytest.raises(ValueError, match="shape"):
        poisson_from_uniform(np.zeros(2), np.zeros(3))
    for bad in (-1.0, 701.0, float("nan")):
        with pytest.raises(ValueError, match="lambda"):
            poisson_from_uniform(np.zeros(1), np.array([bad]))
