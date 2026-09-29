"""Test fixtures for forecast and detect packages (SPEC §7, §8)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from zoneinfo import ZoneInfo

from chhatri.clock import at
from chhatri.domain.enums import CoverStatus, Language, ShopType
from chhatri.domain.models import Alert, AlertKind, AlertLevel, Cover, Loan, Merchant, Zone
from chhatri.sim.types import City, Geography, Hex, SalesPanel, ShopProfile


IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def small_city() -> City:
    """Synthetic city with 3 zones x 25 merchants (~75 total) for fast tests."""
    seed = 20251001

    # Create 3 zones
    zones = (
        Zone(id="Z1", ward="Ward1", name="Zone 1", centroid_lat=19.1, centroid_lng=72.8),
        Zone(id="Z2", ward="Ward2", name="Zone 2", centroid_lat=19.2, centroid_lng=72.9),
        Zone(id="Z3", ward="Ward3", name="Zone 3", centroid_lat=19.3, centroid_lng=73.0),
    )

    # Create hexes (one per zone for simplicity)
    hexes = (
        Hex(h3="h1", zone_id="Z1", center_lat=19.1, center_lng=72.8),
        Hex(h3="h2", zone_id="Z2", center_lat=19.2, center_lng=72.9),
        Hex(h3="h3", zone_id="Z3", center_lat=19.3, center_lng=73.0),
    )

    zones_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "Z1", "shops": 25},
                "geometry": {"type": "Polygon", "coordinates": [[[19.0, 72.7], [19.2, 72.7], [19.2, 72.9], [19.0, 72.9], [19.0, 72.7]]]},
            },
            {
                "type": "Feature",
                "properties": {"id": "Z2", "shops": 25},
                "geometry": {"type": "Polygon", "coordinates": [[[19.1, 72.8], [19.3, 72.8], [19.3, 73.0], [19.1, 73.0], [19.1, 72.8]]]},
            },
            {
                "type": "Feature",
                "properties": {"id": "Z3", "shops": 25},
                "geometry": {"type": "Polygon", "coordinates": [[[19.2, 72.9], [19.4, 72.9], [19.4, 73.1], [19.2, 73.1], [19.2, 72.9]]]},
            },
        ],
    }

    hexes_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"h3": "h1", "zone_id": "Z1"},
                "geometry": {"type": "Point", "coordinates": [72.8, 19.1]},
            },
            {
                "type": "Feature",
                "properties": {"h3": "h2", "zone_id": "Z2"},
                "geometry": {"type": "Point", "coordinates": [72.9, 19.2]},
            },
            {
                "type": "Feature",
                "properties": {"h3": "h3", "zone_id": "Z3"},
                "geometry": {"type": "Point", "coordinates": [73.0, 19.3]},
            },
        ],
    }

    geography = Geography(zones=zones, zones_geojson=zones_geojson, hexes=hexes, hexes_geojson=hexes_geojson)

    # Create 25 merchants per zone (75 total)
    merchants: list[Merchant] = []
    profiles: dict[str, ShopProfile] = {}
    covers: dict[str, Cover] = {}
    loans: dict[str, Loan] = {}

    for z_idx, zone_id in enumerate(["Z1", "Z2", "Z3"]):
        for m_idx in range(25):
            merchant_id = f"S-{z_idx:02d}{m_idx:02d}"
            shop_types = [ShopType.TEA_STALL, ShopType.KIRANA, ShopType.PHARMACY]
            shop_type = shop_types[m_idx % len(shop_types)]

            # Baseline sales ~ 5,000 - 15,000 paise
            base_day_paise = 500000 + (m_idx * 100000) % 1000000

            merchant = Merchant(
                id=merchant_id,
                shop_name=f"Shop {merchant_id}",
                owner_name=f"Owner {m_idx}",
                owner_name_hi=f"मालिक {m_idx}",
                kyc_name=f"OWNER {m_idx}",
                phone=f"+919900000{m_idx:03d}",
                language=Language.HI if m_idx % 2 == 0 else Language.EN,
                zone_id=zone_id,
                lat=19.1 + z_idx * 0.1,
                lng=72.8 + z_idx * 0.1,
                h3_cell=f"h{z_idx + 1}",
                shop_type=shop_type,
                weekly_off=None if z_idx == 0 else (m_idx % 7),  # Z1 has no off days
                is_demo=False,
            )
            merchants.append(merchant)

            # Shop profile with realistic hourly distribution
            if shop_type == ShopType.TEA_STALL:
                hour_weights = tuple(0.05 if 6 <= h < 10 or 16 <= h < 19 else 0.02 for h in range(24))
                hour_weights = tuple(w / sum(hour_weights) for w in hour_weights)
                open_hour, close_hour = 6, 22
            elif shop_type == ShopType.PHARMACY:
                hour_weights = tuple(0.04 if 8 <= h < 23 else 0.01 for h in range(24))
                hour_weights = tuple(w / sum(hour_weights) for w in hour_weights)
                open_hour, close_hour = 8, 23
            else:  # KIRANA
                hour_weights = tuple(0.04 if 7 <= h < 22 else 0.01 for h in range(24))
                hour_weights = tuple(w / sum(hour_weights) for w in hour_weights)
                open_hour, close_hour = 7, 22

            profiles[merchant_id] = ShopProfile(
                merchant_id=merchant_id,
                base_day_paise=base_day_paise,
                open_hour=open_hour,
                close_hour=close_hour,
                hour_weights=hour_weights,
                dow_mult=(0.9, 0.95, 1.0, 1.0, 1.0, 1.1, 1.05),  # Sun, Mon, ..., Sat
                rain_sensitivity=0.5 if shop_type == ShopType.PHARMACY else 0.8,
                avg_ticket_paise=10000 if shop_type == ShopType.PHARMACY else 5000,
            )

            # Covers for merchants
            cover_id = f"CV-{merchant_id}"
            covers[merchant_id] = Cover(
                id=cover_id,
                merchant_id=merchant_id,
                purchased_at=at(date(2025, 6, 1), 10),
                starts_on=date(2025, 6, 8),
                premium_per_day_paise=50000,
                prepaid_through=date(2025, 12, 31),
                status=CoverStatus.ACTIVE,
            )

            # Some merchants have loans
            if m_idx % 3 == 0:
                loan_id = f"LN-{merchant_id}"
                loans[merchant_id] = Loan(
                    id=loan_id,
                    merchant_id=merchant_id,
                    lender_name="Test Lender",
                    daily_instalment_paise=50000,
                    outstanding_paise=5000000,
                )

    return City(
        seed=seed,
        geography=geography,
        merchants=tuple(sorted(merchants, key=lambda m: m.id)),
        profiles=profiles,
        covers=covers,
        loans=loans,
    )


@pytest.fixture
def sales_panel(small_city: City) -> SalesPanel:
    """Generate a realistic 180-hour (7.5-day) sales panel for testing."""
    # Start from a Monday morning
    start = at(date(2025, 8, 18), 6)  # Monday 6 AM IST
    hours = 180  # 7.5 days

    # Create synthetic sales with hourly patterns
    merchant_ids = tuple(m.id for m in small_city.merchants)
    amount_paise = np.zeros((len(merchant_ids), hours), dtype=np.int64)
    txns = np.zeros((len(merchant_ids), hours), dtype=np.int32)

    # Generate sales for each merchant-hour
    rng = np.random.RandomState(small_city.seed)
    for row_idx, merchant_id in enumerate(merchant_ids):
        merchant = small_city.merchant(merchant_id)
        profile = small_city.profiles[merchant_id]

        for hour_idx in range(hours):
            hour_start = start + timedelta(hours=hour_idx)
            hour_of_day = hour_start.hour
            day_of_week = hour_start.weekday()  # 0=Mon, 6=Sun

            # Skip if outside business hours or on weekly off
            if not profile.is_business_hour(hour_of_day):
                continue
            if merchant.weekly_off is not None and day_of_week == merchant.weekly_off:
                continue

            # Base sales for this hour
            base = profile.base_day_paise * profile.hour_weights[hour_of_day]
            dow_factor = profile.dow_mult[day_of_week]
            noise = rng.lognormal(0, 0.15)  # Small noise

            hour_paise = int(base * dow_factor * noise)
            hour_txns = max(1, int(rng.poisson(hour_paise / profile.avg_ticket_paise)))

            amount_paise[row_idx, hour_idx] = hour_paise
            txns[row_idx, hour_idx] = hour_txns

    return SalesPanel(
        merchant_ids=merchant_ids,
        start=start,
        hours=hours,
        amount_paise=amount_paise,
        txns=txns,
    )
