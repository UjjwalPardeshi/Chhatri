"""calibration.json: stable text read back by `load_calibration` (SPEC §17.4, §24.1, B6)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from types import MappingProxyType

import pytest

from chhatri.pipeline.calibration_io import calibration_json, calibration_text, write_calibration
from chhatri.sim.calibration import load_calibration
from chhatri.sim.types import Calibration

TUNED = Calibration(
    anil_base_day_paise=505_731,
    zone_rain_scale=MappingProxyType({"Z7": 0.704364, "Z12": 0.859762, "Z3": 1.174642}),
    z9_slow_depth=0.401234,
    z7_other_scale=0.862263,
    z7_tune_merchant_id="S-0657",
    z7_tune_base_day_paise=254_706,
)


def test_json_has_exactly_the_six_fields_with_sorted_zones() -> None:
    document = calibration_json(TUNED)
    assert sorted(document) == [
        "anil_base_day_paise", "z7_other_scale", "z7_tune_base_day_paise",
        "z7_tune_merchant_id", "z9_slow_depth", "zone_rain_scale",
    ]  # fmt: skip
    assert list(document["zone_rain_scale"]) == ["Z12", "Z3", "Z7"]
    assert document["z7_tune_merchant_id"] == "S-0657"


def test_text_is_stable_sorted_and_newline_terminated() -> None:
    text = calibration_text(TUNED)
    assert text.endswith("}\n") and text == calibration_text(TUNED)
    assert json.loads(text) == calibration_json(TUNED)
    assert text.index('"anil_base_day_paise"') < text.index('"zone_rain_scale"')


def test_round_trip_through_load_calibration(tmp_path: Path) -> None:
    assert write_calibration(tmp_path / "calibration.json", TUNED) is True
    loaded = load_calibration(tmp_path, artifacts_dir=tmp_path)
    assert loaded == TUNED
    assert loaded.z9_slow_depth == TUNED.z9_slow_depth  # floats round-trip exactly


def test_defaults_round_trip(tmp_path: Path) -> None:
    write_calibration(tmp_path / "calibration.json", Calibration())
    assert load_calibration(tmp_path, artifacts_dir=tmp_path) == Calibration()


def test_unchanged_file_is_not_rewritten(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "calibration.json"
    assert write_calibration(path, TUNED) is True
    stamp = path.stat().st_mtime_ns
    assert write_calibration(path, TUNED) is False
    assert path.stat().st_mtime_ns == stamp
    assert not list(path.parent.glob(".*.tmp"))
    assert write_calibration(path, Calibration()) is True


@pytest.mark.parametrize(
    "bad",
    [Calibration(anil_base_day_paise=0), Calibration(z9_slow_depth=math.nan),
     Calibration(zone_rain_scale={"Z3": math.inf, "Z7": 1.0, "Z12": 1.0})],
)  # fmt: skip
def test_invalid_values_are_rejected(bad: Calibration) -> None:
    with pytest.raises(ValueError):
        calibration_json(bad)
