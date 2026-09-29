"""Case service (SPEC §12, §24.3). Open and resolve cases for disputes and soft-fail personal claims."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from chhatri.audit.log import AuditLog
from chhatri.domain.enums import CaseKind, CaseStatus
from chhatri.domain.models import Case
from chhatri.ids import IdFactory
from chhatri.policy.rules import PolicyRules
from chhatri.store.repositories import Store


class CaseService:
    """Manage case lifecycle: open, resolve."""

    def __init__(self, store: Store, audit: AuditLog, ids: IdFactory, rules: PolicyRules) -> None:
        self.store = store
        self.audit = audit
        self.ids = ids
        self.rules = rules

    def open(
        self,
        *,
        kind: CaseKind,
        merchant_id: str,
        at: datetime,
        summary_en: str,
        summary_hi: str | None = None,
        evidence: dict[str, Any] | None = None,
        claim_id: str | None = None,
        decision_id: str | None = None,
    ) -> Case:
        """Open a new case.

        Cases are opened for:
        - PERSONAL_CLAIM_REVIEW: referred personal claims (soft check failures)
        - DISPUTE: merchant disputes an area decision
        - AREA_REVIEW: officer-requested area review

        Args:
            kind: The case kind.
            merchant_id: Affected merchant.
            at: When the case is opened.
            summary_en: Summary text in English.
            summary_hi: Summary text in Hindi (optional).
            evidence: Case evidence bundle (e.g., slip image, decision checks).
            claim_id: Associated claim (for PERSONAL_CLAIM_REVIEW).
            decision_id: Associated decision (for any case).

        Returns:
            The opened Case.
        """
        case_id = self.ids.next_case()
        due_by = at + timedelta(hours=self.rules.dispute_sla_hours)

        case = Case(
            id=case_id,
            kind=kind,
            merchant_id=merchant_id,
            claim_id=claim_id,
            decision_id=decision_id,
            status=CaseStatus.OPEN,
            opened_at=at,
            due_by=due_by,
            summary_en=summary_en,
            summary_hi=summary_hi,
            evidence=evidence or {},
            resolution=None,
            resolved_by=None,
            resolved_at=None,
        )

        self.store.add_case(case)

        # Audit
        self.audit.append(
            at=at,
            actor="system",
            action="case-open",
            subject_type="case",
            subject_id=case_id,
            data={
                "kind": str(kind),
                "merchant_id": merchant_id,
                "claim_id": claim_id,
                "decision_id": decision_id,
                "summary_en": summary_en,
                "due_by": due_by.isoformat(),
            },
        )

        return case

    def resolve(
        self,
        case_id: str,
        *,
        status: CaseStatus,
        by: str,
        resolution: str,
        at: datetime,
    ) -> Case:
        """Resolve an open case.

        Args:
            case_id: The case to resolve.
            status: The resolution status (APPROVED, DECLINED, or CLOSED).
            by: Who resolved it (e.g., "officer:123", "merchant").
            resolution: Explanation of the resolution.
            at: When resolved.

        Returns:
            The resolved Case.

        Raises:
            KeyError: If case not found.
            ValueError: If case is not OPEN.
        """
        case = self.store.case(case_id)

        if case.status != CaseStatus.OPEN:
            raise ValueError(f"Case {case_id} is not OPEN, status is {case.status}")

        resolved_case = case.model_copy(update={
            "status": status,
            "resolved_by": by,
            "resolution": resolution,
            "resolved_at": at,
        })

        self.store.replace_case(resolved_case)

        # Audit
        self.audit.append(
            at=at,
            actor=by,
            action="case-resolve",
            subject_type="case",
            subject_id=case_id,
            data={
                "merchant_id": case.merchant_id,
                "status": str(status),
                "resolution": resolution,
                "resolved_by": by,
            },
        )

        return resolved_case
