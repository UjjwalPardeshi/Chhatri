"""One module per suite. Each ``run(split)`` returns a ``SuiteResult`` and never touches the network."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["SuiteResult"]


@dataclass(frozen=True, slots=True)
class SuiteResult:
    id: str
    status: str  # MEASURED or NOT_MEASURED
    reason: str | None
    metrics: tuple[dict[str, Any], ...] = ()
    items: tuple[dict[str, Any], ...] = ()
    providers: tuple[dict[str, Any], ...] = field(default=())

    def to_summary(self) -> dict[str, Any]:
        return {"id": self.id, "status": self.status, "reason": self.reason, "metrics": list(self.metrics)}
