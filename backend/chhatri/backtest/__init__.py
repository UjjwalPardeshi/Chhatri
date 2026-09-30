"""Backtest of two past monsoons: Chhatri's trigger vs a weather-only trigger (SPEC §18).

Public entry point: `run_backtest(artifacts_dir, *, settings, calibration)`; command line:
``python -m chhatri.backtest``.
"""

from chhatri.backtest.run import run_backtest

__all__ = ["run_backtest"]
