"""SPEC §9.6 explanation strings — exact to the character, en and hi, capped and uncapped."""

from __future__ import annotations

import re

import pytest

from chhatri.config import BACKEND_DIR
from chhatri.money import rupees
from chhatri.policy.amounts import area_breakdown, personal_breakdown
from chhatri.policy.explain import (
    area_formulas,
    explain_area,
    explain_personal,
    personal_formulas,
    weekday_names,
)
from chhatri.policy.rules import default_rules

RULES = default_rules()


def test_area_uncapped_exact() -> None:
    e = explain_area(area_breakdown(rupees(4380), 63, RULES), 1, RULES)
    assert e.formula_en == "½ × ₹4,380 × 63% = ₹1,380"
    assert e.formula_hi == "₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380"
    assert (e.weekday_en, e.weekday_hi) == ("Tuesday", "मंगलवार")
    assert (e.expected_day_paise, e.drop_pct, e.share_pct, e.days) == (rupees(4380), 63, 50, 1)
    assert (e.cap_paise, e.capped, e.amount_paise) == (rupees(2500), False, rupees(1380))


def test_area_capped_exact() -> None:
    e = explain_area(area_breakdown(rupees(9000), 70, RULES), 4, RULES)
    assert e.formula_en == "½ × ₹9,000 × 70% = ₹3,150, capped at ₹2,500"
    assert e.formula_hi == "₹9,000 का 70% = ₹6,300; उसका आधा = ₹3,150; सीमा ₹2,500"
    assert e.capped is True
    assert e.amount_paise == rupees(2500)


def test_personal_capped_exact() -> None:
    e = explain_personal(personal_breakdown(rupees(4380), 1, RULES), 2, RULES)
    assert e.formula_en == "½ × ₹4,380 = ₹2,190 a day, capped at ₹1,500 × 1 day = ₹1,500"
    assert e.formula_hi == "₹4,380 का आधा = ₹2,190 प्रतिदिन; सीमा ₹1,500 × 1 दिन = ₹1,500"
    assert (e.drop_pct, e.days, e.cap_paise, e.capped) == (None, 1, rupees(1500), True)
    assert (e.weekday_en, e.weekday_hi) == ("Wednesday", "बुधवार")


def test_personal_uncapped_exact() -> None:
    e = explain_personal(personal_breakdown(rupees(2400), 2, RULES), 0, RULES)
    assert e.formula_en == "½ × ₹2,400 = ₹1,200 a day × 2 days = ₹2,400"
    assert e.formula_hi == "₹2,400 का आधा = ₹1,200 प्रतिदिन × 2 दिन = ₹2,400"
    assert e.amount_paise == rupees(2400)
    assert e.capped is False


def test_personal_capped_plural_days() -> None:
    e = explain_personal(personal_breakdown(rupees(4380), 3, RULES), 2, RULES)
    assert e.formula_en == "½ × ₹4,380 = ₹2,190 a day, capped at ₹1,500 × 3 days = ₹4,500"
    assert e.formula_hi == "₹4,380 का आधा = ₹2,190 प्रतिदिन; सीमा ₹1,500 × 3 दिन = ₹4,500"


def test_non_half_share_uses_percent_prefix() -> None:
    rules = RULES.model_copy(update={"payout_share": 0.6})
    area = explain_area(area_breakdown(rupees(4380), 63, rules), 1, rules)
    assert area.formula_en == "60% × ₹4,380 × 63% = ₹1,656"
    assert area.formula_hi == "₹4,380 का 63% = ₹2,759.40; उसका 60% = ₹1,656"
    assert area.share_pct == 60
    personal = explain_personal(personal_breakdown(rupees(2000), 1, rules), 1, rules)
    assert personal.formula_en == "60% × ₹2,000 = ₹1,200 a day × 1 day = ₹1,200"
    assert personal.formula_hi == "₹2,000 का 60% = ₹1,200 प्रतिदिन × 1 दिन = ₹1,200"


def test_weekday_names_all_days() -> None:
    names = [weekday_names(i) for i in range(7)]
    assert [n[0] for n in names] == [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    assert [n[1] for n in names] == ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"]


@pytest.mark.parametrize("bad", [-1, 7])
def test_weekday_out_of_range(bad: int) -> None:
    with pytest.raises(ValueError, match="weekday"):
        weekday_names(bad)


def test_formulas_equal_spec_literals_character_for_character() -> None:
    """Reads SPEC §9.6 itself so the strings cannot drift from the contract."""
    spec_text = (BACKEND_DIR.parent / "docs" / "SPEC.md").read_text(encoding="utf-8")
    section = spec_text[spec_text.index("9.6 **Explanation**") : spec_text.index("9.7 **Premium**")]
    literals = [s for s in re.findall(r"`([^`]*)`", re.sub(r"\n\s+", " ", section)) if "₹" in s]
    ours = [
        *area_formulas(area_breakdown(rupees(4380), 63, RULES), RULES),
        *area_formulas(area_breakdown(rupees(9000), 70, RULES), RULES),
        personal_formulas(personal_breakdown(rupees(4380), 1, RULES), RULES)[0],
        personal_formulas(personal_breakdown(rupees(2400), 2, RULES), RULES)[0],
        personal_formulas(personal_breakdown(rupees(4380), 1, RULES), RULES)[1],
    ]
    assert literals == ours
