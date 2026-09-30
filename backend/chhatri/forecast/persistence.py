"""Saving and loading the expected-sales model (SPEC §7.4).

A model directory holds `p10.txt`, `p50.txt`, `p90.txt` (LightGBM text models, exact float
round-trip), `schema.json` (feature list and the fixed category lists) and `manifest.json`
(ModelManifest). Loading validates every file and raises ModelArtifactError instead of returning a
partial model.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Final

import lightgbm as lgb

from chhatri.forecast.errors import ModelArtifactError
from chhatri.forecast.features import CATEGORICAL, FEATURES, FeatureSchema
from chhatri.forecast.history import LEVEL_DAYS
from chhatri.forecast.manifest import ModelManifest
from chhatri.forecast.prediction import QUANTILE_KEYS, QUANTILES, QuantileBoosters

logger = logging.getLogger(__name__)

FORMAT_VERSION: Final = 1
SCHEMA_FILE: Final = "schema.json"
MANIFEST_FILE: Final = "manifest.json"
DATE_FIELDS: Final = ("train_start", "train_end", "calib_start", "calib_end")


def _booster_file(key: str) -> str:
    return f"{key}.txt"


def manifest_to_json(manifest: ModelManifest) -> dict[str, Any]:
    return {
        "seed": manifest.seed,
        **{name: getattr(manifest, name).isoformat() for name in DATE_FIELDS},
        "rows_train": manifest.rows_train,
        "rows_calib": manifest.rows_calib,
        "pinball": dict(manifest.pinball),
        "coverage_p10_p90": manifest.coverage_p10_p90,
        "lower_bound_pct": dict(manifest.lower_bound_pct),
    }


def manifest_from_json(raw: dict[str, Any]) -> ModelManifest:
    try:
        return ModelManifest(
            seed=int(raw["seed"]),
            **{name: date.fromisoformat(raw[name]) for name in DATE_FIELDS},
            rows_train=int(raw["rows_train"]),
            rows_calib=int(raw["rows_calib"]),
            pinball={str(k): float(v) for k, v in raw["pinball"].items()},
            coverage_p10_p90=float(raw["coverage_p10_p90"]),
            lower_bound_pct={str(k): int(v) for k, v in raw["lower_bound_pct"].items()},
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ModelArtifactError(f"invalid {MANIFEST_FILE}: {exc}") from exc


def _schema_json(schema: FeatureSchema) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION,
        "features": list(FEATURES),
        "categorical": list(CATEGORICAL),
        "zone_ids": list(schema.zone_ids),
        "shop_types": list(schema.shop_types),
        "quantiles": list(QUANTILES),
        "level_days": LEVEL_DAYS,
    }


def save_model(directory: Path, boosters: QuantileBoosters, manifest: ModelManifest) -> None:
    """Write the three boosters, the schema and the manifest (deterministic text output)."""
    directory.mkdir(parents=True, exist_ok=True)
    for key, booster in zip(QUANTILE_KEYS, boosters.boosters, strict=True):
        (directory / _booster_file(key)).write_text(booster.model_to_string(), encoding="utf-8")
    (directory / SCHEMA_FILE).write_text(
        json.dumps(_schema_json(boosters.schema), indent=2), encoding="utf-8"
    )
    (directory / MANIFEST_FILE).write_text(json.dumps(manifest_to_json(manifest), indent=2), encoding="utf-8")
    logger.info("saved expected-sales model to %s", directory)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ModelArtifactError(f"missing model file {path}") from exc
    except json.JSONDecodeError as exc:
        raise ModelArtifactError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ModelArtifactError(f"{path} must hold a JSON object")
    return raw


def _load_schema(directory: Path) -> FeatureSchema:
    raw = _read_json(directory / SCHEMA_FILE)
    expected = {
        "format_version": FORMAT_VERSION,
        "features": list(FEATURES),
        "categorical": list(CATEGORICAL),
        "quantiles": list(QUANTILES),
        "level_days": LEVEL_DAYS,
    }
    for key, value in expected.items():
        if raw.get(key) != value:
            raise ModelArtifactError(f"{SCHEMA_FILE}: {key}={raw.get(key)!r}, this code expects {value!r}")
    try:
        return FeatureSchema(zone_ids=tuple(raw["zone_ids"]), shop_types=tuple(raw["shop_types"]))
    except (KeyError, TypeError) as exc:
        raise ModelArtifactError(f"{SCHEMA_FILE}: missing category lists ({exc})") from exc


def _load_booster(path: Path, schema: FeatureSchema) -> lgb.Booster:
    try:
        booster = lgb.Booster(model_str=path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ModelArtifactError(f"missing model file {path}") from exc
    except lgb.basic.LightGBMError as exc:
        raise ModelArtifactError(f"{path} is not a LightGBM model: {exc}") from exc
    if booster.feature_name() != list(FEATURES):
        raise ModelArtifactError(f"{path}: features {booster.feature_name()} != {list(FEATURES)}")
    categories = [list(schema.zone_ids), list(schema.shop_types)]
    if booster.pandas_categorical != categories:
        raise ModelArtifactError(f"{path}: category lists differ from {SCHEMA_FILE}")
    return booster


def load_model(directory: Path) -> tuple[QuantileBoosters, ModelManifest]:
    """Read a directory written by `save_model`; ModelArtifactError on any missing or bad file."""
    if not directory.is_dir():
        raise ModelArtifactError(f"model directory {directory} does not exist")
    schema = _load_schema(directory)
    boosters = tuple(_load_booster(directory / _booster_file(key), schema) for key in QUANTILE_KEYS)
    manifest = manifest_from_json(_read_json(directory / MANIFEST_FILE))
    return QuantileBoosters(boosters=boosters, schema=schema), manifest
