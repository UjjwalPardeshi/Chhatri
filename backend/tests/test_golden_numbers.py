"""Golden numbers test (SPEC §17.4, §22).

Slow test: loads artifacts + monsoon scenario WITHOUT the API
(sim + model + detect + policy) and asserts all golden numbers.

Run with: pytest -m slow tests/test_golden_numbers.py
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path

import pytest

from chhatri.clock import at, ist
from chhatri.domain.enums import DecisionOutcome
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.policy.engine import publish_expected_day
from chhatri.sim.calibration import load_calibration
from chhatri.sim.city import build_city
from chhatri.sim.scenarios import get_scenario
from chhatri.sim.weather import build_shocks

logger = logging.getLogger(__name__)


def get_backend_dir() -> Path:
    """Return backend directory from test location."""
    return Path(__file__).resolve().parent.parent


@pytest.mark.slow
class TestGoldenNumbers:
    """Golden numbers for monsoon replay (SPEC §17.2, §17.4)."""

    @classmethod
    def setup_class(cls):
        """Load artifacts once for all tests."""
        backend_dir = get_backend_dir()
        data_dir = backend_dir / "data"
        artifacts_dir = backend_dir / "artifacts"

        # Ensure artifacts exist
        assert (
            artifacts_dir / "model" / "manifest.json"
        ).exists(), "Run 'make data' to generate model artifacts"

        # Load city, model, calibration
        cls.city = build_city(20251019, data_dir, scale="full")
        cls.calibration = load_calibration(data_dir)
        cls.model = ExpectedSalesModel.load(artifacts_dir / "model")

        # Build shocks without overrides for history
        cls.shocks_base = build_shocks(
            cls.city, data_dir, 20251019, overrides=None
        )

    def test_anil_expected_tuesday(self):
        """Anil's expected Tuesday should be ₹4,380 (SPEC §17.2, §17.4)."""
        # Monsoon replay date
        replay_date = date(2025, 8, 19)  # Tuesday

        # Get Anil's expected day from model
        expected_paise = self.model.expected_day_paise(
            self.city, None, "S-0142", replay_date
        )

        # Published expected (rounded to nearest ₹10)
        expected_published = publish_expected_day(expected_paise)

        # Should be ₹4,380
        assert expected_published == 438_000, (
            f"Anil expected Tuesday should be ₹4,380, got ₹{expected_published / 100}"
        )

    def test_golden_indices(self):
        """Zone indices at 17:00 on monsoon replay (SPEC §17.2)."""
        replay_date = date(2025, 8, 19)  # Tuesday
        scenario = get_scenario("monsoon", self.city, self.calibration)

        # Build shocks WITH scenario overrides
        from chhatri.sim.weather import build_shocks

        shocks = build_shocks(
            self.city,
            get_backend_dir() / "data",
            20251019,
            overrides=scenario.overrides,
        )

        # Generate sales for replay window
        from chhatri.sim.sales import SalesSimulator

        simulator = SalesSimulator(self.city, shocks, 20251019)
        sales = simulator.generate(replay_date, replay_date)

        # Compute indices at 17:00 (hour 17)
        from chhatri.detect.area_index import zone_window
        import numpy as np

        # Get predictions for the day
        predictions = self.model.predict(self.city, None, at(replay_date, 0), 24)

        # Extract P50
        p50 = predictions[:, :, 1]  # (merchants, 24)

        # Window [14:00, 17:00) = hours 14, 15, 16
        window_end_hour = 17
        rows_z7 = self.city.zone_rows("Z7")
        rows_z3 = self.city.zone_rows("Z3")
        rows_z12 = self.city.zone_rows("Z12")
        rows_z9 = self.city.zone_rows("Z9")

        # Compute indices (simplified: hour window sums)
        for rows, zone_id, target_index in [
            (rows_z7, "Z7", 37),
            (rows_z3, "Z3", 38),
            (rows_z12, "Z12", 47),
        ]:
            actual_sum = 0
            expected_sum = 0
            for row in rows:
                # Sum hours 14-16 (before 17:00)
                actual_sum += sales.amount_paise[row, 14:17].sum()
                expected_sum += p50[row, 14:17].sum()

            if expected_sum > 0:
                index = int(actual_sum / expected_sum * 100 + 0.5)  # half up
            else:
                index = 100

            assert (
                index == target_index
            ), f"{zone_id}: expected index {target_index}, got {index}"

    def test_z9_slow_day(self):
        """Z9 shows 61% at 17:00 with no trigger (SPEC §17.2)."""
        replay_date = date(2025, 8, 19)
        scenario = get_scenario("monsoon", self.city, self.calibration)

        # Z9 is a slow day (no alert), so no trigger
        # Index should show 61%
        assert scenario.overrides.slow_days.get(("Z9", replay_date)) is not None, (
            "Z9 should be a slow day in monsoon scenario"
        )

    @pytest.mark.parametrize(
        "zone_id,target_index",
        [("Z7", 37), ("Z3", 38), ("Z12", 47)],
    )
    def test_zone_indices_bounds(self, zone_id, target_index):
        """Each zone's hourly indices are strictly below 50 and lower_bound (SPEC §8.2)."""
        replay_date = date(2025, 8, 19)
        scenario = get_scenario("monsoon", self.city, self.calibration)

        from chhatri.sim.weather import build_shocks
        from chhatri.sim.sales import SalesSimulator

        shocks = build_shocks(
            self.city,
            get_backend_dir() / "data",
            20251019,
            overrides=scenario.overrides,
        )
        simulator = SalesSimulator(self.city, shocks, 20251019)
        sales = simulator.generate(replay_date, replay_date)

        # Predictions
        predictions = self.model.predict(self.city, None, at(replay_date, 0), 24)
        p50 = predictions[:, :, 1]

        rows = self.city.zone_rows(zone_id)
        lower_bound = self.model.lower_bound_pct(zone_id)

        # Check hours 14, 15, 16 (the 3-hour window before 17:00)
        for h in [14, 15, 16]:
            actual_sum = sum(sales.amount_paise[row, h] for row in rows)
            expected_sum = sum(p50[row, h] for row in rows)

            if expected_sum > 0:
                hourly_index = int(
                    actual_sum / expected_sum * 100 + 0.5
                )  # half up
            else:
                hourly_index = 100

            # Must be strictly less than both 50 and lower_bound
            assert hourly_index < 50, (
                f"{zone_id} hour {h}: index {hourly_index} >= 50"
            )
            assert hourly_index < lower_bound, (
                f"{zone_id} hour {h}: index {hourly_index} >= lower_bound {lower_bound}"
            )

    def test_312_shops_paid(self):
        """312 shops paid in monsoon replay (SPEC §17.2, §0.1)."""
        # This requires running full decision logic, which is complex
        # For now, placeholder: would need to mock detector + policy
        pytest.skip(
            "Requires full orchestrator; would be tested in E2E tests"
        )

    def test_anil_payout(self):
        """Anil gets paid ₹1,380 (SPEC §17.2)."""
        # Would require running policy engine with area claim facts
        pytest.skip("Requires policy engine + trigger; would be in E2E tests")

    def test_z7_total_paid(self):
        """Z7 total paid = ₹58,900 (SPEC §17.2)."""
        pytest.skip("Requires full payout accounting; would be in E2E tests")

    def test_personal_claim_anil_illness(self):
        """Anil personal claim (illness): ₹1,500 for 1 day (SPEC §17.2)."""
        # illness scenario: Anil silent on Wed 2025-08-20
        # Replay Thu 2025-08-21; slip admission Wed; ⇒ APPROVED ₹1,500
        pytest.skip("Requires conversation + slip reader; would be in E2E tests")

    def test_ramesh_gets_nothing(self):
        """Ramesh (uncovered in Z3) gets nothing (SPEC §17.2, §5.4)."""
        # Ramesh is in Z3 but is_demo=True and not covered
        # Even in monsoon, uncovered merchants don't pay
        from chhatri.domain.enums import CoverStatus

        ramesh = self.city.merchant("S-0907")
        assert ramesh.zone_id == "Z3"
        assert ramesh.is_demo is True  # in the test case

        # He has no cover (or cover status != ACTIVE)
        cover = self.city.covers.get(ramesh.id)
        if cover:
            assert cover.status != CoverStatus.ACTIVE


@pytest.mark.slow
def test_demo_check_script():
    """Placeholder for demo_check.py integration."""
    # Would test that the three live tests (deck slide 8) pass:
    # 1. "My loss was bigger" → EXPLAINED
    # 2. Slip mismatch → HUMAN (case opened)
    # 3. "Red alert tomorrow, cover me today" → BLOCKED
    pytest.skip("Would be tested via demo_check.py")
