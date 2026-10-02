"""SlipPrecheckService: read a slip, show what was read, and file nothing until the merchant confirms (N3, fs-02 7.3).

One service per loaded scenario. A photo is cleaned (no metadata), read by the provider chain (Gemini vision, then Sarvam,
the simulator only when nothing live applies), validated, and put through the closed status table. The merchant then
confirms the fields, sends another photo, or sends the slip to the team. The policy engine alone decides the claim:
confirming or sending files the slip as read through the BUILT `submit_personal_claim` and the engine runs every check.

Audit rows hold ids, codes and counts. They never hold a patient name, a date or a hospital from the slip (fs-02 14).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Collection, Mapping
from dataclasses import dataclass, replace
from datetime import date
from types import MappingProxyType
from typing import Any, Final, Protocol

from chhatri.ai.labels import AiLabel, AiProvider, FallbackReason
from chhatri.clock import Clock
from chhatri.domain.models import Case, Decision, Message, SlipExtraction
from chhatri.integrations.slip_chain import SlipChain
from chhatri.precheck.clean import clean_image
from chhatri.precheck.fields import kept, reject
from chhatri.precheck.model import MAX_PHOTOS, Action, ConfirmedAs, Precheck, PrecheckStatus, Reason
from chhatri.precheck.rules import decide, is_last_photo
from chhatri.store.protocols import AuditSink

logger = logging.getLogger(__name__)

AI_ACTOR: Final = "ai-agent"
READ_FAILED_SOURCE: Final = "read-failed"
SLIP_FIELDS: Final = ("patient_name", "admission_date", "discharge_date", "hospital_name", "document_type")
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
    """The request does not fit the state: no open check-in, photos used up, already confirmed, wrong action."""


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


Filer = Callable[[str, SlipExtraction, str], Awaitable[Filed]]


@dataclass(frozen=True, slots=True)
class Confirmation:
    precheck: Precheck
    outcome: str
    case_id: str | None
    messages: tuple[Message, ...]


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
        self._items: Mapping[str, Precheck] = MappingProxyType({})
        self._lock = asyncio.Lock()

    @property
    def minimum(self) -> float:
        return self._minimum

    def get(self, merchant_id: str, precheck_id: str) -> Precheck:
        found = self._items.get(precheck_id)
        if found is None or found.merchant_id != merchant_id:
            raise PrecheckNotFound(precheck_id)
        return found

    def for_merchant(self, merchant_id: str) -> tuple[Precheck, ...]:
        return tuple(pc for pc in self._items.values() if pc.merchant_id == merchant_id)

    # ------------------------------------------------------------------ read

    async def precheck(self, merchant_id: str, image: bytes, mime: str) -> Precheck:
        """Read one photo and return its pre-check. `UncleanableImage` for bytes that cannot be decoded."""
        async with self._lock:
            checkin = self._claims.open_silence(merchant_id)
            if checkin is None:
                raise PrecheckConflict("no silence check-in is open for this merchant")
            earlier = [pc for pc in self.for_merchant(merchant_id) if pc.checkin == checkin.isoformat()]
            if len(earlier) >= MAX_PHOTOS:
                raise PrecheckConflict("the photos for this check-in are used up; send it to the team")
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
        open_states = {PrecheckStatus.READY, PrecheckStatus.RETAKE, PrecheckStatus.NEEDS_TEAM}
        changed = {
            pc.id: replace(pc, status=PrecheckStatus.SUPERSEDED)
            for pc in superseding
            if pc.status in open_states
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

    async def confirm(self, merchant_id: str, precheck_id: str, action: Action) -> Confirmation:
        """File the claim: `CONFIRM` while READY, `SEND_TO_TEAM` while RETAKE or NEEDS_TEAM."""
        async with self._lock:
            pc = self.get(merchant_id, precheck_id)
            self._check_action(pc, action)
            if self._claims.open_silence(merchant_id) is None:
                raise PrecheckConflict("the claim for this check-in was already filed")
            filed = await self._filer(merchant_id, self._slip_to_file(pc, action), pc.media_id)
            decision = filed.decision
            done = replace(
                pc,
                status=PrecheckStatus.CONFIRMED,
                confirmed_as=ConfirmedAs.FIELDS_CONFIRMED
                if action is Action.CONFIRM
                else ConfirmedAs.SENT_TO_TEAM,
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
                done, decision.outcome.value, None if case is None else case.id, filed.messages
            )

    @staticmethod
    def _check_action(pc: Precheck, action: Action) -> None:
        if pc.status is PrecheckStatus.CONFIRMED:
            raise PrecheckConflict("this pre-check was already confirmed")
        if pc.status is PrecheckStatus.SUPERSEDED:
            raise PrecheckConflict("a newer photo replaced this pre-check")
        ready = pc.status is PrecheckStatus.READY
        if action is Action.CONFIRM and not ready:
            raise PrecheckConflict(
                "only a READY pre-check can be confirmed; send another photo or send it to the team"
            )
        if action is Action.SEND_TO_TEAM and ready:
            raise PrecheckConflict("a READY pre-check is confirmed, not sent to the team")

    @staticmethod
    def _slip_to_file(pc: Precheck, action: Action) -> SlipExtraction:
        """The slip as read. A flagged read is discarded and the BUILT empty read is filed instead (fs-02 7.3.6)."""
        if action is Action.SEND_TO_TEAM and (pc.slip is None or pc.reason is Reason.INJECTION_SUSPECTED):
            return SlipExtraction(confidence=0.0, source=READ_FAILED_SOURCE)
        if pc.slip is None:
            raise PrecheckConflict("there is no read to confirm")
        return pc.slip

    def _audit_confirmed(self, pc: Precheck, action: Action) -> None:
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
                "claim_id": pc.claim_id,
            },
        )


def _evidence_lines(pc: Precheck) -> dict[str, Any]:
    """The pre-check lines of the officer's evidence (fs-02 13.2): ids, codes and counts, never a slip value."""
    return {
        "precheck_id": pc.id,
        "filed_as": pc.confirmed_as.value if pc.confirmed_as is not None else None,
        "photos": pc.attempt,
        "injection_suspected": pc.reason is Reason.INJECTION_SUSPECTED,
        "mode": pc.label.mode.value,
        "provider": pc.label.provider.value,
        "model": pc.label.model,
        "fallback_reason": pc.label.fallback_reason.value if pc.label.fallback_reason else None,
    }


__all__ = [
    "Confirmation",
    "Filed",
    "PrecheckConflict",
    "PrecheckError",
    "PrecheckNotFound",
    "SlipPrecheckService",
]
