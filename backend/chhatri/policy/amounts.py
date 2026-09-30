"""Payout arithmetic on published numbers (SPEC §4.1, §4.3).

Every amount is integer paise computed with `decimal.Decimal` and ROUND_HALF_UP, starting from the
*published* expected day (rounded to the nearest ₹10) so a merchant can redo the arithmetic from the
numbers shown next to it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from chhatri.money import round_to_rupee, round_to_ten_rupees, to_decimal
from chhatri.policy.rules import PolicyRules

PERCENT: Final = Decimal(100)
MAX_DROP_PCT: Final = 100


@dataclass(frozen=True, slots=True)
class AreaBreakdown:
    """Intermediate figures of an area payout (SPEC §4.3, shown by §9.6).

    `lost_paise` = expected × drop% (exact paise, half up); `share_paise` = share × lost rounded to a
    whole rupee (the uncapped amount); `amount_paise` = min(share_paise, area daily cap).
    """

    expected_day_paise: int
    drop_pct: int
    lost_paise: int
    share_paise: int
    cap_paise: int
    amount_paise: int
    capped: bool


@dataclass(frozen=True, slots=True)
class PersonalBreakdown:
    """Intermediate figures of a personal payout (SPEC §4.3, shown by §9.6).

    `per_day_paise` = share × expected rounded to a whole rupee (uncapped); `paid_per_day_paise` =
    min(per_day_paise, personal daily cap); `amount_paise` = days × paid_per_day_paise.
    """

    expected_day_paise: int
    days: int
    per_day_paise: int
    cap_paise: int
    paid_per_day_paise: int
    amount_paise: int
    capped: bool


def _require_published(expected_day_published: int) -> None:
    if expected_day_published < 0:
        raise ValueError("expected day must be non-negative paise")
    if round_to_ten_rupees(expected_day_published) != expected_day_published:
        raise ValueError(
            f"expected day {expected_day_published} paise is not published (nearest ₹10, SPEC §4.3)"
        )


def publish_expected_day(expected_day_paise: int) -> int:
    """Model expectation for the full business day → the published figure, nearest ₹10 half up (§4.3)."""
    if expected_day_paise < 0:
        raise ValueError("expected day must be non-negative paise")
    return round_to_ten_rupees(expected_day_paise)


def area_breakdown(expected_day_published: int, drop_pct: int, rules: PolicyRules) -> AreaBreakdown:
    """Area payout per shop = min(round_rupee(share × expected × drop% / 100), area cap) (SPEC §4.3)."""
    _require_published(expected_day_published)
    if not 0 <= drop_pct <= MAX_DROP_PCT:
        raise ValueError(f"drop_pct must be within 0..100, got {drop_pct}")
    lost = to_decimal(expected_day_published) * drop_pct / PERCENT
    lost_paise = int(lost.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    share_paise = round_to_rupee(to_decimal(rules.payout_share) * lost)
    cap = rules.area.daily_cap_paise
    return AreaBreakdown(
        expected_day_paise=expected_day_published,
        drop_pct=drop_pct,
        lost_paise=lost_paise,
        share_paise=share_paise,
        cap_paise=cap,
        amount_paise=min(share_paise, cap),
        capped=share_paise > cap,
    )


def personal_breakdown(expected_day_published: int, days: int, rules: PolicyRules) -> PersonalBreakdown:
    """Personal payout = days × min(round_rupee(share × expected), personal cap) (SPEC §4.3)."""
    _require_published(expected_day_published)
    if days < 0:
        raise ValueError(f"days must be non-negative, got {days}")
    per_day = round_to_rupee(to_decimal(rules.payout_share) * to_decimal(expected_day_published))
    cap = rules.personal.daily_cap_paise
    paid_per_day = min(per_day, cap)
    return PersonalBreakdown(
        expected_day_paise=expected_day_published,
        days=days,
        per_day_paise=per_day,
        cap_paise=cap,
        paid_per_day_paise=paid_per_day,
        amount_paise=days * paid_per_day,
        capped=per_day > cap,
    )


def area_amount(expected_day_published: int, drop_pct: int, rules: PolicyRules) -> tuple[int, bool]:
    """(paise, capped) for one shop's area payout (SPEC §4.3, §24.3)."""
    breakdown = area_breakdown(expected_day_published, drop_pct, rules)
    return breakdown.amount_paise, breakdown.capped


def personal_amount(expected_day_published: int, days: int, rules: PolicyRules) -> tuple[int, bool]:
    """(paise, capped) for a personal payout over `days` verified silent days (SPEC §4.3, §24.3)."""
    breakdown = personal_breakdown(expected_day_published, days, rules)
    return breakdown.amount_paise, breakdown.capped
