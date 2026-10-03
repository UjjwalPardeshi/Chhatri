"""What the merchant hears while the treating doctor is asked: the three notify methods and DOCTOR_CHECK_STARTED."""

from __future__ import annotations

from datetime import date

import pytest

from chhatri.clock import ist
from chhatri.conversation.messages import bilingual
from chhatri.domain.enums import CheckCode, CheckStatus, DecisionOutcome, Severity, VerificationStatus
from chhatri.domain.models import CheckResult, Decision, SlipExtraction
from chhatri.sim.city import ANIL
from tests.conversation.conftest import World, make_world

SLIP = SlipExtraction(
    patient_name="Anil R. Jadhav",
    admission_date=date(2025, 8, 20),
    hospital_name="KEM Hospital, Parel",
    document_type="admission_slip",
    doctor_name="Dr S. Rao",
    doctor_registration_no="MMC-2011-45817",
    confidence=0.94,
    source="simulated",
)


@pytest.fixture
def illness() -> World:
    world = make_world(start=ist(2025, 8, 21, 11, 21))
    world.claims.silence = date(2025, 8, 20)
    return world


@pytest.mark.parametrize(
    ("mode", "provider"), [("LIVE", "telegram"), ("SIMULATED", "simulated"), ("FALLBACK", "simulated")]
)
async def test_doctor_asked_carries_the_names_and_an_honest_label(
    illness: World, mode: str, provider: str
) -> None:
    message = await illness.service.notify_doctor_asked(
        ANIL.id, doctor_name="Dr S. Rao", hospital_name="KEM Hospital, Parel", mode=mode
    )
    assert (message.text_hi, message.text_en) == bilingual("DOCTOR_ASKED", doctor="Dr S. Rao")
    assert message.meta["doctor_check"] == "ASKED" and message.meta["hospital_name"] == "KEM Hospital, Parel"
    assert (message.meta["mode"], message.meta["provider"]) == (mode, provider)
    assert message.card is None


async def test_an_unknown_mode_is_refused(illness: World) -> None:
    with pytest.raises(ValueError):
        await illness.service.notify_doctor_asked(
            ANIL.id, doctor_name="Dr S. Rao", hospital_name="KEM", mode="REAL"
        )


async def test_only_a_confirmation_is_told(illness: World) -> None:
    told = await illness.service.notify_doctor_answered(
        ANIL.id, status=VerificationStatus.CONFIRMED, doctor_name="Dr S. Rao", mode="SIMULATED"
    )
    assert told is not None and told.text_en == "Dr S. Rao has confirmed your visit."
    assert told.meta["doctor_check"] == "CONFIRMED" and told.meta["provider"] == "simulated"
    for status in (VerificationStatus.DENIED, VerificationStatus.NO_ANSWER):
        assert (
            await illness.service.notify_doctor_answered(
                ANIL.id, status=status, doctor_name="Dr S. Rao", mode="LIVE"
            )
        ) is None


DOCTOR_SAID_NO = CheckResult(
    code=CheckCode.DOCTOR_NOT_DENIED,
    status=CheckStatus.FAIL,
    severity=Severity.HARD,
    label_en="Doctor did not deny the visit",
    detail_en="the doctor said no",
)


def _decision(outcome: DecisionOutcome) -> Decision:
    return Decision(
        id="D-000009",
        claim_id="CL-000009",
        merchant_id=ANIL.id,
        outcome=outcome,
        amount_paise=0,
        checks=(DOCTOR_SAID_NO,) if outcome is DecisionOutcome.DECLINED else (),
        rules_version="test",
        decided_at=ist(2025, 8, 21, 11, 24),
        decided_by="policy-engine",
    )


async def test_a_personal_decision_after_the_doctor_is_told_like_any_other(illness: World) -> None:
    assert await illness.service.notify_personal_decided(_decision(DecisionOutcome.APPROVED)) == ()
    [declined] = await illness.service.notify_personal_decided(_decision(DecisionOutcome.DECLINED))
    assert declined.text_en is not None and declined.meta.get("doctor_check") is None


class PendingClaims:
    """The world's claims, plus the orchestrator's doctor-check flag (`DoctorCheckPort`)."""

    def __init__(self, inner: object, pending: bool) -> None:
        self._inner, self._pending = inner, pending

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)

    async def submit_personal_claim(self, merchant_id: str, slip: SlipExtraction, media_id: str) -> Decision:
        return await self._inner.submit_personal_claim(merchant_id, slip, media_id)  # type: ignore[attr-defined]

    def doctor_check_pending(self, decision_id: str) -> bool:
        return self._pending


@pytest.mark.parametrize("pending", [True, False])
async def test_filing_while_the_doctor_is_asked_says_so_and_nothing_else(
    illness: World, pending: bool
) -> None:
    flow = illness.service._slips
    flow._claims = PendingClaims(illness.claims, pending)  # type: ignore[assignment]
    filed = await illness.service.file_slip(ANIL.id, SLIP, "MD-000001")
    if pending:
        [started] = filed.messages
        assert filed.doctor_pending
        assert started.text_en == (
            "Thank you. We are now asking Dr S. Rao at KEM Hospital, Parel to confirm your visit. "
            "We will tell you as soon as they answer."
        )
        assert started.meta["doctor_check"] == "STARTED" and started.meta["doctor_name"] == "Dr S. Rao"
    else:
        assert not filed.doctor_pending
        assert all(m.meta.get("doctor_check") is None for m in filed.messages)


async def test_without_the_port_the_messages_are_todays(illness: World) -> None:
    filed = await illness.service.file_slip(ANIL.id, SLIP, "MD-000001")
    assert not filed.doctor_pending
    assert all(m.meta.get("doctor_check") is None for m in filed.messages)
