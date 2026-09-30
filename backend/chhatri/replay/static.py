"""Static context, built once per process (SPEC §24.6; binding decision B6).

`load_static` reads everything that does not change between scenario loads: settings, rules,
calibration, the full city (with its zone and hex GeoJSON), the expected-sales model, the backtest
report and the per-zone premiums. Artefacts live in ``backend/artifacts`` (``chhatri.config.BACKEND_DIR
/ "artifacts"``, B6) unless a test passes its own directory.

Missing or unusable artefacts, documented behaviour (SPEC §19 /api/preflight reports each one):
- model: ``model=None`` and ``model_error`` says why; startup continues, `AppState.load` refuses to
  load a scenario with a clear RuntimeError (the API answers 503).
- calibration.json missing: the documented `Calibration()` defaults (``load_calibration`` logs it).
- premiums.json missing: every zone uses ``min_per_day_rupees`` (SPEC §9.1, logged by the loader).
- backtest report missing: ``backtest_report=None`` (``GET /api/backtest`` answers 404).
A file that exists but is malformed is an error (ValueError), never silently replaced by defaults.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from chhatri.config import BACKEND_DIR, Settings
from chhatri.forecast.errors import ModelArtifactError
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.ledger.premium_table import load_premiums
from chhatri.policy.rules import PolicyRules, default_rules
from chhatri.sim.calibration import CALIBRATION_FILE, load_calibration
from chhatri.sim.city import build_city
from chhatri.sim.types import Calibration, City

__all__ = [
    "ARTIFACTS_DIR",
    "BACKTEST_REPORT",
    "MODEL_DIR",
    "PREMIUMS_FILE",
    "StaticContext",
    "load_model",
    "load_report",
    "load_static",
]

logger = logging.getLogger(__name__)

ARTIFACTS_DIR: Final = BACKEND_DIR / "artifacts"
MODEL_DIR: Final = "model"
BACKTEST_REPORT: Final = Path("backtest") / "report.json"
PREMIUMS_FILE: Final = "premiums.json"
MAKE_DATA_HINT: Final = "run `make data` (python backend/scripts/build_data.py)"

Scale = Literal["full", "small"]


@dataclass(frozen=True, slots=True)
class StaticContext:
    """Everything a scenario load reads but never changes (SPEC §24.6)."""

    settings: Settings
    rules: PolicyRules
    data_dir: Path
    artifacts_dir: Path
    calibration: Calibration
    city: City
    model: ExpectedSalesModel | None
    model_error: str | None
    zones_geojson: dict[str, Any]
    hexes_geojson: dict[str, Any]
    backtest_report: dict[str, Any] | None
    premiums: Mapping[str, int]

    def __post_init__(self) -> None:
        if (self.model is None) == (self.model_error is None):
            raise ValueError("StaticContext needs exactly one of model and model_error")

    @property
    def calibration_path(self) -> Path:
        return self.artifacts_dir / CALIBRATION_FILE

    @property
    def premiums_path(self) -> Path:
        return self.artifacts_dir / PREMIUMS_FILE


def load_model(directory: Path, city: City) -> tuple[ExpectedSalesModel | None, str | None]:
    """(model, None) or (None, reason).

    The model must have been trained for this city: the same seed (SPEC §5.3, §7.2) and a lower
    bound for every zone (SPEC §7.4). Anything else would replay numbers from another world.
    """
    if not directory.is_dir():
        reason = f"model artefacts not found at {directory}; {MAKE_DATA_HINT}"
        logger.error("%s", reason)
        return None, reason
    try:
        model = ExpectedSalesModel.load(directory)
    except (ModelArtifactError, OSError, ValueError) as exc:
        reason = f"model artefacts at {directory} are unusable ({exc}); {MAKE_DATA_HINT}"
        logger.error("%s", reason)
        return None, reason
    if model.manifest.seed != city.seed:
        reason = f"model at {directory} was trained with seed {model.manifest.seed}, the city uses {city.seed}; {MAKE_DATA_HINT}"
        logger.error("%s", reason)
        return None, reason
    missing = [z.id for z in city.zones if z.id not in model.manifest.lower_bound_pct]
    if missing:
        reason = f"model at {directory} has no lower bound for zones {missing}; {MAKE_DATA_HINT}"
        logger.error("%s", reason)
        return None, reason
    return model, None


def load_report(path: Path) -> dict[str, Any] | None:
    """The backtest report (SPEC §18), None when it has not been generated; ValueError if malformed."""
    if not path.exists():
        logger.warning("backtest report %s not found; GET /api/backtest will answer 404", path)
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read the backtest report {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"backtest report {path} must hold a JSON object")
    return raw


def load_static(
    settings: Settings, *, artifacts_dir: Path | None = None, scale: Scale = "full"
) -> StaticContext:
    """Build the process-wide context (SPEC §24.6). Tests may pass their own artefacts and scale."""
    artifacts = Path(artifacts_dir) if artifacts_dir is not None else ARTIFACTS_DIR
    data_dir = Path(settings.chhatri_data_dir)
    rules = default_rules()
    calibration = load_calibration(data_dir, artifacts_dir=artifacts)
    city = build_city(settings.chhatri_seed, data_dir, calibration, scale=scale)
    model, model_error = load_model(artifacts / MODEL_DIR, city)
    report = load_report(artifacts / BACKTEST_REPORT)
    premiums = load_premiums(rules, artifacts / PREMIUMS_FILE)
    logger.info(
        "static context: %d merchants, model %s, %d zone premiums",
        len(city.merchants),
        "loaded" if model is not None else "missing",
        len(premiums),
    )
    return StaticContext(
        settings=settings,
        rules=rules,
        data_dir=data_dir,
        artifacts_dir=artifacts,
        calibration=calibration,
        city=city,
        model=model,
        model_error=model_error,
        zones_geojson=city.geography.zones_geojson,
        hexes_geojson=city.geography.hexes_geojson,
        backtest_report=report,
        premiums=premiums,
    )
