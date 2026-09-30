"""Pipeline configuration (SPEC §7.4, §23, B6) and golden targets (SPEC §17.2)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from chhatri.config import BACKEND_DIR, Settings
from chhatri.pipeline.config import (
    ARTIFACTS_DIR,
    CALIB_WEEKS,
    NUM_THREADS,
    REPLAY_TRAIN_END,
    TRAIN_WEEKS,
    PipelineConfig,
    default_config,
)
from chhatri.pipeline.targets import SPEC_TARGETS, Targets
from tests.pipeline.conftest import SEED


def test_defaults_are_the_replay_model_of_spec_7_4(tmp_path: Path) -> None:
    config = PipelineConfig(seed=SEED, data_dir=tmp_path, artifacts_dir=str(tmp_path / "a"))  # type: ignore[arg-type]
    assert date(2025, 8, 18) == REPLAY_TRAIN_END
    assert (config.train_end, config.train_weeks, config.calib_weeks) == (REPLAY_TRAIN_END, 26, 4)
    assert (TRAIN_WEEKS, CALIB_WEEKS) == (26, 4)
    assert config.num_threads == NUM_THREADS == 4
    assert config.sample_frac == 0.35
    assert config.artifacts_dir == tmp_path / "a"
    assert config.model_dir == tmp_path / "a" / "model"
    assert config.calibration_path == tmp_path / "a" / "calibration.json"
    assert config.manifest_path == tmp_path / "a" / "MANIFEST.json"


def test_artifacts_default_to_backend_artifacts() -> None:
    assert ARTIFACTS_DIR == BACKEND_DIR / "artifacts"
    config = default_config(Settings(chhatri_seed=7))
    assert config.seed == 7
    assert config.artifacts_dir == ARTIFACTS_DIR
    assert config.data_dir == Settings().chhatri_data_dir
    override = default_config(
        Settings(chhatri_seed=7), artifacts_dir=Path("/x"), data_dir=Path("/d"), scale="small"
    )
    assert (override.artifacts_dir, override.data_dir, override.scale) == (Path("/x"), Path("/d"), "small")


@pytest.mark.parametrize(
    "overrides",
    [{"seed": -1}, {"calib_weeks": 0}, {"calib_weeks": 26}, {"sample_frac": 0.0}, {"sample_frac": 1.5},
     {"num_threads": 0}, {"scale": "medium"}],
)  # fmt: skip
def test_invalid_config(tmp_path: Path, overrides: dict[str, object]) -> None:
    params: dict[str, object] = {"seed": SEED, "data_dir": tmp_path, "artifacts_dir": tmp_path}
    params.update(overrides)
    with pytest.raises(ValueError):
        PipelineConfig(**params)  # type: ignore[arg-type]


def test_spec_targets_are_the_deck_numbers() -> None:
    assert SPEC_TARGETS.anil_expected_paise == 438_000
    assert dict(SPEC_TARGETS.zone_index_pct) == {"Z7": 37, "Z3": 38, "Z12": 47}
    assert dict(SPEC_TARGETS.zone_shops) == {"Z7": 46, "Z3": 141, "Z12": 125}
    assert SPEC_TARGETS.area_decisions == 312
    assert SPEC_TARGETS.slow_index_pct == 61
    assert SPEC_TARGETS.z7_total_paise == 5_890_000
    assert SPEC_TARGETS.anil_area_paise == 138_000
    assert SPEC_TARGETS.drop_pct("Z7") == 63
    assert SPEC_TARGETS.anil_formula_en == "½ × ₹4,380 × 63% = ₹1,380"
    with pytest.raises(TypeError):
        SPEC_TARGETS.zone_index_pct["Z7"] = 1  # type: ignore[index]


@pytest.mark.parametrize(
    "overrides",
    [{"zone_index_pct": {"Z7": 37}}, {"zone_shops": {"Z7": 1, "Z3": 1, "Z12": 1, "Z9": 1}},
     {"zone_index_pct": {"Z7": 0, "Z3": 38, "Z12": 47}}, {"anil_expected_paise": 0}, {"z7_total_paise": -1}],
)  # fmt: skip
def test_invalid_targets(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        Targets(**overrides)  # type: ignore[arg-type]
