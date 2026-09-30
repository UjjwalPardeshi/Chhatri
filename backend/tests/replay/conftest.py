"""Session fixtures for the replay tests (SPEC §24.6): a small city and a quickly trained model.

No test here needs `make data`: the StaticContext is built directly from `build_city(scale="small")`
and an ExpectedSalesModel trained on simulated history of that city (`tests.replay.small_world`,
cached per process so the API and demo-flow tests reuse it; num_threads ≤ 4, SPEC §7.2).
Read-only tests share one monsoon replay stepped to 17:05, built on a private event loop so no
test's loop is involved.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chhatri.config import Settings
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.replay.state import Runtime
from chhatri.replay.static import StaticContext
from chhatri.sim.types import City
from tests.replay import small_world
from tests.replay.helpers import loaded, make_static, offline_settings, run_in_thread


@pytest.fixture(scope="session")
def var_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("replay-var")


@pytest.fixture(scope="session")
def settings(var_dir: Path) -> Settings:
    return offline_settings(var_dir)


@pytest.fixture(scope="session")
def small_city() -> City:
    return small_world.small_city()


@pytest.fixture(scope="session")
def small_model() -> ExpectedSalesModel:
    return small_world.small_model()


@pytest.fixture(scope="session")
def static(
    settings: Settings, small_city: City, small_model: ExpectedSalesModel, var_dir: Path
) -> StaticContext:
    return make_static(settings, small_city, small_model, var_dir / "artifacts")


@pytest.fixture(scope="session")
def monsoon_1705(static: StaticContext) -> Runtime:
    """The monsoon replay at 17:05 (credits 17:04, pauses 17:05); read-only for every test."""
    return run_in_thread(lambda: loaded(static, "monsoon", seek="17:05"))
