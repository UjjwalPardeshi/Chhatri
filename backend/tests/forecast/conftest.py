"""Shared fixtures for forecast tests: a synthetic 75-shop city, 120 days of sales, one trained model."""

from __future__ import annotations

from datetime import date

import pytest

from chhatri.clock import at, ist
from chhatri.domain.enums import AlertKind
from chhatri.domain.models import Alert
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.sim.types import City, SalesPanel
from tests.forecast.synthetic import make_alert, make_city, make_panel

FIRST_DAY = date(2025, 1, 1)
PANEL_DAYS = 120
TRAIN_END = date(2025, 4, 30)
TRAIN_WEEKS = 12
CALIB_WEEKS = 4
SEED = 1


def training_alerts() -> tuple[Alert, ...]:
    """A rain alert on a fit day (Z1) and a city-wide civic alert on a calibration day."""
    return (
        make_alert(["Z1"], ist(2025, 3, 11, 14), ist(2025, 3, 11, 20), alert_id="A-20250310-01"),
        make_alert(
            ["Z1", "Z2", "Z3"],
            at(date(2025, 4, 15), 0),
            at(date(2025, 4, 16), 0),
            kind=AlertKind.CIVIC,
            alert_id="A-20250414-01",
        ),
    )


@pytest.fixture(scope="session")
def city() -> City:
    return make_city(weekly_off_every=5, uncovered=frozenset({"S-0003"}))


@pytest.fixture(scope="session")
def panel(city: City) -> SalesPanel:
    closures = {"S-0010": [date(2025, 3, 1), date(2025, 3, 2)], "S-0020": [date(2025, 4, 20)]}
    return make_panel(city, FIRST_DAY, PANEL_DAYS, closures=closures)


@pytest.fixture(scope="session")
def alerts() -> tuple[Alert, ...]:
    return training_alerts()


@pytest.fixture(scope="session")
def model(city: City, panel: SalesPanel, alerts: tuple[Alert, ...]) -> ExpectedSalesModel:
    return ExpectedSalesModel.train(
        city,
        panel,
        alerts,
        train_end=TRAIN_END,
        train_weeks=TRAIN_WEEKS,
        calib_weeks=CALIB_WEEKS,
        seed=SEED,
        sample_frac=0.5,
        num_threads=1,
    )
