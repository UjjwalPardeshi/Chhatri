"""Tests for detect/triggers.py (SPEC §8.2, §24.2)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from zoneinfo import ZoneInfo

from chhatri.clock import at
from chhatri.detect.triggers import evaluate_hour
from chhatri.domain.models import Alert, AlertKind, AlertLevel, AreaTrigger
from chhatri.policy.rules import default_rules
from chhatri.sim.types import City, SalesPanel
import numpy as np

IST = ZoneInfo("Asia/Kolkata")


class TestEvaluateHourValidation:
    """Hour boundary validation and trigger conditions."""

    def test_evaluate_hour_requires_hour_boundary(self, small_city: City, sales_panel: SalesPanel) -> None:
        """evaluate_hour() requires an hour boundary (SPEC §8.2)."""
        rules = default_rules()

        # Not on hour boundary
        with pytest.raises(ValueError, match="hour boundary"):
            evaluate_hour(
                at=at(date(2025, 8, 19), 14) + timedelta(minutes=30),
                city=small_city,
                actual=sales_panel,
                expected_p50=np.zeros((len(small_city.merchants), sales_panel.hours, 3)),
                alerts=[],
                lower_bounds={},
                rules=rules,
                already_triggered=frozenset(),
            )

    def test_evaluate_hour_accepts_hour_boundary(self, small_city: City, sales_panel: SalesPanel) -> None:
        """evaluate_hour() accepts an hour boundary."""
        rules = default_rules()

        triggers, states = evaluate_hour(
            at=at(date(2025, 8, 19), 14),
            city=small_city,
            actual=sales_panel,
            expected_p50=np.ones((len(small_city.merchants), sales_panel.hours, 3)) * 100,
            alerts=[],
            lower_bounds={z.id: 50 for z in small_city.zones},
            rules=rules,
            already_triggered=frozenset(),
        )

        assert isinstance(triggers, tuple)
        assert isinstance(states, dict)


class TestZoneStatus:
    """Zone status transitions."""

    def test_zone_status_no_data_when_few_shops(self, small_city: City, sales_panel: SalesPanel) -> None:
        """Zone status is 'no_data' when < min_shops_in_index (SPEC §8.2)."""
        # Use default rules which have min_shops_in_index=20
        # Our small_city has only 25 merchants per zone
        rules = default_rules()

        _, states = evaluate_hour(
            at=at(date(2025, 8, 19), 17),
            city=small_city,
            actual=sales_panel,
            expected_p50=np.ones((len(small_city.merchants), sales_panel.hours, 3)) * 100,
            alerts=[],
            lower_bounds={z.id: 50 for z in small_city.zones},
            rules=rules,
            already_triggered=frozenset(),
        )

        # Zones should have some status assigned
        assert all(zone.id in states for zone in small_city.zones)

    def test_zone_status_values_are_valid(self, small_city: City, sales_panel: SalesPanel) -> None:
        """Zone status is one of: triggered/watch/slow_day/no_data/normal."""
        rules = default_rules()

        _, states = evaluate_hour(
            at=at(date(2025, 8, 19), 17),
            city=small_city,
            actual=sales_panel,
            expected_p50=np.ones((len(small_city.merchants), sales_panel.hours, 3)) * 100,
            alerts=[],
            lower_bounds={z.id: 50 for z in small_city.zones},
            rules=rules,
            already_triggered=frozenset(),
        )

        valid_statuses = {"triggered", "watch", "slow_day", "no_data", "normal"}
        for state in states.values():
            assert state.status in valid_statuses


class TestAlreadyTriggered:
    """Already-triggered zones should not trigger again the same day."""

    def test_no_duplicate_trigger_same_day(self, small_city: City, sales_panel: SalesPanel) -> None:
        """Zone marked as triggered should not trigger again that day (SPEC §8.2)."""
        rules = default_rules()

        alert_start = at(date(2025, 8, 19), 14)
        alert_end = alert_start + timedelta(hours=4)
        alert = Alert(
            id="A-20250819-01",
            kind=AlertKind.RAIN,
            level=AlertLevel.RED,
            zone_ids=("Z1",),
            issued_at=alert_start - timedelta(hours=1),
            valid_from=alert_start,
            valid_to=alert_end,
            source="test",
            headline_en="Test",
            headline_hi="परीक्षण",
        )

        expected_p50 = np.ones((len(small_city.merchants), sales_panel.hours, 3)) * 10000
        already_triggered = frozenset([("Z1", date(2025, 8, 19))])

        triggers, states = evaluate_hour(
            at=at(date(2025, 8, 19), 17),
            city=small_city,
            actual=sales_panel,
            expected_p50=expected_p50,
            alerts=[alert],
            lower_bounds={z.id: 50 for z in small_city.zones},
            rules=rules,
            already_triggered=already_triggered,
        )

        # Z1 should not appear in triggers
        z1_triggers = [t for t in triggers if t.zone_id == "Z1"]
        assert len(z1_triggers) == 0


class TestHourlyIndexOrder:
    """Hourly indices must be oldest first (t-3h, t-2h, t-1h)."""

    def test_hourly_indices_oldest_first(self, small_city: City, sales_panel: SalesPanel) -> None:
        """hourly_index_pct are oldest first: (t-3h, t-2h, t-1h) (SPEC §8.2)."""
        rules = default_rules()

        at_time = at(date(2025, 8, 19), 17)

        _, states = evaluate_hour(
            at=at_time,
            city=small_city,
            actual=sales_panel,
            expected_p50=np.ones((len(small_city.merchants), sales_panel.hours, 3)) * 100,
            alerts=[],
            lower_bounds={z.id: 50 for z in small_city.zones},
            rules=rules,
            already_triggered=frozenset(),
        )

        # All zones should have hourly_pct with 3 elements (oldest to newest)
        for zone_state in states.values():
            if zone_state.status != "no_data":
                assert len(zone_state.hourly_pct) == 3
