"""SPEC §4.3 published-numbers arithmetic (Decimal, ROUND_HALF_UP)."""

from __future__ import annotations

import pytest

from chhatri.money import rupees
from chhatri.policy.amounts import area_breakdown, personal_breakdown
from chhatri.policy.engine import area_amount, personal_amount, publish_expected_day
from chhatri.policy.rules import default_rules

RULES = default_rules()


@pytest.mark.parametrize(
    ("raw", "published"),
    [
        (437_512, rupees(4380)),  # ₹4,375.12 → ₹4,380
        (437_500, rupees(4380)),  # exactly ₹4,375 → half up
        (437_499, rupees(4370)),
        (438_000, rupees(4380)),
        (0, 0),
        (499, 0),
        (500, rupees(10)),
    ],
)
def test_publish_expected_day_rounds_half_up_to_ten_rupees(raw: int, published: int) -> None:
    assert publish_expected_day(raw) == published


def test_publish_rejects_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        publish_expected_day(-1)


def test_area_deck_example_1380() -> None:
    assert area_amount(rupees(4380), 63, RULES) == (rupees(1380), False)
    b = area_breakdown(rupees(4380), 63, RULES)
    assert (b.lost_paise, b.share_paise, b.cap_paise) == (275_940, rupees(1380), rupees(2500))


def test_area_cap_2500() -> None:
    assert area_amount(rupees(9000), 70, RULES) == (rupees(2500), True)
    assert area_breakdown(rupees(9000), 70, RULES).share_paise == rupees(3150)


def test_area_exactly_at_cap_is_not_capped() -> None:
    assert area_amount(rupees(10000), 50, RULES) == (rupees(2500), False)


def test_area_rounds_half_up_to_rupee() -> None:
    # 0.5 × 4,370 × 63% = 1,376.55 → 1,377
    assert area_amount(rupees(4370), 63, RULES) == (rupees(1377), False)
    # 0.5 × 10 × 1% = 0.05 → 0
    assert area_amount(rupees(10), 1, RULES) == (0, False)


def test_personal_deck_example_1500() -> None:
    assert personal_amount(rupees(4380), 1, RULES) == (rupees(1500), True)
    b = personal_breakdown(rupees(4380), 1, RULES)
    assert (b.per_day_paise, b.paid_per_day_paise) == (rupees(2190), rupees(1500))


def test_personal_uncapped_two_days() -> None:
    assert personal_amount(rupees(2400), 2, RULES) == (rupees(2400), False)


def test_personal_zero_days_is_zero() -> None:
    assert personal_amount(rupees(2400), 0, RULES) == (0, False)


@pytest.mark.parametrize("bad", [438_001, 437_512, -1000])
def test_unpublished_expected_day_is_rejected(bad: int) -> None:
    with pytest.raises(ValueError):
        area_amount(bad, 63, RULES)
    with pytest.raises(ValueError):
        personal_amount(bad, 1, RULES)


@pytest.mark.parametrize("drop", [-1, 101])
def test_drop_out_of_range_rejected(drop: int) -> None:
    with pytest.raises(ValueError, match="drop_pct"):
        area_amount(rupees(4380), drop, RULES)


def test_negative_days_rejected() -> None:
    with pytest.raises(ValueError, match="days"):
        personal_amount(rupees(4380), -1, RULES)


def test_other_share_uses_decimal() -> None:
    rules = RULES.model_copy(update={"payout_share": 0.6})
    # 0.6 × 4,380 × 63% = 1,655.64 → 1,656
    assert area_amount(rupees(4380), 63, rules) == (rupees(1656), False)
