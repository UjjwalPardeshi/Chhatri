"""Backtest metrics, premiums and loss ratios (SPEC §9.7, §18)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from types import MappingProxyType

import pytest

from chhatri.backtest.ledger import ClaimOutcome
from chhatri.backtest.metrics import (
    DAYS_PER_YEAR,
    drop_breakdown,
    paid_zone_days,
    personal_metrics,
    premium_per_day,
    ratio,
    real_drops,
    trigger_metrics,
    trigger_to_money,
    zone_economics,
)
from chhatri.clock import at
from chhatri.domain.enums import ClaimKind, DecisionOutcome
from chhatri.policy.rules import PolicyRules
from chhatri.sim.types import GroundTruth

D1, D2, D3 = date(2024, 7, 1), date(2024, 7, 2), date(2024, 7, 3)


def _area(
    zone: str, day: date, amount: int, outcome: DecisionOutcome = DecisionOutcome.APPROVED
) -> ClaimOutcome:
    decided = at(day, 17)
    credited = decided + timedelta(minutes=4) if outcome is DecisionOutcome.APPROVED else None
    return ClaimOutcome(ClaimKind.AREA, f"S-{zone}", zone, day, decided, credited, outcome, amount)


def _personal(outcome: DecisionOutcome, amount: int = 0, *, doubtful: bool = False) -> ClaimOutcome:
    return ClaimOutcome(
        ClaimKind.PERSONAL, "S-0001", "Z7", D1, at(D2, 12), None, outcome, amount, doubtful=doubtful
    )


@pytest.mark.parametrize(
    ("num", "den", "expected"),
    [(1, 3, 0.3333), (2, 3, 0.6667), (1, 8, 0.125), (0, 5, 0.0), (5, 0, 0.0), (1, 20000, 0.0001)],
)
def test_ratio_rounds_half_up(num: int, den: int, expected: float) -> None:
    assert ratio(num, den) == expected


def test_trigger_metrics_counts_zone_days() -> None:
    outcomes = [
        _area("Z7", D1, 138_000),
        _area("Z7", D1, 50_000),  # same zone-day: one payout
        _area("Z3", D1, 0, DecisionOutcome.DECLINED),  # nothing paid: not a payout
        _area("Z3", D2, 20_000),
        _personal(DecisionOutcome.APPROVED, 150_000),  # personal claims are not area payouts
    ]
    drops = frozenset({("Z7", D1), ("Z3", D1), ("Z12", D3)})
    m = trigger_metrics("chhatri", outcomes, drops)
    assert (m.real_drops, m.real_drops_paid, m.payouts, m.payouts_no_real_drop) == (3, 1, 2, 1)
    assert m.recall == 0.3333 and m.false_positive_rate == 0.5
    assert m.paid_paise == 208_000
    assert paid_zone_days(outcomes) == {("Z7", D1), ("Z3", D2)}


def test_trigger_metrics_without_payouts_or_drops() -> None:
    m = trigger_metrics("weather_only", [], frozenset())
    assert (m.recall, m.false_positive_rate, m.payouts, m.paid_paise) == (0.0, 0.0, 0, 0)


def test_premium_formula_spec_9_7(rules: PolicyRules) -> None:
    # 100 shops, 2 seasons, ₹3,65,000 paid: ₹1,825 per shop-year / 365 / 0.65 = ₹7.6923… → 769 paise
    assert premium_per_day(36_500_000, 100, 2, rules) == 769
    assert premium_per_day(0, 100, 2, rules) == 200  # min_per_day_rupees floor
    assert premium_per_day(10_000_000, 0, 2, rules) == 200
    assert premium_per_day(10_000_000, 10, 0, rules) == 200


def test_premium_rounds_half_up(rules: PolicyRules) -> None:
    # 8 shops, 1 season: 475,449 / 8 / 365 / 0.65 = 250.5 paise exactly → 251 (ROUND_HALF_UP)
    assert premium_per_day(475_449, 8, 1, rules) == 251
    assert premium_per_day(475_448, 8, 1, rules) == 250


def test_zone_economics(rules: PolicyRules) -> None:
    chhatri = [
        _area("Z7", D1, 3_650_000),
        _area("Z7", D2, 3_650_000),
        _area("Z3", D1, 0, DecisionOutcome.DECLINED),
    ]
    drops = frozenset({("Z7", D1), ("Z3", D1), ("Z3", D3)})
    rows = zone_economics(["Z3", "Z7", "Z9"], {"Z3": 10, "Z7": 10, "Z9": 0}, chhatri, drops, 1, rules)
    z3, z7, z9 = rows
    assert z7.premium_per_day_paise == 3077  # ₹7,300 per shop-year / 365 / 0.65 = ₹30.769… → ₹30.77
    assert z7.premiums_paise == 3077 * 10 * DAYS_PER_YEAR
    assert z7.payouts_paise == 7_300_000
    assert z7.loss_ratio == ratio(7_300_000, 3077 * 10 * DAYS_PER_YEAR)
    assert (z7.chhatri_fp, z7.chhatri_fn) == (1, 0)
    assert (z3.premium_per_day_paise, z3.payouts_paise, z3.chhatri_fp, z3.chhatri_fn) == (200, 0, 0, 2)
    assert (z9.premiums_paise, z9.loss_ratio, z9.covered_shops) == (0, 0.0, 0)


def test_personal_metrics() -> None:
    outcomes = [
        _personal(DecisionOutcome.APPROVED, 150_000),
        _personal(DecisionOutcome.APPROVED, 300_000),
        _personal(DecisionOutcome.REFERRED, doubtful=True),
        _personal(DecisionOutcome.REFERRED),
        _personal(DecisionOutcome.DECLINED, doubtful=True),
        _area("Z7", D1, 1),
    ]
    p = personal_metrics(outcomes)
    assert (p.claims, p.auto_paid, p.referred, p.declined) == (5, 2, 2, 1)
    assert p.referred_share == 0.4 and p.paid_paise == 450_000
    assert (p.doubtful, p.doubtful_referred, p.doubtful_auto_paid) == (2, 1, 0)
    empty = personal_metrics([])
    assert (empty.referred_share, empty.doubtful) == (0.0, 0)
    leaked = personal_metrics([_personal(DecisionOutcome.APPROVED, 150_000, doubtful=True)])
    assert leaked.doubtful_auto_paid == 1


def test_trigger_to_money(rules: PolicyRules) -> None:
    assert trigger_to_money([_area("Z7", D1, 1)], rules) == "same day · 4 min"
    late = ClaimOutcome(
        ClaimKind.AREA,
        "S-1",
        "Z7",
        D1,
        at(D2, 0),
        at(D2, 0) + timedelta(minutes=4),
        DecisionOutcome.APPROVED,
        1,
    )
    assert trigger_to_money([_area("Z7", D1, 1), late], rules) == "same day for 1 of 2 payouts · 4 min"


def test_real_drops_are_every_shock_loss_of_at_least_40_pct() -> None:
    # SPEC §18: "true shock-caused loss ≥ 40 % of expected day sales", whatever the shock.
    losses = {("Z1", D1): 0.40, ("Z2", D1): 0.39, ("Z3", D1): 0.75, ("Z4", D1): 0.45, ("Z5", D1): 0.0}
    labels = {("Z1", D1): "rain", ("Z2", D1): "rain", ("Z3", D1): "bandh", ("Z4", D1): "slow_day"}
    labels[("Z5", D1)] = "normal"
    truth = GroundTruth(MappingProxyType(losses), MappingProxyType(labels), MappingProxyType({}))
    assert real_drops(truth) == {("Z1", D1), ("Z3", D1), ("Z4", D1)}


def test_drop_breakdown_by_label() -> None:
    labels = {("Z1", D1): "rain", ("Z2", D1): "rain", ("Z3", D1): "bandh", ("Z4", D2): "slow_day"}
    chhatri = frozenset({("Z1", D1), ("Z3", D1), ("Z9", D3)})
    weather = frozenset({("Z2", D1), ("Z1", D1)})
    rows = drop_breakdown(labels, chhatri, weather)
    assert [(r.label, r.drops, r.chhatri_paid, r.weather_paid) for r in rows] == [
        ("rain", 2, 1, 2),
        ("bandh", 1, 1, 0),
        ("slow_day", 1, 0, 0),
    ]
    assert drop_breakdown({}, chhatri, weather) == ()
    with pytest.raises(ValueError, match="label"):
        drop_breakdown({("Z1", D1): "hail"}, chhatri, weather)


def test_outcome_times_are_aware() -> None:
    assert isinstance(_area("Z7", D1, 1).decided_at, datetime)
    assert _area("Z7", D1, 1).decided_at.utcoffset() == timedelta(hours=5, minutes=30)
