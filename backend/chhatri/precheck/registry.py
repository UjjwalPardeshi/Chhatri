"""One pre-check service per loaded scenario, built the first time a request needs it (N3, fs-02 8.1 and 8.3).

The service lives as long as the scenario's `Store`, which every load and reset replaces, so a scenario load clears the
pre-checks and restarts the `PC-` ids with the rest of the runtime (data-model 5.12). While `n3_slip_precheck` is off the
resolver answers None, and the photo route and the chat read and decide in one step as before. With rule
`personal.require_doctor_confirmation` on, confirming asks the doctor question through the conversation and the answer
goes to the run's consent book (`consent.verification`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary

from chhatri.consent.verification import verification_consents
from chhatri.domain.models import Message, SlipExtraction
from chhatri.features import is_enabled
from chhatri.integrations.slip_chain import SlipChain
from chhatri.precheck.consent_step import ConsentQuestion
from chhatri.precheck.service import Filed, SlipPrecheckService

if TYPE_CHECKING:
    from chhatri.replay.state import Runtime

FLAG = "n3_slip_precheck"
_SERVICES: WeakKeyDictionary[object, SlipPrecheckService] = WeakKeyDictionary()


def precheck_service(rt: Runtime) -> SlipPrecheckService | None:
    """The scenario's service, or None while the flag is off."""
    if not is_enabled(FLAG, rt.static.settings):
        return None
    service = _SERVICES.get(rt.store)
    if service is None:
        service = build_service(rt)
        _SERVICES[rt.store] = service
    return service


def build_service(rt: Runtime, *, chain: SlipChain | None = None) -> SlipPrecheckService:
    """A service over `rt`; `chain` replaces the runtime's reader chain (tests give it fake providers)."""

    async def filer(merchant_id: str, slip: SlipExtraction, media_id: str) -> Filed:
        filed = await rt.conversation.file_slip(merchant_id, slip, media_id)
        return Filed(filed.decision, filed.messages, getattr(filed, "doctor_pending", False))

    async def asker(merchant_id: str, question: ConsentQuestion) -> Message:
        message: Message = await rt.conversation.ask_doctor_consent(merchant_id, question)
        return message

    return SlipPrecheckService(
        ids=rt.ids,
        clock=rt.clock,
        audit=rt.audit,
        store=rt.store,
        claims=rt.orchestrator,
        chain=chain or rt.integrations.slip_chain,
        minimum=rt.static.rules.personal.slip_confidence_min,
        filer=filer,
        require_doctor=rt.static.rules.personal.require_doctor_confirmation,
        asker=asker,
        consents=verification_consents(rt.store, ids=rt.ids, audit=rt.audit, settings=rt.static.settings),
    )
