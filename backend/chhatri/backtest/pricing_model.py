"""Price the cover for any product levers from the pricing table (business model §3; `chhatri.backtest.pricing`).

Levers: the area index floor (one of the table's floors), the payout share, the area daily cap and the loading. For
one set of levers every zone gets the same treatment the backtest gives the rules today:

- each trigger pays every covered shop of its zone ``min(cap, share × published expected day × drop %)``, rounded
  to the rupee half up (SPEC §4.3);
- the expected annual payout per shop is the zone's payouts ÷ covered shops ÷ seasons (one monsoon is one policy
  year, business model §3.1);
- the premium per day is ``max(₹2, expected annual payout ÷ 365 ÷ (1 − loading))`` in paise, half up (SPEC §9.7).

City-wide, the floor also sets the trigger's quality against the simulator's ground truth: the share of real drops
that got a trigger, and the share of triggers with no real drop. Area claims only: hospital cash, the waiting
period and the annual limit are not in the table, so a price here is a planning figure, not an actuarial one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from statistics import median
from typing import Any, Final

__all__ = ["Levers", "ZonePrice", "levers_from_rules", "price"]

DAYS_PER_YEAR: Final = Decimal(365)
DAYS_PER_MONTH: Final = 30
PAISE: Final = 100
PERCENT: Final = Decimal(100)
ONE: Final = Decimal(1)


@dataclass(frozen=True, slots=True)
class Levers:
    floor_pct: int
    share_pct: int
    cap_rupees: int
    loading_pct: int
    min_per_day_rupees: int = 2


@dataclass(frozen=True, slots=True)
class ZonePrice:
    zone_id: str
    shops: int
    triggers: int
    payout_paise: int
    expected_payout_per_year_paise: int
    premium_per_day_paise: int

    def to_wire(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "shops": self.shops,
            "triggers": self.triggers,
            "expected_payout_per_year_paise": self.expected_payout_per_year_paise,
            "premium_per_day_paise": self.premium_per_day_paise,
        }


def levers_from_rules(rules: Any) -> Levers:
    """The levers the published rule set uses today."""
    return Levers(
        floor_pct=rules.area.index_floor_pct,
        share_pct=int(round(rules.payout_share * 100)),
        cap_rupees=rules.area.daily_cap_rupees,
        loading_pct=int(round(rules.premium.loading * 100)),
        min_per_day_rupees=rules.premium.min_per_day_rupees,
    )


def _half_up(value: Decimal) -> int:
    return int(value.quantize(ONE, rounding=ROUND_HALF_UP))


def _shop_payout(expected_rupees: int, drop_pct: int, levers: Levers) -> int:
    """One shop's area payout in rupees for one trigger."""
    lost = Decimal(expected_rupees) * Decimal(drop_pct) / PERCENT
    return min(levers.cap_rupees, _half_up(Decimal(levers.share_pct) / PERCENT * lost))


def _premium_paise(per_year_paise: Decimal, levers: Levers) -> int:
    loading = Decimal(levers.loading_pct) / PERCENT
    daily = per_year_paise / DAYS_PER_YEAR / (ONE - loading)
    return max(levers.min_per_day_rupees * PAISE, _half_up(daily))


def _zone_prices(
    table: Mapping[str, Any], events: Sequence[Sequence[Any]], levers: Levers
) -> list[ZonePrice]:
    seasons = len(table["seasons"])
    paid: dict[str, int] = {}
    count: dict[str, int] = {}
    for zone_id, _day, drop_pct, _real, expected in events:
        paid[zone_id] = paid.get(zone_id, 0) + sum(_shop_payout(e, drop_pct, levers) for e in expected)
        count[zone_id] = count.get(zone_id, 0) + 1
    prices = []
    for zone_id, shops in sorted(table["shops"].items(), key=lambda kv: int(kv[0][1:])):
        payout_paise = paid.get(zone_id, 0) * PAISE
        per_year = Decimal(payout_paise) / Decimal(shops * seasons) if shops else Decimal(0)
        prices.append(
            ZonePrice(
                zone_id,
                shops,
                count.get(zone_id, 0),
                payout_paise,
                _half_up(per_year),
                _premium_paise(per_year, levers),
            )
        )
    return prices


def _quality(table: Mapping[str, Any], events: Sequence[Sequence[Any]]) -> dict[str, Any]:
    real_days = {(zone, day) for zone, day, _drop, real, _e in events if real}
    payouts = len(events)
    no_real = sum(1 for *_head, real, _e in events if not real)
    real_total = int(table["real_drops"])
    return {
        "real_drops": real_total,
        "real_drops_paid": len(real_days),
        "recall": round(len(real_days) / real_total, 4) if real_total else None,
        "payouts": payouts,
        "payouts_no_real_drop": no_real,
        "false_payout_share": round(no_real / payouts, 4) if payouts else None,
    }


def price(table: Mapping[str, Any], levers: Levers, current_paise: Mapping[str, int]) -> dict[str, Any]:
    """Every zone's price for ``levers``, the city summary and the trigger's quality. ``current_paise`` is today's
    premium per zone (premiums.json), for the loss ratio a zone would run at today's price."""
    key = str(levers.floor_pct)
    if key not in table["events"]:
        raise ValueError(f"floor must be one of {table['floors']}")
    events = table["events"][key]
    zones = _zone_prices(table, events, levers)
    premiums = [z.premium_per_day_paise for z in zones]
    wire = []
    for zone in zones:
        today = current_paise.get(zone.zone_id)
        ratio = (
            None
            if not today
            else round(zone.expected_payout_per_year_paise / (today * int(DAYS_PER_YEAR)), 4)
        )
        wire.append(
            {
                **zone.to_wire(),
                "premium_per_month_paise": zone.premium_per_day_paise * DAYS_PER_MONTH,
                "premium_per_year_paise": zone.premium_per_day_paise * int(DAYS_PER_YEAR),
                "payout_days_per_year": round(zone.triggers / len(table["seasons"]), 2),
                "current_premium_per_day_paise": today,
                "loss_ratio_at_current_price": ratio,
            }
        )
    return {
        "label": table["label"],
        "seasons": table["seasons"],
        "floors": table["floors"],
        "zones": wire,
        "city": {
            "premium_min_paise": min(premiums),
            "premium_median_paise": _half_up(Decimal(str(median(premiums)))),
            "premium_max_paise": max(premiums),
            **_quality(table, events),
        },
    }
