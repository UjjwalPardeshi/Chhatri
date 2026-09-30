"""Audit `data` payloads for domain objects (SPEC §11: every decision stores all checks in `data`)."""

from __future__ import annotations

from typing import Any

from chhatri.domain.models import Decision


def decision_data(decision: Decision) -> dict[str, Any]:
    """JSON-ready audit payload of a decision: outcome, amount, every check and the explanation."""
    return decision.model_dump(mode="json")
