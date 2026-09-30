#!/usr/bin/env python3
"""`make data` (SPEC §23): geo → city → history → model → calibrate → backtest → MANIFEST.json.

Thin entry point; the steps live in `chhatri.pipeline`. See `python scripts/build_data.py --help`.
"""

from __future__ import annotations

from chhatri.pipeline.cli import build_data_main

if __name__ == "__main__":
    raise SystemExit(build_data_main())
