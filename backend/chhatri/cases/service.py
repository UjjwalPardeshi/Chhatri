"""Claims-officer cases (SPEC §12, §24.3).

Cases are opened for REFERRED personal claims (PERSONAL_CLAIM_REVIEW), merchant disputes (DISPUTE)
and officer-requested area reviews (AREA_REVIEW). Ids come from `IdFactory.next_case()` and start at
C-2291 on every scenario load (SPEC §3); `due_by = opened_at + dispute_sla_hours`. Opening and
resolving are audited. Inputs are validated: the merchant must exist, a linked claim/decision must
exist and belong to the merchant, a PERSONAL_CLAIM_REVIEW needs a REFERRED decision, and only an
OPEN case can be resolved (to APPROVED, DECLINED or CLOSED) by an officer, system or workflow actor.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any, Final

from chhatri.audit.log import AuditLog
from chhatri.clock import require_aware
from chhatri.domain.enums import CaseKind, CaseStatus, DecisionOutcome
from chhatri.domain.models import Case
from chhatri.ids import IdFactory
from chhatri.policy.rules import PolicyRules
from chhatri.store.repositories import Store

logger = logging.getLogger(__name__)

ACTOR: Final = "system"
RESOLVED_STATUSES: Final = frozenset({CaseStatus.APPROVED, CaseStatus.DECLINED, CaseStatus.CLOSED})
RESOLVER_PATTERN: Final = re.compile(r"^system$|^(officer|workflow):[A-Za-z0-9][A-Za-z0-9._@-]{0,63}$")


class CaseService:
    """Open and resolve cases for claims officers (SPEC §12)."""

    def __init__(self, store: Store, audit: AuditLog, ids: IdFactory, rules: PolicyRules) -> None:
        self._store = store
        self._audit = audit
        self._ids = ids
        self._rules = rules

    def _validate_links(
        self, kind: CaseKind, merchant_id: str, claim_id: str | None, decision_id: str | None
    ) -> None:
        self._store.city.merchant(merchant_id)
        if claim_id is not None and self._store.claim(claim_id).merchant_id != merchant_id:
            raise ValueError(f"claim {claim_id} does not belong to {merchant_id}")
        decision = self._store.decision(decision_id) if decision_id is not None else None
        if decision is not None and decision.merchant_id != merchant_id:
            raise ValueError(f"decision {decision_id} does not belong to {merchant_id}")
        if decision is not None and claim_id is not None and decision.claim_id != claim_id:
            raise ValueError(f"decision {decision_id} is not for claim {claim_id}")
        if kind is CaseKind.PERSONAL_CLAIM_REVIEW and (
            decision is None or decision.outcome is not DecisionOutcome.REFERRED
        ):
            raise ValueError("a personal claim review needs the REFERRED decision it reviews")

    def open(
        self,
        *,
        kind: CaseKind,
        merchant_id: str,
        at: datetime,
        summary_en: str,
        summary_hi: str | None,
        evidence: Mapping[str, Any],
        claim_id: str | None = None,
        decision_id: str | None = None,
    ) -> Case:
        """Open a case due `dispute_sla_hours` after `at` (SPEC §12)."""
        at, kind = require_aware(at), CaseKind(kind)
        if not summary_en.strip():
            raise ValueError("a case needs an English summary")
        self._validate_links(kind, merchant_id, claim_id, decision_id)
        case = Case(
            id=self._ids.next_case(),
            kind=kind,
            merchant_id=merchant_id,
            claim_id=claim_id,
            decision_id=decision_id,
            status=CaseStatus.OPEN,
            opened_at=at,
            due_by=at + timedelta(hours=self._rules.dispute_sla_hours),
            summary_en=summary_en,
            summary_hi=summary_hi,
            evidence=dict(evidence),
        )
        self._store.add_case(case)
        self._audit.append(
            at=at,
            actor=ACTOR,
            action="case.open",
            subject_type="case",
            subject_id=case.id,
            data={
                "kind": kind.value,
                "merchant_id": merchant_id,
                "claim_id": claim_id,
                "decision_id": decision_id,
                "summary_en": summary_en,
                "due_by": case.due_by.isoformat(),
                "evidence_keys": sorted(case.evidence),
            },
        )
        logger.info("case %s opened (%s)", case.id, kind.value)
        return case

    def resolve(self, case_id: str, *, status: CaseStatus, by: str, resolution: str, at: datetime) -> Case:
        """Close an OPEN case as APPROVED, DECLINED or CLOSED (SPEC §9.4, §12).

        `status` may be given as its string value; a blank resolution defaults to "<Status> by <by>".
        """
        at, status = require_aware(at), CaseStatus(status)
        if status not in RESOLVED_STATUSES:
            raise ValueError(f"a case resolves to APPROVED, DECLINED or CLOSED, not {status}")
        if not RESOLVER_PATTERN.fullmatch(by):
            raise ValueError(f"cases are resolved by an officer, workflow or system actor, not {by!r}")
        resolution = resolution.strip() or f"{status.value.title()} by {by}"
        case = self._store.case(case_id)
        if case.status is not CaseStatus.OPEN:
            raise ValueError(f"case {case_id} is already {case.status}")
        if at < case.opened_at:
            raise ValueError(f"case {case_id} cannot be resolved before it was opened")
        resolved = case.model_copy(
            update={"status": status, "resolution": resolution, "resolved_by": by, "resolved_at": at}
        )
        self._store.replace_case(resolved)
        self._audit.append(
            at=at,
            actor=by,
            action="case.resolve",
            subject_type="case",
            subject_id=case_id,
            data={
                "kind": case.kind.value,
                "merchant_id": case.merchant_id,
                "status": status.value,
                "resolution": resolution,
                "within_sla": at <= case.due_by,
            },
        )
        return resolved
