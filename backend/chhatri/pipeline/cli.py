"""Command lines behind ``scripts/build_data.py`` (`make data`) and ``scripts/calibrate.py`` (SPEC §23).

``build_data.py [--steps a,b,...] [--force] [--skip-backtest] [--recalibrate]`` runs the pipeline
steps of `chhatri.pipeline.steps` in their fixed order and logs each step's duration.
``calibrate.py [--recalibrate]`` runs the calibrate and manifest steps only (training the model
first when it is missing or stale). Both accept ``--seed``, ``--data-dir`` and ``--artifacts-dir``
(default: `Settings` and ``backend/artifacts``, B6) and exit 0 on success, 1 on any failure (with
the error logged), 2 on bad arguments.
"""

from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from chhatri.config import Settings
from chhatri.pipeline.config import ARTIFACTS_DIR, PipelineConfig
from chhatri.pipeline.steps import STEPS, Options, initial_state, run_steps

__all__ = ["build_data_main", "calibrate_main", "parse_steps"]

logger = logging.getLogger(__name__)

LOG_FORMAT: Final = "%(asctime)s %(levelname)s %(name)s: %(message)s"
EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
CALIBRATE_STEPS: Final = ("calibrate", "manifest")
SKIPPABLE: Final = "backtest"


def parse_steps(text: str, *, skip_backtest: bool) -> tuple[str, ...]:
    """Comma-separated step names -> the selected steps (ValueError on unknown names)."""
    names = [s.strip() for s in text.split(",") if s.strip()]
    unknown = [s for s in names if s not in STEPS]
    if unknown:
        raise ValueError(f"unknown step(s) {unknown}; choose from {', '.join(STEPS)}")
    return tuple(s for s in names if not (skip_backtest and s == SKIPPABLE))


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--recalibrate", action="store_true", help="start calibration from the defaults")
    parser.add_argument("--seed", type=int, default=None, help="simulation seed (default: CHHATRI_SEED)")
    parser.add_argument("--data-dir", type=Path, default=None, help="input data directory")
    parser.add_argument("--artifacts-dir", type=Path, default=ARTIFACTS_DIR, help="artefacts directory")


def _config(args: argparse.Namespace) -> PipelineConfig:
    settings = Settings()
    return PipelineConfig(
        seed=settings.chhatri_seed if args.seed is None else args.seed,
        data_dir=settings.chhatri_data_dir if args.data_dir is None else args.data_dir,
        artifacts_dir=args.artifacts_dir,
    )


def _run(config: PipelineConfig, options: Options) -> int:
    try:
        run_steps(initial_state(config, options), time.perf_counter)
    except Exception:
        logger.exception("data pipeline failed")
        return EXIT_FAILED
    return EXIT_OK


def build_data_main(argv: Sequence[str] | None = None) -> int:
    """`make data`: geo → city → history → model → calibrate → backtest → manifest."""
    parser = argparse.ArgumentParser(
        prog="build_data.py", description="Build the Chhatri artefacts (SPEC §23)"
    )
    parser.add_argument(
        "--steps", default=",".join(STEPS), help=f"comma-separated subset of {','.join(STEPS)}"
    )
    parser.add_argument("--force", action="store_true", help="rebuild artefacts even when up to date")
    parser.add_argument("--skip-backtest", action="store_true", help="leave out the backtest step")
    _common(parser)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    try:
        options = Options(
            steps=parse_steps(args.steps, skip_backtest=args.skip_backtest),
            force=args.force,
            recalibrate=args.recalibrate,
        )
    except ValueError as exc:
        parser.error(str(exc))
    return _run(_config(args), options)


def calibrate_main(argv: Sequence[str] | None = None) -> int:
    """SPEC §17.4 calibration only (then the manifest)."""
    parser = argparse.ArgumentParser(prog="calibrate.py", description="SPEC §17.4 calibration")
    _common(parser)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    return _run(_config(args), Options(steps=CALIBRATE_STEPS, recalibrate=args.recalibrate))
