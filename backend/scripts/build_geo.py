#!/usr/bin/env python3
"""Build the committed geography files (SPEC §5.1, §5.2): data/zones.json, data/geo/zones.geojson
and data/geo/hexes.geojson. Deterministic: re-running with the same seed is byte-identical.
The logic lives in `chhatri.sim.geo_export` so the data pipeline writes the same bytes.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from chhatri.config import DATA_DIR, Settings
from chhatri.sim.geo_export import write_geo_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build zones.json, zones.geojson and hexes.geojson")
    parser.add_argument("--seed", type=int, default=Settings().chhatri_seed)
    parser.add_argument(
        "--data-dir", type=Path, default=DATA_DIR, help="directory with geo/bmc_wards.geojson"
    )
    parser.add_argument("--out", type=Path, default=None, help="output data directory (default: --data-dir)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    write_geo_files(args.seed, args.data_dir, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
