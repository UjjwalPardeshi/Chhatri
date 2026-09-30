"""Slip photo → personal claim → reply (SPEC §13.5; HUMAN variants: name / dates / unreadable / days)."""

from __future__ import annotations

import logging
from datetime import date

import pytest

from chhatri.clock import ist
from chhatri.domain.enums import DecisionOutcome, MessageKind
from chhatri.domain.models import Decision, SlipExtraction
from chhatri.integrations.base import IntegrationError
from chhatri.sim.city import ANIL, RAMESH
from chhatri.sim.slips import render_slip, render_unreadable_slip
from tests.conversation.conftest import SILENT_DAY, World, make_world

PNG = "image/png"


def _illness_world() -> World:
    world = make_world(start=ist(2025, 8, 21, 11, 25))
    world.claims.silence = SILENT_DAY
    return world


async def test_photo_without_an_open_check_in_files_no_claim(world: World) -> None:
    image, reply = await world.service.handle_image(ANIL.id, b"\x89PNG-bytes", PNG, "MD-9")
    assert image.media_url == "/api/media/MD-9"
    assert reply.text_en.startswith("Thanks for the photo. There's no open claim right now.")
    assert world.claims.submitted == []
    assert world.store.media("MD-9") == (b"\x89PNG-bytes", PNG)


@pytest.mark.parametrize(
    ("slip", "expected_en_start"),
    [
        (
            render_unreadable_slip("Anil R. Jadhav", SILENT_DAY, "KEM Hospital", "Viral fever"),
            "Thank you. We couldn't read",
        ),
        (b"\x89PNG not a slip at all", "Thank you. We couldn't read"),
        (
            render_slip("Anil R. Jadhav", date(2025, 8, 21), "KEM Hospital", "Viral fever"),
            "Thank you. The dates on the slip",
        ),
        (
            render_slip("Sunil Pawar", SILENT_DAY, "KEM Hospital", "Viral fever"),
            "Thank you. The name on the slip",
        ),
    ],
)
async def test_referred_variants_with_case_chip(slip: bytes, expected_en_start: str) -> None:
    world = _illness_world()
    image, told, chip = await world.service.handle_image(ANIL.id, slip, PNG, "MD-9")
    assert told.text_en.startswith(expected_en_start)
    assert told.text_en.endswith(", so our team will check it. You'll hear back within 24 hours.")
    assert (chip.kind, chip.meta) == (MessageKind.CASE_CHIP, {"case_id": "C-2291"})
    assert world.store.decisions_for(ANIL.id)[-1].outcome is DecisionOutcome.REFERRED


async def test_reader_failure_goes_to_a_human(caplog: pytest.LogCaptureFixture) -> None:
    world = _illness_world()

    async def broken(image: bytes, mime_type: str) -> SlipExtraction:
        raise IntegrationError("sarvam_vision", "doc-ai job failed")

    world.service._slips._reader.read_slip = broken  # type: ignore[method-assign]
    caplog.set_level(logging.ERROR)
    _, told, _ = await world.service.handle_image(ANIL.id, b"\x89PNG", PNG, "MD-9")
    assert told.text_en.startswith("Thank you. We couldn't read the slip clearly")
    (_, slip, media_id) = world.claims.submitted[0]
    assert (slip.source, slip.confidence, media_id) == ("read-failed", 0.0, "MD-9")
    assert "slip MD-9 unreadable by the reader: doc-ai job failed" in caplog.text


async def test_slip_read_is_audited_without_the_patient_name() -> None:
    world = _illness_world()
    await world.service.handle_image(
        ANIL.id, render_slip("Sunil Pawar", SILENT_DAY, "KEM", "Fever"), PNG, "MD-9"
    )
    (entry,) = [e for e in world.audit.entries(limit=100) if e.action == "slip.read"]
    assert (entry.subject_type, entry.subject_id) == ("media", "MD-9")
    assert entry.data["fields_read"] == ["patient_name", "admission_date", "hospital_name", "document_type"]
    assert "Sunil" not in str(entry.data)


async def test_referred_without_a_case_yet_omits_the_chip(caplog: pytest.LogCaptureFixture) -> None:
    world = _illness_world()
    world.claims.open_case_on_referral = False
    caplog.set_level(logging.ERROR)
    replies = await world.service.handle_image(
        ANIL.id, render_slip("Sunil Pawar", SILENT_DAY, "KEM", "F"), PNG, "M"
    )
    assert [m.kind for m in replies] == [MessageKind.IMAGE, MessageKind.TEXT]
    assert "has no review case yet; chip omitted" in caplog.text


async def test_declined_claim_gives_the_hard_check_reason() -> None:
    world = _illness_world()
    replies = await world.service.handle_image(
        RAMESH.id, render_slip("Ramesh Pawar", SILENT_DAY, "KEM", "F"), PNG, "M"
    )
    assert replies[-1].text_hi == "रमेश जी, यह दावा मंज़ूर नहीं हो सका। उस दिन आपका कवर चालू नहीं था।"
    assert (
        replies[-1].text_en == "Ramesh ji, this claim can't be paid. Your cover wasn't in force on that day."
    )
    assert world.store.decisions_for(RAMESH.id)[-1].outcome is DecisionOutcome.DECLINED


async def test_decision_for_another_merchant_is_rejected() -> None:
    world = _illness_world()
    real = world.claims.submit_personal_claim

    async def wrong(merchant_id: str, slip: SlipExtraction, media_id: str) -> Decision:
        decision = await real(merchant_id, slip, media_id)
        return decision.model_copy(update={"merchant_id": RAMESH.id})

    world.claims.submit_personal_claim = wrong  # type: ignore[method-assign]
    with pytest.raises(ValueError, match="is for S-0907"):
        await world.service.handle_image(
            ANIL.id, render_slip("Anil Jadhav", SILENT_DAY, "KEM", "F"), PNG, "M"
        )
