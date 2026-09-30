"""Shop-type parameters (SPEC §5.3, §6.2).

One `ShopTypeSpec` per `ShopType`: the table of §5.3 (median day, rain sensitivity, average ticket,
business hours) plus the fixed hourly curve and day-of-week multipliers. Hourly curves are relative
weights over business hours only, normalised to sum to 1 by `hour_weights`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from chhatri.domain.enums import ShopType
from chhatri.money import rupees

HOURS_PER_DAY = 24
DAYS_PER_WEEK = 7


@dataclass(frozen=True, slots=True)
class ShopTypeSpec:
    """Per-type constants. ``curve`` has one relative weight per hour in [open_hour, close_hour)."""

    shop_type: ShopType
    label: str
    median_day_paise: int
    rain_sensitivity: float
    avg_ticket_paise: int
    open_hour: int
    close_hour: int
    curve: tuple[float, ...]
    dow_mult: tuple[float, ...]  # Mon..Sun
    festival: bool  # SPEC §6.3 Ganesh uplift applies (food, sweets, kirana)
    mix_weight: float  # share of generated shops of this type

    def __post_init__(self) -> None:
        if len(self.curve) != self.close_hour - self.open_hour:
            raise ValueError(f"{self.shop_type}: curve needs one weight per business hour")
        if len(self.dow_mult) != DAYS_PER_WEEK or min(self.curve) <= 0:
            raise ValueError(f"{self.shop_type}: bad dow_mult or non-positive curve weight")

    @property
    def hour_weights(self) -> tuple[float, ...]:
        """24 weights summing to 1, zero outside [open_hour, close_hour) (SPEC §24.1)."""
        total = sum(self.curve)
        weights = [0.0] * HOURS_PER_DAY
        for offset, weight in enumerate(self.curve):
            weights[self.open_hour + offset] = weight / total
        return tuple(weights)


_SPECS = (
    # Tea: peaks 07-10 and 16-19 (SPEC §5.3); quieter at weekends (office crowd).
    ShopTypeSpec(ShopType.TEA_STALL, "Tea Stall", rupees(4000), 0.85, rupees(18), 6, 22,
                 (4, 9, 10, 9, 5, 4, 4, 4, 4, 5, 8, 9, 8, 5, 3, 2),
                 (1.00, 1.00, 1.00, 1.00, 1.02, 0.95, 0.90), True, 0.20),
    # Street food: peaks 12-14 and 18-22; Sunday +10 %.
    ShopTypeSpec(ShopType.STREET_FOOD, "Snack Centre", rupees(6000), 0.90, rupees(45), 10, 23,
                 (2, 4, 8, 9, 6, 4, 4, 6, 9, 11, 11, 9, 5),
                 (0.95, 0.95, 0.95, 0.97, 1.05, 1.08, 1.10), True, 0.18),
    ShopTypeSpec(ShopType.FRUIT_VEG, "Fruit & Veg", rupees(5000), 0.90, rupees(60), 7, 21,
                 (8, 10, 9, 7, 5, 4, 3, 3, 4, 6, 9, 10, 9, 6),
                 (1.00, 0.98, 0.98, 1.00, 1.00, 1.05, 1.10), True, 0.15),
    ShopTypeSpec(ShopType.KIRANA, "Kirana Store", rupees(9000), 0.55, rupees(120), 7, 22,
                 (5, 7, 8, 8, 7, 6, 5, 5, 5, 6, 8, 9, 9, 7, 4),
                 (0.98, 0.97, 0.97, 0.98, 1.00, 1.05, 1.08), True, 0.20),
    ShopTypeSpec(ShopType.PHARMACY, "Medical Store", rupees(12000), 0.35, rupees(250), 8, 23,
                 (3, 5, 7, 7, 6, 6, 5, 5, 6, 7, 8, 9, 9, 7, 4),
                 (1.02, 1.00, 1.00, 1.00, 1.00, 0.98, 0.92), False, 0.08),
    # Salons: Tuesday is the traditional slow day in Mumbai; weekends busy.
    ShopTypeSpec(ShopType.SALON, "Hair Salon", rupees(3500), 0.80, rupees(150), 9, 21,
                 (3, 6, 8, 8, 7, 6, 6, 7, 9, 10, 9, 6),
                 (0.95, 0.80, 0.95, 1.00, 1.05, 1.20, 1.25), False, 0.09),
    # Mobile recharge: Sunday -30 %.
    ShopTypeSpec(ShopType.MOBILE_RECHARGE, "Mobile Recharge", rupees(3000), 0.70, rupees(100), 9, 21,
                 (4, 6, 8, 8, 7, 6, 7, 8, 9, 9, 8, 5),
                 (1.05, 1.02, 1.02, 1.02, 1.02, 0.95, 0.70), False, 0.10),
)  # fmt: skip

SHOP_TYPE_SPECS: Mapping[ShopType, ShopTypeSpec] = MappingProxyType({s.shop_type: s for s in _SPECS})
SHOP_TYPE_ORDER: tuple[ShopType, ...] = tuple(s.shop_type for s in _SPECS)
SHOP_TYPE_MIX: tuple[float, ...] = tuple(s.mix_weight for s in _SPECS)
FESTIVAL_SHOP_TYPES: frozenset[ShopType] = frozenset(s.shop_type for s in _SPECS if s.festival)

if abs(sum(SHOP_TYPE_MIX) - 1.0) > 1e-9 or set(SHOP_TYPE_SPECS) != set(ShopType):
    raise RuntimeError("shop-type table must cover every ShopType with mix weights summing to 1")
