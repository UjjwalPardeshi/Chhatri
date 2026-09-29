"""City builder (SPEC §5.3, §5.4, §5.5, §24.1).

Generates merchants deterministically from seed, assigns shop types, profiles, covers and loans.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import numpy as np

from chhatri.clock import ist
from chhatri.domain.enums import CoverStatus, Language, ShopType
from chhatri.domain.models import Cover, Loan, Merchant
from chhatri.money import rupees
from chhatri.sim.geo import build_geography
from chhatri.sim.types import Calibration, City, ShopProfile

# Shop type characteristics (SPEC §5.3)
SHOP_PROFILES = {
    ShopType.TEA_STALL: {
        "median_day_paise": rupees(4000),
        "rain_sensitivity": 0.85,
        "avg_ticket_paise": 18,
        "open_hour": 6,
        "close_hour": 22,
        "hour_weights": (
            0.05, 0.06, 0.05, 0.03, 0.02, 0.02,  # 00-05
            0.08, 0.10, 0.10, 0.08, 0.06, 0.05,  # 06-11
            0.04, 0.04, 0.04, 0.07, 0.08, 0.09,  # 12-17
            0.04, 0.03, 0.02, 0.01, 0.00, 0.00   # 18-23
        ),
        "dow_mult": (1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 1.05),  # Mon-Sun
    },
    ShopType.STREET_FOOD: {
        "median_day_paise": rupees(6000),
        "rain_sensitivity": 0.90,
        "avg_ticket_paise": 45,
        "open_hour": 10,
        "close_hour": 23,
        "hour_weights": (
            0.00, 0.00, 0.00, 0.00, 0.00, 0.00,
            0.00, 0.00, 0.00, 0.01, 0.03, 0.04,
            0.08, 0.10, 0.08, 0.06, 0.04, 0.08,
            0.12, 0.14, 0.12, 0.04, 0.00, 0.00
        ),
        "dow_mult": (0.9, 0.9, 0.9, 0.9, 0.95, 1.2, 1.3),  # Sun +30%
    },
    ShopType.FRUIT_VEG: {
        "median_day_paise": rupees(5000),
        "rain_sensitivity": 0.90,
        "avg_ticket_paise": 60,
        "open_hour": 7,
        "close_hour": 21,
        "hour_weights": (
            0.01, 0.01, 0.01, 0.01, 0.02, 0.03,
            0.10, 0.12, 0.11, 0.08, 0.06, 0.05,
            0.05, 0.04, 0.04, 0.05, 0.06, 0.07,
            0.05, 0.03, 0.02, 0.00, 0.00, 0.00
        ),
        "dow_mult": (1.0, 1.0, 1.0, 1.0, 1.0, 0.9, 1.1),
    },
    ShopType.KIRANA: {
        "median_day_paise": rupees(9000),
        "rain_sensitivity": 0.55,
        "avg_ticket_paise": 120,
        "open_hour": 7,
        "close_hour": 22,
        "hour_weights": (
            0.02, 0.02, 0.02, 0.02, 0.03, 0.04,
            0.08, 0.09, 0.08, 0.07, 0.06, 0.06,
            0.08, 0.08, 0.08, 0.07, 0.06, 0.06,
            0.06, 0.04, 0.03, 0.02, 0.00, 0.00
        ),
        "dow_mult": (1.0, 1.0, 1.0, 1.0, 1.0, 0.95, 1.05),
    },
    ShopType.PHARMACY: {
        "median_day_paise": rupees(12000),
        "rain_sensitivity": 0.35,
        "avg_ticket_paise": 250,
        "open_hour": 8,
        "close_hour": 23,
        "hour_weights": (
            0.02, 0.02, 0.02, 0.02, 0.02, 0.02,
            0.03, 0.04, 0.06, 0.07, 0.07, 0.07,
            0.08, 0.08, 0.07, 0.07, 0.07, 0.08,
            0.08, 0.08, 0.07, 0.04, 0.01, 0.00
        ),
        "dow_mult": (1.05, 1.05, 1.05, 1.05, 1.05, 0.95, 1.0),
    },
    ShopType.SALON: {
        "median_day_paise": rupees(3500),
        "rain_sensitivity": 0.80,
        "avg_ticket_paise": 150,
        "open_hour": 9,
        "close_hour": 21,
        "hour_weights": (
            0.00, 0.00, 0.00, 0.00, 0.00, 0.00,
            0.00, 0.00, 0.00, 0.05, 0.07, 0.08,
            0.10, 0.10, 0.09, 0.08, 0.08, 0.10,
            0.12, 0.08, 0.00, 0.00, 0.00, 0.00
        ),
        "dow_mult": (0.9, 1.2, 0.9, 1.0, 1.0, 1.0, 0.8),  # Tue popular, Sun low
    },
    ShopType.MOBILE_RECHARGE: {
        "median_day_paise": rupees(3000),
        "rain_sensitivity": 0.70,
        "avg_ticket_paise": 100,
        "open_hour": 9,
        "close_hour": 21,
        "hour_weights": (
            0.00, 0.00, 0.00, 0.00, 0.00, 0.00,
            0.00, 0.00, 0.00, 0.05, 0.06, 0.07,
            0.08, 0.08, 0.08, 0.09, 0.10, 0.10,
            0.10, 0.05, 0.00, 0.00, 0.00, 0.00
        ),
        "dow_mult": (0.7, 1.0, 1.0, 1.0, 1.0, 1.0, 0.7),  # Lower on weekends
    },
}

# Merchant name generation from seed
FIRST_NAMES_HI = [
    ("Anil", "अनिल"), ("Ramesh", "रमेश"), ("Vikram", "विक्रम"), ("Sanjay", "संजय"),
    ("Rajesh", "राजेश"), ("Sunil", "सुनिल"), ("Akshay", "अक्षय"), ("Arjun", "अर्जुन"),
    ("Rohan", "रोहन"), ("Nitin", "नितिन"), ("Hemant", "हेमंत"), ("Manoj", "मनोज"),
    ("Ashok", "अशोक"), ("Balaji", "बालाजी"), ("Chetan", "चेतन"), ("Deepak", "दीपक"),
    ("Eknath", "एकनाथ"), ("Govind", "गोविंद"), ("Hari", "हरि"), ("Ishan", "ईशान"),
    ("Jagat", "जगत"), ("Keshav", "केशव"), ("Lokesh", "लोकेश"), ("Mohan", "मोहन"),
    ("Naresh", "नरेश"), ("Om", "ॐ"), ("Pradeep", "प्रदीप"), ("Quresh", "कुरेश"),
    ("Rajiv", "राजीव"), ("Shekhar", "शेखर"), ("Tushar", "तुषार"), ("Uday", "उदय"),
    ("Varun", "वरुण"), ("Wasim", "वसीम"), ("Xavier", "जेवियर"), ("Yash", "यश"),
    ("Zeeshan", "जीशान"), ("Ashish", "आशीष"), ("Bhushan", "भूषण"), ("Chirag", "चिराग"),
]

LAST_NAMES = [
    "Jadhav", "Pawar", "Sharma", "Patel", "Singh", "Khan", "Desai", "Rao",
    "Dey", "Gupta", "Verma", "Saxena", "Mishra", "Nair", "Iyer", "Menon",
    "Reddy", "Yadav", "Joshi", "Kulkarni", "Pathak", "Pandey", "Bhattacharya",
]


def _normalize_merchant_names() -> list[tuple[str, str, str]]:
    """Generate (first_name, first_name_hi, last_name) tuples."""
    names = []
    for first_en, first_hi in FIRST_NAMES_HI:
        for last_name in LAST_NAMES:
            names.append((first_en, first_hi, last_name))
    return names


MERCHANT_NAMES = _normalize_merchant_names()


def build_city(
    seed: int,
    data_dir: Path,
    calibration: Calibration | None = None,
    scale: str = "full"
) -> City:
    """Build a deterministic city from seed.

    Args:
        seed: Random seed for deterministic generation
        data_dir: Path to data directory (contains geo/bmc_wards.geojson)
        calibration: Calibration data (from load_calibration); if None, uses defaults
        scale: "full" (all wards) or "small" (only Z3, Z7, Z9, Z12 with demo merchants)

    Returns:
        City with merchants, covers, loans, and geographic data.
    """
    if calibration is None:
        calibration = Calibration()

    # Load geography
    wards_path = data_dir / "geo" / "bmc_wards.geojson"

    # Determine shop counts per zone
    if scale == "small":
        shops_per_zone = {
            "Z3": 40,
            "Z7": 46,
            "Z9": 25,
            "Z12": 30,
        }
    else:
        shops_per_zone = {
            "Z7": 46,
            "Z3": 141,
            "Z12": 125,
            "Z9": 64,
        }
        # Generate counts for other zones (deterministic 30-120)
        other_count_rng = np.random.default_rng(seed + 1000)
        other_zones = [f"Z{i}" for i in range(1, 25) if f"Z{i}" not in shops_per_zone]
        for zone_id in other_zones:
            shops_per_zone[zone_id] = int(other_count_rng.integers(30, 121))

    geography = build_geography(wards_path, shops_per_zone, resolution=8)

    # Demo merchants (fixed)
    # S-0142: Anil Jadhav (Z7, F/S, Parel)
    # S-0907: Ramesh Pawar (Z3, G/S, Worli)

    demo_merchants_data = {
        "S-0142": {
            "name_en": "Anil Jadhav",
            "name_hi": "अनिल",
            "zone_id": "Z7",
            "shop_name": "Anil's Tea Stall",
            "shop_type": ShopType.TEA_STALL,
            "lat": 19.0046,
            "lng": 72.8424,
            "loan_daily_paise": 60_000,  # ₹600
            "cover_purchased_days_ago": 60,
        },
        "S-0907": {
            "name_en": "Ramesh Pawar",
            "name_hi": "रमेश",
            "zone_id": "Z3",
            "shop_name": "Ramesh Vada Pav",
            "shop_type": ShopType.STREET_FOOD,
            "lat": 19.0170,
            "lng": 72.8299,
            "has_cover": False,  # Ramesh is NOT covered
            "has_loan": False,
        },
    }

    merchants_list: list[Merchant] = []
    covers_dict: dict[str, Cover] = {}
    loans_dict: dict[str, Loan] = {}
    profiles_dict: dict[str, ShopProfile] = {}

    # Add demo merchants first
    for merchant_id, data in demo_merchants_data.items():
        zone = geography.zone(data["zone_id"])
        shop_type = data["shop_type"]

        # Find h3 cell for this location
        h3_cell = None
        for hex_obj in geography.hexes:
            if hex_obj.zone_id == data["zone_id"]:
                h3_cell = hex_obj.h3
                break
        if not h3_cell:
            h3_cell = geography.hexes[0].h3  # Fallback

        merchant = Merchant(
            id=merchant_id,
            shop_name=data["shop_name"],
            owner_name=data["name_en"],
            owner_name_hi=data["name_hi"],
            kyc_name=f"{data['name_en'].split()[0].upper()} RAMESH {data['name_en'].split()[-1].upper()}",
            phone=f"+9199000{int(merchant_id[2:]):05d}",
            language=Language.HI,
            zone_id=data["zone_id"],
            lat=data["lat"],
            lng=data["lng"],
            h3_cell=h3_cell,
            shop_type=shop_type,
            weekly_off=None if data["zone_id"] in ["Z3", "Z7", "Z12"] else None,
            is_demo=True
        )
        merchants_list.append(merchant)

        # Add cover if applicable
        if data.get("has_cover", True):
            purchased_at = ist(2025, 6, 20)  # Purchased 60 days before replay
            cover = Cover(
                id=f"CV-{merchant_id[2:]}",
                merchant_id=merchant_id,
                purchased_at=purchased_at,
                starts_on=purchased_at.date() + timedelta(days=7),
                premium_per_day_paise=rupees(2),  # Default
                prepaid_through=ist(2025, 9, 30).date(),  # Per SPEC §5.4
                status=CoverStatus.ACTIVE
            )
            covers_dict[merchant_id] = cover

        # Add loan if applicable
        if data.get("has_loan", data.get("loan_daily_paise") is not None):
            loan = Loan(
                id=f"LN-{merchant_id[2:]}",
                merchant_id=merchant_id,
                lender_name="Simulated lender (NBFC partner)",
                daily_instalment_paise=data.get("loan_daily_paise", 20_000),
                outstanding_paise=100_000
            )
            loans_dict[merchant_id] = loan

        # Create profile
        shop_prof = SHOP_PROFILES[shop_type]
        if merchant_id == "S-0142":  # Anil's base is calibrated
            base_day = calibration.anil_base_day_paise
        else:
            base_day = shop_prof["median_day_paise"]

        profile = ShopProfile(
            merchant_id=merchant_id,
            base_day_paise=base_day,
            open_hour=shop_prof["open_hour"],
            close_hour=shop_prof["close_hour"],
            hour_weights=shop_prof["hour_weights"],
            dow_mult=shop_prof["dow_mult"],
            rain_sensitivity=shop_prof["rain_sensitivity"],
            avg_ticket_paise=shop_prof["avg_ticket_paise"]
        )
        profiles_dict[merchant_id] = profile

    # Generate other merchants (deterministic from seed, skip demo ids)
    used_ids = {int(mid[2:]) for mid in demo_merchants_data}
    merchant_counter = 1

    for zone in geography.zones:
        zone_shop_count = shops_per_zone.get(zone.id, 0)

        # Check which shops are already added (demo shops)
        demo_in_zone = [mid for mid in demo_merchants_data
                       if demo_merchants_data[mid]["zone_id"] == zone.id]
        remaining_count = zone_shop_count - len(demo_in_zone)

        # Generate merchants for this zone
        zone_rng = np.random.default_rng(seed + hash(zone.id) % (2**32))

        for _ in range(remaining_count):
            # Find next available id
            while merchant_counter in used_ids or merchant_counter == 142 or merchant_counter == 907:
                merchant_counter += 1

            merchant_id = f"S-{merchant_counter:04d}"
            used_ids.add(merchant_counter)

            # Generate deterministic merchant data
            name_idx = zone_rng.integers(0, len(MERCHANT_NAMES))
            first_en, first_hi, last_en = MERCHANT_NAMES[name_idx]

            shop_type_idx = zone_rng.integers(0, len(SHOP_PROFILES))
            shop_type = list(SHOP_PROFILES.keys())[shop_type_idx]

            # Pick h3 cell in zone
            zone_hexes = [h for h in geography.hexes if h.zone_id == zone.id]
            if zone_hexes:
                hex_idx = zone_rng.integers(0, len(zone_hexes))
                hex_obj = zone_hexes[hex_idx]
                h3_cell = hex_obj.h3
                lat, lng = hex_obj.center_lat, hex_obj.center_lng
            else:
                h3_cell = "N/A"
                lat, lng = zone.centroid_lat, zone.centroid_lng

            # Weekly off: ~15% have a weekly off, but not for Z3/Z7/Z12/demo
            if zone.id in ["Z3", "Z7", "Z12"]:
                weekly_off = None
            else:
                if zone_rng.random() < 0.15:
                    # Salons prefer Tuesday (1)
                    weekly_off = 1 if shop_type == ShopType.SALON else zone_rng.integers(0, 7)
                else:
                    weekly_off = None

            merchant = Merchant(
                id=merchant_id,
                shop_name=f"{first_en}'s {shop_type.value.replace('_', ' ').title()}",
                owner_name=f"{first_en} {last_en}",
                owner_name_hi=first_hi,
                kyc_name=f"{first_en.upper()} RAMESH {last_en.upper()}",
                phone=f"+9199000{merchant_counter:05d}",
                language=Language.HI,
                zone_id=zone.id,
                lat=lat,
                lng=lng,
                h3_cell=h3_cell,
                shop_type=shop_type,
                weekly_off=weekly_off,
                is_demo=False
            )
            merchants_list.append(merchant)
            merchant_counter += 1

            # Add cover (60+ days purchased, prepaid through replay date)
            purchased_at = ist(2025, 6, 20)  # 60 days before 2025-08-19
            cover = Cover(
                id=f"CV-{merchant_id[2:]}",
                merchant_id=merchant_id,
                purchased_at=purchased_at,
                starts_on=purchased_at.date() + timedelta(days=7),
                premium_per_day_paise=rupees(2),  # Default; overridden by backtest
                prepaid_through=ist(2025, 9, 30).date(),  # Per SPEC §5.4
                status=CoverStatus.ACTIVE
            )
            covers_dict[merchant_id] = cover

            # ~40% have loans
            if zone_rng.random() < 0.40:
                # ₹200-900 in multiples of ₹50
                instalment = (zone_rng.integers(4, 19) * 50) * 100  # paise
                loan = Loan(
                    id=f"LN-{merchant_id[2:]}",
                    merchant_id=merchant_id,
                    lender_name="Simulated lender (NBFC partner)",
                    daily_instalment_paise=instalment,
                    outstanding_paise=200_000
                )
                loans_dict[merchant_id] = loan

            # Create profile
            shop_prof = SHOP_PROFILES[shop_type]

            # Apply calibration scales for Z7
            if zone.id == "Z7" and merchant_id != "S-0142":
                base_day = int(shop_prof["median_day_paise"] * calibration.z7_other_scale)
                if calibration.z7_tune_merchant_id == merchant_id:
                    base_day = calibration.z7_tune_base_day_paise or base_day
            else:
                base_day = shop_prof["median_day_paise"]

            profile = ShopProfile(
                merchant_id=merchant_id,
                base_day_paise=base_day,
                open_hour=shop_prof["open_hour"],
                close_hour=shop_prof["close_hour"],
                hour_weights=shop_prof["hour_weights"],
                dow_mult=shop_prof["dow_mult"],
                rain_sensitivity=shop_prof["rain_sensitivity"],
                avg_ticket_paise=shop_prof["avg_ticket_paise"]
            )
            profiles_dict[merchant_id] = profile

    # Sort merchants by id
    merchants_list.sort(key=lambda m: m.id)
    merchants_tuple = tuple(merchants_list)

    return City(
        seed=seed,
        geography=geography,
        merchants=merchants_tuple,
        profiles=profiles_dict,
        covers=covers_dict,
        loans=loans_dict
    )
