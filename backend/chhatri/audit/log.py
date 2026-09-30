"""Tamper-evident, append-only audit log on SQLite (SPEC §11, §24.3).

`hash = sha256(canonical_json({seq, at, actor, action, subject_type, subject_id, data, prev_hash}))`
with `canonical_json = json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False,
default=str)`. The genesis `prev_hash` is 64 zeros. `recorded_at` (wall clock) is stored but excluded
from the hash, so the same scenario yields the same chain (SPEC §0.2).

Implementation notes: `at` is normalised to IST and hashed as `str(at)` — exactly what
`default=str` produces — and stored as that same text; `data` is round-tripped through canonical
JSON so the returned entry, the stored row and the hashed value agree. SQLite triggers reject
UPDATE and DELETE so the table is append-only through normal use; `verify()` still detects rows
edited behind the triggers' back. Actors must be one of SPEC §11's forms.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import threading
from collections.abc import Iterator, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from chhatri.clock import IST, require_aware
from chhatri.domain.models import AuditEntry
from chhatri.store.db import connect

logger = logging.getLogger(__name__)

GENESIS_HASH: Final = "0" * 64
MAX_PAGE: Final = 5000
ACTOR_PATTERN: Final = re.compile(
    r"^(system|model|policy-engine|ai-agent)$|^(officer|merchant|workflow):[A-Za-z0-9][A-Za-z0-9._@-]{0,63}$"
)
_SCHEMA: Final = (
    """CREATE TABLE IF NOT EXISTS audit_entries (
        seq INTEGER PRIMARY KEY, at TEXT NOT NULL, recorded_at TEXT NOT NULL, actor TEXT NOT NULL,
        action TEXT NOT NULL, subject_type TEXT NOT NULL, subject_id TEXT NOT NULL,
        data TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL)""",
    """CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_entries
        BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END""",
    """CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_entries
        BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END""",
)
_INSERT: Final = (
    "INSERT INTO audit_entries (seq, at, recorded_at, actor, action, subject_type, subject_id, data, prev_hash, hash)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
_SELECT_ONE: Final = "SELECT * FROM audit_entries WHERE seq = ?"
_SELECT_PAGE: Final = "SELECT * FROM audit_entries WHERE seq > ? ORDER BY seq LIMIT ?"
_SELECT_ALL: Final = "SELECT * FROM audit_entries ORDER BY seq"


def canonical_json(value: Any) -> str:
    """SPEC §11 canonical JSON."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def entry_hash(
    *,
    seq: int,
    at: str,
    actor: str,
    action: str,
    subject_type: str,
    subject_id: str,
    data: Any,
    prev_hash: str,
) -> str:
    """sha256 over the hashed fields of one entry (SPEC §11); `at` is the stored `str(at)` text."""
    payload = {
        "seq": seq,
        "at": at,
        "actor": actor,
        "action": action,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "data": data,
        "prev_hash": prev_hash,
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _row_hash(row: sqlite3.Row) -> str:
    return entry_hash(
        seq=row["seq"],
        at=row["at"],
        actor=row["actor"],
        action=row["action"],
        subject_type=row["subject_type"],
        subject_id=row["subject_id"],
        data=json.loads(row["data"]),
        prev_hash=row["prev_hash"],
    )


def _to_entry(row: sqlite3.Row) -> AuditEntry:
    return AuditEntry(
        seq=row["seq"],
        at=datetime.fromisoformat(row["at"]),
        recorded_at=datetime.fromisoformat(row["recorded_at"]),
        actor=row["actor"],
        action=row["action"],
        subject_type=row["subject_type"],
        subject_id=row["subject_id"],
        data=json.loads(row["data"]),
        prev_hash=row["prev_hash"],
        hash=row["hash"],
    )


def _validate(actor: str, action: str, subject_type: str, subject_id: str) -> None:
    if not ACTOR_PATTERN.fullmatch(actor):
        raise ValueError(f"unknown audit actor {actor!r} (SPEC §11)")
    if not (action.strip() and subject_type.strip() and subject_id.strip()):
        raise ValueError("audit action, subject_type and subject_id must be non-empty")


class AuditLog:
    """Hash-chained audit log; satisfies `store.protocols.AuditSink` (SPEC §11, §24.3)."""

    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._conn = connect(path)
        with self._lock, self._conn:
            for statement in _SCHEMA:
                self._conn.execute(statement)
        last = self._conn.execute("SELECT seq, hash FROM audit_entries ORDER BY seq DESC LIMIT 1").fetchone()
        self._seq: int = last["seq"] if last else 0
        self._head: str = last["hash"] if last else GENESIS_HASH

    def append(
        self,
        *,
        at: datetime,
        actor: str,
        action: str,
        subject_type: str,
        subject_id: str,
        data: Mapping[str, Any],
    ) -> AuditEntry:
        """Append one entry at simulated time `at`; returns it with seq, prev_hash and hash."""
        _validate(actor, action, subject_type, subject_id)
        at_text = str(require_aware(at))
        data_json = canonical_json(dict(data))
        data_value = json.loads(data_json)
        recorded_at = datetime.now(tz=IST).isoformat()
        with self._lock:
            seq, prev = self._seq + 1, self._head
            digest = entry_hash(
                seq=seq,
                at=at_text,
                actor=actor,
                action=action,
                subject_type=subject_type,
                subject_id=subject_id,
                data=data_value,
                prev_hash=prev,
            )
            row = (
                seq,
                at_text,
                recorded_at,
                actor,
                action,
                subject_type,
                subject_id,
                data_json,
                prev,
                digest,
            )
            try:
                with self._conn:
                    self._conn.execute(_INSERT, row)
            except sqlite3.Error:
                logger.exception("audit append failed at seq %d (%s %s)", seq, action, subject_type)
                raise
            self._seq, self._head = seq, digest
            fetched = self._conn.execute(_SELECT_ONE, (seq,)).fetchone()
        return _to_entry(fetched)

    def entries(self, *, after: int = 0, limit: int = 200) -> tuple[AuditEntry, ...]:
        """Entries with seq > after, oldest first, at most `limit` (1..5000)."""
        if after < 0 or not 1 <= limit <= MAX_PAGE:
            raise ValueError(f"after must be ≥ 0 and limit within 1..{MAX_PAGE}")
        with self._lock:
            rows = self._conn.execute(
                _SELECT_PAGE,
                (after, limit),
            ).fetchall()
        return tuple(_to_entry(r) for r in rows)

    def _rows(self) -> Iterator[sqlite3.Row]:
        yield from self._conn.execute(_SELECT_ALL)

    def verify(self) -> dict[str, Any]:
        """Recompute the chain: {valid, entries, head_hash, first_bad_seq} (SPEC §11)."""
        with self._lock:
            count, expected_prev, head, first_bad = 0, GENESIS_HASH, GENESIS_HASH, None
            for row in self._rows():
                count += 1
                intact = (
                    row["seq"] == count
                    and row["prev_hash"] == expected_prev
                    and _row_hash(row) == row["hash"]
                )
                if not intact and first_bad is None:
                    first_bad = row["seq"]
                expected_prev = head = row["hash"]
        if first_bad is not None:
            logger.warning("audit chain broken at seq %d", first_bad)
        return {"valid": first_bad is None, "entries": count, "head_hash": head, "first_bad_seq": first_bad}

    def head_hash(self) -> str:
        """Hash of the newest entry, or the genesis hash when empty."""
        with self._lock:
            return self._head

    def __len__(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM audit_entries").fetchone()[0])

    def close(self) -> None:
        """Close the SQLite connection."""
        with self._lock:
            self._conn.close()
