"""Hand-written, synthetic labelled sets (plan section 6.2) and their hashes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Final

__all__ = ["FIXTURE_DIR", "HELD_OUT_FILES", "file_sha256", "held_out_hashes", "load_rows", "select_split"]

FIXTURE_DIR: Final = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "evals"
HELD_OUT_FILES: Final = ("intents.jsonl", "guard.jsonl", "ask.jsonl")
SPLITS: Final = ("held_out", "dev", "all")


def load_rows(name: str, directory: Path = FIXTURE_DIR) -> list[dict[str, Any]]:
    """The rows of one JSONL set. Every row must be marked synthetic (plan section 6.2)."""
    rows = [
        json.loads(line)
        for line in (directory / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for row in rows:
        if row.get("synthetic") is not True:
            raise ValueError(f"{name}: row {row.get('id')} is not marked synthetic")
        if row.get("split") not in ("held_out", "dev"):
            raise ValueError(f"{name}: row {row.get('id')} has no split")
    return rows


def select_split(rows: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}")
    return rows if split == "all" else [r for r in rows if r["split"] == split]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def held_out_hashes(directory: Path = FIXTURE_DIR) -> dict[str, str]:
    """One SHA-256 per held-out file, so a change after a run is visible (AC-EVAL-07)."""
    return {name: file_sha256(directory / name) for name in HELD_OUT_FILES if (directory / name).exists()}
