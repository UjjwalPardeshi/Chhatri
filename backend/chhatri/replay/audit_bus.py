"""Audit log that also streams every entry to the console (SPEC §11, §19.1 ``audit`` event).

The replay keeps its audit chain in an in-memory SQLite database (SPEC §3: the log is recreated on
every scenario load, so the same scenario always yields the same seqs and hashes; a file-backed log
with one fsync per append would also stall the 17:00 burst of ~1,000 entries). Every append is
published as ``audit {seq, action, actor, subject_type, subject_id}`` on the process-wide bus.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from chhatri.audit.log import AuditLog
from chhatri.domain.models import AuditEntry
from chhatri.events import EventBus

__all__ = ["PublishingAuditLog"]


class PublishingAuditLog(AuditLog):
    """`AuditLog` (in memory) that publishes an ``audit`` event after each append."""

    def __init__(self, bus: EventBus) -> None:
        super().__init__(None)
        self._bus = bus

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
        entry = super().append(
            at=at, actor=actor, action=action, subject_type=subject_type, subject_id=subject_id, data=data
        )
        self._bus.publish(
            "audit",
            entry.at,
            {
                "seq": entry.seq,
                "action": entry.action,
                "actor": entry.actor,
                "subject_type": entry.subject_type,
                "subject_id": entry.subject_id,
            },
        )
        return entry
