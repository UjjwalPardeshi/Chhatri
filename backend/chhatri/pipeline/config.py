"""Configuration of the data pipeline (SPEC §7, §17.4, §23; decisions B6, B9).

`PipelineConfig` says where the pipeline reads inputs (``data_dir``: wards, weather fixtures,
slips) and writes artefacts (``artifacts_dir``, default ``backend/artifacts``: ``model/``,
``calibration.json`` and ``MANIFEST.json`` — the only artefacts this package writes, B6), plus the
replay model's training window: ``train_end`` 2025-08-18 (the day before the monsoon replay,
SPEC §7.4), 26 training weeks of which the last 4 are held out for calibration (SPEC §7.4, §24.2),
sampling 35 % of fit rows and 4 LightGBM threads (the shared-machine cap; SPEC §7.2 asks for one
thread only in tests). ``scale="small"`` builds the four-zone test city (SPEC §24.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final, Literal

from chhatri.config import BACKEND_DIR, Settings
from chhatri.sim.calibration import CALIBRATION_FILE

__all__ = [
    "ARTIFACTS_DIR",
    "CALIB_WEEKS",
    "MANIFEST_FILE",
    "MODEL_DIRNAME",
    "NUM_THREADS",
    "REPLAY_TRAIN_END",
    "SAMPLE_FRAC",
    "TRAIN_WEEKS",
    "PipelineConfig",
    "Scale",
    "default_config",
]

ARTIFACTS_DIR: Final = BACKEND_DIR / "artifacts"  # B6
MODEL_DIRNAME: Final = "model"
MANIFEST_FILE: Final = "MANIFEST.json"
REPLAY_TRAIN_END: Final = date(2025, 8, 18)  # SPEC §7.4
TRAIN_WEEKS: Final = 26  # SPEC §24.2 default; includes the held-out weeks (SPEC §7.4)
CALIB_WEEKS: Final = 4  # SPEC §7.4: the last 4 weeks of the training window
SAMPLE_FRAC: Final = 0.35  # SPEC §24.2 default
NUM_THREADS: Final = 4  # at most 4 threads on the shared machine
SCALES: Final = ("full", "small")

Scale = Literal["full", "small"]


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """Inputs, outputs and training parameters of one pipeline run (validated on construction)."""

    seed: int
    data_dir: Path
    artifacts_dir: Path
    train_end: date = REPLAY_TRAIN_END
    train_weeks: int = TRAIN_WEEKS
    calib_weeks: int = CALIB_WEEKS
    sample_frac: float = SAMPLE_FRAC
    num_threads: int = NUM_THREADS
    scale: Scale = "full"

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError(f"seed must be non-negative, got {self.seed}")
        if not 1 <= self.calib_weeks < self.train_weeks:
            raise ValueError(
                f"need 1 <= calib_weeks < train_weeks, got {self.calib_weeks} and {self.train_weeks}"
            )
        if not 0.0 < self.sample_frac <= 1.0:
            raise ValueError(f"sample_frac must be in (0, 1], got {self.sample_frac}")
        if self.num_threads < 1:
            raise ValueError(f"num_threads must be >= 1, got {self.num_threads}")
        if self.scale not in SCALES:
            raise ValueError(f"scale must be one of {SCALES}, got {self.scale!r}")
        object.__setattr__(self, "data_dir", Path(self.data_dir))
        object.__setattr__(self, "artifacts_dir", Path(self.artifacts_dir))

    @property
    def model_dir(self) -> Path:
        return self.artifacts_dir / MODEL_DIRNAME

    @property
    def calibration_path(self) -> Path:
        return self.artifacts_dir / CALIBRATION_FILE

    @property
    def manifest_path(self) -> Path:
        return self.artifacts_dir / MANIFEST_FILE


def default_config(
    settings: Settings | None = None,
    *,
    artifacts_dir: Path | None = None,
    data_dir: Path | None = None,
    scale: Scale = "full",
) -> PipelineConfig:
    """The configuration `make data` uses: seed and data directory from `Settings`, B6 artefacts."""
    settings = settings if settings is not None else Settings()
    return PipelineConfig(
        seed=settings.chhatri_seed,
        data_dir=data_dir if data_dir is not None else settings.chhatri_data_dir,
        artifacts_dir=artifacts_dir if artifacts_dir is not None else ARTIFACTS_DIR,
        scale=scale,
    )
