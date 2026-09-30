"""The `make data` steps and their idempotency (SPEC §23, B6)."""

from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path

import pytest

from chhatri.forecast.model import ExpectedSalesModel
from chhatri.pipeline import steps as st
from chhatri.pipeline.calibration_io import write_calibration
from chhatri.pipeline.calibration_run import CalibrationRun
from chhatri.pipeline.errors import PipelineError
from chhatri.pipeline.golden import MonsoonReport
from chhatri.pipeline.steps import STEPS, Options, State, initial_state, run_steps
from chhatri.pipeline.world import World, training_history
from chhatri.sim.types import Calibration
from tests.pipeline.conftest import SMALL_TARGETS, small_config


def test_options_normalise_and_validate() -> None:
    assert Options(steps=("manifest", "geo")).steps == ("geo", "manifest")
    assert Options().steps == STEPS
    for bad in ((), ("geo", "bogus")):
        with pytest.raises(ValueError):
            Options(steps=bad)
    with pytest.raises(ValueError, match="recalibrate"):
        Options(steps=("model",), recalibrate=True)


def test_initial_state_reads_calibration_and_backtest_inputs(artifacts: Path) -> None:
    config = small_config(artifacts)
    assert initial_state(config, Options()).calibration == Calibration()
    tuned = Calibration(anil_base_day_paise=500_000)
    write_calibration(config.calibration_path, tuned)
    (artifacts / "MANIFEST.json").write_text(json.dumps({"backtest_inputs": "abc"}))
    state = initial_state(config, Options())
    assert state.calibration == tuned and state.backtest_inputs == "abc"
    assert initial_state(config, Options(recalibrate=True)).calibration == Calibration()
    (artifacts / "MANIFEST.json").write_text(json.dumps({"backtest_inputs": 3}))
    assert initial_state(config, Options()).backtest_inputs is None


def test_geo_step_refuses_the_small_city(artifacts: Path) -> None:
    with pytest.raises(PipelineError, match="full"):
        st.step_geo(initial_state(small_config(artifacts), Options(steps=("geo",))))


def test_geo_step_writes_into_the_data_dir(tmp_path: Path, world: World) -> None:
    config = dataclasses.replace(small_config(tmp_path / "a"), scale="full", data_dir=tmp_path)
    state = State(config, Options(steps=("geo",)), Calibration(), world=world)
    after = st.step_geo(state)
    assert after.world is world
    assert (tmp_path / "zones.json").exists() and (tmp_path / "geo" / "hexes.geojson").exists()


def test_city_step_checks_the_pilot_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = dataclasses.replace(small_config(tmp_path), scale="full")
    state = st.step_city(initial_state(config, Options(steps=("city",))))
    assert state.world is not None and len(state.world.city.merchants) == 1821
    monkeypatch.setattr(st, "PILOT_SHOPS_FULL", {"Z7": 45})
    with pytest.raises(PipelineError, match="pilot counts"):
        st.step_city(state)


def test_history_and_model_steps_reuse_earlier_work(
    artifacts: Path, world: World, model: ExpectedSalesModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = small_config(artifacts)
    calls: list[object] = []
    monkeypatch.setattr(
        st, "ensure_model", lambda c, *, history, force: calls.append((history, force)) or model
    )
    calibrated = Calibration(anil_base_day_paise=505_000)
    state = st.step_history(State(config, Options(force=True), calibrated))
    assert state.history is not None and state.history.panel.start.date() == state.history.first_day
    assert state.history.digest == training_history(world, config).digest  # the uncalibrated city
    state = st.step_model(state)
    assert calls == [(state.history, True)] and state.model is model


def test_calibrate_step_writes_the_converged_calibration(
    artifacts: Path, model: ExpectedSalesModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = small_config(artifacts)
    tuned = Calibration(anil_base_day_paise=505_000)
    seen: dict[str, object] = {}

    def fake_run(config, start, *, model, rules, targets):
        seen.update(start=start, model=model, targets=targets)
        return CalibrationRun(tuned, model, 2, MonsoonReport((), (), 0))

    monkeypatch.setattr(st, "run_calibration", fake_run)
    monkeypatch.setattr(st, "ensure_model", lambda c: model)
    options = Options(steps=("calibrate",), targets=SMALL_TARGETS)
    state = st.step_calibrate(initial_state(config, options))
    assert seen == {"start": Calibration(), "model": model, "targets": SMALL_TARGETS}
    assert state.calibration == tuned and state.model is model and state.world is None
    assert json.loads(config.calibration_path.read_text())["anil_base_day_paise"] == 505_000
    other = object()
    st.step_calibrate(dataclasses.replace(initial_state(config, options), model=other))  # type: ignore[arg-type]
    assert seen["model"] is other  # the model step's model is reused


def _fake_backtest(calls: list[Calibration], write: bool = True):
    def run_backtest(artifacts_dir: Path, *, settings, calibration: Calibration) -> dict:
        calls.append(calibration)
        if write:
            (artifacts_dir / "backtest").mkdir(exist_ok=True)
            for rel in st.BACKTEST_OUTPUTS:
                (artifacts_dir / rel).write_text("{}")
        return {}

    return run_backtest


def test_backtest_step_runs_once_per_calibration(artifacts: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import chhatri.backtest

    calls: list[Calibration] = []
    monkeypatch.setattr(chhatri.backtest, "run_backtest", _fake_backtest(calls))
    state = initial_state(small_config(artifacts), Options(steps=("backtest",)))
    state = st.step_backtest(state)
    assert calls == [Calibration()] and state.backtest_inputs == st.backtest_inputs(state)
    assert st.step_backtest(state) is state and len(calls) == 1
    forced = dataclasses.replace(state, options=Options(steps=("backtest",), force=True))
    st.step_backtest(forced)
    assert len(calls) == 2
    other = dataclasses.replace(state, calibration=Calibration(anil_base_day_paise=1))
    assert st.backtest_inputs(other) != st.backtest_inputs(state)


def test_backtest_step_fails_without_outputs(artifacts: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import chhatri.backtest

    monkeypatch.setattr(chhatri.backtest, "run_backtest", _fake_backtest([], write=False))
    with pytest.raises(PipelineError, match="without writing"):
        st.step_backtest(initial_state(small_config(artifacts), Options(steps=("backtest",))))


def test_manifest_step(
    artifacts: Path, config, model: ExpectedSalesModel, caplog: pytest.LogCaptureFixture
) -> None:
    empty = small_config(artifacts)
    with caplog.at_level(logging.WARNING):
        st.step_manifest(initial_state(empty, Options(steps=("manifest",))))
    assert "MANIFEST model is null" in caplog.text
    assert json.loads(empty.manifest_path.read_text())["model"] is None
    with_model = dataclasses.replace(empty, artifacts_dir=config.artifacts_dir)
    st.step_manifest(initial_state(with_model, Options(steps=("manifest",))))
    document = json.loads(with_model.manifest_path.read_text())
    assert document["model"]["train_end"] == "2025-08-18"
    assert "model/p50.txt" in document["artifacts"]
    in_memory = State(empty, Options(steps=("manifest",)), Calibration(), model=model)
    st.step_manifest(in_memory)
    assert json.loads(empty.manifest_path.read_text())["model"]["rows_train"] == model.manifest.rows_train


def test_run_steps_runs_in_order_and_logs_durations(
    artifacts: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    order: list[str] = []
    fake = {name: (lambda s, name=name: order.append(name) or s) for name in STEPS}
    monkeypatch.setattr(st, "STEP_FUNCTIONS", fake)
    ticks = iter(range(100))
    state = initial_state(small_config(artifacts), Options(steps=("manifest", "city", "model")))
    with caplog.at_level(logging.INFO):
        run_steps(state, lambda: float(next(ticks)))
    assert order == ["city", "model", "manifest"]
    assert "step city: done in 1.0 s" in caplog.text
    assert "pipeline done in" in caplog.text
