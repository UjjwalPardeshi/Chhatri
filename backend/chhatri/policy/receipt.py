"""The receipt extras of a decision, built when it is made (fs-09 section 10). Pure: no I/O.

`build_receipt(facts, decision, rules)` returns the sources behind each check and money number (H13,
`policy.provenance`) and the counterfactuals the engine confirmed (H14, `policy.counterfactual`). They are built from
the facts the engine saw, at decision time, and stored with the decision (`Decision.sources` and
`Decision.counterfactuals`), so they are part of its hash-chained audit entry. Building them later from the store would
be wrong: after the payout the "already paid" fact has changed. The engine's `evaluate_*` signatures do not change.

A bug in a receipt builder must not stop a decision from being recorded, so a failure is logged with its traceback and the
decision is recorded without the extras it could not build.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from chhatri.domain.models import Counterfactual, Decision, SourcedLine
from chhatri.policy.counterfactual import counterfactuals
from chhatri.policy.facts import AreaClaimFacts, PersonalClaimFacts
from chhatri.policy.provenance import build_sources
from chhatri.policy.rules import PolicyRules

__all__ = ["ReceiptExtras", "build_receipt", "with_receipt"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ReceiptExtras:
    sources: tuple[SourcedLine, ...]
    counterfactuals: tuple[Counterfactual, ...]


def build_receipt(
    facts: AreaClaimFacts | PersonalClaimFacts, decision: Decision, rules: PolicyRules
) -> ReceiptExtras:
    """The sources and counterfactuals of `decision`, from the facts it was decided on."""
    sources: tuple[SourcedLine, ...] = ()
    confirmed: tuple[Counterfactual, ...] = ()
    try:
        sources = build_sources(facts, decision, rules)
        confirmed = counterfactuals(facts, decision, rules)
    except Exception:  # noqa: BLE001 - a receipt bug must never stop a decision; logged with the traceback
        logger.exception("receipt of decision %s could not be fully built", decision.id)
    return ReceiptExtras(sources, confirmed)


def with_receipt(
    decision: Decision, facts: AreaClaimFacts | PersonalClaimFacts, rules: PolicyRules
) -> Decision:
    """A copy of `decision` that carries its sources and counterfactuals."""
    extras = build_receipt(facts, decision, rules)
    return decision.model_copy(update={"sources": extras.sources, "counterfactuals": extras.counterfactuals})
