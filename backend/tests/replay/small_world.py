"""The small test city and its quickly trained model, built once per test process (SPEC §24.1, §7).

The replay, API integration and demo-flow tests all need the same world. The session fixtures of
each test package call these cached builders, so one pytest run builds the small city and trains
the model once, whichever packages it collects. Nothing here needs ``make data``.
"""

from __future__ import annotations

from datetime import date
from functools import cache
from typing import Final

from chhatri.config import DATA_DIR
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.sim.city import build_city
from chhatri.sim.sales import SalesSimulator
from chhatri.sim.scenarios import get_scenario
from chhatri.sim.types import Calibration, City
from chhatri.sim.weather import build_shocks
from tests.replay.helpers import SEED

__all__ = ["small_city", "small_model"]

HISTORY_FIRST: Final = date(2025, 3, 1)
TRAIN_END: Final = date(2025, 8, 18)  # SPEC §7.4: the replay model ends the day before the monsoon
TRAIN_WEEKS: Final = 16
CALIB_WEEKS: Final = 4
SAMPLE_FRAC: Final = 0.35
TRAIN_THREADS: Final = 4  # shared machine: at most 4 LightGBM threads


@cache
def small_city() -> City:
    """SPEC §24.1 ``scale="small"``: Z3, Z7, Z9 and Z12 with the demo merchants, default calibration."""
    return build_city(SEED, DATA_DIR, Calibration(), scale="small")


@cache
def small_model() -> ExpectedSalesModel:
    """An expected-sales model trained on the small city up to the day before the monsoon replay."""
    city = small_city()
    scenario = get_scenario("monsoon", city, Calibration())
    shocks = build_shocks(city, DATA_DIR, SEED, overrides=scenario.overrides)
    history = SalesSimulator(city, shocks, SEED).generate(HISTORY_FIRST, TRAIN_END)
    return ExpectedSalesModel.train(
        city,
        history,
        shocks.alerts_between(history.start, history.end),
        train_end=TRAIN_END,
        train_weeks=TRAIN_WEEKS,
        calib_weeks=CALIB_WEEKS,
        seed=SEED,
        sample_frac=SAMPLE_FRAC,
        num_threads=TRAIN_THREADS,
    )
