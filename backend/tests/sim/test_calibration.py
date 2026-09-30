"""SPEC §17.4, §24.1: load_calibration defaults and validation."""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType

import pytest

from chhatri.sim.calibration import Calibration, load_calibration

GOOD = {
    "anil_base_day_paise": 438_000,
    "zone_rain_scale": {"Z3": 1.2, "Z7": 0.8, "Z12": 1},
    "z9_slow_depth": 0.4,
    "z7_other_scale": 1,
    "z7_tune_merchant_id": "S-0101",
    "z7_tune_base_day_paise": 512_300,
}


def write(tmp_path: Path, payload: object) -> Path:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "calibration.json").write_text(
        json.dumps(payload) if not isinstance(payload, str) else payload
    )
    return tmp_path / "data"


def test_missing_file_gives_documented_defaults(tmp_path: Path) -> None:
    assert load_calibration(tmp_path / "data") == Calibration()


def test_reads_artifacts_next_to_data_dir(tmp_path: Path) -> None:
    calibration = load_calibration(write(tmp_path, GOOD))
    assert calibration.anil_base_day_paise == 438_000
    assert dict(calibration.zone_rain_scale) == {"Z12": 1.0, "Z3": 1.2, "Z7": 0.8}
    assert isinstance(calibration.zone_rain_scale, MappingProxyType)
    assert calibration.z9_slow_depth == 0.4 and calibration.z7_other_scale == 1.0
    assert (calibration.z7_tune_merchant_id, calibration.z7_tune_base_day_paise) == ("S-0101", 512_300)


def test_explicit_artifacts_dir(tmp_path: Path) -> None:
    other = tmp_path / "elsewhere"
    other.mkdir()
    (other / "calibration.json").write_text(
        json.dumps(GOOD | {"z7_tune_merchant_id": None, "z7_tune_base_day_paise": None})
    )
    calibration = load_calibration(tmp_path / "data", artifacts_dir=other)
    assert calibration.z7_tune_merchant_id is None


@pytest.mark.parametrize(
    "payload",
    [
        "{not json",
        [1, 2],
        {k: v for k, v in GOOD.items() if k != "z9_slow_depth"},
        GOOD | {"extra": 1},
        GOOD | {"anil_base_day_paise": 0},
        GOOD | {"anil_base_day_paise": "438000"},
        GOOD | {"zone_rain_scale": {"Z3": 1.0, "Z7": 1.0}},
        GOOD | {"zone_rain_scale": {"Z3": 1.0, "Z7": -1.0, "Z12": 1.0}},
        GOOD | {"z9_slow_depth": 1.0},
        GOOD | {"z7_other_scale": 0},
        GOOD | {"z7_tune_merchant_id": "anil"},
        GOOD | {"z7_tune_merchant_id": None},
    ],
)
def test_malformed_file_raises(tmp_path: Path, payload: object) -> None:
    with pytest.raises(ValueError, match="calibration"):
        load_calibration(write(tmp_path, payload))
