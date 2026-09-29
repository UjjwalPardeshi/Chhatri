"""Fast unit tests for pipeline infrastructure (SPEC §24).

These test the pipeline components WITHOUT running full data generation.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from chhatri.pipeline.history import compute_history_dates
from chhatri.sim.calibration import load_calibration
from chhatri.sim.city import build_city


class TestPipelineInfrastructure:
    """Test pipeline components."""

    def test_compute_history_dates(self):
        """History window calculation (SPEC §7.1, §17.2)."""
        # Train end = day before monsoon replay
        train_end = date(2025, 8, 18)

        start_date, end_date = compute_history_dates(
            train_end, train_weeks=26, calib_weeks=4, lookback_days=56
        )

        # Verify end date
        assert end_date == train_end

        # Verify we cover enough history
        days_covered = (end_date - start_date).days
        expected_days = (8 + 26 + 4) * 7 + 56  # 8-week shop_level + train + calib + lookback
        assert (
            days_covered >= expected_days - 1
        ), f"Need {expected_days} days, got {days_covered}"

    def test_calibration_defaults(self):
        """Load default calibration (SPEC §17.4)."""
        backend_dir = Path(__file__).resolve().parent.parent.parent
        data_dir = backend_dir / "data"

        calibration = load_calibration(data_dir)

        # Check default values
        assert calibration.anil_base_day_paise > 0
        assert isinstance(calibration.zone_rain_scale, dict)
        assert 0 < calibration.z9_slow_depth < 1
        assert calibration.z7_other_scale > 0

    def test_city_build(self):
        """City with merchants and profiles (SPEC §5.3, §5.4)."""
        backend_dir = Path(__file__).resolve().parent.parent.parent
        data_dir = backend_dir / "data"

        city = build_city(20251019, data_dir, scale="full")

        # Verify structure
        assert len(city.merchants) == 2073
        assert len(city.zones) == 24
        assert "S-0142" in [m.id for m in city.merchants]  # Anil
        assert "S-0907" in [m.id for m in city.merchants]  # Ramesh

        # Verify Anil is in Z7
        anil = city.merchant("S-0142")
        assert anil.zone_id == "Z7"
        assert anil.is_demo is True

        # Verify Ramesh is in Z3
        ramesh = city.merchant("S-0907")
        assert ramesh.zone_id == "Z3"
        assert ramesh.is_demo is True

    def test_city_small_scale(self):
        """Small-scale city for fast tests (SPEC §24.1)."""
        backend_dir = Path(__file__).resolve().parent.parent.parent
        data_dir = backend_dir / "data"

        city_small = build_city(20251019, data_dir, scale="small")

        # Only pilot zones
        zones_in_small = {m.zone_id for m in city_small.merchants}
        assert zones_in_small <= {"Z3", "Z7", "Z9", "Z12"}

    def test_pipeline_idempotency(self):
        """Pipeline steps are idempotent (SPEC §23)."""
        backend_dir = Path(__file__).resolve().parent.parent.parent

        # Running build_city twice should give same result
        data_dir = backend_dir / "data"
        city1 = build_city(20251019, data_dir, scale="full")
        city2 = build_city(20251019, data_dir, scale="full")

        # Merchants should be identical (deterministic seed)
        assert len(city1.merchants) == len(city2.merchants)
        for m1, m2 in zip(city1.merchants, city2.merchants):
            assert m1.id == m2.id
            assert m1.zone_id == m2.zone_id


@pytest.mark.slow
def test_build_data_script_validation():
    """Validate build_data.py script structure."""
    backend_dir = Path(__file__).resolve().parent.parent.parent
    script_path = backend_dir / "scripts" / "build_data.py"

    assert script_path.exists(), f"Script not found: {script_path}"

    # Read script to check for required functions
    with open(script_path) as f:
        content = f.read()

    for required in ["step_geo", "step_city", "step_model", "step_manifest"]:
        assert f"def {required}" in content, f"Missing function: {required}"
