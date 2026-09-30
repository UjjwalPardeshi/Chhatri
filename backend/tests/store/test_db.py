"""store/db.py SQLite connection helper (SPEC §1, §11)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from chhatri.store.db import connect


def test_memory_connection_uses_row_factory() -> None:
    conn = connect(None)
    row = conn.execute("SELECT 1 AS one").fetchone()
    assert row["one"] == 1


def test_file_connection(tmp_path: Path) -> None:
    conn = connect(tmp_path / "a.db")
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.commit()
    assert (tmp_path / "a.db").exists()


def test_missing_parent_raises(tmp_path: Path) -> None:
    with pytest.raises(sqlite3.OperationalError):
        connect(tmp_path / "missing" / "a.db")
