"""SPEC §19.2 JSON for the policy page and the integration badges (SPEC §9, §0.1, §20)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from chhatri.integrations.base import IntegrationStatus
from chhatri.policy.catalogue import AUTHORITY_TABLE, CHECK_ORDER, CHECK_SPECS
from chhatri.policy.rules import PolicyRules

__all__ = ["integrations_view", "policy_view"]


def policy_view(rules: PolicyRules) -> dict[str, Any]:
    """PolicyView: the loaded rules, the deck's payout-authority table and the §9.2 checks."""
    return {
        "rules": rules.model_dump(mode="json"),
        "authority": [{"case": row.case, "alone": row.alone, "human": row.human} for row in AUTHORITY_TABLE],
        "checks": [
            {
                "code": code.value,
                "severity": CHECK_SPECS[code].severity.value,
                "applies": CHECK_SPECS[code].applies.value,
                "passes_when": CHECK_SPECS[code].passes_when,
            }
            for code in CHECK_ORDER
        ],
    }


def integrations_view(statuses: Sequence[IntegrationStatus]) -> list[dict[str, Any]]:
    """IntegrationStatus list (SPEC §0.1: nothing simulated is ever shown as live)."""
    return [{"name": s.name, "mode": s.mode.value, "detail": s.detail} for s in statuses]
