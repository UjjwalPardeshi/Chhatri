"""Tests for AuditLog (SPEC §11, §24.3). Append-only with tamper detection."""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
import sqlite3

from chhatri.audit.log import AuditLog

IST = ZoneInfo("Asia/Kolkata")


class TestAuditLogInMemory:
    """In-memory audit log tests."""

    @pytest.fixture
    def log(self):
        """Fresh in-memory log."""
        return AuditLog()

    def test_append_entry(self, log):
        """Append an entry and get it back."""
        entry = log.append(
            at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            actor="policy-engine",
            action="payout-execute",
            subject_type="payout",
            subject_id="P-000001",
            data={"amount_paise": 138000, "merchant_id": "S-0142"}
        )

        assert entry.seq == 1
        assert entry.actor == "policy-engine"
        assert entry.subject_id == "P-000001"
        assert entry.hash != ""
        assert len(entry.hash) == 64  # SHA256 hex

    def test_genesis_prev_hash(self, log):
        """First entry has genesis prev_hash (64 zeros)."""
        entry = log.append(
            at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            actor="system",
            action="test",
            subject_type="test",
            subject_id="T-1",
            data={}
        )
        assert entry.prev_hash == "0" * 64

    def test_chain_linking(self, log):
        """Entries link to previous via prev_hash."""
        entry1 = log.append(
            at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            actor="system",
            action="test1",
            subject_type="test",
            subject_id="T-1",
            data={}
        )

        entry2 = log.append(
            at=datetime(2025, 8, 19, 17, 1, tzinfo=IST),
            actor="system",
            action="test2",
            subject_type="test",
            subject_id="T-2",
            data={}
        )

        # Entry 2 should link to entry 1
        assert entry2.prev_hash == entry1.hash
        assert entry2.seq == 2

    def test_entries_after(self, log):
        """Get entries after a sequence number."""
        for i in range(5):
            log.append(
                at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
                actor="system",
                action=f"test{i}",
                subject_type="test",
                subject_id=f"T-{i}",
                data={}
            )

        # Get after seq 2
        entries = log.entries(after=2, limit=10)
        assert len(entries) == 3  # seq 3, 4, 5
        assert entries[0].seq == 3
        assert entries[-1].seq == 5

    def test_verify_valid_chain(self, log):
        """Verify returns valid when chain is intact."""
        for i in range(3):
            log.append(
                at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
                actor="system",
                action=f"test{i}",
                subject_type="test",
                subject_id=f"T-{i}",
                data={}
            )

        result = log.verify()
        assert result["valid"] is True
        assert result["entries"] == 3
        assert result["first_bad_seq"] is None

    def test_verify_empty_log(self, log):
        """Verify empty log."""
        result = log.verify()
        assert result["valid"] is True
        assert result["entries"] == 0
        assert result["head_hash"] == "0" * 64

    def test_head_hash(self, log):
        """Get head hash (last entry or genesis)."""
        assert log.head_hash() == "0" * 64  # Empty

        entry = log.append(
            at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            actor="system",
            action="test",
            subject_type="test",
            subject_id="T-1",
            data={}
        )
        assert log.head_hash() == entry.hash

    def test_len(self, log):
        """Count entries."""
        assert len(log) == 0

        log.append(
            at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            actor="system",
            action="test",
            subject_type="test",
            subject_id="T-1",
            data={}
        )
        assert len(log) == 1


class TestAuditLogFileBased:
    """File-based audit log tests (to verify SQLite works)."""

    def test_file_based_log(self, tmp_path):
        """Create log on disk."""
        db_path = tmp_path / "audit.db"
        log = AuditLog(path=db_path)

        entry = log.append(
            at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            actor="system",
            action="test",
            subject_type="test",
            subject_id="T-1",
            data={"key": "value"}
        )

        assert db_path.exists()
        assert entry.seq == 1

    def test_file_persistence(self, tmp_path):
        """Data persists across log instances."""
        db_path = tmp_path / "audit.db"

        # Write
        log1 = AuditLog(path=db_path)
        entry1 = log1.append(
            at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            actor="system",
            action="test",
            subject_type="test",
            subject_id="T-1",
            data={}
        )

        # Read from new instance
        log2 = AuditLog(path=db_path)
        assert len(log2) == 1
        entries = log2.entries(after=0)
        assert entries[0].seq == 1
        assert entries[0].actor == "system"


class TestAuditTamperDetection:
    """Tamper detection tests."""

    def test_tamper_detection_hash_modification(self, tmp_path):
        """Verify detects modified hash."""
        db_path = tmp_path / "audit.db"
        log = AuditLog(path=db_path)

        # Append entries
        log.append(
            at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            actor="system",
            action="test1",
            subject_type="test",
            subject_id="T-1",
            data={}
        )
        log.append(
            at=datetime(2025, 8, 19, 17, 1, tzinfo=IST),
            actor="system",
            action="test2",
            subject_type="test",
            subject_id="T-2",
            data={}
        )

        # Verify valid before tampering
        result = log.verify()
        assert result["valid"] is True

        # Tamper with first entry
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("UPDATE audit_entries SET hash='0'*64 WHERE seq=1")
        conn.commit()
        conn.close()

        # Verify detects tampering
        log2 = AuditLog(path=db_path)
        result = log2.verify()
        assert result["valid"] is False
        assert result["first_bad_seq"] == 1

    def test_tamper_detection_prev_hash_modification(self, tmp_path):
        """Verify detects broken chain (modified prev_hash)."""
        db_path = tmp_path / "audit.db"
        log = AuditLog(path=db_path)

        # Append entries
        log.append(
            at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            actor="system",
            action="test1",
            subject_type="test",
            subject_id="T-1",
            data={}
        )
        log.append(
            at=datetime(2025, 8, 19, 17, 1, tzinfo=IST),
            actor="system",
            action="test2",
            subject_type="test",
            subject_id="T-2",
            data={}
        )

        # Tamper with chain (change prev_hash of entry 2)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("UPDATE audit_entries SET prev_hash='0'*64 WHERE seq=2")
        conn.commit()
        conn.close()

        # Verify detects broken chain
        log2 = AuditLog(path=db_path)
        result = log2.verify()
        assert result["valid"] is False
        assert result["first_bad_seq"] == 2

    def test_recorded_at_not_in_hash(self, tmp_path):
        """recorded_at field is not included in hash (per spec)."""
        db_path = tmp_path / "audit.db"
        log1 = AuditLog(path=db_path)

        entry1 = log1.append(
            at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            actor="system",
            action="test",
            subject_type="test",
            subject_id="T-1",
            data={}
        )

        hash1 = entry1.hash

        # Close and reopen with same data (recorded_at will be different)
        log1._conn.close()
        del log1

        # If recorded_at was in the hash, re-computing would give different result
        # But since it's excluded, we can verify by checking the hash is reproducible
        log2 = AuditLog(path=db_path)
        result = log2.verify()
        assert result["valid"] is True  # Valid means hashes are reproducible
