"""Audit log (SPEC §11, §24.3). Append-only SQLite with tamper-evident hashing.

Canonical JSON: json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False, default=str)
Hash: sha256(canonical JSON of all fields except recorded_at and hash itself)
Genesis prev_hash: 64 zeros
Verify: recompute chain and detect tampering
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from chhatri.domain.models import AuditEntry


def _canonical_json(data: dict[str, Any]) -> str:
    """JSON with sort_keys, compact separators, and ensure_ascii=False."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _compute_hash(data: dict[str, Any]) -> str:
    """SHA256 of canonical JSON."""
    canonical = _canonical_json(data)
    return hashlib.sha256(canonical.encode()).hexdigest()


class AuditLog:
    """Append-only audit log on SQLite. Thread-safe. Satisfies AuditSink protocol."""

    def __init__(self, path: Path | None = None) -> None:
        """Initialize audit log.

        Args:
            path: Path to SQLite file, or None for in-memory.
        """
        self._lock = threading.RLock()
        self._path = path

        # Initialize database
        db_path = ":memory:" if path is None else str(path)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        self._next_seq = self._load_next_seq()

    def _init_schema(self) -> None:
        """Create the audit table if it doesn't exist."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_entries (
                    seq INTEGER PRIMARY KEY,
                    at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    hash TEXT NOT NULL
                )
            """)
            self._conn.commit()

    def _load_next_seq(self) -> int:
        """Load the next sequence number from the database."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT MAX(seq) FROM audit_entries")
            row = cursor.fetchone()
            if row and row[0] is not None:
                return row[0] + 1
            return 1

    def _get_prev_hash(self) -> str:
        """Get the hash of the last entry, or genesis (64 zeros)."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT hash FROM audit_entries ORDER BY seq DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return row[0]
            return "0" * 64

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
        """Append an entry to the audit log.

        Args:
            at: Simulated/business time (included in hash).
            actor: Who performed the action.
            action: What was done.
            subject_type: Type of subject (e.g., "decision", "payout").
            subject_id: ID of the subject.
            data: Arbitrary data (included in hash).

        Returns:
            The created AuditEntry with seq, hash, prev_hash, and recorded_at set.
        """
        with self._lock:
            seq = self._next_seq
            self._next_seq += 1

            # Get wall-clock time
            recorded_at = datetime.now(datetime.now().astimezone().tzinfo)

            # Get previous hash
            prev_hash = self._get_prev_hash()

            # Compute hash (excludes recorded_at)
            hash_data = {
                "seq": seq,
                "at": at.isoformat(),
                "actor": actor,
                "action": action,
                "subject_type": subject_type,
                "subject_id": subject_id,
                "data": dict(data),
                "prev_hash": prev_hash,
            }
            entry_hash = _compute_hash(hash_data)

            # Store in database
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_entries
                (seq, at, recorded_at, actor, action, subject_type, subject_id, data, prev_hash, hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    seq,
                    at.isoformat(),
                    recorded_at.isoformat(),
                    actor,
                    action,
                    subject_type,
                    subject_id,
                    _canonical_json(dict(data)),
                    prev_hash,
                    entry_hash,
                ),
            )
            self._conn.commit()

            # Return the entry
            return AuditEntry(
                seq=seq,
                at=at,
                recorded_at=recorded_at,
                actor=actor,
                action=action,
                subject_type=subject_type,
                subject_id=subject_id,
                data=dict(data),
                prev_hash=prev_hash,
                hash=entry_hash,
            )

    def entries(self, *, after: int = 0, limit: int = 200) -> tuple[AuditEntry, ...]:
        """Get entries after a sequence number.

        Args:
            after: Get entries with seq > after. Default 0 (all from start).
            limit: Maximum number of entries to return.

        Returns:
            Tuple of AuditEntry objects.
        """
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT * FROM audit_entries WHERE seq > ? ORDER BY seq ASC LIMIT ?",
                (after, limit),
            )
            rows = cursor.fetchall()

            result = []
            for row in rows:
                result.append(
                    AuditEntry(
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
                )

            return tuple(result)

    def verify(self) -> dict[str, Any]:
        """Verify the integrity of the audit chain.

        Returns:
            {
                "valid": bool,
                "entries": int (number of entries in the chain),
                "head_hash": str (hash of the last entry, or 64 zeros if empty),
                "first_bad_seq": int | None (seq of first tampered entry, or None if all valid)
            }
        """
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM audit_entries")
            count = cursor.fetchone()[0]

            if count == 0:
                return {
                    "valid": True,
                    "entries": 0,
                    "head_hash": "0" * 64,
                    "first_bad_seq": None,
                }

            # Verify the chain
            cursor.execute("SELECT * FROM audit_entries ORDER BY seq ASC")
            rows = cursor.fetchall()

            expected_prev_hash = "0" * 64
            first_bad_seq = None

            for row in rows:
                # Recompute hash (exclude recorded_at)
                hash_data = {
                    "seq": row["seq"],
                    "at": row["at"],
                    "actor": row["actor"],
                    "action": row["action"],
                    "subject_type": row["subject_type"],
                    "subject_id": row["subject_id"],
                    "data": json.loads(row["data"]),
                    "prev_hash": row["prev_hash"],
                }
                computed_hash = _compute_hash(hash_data)

                # Check hash
                if computed_hash != row["hash"] and first_bad_seq is None:
                    first_bad_seq = row["seq"]

                # Check prev_hash
                if row["prev_hash"] != expected_prev_hash and first_bad_seq is None:
                    first_bad_seq = row["seq"]

                expected_prev_hash = row["hash"]

            return {
                "valid": first_bad_seq is None,
                "entries": count,
                "head_hash": expected_prev_hash,
                "first_bad_seq": first_bad_seq,
            }

    def head_hash(self) -> str:
        """Get the hash of the last entry, or genesis (64 zeros)."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT hash FROM audit_entries ORDER BY seq DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return row[0]
            return "0" * 64

    def __len__(self) -> int:
        """Number of entries in the log."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM audit_entries")
            return cursor.fetchone()[0]
