"""SPEC §11 audit log: canonical JSON, chain, verify, tamper detection, paging, actors."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from chhatri.audit.log import GENESIS_HASH, AuditLog, canonical_json
from chhatri.audit.records import decision_data
from chhatri.clock import ist
from chhatri.domain.enums import CheckCode
from chhatri.policy.engine import evaluate_area_claim
from chhatri.policy.rules import default_rules
from chhatri.store.protocols import AuditSink
from tests.policy import builders as b

AT = ist(2025, 8, 19, 17)


def add(log: AuditLog, n: int = 1, **kw: object):
    entry = None
    for i in range(n):
        entry = log.append(
            at=kw.get("at", AT),  # type: ignore[arg-type]
            actor=kw.get("actor", "system"),  # type: ignore[arg-type]
            action="payout.execute",
            subject_type="payout",
            subject_id=f"P-{i:06d}",
            data=kw.get("data", {"amount_paise": 138000, "i": i}),  # type: ignore[arg-type]
        )
    return entry


def test_protocol_and_empty_state() -> None:
    log = AuditLog()
    assert isinstance(log, AuditSink)
    assert len(log) == 0
    assert log.head_hash() == GENESIS_HASH == "0" * 64
    assert log.verify() == {"valid": True, "entries": 0, "head_hash": GENESIS_HASH, "first_bad_seq": None}


def test_hash_is_spec_canonical_json_without_recorded_at() -> None:
    log = AuditLog()
    e = log.append(
        at=AT, actor="policy-engine", action="decision.area", subject_type="decision", subject_id="D-000001",
        data={"z": 1, "a": "अनिल", "when": date(2025, 8, 19)},
    )  # fmt: skip
    payload = {
        "seq": 1,
        "at": AT,
        "actor": "policy-engine",
        "action": "decision.area",
        "subject_type": "decision",
        "subject_id": "D-000001",
        "data": {"z": 1, "a": "अनिल", "when": date(2025, 8, 19)},
        "prev_hash": "0" * 64,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    assert e.hash == hashlib.sha256(text.encode()).hexdigest()
    assert e.prev_hash == GENESIS_HASH
    assert e.data == {"z": 1, "a": "अनिल", "when": "2025-08-19"}
    assert e.at == AT and e.recorded_at.tzinfo is not None


def test_chain_links_and_same_inputs_same_hashes() -> None:
    a, b_ = AuditLog(), AuditLog()
    add(a, 3)
    add(b_, 3)
    ea, eb = a.entries(), b_.entries()
    assert [e.hash for e in ea] == [e.hash for e in eb]
    assert [e.seq for e in ea] == [1, 2, 3]
    assert ea[1].prev_hash == ea[0].hash and ea[2].prev_hash == ea[1].hash
    assert a.head_hash() == ea[-1].hash
    assert a.verify() == {"valid": True, "entries": 3, "head_hash": ea[-1].hash, "first_bad_seq": None}


def test_entries_paging_and_validation() -> None:
    log = AuditLog()
    add(log, 5)
    assert [e.seq for e in log.entries(after=2, limit=2)] == [3, 4]
    assert log.entries(after=5) == ()
    assert len(log.entries()) == 5
    for bad in ({"after": -1}, {"limit": 0}, {"limit": 5001}):
        with pytest.raises(ValueError):
            log.entries(**bad)  # type: ignore[arg-type]


def test_append_only_triggers_block_update_and_delete(tmp_path: Path) -> None:
    path = tmp_path / "audit.db"
    log = AuditLog(path)
    add(log, 2)
    conn = sqlite3.connect(path)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE audit_entries SET actor = 'model' WHERE seq = 1")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM audit_entries WHERE seq = 1")
    conn.close()


def _tamper(path: Path, sql: str, *args: object) -> None:
    conn = sqlite3.connect(path)
    conn.execute("DROP TRIGGER audit_no_update")
    conn.execute("DROP TRIGGER audit_no_delete")
    conn.execute(sql, args)
    conn.commit()
    conn.close()


def test_tamper_data_detected_via_direct_sqlite_edit(tmp_path: Path) -> None:
    path = tmp_path / "audit.db"
    log = AuditLog(path)
    add(log, 4)
    _tamper(
        path,
        "UPDATE audit_entries SET data = ? WHERE seq = 2",
        canonical_json({"amount_paise": 999999, "i": 1}),
    )
    result = log.verify()
    assert result["valid"] is False and result["first_bad_seq"] == 2 and result["entries"] == 4


def test_tamper_with_rehash_still_breaks_next_link(tmp_path: Path) -> None:
    path = tmp_path / "audit.db"
    log = AuditLog(path)
    add(log, 3)
    _tamper(path, "UPDATE audit_entries SET hash = ? WHERE seq = 2", "f" * 64)
    assert log.verify()["first_bad_seq"] == 2


def test_deleted_row_detected(tmp_path: Path) -> None:
    path = tmp_path / "audit.db"
    log = AuditLog(path)
    add(log, 3)
    _tamper(path, "DELETE FROM audit_entries WHERE seq = ?", 2)
    assert log.verify() | {"head_hash": None} == {
        "valid": False,
        "entries": 2,
        "head_hash": None,
        "first_bad_seq": 3,
    }


def test_recorded_at_edit_does_not_break_chain(tmp_path: Path) -> None:
    path = tmp_path / "audit.db"
    log = AuditLog(path)
    add(log, 2)
    _tamper(path, "UPDATE audit_entries SET recorded_at = ? WHERE seq = 1", "2030-01-01T00:00:00+05:30")
    assert log.verify()["valid"] is True


def test_reopen_file_continues_chain(tmp_path: Path) -> None:
    path = tmp_path / "audit.db"
    first = AuditLog(path)
    add(first, 2)
    head = first.head_hash()
    first.close()
    again = AuditLog(path)
    assert len(again) == 2 and again.head_hash() == head
    e = add(again, 1)
    assert e is not None and e.seq == 3 and e.prev_hash == head
    assert again.verify()["valid"] is True


@pytest.mark.parametrize(
    "actor",
    ["system", "model", "policy-engine", "ai-agent", "officer:priya", "merchant:S-0142", "workflow:payout"],
)
def test_spec_actors_accepted(actor: str) -> None:
    assert add(AuditLog(), actor=actor) is not None


@pytest.mark.parametrize("actor", ["", "robot", "officer:", "officer: x", "workflow:a b", "System"])
def test_unknown_actors_rejected(actor: str) -> None:
    with pytest.raises(ValueError, match="actor"):
        add(AuditLog(), actor=actor)


def test_empty_subject_rejected_and_naive_time_rejected() -> None:
    log = AuditLog()
    with pytest.raises(ValueError, match="non-empty"):
        log.append(at=AT, actor="system", action=" ", subject_type="x", subject_id="y", data={})
    with pytest.raises(ValueError, match="aware"):
        log.append(
            at=datetime(2025, 8, 19, 17),
            actor="system",
            action="a",
            subject_type="x",
            subject_id="y",
            data={},
        )


def test_non_json_values_use_str_and_utc_time_normalised_to_ist() -> None:
    log = AuditLog()
    utc = datetime.fromisoformat("2025-08-19T11:30:00+00:00")
    e = add(log, at=utc, data={"amount": Decimal("1.50")})
    assert e is not None and e.data == {"amount": "1.50"}
    assert e.at == AT and str(e.at) == "2025-08-19 17:00:00+05:30"
    assert log.verify()["valid"] is True


def test_decision_data_contains_every_check() -> None:
    d = evaluate_area_claim(b.area_facts(), default_rules(), decision_id="D-000001", now=AT)
    data = decision_data(d)
    assert [c["code"] for c in data["checks"]] == [c.code.value for c in d.checks]
    assert CheckCode.BELOW_FLOOR.value in {c["code"] for c in data["checks"]}
    log = AuditLog()
    entry = log.append(
        at=AT,
        actor="policy-engine",
        action="decision.area",
        subject_type="decision",
        subject_id=d.id,
        data=data,
    )
    assert entry.data["explanation"]["formula_en"] == "½ × ₹4,380 × 63% = ₹1,380"


def test_concurrent_appends_keep_a_valid_chain() -> None:
    log = AuditLog()
    pool = [threading.Thread(target=add, args=(log, 50)) for _ in range(6)]
    for t in pool:
        t.start()
    for t in pool:
        t.join()
    result = log.verify()
    assert result["valid"] is True and result["entries"] == 300 and len(log) == 300


def test_append_failure_is_logged_and_raised(caplog: pytest.LogCaptureFixture) -> None:
    log = AuditLog()
    add(log, 1)
    head = log.head_hash()
    log.close()
    with pytest.raises(sqlite3.ProgrammingError):
        add(log, 1)
    assert "audit append failed at seq 2" in caplog.text
    assert log.head_hash() == head


def test_latest_finds_the_newest_entry_of_an_action_about_a_subject_at_or_before_a_time() -> None:
    """The claim tracker reads when a shop was checked in on (K5): the newest `silence.detected` before the claim."""
    log = AuditLog()

    def detected(subject: str, at: datetime) -> int:
        entry = log.append(
            at=at,
            actor="model",
            action="silence.detected",
            subject_type="merchant",
            subject_id=subject,
            data={},
        )
        return entry.seq

    first, other, second = (
        detected("S-0142", ist(2025, 8, 20, 11, 20)),
        detected("S-0907", AT),
        detected("S-0142", ist(2025, 8, 21, 11, 20)),
    )
    add(log)
    found = log.latest(action="silence.detected", subject_id="S-0142", at_or_before=ist(2025, 8, 21, 11, 21))
    assert found is not None and found.seq == second
    earlier = log.latest(
        action="silence.detected", subject_id="S-0142", at_or_before=ist(2025, 8, 21, 11, 19)
    )
    assert earlier is not None and earlier.seq == first
    assert (
        log.latest(action="silence.detected", subject_id="S-0142", at_or_before=ist(2025, 8, 20, 11, 0))
        is None
    )
    assert log.latest(action="silence.detected", subject_id="S-0001", at_or_before=ist(2025, 9, 1)) is None
    assert log.latest(action="trigger.fired", subject_id="S-0142", at_or_before=ist(2025, 9, 1)) is None
    assert other not in {first, second}
    with pytest.raises(ValueError, match="aware"):
        log.latest(action="silence.detected", subject_id="S-0142", at_or_before=datetime(2025, 8, 21, 11, 21))
