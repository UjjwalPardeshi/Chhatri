"""The `make data` steps: geo → city → history → model → calibrate → backtest → manifest (SPEC §23).

Steps always run in that order; each takes and returns an immutable `State`, building whatever an
earlier (possibly unselected) step would have provided. Every step is idempotent: an artefact that
is up to date with its inputs is left alone unless ``force`` is set.

- geo: the committed geography files (`sync_geo_files`), full city only.
- city: the calibrated full city and the monsoon world; checks the SPEC §5.1 pilot shop counts.
- history: the replay model's training history — the uncalibrated city's monsoon world
  (`training_world`), in memory only (`training_history`).
- model: ``artifacts/model`` via `ensure_model` (retrained only when its inputs changed).
- calibrate: the SPEC §17.4 fixed point under that model (`run_calibration`), then
  ``artifacts/calibration.json``. The calibration never changes the model's training history
  (`chhatri.pipeline.world` explains why), so it needs no retraining.
- backtest: ``chhatri.backtest.run_backtest`` (imported lazily, B6); skipped when the manifest says
  it already ran with this calibration and its outputs exist.
- manifest: ``artifacts/MANIFEST.json`` (`build_manifest`, rewritten only on change).

The starting calibration is ``calibration.json`` (defaults when absent), or the `Calibration()`
defaults with ``recalibrate``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from chhatri.config import Settings
from chhatri.forecast.manifest import ModelManifest
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.pipeline.calibration_io import calibration_text, write_calibration
from chhatri.pipeline.calibration_run import run_calibration
from chhatri.pipeline.config import PipelineConfig
from chhatri.pipeline.errors import PipelineError
from chhatri.pipeline.geo_files import sync_geo_files
from chhatri.pipeline.manifest import build_manifest, git_commit, read_manifest, write_manifest
from chhatri.pipeline.model_store import ensure_model
from chhatri.pipeline.targets import SPEC_TARGETS, Targets
from chhatri.pipeline.world import TrainingHistory, World, build_world, training_history, training_world
from chhatri.policy.rules import default_rules
from chhatri.sim.calibration import load_calibration
from chhatri.sim.city import PILOT_SHOPS_FULL, RAMESH_ID
from chhatri.sim.types import Calibration

__all__ = ["BACKTEST_OUTPUTS", "STEPS", "Options", "State", "Step", "initial_state", "run_steps"]

logger = logging.getLogger(__name__)

STEPS: Final = ("geo", "city", "history", "model", "calibrate", "backtest", "manifest")
BACKTEST_OUTPUTS: Final = ("backtest/report.json", "backtest/report.md", "premiums.json")  # B6


@dataclass(frozen=True, slots=True)
class Options:
    """Which steps to run and how (see `chhatri.pipeline.cli`)."""

    steps: tuple[str, ...] = STEPS
    force: bool = False
    recalibrate: bool = False
    targets: Targets = SPEC_TARGETS  # the pipeline's own tests calibrate the small city to others

    def __post_init__(self) -> None:
        unknown = [s for s in self.steps if s not in STEPS]
        if unknown or not self.steps:
            raise ValueError(f"unknown or no steps {unknown}; choose from {STEPS}")
        if self.recalibrate and "calibrate" not in self.steps:
            raise ValueError(
                "recalibrate needs the calibrate step (the model would not match calibration.json)"
            )
        object.__setattr__(self, "steps", tuple(s for s in STEPS if s in self.steps))


@dataclass(frozen=True, slots=True)
class State:
    """What earlier steps produced; None until built."""

    config: PipelineConfig
    options: Options
    calibration: Calibration
    world: World | None = None  # the monsoon world of `calibration`
    history: TrainingHistory | None = None  # the uncalibrated city's training history
    model: ExpectedSalesModel | None = None
    backtest_inputs: str | None = None


def initial_state(config: PipelineConfig, options: Options) -> State:
    if options.recalibrate:
        calibration = Calibration()
    else:
        calibration = load_calibration(config.data_dir, artifacts_dir=config.artifacts_dir)
    previous = read_manifest(config.manifest_path) or {}
    inputs = previous.get("backtest_inputs")
    return State(config, options, calibration, backtest_inputs=inputs if isinstance(inputs, str) else None)


def _world(state: State) -> World:
    return state.world if state.world is not None else build_world(state.config, state.calibration)


def _history(state: State) -> TrainingHistory:
    if state.history is not None:
        return state.history
    return training_history(training_world(state.config), state.config)


def step_geo(state: State) -> State:
    if state.config.scale != "full":
        raise PipelineError("the geo step writes the committed full-city files; use scale 'full'")
    world = _world(state)
    written = sync_geo_files(world.city, state.config.data_dir, force=state.options.force)
    logger.info("geo: %d file(s) written", len(written))
    return dataclasses.replace(state, world=world)


def step_city(state: State) -> State:
    world = _world(state)
    city = world.city
    covered = {z.id: sum(1 for m in city.merchants_in_zone(z.id) if m.id in city.covers) for z in city.zones}
    if state.config.scale == "full":
        wrong = {z: covered.get(z) for z, n in PILOT_SHOPS_FULL.items() if covered.get(z) != n}
        if wrong or RAMESH_ID in city.covers:
            raise PipelineError(
                f"city breaks SPEC §5.1/§5.4: pilot counts {wrong}, Ramesh covered={RAMESH_ID in city.covers}"
            )
    pilot = {z: covered.get(z) for z in PILOT_SHOPS_FULL}
    logger.info(
        "city: %d merchants, %d covered, pilot zones %s", len(city.merchants), len(city.covers), pilot
    )
    return dataclasses.replace(state, world=world)


def step_history(state: State) -> State:
    return dataclasses.replace(state, history=_history(state))


def step_model(state: State) -> State:
    history = _history(state)
    model = ensure_model(state.config, history=history, force=state.options.force)
    return dataclasses.replace(state, history=history, model=model)


def step_calibrate(state: State) -> State:
    config = state.config
    model = state.model if state.model is not None else ensure_model(config)
    run = run_calibration(
        config, state.calibration, model=model, rules=default_rules(), targets=state.options.targets
    )
    write_calibration(config.calibration_path, run.calibration)
    logger.info("calibrate: converged in %d pass(es): %s", run.passes, calibration_text(run.calibration))
    return dataclasses.replace(state, calibration=run.calibration, world=None, model=run.model)


def backtest_inputs(state: State) -> str:
    """Digest of what the backtest depends on from this pipeline: seed and calibration."""
    return hashlib.sha256(f"{state.config.seed}\n{calibration_text(state.calibration)}".encode()).hexdigest()


def step_backtest(state: State) -> State:
    config, inputs = state.config, backtest_inputs(state)
    outputs = [config.artifacts_dir / rel for rel in BACKTEST_OUTPUTS]
    if not state.options.force and state.backtest_inputs == inputs and all(p.exists() for p in outputs):
        logger.info("backtest up to date for this calibration; skipped")
        return state
    from chhatri.backtest import run_backtest  # lazy: the backtest package is optional here (B6)

    settings = Settings(chhatri_seed=config.seed, chhatri_data_dir=config.data_dir)
    run_backtest(config.artifacts_dir, settings=settings, calibration=state.calibration)
    missing = [str(p) for p in outputs if not p.exists()]
    if missing:
        raise PipelineError(f"backtest finished without writing {missing}")
    return dataclasses.replace(state, backtest_inputs=inputs)


def _model_manifest(state: State) -> ModelManifest | None:
    if state.model is not None:
        return state.model.manifest
    if not state.config.model_dir.exists():
        logger.warning("no replay model in %s; MANIFEST model is null", state.config.model_dir)
        return None
    return ExpectedSalesModel.load(state.config.model_dir).manifest


def step_manifest(state: State) -> State:
    document = build_manifest(
        state.config,
        state.calibration,
        _model_manifest(state),
        backtest_inputs=state.backtest_inputs,
        commit=git_commit(),
    )
    write_manifest(state.config.manifest_path, document, force=state.options.force)
    return state


Step = Callable[[State], State]
STEP_FUNCTIONS: Mapping[str, Step] = MappingProxyType(
    {
        "geo": step_geo,
        "city": step_city,
        "history": step_history,
        "model": step_model,
        "calibrate": step_calibrate,
        "backtest": step_backtest,
        "manifest": step_manifest,
    }
)
if tuple(STEP_FUNCTIONS) != STEPS:
    raise RuntimeError("every step needs exactly one function, in pipeline order")


def run_steps(state: State, clock: Callable[[], float]) -> State:
    """Run the selected steps in order, logging each one's duration (`clock` returns seconds)."""
    started = clock()
    for name in state.options.steps:
        begin = clock()
        logger.info("step %s: start", name)
        state = STEP_FUNCTIONS[name](state)
        logger.info("step %s: done in %.1f s", name, clock() - begin)
    logger.info("pipeline done in %.1f s (%s)", clock() - started, ", ".join(state.options.steps))
    return state
