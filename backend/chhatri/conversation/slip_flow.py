"""Hospital-slip photo → personal claim → reply (SPEC §13.5 silent check-in, §13.6 HUMAN, §9.3).

- No open silence check-in → PHOTO_NOT_NEEDED; no claim is filed.
- The SlipReader reads the photo (audited ``slip.read``: source, confidence, document type and which
  fields were read — never the patient's name). A reader failure (``IntegrationError``) is logged and
  the claim goes ahead with an empty, zero-confidence extraction, so SLIP_READABLE fails and a
  claims officer looks at the photo (deck: "Slip unclear … Goes to a human: Always").
- ``submit_personal_claim`` decides through the policy engine (the orchestrator):
  APPROVED → no reply yet: the money message (PERSONAL_PAID + card + Soundbox) is sent at credit
  time by ``notify_personal_paid`` (binding decision B2), so the merchant is never told "credited"
  before the rail credits it; REFERRED → the SLIP_TO_HUMAN variant + CASE_CHIP with the review case
  (looked up by decision id; if the orchestrator has not opened it yet the chip is omitted and an
  error is logged); DECLINED → PERSONAL_DECLINED with the first failing HARD check's reason.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from chhatri.conversation.messages import bilingual, name_facts
from chhatri.conversation.outbox import AI_ACTOR, Outbox, Outgoing
from chhatri.conversation.ports import ClaimsPort, ConversationStore
from chhatri.conversation.reasons import declined_reason_key, slip_to_human_key
from chhatri.conversation.replies import case_chip
from chhatri.domain.enums import DecisionOutcome
from chhatri.domain.models import Decision, Merchant, Message, SlipExtraction
from chhatri.integrations.base import IntegrationError, SlipReader
from chhatri.precheck.chat import chat_outgoing
from chhatri.precheck.clean import UncleanableImage
from chhatri.precheck.service import PrecheckConflict, SlipPrecheckService
from chhatri.store.protocols import AuditSink

logger = logging.getLogger(__name__)

READ_FAILED_SOURCE: Final = "read-failed"
SLIP_FIELDS: Final = ("patient_name", "admission_date", "discharge_date", "hospital_name", "document_type")


@dataclass(frozen=True, slots=True)
class FiledSlip:
    """A slip filed as a personal claim: the engine's decision and what the merchant was told."""

    decision: Decision
    messages: tuple[Message, ...]


PrecheckResolver = Callable[[], SlipPrecheckService | None]
"""None while `n3_slip_precheck` is off: the photo is read and decided in one step, exactly as before."""


def _no_precheck() -> SlipPrecheckService | None:
    return None


def _everyone_agreed(merchant_id: str) -> bool:
    return True  # `n6_consents` off: the slip gate passes


class SlipFlow:
    """Replies to an inbound slip photo."""

    def __init__(
        self,
        *,
        outbox: Outbox,
        claims: ClaimsPort,
        store: ConversationStore,
        reader: SlipReader,
        audit: AuditSink,
        precheck: PrecheckResolver = _no_precheck,
        slip_consent: Callable[[str], bool] = _everyone_agreed,
    ) -> None:
        self._precheck = precheck
        self._slip_consent = slip_consent
        self._outbox = outbox
        self._claims = claims
        self._store = store
        self._reader = reader
        self._audit = audit

    async def reply(self, merchant: Merchant, image: bytes, mime: str, media_id: str) -> tuple[Message, ...]:
        if self._claims.open_silence(merchant.id) is None:
            return (await self._outbox.send(merchant, Outgoing.text("PHOTO_NOT_NEEDED")),)
        if not self._slip_consent(merchant.id):  # N6: nothing is read, and the check-in stays open
            return (await self._outbox.send(merchant, Outgoing.text("SLIP_CONSENT_NEEDED")),)
        service = self._precheck()
        if service is not None:
            return await self._show_precheck(service, merchant, image, mime)
        slip = await self._read(merchant, image, mime, media_id)
        return (await self.file(merchant, slip, media_id)).messages

    async def file(self, merchant: Merchant, slip: SlipExtraction, media_id: str) -> FiledSlip:
        """Decide a personal claim for `slip` and tell the merchant (the pre-check's confirm calls this too)."""
        decision = await self._claims.submit_personal_claim(merchant.id, slip, media_id)
        if decision.merchant_id != merchant.id:
            raise ValueError(f"decision {decision.id} is for {decision.merchant_id}, not {merchant.id}")
        if decision.outcome is DecisionOutcome.APPROVED:
            return FiledSlip(decision, ())
        if decision.outcome is DecisionOutcome.REFERRED:
            return FiledSlip(decision, await self._referred(merchant, decision))
        return FiledSlip(decision, (await self._declined(merchant, decision),))

    async def _show_precheck(
        self, service: SlipPrecheckService, merchant: Merchant, image: bytes, mime: str
    ) -> tuple[Message, ...]:
        """Flag on: read the photo and show it. Nothing is decided until the merchant confirms (fs-02 8.3)."""
        try:
            pc = await service.precheck(merchant.id, image, mime)
        except PrecheckConflict:
            return (await self._outbox.send(merchant, Outgoing.text("SLIP_PHOTO_LIMIT")),)
        except UncleanableImage:
            return (await self._outbox.send(merchant, Outgoing.text("SLIP_RETAKE_CLEAR")),)
        return (await self._outbox.send(merchant, chat_outgoing(pc, minimum=service.minimum)),)

    async def _read(self, merchant: Merchant, image: bytes, mime: str, media_id: str) -> SlipExtraction:
        try:
            slip = await self._reader.read_slip(image, mime)
        except IntegrationError as exc:
            logger.error("conversation: slip %s unreadable by the reader: %s", media_id, exc.safe_message)
            slip = SlipExtraction(confidence=0.0, source=READ_FAILED_SOURCE)
        self._audit.append(
            at=self._outbox.now(),
            actor=AI_ACTOR,
            action="slip.read",
            subject_type="media",
            subject_id=media_id,
            data={
                "merchant_id": merchant.id,
                "source": slip.source,
                "confidence": slip.confidence,
                "document_type": slip.document_type,
                "fields_read": [name for name in SLIP_FIELDS if getattr(slip, name) is not None],
            },
        )
        return slip

    async def _referred(self, merchant: Merchant, decision: Decision) -> tuple[Message, ...]:
        told = await self._outbox.send(merchant, Outgoing.text(slip_to_human_key(decision)))
        case = next((c for c in self._store.cases() if c.decision_id == decision.id), None)
        if case is None:
            logger.error(
                "conversation: REFERRED decision %s has no review case yet; chip omitted", decision.id
            )
            return (told,)
        return (told, await self._outbox.send(merchant, case_chip(case.id)))

    async def _declined(self, merchant: Merchant, decision: Decision) -> Message:
        reason_hi, reason_en = bilingual(declined_reason_key(decision))
        reply = Outgoing.text(
            "PERSONAL_DECLINED", reason_hi=reason_hi, reason_en=reason_en, **name_facts(merchant)
        )
        return await self._outbox.send(merchant, reply)
