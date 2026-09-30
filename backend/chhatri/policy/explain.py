"""Explanations of payout arithmetic (SPEC §9.6), bilingual, from published numbers only.

Exact formats (SPEC §9.6), `½` when `payout_share == 0.5`, otherwise `{share_pct}% ×`:
- area en `½ × ₹4,380 × 63% = ₹1,380`; capped `½ × ₹9,000 × 70% = ₹3,150, capped at ₹2,500`
- area hi `₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380`; capped
  `₹9,000 का 70% = ₹6,300; उसका आधा = ₹3,150; सीमा ₹2,500`
- personal en capped `½ × ₹4,380 = ₹2,190 a day, capped at ₹1,500 × 1 day = ₹1,500`;
  uncapped `½ × ₹2,400 = ₹1,200 a day × 2 days = ₹2,400`
- personal hi capped `₹4,380 का आधा = ₹2,190 प्रतिदिन; सीमा ₹1,500 × 1 दिन = ₹1,500`

Interpretations where SPEC §9.6 gives no literal (documented choices):
- personal hi uncapped mirrors the en form: `₹2,400 का आधा = ₹1,200 प्रतिदिन × 2 दिन = ₹2,400`.
- a share other than one half reads `उसका {share_pct}%` / `का {share_pct}%` in Hindi where the
  literal uses `उसका आधा` / `का आधा`.
- English pluralises `day`/`days`; Hindi `दिन` is invariant.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from chhatri.domain.models import Explanation
from chhatri.money import format_inr, to_decimal
from chhatri.policy.amounts import AreaBreakdown, PersonalBreakdown
from chhatri.policy.rules import PolicyRules

HALF: Final = Decimal("0.5")
HALF_GLYPH_EN: Final = "½ ×"
HALF_WORD_HI: Final = "आधा"
AREA_DAYS: Final = 1
WEEKDAYS_EN: Final = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
WEEKDAYS_HI: Final = ("सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार")


def weekday_names(weekday: int) -> tuple[str, str]:
    """(English, Hindi) weekday name, 0 = Monday (SPEC §13.4 weekday list)."""
    if not 0 <= weekday < len(WEEKDAYS_EN):
        raise ValueError(f"weekday must be 0..6 (Mon=0), got {weekday}")
    return WEEKDAYS_EN[weekday], WEEKDAYS_HI[weekday]


def _is_half(rules: PolicyRules) -> bool:
    return to_decimal(rules.payout_share) == HALF


def share_prefix_en(rules: PolicyRules) -> str:
    """`½ ×` for a one-half share, else `{share_pct}% ×` (SPEC §9.6)."""
    return HALF_GLYPH_EN if _is_half(rules) else f"{rules.share_pct}% ×"


def share_word_hi(rules: PolicyRules) -> str:
    """`आधा` for a one-half share, else `{share_pct}%` (documented interpretation of SPEC §9.6)."""
    return HALF_WORD_HI if _is_half(rules) else f"{rules.share_pct}%"


def _days_en(days: int) -> str:
    return f"{days} day" if days == 1 else f"{days} days"


def area_formulas(b: AreaBreakdown, rules: PolicyRules) -> tuple[str, str]:
    """(formula_en, formula_hi) for an area payout (SPEC §9.6)."""
    expected, share = format_inr(b.expected_day_paise), format_inr(b.share_paise)
    en = f"{share_prefix_en(rules)} {expected} × {b.drop_pct}% = {share}"
    hi = f"{expected} का {b.drop_pct}% = {format_inr(b.lost_paise)}; उसका {share_word_hi(rules)} = {share}"
    if b.capped:
        cap = format_inr(b.cap_paise)
        en = f"{en}, capped at {cap}"
        hi = f"{hi}; सीमा {cap}"
    return en, hi


def personal_formulas(b: PersonalBreakdown, rules: PolicyRules) -> tuple[str, str]:
    """(formula_en, formula_hi) for a personal payout (SPEC §9.6)."""
    expected, per_day = format_inr(b.expected_day_paise), format_inr(b.per_day_paise)
    amount = format_inr(b.amount_paise)
    en_head = f"{share_prefix_en(rules)} {expected} = {per_day} a day"
    hi_head = f"{expected} का {share_word_hi(rules)} = {per_day} प्रतिदिन"
    if b.capped:
        cap = format_inr(b.cap_paise)
        en = f"{en_head}, capped at {cap} × {_days_en(b.days)} = {amount}"
        hi = f"{hi_head}; सीमा {cap} × {b.days} दिन = {amount}"
    else:
        en = f"{en_head} × {_days_en(b.days)} = {amount}"
        hi = f"{hi_head} × {b.days} दिन = {amount}"
    return en, hi


def explain_area(b: AreaBreakdown, weekday: int, rules: PolicyRules) -> Explanation:
    """Explanation of an area payout for the event weekday (SPEC §9.6)."""
    weekday_en, weekday_hi = weekday_names(weekday)
    formula_en, formula_hi = area_formulas(b, rules)
    return Explanation(
        weekday_en=weekday_en,
        weekday_hi=weekday_hi,
        expected_day_paise=b.expected_day_paise,
        drop_pct=b.drop_pct,
        share_pct=rules.share_pct,
        days=AREA_DAYS,
        cap_paise=b.cap_paise,
        capped=b.capped,
        amount_paise=b.amount_paise,
        formula_en=formula_en,
        formula_hi=formula_hi,
    )


def explain_personal(b: PersonalBreakdown, weekday: int, rules: PolicyRules) -> Explanation:
    """Explanation of a personal payout over the claimed silent days (SPEC §9.6)."""
    weekday_en, weekday_hi = weekday_names(weekday)
    formula_en, formula_hi = personal_formulas(b, rules)
    return Explanation(
        weekday_en=weekday_en,
        weekday_hi=weekday_hi,
        expected_day_paise=b.expected_day_paise,
        drop_pct=None,
        share_pct=rules.share_pct,
        days=b.days,
        cap_paise=b.cap_paise,
        capped=b.capped,
        amount_paise=b.amount_paise,
        formula_en=formula_en,
        formula_hi=formula_hi,
    )
