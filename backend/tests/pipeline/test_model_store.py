"""artifacts/model: trained once per input set, swapped in atomically (SPEC §7.4, B6)."""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from chhatri.forecast.model import ExpectedSalesModel
from chhatri.pipeline import model_store as ms
from chhatri.pipeline.config import PipelineConfig
from chhatri.pipeline.model_store import RECORD_FILE, ensure_model, read_record, training_record
from chhatri.pipeline.world import TrainingHistory, World, training_history
from tests.pipeline.conftest import small_config


@pytest.fixture
def trainings(monkeypatch: pytest.MonkeyPatch, model: ExpectedSalesModel) -> list[str]:
    """Replace training by the session model and count the calls."""
    calls: list[str] = []

    def fake_train(config: PipelineConfig, history: TrainingHistory) -> ExpectedSalesModel:
        calls.append(history.digest)
        return model

    monkeypatch.setattr(ms, "train_model", fake_train)
    return calls


def test_record_lists_every_training_input(config: PipelineConfig, world: World) -> None:
    history = training_history(world, config)
    record = training_record(config, history)
    assert record["history_digest"] == history.digest
    assert record["train_end"] == "2025-08-18"
    assert (record["train_weeks"], record["calib_weeks"], record["num_threads"]) == (4, 2, 1)
    assert record["history_first_day"] == history.first_day.isoformat()
    assert {"seed", "scale", "sample_frac", "lightgbm", "record_version"} <= set(record)
    assert record["history_calibration"] == {
        "anil_base_day_paise": 420_000, "z7_other_scale": 1.0,
        "z7_tune_base_day_paise": None, "z7_tune_merchant_id": None,
    }  # fmt: skip  # the uncalibrated city (pipeline.world)


def test_session_model_was_saved_with_its_record(config: PipelineConfig, model: ExpectedSalesModel) -> None:
    assert sorted(p.name for p in config.model_dir.iterdir()) == [
        "manifest.json", "p10.txt", "p50.txt", "p90.txt", "schema.json", RECORD_FILE,
    ]  # fmt: skip
    assert stat.S_IMODE(config.model_dir.stat().st_mode) == ms.DIR_MODE
    assert not [p for p in config.artifacts_dir.iterdir() if p.name.startswith(".")]
    assert ExpectedSalesModel.load(config.model_dir).manifest == model.manifest


def test_up_to_date_model_is_loaded_not_trained(artifacts: Path, world: World, trainings: list[str]) -> None:
    config = small_config(artifacts)
    first = ensure_model(config)
    assert len(trainings) == 1
    again = ensure_model(config, history=training_history(world, config))
    assert len(trainings) == 1 and again.manifest == first.manifest
    ensure_model(config, force=True)
    assert len(trainings) == 2
    assert not [p for p in artifacts.iterdir() if p.name.startswith(".")]


def test_changed_inputs_retrain(artifacts: Path, trainings: list[str]) -> None:
    ensure_model(small_config(artifacts))
    ensure_model(small_config(artifacts, sample_frac=0.5))
    assert len(trainings) == 2


def test_broken_record_or_model_retrains(artifacts: Path, trainings: list[str]) -> None:
    config = small_config(artifacts)
    ensure_model(config)
    (config.model_dir / RECORD_FILE).write_text("{broken", encoding="utf-8")
    assert read_record(config.model_dir) is None
    ensure_model(config)
    assert len(trainings) == 2
    (config.model_dir / "p50.txt").unlink()
    ensure_model(config)
    assert len(trainings) == 3
    (config.model_dir / RECORD_FILE).write_text("[1]", encoding="utf-8")
    assert read_record(config.model_dir) is None
    assert read_record(artifacts / "missing") is None


def test_failed_save_leaves_the_previous_model(
    artifacts: Path, trainings: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    config = small_config(artifacts)
    ensure_model(config)
    before = json.loads((config.model_dir / RECORD_FILE).read_text())

    def broken_save(self: ExpectedSalesModel, directory: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(ExpectedSalesModel, "save", broken_save)
    with pytest.raises(OSError, match="disk full"):
        ensure_model(config, force=True)
    assert json.loads((config.model_dir / RECORD_FILE).read_text()) == before
    assert not [p for p in artifacts.iterdir() if p.name.startswith(".")]


def test_train_model_fits_the_history_city(config: PipelineConfig, world: World, monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake(city, panel, alerts, **params):
        seen.update(city=city, panel=panel, alerts=alerts, **params)
        return "model"

    monkeypatch.setattr(ExpectedSalesModel, "train", staticmethod(fake))
    history = training_history(world, config)
    assert ms.train_model(config, history) == "model"
    assert (
        seen["city"] is history.city and seen["panel"] is history.panel and seen["alerts"] == history.alerts
    )
    assert (seen["train_end"], seen["train_weeks"], seen["calib_weeks"]) == (config.train_end, 4, 2)
    assert (seen["seed"], seen["sample_frac"], seen["num_threads"]) == (config.seed, 0.35, 1)
