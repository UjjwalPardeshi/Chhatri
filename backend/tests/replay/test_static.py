"""load_static: artefacts present, missing or wrong (SPEC §19 preflight, §24.6; decision B6)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from chhatri.config import Settings
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.replay import static as static_module
from chhatri.replay.static import (
    BACKTEST_REPORT,
    MODEL_DIR,
    PREMIUMS_FILE,
    StaticContext,
    load_report,
    load_static,
)
from chhatri.sim.types import City
from tests.replay.helpers import SEED, offline_settings


@pytest.fixture(scope="module")
def artefacts(tmp_path_factory: pytest.TempPathFactory, small_model: ExpectedSalesModel) -> Path:
    root = tmp_path_factory.mktemp("artefacts")
    small_model.save(root / MODEL_DIR)
    (root / "backtest").mkdir()
    (root / BACKTEST_REPORT).write_text(json.dumps({"label": "simulated sales · real Open-Meteo rainfall"}))
    (root / PREMIUMS_FILE).write_text(json.dumps({"Z7": 2068, "Z3": 1420}))
    return root


def test_everything_loads_from_a_complete_artefact_directory(artefacts: Path, settings: Settings) -> None:
    static = load_static(settings, artifacts_dir=artefacts, scale="small")
    assert static.model is not None and static.model_error is None
    assert static.artifacts_dir == artefacts and static.data_dir == settings.chhatri_data_dir
    assert static.backtest_report == {"label": "simulated sales · real Open-Meteo rainfall"}
    assert static.premiums["Z7"] == 2068 and static.premiums["Z3"] == 1420
    assert static.zones_geojson is static.city.geography.zones_geojson
    assert static.hexes_geojson is static.city.geography.hexes_geojson
    assert static.rules.version == "pilot-0.1"
    assert static.premiums_path.is_file() and not static.calibration_path.is_file()


def test_missing_artefacts_do_not_crash_startup(tmp_path: Path, settings: Settings) -> None:
    static = load_static(settings, artifacts_dir=tmp_path, scale="small")
    assert static.model is None
    assert static.model_error is not None and "make data" in static.model_error
    assert static.backtest_report is None
    assert dict(static.premiums) == {}  # SPEC §9.1: every zone at min_per_day_rupees when absent


def test_an_unreadable_model_directory_is_reported(tmp_path: Path, settings: Settings) -> None:
    (tmp_path / MODEL_DIR).mkdir()
    static = load_static(settings, artifacts_dir=tmp_path, scale="small")
    assert static.model is None
    assert static.model_error is not None and "unusable" in static.model_error


def test_a_model_trained_with_another_seed_is_refused(artefacts: Path, var_dir: Path) -> None:
    other = offline_settings(var_dir, chhatri_seed=SEED + 1)
    static = load_static(other, artifacts_dir=artefacts, scale="small")
    assert static.model is None
    assert static.model_error is not None and f"seed {SEED}" in static.model_error


def test_a_model_without_every_zone_bound_is_refused(
    monkeypatch: pytest.MonkeyPatch, small_city: City, tmp_path: Path
) -> None:
    (tmp_path / MODEL_DIR).mkdir()
    fake = SimpleNamespace(manifest=SimpleNamespace(seed=small_city.seed, lower_bound_pct={"Z7": 90}))
    monkeypatch.setattr(ExpectedSalesModel, "load", classmethod(lambda cls, directory: fake))
    model, error = static_module.load_model(tmp_path / MODEL_DIR, small_city)
    assert model is None and error is not None and "no lower bound for zones" in error


@pytest.mark.parametrize("content", ["{not json", "[1, 2]"])
def test_a_malformed_backtest_report_is_an_error(tmp_path: Path, content: str) -> None:
    path = tmp_path / "report.json"
    path.write_text(content)
    with pytest.raises(ValueError, match="backtest report"):
        load_report(path)


def test_static_context_needs_exactly_one_of_model_and_error(static: StaticContext) -> None:
    fields = {name: getattr(static, name) for name in StaticContext.__dataclass_fields__}
    with pytest.raises(ValueError, match="exactly one"):
        StaticContext(**{**fields, "model_error": "also broken"})
    with pytest.raises(ValueError, match="exactly one"):
        StaticContext(**{**fields, "model": None})
