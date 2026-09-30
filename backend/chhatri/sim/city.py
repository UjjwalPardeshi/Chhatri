"""City builder: zones, merchants, profiles, covers and loans (SPEC §5.3-§5.5, §17.4, §24.1).

Shop numbers per zone count covered pilot merchants only (§5.4): full scale Z7=46, Z3=141,
Z12=125, Z9=64 and every other zone a seed-deterministic count in 30..120; small scale Z3=40,
Z7=46, Z9=25, Z12=30 and no other shops. Anil (S-0142) is one of Z7's 46; Ramesh (S-0907) is an
extra, uncovered merchant in Z3. Generated ids run S-0001.. in zone order (Z1..Z24), skipping
the demo ids. Every merchant speaks Hindi (the language the conversation templates cover, §13).

Calibration hooks (§17.4): Anil's base day, a common scale on Z7's other merchants, and one Z7
merchant fine-tuned to an exact base day. Rain and slow-day hooks are applied by the scenarios.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Literal

import h3

from chhatri.domain.enums import Language, ShopType
from chhatri.domain.models import Merchant
from chhatri.policy.rules import PolicyRules, default_rules
from chhatri.sim.geo import WardGeography, build_geography, ward_zone_ids, with_hex_shops, zone_number
from chhatri.sim.merchants import (
    GeneratedShop,
    ZonePlacer,
    cover_for,
    generate_shop,
    loan_for,
    phone_for,
)
from chhatri.sim.profiles import SHOP_TYPE_SPECS
from chhatri.sim.rng import Stream, generator
from chhatri.sim.types import Calibration, City, ShopProfile

__all__ = ["City", "build_city", "shops_per_zone", "ANIL_ID", "RAMESH_ID", "DEMO_IDS"]

logger = logging.getLogger(__name__)

Scale = Literal["full", "small"]
ANIL_ID = "S-0142"
RAMESH_ID = "S-0907"
DEMO_IDS = frozenset({ANIL_ID, RAMESH_ID})
PILOT_SHOPS_FULL: Mapping[str, int] = MappingProxyType({"Z7": 46, "Z3": 141, "Z12": 125, "Z9": 64})
PILOT_SHOPS_SMALL: Mapping[str, int] = MappingProxyType({"Z3": 40, "Z7": 46, "Z9": 25, "Z12": 30})
OTHER_ZONE_SHOPS = (30, 120)  # inclusive, SPEC §5.1
WARDS_FILE = Path("geo") / "bmc_wards.geojson"
ANIL_LOAN_DAILY_PAISE = 60_000  # Rs 600 (SPEC §5.4)
ANIL_LOAN_REMAINING_DAYS = 120
ANIL_COVER_PURCHASED = (date(2025, 3, 10), 11)  # well inside the 60..400-day window
ANIL = Merchant(
    id=ANIL_ID,
    shop_name="Anil's Tea Stall",
    owner_name="Anil Jadhav",
    owner_name_hi="अनिल",
    kyc_name="ANIL RAMESH JADHAV",
    phone=phone_for(142),
    language=Language.HI,
    zone_id="Z7",
    lat=19.0046,
    lng=72.8424,
    h3_cell="",  # set from the grid in `_demo_shops`
    shop_type=ShopType.TEA_STALL,
    weekly_off=None,
    is_demo=True,
)
RAMESH = Merchant(
    id=RAMESH_ID,
    shop_name="Ramesh Vada Pav",
    owner_name="Ramesh Pawar",
    owner_name_hi="रमेश",
    kyc_name="RAMESH VITTHAL PAWAR",
    phone=phone_for(907),
    language=Language.HI,
    zone_id="Z3",
    lat=19.0100,
    lng=72.8180,
    h3_cell="",
    shop_type=ShopType.STREET_FOOD,
    weekly_off=None,
    is_demo=True,
)

COVERED_DEMO = (ANIL,)


def shops_per_zone(seed: int, zone_ids: tuple[str, ...], scale: Scale) -> Mapping[str, int]:
    """Covered-shop count per zone (SPEC §5.1); other zones drawn from one seeded stream."""
    if scale == "small":
        return PILOT_SHOPS_SMALL
    if scale != "full":
        raise ValueError(f"scale must be 'full' or 'small', got {scale!r}")
    others = [z for z in zone_ids if z not in PILOT_SHOPS_FULL]
    draws = generator(seed, Stream.ZONE_SHOP_COUNTS).integers(
        OTHER_ZONE_SHOPS[0], OTHER_ZONE_SHOPS[1] + 1, len(others)
    )
    counts = dict(PILOT_SHOPS_FULL) | {z: int(n) for z, n in zip(others, draws, strict=True)}
    return MappingProxyType({z: counts[z] for z in zone_ids})


def _demo_shops(
    geography: WardGeography, calibration: Calibration, rules: PolicyRules
) -> list[GeneratedShop]:
    shops = []
    for demo in (ANIL, RAMESH):
        if geography.zone_of(demo.lat, demo.lng) != demo.zone_id:
            raise ValueError(f"demo merchant {demo.id} is not inside zone {demo.zone_id}")
        cell = next(
            (hx.h3 for hx in geography.hexes if hx.zone_id == demo.zone_id and _contains(hx.h3, demo)), None
        )
        if cell is None:
            raise ValueError(f"demo merchant {demo.id} is not inside any hex of {demo.zone_id}")
        merchant = demo.model_copy(update={"h3_cell": cell})
        covered = demo.id == ANIL_ID
        spec = SHOP_TYPE_SPECS[demo.shop_type]
        purchased, hour = ANIL_COVER_PURCHASED
        shops.append(
            GeneratedShop(
                merchant=merchant,
                base_day_paise=calibration.anil_base_day_paise if covered else spec.median_day_paise,
                cover=cover_for(142, purchased, hour, rules) if covered else None,
                loan=loan_for(142, ANIL_LOAN_DAILY_PAISE, ANIL_LOAN_REMAINING_DAYS) if covered else None,
            )
        )
    return shops


def _contains(cell: str, merchant: Merchant) -> bool:
    return h3.latlng_to_cell(merchant.lat, merchant.lng, h3.get_resolution(cell)) == cell


def _generated_shops(
    seed: int, geography: WardGeography, counts: Mapping[str, int], rules: PolicyRules
) -> list[GeneratedShop]:
    demo_zone_counts = Counter(m.zone_id for m in COVERED_DEMO)  # they count in the zone totals
    wards = dict(geography.ward_shapes)
    numbers = (n for n in range(1, 10_000) if f"S-{n:04d}" not in DEMO_IDS)
    shops: list[GeneratedShop] = []
    for zone in geography.zones:
        placer = ZonePlacer(zone.id, geography.hexes, wards[zone.id])
        for _ in range(counts.get(zone.id, 0) - demo_zone_counts[zone.id]):
            shops.append(generate_shop(seed, next(numbers), zone.id, placer, rules))
    return shops


def _apply_z7_calibration(shops: list[GeneratedShop], calibration: Calibration) -> list[GeneratedShop]:
    """SPEC §17.4 (d): scale Z7's other merchants, then set the tuned merchant's base exactly."""
    tune_id = calibration.z7_tune_merchant_id
    if tune_id is not None and not any(
        s.merchant.id == tune_id and s.merchant.zone_id == "Z7" for s in shops
    ):
        raise ValueError(f"z7_tune_merchant_id {tune_id} is not a generated Z7 merchant")
    out = []
    for shop in shops:
        if shop.merchant.zone_id != "Z7":
            out.append(shop)
            continue
        base = round(shop.base_day_paise * calibration.z7_other_scale)
        if shop.merchant.id == tune_id and calibration.z7_tune_base_day_paise is not None:
            base = calibration.z7_tune_base_day_paise
        out.append(GeneratedShop(shop.merchant, base, shop.cover, shop.loan))
    return out


def _profile(shop: GeneratedShop) -> ShopProfile:
    spec = SHOP_TYPE_SPECS[shop.merchant.shop_type]
    return ShopProfile(
        merchant_id=shop.merchant.id,
        base_day_paise=shop.base_day_paise,
        open_hour=spec.open_hour,
        close_hour=spec.close_hour,
        hour_weights=spec.hour_weights,
        dow_mult=spec.dow_mult,
        rain_sensitivity=spec.rain_sensitivity,
        avg_ticket_paise=spec.avg_ticket_paise,
    )


def build_city(
    seed: int, data_dir: Path, calibration: Calibration | None = None, scale: Scale = "full"
) -> City:
    """Deterministic city from the seed (SPEC §5, §24.1); ``calibration`` defaults to `Calibration()`."""
    calibration = calibration if calibration is not None else Calibration()
    rules = default_rules()
    zone_ids = tuple(sorted(ward_zone_ids().values(), key=zone_number))
    counts = shops_per_zone(seed, zone_ids, scale)
    base = build_geography(Path(data_dir) / WARDS_FILE, counts)
    generated = _apply_z7_calibration(_generated_shops(seed, base, counts, rules), calibration)
    shops = sorted([*_demo_shops(base, calibration, rules), *generated], key=lambda s: s.merchant.id)
    hex_shops = Counter(s.merchant.h3_cell for s in shops if s.cover is not None)
    geography = with_hex_shops(base, hex_shops)
    city = City(
        seed=seed,
        geography=geography,
        merchants=tuple(s.merchant for s in shops),
        profiles={s.merchant.id: _profile(s) for s in shops},
        covers={s.merchant.id: s.cover for s in shops if s.cover is not None},
        loans={s.merchant.id: s.loan for s in shops if s.loan is not None},
    )
    logger.info(
        "city seed=%d scale=%s: %d merchants, %d covered, %d loans",
        seed, scale, len(city.merchants), len(city.covers), len(city.loans),
    )  # fmt: skip
    return city
