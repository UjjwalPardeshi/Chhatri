#!/usr/bin/env python3
"""SPEC §17.4 calibration: writes backend/artifacts/calibration.json (and refreshes MANIFEST.json).

Thin entry point; the search lives in `chhatri.pipeline`. See `python scripts/calibrate.py --help`.
"""

from __future__ import annotations

from chhatri.pipeline.cli import calibrate_main

if __name__ == "__main__":
    raise SystemExit(calibrate_main())
