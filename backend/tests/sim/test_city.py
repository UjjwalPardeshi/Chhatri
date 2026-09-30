"""SPEC §5.3-§5.5, §17.4, §24.1: merchants, profiles, covers, loans and calibration hooks."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pytest

from chhatri.domain.enums import CoverStatus, Language, ShopType
from chhatri.sim.city import ANIL_ID, RAMESH_ID, build_city, shops_per_zone
from chhatri.sim.profiles import SHOP_TYPE_SPECS
from chhatri.sim.types import Calibration, City

SEED = 20251019
REPLAY = date(2025, 8, 19)


def covered_counts(city: City) -> Counter[str]:
    return Counter(city.merchant(mid).zone_id for mid in city.covers)


def test_full_city_zone_counts(full_city: City) -> None:
    counts = covered_counts(full_city)
    assert (counts["Z7"], counts["Z3"], counts["Z12"], counts["Z9"]) == (46, 141, 125, 64)
    others = {z.id: counts[z.id] for z in full_city.zones if z.id not in {"Z3", "Z7", "Z9", "Z12"}}
    assert len(others) == 20 and all(30 <= n <= 120 for n in others.values())
    assert len(full_city.merchants) == sum(counts.values()) + 1  # + Ramesh, uncovered
    assert 46 + 141 + 125 == 312  # the deck's "312 shops paid"


def test_small_city_zone_counts(small_city: City) -> None:
    counts = covered_counts(small_city)
    assert dict(counts) == {"Z3": 40, "Z7": 46, "Z9": 25, "Z12": 30}
    assert {ANIL_ID, RAMESH_ID} <= set(small_city.profiles)


def test_other_zone_counts_are_deterministic_and_seed_dependent() -> None:
    zone_ids = tuple(f"Z{i}" for i in range(1, 25))
    assert shops_per_zone(SEED, zone_ids, "full") == shops_per_zone(SEED, zone_ids, "full")
    assert shops_per_zone(SEED, zone_ids, "full") != shops_per_zone(SEED + 1, zone_ids, "full")
    with pytest.raises(ValueError, match="scale"):
        shops_per_zone(SEED, zone_ids, "medium")  # type: ignore[arg-type]


def test_merchant_ids_sorted_and_skip_demo_ids(full_city: City) -> None:
    ids = [m.id for m in full_city.merchants]
    assert ids == sorted(ids)
    generated = [int(i[2:]) for i in ids if i not in {ANIL_ID, RAMESH_ID}]
    expected = [n for n in range(1, len(generated) + 3) if n not in (142, 907)][: len(generated)]
    assert generated == expected
    assert full_city.merchants[0].id == "S-0001"


def test_city_invariants(full_city: City) -> None:
    assert set(full_city.profiles) == {m.id for m in full_city.merchants}
    for i, merchant in enumerate(full_city.merchants):
        profile = full_city.profiles[merchant.id]
        assert full_city.row(merchant.id) == i
        assert len(profile.hour_weights) == 24 and abs(sum(profile.hour_weights) - 1.0) < 1e-9
        assert all(w == 0 for h, w in enumerate(profile.hour_weights) if not profile.is_business_hour(h))
        assert all(w > 0 for h, w in enumerate(profile.hour_weights) if profile.is_business_hour(h))
        assert len(profile.dow_mult) == 7 and 0 <= profile.rain_sensitivity <= 1
        spec = SHOP_TYPE_SPECS[merchant.shop_type]
        assert (profile.open_hour, profile.close_hour) == (spec.open_hour, spec.close_hour)
        assert profile.avg_ticket_paise == spec.avg_ticket_paise
    for zone in full_city.zones:
        rows = full_city.zone_rows(zone.id)
        assert all(full_city.merchants[r].zone_id == zone.id for r in rows)
    assert sum(len(full_city.zone_rows(z.id)) for z in full_city.zones) == len(full_city.merchants)
    with pytest.raises(KeyError):
        full_city.merchant("S-9999")


def test_merchants_are_inside_their_zone_and_hex(full_city: City) -> None:
    import h3

    geo = full_city.geography
    hex_zone = {hx.h3: hx.zone_id for hx in geo.hexes}
    for m in full_city.merchants:
        assert geo.zone_of(m.lat, m.lng) == m.zone_id  # type: ignore[attr-defined]
        assert h3.latlng_to_cell(m.lat, m.lng, 8) == m.h3_cell
        assert hex_zone[m.h3_cell] == m.zone_id


def test_demo_merchants_exact(full_city: City) -> None:
    anil = full_city.merchant(ANIL_ID)
    assert (anil.shop_name, anil.owner_name, anil.owner_name_hi) == (
        "Anil's Tea Stall",
        "Anil Jadhav",
        "अनिल",
    )
    assert (anil.kyc_name, anil.zone_id, anil.lat, anil.lng) == ("ANIL RAMESH JADHAV", "Z7", 19.0046, 72.8424)
    assert anil.language is Language.HI and anil.shop_type is ShopType.TEA_STALL and anil.is_demo
    assert full_city.geography.zone(anil.zone_id).ward == "F/S"
    loan = full_city.loans[ANIL_ID]
    assert loan.daily_instalment_paise == 60_000 and loan.lender_name == "Simulated lender (NBFC partner)"
    assert ANIL_ID in full_city.covers
    ramesh = full_city.merchant(RAMESH_ID)
    assert (ramesh.shop_name, ramesh.owner_name, ramesh.owner_name_hi) == (
        "Ramesh Vada Pav",
        "Ramesh Pawar",
        "रमेश",
    )
    assert ramesh.zone_id == "Z3" and ramesh.is_demo and ramesh.weekly_off is None
    assert RAMESH_ID not in full_city.covers and RAMESH_ID not in full_city.loans
    assert full_city.geography.zone_of(ramesh.lat, ramesh.lng) == "Z3"  # type: ignore[attr-defined]
    assert sum(m.is_demo for m in full_city.merchants) == 2


def test_weekly_off_rules(full_city: City) -> None:
    for m in full_city.merchants:
        if m.zone_id in {"Z3", "Z7", "Z12"} or m.is_demo:
            assert m.weekly_off is None
    offs = [m.weekly_off for m in full_city.merchants if m.weekly_off is not None]
    assert offs and all(0 <= d <= 6 for d in offs)
    salons = [m for m in full_city.merchants if m.shop_type is ShopType.SALON and m.weekly_off is not None]
    assert salons and all(m.weekly_off == 1 for m in salons)


def test_covers_loans_and_phones(full_city: City) -> None:
    assert set(full_city.covers) == {m.id for m in full_city.merchants} - {RAMESH_ID}
    for mid, cover in full_city.covers.items():
        age = (REPLAY - cover.purchased_at.date()).days
        assert 60 <= age <= 400
        assert cover.starts_on == cover.purchased_at.date() + timedelta(days=7)
        assert cover.prepaid_through is not None and cover.prepaid_through >= date(2025, 8, 20)
        assert cover.status is CoverStatus.ACTIVE and cover.merchant_id == mid
    generated = [m for m in full_city.merchants if not m.is_demo]
    loan_share = sum(m.id in full_city.loans for m in generated) / len(generated)
    assert 0.36 <= loan_share <= 0.44
    for loan in full_city.loans.values():
        assert loan.daily_instalment_paise % 5000 == 0 and 20_000 <= loan.daily_instalment_paise <= 90_000
        assert loan.outstanding_paise > 0
    for m in full_city.merchants:
        assert m.phone.startswith("+9199000") and len(m.phone) == 13 and m.phone[3:].isdigit()
    assert len({m.phone for m in full_city.merchants}) == len(full_city.merchants)


def test_generated_names_avoid_demo_names(full_city: City) -> None:
    firsts = {m.owner_name.split()[0] for m in full_city.merchants if not m.is_demo}
    assert not firsts & {"Anil", "Ramesh", "Sunil"}
    assert all(m.kyc_name == m.kyc_name.upper() and len(m.kyc_name.split()) >= 3 for m in full_city.merchants)


def test_build_city_is_deterministic(small_city: City, data_dir: Path) -> None:
    again = build_city(SEED, data_dir, scale="small")
    assert again.merchants == small_city.merchants
    assert dict(again.profiles) == dict(small_city.profiles)
    assert dict(again.covers) == dict(small_city.covers) and dict(again.loans) == dict(small_city.loans)
    other = build_city(SEED + 1, data_dir, scale="small")
    assert other.merchants != small_city.merchants


def test_calibration_hooks_on_city(small_city: City, data_dir: Path) -> None:
    z7_other = next(m.id for m in small_city.merchants if m.zone_id == "Z7" and not m.is_demo)
    tuned = next(
        m.id for m in small_city.merchants if m.zone_id == "Z7" and not m.is_demo and m.id != z7_other
    )
    z3_shop = next(m.id for m in small_city.merchants if m.zone_id == "Z3" and not m.is_demo)
    calibration = Calibration(
        anil_base_day_paise=438_000,
        z7_other_scale=1.5,
        z7_tune_merchant_id=tuned,
        z7_tune_base_day_paise=777_700,
    )
    city = build_city(SEED, data_dir, calibration, scale="small")
    base = small_city.profiles
    assert city.profiles[ANIL_ID].base_day_paise == 438_000
    assert small_city.profiles[ANIL_ID].base_day_paise == Calibration().anil_base_day_paise
    assert city.profiles[z7_other].base_day_paise == round(base[z7_other].base_day_paise * 1.5)
    assert city.profiles[tuned].base_day_paise == 777_700
    assert city.profiles[z3_shop].base_day_paise == base[z3_shop].base_day_paise
    assert city.merchants == small_city.merchants


def test_tune_merchant_must_be_a_generated_z7_shop(small_city: City, data_dir: Path) -> None:
    z3_shop = next(m.id for m in small_city.merchants if m.zone_id == "Z3" and not m.is_demo)
    for bad in (z3_shop, ANIL_ID, "S-9999"):
        with pytest.raises(ValueError, match="z7_tune_merchant_id"):
            build_city(
                SEED, data_dir, Calibration(z7_tune_merchant_id=bad, z7_tune_base_day_paise=1), scale="small"
            )


def test_base_day_spread_is_lognormal_around_type_median(full_city: City) -> None:
    import numpy as np

    for shop_type, spec in SHOP_TYPE_SPECS.items():
        bases = [
            full_city.profiles[m.id].base_day_paise
            for m in full_city.merchants
            if m.shop_type is shop_type and not m.is_demo and m.zone_id != "Z7"
        ]
        assert abs(np.median(bases) / spec.median_day_paise - 1) < 0.15
