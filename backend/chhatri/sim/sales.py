"""Sales simulator (SPEC §6, §24.1).

Deterministic hourly sales generation with shocks. Slice-consistent: same seed + date range
yields identical results as a subset of a longer generation.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from enum import IntEnum

import numpy as np

from chhatri.clock import at
from chhatri.sim.types import HOUR, City, GroundTruth, SalesPanel


# RNG stream IDs for reproducibility
class RNGStream(IntEnum):
    """Deterministic stream IDs for seeding."""
    BASE_DAY_NOISE = 1
    DOW_MULT_NOISE = 2
    HOUR_PROFILE_NOISE = 3
    RAIN_IMPACT = 4
    FESTIVAL_MULT = 5
    TREND_FACTOR = 6
    FINAL_NOISE = 7
    CLOSURE_HAZARD = 8
    TXN_COUNT = 9


class SalesSimulator:
    """Generates hourly sales panels with shocks."""

    def __init__(self, city: City, shocks, seed: int):
        """Initialize sales simulator.

        Args:
            city: City with merchants and profiles
            shocks: ShockCalendar with weather and closure data
            seed: Base random seed
        """
        self.city = city
        self.shocks = shocks
        self.seed = seed
        self._ground_truth_cache = {}

    def _rng_for(self, merchant_id: str, day: date, stream: int) -> np.random.Generator:
        """Create deterministic RNG for a merchant-day-stream combination.

        This ensures that the same (merchant, day, stream) always yields the same sequence,
        regardless of what dates have been requested before (slice consistency).
        Seeds from (base_seed, day ordinal, stream) per SPEC §6.2.
        """
        # Use deterministic hash (not Python's hash() which varies across sessions)
        key = f"{merchant_id}:{day.toordinal()}:{stream}:{self.seed}"
        # MD5 returns bytes; convert to uint32 for numpy
        hash_bytes = hashlib.md5(key.encode(), usedforsecurity=False).digest()
        stream_seed = int.from_bytes(hash_bytes[:4], byteorder='big', signed=False) % (2**31)
        return np.random.default_rng(stream_seed)

    def generate(self, start_day: date, end_day: date) -> SalesPanel:
        """Generate sales for a date range.

        Args:
            start_day: Start date (inclusive)
            end_day: End date (inclusive)

        Returns:
            SalesPanel with hourly amounts and transaction counts.
        """
        start_dt = at(start_day, 0)
        end_dt = at(end_day + timedelta(days=1), 0)
        hours = int((end_dt - start_dt) / HOUR)

        merchant_ids = self.city.merchants
        m_count = len(merchant_ids)

        # Initialize arrays
        amount_paise = np.zeros((m_count, hours), dtype=np.int64)
        txns = np.zeros((m_count, hours), dtype=np.int32)

        # Generate hour by hour
        current_dt = start_dt
        hour_idx = 0

        while hour_idx < hours:
            current_day = current_dt.date()
            current_hour = current_dt.hour

            for merchant_idx, merchant in enumerate(merchant_ids):
                profile = self.city.profiles[merchant.id]

                # Check if this is a business hour
                if not profile.is_business_hour(current_hour):
                    amount_paise[merchant_idx, hour_idx] = 0
                    txns[merchant_idx, hour_idx] = 0
                    continue

                # Check if it's a weekly-off day
                if merchant.weekly_off is not None and current_day.weekday() == merchant.weekly_off:
                    amount_paise[merchant_idx, hour_idx] = 0
                    txns[merchant_idx, hour_idx] = 0
                    continue

                # Check if merchant is closed
                closure_ranges = self.shocks.closures(merchant.id)
                is_closed = any(start <= current_day <= end for start, end in closure_ranges)
                if is_closed:
                    amount_paise[merchant_idx, hour_idx] = 0
                    txns[merchant_idx, hour_idx] = 0
                    continue

                # Generate sales for this hour
                # Base formula: base_day × dow_mult × hour_profile × festival_mult × trend × (1-impact) × noise

                base_day = profile.base_day_paise

                # Day-of-week multiplier
                dow_mult = profile.dow_mult[current_day.weekday()]

                # Hour profile
                hour_weight = profile.hour_weights[current_hour]

                # Festival multiplier
                festival_mult = self._festival_multiplier(merchant.shop_type, current_day)

                # Rain impact
                rain_mm_val = self.shocks.rain_mm(merchant.zone_id, current_dt)
                rain_impact = self._rain_impact(rain_mm_val, profile, merchant.zone_id)

                # Slow day
                slow_depth = self.shocks.slow_day_depth(merchant.zone_id, current_day)

                # Bandh impact
                bandh_impact = 0.75 if self.shocks.is_bandh(current_day) else 0.0

                # Combine shocks (worst case)
                total_impact = max(rain_impact, slow_depth, bandh_impact)

                # Trend (constant 1.0 for simplicity in demo)
                trend = 1.0

                # Generate noise: day-level and hour-level
                day_rng = self._rng_for(merchant.id, current_day, RNGStream.BASE_DAY_NOISE)
                day_noise_factor = np.exp(day_rng.normal(0, 0.10))  # σ ≈ 0.10

                hour_rng = self._rng_for(merchant.id, current_day, RNGStream.HOUR_PROFILE_NOISE + current_hour)
                hour_noise_factor = np.exp(hour_rng.normal(0, 0.25))  # σ ≈ 0.25

                # Compute expected amount (before noise)
                hourly_base = base_day * dow_mult * hour_weight * festival_mult * trend * (1.0 - total_impact)

                # Apply noise
                final_amount = hourly_base * day_noise_factor * hour_noise_factor
                amount_paise[merchant_idx, hour_idx] = max(0, int(final_amount))

                # Generate transaction count
                if amount_paise[merchant_idx, hour_idx] > 0:
                    avg_ticket = profile.avg_ticket_paise
                    expected_txns = amount_paise[merchant_idx, hour_idx] / avg_ticket

                    txn_rng = self._rng_for(merchant.id, current_day, RNGStream.TXN_COUNT + current_hour)
                    txn_count = txn_rng.poisson(expected_txns)
                    txns[merchant_idx, hour_idx] = int(txn_count)
                else:
                    txns[merchant_idx, hour_idx] = 0

            current_dt += HOUR
            hour_idx += 1

        return SalesPanel(
            merchant_ids=tuple(m.id for m in merchant_ids),
            start=start_dt,
            hours=hours,
            amount_paise=amount_paise,
            txns=txns
        )

    def counterfactual(self, start_day: date, end_day: date) -> SalesPanel:
        """Generate sales with identical noise but no shocks (rain, bandh, slow days).

        Used for computing actual vs expected losses (SPEC §6.3).
        Returns the same sales as generate() but with all shock impacts (rain, bandh, slow days, closures) set to zero.
        This requires the same noise factors but impact = 0.
        """
        start_dt = at(start_day, 0)
        end_dt = at(end_day + timedelta(days=1), 0)
        hours = int((end_dt - start_dt) / HOUR)

        merchant_ids = self.city.merchants
        m_count = len(merchant_ids)

        # Initialize arrays
        amount_paise = np.zeros((m_count, hours), dtype=np.int64)
        txns = np.zeros((m_count, hours), dtype=np.int32)

        # Generate hour by hour, but with impact = 0 (no shocks)
        current_dt = start_dt
        hour_idx = 0

        while hour_idx < hours:
            current_day = current_dt.date()
            current_hour = current_dt.hour

            for merchant_idx, merchant in enumerate(merchant_ids):
                profile = self.city.profiles[merchant.id]

                # Check if this is a business hour
                if not profile.is_business_hour(current_hour):
                    amount_paise[merchant_idx, hour_idx] = 0
                    txns[merchant_idx, hour_idx] = 0
                    continue

                # Check if it's a weekly-off day
                if merchant.weekly_off is not None and current_day.weekday() == merchant.weekly_off:
                    amount_paise[merchant_idx, hour_idx] = 0
                    txns[merchant_idx, hour_idx] = 0
                    continue

                # For counterfactual, ignore closures - no impact
                # (closures are shocks, not noise)

                # Generate sales for this hour with NO shock impact
                base_day = profile.base_day_paise
                dow_mult = profile.dow_mult[current_day.weekday()]
                hour_weight = profile.hour_weights[current_hour]
                festival_mult = self._festival_multiplier(merchant.shop_type, current_day)
                trend = 1.0

                # NO IMPACT (counterfactual has no shocks)
                total_impact = 0.0

                # Generate identical noise as in generate()
                day_rng = self._rng_for(merchant.id, current_day, RNGStream.BASE_DAY_NOISE)
                day_noise_factor = np.exp(day_rng.normal(0, 0.10))

                hour_rng = self._rng_for(merchant.id, current_day, RNGStream.HOUR_PROFILE_NOISE + current_hour)
                hour_noise_factor = np.exp(hour_rng.normal(0, 0.25))

                # Compute expected amount (with impact = 0)
                hourly_base = base_day * dow_mult * hour_weight * festival_mult * trend * (1.0 - total_impact)

                # Apply noise
                final_amount = hourly_base * day_noise_factor * hour_noise_factor
                amount_paise[merchant_idx, hour_idx] = max(0, int(final_amount))

                # Generate transaction count with same RNG as generate()
                if amount_paise[merchant_idx, hour_idx] > 0:
                    avg_ticket = profile.avg_ticket_paise
                    expected_txns = amount_paise[merchant_idx, hour_idx] / avg_ticket

                    txn_rng = self._rng_for(merchant.id, current_day, RNGStream.TXN_COUNT + current_hour)
                    txn_count = txn_rng.poisson(expected_txns)
                    txns[merchant_idx, hour_idx] = int(txn_count)
                else:
                    txns[merchant_idx, hour_idx] = 0

            current_dt += HOUR
            hour_idx += 1

        return SalesPanel(
            merchant_ids=tuple(m.id for m in merchant_ids),
            start=start_dt,
            hours=hours,
            amount_paise=amount_paise,
            txns=txns
        )

    def ground_truth(self, start_day: date, end_day: date) -> GroundTruth:
        """Compute ground truth loss labels per zone-day.

        Returns:
            GroundTruth with loss percentages and shock labels
        """
        actual = self.generate(start_day, end_day)
        counterfactual = self.counterfactual(start_day, end_day)

        zone_day_loss: dict[tuple[str, date], float] = {}
        zone_day_label: dict[tuple[str, date], str] = {}

        current_day = start_day
        while current_day <= end_day:
            for zone in self.city.zones:
                zone_rows = self.city.zone_rows(zone.id)

                if not zone_rows:
                    continue

                # Get actual and counterfactual for this zone-day
                day_panel_actual = actual.day(current_day)
                day_panel_cf = counterfactual.day(current_day)

                zone_actual_amount = day_panel_actual.amount_paise[list(zone_rows), :].sum()
                zone_cf_amount = day_panel_cf.amount_paise[list(zone_rows), :].sum()

                loss_pct = 1.0 - (zone_actual_amount / zone_cf_amount) if zone_cf_amount > 0 else 0.0

                zone_day_loss[(zone.id, current_day)] = loss_pct

                # Determine label
                if self.shocks.is_bandh(current_day):
                    label = "bandh"
                elif self.shocks.slow_day_depth(zone.id, current_day) > 0:
                    label = "slow_day"
                elif self.shocks.rain_mm(zone.id, at(current_day, 12)) > 0:
                    label = "rain"
                else:
                    label = "normal"

                zone_day_label[(zone.id, current_day)] = label

            current_day += timedelta(days=1)

        # Collect closures
        closures: dict[str, tuple[tuple[date, date], ...]] = {}
        for merchant in self.city.merchants:
            closure_ranges = self.shocks.closures(merchant.id)
            if closure_ranges:
                closures[merchant.id] = closure_ranges

        return GroundTruth(
            zone_day_loss_pct=zone_day_loss,
            zone_day_label=zone_day_label,
            closures=closures
        )

    def _rain_impact(self, rain_mm: float, profile, zone_id: str) -> float:
        """Compute sales impact from rainfall.

        Formula: impact = sensitivity × g(r3) where g(r) = 1 - exp(-r / divisor)
        r3 = rainfall in last 3 hours (current + 2 previous)
        Divisor = 18 for waterlogging-prone zones, else 25.
        """
        if rain_mm <= 0:
            return 0.0

        zone = self.city.geography.zone(zone_id)
        divisor = 18 if zone.waterlogging_prone else 25

        # For simplicity, assume r3 ≈ rain_mm (would need 3h history for exact)
        g_r = 1.0 - np.exp(-rain_mm / divisor)
        impact = profile.rain_sensitivity * g_r

        return min(1.0, impact)  # Cap at 100%

    def _festival_multiplier(self, shop_type, day: date) -> float:
        """Compute sales multiplier for festivals."""
        # Ganesh Chaturthi: 10-day window (SPEC §6.3)
        ganesh_2024 = (date(2024, 9, 7), date(2024, 9, 16))
        ganesh_2025 = (date(2025, 8, 27), date(2025, 9, 5))

        in_ganesh = (
            (ganesh_2024[0] <= day <= ganesh_2024[1]) or
            (ganesh_2025[0] <= day <= ganesh_2025[1])
        )

        if in_ganesh:
            # +20% for food/sweets/kirana
            from chhatri.domain.enums import ShopType
            if shop_type in [ShopType.STREET_FOOD, ShopType.FRUIT_VEG, ShopType.KIRANA]:
                return 1.20

        return 1.0
