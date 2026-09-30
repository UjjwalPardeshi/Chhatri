"""Model save/load round trip and artefact validation (SPEC §7.4)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from chhatri.clock import at
from chhatri.forecast.errors import ModelArtifactError
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.sim.types import City, SalesPanel

MAX_MODEL_BYTES = 10 * 1024 * 1024


@pytest.fixture
def saved(model: ExpectedSalesModel, tmp_path: Path) -> Iterator[Path]:
    directory = tmp_path / "model"
    model.save(directory)
    yield directory


def test_round_trip_reproduces_predictions(
    model: ExpectedSalesModel, saved: Path, city: City, panel: SalesPanel
) -> None:
    loaded = ExpectedSalesModel.load(saved)
    assert loaded.manifest == model.manifest
    assert loaded.schema == model.schema
    start = at(date(2025, 4, 28), 0)
    assert np.array_equal(loaded.predict(city, panel, start, 48), model.predict(city, panel, start, 48))


def test_files_are_small_and_deterministic(model: ExpectedSalesModel, saved: Path, tmp_path: Path) -> None:
    assert sorted(p.name for p in saved.iterdir()) == [
        "manifest.json",
        "p10.txt",
        "p50.txt",
        "p90.txt",
        "schema.json",
    ]
    assert sum(p.stat().st_size for p in saved.iterdir()) < MAX_MODEL_BYTES
    again = tmp_path / "again"
    model.save(again)
    for path in saved.iterdir():
        assert (again / path.name).read_bytes() == path.read_bytes()
    schema = json.loads((saved / "schema.json").read_text())
    assert schema["zone_ids"] == ["Z1", "Z2", "Z3"] and len(schema["shop_types"]) == 7


def test_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ModelArtifactError, match="does not exist"):
        ExpectedSalesModel.load(tmp_path / "nope")


@pytest.mark.parametrize("name", ["p50.txt", "schema.json", "manifest.json"])
def test_missing_file(saved: Path, name: str) -> None:
    (saved / name).unlink()
    with pytest.raises(ModelArtifactError, match="missing model file"):
        ExpectedSalesModel.load(saved)


def _edit_json(path: Path, **changes: object) -> None:
    raw = json.loads(path.read_text())
    raw.update(changes)
    path.write_text(json.dumps(raw))


@pytest.mark.parametrize(
    "changes",
    [{"format_version": 99}, {"features": ["hour"]}, {"level_days": 7}],
)
def test_schema_mismatch(saved: Path, changes: dict[str, object]) -> None:
    _edit_json(saved / "schema.json", **changes)
    with pytest.raises(ModelArtifactError, match="schema.json"):
        ExpectedSalesModel.load(saved)


def test_category_lists_must_match_boosters(saved: Path) -> None:
    _edit_json(saved / "schema.json", zone_ids=["Z1", "Z2", "Z4"])
    with pytest.raises(ModelArtifactError, match="category lists"):
        ExpectedSalesModel.load(saved)


def test_schema_without_categories(saved: Path) -> None:
    raw = json.loads((saved / "schema.json").read_text())
    del raw["zone_ids"]
    (saved / "schema.json").write_text(json.dumps(raw))
    with pytest.raises(ModelArtifactError, match="category lists"):
        ExpectedSalesModel.load(saved)


@pytest.mark.parametrize("content", ["not json", "[1, 2]"])
def test_bad_json(saved: Path, content: str) -> None:
    (saved / "manifest.json").write_text(content)
    with pytest.raises(ModelArtifactError):
        ExpectedSalesModel.load(saved)


def test_bad_manifest_fields(saved: Path) -> None:
    _edit_json(saved / "manifest.json", train_start="yesterday")
    with pytest.raises(ModelArtifactError, match="manifest.json"):
        ExpectedSalesModel.load(saved)


def test_corrupt_booster(saved: Path) -> None:
    (saved / "p90.txt").write_text("garbage")
    with pytest.raises(ModelArtifactError, match="p90.txt"):
        ExpectedSalesModel.load(saved)


def test_booster_with_other_features(saved: Path) -> None:
    text = (saved / "p10.txt").read_text().replace("shop_hour_share", "other_feature")
    (saved / "p10.txt").write_text(text)
    with pytest.raises(ModelArtifactError, match="features"):
        ExpectedSalesModel.load(saved)
