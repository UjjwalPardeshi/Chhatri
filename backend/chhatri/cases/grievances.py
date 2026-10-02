"""N5 grievance ladder service (fs-06 section 8, data-model-and-api section 5.4): open, escalate, resolve.

A grievance lives in memory in a ``GrievanceBook`` per scenario run (one book per ``Store``, so a reload starts it
afresh, like cases). A dispute about a decision opens the DISPUTE case through the same code as the chat path, so
a dispute opened either way is the same case. Audit entries hold ids, codes and counts and never the merchant's
words (``text`` is kept on the grievance only).
"""

from __future__ import annotations

import logging
import threading
import weakref
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final, Literal

from pydantic import Field

from chhatri.audit.log import AuditLog
from chhatri.cases import ladder
from chhatri.clock import IST, require_aware
from chhatri.conversation.ports import DisputeOutcome
from chhatri.domain.enums import CaseKind, CaseStatus, DecisionOutcome
from chhatri.domain.models import Case, Decision, Frozen
from chhatri.ids import IdFactory
from chhatri.store.repositories import Store

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS: Final = 500
OPEN_REVIEW_KINDS: Final = (CaseKind.PERSONAL_CLAIM_REVIEW, CaseKind.AREA_REVIEW)
DECISION_AUDIT_ACTIONS: Final = ("decision.officer", "decision.personal", "decision.area")

__all__ = [
    "GrievanceBook",
    "GrievanceConflict",
    "GrievanceInvalid",
    "GrievanceService",
    "Grievance",
    "GrievanceStep",
    "OpenResult",
    "book_for",
    "grievance_view",
]


class GrievanceInvalid(ValueError):
    """The request is well formed but cannot be done (HTTP 422); ``fields`` names the input."""

    def __init__(self, message: str, fields: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.fields = fields or {}


class GrievanceConflict(ValueError):
    """The grievance is not in a state that allows this (HTTP 409)."""


class GrievanceStep(Frozen):
    id: str
    state: Literal["NOT_STARTED", "ACTIVE", "DONE"]
    entered_at: datetime | None = None
    outcome: Literal["ESCALATED", "SOLVED"] | None = None


class Grievance(Frozen):
    id: str = Field(pattern=r"^GR-\d{6,}$")
    merchant_id: str
    decision_id: str | None = None
    case_id: str | None = None
    kind: Literal["DISPUTE", "COMPLAINT"]
    topic: str
    respondent: Literal["PAYTM", "INSURER", "LENDER"]
    text: str
    lang: str
    status: Literal["OPEN", "RESOLVED"]
    opened_at: datetime
    due_by: datetime | None = None  # our own answer time, from the linked case
    current_step: str
    steps: tuple[GrievanceStep, ...]
    resolved_at: datetime | None = None
    receipt_audit_seq: int | None = None


class GrievanceBook:
    """The grievances of one scenario run, insertion order (oldest first)."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: dict[str, Grievance] = {}

    def add(self, grievance: Grievance) -> None:
        with self._lock:
            if grievance.id in self._items:
                raise ValueError(f"grievance {grievance.id} already exists")
            self._items[grievance.id] = grievance

    def replace(self, grievance: Grievance) -> None:
        with self._lock:
            if grievance.id not in self._items:
                raise KeyError(f"unknown grievance {grievance.id}")
            self._items[grievance.id] = grievance

    def get(self, grievance_id: str) -> Grievance:
        with self._lock:
            try:
                return self._items[grievance_id]
            except KeyError:
                raise KeyError(f"unknown grievance {grievance_id}") from None

    def for_merchant(self, merchant_id: str) -> tuple[Grievance, ...]:
        with self._lock:
            return tuple(g for g in self._items.values() if g.merchant_id == merchant_id)


_BOOKS: Final[weakref.WeakKeyDictionary[Store, GrievanceBook]] = weakref.WeakKeyDictionary()
_BOOKS_LOCK: Final = threading.Lock()


def book_for(store: Store) -> GrievanceBook:
    """The book of this scenario run (a new Store, from a reload, has an empty one)."""
    with _BOOKS_LOCK:
        book = _BOOKS.get(store)
        if book is None:
            book = _BOOKS[store] = GrievanceBook()
        return book


@dataclass(frozen=True, slots=True)
class OpenResult:
    grievance: Grievance
    created: bool


OpenDispute = Callable[[str, str], Awaitable[DisputeOutcome]]
NotifyDispute = Callable[[Case, bool], Awaitable[Any]]


def grievance_view(grievance: Grievance, *, now: datetime, sla_hours: int) -> dict[str, Any]:
    """The JSON of one grievance (data-model section 5.4); clocks are computed here, when it is read."""
    steps = []
    for stored, step in zip(grievance.steps, ladder.ladder_for(grievance.respondent), strict=True):
        due = grievance.due_by if step.id == "PAYTM_DISPUTE" else None
        item: dict[str, Any] = {
            "level": len(steps) + 1,
            "id": step.id,
            "name": step.name,
            "state": stored.state,
            "delivery": step.delivery,
        }
        if stored.entered_at is not None:
            item["entered_at"] = stored.entered_at.isoformat()
        item["clock"] = ladder.clock_view(
            step.id, entered_at=stored.entered_at, now=now, due_by=due, sla_hours=sla_hours
        )
        steps.append(item)
    return {
        "grievance_id": grievance.id,
        "kind": grievance.kind,
        "topic": grievance.topic,
        "respondent": grievance.respondent,
        "decision_id": grievance.decision_id,
        "case_id": grievance.case_id,
        "status": grievance.status,
        "opened_at": grievance.opened_at.isoformat(),
        "current_step": grievance.current_step,
        "ladder_steps": steps,
        "next_action": None
        if grievance.status == "RESOLVED"
        else ladder.next_action(grievance.respondent, grievance.current_step),
        "receipt_audit_seq": grievance.receipt_audit_seq,
    }


def _first_steps(respondent: str, now: datetime) -> tuple[GrievanceStep, ...]:
    rungs = ladder.ladder_for(respondent)
    return tuple(
        GrievanceStep(
            id=rung.id,
            state="ACTIVE" if index == 0 else "NOT_STARTED",
            entered_at=now if index == 0 else None,
        )
        for index, rung in enumerate(rungs)
    )


class GrievanceService:
    """Open, escalate and resolve grievances for one scenario run."""

    def __init__(self, *, store: Store, audit: AuditLog, ids: IdFactory, sla_hours: int) -> None:
        self._store = store
        self._audit = audit
        self._ids = ids
        self._sla_hours = sla_hours
        self._book = book_for(store)

    @property
    def sla_hours(self) -> int:
        return self._sla_hours

    def list_for(self, merchant_id: str, *, now: datetime) -> list[dict[str, Any]]:
        """The merchant's grievances as views, newest first."""
        items = reversed(self._book.for_merchant(merchant_id))
        return [grievance_view(g, now=now, sla_hours=self._sla_hours) for g in items]

    def get_view(self, grievance_id: str, *, now: datetime) -> dict[str, Any]:
        return grievance_view(self._book.get(grievance_id), now=now, sla_hours=self._sla_hours)

    # ------------------------------------------------------------------ open
    def _decision_for(self, merchant_id: str, topic: str, decision_id: str | None) -> Decision | None:
        if decision_id is not None:
            try:
                decision = self._store.decision(decision_id)
            except KeyError:
                raise GrievanceInvalid("unknown decision", {"decision_id": "unknown decision"}) from None
            if decision.merchant_id != merchant_id:
                raise GrievanceInvalid("unknown decision", {"decision_id": "unknown decision"})
            return decision
        if topic == "PAYOUT_AMOUNT":
            return self._store.latest_paid_decision(merchant_id)
        if topic == "CLAIM_DECLINED":
            declined = [
                d for d in self._store.decisions_for(merchant_id) if d.outcome is DecisionOutcome.DECLINED
            ]
            return declined[-1] if declined else None
        return None

    def _check_disputable(self, merchant_id: str, topic: str, decision: Decision | None) -> Decision:
        if decision is None:
            raise GrievanceInvalid(
                "there is no decision to dispute", {"decision_id": "no decision to dispute"}
            )
        wanted = DecisionOutcome.DECLINED if topic == "CLAIM_DECLINED" else DecisionOutcome.APPROVED
        if decision.outcome is not wanted:
            raise GrievanceInvalid(
                "the decision does not fit this topic", {"decision_id": "does not fit the topic"}
            )
        if self._store.latest_final_decision(merchant_id) != decision:
            # The shared case-opening code disputes the merchant's latest settled decision (a documented limit).
            raise GrievanceInvalid(
                "only the latest settled decision can be disputed",
                {"decision_id": "not the latest settled decision"},
            )
        return decision

    def _existing(self, merchant_id: str, decision_id: str | None, topic: str) -> Grievance | None:
        return next(
            (
                g
                for g in self._book.for_merchant(merchant_id)
                if g.status == "OPEN" and g.topic == topic and g.decision_id == decision_id
            ),
            None,
        )

    def _review_case(self, merchant_id: str) -> Case:
        cases = [
            c
            for c in self._store.cases(CaseStatus.OPEN)
            if c.merchant_id == merchant_id and c.kind in OPEN_REVIEW_KINDS
        ]
        if not cases:
            raise GrievanceInvalid("there is no open review to ask about", {"topic": "no open review case"})
        return cases[-1]

    async def open(
        self,
        *,
        merchant_id: str,
        topic: str,
        text: str,
        lang: str,
        decision_id: str | None,
        now: datetime,
        open_dispute: OpenDispute,
        notify: NotifyDispute,
    ) -> OpenResult:
        now = require_aware(now)
        if topic not in ladder.TOPICS:
            raise GrievanceInvalid("unknown topic", {"topic": "not one of the listed topics"})
        if len(text) > MAX_TEXT_CHARS:
            raise GrievanceInvalid("text is too long", {"text": f"at most {MAX_TEXT_CHARS} characters"})
        decision = self._decision_for(merchant_id, topic, decision_id)
        if topic in ladder.DISPUTE_TOPICS:
            decision = self._check_disputable(merchant_id, topic, decision)
        resolved_id = decision.id if decision is not None else None
        existing = self._existing(merchant_id, resolved_id, topic)
        if existing is not None:
            return OpenResult(existing, created=False)
        case = await self._case_for(merchant_id, topic, text, open_dispute, notify)
        respondent = ladder.respondent_for(topic)
        grievance = Grievance(
            id=self._ids.next("grievance"),
            merchant_id=merchant_id,
            decision_id=resolved_id,
            case_id=case.id if case is not None else None,
            kind=ladder.kind_for(topic),  # type: ignore[arg-type]
            topic=topic,
            respondent=respondent,  # type: ignore[arg-type]
            text=text,
            lang=lang,
            status="OPEN",
            opened_at=now,
            due_by=case.due_by if case is not None else None,
            current_step=ladder.ladder_for(respondent)[0].id,
            steps=_first_steps(respondent, now),
        )
        self._book.add(grievance)
        self._audit.append(
            at=now,
            actor=f"merchant:{merchant_id}",
            action="grievance.open",
            subject_type="grievance",
            subject_id=grievance.id,
            data={
                "merchant_id": merchant_id,
                "topic": topic,
                "respondent": respondent,
                "decision_id": resolved_id,
                "case_id": grievance.case_id,
                "first_step": grievance.current_step,
            },
        )
        logger.info("grievance %s opened (%s, %s)", grievance.id, topic, respondent)
        return OpenResult(grievance, created=True)

    async def _case_for(
        self, merchant_id: str, topic: str, text: str, open_dispute: OpenDispute, notify: NotifyDispute
    ) -> Case | None:
        if topic == "CLAIM_SLOW":
            return self._review_case(merchant_id)
        if topic not in ladder.DISPUTE_TOPICS:
            return None
        outcome = await open_dispute(merchant_id, text)
        if outcome.case is None:
            raise GrievanceInvalid(
                "there is no decision to dispute", {"decision_id": "no decision to dispute"}
            )
        await notify(outcome.case, outcome.already_open)
        return outcome.case

    # ------------------------------------------------------------------ escalate and resolve
    def _owned(self, merchant_id: str, grievance_id: str) -> Grievance:
        grievance = self._book.get(grievance_id)
        if grievance.merchant_id != merchant_id:
            raise KeyError(f"unknown grievance {grievance_id}")
        return grievance

    def _receipt_seq(self, decision_id: str | None, now: datetime) -> int | None:
        if decision_id is None:
            return None
        entries = (
            self._audit.latest(action=action, subject_id=decision_id, at_or_before=now)
            for action in DECISION_AUDIT_ACTIONS
        )
        return max((e.seq for e in entries if e is not None), default=None)

    def _check_filed_on(self, filed_on: date | None, grievance: Grievance, now: datetime) -> None:
        if filed_on is None:
            return
        today = now.astimezone(IST).date()
        if filed_on > today or filed_on < grievance.opened_at.astimezone(IST).date():
            raise GrievanceInvalid(
                "filed_on is outside the grievance's dates",
                {"filed_on": "between the day it was opened and today"},
            )

    def escalate(
        self, *, merchant_id: str, grievance_id: str, escalate_from: str, filed_on: date | None, now: datetime
    ) -> Grievance:
        now = require_aware(now)
        grievance = self._owned(merchant_id, grievance_id)
        if grievance.status != "OPEN":
            raise GrievanceConflict("the grievance is already resolved")
        if escalate_from != grievance.current_step:
            raise GrievanceConflict("escalate_from is not the current step")
        ids = [s.id for s in grievance.steps]
        position = ids.index(grievance.current_step)
        if position + 1 >= len(ids):
            raise GrievanceConflict("this is the last step")
        self._check_filed_on(filed_on, grievance, now)
        target = ids[position + 1]
        entered = ladder.filed_on_start(filed_on) if filed_on and target in ladder.FILED_STEPS else now
        steps = tuple(
            step.model_copy(update={"state": "DONE", "outcome": "ESCALATED"})
            if index == position
            else step.model_copy(update={"state": "ACTIVE", "entered_at": entered})
            if index == position + 1
            else step
            for index, step in enumerate(grievance.steps)
        )
        seq = self._receipt_seq(grievance.decision_id, now)
        updated = grievance.model_copy(
            update={"current_step": target, "steps": steps, "receipt_audit_seq": seq}
        )
        self._book.replace(updated)
        clock_kind = ladder.STEP_BY_ID[target].clock_kind
        self._audit.append(
            at=now,
            actor=f"merchant:{merchant_id}",
            action="grievance.escalate",
            subject_type="grievance",
            subject_id=grievance.id,
            data={
                "merchant_id": merchant_id,
                "from": grievance.current_step,
                "to": target,
                "filed_on": filed_on.isoformat() if filed_on else None,
                "clock_kind": clock_kind,
                "decision_id": grievance.decision_id,
                "receipt_audit_seq": seq,
            },
        )
        return updated

    def resolve(self, *, merchant_id: str, grievance_id: str, now: datetime) -> Grievance:
        now = require_aware(now)
        grievance = self._owned(merchant_id, grievance_id)
        if grievance.status != "OPEN":
            raise GrievanceConflict("the grievance is already resolved")
        steps = tuple(
            step.model_copy(update={"state": "DONE", "outcome": "SOLVED"})
            if step.id == grievance.current_step
            else step
            for step in grievance.steps
        )
        updated = grievance.model_copy(update={"status": "RESOLVED", "steps": steps, "resolved_at": now})
        self._book.replace(updated)
        self._audit.append(
            at=now,
            actor=f"merchant:{merchant_id}",
            action="grievance.resolve",
            subject_type="grievance",
            subject_id=grievance.id,
            data={"merchant_id": merchant_id, "step": grievance.current_step},
        )
        return updated
