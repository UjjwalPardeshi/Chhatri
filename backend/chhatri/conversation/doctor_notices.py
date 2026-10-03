"""What the merchant hears while Chhatri asks the treating doctor (SPEC §9.2; called by the claim pipeline).

- ``check_started`` right after the claim is filed when the pipeline will still ask the doctor (the decision is
  interim): DOCTOR_CHECK_STARTED with the directory's names, or DOCTOR_WAITING when no name is known.
- ``asked`` when the question has gone out: DOCTOR_ASKED.
- ``answered`` when the doctor confirmed: DOCTOR_CONFIRMED_VISIT. A denial or no answer says nothing here: the decision
  that follows explains itself (PERSONAL_DECLINED, or SLIP_TO_HUMAN_* with the case chip).

Each message carries ``meta.doctor_check`` (STARTED, ASKED, CONFIRMED) and the names; ASKED and CONFIRMED also carry the
H26-style label of who answers (``mode`` LIVE when a real doctor's Telegram chat is asked, else SIMULATED or FALLBACK;
``provider`` telegram or simulated) so the console's chip is honest about a stand-in doctor. The doctor's contact, the
amount and the policy never appear.
"""

from __future__ import annotations

from typing import Final

from chhatri.conversation.outbox import Outbox, Outgoing
from chhatri.conversation.ports import MerchantDirectory
from chhatri.domain.enums import VerificationStatus
from chhatri.domain.models import Merchant, Message, SlipExtraction
from chhatri.precheck.consent_step import care_names

__all__ = ["DOCTOR_MODES", "DoctorNotices"]

DOCTOR_MODES: Final = frozenset({"LIVE", "SIMULATED", "FALLBACK"})
LIVE_PROVIDER: Final = "telegram"
STAND_IN_PROVIDER: Final = "simulated"


def _label(mode: str) -> dict[str, str]:
    if mode not in DOCTOR_MODES:
        raise ValueError(f"mode must be one of {sorted(DOCTOR_MODES)}, not {mode!r}")
    return {"mode": mode, "provider": LIVE_PROVIDER if mode == "LIVE" else STAND_IN_PROVIDER}


def _with_meta(out: Outgoing, meta: dict[str, object]) -> Outgoing:
    return Outgoing(key=out.key, kind=out.kind, text_hi=out.text_hi, text_en=out.text_en, meta=meta)


class DoctorNotices:
    """The doctor-check lines of the chat."""

    def __init__(self, *, outbox: Outbox, directory: MerchantDirectory) -> None:
        self._outbox = outbox
        self._directory = directory

    async def check_started(self, merchant: Merchant, slip: SlipExtraction | None) -> Message:
        names = care_names(slip)
        meta: dict[str, object] = {
            "doctor_check": "STARTED",
            "doctor_name": names.doctor_name,
            "hospital_name": names.hospital_name,
        }
        if names.doctor_name is None or names.hospital_name is None:
            return await self._outbox.send(merchant, _with_meta(Outgoing.text("DOCTOR_WAITING"), meta))
        out = Outgoing.text("DOCTOR_CHECK_STARTED", doctor=names.doctor_name, hospital=names.hospital_name)
        return await self._outbox.send(merchant, _with_meta(out, meta))

    async def asked(self, merchant_id: str, *, doctor_name: str, hospital_name: str, mode: str) -> Message:
        merchant = self._directory.merchant(merchant_id)
        meta: dict[str, object] = {
            "doctor_check": "ASKED",
            "doctor_name": doctor_name,
            "hospital_name": hospital_name,
            **_label(mode),
        }
        return await self._outbox.send(
            merchant, _with_meta(Outgoing.text("DOCTOR_ASKED", doctor=doctor_name), meta)
        )

    async def answered(
        self, merchant_id: str, *, status: VerificationStatus, doctor_name: str, mode: str
    ) -> Message | None:
        label = _label(mode)
        if VerificationStatus(status) is not VerificationStatus.CONFIRMED:
            return None
        merchant = self._directory.merchant(merchant_id)
        meta: dict[str, object] = {"doctor_check": "CONFIRMED", "doctor_name": doctor_name, **label}
        out = Outgoing.text("DOCTOR_CONFIRMED_VISIT", doctor=doctor_name)
        return await self._outbox.send(merchant, _with_meta(out, meta))
