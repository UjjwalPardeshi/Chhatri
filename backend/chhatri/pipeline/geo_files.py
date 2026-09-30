"""The committed geography files, written by the pipeline's geo step (SPEC §5.1, §5.2, §23).

The file contents come from `chhatri.sim.geo_export.geo_files`, the same function
``scripts/build_geo.py`` uses, so both write byte-identical ``data/zones.json``,
``data/geo/zones.geojson`` and ``data/geo/hexes.geojson``. Shop counts do not depend on the
calibration (it only changes sales levels), so any full city of the seed gives the same files.
Only files whose text changes are rewritten, unless forced.
"""

from __future__ import annotations

import logging
from pathlib import Path

from chhatri.sim.geo_export import geo_files
from chhatri.sim.types import City

__all__ = ["sync_geo_files"]

logger = logging.getLogger(__name__)


def sync_geo_files(city: City, data_dir: Path, *, force: bool = False) -> tuple[Path, ...]:
    """Write the geo files of `city` under `data_dir`; returns the paths actually written."""
    written: list[Path] = []
    for rel, text in geo_files(city).items():
        path = data_dir / rel
        if not force and path.exists() and path.read_text(encoding="utf-8") == text:
            logger.info("geo file unchanged: %s", path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        logger.info("wrote %s (%d bytes)", path, len(text.encode("utf-8")))
        written.append(path)
    return tuple(written)
