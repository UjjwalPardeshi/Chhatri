"""CLI entry point for backtest (SPEC §24.6).

Usage: python -m chhatri.backtest
"""

import asyncio
import logging
import sys
from pathlib import Path

from chhatri.backtest.run import run_backtest
from chhatri.config import Settings
from chhatri.sim.calibration import load_calibration

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    """Run backtest on historical monsoon seasons.

    Returns:
        Exit code (0 on success, 1 on error)
    """
    try:
        settings = Settings()
        calibration = load_calibration(Path(settings.data_dir))
        artifacts_dir = Path(settings.artifacts_dir)

        logger.info(f"Running backtest on {artifacts_dir}")
        report = run_backtest(artifacts_dir, settings=settings, calibration=calibration)

        logger.info(f"Backtest complete")
        logger.info(f"  Seasons: {', '.join(report['seasons'])}")
        logger.info(f"  Triggers: {len(report['triggers'])}")
        logger.info(f"  Zones: {len(report['zones'])}")

        return 0
    except Exception as e:
        logger.exception(f"Backtest failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
