"""The pricing simulator's arithmetic (business model §3; chhatri.backtest.pricing_model) and its committed table."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest

from chhatri.backtest.pricing import _with_floor, write_table
from chhatri.backtest.pricing_model import Levers, levers_from_rules, price
from chhatri.config import BACKEND_DIR
from chhatri.policy.rules import default_rules

RULES_LEVERS: Final = Levers(floor_pct=50, share_pct=50, cap_rupees=2500, loading_pct=35)
ARTIFACTS: Final = BACKEND_DIR / "artifacts"


def table(events: dict[str, list[list[Any]]], shops: dict[str, int] | None = None) -> dict[str, Any]:
    return {
        "label": "test",
        "seasons": ["s1", "s2"],
        "floors": [40, 50],
        "shops": shops or {"Z1": 2, "Z2": 1},
        "real_drops": 4,
        "events": {"40": [], "50": [], **events},
    }


def test_each_trigger_pays_every_covered_shop_half_the_lost_day_up_to_the_cap() -> None:
    """₹4,380 × 63% × ½ = ₹1,379.7 → ₹1,380; ₹10,000 × 60% × ½ = ₹3,000 → the ₹2,500 cap."""
    events = {"50": [["Z1", "2025-08-19", 63, 1, [4380, 10_000]]]}
    z1 = price(table(events), RULES_LEVERS, {})["zones"][0]
    assert z1["expected_payout_per_year_paise"] == (1380 + 2500) * 100 // (2 * 2)
    assert z1["triggers"] == 1 and z1["payout_days_per_year"] == 0.5


def test_the_premium_is_the_expected_payout_over_a_year_over_one_minus_the_loading() -> None:
    events = {"50": [["Z1", "2025-08-19", 63, 1, [4380, 4380]]]}
    z1 = price(table(events), RULES_LEVERS, {})["zones"][0]
    per_year = 1380 * 2 * 100 / (2 * 2)
    assert z1["premium_per_day_paise"] == round(per_year / 365 / 0.65)
    assert z1["premium_per_month_paise"] == z1["premium_per_day_paise"] * 30
    assert z1["premium_per_year_paise"] == z1["premium_per_day_paise"] * 365


def test_a_zone_with_no_trigger_pays_the_minimum_premium() -> None:
    zones = price(table({}), RULES_LEVERS, {})["zones"]
    assert {z["premium_per_day_paise"] for z in zones} == {200}


def test_a_smaller_share_and_a_lower_cap_cost_less() -> None:
    events = {"50": [["Z1", "2025-08-19", 63, 1, [4380, 10_000]]]}
    full = price(table(events), RULES_LEVERS, {})["zones"][0]["premium_per_day_paise"]
    lean = price(table(events), Levers(50, 30, 1500, 35), {})["zones"][0]["premium_per_day_paise"]
    assert lean < full


def test_the_loss_ratio_at_todays_price_compares_the_payout_with_todays_premium() -> None:
    events = {"50": [["Z1", "2025-08-19", 63, 1, [4380, 4380]]]}
    z1 = price(table(events), RULES_LEVERS, {"Z1": 1000})["zones"][0]
    assert z1["current_premium_per_day_paise"] == 1000
    assert z1["loss_ratio_at_current_price"] == round(z1["expected_payout_per_year_paise"] / (1000 * 365), 4)


def test_the_floor_sets_the_triggers_quality_against_the_real_drops() -> None:
    events = {
        "50": [
            ["Z1", "2025-08-19", 63, 1, [4380]],
            ["Z2", "2025-08-19", 55, 0, [3000]],
            ["Z1", "2025-08-20", 52, 1, [4380]],
        ]
    }
    city = price(table(events), RULES_LEVERS, {})["city"]
    assert (city["real_drops_paid"], city["real_drops"], city["recall"]) == (2, 4, 0.5)
    assert (city["payouts_no_real_drop"], city["payouts"], city["false_payout_share"]) == (1, 3, 0.3333)


def test_a_floor_outside_the_table_is_refused() -> None:
    with pytest.raises(ValueError, match="floor must be one of"):
        price(table({}), Levers(45, 50, 2500, 35), {})


def test_the_published_rules_are_the_default_levers() -> None:
    assert levers_from_rules(default_rules()) == Levers(50, 50, 2500, 35, 2)


@pytest.mark.skipif(not (ARTIFACTS / "pricing" / "events.json").exists(), reason="pricing table not built")
def test_the_committed_table_reproduces_premiums_json_and_the_report_at_the_rules_levers() -> None:
    """The simulator and the backtest agree: same premium in every zone, same recall and false payouts."""
    committed = json.loads((ARTIFACTS / "pricing" / "events.json").read_text(encoding="utf-8"))
    premiums = json.loads((ARTIFACTS / "premiums.json").read_text(encoding="utf-8"))
    report = json.loads((ARTIFACTS / "backtest" / "report.json").read_text(encoding="utf-8"))
    result = price(committed, levers_from_rules(default_rules()), premiums)
    assert {z["zone_id"]: z["premium_per_day_paise"] for z in result["zones"]} == premiums
    chhatri = next(t for t in report["triggers"] if t["name"] == "chhatri")
    city = result["city"]
    assert (city["real_drops_paid"], city["real_drops"]) == (
        chhatri["real_drops_paid"],
        chhatri["real_drops"],
    )
    assert (city["payouts_no_real_drop"], city["payouts"]) == (
        chhatri["payouts_no_real_drop"],
        chhatri["payouts"],
    )


def test_the_table_builder_changes_only_the_index_floor(tmp_path: Path) -> None:
    rules = default_rules()
    lower = _with_floor(rules, 40)
    assert lower.area.index_floor_pct == 40
    assert lower.model_copy(update={"area": rules.area}) == rules
    path = write_table({"floors": [40]}, tmp_path)
    assert path == tmp_path / "pricing" / "events.json" and json.loads(path.read_text()) == {"floors": [40]}
