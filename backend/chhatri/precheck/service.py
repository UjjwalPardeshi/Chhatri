"""SlipPrecheckService: read a slip, show what was read, and file nothing until the merchant confirms (N3, fs-02 7.3).

One service per loaded scenario. A photo is cleaned (no metadata), read by the provider chain (Gemini vision, then Sarvam,
the simulator only when nothing live applies), validated, and put through the closed status table. The merchant then
confirms the fields, sends another photo, or sends the slip to the team. The policy engine alone decides the claim:
confirming or sending files the slip as read through the BUILT `submit_personal_claim` and the engine runs every check.

With rule `personal.require_doctor_confirmation` on (`require_doctor`), confirming the fields files nothing yet: the
pre-check waits (AWAITING_CONSENT) for the answer to "may we ask your doctor?" (`consent_step`). The answer is written
to the consent ledger first and the READY read is then filed exactly as before; a No is filed too (the engine refers it).
Each refusal carries a code (`PrecheckConflict.code`) the routes and the chat turn into a friendly sentence.

Audit rows hold ids, codes and counts. They never hold a patient name, a date or a hospital from the slip (fs-02 14).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Collection, Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime
from types import MappingProxyType
from typing import Any, Final, Protocol

from chhatri.ai.labels import AiLabel, AiProvider, FallbackReason
from chhatri.clock import Clock
from chhatri.domain.models import Case, Decision, Message, SlipExtraction
from chhatri.integrations.slip_chain import SlipChain
from chhatri.precheck.clean import clean_image
from chhatri.precheck.consent_step import ConsentQuestion, consent_question
from chhatri.precheck.fields import kept, reject
from chhatri.precheck.model import (
    CONSENT_ACTIONS,
    MAX_PHOTOS,
    OPEN_STATUSES,
    Action,
    ConfirmedAs,
    Precheck,
    PrecheckStatus,
    Reason,
)
from chhatri.precheck.rules import decide, is_last_photo
from chhatri.store.protocols import AuditSink

logger = logging.getLogger(__name__)

AI_ACTOR: Final = "ai-agent"
READ_FAILED_SOURCE: Final = "read-failed"
SLIP_FIELDS: Final = (
    "patient_name",
    "admission_date",
    "discharge_date",
    "hospital_name",
    "doctor_name",
    "doctor_registration_no",
    "document_type",
)
# Proposed budgets (fs-02 7.3.1 and open question 7): the whole chain fits the 10 s read-time target of section 15
# for a Gemini read, and leaves Sarvam a fair try when Gemini fails fast. Tuned in the Wave 2 rehearsal.
LINK_TIMEOUTS: Final[Mapping[AiProvider, float]] = MappingProxyType(
    {AiProvider.GEMINI: 6.0, AiProvider.SARVAM: 12.0}
)
DEFAULT_TIMEOUT_S: Final = 10.0
TOTAL_TIMEOUT_S: Final = 20.0


class PrecheckError(Exception):
    """Base of the refusals the routes turn into 404 and 409."""


class PrecheckNotFound(PrecheckError):
    """An unknown pre-check, or one that belongs to another merchant."""


class PrecheckConflict(PrecheckError):
    """The request does not fit the state: no open check-in, photos used up, already confirmed, wrong action.

    `code`: no_checkin, photo_limit, already_confirmed, superseded, not_ready, ready_not_team, consent_pending,
    no_consent_question or no_read (the 409 `code` of the routes)."""

    def __init__(self, message: str, code: str = "conflict") -> None:
        super().__init__(message)
        self.code = code


class OpenSilence(Protocol):
    def open_silence(self, merchant_id: str) -> date | None: ...


class MediaStore(Protocol):
    def put_media(self, data: bytes, mime: str, media_id: str) -> None: ...
    def cases(self) -> tuple[Case, ...]: ...
    def replace_case(self, c: Case) -> None: ...


class Ids(Protocol):
    def next(self, kind: str) -> str: ...


@dataclass(frozen=True, slots=True)
class Filed:
    """What filing a slip produced: the engine's decision and the messages the merchant got."""

    decision: Decision
    messages: tuple[Message, ...]
    doctor_pending: bool = False  # the pipeline is still asking the doctor: the outcome is interim


Filer = Callable[[str, SlipExtraction, str], Awaitable[Filed]]
ConsentAsker = Callable[[str, ConsentQuestion], Awaitable[Message]]


class ConsentRecorder(Protocol):
    """The consent ledger (`consent.verification.DoctorConsents`)."""

    def record(
        self,
        *,
        merchant_id: str,
        granted: bool,
        at: datetime,
        source: str,
        precheck_id: str | None,
        checkin: date | None,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class Confirmation:
    """What one action did. While the doctor question waits: no outcome, the question in `consent`."""

    precheck: Precheck
    outcome: str | None
    case_id: str | None
    messages: tuple[Message, ...]
    consent: ConsentQuestion | None = None
    doctor_pending: bool = False


def _no_forced() -> Collection[str]:
    return frozenset()


class SlipPrecheckService:
    def __init__(
        self,
        *,
        ids: Ids,
        clock: Clock,
        audit: AuditSink,
        store: MediaStore,
        claims: OpenSilence,
        chain: SlipChain,
        minimum: float,
        filer: Filer,
        forced: Callable[[], Collection[str]] = _no_forced,
        require_doctor: bool = False,
        asker: ConsentAsker | None = None,
        consents: ConsentRecorder | None = None,
    ) -> None:
        self._ids = ids
        self._clock = clock
        self._audit = audit
        self._store = store
        self._claims = claims
        self._chain = chain
        self._minimum = minimum
        self._filer = filer
        self._forced = forced
        self._require_doctor = require_doctor
        self._asker = asker
        self._consents = consents
        self._items: Mapping[str, Precheck] = MappingProxyType({})
        self._lock = asyncio.Lock()

    @property
    def minimum(self) -> float:
        return self._minimum

    @property
    def require_doctor(self) -> bool:
        return self._require_doctor

    def get(self, merchant_id: str, precheck_id: str) -> Precheck:
        found = self._items.get(precheck_id)
        if found is None or found.merchant_id != merchant_id:
            raise PrecheckNotFound(precheck_id)
        return found

    def for_merchant(self, merchant_id: str) -> tuple[Precheck, ...]:
        return tuple(pc for pc in self._items.values() if pc.merchant_id == merchant_id)

    def open_for(self, merchant_id: str) -> Precheck | None:
        """The latest pre-check of the open check-in while it still waits for the merchant, else None."""
        checkin = self._claims.open_silence(merchant_id)
        if checkin is None:
            return None
        mine = [pc for pc in self.for_merchant(merchant_id) if pc.checkin == checkin.isoformat()]
        latest = max(mine, key=lambda pc: pc.attempt, default=None)
        return latest if latest is not None and latest.status in OPEN_STATUSES else None

    # ------------------------------------------------------------------ read

    async def precheck(self, merchant_id: str, image: bytes, mime: str) -> Precheck:
        """Read one photo and return its pre-check. `UncleanableImage` for bytes that cannot be decoded."""
        async with self._lock:
            checkin = self._claims.open_silence(merchant_id)
            if checkin is None:
                raise PrecheckConflict("no silence check-in is open for this merchant", "no_checkin")
            earlier = [pc for pc in self.for_merchant(merchant_id) if pc.checkin == checkin.isoformat()]
            if len(earlier) >= MAX_PHOTOS:
                raise PrecheckConflict(
                    "the photos for this check-in are used up; send it to the team", "photo_limit"
                )
            cleaned, cleaned_mime = clean_image(image, mime)
            media_id = self._ids.next("media")
            self._store.put_media(cleaned, cleaned_mime, media_id)
            result = await self._chain.read_with_label(
                cleaned,
                cleaned_mime,
                timeout_s=DEFAULT_TIMEOUT_S,
                original=image,
                original_mime_type=mime,
                accept=reject,
                forced=self._forced(),
                link_timeouts=LINK_TIMEOUTS,
                total_timeout_s=TOTAL_TIMEOUT_S,
            )
            slip, injected = self._screened(result.value, result.label)
            attempt = len(earlier) + 1
            verdict = decide(
                slip,
                today=self._clock.now().date(),
                minimum=self._minimum,
                injected=injected,
                last_photo=is_last_photo(attempt),
                require_doctor=self._require_doctor,
            )
            created = Precheck(
                id=self._ids.next("precheck"),
                merchant_id=merchant_id,
                checkin=checkin.isoformat(),
                attempt=attempt,
                media_id=media_id,
                status=verdict.status,
                reason=verdict.reason,
                guidance_key=verdict.guidance_key,
                slip=slip,
                gate_passed=verdict.gate_passed,
                label=result.label,
                created_at=self._clock.now(),
            )
            self._store_new(created, superseding=earlier)
            self._audit_read(created)
            return created

    @staticmethod
    def _screened(value: SlipExtraction | None, label: AiLabel) -> tuple[SlipExtraction | None, bool]:
        """The kept read, and whether the text was flagged. The simulated read is screened here too: it skips `accept`."""
        injected = value is None and label.fallback_reason is FallbackReason.INJECTION_SUSPECTED
        if value is None:
            return None, injected
        rejection = reject(value)
        if rejection is None:
            return kept(value), False
        return None, rejection.reason is FallbackReason.INJECTION_SUSPECTED

    def _store_new(self, created: Precheck, *, superseding: list[Precheck]) -> None:
        changed = {
            pc.id: replace(pc, status=PrecheckStatus.SUPERSEDED)
            for pc in superseding
            if pc.status in OPEN_STATUSES
        }
        self._items = MappingProxyType({**self._items, **changed, created.id: created})

    def _audit_read(self, pc: Precheck) -> None:
        slip = pc.slip
        self._audit.append(
            at=pc.created_at,
            actor=AI_ACTOR,
            action="slip.read",
            subject_type="media",
            subject_id=pc.media_id,
            data={
                "merchant_id": pc.merchant_id,
                "precheck_id": pc.id,
                "attempt": pc.attempt,
                "source": READ_FAILED_SOURCE if slip is None else slip.source,
                "confidence": 0.0 if slip is None else slip.confidence,
                "document_type": None if slip is None else slip.document_type,
                "fields_read": []
                if slip is None
                else [n for n in SLIP_FIELDS if getattr(slip, n) is not None],
                **pc.label.to_wire(),
            },
        )
        self._audit.append(
            at=pc.created_at,
            actor=AI_ACTOR,
            action="precheck.shown",
            subject_type="precheck",
            subject_id=pc.id,
            data={
                "merchant_id": pc.merchant_id,
                "precheck_id": pc.id,
                "status": pc.status.value,
                "reason": None if pc.reason is None else pc.reason.value,
                "attempt": pc.attempt,
            },
        )

    # ------------------------------------------------------------------ confirm

    async def confirm(
        self, merchant_id: str, precheck_id: str, action: Action, *, source: str = "APP"
    ) -> Confirmation:
        """One merchant action. `source` is APP (the routes) or CHAT (the conversation), for the consent ledger.

        `CONFIRM` while READY files the claim, or with the doctor rule on asks the doctor question and files nothing;
        `CONSENT_YES` / `CONSENT_NO` answer it (ledger first, then the READY read is filed); `SEND_TO_TEAM` while
        RETAKE or NEEDS_TEAM files the slip for a person."""
        async with self._lock:
            pc = self.get(merchant_id, precheck_id)
            _check_action(pc, action)
            if self._claims.open_silence(merchant_id) is None:
                raise PrecheckConflict("the claim for this check-in was already filed", "no_checkin")
            if action is Action.CONFIRM and self._require_doctor:
                return await self._ask_consent(pc)
            if action in CONSENT_ACTIONS:
                return await self._answer_consent(pc, action, source)
            filed = await self._filer(merchant_id, self._slip_to_file(pc, action), pc.media_id)
            confirmed_as = (
                ConfirmedAs.FIELDS_CONFIRMED if action is Action.CONFIRM else ConfirmedAs.SENT_TO_TEAM
            )
            return self._filed(replace(pc, confirmed_as=confirmed_as), action, filed)

    async def _ask_consent(self, pc: Precheck) -> Confirmation:
        if pc.slip is None:
            raise PrecheckConflict("there is no read to confirm", "no_read")
        question = consent_question(pc)
        waiting = replace(
            pc,
            status=PrecheckStatus.AWAITING_CONSENT,
            confirmed_as=ConfirmedAs.FIELDS_CONFIRMED,
            fields_confirmed_at=self._clock.now(),
        )
        self._items = MappingProxyType({**self._items, waiting.id: waiting})
        self._audit_confirmed(waiting, Action.CONFIRM, awaiting_consent=True)
        sent = () if self._asker is None else (await self._asker(pc.merchant_id, question),)
        waiting = replace(waiting, messages=tuple(m.id for m in sent))
        self._items = MappingProxyType({**self._items, waiting.id: waiting})
        return Confirmation(waiting, None, None, sent, consent=question)

    async def _answer_consent(self, pc: Precheck, action: Action, source: str) -> Confirmation:
        if pc.slip is None:  # an AWAITING_CONSENT pre-check always holds the READY read
            raise PrecheckConflict("there is no read to confirm", "no_read")
        granted = action is Action.CONSENT_YES
        now = self._clock.now()
        if self._consents is not None:  # the ledger first: the pipeline reads it while deciding
            self._consents.record(
                merchant_id=pc.merchant_id,
                granted=granted,
                at=now,
                source=source,
                precheck_id=pc.id,
                checkin=date.fromisoformat(pc.checkin),
            )
        filed = await self._filer(pc.merchant_id, pc.slip, pc.media_id)
        answered = replace(pc, consent=granted, consent_at=now)
        done = self._filed(answered, action, filed)
        return replace(done, consent=consent_question(pc))

    def _filed(self, pc: Precheck, action: Action, filed: Filed) -> Confirmation:
        """Store the CONFIRMED pre-check, audit it and give the officer's case its pre-check lines."""
        decision = filed.decision
        done = replace(
            pc,
            status=PrecheckStatus.CONFIRMED,
            claim_id=decision.claim_id,
            decision_id=decision.id,
            messages=tuple(m.id for m in filed.messages),
        )
        self._items = MappingProxyType({**self._items, done.id: done})
        self._audit_confirmed(done, action)
        case = next((c for c in self._store.cases() if c.decision_id == decision.id), None)
        if case is not None:  # N3.11: the officer's evidence says how the read was made and filed
            self._store.replace_case(
                case.model_copy(update={"evidence": {**case.evidence, "precheck": _evidence_lines(done)}})
            )
        return Confirmation(
            done,
            decision.outcome.value,
            None if case is None else case.id,
            filed.messages,
            doctor_pending=filed.doctor_pending,
        )

    @staticmethod
    def _slip_to_file(pc: Precheck, action: Action) -> SlipExtraction:
        """The slip as read. A flagged read is discarded and the BUILT empty read is filed instead (fs-02 7.3.6)."""
        if action is Action.SEND_TO_TEAM and (pc.slip is None or pc.reason is Reason.INJECTION_SUSPECTED):
            return SlipExtraction(confidence=0.0, source=READ_FAILED_SOURCE)
        if pc.slip is None:
            raise PrecheckConflict("there is no read to confirm", "no_read")
        return pc.slip

    def _audit_confirmed(self, pc: Precheck, action: Action, *, awaiting_consent: bool = False) -> None:
        extra = {"awaiting_consent": True} if awaiting_consent else {}
        self._audit.append(
            at=self._clock.now(),
            actor=f"merchant:{pc.merchant_id}",
            action="precheck.confirmed",
            subject_type="precheck",
            subject_id=pc.id,
            data={
                "merchant_id": pc.merchant_id,
                "precheck_id": pc.id,
                "action": action.value,
                **extra,
                "claim_id": pc.claim_id,
            },
        )


_CONFLICTS: Final[Mapping[PrecheckStatus, tuple[str, str]]] = MappingProxyType(
    {
        PrecheckStatus.CONFIRMED: ("already_confirmed", "this pre-check was already confirmed"),
        PrecheckStatus.SUPERSEDED: ("superseded", "a newer photo replaced this pre-check"),
    }
)


def _check_action(pc: Precheck, action: Action) -> None:
    """The action table: first match wins, each refusal with its code (design 2.3)."""
    closed = _CONFLICTS.get(pc.status)
    if closed is not None:
        raise PrecheckConflict(closed[1], closed[0])
    if pc.status is PrecheckStatus.AWAITING_CONSENT:
        if action not in CONSENT_ACTIONS:
            raise PrecheckConflict("please answer the question about the doctor first", "consent_pending")
        return
    if action in CONSENT_ACTIONS:
        raise PrecheckConflict(
            "no question about the doctor is waiting for this pre-check", "no_consent_question"
        )
    ready = pc.status is PrecheckStatus.READY
    if action is Action.CONFIRM and not ready:
        raise PrecheckConflict(
            "only a READY pre-check can be confirmed; send another photo or send it to the team", "not_ready"
        )
    if action is Action.SEND_TO_TEAM and ready:
        raise PrecheckConflict("a READY pre-check is confirmed, not sent to the team", "ready_not_team")


def _evidence_lines(pc: Precheck) -> dict[str, Any]:
    """The pre-check lines of the officer's evidence (fs-02 13.2): ids, codes and counts, never a slip value."""
    return {
        "precheck_id": pc.id,
        "filed_as": pc.confirmed_as.value if pc.confirmed_as is not None else None,
        "photos": pc.attempt,
        "injection_suspected": pc.reason is Reason.INJECTION_SUSPECTED,
        "doctor_consent": None if pc.consent is None else ("GIVEN" if pc.consent else "REFUSED"),
        "mode": pc.label.mode.value,
        "provider": pc.label.provider.value,
        "model": pc.label.model,
        "fallback_reason": pc.label.fallback_reason.value if pc.label.fallback_reason else None,
    }


__all__ = [
    "Confirmation",
    "ConsentAsker",
    "ConsentRecorder",
    "Filed",
    "PrecheckConflict",
    "PrecheckError",
    "PrecheckNotFound",
    "SlipPrecheckService",
]
