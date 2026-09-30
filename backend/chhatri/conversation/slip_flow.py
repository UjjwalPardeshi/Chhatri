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
from typing import Final

from chhatri.conversation.messages import bilingual, name_facts
from chhatri.conversation.outbox import AI_ACTOR, Outbox, Outgoing
from chhatri.conversation.ports import ClaimsPort, ConversationStore
from chhatri.conversation.reasons import declined_reason_key, slip_to_human_key
from chhatri.conversation.replies import case_chip
from chhatri.domain.enums import DecisionOutcome
from chhatri.domain.models import Decision, Merchant, Message, SlipExtraction
from chhatri.integrations.base import IntegrationError, SlipReader
from chhatri.store.protocols import AuditSink

logger = logging.getLogger(__name__)

READ_FAILED_SOURCE: Final = "read-failed"
SLIP_FIELDS: Final = ("patient_name", "admission_date", "discharge_date", "hospital_name", "document_type")


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
    ) -> None:
        self._outbox = outbox
        self._claims = claims
        self._store = store
        self._reader = reader
        self._audit = audit

    async def reply(self, merchant: Merchant, image: bytes, mime: str, media_id: str) -> tuple[Message, ...]:
        if self._claims.open_silence(merchant.id) is None:
            return (await self._outbox.send(merchant, Outgoing.text("PHOTO_NOT_NEEDED")),)
        slip = await self._read(merchant, image, mime, media_id)
        decision = await self._claims.submit_personal_claim(merchant.id, slip, media_id)
        if decision.merchant_id != merchant.id:
            raise ValueError(f"decision {decision.id} is for {decision.merchant_id}, not {merchant.id}")
        if decision.outcome is DecisionOutcome.APPROVED:
            return ()
        if decision.outcome is DecisionOutcome.REFERRED:
            return await self._referred(merchant, decision)
        return (await self._declined(merchant, decision),)

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
