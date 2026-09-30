"""SQLite connections for append-only tables (SPEC §1 store/db.py, used by the audit log §11)."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

MEMORY: Final = ":memory:"


def connect(path: Path | None) -> sqlite3.Connection:
    """Open a SQLite connection usable from any thread (callers serialise access with a lock).

    `None` gives a private in-memory database. A file path must have an existing parent directory;
    sqlite errors propagate after being logged (no silent fallback to memory).
    """
    target = MEMORY if path is None else str(path)
    try:
        conn = sqlite3.connect(target, check_same_thread=False)
    except sqlite3.Error:
        logger.exception("cannot open SQLite database at %s", target)
        raise
    conn.row_factory = sqlite3.Row
    return conn
