"""Recording a policy decision: store, audit (with every check), SSE and memory (SPEC §9, §11, §16).

SPEC §11: "Every decision stores all checks in `data`" — the audit payload is the full decision
(`chhatri.audit.records.decision_data`: the checks, the explanation, and the sources and counterfactuals of the
receipt, H13 and H14) plus the claim it decides. The claim summary leaves out the raw slip (its fields are in the
checks' observed values and in the case evidence).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from chhatri.audit.records import decision_data
from chhatri.domain.models import Claim, Decision
from chhatri.policy.facts import AreaClaimFacts, PersonalClaimFacts
from chhatri.policy.receipt import with_receipt
from chhatri.replay.memory_facts import decision_fact
from chhatri.replay.publish import Publisher, RuntimeLink

__all__ = ["POLICY_ACTOR", "DecisionRecorder", "claim_summary"]

POLICY_ACTOR: Final = "policy-engine"


def claim_summary(claim: Claim) -> dict[str, Any]:
    """JSON-ready claim facts for the audit log."""
    return {
        "id": claim.id,
        "kind": claim.kind.value,
        "merchant_id": claim.merchant_id,
        "event_date": claim.event_date.isoformat(),
        "trigger_id": claim.trigger_id,
        "silent_dates": [d.isoformat() for d in claim.silent_dates],
        "expected_day_paise": claim.expected_day_paise,
        "drop_pct": claim.drop_pct,
        "slip_media_id": claim.slip_media_id,
    }


class DecisionRecorder:
    """Stores, audits, publishes and remembers decisions."""

    def __init__(self, link: RuntimeLink, publisher: Publisher) -> None:
        self._link = link
        self._publisher = publisher

    async def record(
        self,
        decision: Decision,
        *,
        action: str,
        actor: str = POLICY_ACTOR,
        claim: Claim | None = None,
        extra: Mapping[str, Any] | None = None,
        facts: AreaClaimFacts | PersonalClaimFacts | None = None,
    ) -> Decision:
        """Add `claim` (when new) and `decision` to the store, then audit, publish and remember.

        With the `facts` the engine decided on, the decision first gets its sources and counterfactuals (H13, H14), so
        they are stored, hash-chained and published with it. The decision that was recorded is returned.
        """
        rt = self._link.rt
        if facts is not None:
            decision = with_receipt(decision, facts, rt.static.rules)
        if claim is not None:
            rt.store.add_claim(claim)
        rt.store.add_decision(decision)
        stored_claim = rt.store.claim(decision.claim_id)
        data = {**decision_data(decision), "claim": claim_summary(stored_claim), **(extra or {})}
        rt.audit.append(
            at=decision.decided_at,
            actor=actor,
            action=action,
            subject_type="decision",
            subject_id=decision.id,
            data=data,
        )
        self._publisher.decision(decision)
        zone_id = rt.static.city.merchant(decision.merchant_id).zone_id
        await rt.integrations.memory.remember(decision_fact(decision, stored_claim, zone_id))
        return decision
