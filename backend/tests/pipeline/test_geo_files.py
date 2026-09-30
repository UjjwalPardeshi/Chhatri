"""The geo step writes the same bytes as scripts/build_geo.py, only when they change (SPEC §5.1, §5.2)."""

from __future__ import annotations

from pathlib import Path

from chhatri.config import DATA_DIR
from chhatri.pipeline.geo_files import sync_geo_files
from chhatri.pipeline.world import World
from chhatri.sim.geo_export import geo_files


def test_writes_missing_files_then_nothing(tmp_path: Path, world: World) -> None:
    written = sync_geo_files(world.city, tmp_path)
    expected = geo_files(world.city)
    assert sorted(p.relative_to(tmp_path) for p in written) == sorted(expected)
    for rel, text in expected.items():
        assert (tmp_path / rel).read_text(encoding="utf-8") == text
    assert sync_geo_files(world.city, tmp_path) == ()
    assert len(sync_geo_files(world.city, tmp_path, force=True)) == len(expected)


def test_rewrites_only_changed_files(tmp_path: Path, world: World) -> None:
    sync_geo_files(world.city, tmp_path)
    zones = tmp_path / "zones.json"
    zones.write_text("[]\n", encoding="utf-8")
    assert sync_geo_files(world.city, tmp_path) == (zones,)


def test_committed_files_match_the_full_city(tmp_path: Path) -> None:
    from chhatri.sim.city import build_city

    full = build_city(20251019, DATA_DIR, scale="full")
    for rel, text in geo_files(full).items():
        assert (DATA_DIR / rel).read_text(encoding="utf-8") == text, rel
