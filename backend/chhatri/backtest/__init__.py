"""Backtest module (SPEC §18, §19.2, §24.6).

Runs historical monsoon seasons on simulated sales with real Open-Meteo rainfall.
Compares Chhatri's trigger against weather-only baseline and computes premiums.
"""

from chhatri.backtest.run import run_backtest

__all__ = ["run_backtest"]
