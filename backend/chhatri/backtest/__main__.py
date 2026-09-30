"""``python -m chhatri.backtest``: run the SPEC §18 backtest and write its artefacts (decision B6).

Writes ``backend/artifacts/backtest/report.json``, ``report.md`` and ``backend/artifacts/premiums.json``
(or under ``--artifacts-dir``), using the calibration in ``artifacts/calibration.json`` (defaults when
absent, SPEC §24.1). Exit status 0 on success, 1 on failure (the error is logged with its traceback).
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from chhatri.backtest.run import run_backtest
from chhatri.config import BACKEND_DIR, Settings
from chhatri.sim.calibration import load_calibration

logger = logging.getLogger("chhatri.backtest")

DEFAULT_ARTIFACTS: Final = BACKEND_DIR / "artifacts"
LOG_FORMAT: Final = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m chhatri.backtest", description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS, help="output directory")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings()
    logging.basicConfig(level=settings.chhatri_log_level, format=LOG_FORMAT)
    try:
        calibration = load_calibration(settings.chhatri_data_dir, artifacts_dir=args.artifacts_dir)
        report = run_backtest(args.artifacts_dir, settings=settings, calibration=calibration)
    except Exception:
        logger.exception("backtest failed")
        return 1
    chhatri, weather = report["triggers"]
    logger.info(
        "recall %.2f vs %.2f; payouts with no real drop %d vs %d",
        chhatri["recall"],
        weather["recall"],
        chhatri["payouts_no_real_drop"],
        weather["payouts_no_real_drop"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
