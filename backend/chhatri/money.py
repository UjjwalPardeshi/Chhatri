"""Money helpers (SPEC §4). Amounts are integer paise; arithmetic uses Decimal, ROUND_HALF_UP."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Final

PAISE_PER_RUPEE: Final = 100


def to_decimal(value: int | str | Decimal | float) -> Decimal:
    if isinstance(value, float):
        # floats are only accepted from model outputs; go through str to avoid binary artefacts
        return Decimal(repr(value))
    return Decimal(value)


def rupees(value: int | str | Decimal) -> int:
    """Rupees → paise (exact)."""
    paise = to_decimal(value) * PAISE_PER_RUPEE
    if paise != paise.to_integral_value():
        raise ValueError(f"{value!r} rupees is not a whole number of paise")
    return int(paise)


def round_to_rupee(paise: Decimal | int | float) -> int:
    """Round a paise amount half-up to a whole rupee; returns paise."""
    rupee_units = (to_decimal(paise) / PAISE_PER_RUPEE).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(rupee_units) * PAISE_PER_RUPEE


def round_to_ten_rupees(paise: Decimal | int | float) -> int:
    """Round a paise amount half-up to the nearest ₹10 (published expected-day figure, SPEC §4.3)."""
    tens = (to_decimal(paise) / (PAISE_PER_RUPEE * 10)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(tens) * PAISE_PER_RUPEE * 10


def percent_half_up(numerator: Decimal | int | float, denominator: Decimal | int | float) -> int:
    """Integer percent, half up. Raises on a zero denominator."""
    den = to_decimal(denominator)
    if den == 0:
        raise ZeroDivisionError("percent of zero")
    return int((to_decimal(numerator) * 100 / den).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def indian_grouping(n: int) -> str:
    """1234567 → '12,34,567'. Non-negative integers only."""
    if n < 0:
        raise ValueError("indian_grouping expects a non-negative integer")
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups) + "," + tail


def format_inr(paise: int) -> str:
    """₹1,380 · ₹1,58,900 · ₹1.80 · -₹50 (SPEC §4.2)."""
    sign = "-" if paise < 0 else ""
    whole, frac = divmod(abs(paise), PAISE_PER_RUPEE)
    text = f"₹{indian_grouping(whole)}"
    if frac:
        text += f".{frac:02d}"
    return sign + text
