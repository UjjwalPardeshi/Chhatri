"""The replay model artefact, ``backend/artifacts/model/`` (SPEC §7.4, §23; decision B6).

`ensure_model` trains the replay model on the uncalibrated city's training history
(`world.training_world`, ``train_end`` 2025-08-18, 26 weeks with the last 4 held out, SPEC
§7.2-§7.4) and saves it with the forecast save API, unless the directory already holds a model
trained on exactly the same inputs. Next to the model files it writes ``training.json``: the
training parameters, the history's calibration knobs and the sha256 of the training history and
alerts (`world.panel_digest`), so any change to the simulator or the parameters is detected and a
stale model is never reused. A new model is written to a temporary sibling directory and swapped in
by renames, so the directory is never half-written.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, Final

import lightgbm as lgb

from chhatri.forecast.errors import ModelArtifactError
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.pipeline.config import PipelineConfig
from chhatri.pipeline.world import TRAINING_CALIBRATION, TrainingHistory, training_history, training_world

__all__ = ["RECORD_FILE", "ensure_model", "read_record", "train_model", "training_record"]

logger = logging.getLogger(__name__)

RECORD_FILE: Final = "training.json"
RECORD_VERSION: Final = 2
STAGING_PREFIX: Final = ".model-staging-"
RETIRED_PREFIX: Final = ".model-retired-"
DIR_MODE: Final = 0o755  # mkdtemp creates 0700; the artefact directory is world-readable


def training_record(config: PipelineConfig, history: TrainingHistory) -> dict[str, Any]:
    """Everything the trained model depends on (compared verbatim to decide whether to retrain)."""
    return {
        "record_version": RECORD_VERSION,
        "seed": config.seed,
        "scale": config.scale,
        "train_end": config.train_end.isoformat(),
        "train_weeks": config.train_weeks,
        "calib_weeks": config.calib_weeks,
        "sample_frac": config.sample_frac,
        "num_threads": config.num_threads,
        "history_first_day": history.first_day.isoformat(),
        "history_last_day": history.last_day.isoformat(),
        "history_digest": history.digest,
        "history_calibration": {
            "anil_base_day_paise": TRAINING_CALIBRATION.anil_base_day_paise,
            "z7_other_scale": float(TRAINING_CALIBRATION.z7_other_scale),
            "z7_tune_base_day_paise": TRAINING_CALIBRATION.z7_tune_base_day_paise,
            "z7_tune_merchant_id": TRAINING_CALIBRATION.z7_tune_merchant_id,
        },
        "lightgbm": lgb.__version__,
    }


def read_record(model_dir: Path) -> dict[str, Any] | None:
    """The stored training record, or None when absent or unreadable (logged; the model is rebuilt)."""
    path = model_dir / RECORD_FILE
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("unreadable training record %s (%s); the model will be retrained", path, exc)
        return None
    return raw if isinstance(raw, dict) else None


def train_model(config: PipelineConfig, history: TrainingHistory) -> ExpectedSalesModel:
    """Train the replay model on `history` (SPEC §7.1-§7.4) with the configured threads."""
    return ExpectedSalesModel.train(
        history.city,
        history.panel,
        history.alerts,
        train_end=config.train_end,
        train_weeks=config.train_weeks,
        calib_weeks=config.calib_weeks,
        seed=config.seed,
        sample_frac=config.sample_frac,
        num_threads=config.num_threads,
    )


def _save(model_dir: Path, model: ExpectedSalesModel, record: dict[str, Any]) -> None:
    model_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=model_dir.parent))
    staging.chmod(DIR_MODE)
    try:
        model.save(staging)
        (staging / RECORD_FILE).write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        retired = None
        if model_dir.exists():
            retired = Path(tempfile.mkdtemp(prefix=RETIRED_PREFIX, dir=model_dir.parent))
            retired.rmdir()
            model_dir.rename(retired)
        staging.rename(model_dir)
        if retired is not None:
            shutil.rmtree(retired)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    logger.info("saved replay model to %s", model_dir)


def ensure_model(
    config: PipelineConfig, *, history: TrainingHistory | None = None, force: bool = False
) -> ExpectedSalesModel:
    """The replay model: loaded when up to date with its inputs, else trained and saved.

    `history` must be `training_history(training_world(config), config)` when given (saves
    generating it twice).
    """
    if history is None:
        history = training_history(training_world(config), config)
    record = training_record(config, history)
    if not force and read_record(config.model_dir) == record:
        try:
            model = ExpectedSalesModel.load(config.model_dir)
        except ModelArtifactError as exc:
            logger.warning("model in %s is unusable (%s); retraining", config.model_dir, exc)
        else:
            logger.info("replay model up to date in %s", config.model_dir)
            return model
    model = train_model(config, history)
    _save(config.model_dir, model, record)
    return model
