"""Narrow protocols other packages type against (SPEC §24.3). Scaffold — read-only for builders.

`chhatri.store.repositories.Store` and `chhatri.audit.log.AuditLog` satisfy these structurally.
Packages that only need a slice (e.g. conversation needs messages + media) depend on the slice.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from chhatri.domain.models import AuditEntry, Message


@runtime_checkable
class AuditSink(Protocol):
    def append(
        self,
        *,
        at: datetime,
        actor: str,
        action: str,
        subject_type: str,
        subject_id: str,
        data: Mapping[str, Any],
    ) -> AuditEntry: ...


@runtime_checkable
class MessageLog(Protocol):
    def add_message(self, message: Message) -> None: ...

    def messages(self, merchant_id: str) -> tuple[Message, ...]: ...

    def put_media(self, data: bytes, mime: str, media_id: str) -> None: ...

    def media(self, media_id: str) -> tuple[bytes, str]: ...
