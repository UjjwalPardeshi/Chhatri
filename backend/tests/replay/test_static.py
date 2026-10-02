"""load_static: artefacts present, missing or wrong (SPEC §19 preflight, §24.6; decision B6)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from chhatri.config import Settings
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.integrations.free_tier import free_tier_gate_detail
from chhatri.replay import static as static_module
from chhatri.replay.preflight import preflight_rows
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


def test_pilot_covers_are_seeded_at_the_zone_price(artefacts: Path, settings: Settings) -> None:
    """K6-T04: a pilot cover pays its zone's price (Anil, Z7), not the ₹2 minimum; an unpriced zone keeps the floor."""
    static = load_static(settings, artifacts_dir=artefacts, scale="small")
    prices = {"Z7": 2068, "Z3": 1420}
    floor = static.rules.premium.min_per_day_rupees * 100
    covers = static.city.covers
    assert covers["S-0142"].premium_per_day_paise == 2068
    for merchant_id, cover in covers.items():
        zone = static.city.merchant(merchant_id).zone_id
        assert cover.premium_per_day_paise == prices.get(zone, floor), (merchant_id, zone)
    assert any(static.city.merchant(m).zone_id == "Z3" for m in covers), (
        "the check covers a second priced zone"
    )
    bare = load_static(settings, artifacts_dir=artefacts.parent / "no-such-artefacts", scale="small")
    assert {c.premium_per_day_paise for c in bare.city.covers.values()} == {floor}


def test_missing_artefacts_do_not_crash_startup(tmp_path: Path, settings: Settings) -> None:
    static = load_static(settings, artifacts_dir=tmp_path, scale="small")
    assert static.model is None
    assert static.model_error is not None and "make data" in static.model_error
    assert static.backtest_report is None
    assert dict(static.premiums) == {}  # no file, no prices: a cover quote for any zone fails (X3)
    assert static.zones_without_premium == tuple(z.id for z in static.city.zones)


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


def listed_zones(detail: str) -> list[str]:
    """The zone ids a premiums row names after "no premium for zones"."""
    return detail.split("no premium for zones ")[1].split(";")[0].split(", ")


def test_preflight_lists_zones_without_a_price(artefacts: Path, settings: Settings) -> None:
    """X3: the artefacts price Z7 and Z3 only, so every other city zone has no price and the row says so."""
    static = load_static(settings, artifacts_dir=artefacts, scale="small")
    every = [zone.id for zone in static.city.zones]
    assert static.zones_without_premium == tuple(zone for zone in every if zone not in ("Z3", "Z7"))
    row = next(r for r in preflight_rows(static, None) if r["name"] == "premiums")
    assert row["ok"] is False
    listed = listed_zones(row["detail"])
    assert listed == list(static.zones_without_premium)
    assert "Z9" in listed and "Z12" in listed and "Z7" not in listed and "Z3" not in listed


def test_preflight_says_the_file_is_missing_and_lists_every_zone(tmp_path: Path, settings: Settings) -> None:
    static = load_static(settings, artifacts_dir=tmp_path, scale="small")
    row = next(r for r in preflight_rows(static, None) if r["name"] == "premiums")
    assert row["ok"] is False
    assert "premiums.json missing" in row["detail"]
    assert listed_zones(row["detail"]) == [zone.id for zone in static.city.zones]


def test_preflight_premiums_row_is_ok_when_every_zone_has_a_price(static: StaticContext) -> None:
    priced = replace(static, premiums=MappingProxyType({zone.id: 300 for zone in static.city.zones}))
    assert priced.zones_without_premium == ()
    row = next(r for r in preflight_rows(priced, None) if r["name"] == "premiums")
    assert row == {"name": "premiums", "ok": True, "detail": "24 zone premiums loaded"}


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


@pytest.mark.parametrize("synthetic", [True, False])
def test_preflight_shows_the_free_tier_data_gate(static: StaticContext, synthetic: bool) -> None:
    """ADR 0009 section 3: the gate state is a preflight row. A closed gate is safe, so the row is ok either way."""
    settings = static.settings.model_copy(update={"chhatri_data_is_synthetic": synthetic})
    gated = replace(static, settings=settings)
    row = next(r for r in preflight_rows(gated, None) if r["name"] == "free_tier_gate")
    assert row == {"name": "free_tier_gate", "ok": True, "detail": free_tier_gate_detail(settings)}
    assert ("CHHATRI_DATA_IS_SYNTHETIC=true" in row["detail"]) is synthetic
