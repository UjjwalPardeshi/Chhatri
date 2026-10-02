"""Generated and demo merchants (SPEC §5.3-§5.5).

Every generated merchant draws all of its attributes from its own counter-based stream
``(seed, MERCHANT, number)`` in a fixed order, so a shop's attributes depend only on the seed and
its id number. Placement: a uniformly chosen hex of the zone, then a uniform point inside that hex
and the ward (rejection sampling); after `PLACEMENT_TRIES` misses the hex centre is used, which is
inside the ward by construction of the grid (§5.2).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

import h3
import numpy as np
import shapely
from shapely.geometry.base import BaseGeometry

from chhatri.clock import at
from chhatri.domain.enums import CoverStatus, Language, ShopType
from chhatri.domain.models import Cover, Loan, Merchant
from chhatri.money import rupees
from chhatri.policy.rules import PolicyRules
from chhatri.sim.names import FATHER_NAMES, FIRST_NAMES, SURNAMES
from chhatri.sim.profiles import SHOP_TYPE_MIX, SHOP_TYPE_ORDER, SHOP_TYPE_SPECS
from chhatri.sim.rng import Stream, generator
from chhatri.sim.types import Hex

REFERENCE_DAY = date(2025, 8, 19)  # SPEC §17.4 replay date; cover ages count back from it
PREPAID_THROUGH = date(2025, 8, 22)  # >= every scenario day + 1 (SPEC §9.7, §17.2)
COVER_AGE_DAYS = (60, 400)  # purchased 60..400 days before the replay (SPEC §5.5)
COVER_PURCHASE_HOURS = (9, 21)  # purchase hour of day, [lo, hi)
BASE_DAY_SIGMA = 0.30  # SPEC §5.3 lognormal spread of typical day sales around the type median
WEEKLY_OFF_SHARE = 0.20  # share of shops (outside Z3/Z7/Z12) with one weekly off day
SALON_WEEKLY_OFF = 1  # Tuesday, the traditional salon holiday in Mumbai
NO_WEEKLY_OFF_ZONES = frozenset({"Z3", "Z7", "Z12"})  # SPEC §5.3
LOAN_SHARE = 0.40  # SPEC §5.5
LOAN_STEP_RUPEES = 50
LOAN_INSTALMENT_STEPS = (4, 18)  # x Rs 50 -> Rs 200..900 inclusive
LOAN_REMAINING_DAYS = (30, 240)
LENDER_NAME = "Simulated lender (NBFC partner)"
PHONE_PREFIX = "+9199000"  # SPEC §5.5: fake numbers, 10 digits after +91
PLACEMENT_TRIES = 64
COORD_DECIMALS = 6


@dataclass(frozen=True, slots=True)
class GeneratedShop:
    """One merchant with the attributes the city needs to build its profile."""

    merchant: Merchant
    base_day_paise: int
    cover: Cover | None
    loan: Loan | None


def merchant_id(number: int) -> str:
    return f"S-{number:04d}"


def phone_for(number: int) -> str:
    return f"{PHONE_PREFIX}{number:05d}"


def cover_for(
    number: int, purchased: date, hour: int, rules: PolicyRules, premium_per_day_paise: int | None = None
) -> Cover:
    """ACTIVE cover, waiting period from the rules, prepaid through `PREPAID_THROUGH` (SPEC §5.5).

    The price per day is the minimum of the rules unless the caller knows the zone's price (K6-T04).
    """
    return Cover(
        id=f"CV-{number:04d}",
        merchant_id=merchant_id(number),
        purchased_at=at(purchased, hour),
        starts_on=purchased + timedelta(days=rules.cover.waiting_period_days),
        premium_per_day_paise=premium_per_day_paise or rupees(rules.premium.min_per_day_rupees),
        prepaid_through=PREPAID_THROUGH,
        status=CoverStatus.ACTIVE,
    )


def at_zone_price(cover: Cover, zone_id: str, premiums: Mapping[str, int]) -> Cover:
    """The cover at its zone's daily price (K6-T04: Anil in Z7 pays ₹18.62, not the ₹2 minimum).

    A zone with no entry keeps the price the cover has; the loader of the table names such zones (X3).
    """
    price = premiums.get(zone_id)
    return cover if price is None else cover.model_copy(update={"premium_per_day_paise": price})


def loan_for(number: int, daily_paise: int, remaining_days: int) -> Loan:
    return Loan(
        id=f"LN-{number:04d}",
        merchant_id=merchant_id(number),
        lender_name=LENDER_NAME,
        daily_instalment_paise=daily_paise,
        outstanding_paise=daily_paise * remaining_days,
    )


class ZonePlacer:
    """Places shops inside one zone: hex chosen uniformly, point uniform in hex ∩ ward."""

    def __init__(self, zone_id: str, hexes: tuple[Hex, ...], ward: BaseGeometry) -> None:
        self._hexes = tuple(hx for hx in hexes if hx.zone_id == zone_id)
        if not self._hexes:
            raise ValueError(f"zone {zone_id} has no hexes to place shops in")
        self._ward = ward
        self._bounds: dict[str, tuple[float, float, float, float]] = {}

    def _hex_bounds(self, cell: str) -> tuple[float, float, float, float]:
        if cell not in self._bounds:
            lats, lngs = zip(*h3.cell_to_boundary(cell), strict=True)
            self._bounds[cell] = (min(lngs), min(lats), max(lngs), max(lats))
        return self._bounds[cell]

    def place(self, rng: np.random.Generator) -> tuple[float, float, str]:
        """(lat, lng, h3_cell): the first of `PLACEMENT_TRIES` candidates inside the hex and ward."""
        hx = self._hexes[int(rng.integers(len(self._hexes)))]
        min_x, min_y, max_x, max_y = self._hex_bounds(hx.h3)
        uv = rng.random((PLACEMENT_TRIES, 2))
        lngs = np.round(min_x + uv[:, 0] * (max_x - min_x), COORD_DECIMALS)
        lats = np.round(min_y + uv[:, 1] * (max_y - min_y), COORD_DECIMALS)
        resolution = h3.get_resolution(hx.h3)
        in_ward = shapely.intersects_xy(self._ward, lngs, lats)
        for i in np.flatnonzero(in_ward).tolist():
            lat, lng = float(lats[i]), float(lngs[i])
            if h3.latlng_to_cell(lat, lng, resolution) == hx.h3:
                return lat, lng, hx.h3
        return hx.center_lat, hx.center_lng, hx.h3


def _pick(rng: np.random.Generator, options: tuple) -> object:
    return options[int(rng.integers(len(options)))]


def _weekly_off(rng: np.random.Generator, zone_id: str, shop_type: ShopType) -> int | None:
    has_off = rng.random() < WEEKLY_OFF_SHARE
    day = SALON_WEEKLY_OFF if shop_type is ShopType.SALON else int(rng.integers(7))
    return day if has_off and zone_id not in NO_WEEKLY_OFF_ZONES else None


def _loan(rng: np.random.Generator, number: int) -> Loan | None:
    has_loan = rng.random() < LOAN_SHARE
    lo, hi = LOAN_INSTALMENT_STEPS
    daily = rupees(LOAN_STEP_RUPEES * int(rng.integers(lo, hi + 1)))
    remaining = int(rng.integers(LOAN_REMAINING_DAYS[0], LOAN_REMAINING_DAYS[1] + 1))
    return loan_for(number, daily, remaining) if has_loan else None


def generate_shop(
    seed: int, number: int, zone_id: str, placer: ZonePlacer, rules: PolicyRules
) -> GeneratedShop:
    """One covered pilot merchant; the draw order below is part of the determinism contract."""
    rng = generator(seed, Stream.MERCHANT, number)
    shop_type = SHOP_TYPE_ORDER[int(rng.choice(len(SHOP_TYPE_ORDER), p=SHOP_TYPE_MIX))]
    spec = SHOP_TYPE_SPECS[shop_type]
    first_en, first_hi = _pick(rng, FIRST_NAMES)  # type: ignore[misc]
    father = str(_pick(rng, FATHER_NAMES))
    surname = str(_pick(rng, SURNAMES))
    base_day = round(spec.median_day_paise * float(np.exp(BASE_DAY_SIGMA * rng.standard_normal())))
    weekly_off = _weekly_off(rng, zone_id, shop_type)
    lat, lng, cell = placer.place(rng)
    cover_age = int(rng.integers(COVER_AGE_DAYS[0], COVER_AGE_DAYS[1] + 1))
    cover_hour = int(rng.integers(*COVER_PURCHASE_HOURS))
    loan = _loan(rng, number)
    merchant = Merchant(
        id=merchant_id(number),
        shop_name=f"{first_en}'s {spec.label}",
        owner_name=f"{first_en} {surname}",
        owner_name_hi=str(first_hi),
        kyc_name=f"{first_en} {father} {surname}".upper(),
        phone=phone_for(number),
        language=Language.HI,
        zone_id=zone_id,
        lat=lat,
        lng=lng,
        h3_cell=cell,
        shop_type=shop_type,
        weekly_off=weekly_off,
        is_demo=False,
    )
    cover = cover_for(number, REFERENCE_DAY - timedelta(days=cover_age), cover_hour, rules)
    return GeneratedShop(merchant=merchant, base_day_paise=base_day, cover=cover, loan=loan)
