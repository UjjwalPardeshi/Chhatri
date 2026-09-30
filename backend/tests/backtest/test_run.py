"""End-to-end backtest on the small city (SPEC §18): shape, outputs, consistency, determinism."""

from __future__ import annotations

import dataclasses
import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from chhatri.api.schemas import BacktestReport
from chhatri.backtest.config import REPORT_LABEL
from chhatri.backtest.report import PREMIUMS_JSON, REPORT_DIR, REPORT_JSON, REPORT_MD
from chhatri.backtest.run import run_backtest
from chhatri.backtest.world import World
from chhatri.config import Settings
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.ledger.premium_table import load_premiums
from chhatri.money import format_inr
from chhatri.policy.rules import PolicyRules
from chhatri.sim.types import Calibration
from tests.backtest.conftest import TEST_CONFIG, TEST_SEASON


def test_report_validates_against_the_spec_schema(report: dict[str, Any]) -> None:
    BacktestReport.model_validate(report)
    assert report["label"] == REPORT_LABEL
    assert report["seasons"] == [TEST_SEASON.label]
    assert report["generated_at"] == "2024-07-22T00:00:00+05:30"


def test_both_triggers_see_the_same_real_drops(report: dict[str, Any]) -> None:
    chhatri, weather = report["triggers"]
    assert chhatri["real_drops"] == weather["real_drops"]
    for trigger in (chhatri, weather):
        assert trigger["real_drops_paid"] + trigger["payouts_no_real_drop"] == trigger["payouts"]
        assert trigger["real_drops_paid"] <= trigger["real_drops"]
        assert trigger["documents_per_area_claim"] == 0
    assert chhatri["payouts"] > 0 and chhatri["paid_paise"] > 0
    assert weather["payouts"] > 0 and weather["paid_paise"] > 0
    assert chhatri["trigger_to_money"].startswith("same day")
    assert weather["trigger_to_money"].startswith("next day")


def test_zones_price_every_zone_and_pay_what_chhatri_paid(
    report: dict[str, Any], run_dir: Path, rules: PolicyRules
) -> None:
    zones = report["zones"]
    assert [z["zone_id"] for z in zones] == [f"Z{i}" for i in range(1, 25)]
    chhatri = report["triggers"][0]
    assert sum(z["payouts_paise"] for z in zones) == chhatri["paid_paise"]
    assert sum(z["chhatri_fp"] for z in zones) == chhatri["payouts_no_real_drop"]
    assert sum(z["chhatri_fn"] for z in zones) == chhatri["real_drops"] - chhatri["real_drops_paid"]
    premiums = load_premiums(rules, run_dir / PREMIUMS_JSON)
    assert list(premiums) == sorted(premiums) and len(premiums) == 24
    for zone in zones:
        assert zone["premium_per_day_label"] == format_inr(premiums[zone["zone_id"]])
        if zone["premiums_paise"]:
            assert zone["loss_ratio"] <= 1 - rules.premium.loading + 0.001  # in-sample, loaded premium
    assert {z["zone_id"] for z in zones if z["premiums_paise"]} == {"Z3", "Z7", "Z9", "Z12"}


def test_personal_claims_are_counted(report: dict[str, Any]) -> None:
    personal = report["personal"]
    assert personal["claims"] > 0
    assert personal["auto_paid"] + personal["referred"] <= personal["claims"]
    assert personal["referred"] > 0  # a closure longer than max_auto_days reaches a human


def test_outputs_are_written(report: dict[str, Any], run_dir: Path) -> None:
    written = json.loads((run_dir / REPORT_DIR / REPORT_JSON).read_text(encoding="utf-8"))
    assert written == report
    assert (run_dir / REPORT_DIR / REPORT_MD).read_text(encoding="utf-8").startswith("# Chhatri backtest")


def test_same_seed_gives_byte_identical_outputs(
    report: dict[str, Any], run_dir: Path, tmp_path: Path, settings: Settings
) -> None:
    """A run that builds its own world and trains its own model matches the shared-fixture run."""
    again = run_backtest(tmp_path, settings=settings, calibration=Calibration(), config=TEST_CONFIG)
    assert again == report
    for name in (f"{REPORT_DIR}/{REPORT_JSON}", f"{REPORT_DIR}/{REPORT_MD}", PREMIUMS_JSON):
        assert (tmp_path / name).read_bytes() == (run_dir / name).read_bytes()


def test_reused_inputs_must_match_the_configuration(
    tmp_path: Path, settings: Settings, world: World, model: ExpectedSalesModel
) -> None:
    kwargs: dict[str, Any] = {"settings": settings, "calibration": Calibration(), "config": TEST_CONFIG}
    other_seed = settings.model_copy(update={"chhatri_seed": settings.chhatri_seed + 1})
    with pytest.raises(ValueError, match="seed"):
        run_backtest(tmp_path, **{**kwargs, "settings": other_seed}, world=world)
    shorter = dataclasses.replace(TEST_SEASON, end=TEST_SEASON.end - timedelta(days=1))
    shifted = dataclasses.replace(TEST_CONFIG, seasons=(shorter,))
    with pytest.raises(ValueError, match="does not span"):
        run_backtest(tmp_path, **{**kwargs, "config": shifted}, world=world)
    with pytest.raises(ValueError, match="model trained"):
        run_backtest(tmp_path, **kwargs, world=world, models={TEST_SEASON: _relabelled(model, seed=1)})
    assert not list(tmp_path.iterdir())  # nothing written when the inputs are refused


def _relabelled(model: ExpectedSalesModel, *, seed: int) -> ExpectedSalesModel:
    """A stand-in whose manifest says it was trained with another seed."""
    return cast(ExpectedSalesModel, SimpleNamespace(manifest=dataclasses.replace(model.manifest, seed=seed)))
