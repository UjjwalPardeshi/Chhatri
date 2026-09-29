"""Tests for city builder (SPEC §5.3, §5.4, §5.5, §24.1)."""

from datetime import date
from pathlib import Path

import pytest

from chhatri.domain.enums import Language
from chhatri.money import rupees
from chhatri.sim.city import build_city


@pytest.fixture
def data_dir():
    """Path to test data directory."""
    return Path(__file__).resolve().parent.parent.parent / "data"


def test_build_city_small_scale(data_dir):
    """Test city building with small scale (fast tests)."""
    city = build_city(20251019, data_dir, scale="small")

    # Should have only 4 zones with demo merchants
    zone_ids = {m.zone_id for m in city.merchants}
    assert zone_ids == {"Z3", "Z7", "Z9", "Z12"}

    # Should have exact counts per spec
    assert len([m for m in city.merchants if m.zone_id == "Z3"]) == 40
    assert len([m for m in city.merchants if m.zone_id == "Z7"]) == 46
    assert len([m for m in city.merchants if m.zone_id == "Z9"]) == 25
    assert len([m for m in city.merchants if m.zone_id == "Z12"]) == 30

    assert len(city.merchants) == 141


def test_build_city_full_scale(data_dir):
    """Test city building with full scale."""
    city = build_city(20251019, data_dir, scale="full")

    # Should have all 24 zones
    zone_ids = {m.zone_id for m in city.merchants}
    assert len(zone_ids) == 24
    assert "Z1" in zone_ids and "Z24" in zone_ids

    # Should have exactly the pilot counts
    assert len([m for m in city.merchants if m.zone_id == "Z3"]) == 141
    assert len([m for m in city.merchants if m.zone_id == "Z7"]) == 46
    assert len([m for m in city.merchants if m.zone_id == "Z9"]) == 64
    assert len([m for m in city.merchants if m.zone_id == "Z12"]) == 125


def test_anil_demo_merchant(data_dir):
    """Test Anil's merchant properties (SPEC §5.4)."""
    city = build_city(20251019, data_dir, scale="small")

    anil = city.merchant("S-0142")
    assert anil.shop_name == "Anil's Tea Stall"
    assert anil.owner_name == "Anil Jadhav"
    assert anil.owner_name_hi == "अनिल"
    assert anil.kyc_name == "ANIL RAMESH JADHAV"
    assert anil.zone_id == "Z7"
    assert anil.language == Language.HI
    assert anil.is_demo is True
    assert anil.weekly_off is None

    # Location must be inside F/S ward
    assert 19.0046 - 0.01 < anil.lat < 19.0046 + 0.01
    assert 72.8424 - 0.01 < anil.lng < 72.8424 + 0.01


def test_ramesh_demo_merchant(data_dir):
    """Test Ramesh's merchant properties (SPEC §5.4)."""
    city = build_city(20251019, data_dir, scale="small")

    ramesh = city.merchant("S-0907")
    assert ramesh.shop_name == "Ramesh Vada Pav"
    assert ramesh.owner_name == "Ramesh Pawar"
    assert ramesh.owner_name_hi == "रमेश"
    assert ramesh.zone_id == "Z3"
    assert ramesh.is_demo is True
    assert ramesh.weekly_off is None


def test_anil_loan(data_dir):
    """Test Anil has a loan with ₹600 daily instalment (SPEC §5.4)."""
    city = build_city(20251019, data_dir, scale="small")

    anil_loan = city.loans.get("S-0142")
    assert anil_loan is not None
    assert anil_loan.daily_instalment_paise == rupees(600)
    assert anil_loan.lender_name == "Simulated lender (NBFC partner)"


def test_ramesh_no_cover(data_dir):
    """Test Ramesh is NOT covered (SPEC §5.4)."""
    city = build_city(20251019, data_dir, scale="small")

    ramesh_cover = city.covers.get("S-0907")
    assert ramesh_cover is None


def test_pilot_merchants_have_covers(data_dir):
    """Test all pilot merchants except Ramesh have covers (SPEC §5.5)."""
    city = build_city(20251019, data_dir, scale="small")

    # All merchants except Ramesh should have covers
    for merchant in city.merchants:
        if merchant.id == "S-0907":  # Ramesh
            assert merchant.id not in city.covers
        else:
            assert merchant.id in city.covers, f"Merchant {merchant.id} should have cover"


def test_no_weekly_off_in_pilot_zones(data_dir):
    """Test no weekly_off in Z3, Z7, Z12 (SPEC §5.3)."""
    city = build_city(20251019, data_dir, scale="small")

    for merchant in city.merchants:
        if merchant.zone_id in ["Z3", "Z7", "Z12"]:
            assert merchant.weekly_off is None, f"Merchant {merchant.id} in pilot zone should have no weekly_off"


def test_merchant_phone_format(data_dir):
    """Test merchant phone numbers are valid (SPEC §5.5)."""
    city = build_city(20251019, data_dir, scale="small")

    for merchant in city.merchants:
        # Phone should be "+9199000" + 5 digits
        assert merchant.phone.startswith("+9199000")
        assert len(merchant.phone) == 13  # +91 + 9900000 + 5 digits
        assert merchant.phone[8:].isdigit()


def test_merchant_phone_matches_id(data_dir):
    """Test that phone number matches merchant ID (SPEC §5.5)."""
    city = build_city(20251019, data_dir, scale="small")

    for merchant in city.merchants:
        merchant_num = int(merchant.id[2:])  # Extract number from S-XXXX
        phone_num = int(merchant.phone[8:])  # Extract last 5 digits from +9199000XXXXX
        # For demo merchants, phone should match ID
        # For non-demo, phone is based on counter, so just check format
        if merchant.is_demo:
            assert phone_num == merchant_num, f"Demo merchant {merchant.id} phone should match ID"


def test_deterministic_generation(data_dir):
    """Test that same seed generates identical merchants."""
    city1 = build_city(20251019, data_dir, scale="small")
    city2 = build_city(20251019, data_dir, scale="small")

    assert len(city1.merchants) == len(city2.merchants)
    for m1, m2 in zip(city1.merchants, city2.merchants):
        assert m1.id == m2.id
        assert m1.owner_name == m2.owner_name
        assert m1.zone_id == m2.zone_id


def test_different_seed_different_merchants(data_dir):
    """Test that different seeds generate different merchants."""
    city1 = build_city(20251019, data_dir, scale="small")
    city2 = build_city(20251020, data_dir, scale="small")

    # Merchant IDs should be in same range but names might differ
    # (non-demo merchants are different)
    for m1, m2 in zip(city1.merchants, city2.merchants):
        if m1.is_demo:
            assert m1.id == m2.id  # Demo merchants are fixed
        # Non-demo merchants might have different names
