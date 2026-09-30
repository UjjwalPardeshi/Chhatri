"""Shared fixtures for the sim tests: cities and shock calendars are built once per session."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from chhatri.config import BACKEND_DIR, DATA_DIR
from chhatri.sim.city import build_city
from chhatri.sim.scenarios import get_scenario
from chhatri.sim.types import Calibration, City
from chhatri.sim.weather import ShockCalendar, build_shocks

SEED = 20251019


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture(scope="session")
def full_city() -> City:
    return build_city(SEED, DATA_DIR, scale="full")


@pytest.fixture(scope="session")
def small_city() -> City:
    return build_city(SEED, DATA_DIR, scale="small")


@pytest.fixture(scope="session")
def small_shocks(small_city: City) -> ShockCalendar:
    return build_shocks(small_city, DATA_DIR, SEED)


@pytest.fixture(scope="session")
def monsoon_shocks(small_city: City) -> ShockCalendar:
    scenario = get_scenario("monsoon", small_city, Calibration())
    return build_shocks(small_city, DATA_DIR, SEED, scenario.overrides)


def load_script(name: str) -> ModuleType:
    """Import backend/scripts/<name>.py as a module (scripts/ is not a package)."""
    path = BACKEND_DIR / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"chhatri_script_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
