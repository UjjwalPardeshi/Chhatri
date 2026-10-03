"""The consent step of the pre-check (rule personal.require_doctor_confirmation), on the service with fakes.

CONFIRM asks "may we ask the doctor?" and files nothing; CONSENT_YES / CONSENT_NO write the answer to the ledger first,
then file the READY read through the same filer as before. Every cell of the action table is a 409 with its own code.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from PIL import Image

from chhatri.ai.chain import ChainResult
from chhatri.ai.labels import AiLabel, AiMode, AiProvider, FallbackReason
from chhatri.audit.log import AuditLog
from chhatri.clock import ManualClock, ist
from chhatri.domain.enums import CaseKind, CaseStatus, Channel, DecisionOutcome, Direction, MessageKind
from chhatri.domain.models import Case, Decision, Message, SlipExtraction
from chhatri.ids import IdFactory
from chhatri.precheck.consent_step import ConsentQuestion, consent_question, consent_view
from chhatri.precheck.model import Action, ConfirmedAs, PrecheckStatus, Reason
from chhatri.precheck.service import Filed, PrecheckConflict, SlipPrecheckService

MERCHANT = "S-0142"
CHECKIN = date(2025, 8, 20)
START = ist(2025, 8, 21, 11, 21)
LABEL = AiLabel(AiMode.SIMULATED, AiProvider.SIMULATED, fallback_reason=FallbackReason.NO_KEY)
ANIL_SLIP = SlipExtraction(
    patient_name="Anil R. Jadhav",
    admission_date=CHECKIN,
    hospital_name="KEM Hospital, Parel",
    document_type="admission_slip",
    doctor_name="Dr S. Rao",
    doctor_registration_no="MMC-2011-45817",
    confidence=0.94,
    source="simulated",
)


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(out, format="PNG")
    return out.getvalue()


@dataclass
class FakeChain:
    reads: list[SlipExtraction | None]

    async def read_with_label(self, image: bytes, mime: str, **_: Any) -> ChainResult[SlipExtraction]:
        return ChainResult(self.reads.pop(0), LABEL)


@dataclass
class FakeStore:
    case_list: list[Case] = field(default_factory=list)
    media: dict[str, bytes] = field(default_factory=dict)

    def put_media(self, data: bytes, mime: str, media_id: str) -> None:
        self.media[media_id] = data

    def cases(self) -> tuple[Case, ...]:
        return tuple(self.case_list)

    def replace_case(self, c: Case) -> None:
        self.case_list = [c if old.id == c.id else old for old in self.case_list]


@dataclass
class FakeClaims:
    open: date | None = CHECKIN

    def open_silence(self, merchant_id: str) -> date | None:
        return self.open


@dataclass
class FakeConsents:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def record(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        return object()


def message(mid: str, key: str) -> Message:
    return Message(
        id=mid,
        merchant_id=MERCHANT,
        direction=Direction.OUTBOUND,
        channel=Channel.SIMULATOR,
        kind=MessageKind.TEXT,
        text_en=key,
        created_at=START,
    )


@dataclass
class Rig:
    service: SlipPrecheckService
    clock: ManualClock
    claims: FakeClaims
    store: FakeStore
    consents: FakeConsents
    audit: AuditLog
    filed: list[tuple[str, SlipExtraction, str]]
    asked: list[ConsentQuestion]
    events: list[str]


def rig(
    reads: list[SlipExtraction | None],
    *,
    require_doctor: bool = True,
    outcome: DecisionOutcome = DecisionOutcome.APPROVED,
) -> Rig:
    clock = ManualClock(START)
    claims, store, consents, audit = FakeClaims(), FakeStore(), FakeConsents(), AuditLog()
    filed: list[tuple[str, SlipExtraction, str]] = []
    asked: list[ConsentQuestion] = []
    events: list[str] = []
    original_record = consents.record

    def record(**kwargs: Any) -> object:
        events.append("ledger")
        return original_record(**kwargs)

    consents.record = record  # type: ignore[method-assign]

    async def filer(merchant_id: str, slip: SlipExtraction, media_id: str) -> Filed:
        events.append("filed")
        filed.append((merchant_id, slip, media_id))
        decision = Decision(
            id="D-000001",
            claim_id="CL-000001",
            merchant_id=merchant_id,
            outcome=outcome,
            amount_paise=150_000 if outcome is DecisionOutcome.APPROVED else 0,
            checks=(),
            rules_version="test",
            decided_at=clock.now(),
            decided_by="policy-engine",
        )
        if outcome is DecisionOutcome.REFERRED:
            store.case_list.append(
                Case(
                    id="C-2291",
                    kind=CaseKind.PERSONAL_CLAIM_REVIEW,
                    merchant_id=merchant_id,
                    claim_id="CL-000001",
                    decision_id="D-000001",
                    status=CaseStatus.OPEN,
                    opened_at=clock.now(),
                    due_by=clock.now() + timedelta(hours=4),
                    summary_en="review",
                )
            )
        claims.open = None
        return Filed(decision, (message("M-000009", "OUTCOME"),))

    async def asker(merchant_id: str, question: ConsentQuestion) -> Message:
        asked.append(question)
        return message("M-000005", question.key)

    service = SlipPrecheckService(
        ids=IdFactory(),
        clock=clock,
        audit=audit,
        store=store,
        claims=claims,
        chain=FakeChain(list(reads)),  # type: ignore[arg-type]
        minimum=0.80,
        filer=filer,
        require_doctor=require_doctor,
        asker=asker,
        consents=consents,
    )
    return Rig(service, clock, claims, store, consents, audit, filed, asked, events)


async def ready(r: Rig) -> str:
    pc = await r.service.precheck(MERCHANT, png(), "image/png")
    assert pc.status is PrecheckStatus.READY
    return pc.id


# ------------------------------------------------------------------------------------------------ the two steps


async def test_confirm_asks_the_question_once_and_files_nothing() -> None:
    r = rig([ANIL_SLIP])
    pc_id = await ready(r)
    done = await r.service.confirm(MERCHANT, pc_id, Action.CONFIRM, source="CHAT")
    pc = done.precheck
    assert pc.status is PrecheckStatus.AWAITING_CONSENT and pc.confirmed_as is ConfirmedAs.FIELDS_CONFIRMED
    assert pc.fields_confirmed_at is not None and pc.claim_id is None and pc.consent is None
    assert (done.outcome, done.case_id, done.doctor_pending) == (None, None, False)
    assert [m.id for m in done.messages] == ["M-000005"] and pc.messages == ("M-000005",)
    assert done.consent is not None and done.consent.precheck_id == pc_id
    assert len(r.asked) == 1 and r.filed == [] and r.consents.calls == []
    [row] = [e for e in r.audit.entries() if e.action == "precheck.confirmed"]
    assert row.data == {
        "merchant_id": MERCHANT,
        "precheck_id": pc_id,
        "action": "CONFIRM",
        "awaiting_consent": True,
        "claim_id": None,
    }


@pytest.mark.parametrize(("action", "granted"), [(Action.CONSENT_YES, True), (Action.CONSENT_NO, False)])
async def test_an_answer_is_recorded_first_then_the_ready_read_is_filed(
    action: Action, granted: bool
) -> None:
    r = rig([ANIL_SLIP])
    pc_id = await ready(r)
    await r.service.confirm(MERCHANT, pc_id, Action.CONFIRM)
    done = await r.service.confirm(MERCHANT, pc_id, action, source="CHAT")
    assert r.events == ["ledger", "filed"]
    [call] = r.consents.calls
    assert call == {
        "merchant_id": MERCHANT,
        "granted": granted,
        "at": START,
        "source": "CHAT",
        "precheck_id": pc_id,
        "checkin": CHECKIN,
    }
    [(merchant, slip, media_id)] = r.filed
    assert merchant == MERCHANT and slip.patient_name == "Anil R. Jadhav" and slip.doctor_name == "Dr S. Rao"
    assert media_id in r.store.media
    pc = done.precheck
    assert pc.status is PrecheckStatus.CONFIRMED and pc.confirmed_as is ConfirmedAs.FIELDS_CONFIRMED
    assert (pc.consent, pc.consent_at, pc.claim_id, pc.decision_id) == (
        granted,
        START,
        "CL-000001",
        "D-000001",
    )
    assert done.outcome == "APPROVED" and [m.id for m in done.messages] == ["M-000009"]
    assert done.consent is not None and done.consent.doctor_name == "Dr S. Rao"
    actions = [e.data["action"] for e in r.audit.entries() if e.action == "precheck.confirmed"]
    assert actions == ["CONFIRM", action.value]


async def test_a_referred_answer_puts_the_consent_in_the_officers_evidence() -> None:
    r = rig([ANIL_SLIP], outcome=DecisionOutcome.REFERRED)
    pc_id = await ready(r)
    await r.service.confirm(MERCHANT, pc_id, Action.CONFIRM)
    done = await r.service.confirm(MERCHANT, pc_id, Action.CONSENT_NO)
    assert (done.outcome, done.case_id) == ("REFERRED", "C-2291")
    evidence = r.store.case_list[0].evidence["precheck"]
    assert evidence["doctor_consent"] == "REFUSED" and evidence["filed_as"] == "FIELDS_CONFIRMED"


async def test_with_the_rule_off_confirm_files_at_once_as_before() -> None:
    r = rig([ANIL_SLIP], require_doctor=False)
    pc_id = await ready(r)
    done = await r.service.confirm(MERCHANT, pc_id, Action.CONFIRM)
    assert done.precheck.status is PrecheckStatus.CONFIRMED and done.consent is None
    assert len(r.filed) == 1 and r.asked == [] and r.consents.calls == []
    row = next(e for e in r.audit.entries() if e.action == "precheck.confirmed")
    assert row.data == {
        "merchant_id": MERCHANT,
        "precheck_id": pc_id,
        "action": "CONFIRM",
        "claim_id": "CL-000001",
    }


async def test_the_rule_adds_the_doctor_row_to_the_read() -> None:
    no_doctor = ANIL_SLIP.model_copy(update={"doctor_registration_no": None})
    r = rig([no_doctor])
    pc = await r.service.precheck(MERCHANT, png(), "image/png")
    assert (pc.status, pc.reason, pc.guidance_key) == (
        PrecheckStatus.RETAKE,
        Reason.DOCTOR_MISSING,
        "SLIP_RETAKE_DOCTOR",
    )
    off = rig([no_doctor], require_doctor=False)
    assert (await off.service.precheck(MERCHANT, png(), "image/png")).status is PrecheckStatus.READY


# ------------------------------------------------------------------------------------------------ the action table


def _code(exc: pytest.ExceptionInfo[PrecheckConflict]) -> str:
    return exc.value.code


ACTIONS = list(Action)
TABLE: dict[str, dict[Action, str | None]] = {
    "READY": {
        Action.CONFIRM: None,
        Action.SEND_TO_TEAM: "ready_not_team",
        Action.CONSENT_YES: "no_consent_question",
        Action.CONSENT_NO: "no_consent_question",
    },
    "RETAKE": {
        Action.CONFIRM: "not_ready",
        Action.SEND_TO_TEAM: None,
        Action.CONSENT_YES: "no_consent_question",
        Action.CONSENT_NO: "no_consent_question",
    },
    "AWAITING_CONSENT": {
        Action.CONFIRM: "consent_pending",
        Action.SEND_TO_TEAM: "consent_pending",
        Action.CONSENT_YES: None,
        Action.CONSENT_NO: None,
    },
    "CONFIRMED": dict.fromkeys(ACTIONS, "already_confirmed"),
    "SUPERSEDED": dict.fromkeys(ACTIONS, "superseded"),
}


async def _in_state(state: str) -> tuple[Rig, str]:
    if state == "RETAKE":
        r = rig([ANIL_SLIP.model_copy(update={"patient_name": None})])
        return r, (await r.service.precheck(MERCHANT, png(), "image/png")).id
    r = rig([ANIL_SLIP, ANIL_SLIP])
    pc_id = await ready(r)
    if state == "AWAITING_CONSENT":
        await r.service.confirm(MERCHANT, pc_id, Action.CONFIRM)
    elif state == "CONFIRMED":
        await r.service.confirm(MERCHANT, pc_id, Action.CONFIRM)
        await r.service.confirm(MERCHANT, pc_id, Action.CONSENT_YES)
        r.claims.open = CHECKIN  # the check-in reopened: the code is still about the pre-check
    elif state == "SUPERSEDED":
        await r.service.precheck(MERCHANT, png(), "image/png")
    return r, pc_id


@pytest.mark.parametrize("state", list(TABLE))
@pytest.mark.parametrize("action", ACTIONS)
async def test_every_cell_of_the_action_table(state: str, action: Action) -> None:
    r, pc_id = await _in_state(state)
    expected = TABLE[state][action]
    if expected is None:
        done = await r.service.confirm(MERCHANT, pc_id, action)
        assert done.precheck.status in (PrecheckStatus.CONFIRMED, PrecheckStatus.AWAITING_CONSENT)
        return
    with pytest.raises(PrecheckConflict) as exc:
        await r.service.confirm(MERCHANT, pc_id, action)
    assert _code(exc) == expected


async def test_no_open_check_in_is_no_checkin() -> None:
    r = rig([ANIL_SLIP])
    pc_id = await ready(r)
    r.claims.open = None
    with pytest.raises(PrecheckConflict) as exc:
        await r.service.confirm(MERCHANT, pc_id, Action.CONFIRM)
    assert _code(exc) == "no_checkin"
    with pytest.raises(PrecheckConflict) as read:
        await r.service.precheck(MERCHANT, png(), "image/png")
    assert _code(read) == "no_checkin"


async def test_the_fourth_photo_is_photo_limit() -> None:
    blank = ANIL_SLIP.model_copy(update={"patient_name": None})
    r = rig([blank, blank, blank])
    for _ in range(3):
        await r.service.precheck(MERCHANT, png(), "image/png")
    with pytest.raises(PrecheckConflict) as exc:
        await r.service.precheck(MERCHANT, png(), "image/png")
    assert _code(exc) == "photo_limit"


async def test_a_new_photo_supersedes_a_waiting_question() -> None:
    r = rig([ANIL_SLIP, ANIL_SLIP])
    pc_id = await ready(r)
    await r.service.confirm(MERCHANT, pc_id, Action.CONFIRM)
    newer = await r.service.precheck(MERCHANT, png(), "image/png")
    assert r.service.get(MERCHANT, pc_id).status is PrecheckStatus.SUPERSEDED
    assert r.service.open_for(MERCHANT) == newer


# ------------------------------------------------------------------------------------------------ open_for


async def test_open_for_is_the_latest_open_pre_check_of_the_open_check_in() -> None:
    r = rig([ANIL_SLIP])
    assert r.service.open_for(MERCHANT) is None
    pc_id = await ready(r)
    assert r.service.open_for(MERCHANT) is not None and r.service.open_for(MERCHANT).id == pc_id  # type: ignore[union-attr]
    await r.service.confirm(MERCHANT, pc_id, Action.CONFIRM)
    waiting = r.service.open_for(MERCHANT)
    assert waiting is not None and waiting.status is PrecheckStatus.AWAITING_CONSENT
    await r.service.confirm(MERCHANT, pc_id, Action.CONSENT_YES)
    assert r.service.open_for(MERCHANT) is None  # filed: nothing open, and the check-in closed
    assert r.service.open_for("S-0907") is None


# ------------------------------------------------------------------------------------------------ the question


def test_the_question_names_the_directory_doctor_and_hospital() -> None:
    from chhatri.precheck.model import Precheck

    pc = Precheck(
        id="PC-000001",
        merchant_id=MERCHANT,
        checkin=CHECKIN.isoformat(),
        attempt=1,
        media_id="MD-000001",
        status=PrecheckStatus.READY,
        reason=None,
        guidance_key=None,
        slip=ANIL_SLIP.model_copy(update={"hospital_name": "K.E.M. Hospital Parel", "doctor_name": "S Rao"}),
        gate_passed=True,
        label=LABEL,
        created_at=START,
    )
    q = consent_question(pc)
    assert (q.key, q.doctor_name, q.hospital_name, q.hospital_id) == (
        "DOCTOR_CONSENT_ASK",
        "Dr S. Rao",
        "KEM Hospital, Parel",
        "H-KEM",
    )
    assert q.doctor_registration_no == "MMC-2011-45817"
    assert "Dr S. Rao" in q.text_en and "KEM Hospital, Parel" in q.text_en and "Dr S. Rao" in q.text_hi
    unknown = consent_question(
        Precheck(
            **{
                **_fields(pc),
                "slip": ANIL_SLIP.model_copy(update={"doctor_name": None, "hospital_name": None}),
            }
        )
    )
    assert unknown.key == "DOCTOR_CONSENT_ASK_GENERIC" and unknown.doctor_name is None
    assert "treating doctor" in unknown.text_en
    slip_only = consent_question(
        Precheck(
            **{
                **_fields(pc),
                "slip": ANIL_SLIP.model_copy(
                    update={
                        "hospital_name": "City Care Clinic",
                        "doctor_registration_no": "XX-1",
                        "doctor_name": "Dr Mehta",
                    }
                ),
            }
        )
    )
    assert (slip_only.key, slip_only.doctor_name, slip_only.hospital_name, slip_only.hospital_id) == (
        "DOCTOR_CONSENT_ASK",
        "Dr Mehta",
        "City Care Clinic",
        None,
    )


def _fields(pc: Any) -> dict[str, Any]:
    return {name: getattr(pc, name) for name in pc.__dataclass_fields__}


def test_the_consent_view_is_the_wire_shape() -> None:
    from chhatri.precheck.model import Precheck

    pc = Precheck(
        id="PC-000001",
        merchant_id=MERCHANT,
        checkin=CHECKIN.isoformat(),
        attempt=1,
        media_id="MD-000001",
        status=PrecheckStatus.READY,
        reason=None,
        guidance_key=None,
        slip=ANIL_SLIP,
        gate_passed=True,
        label=LABEL,
        created_at=START,
    )
    q = consent_question(pc)
    asked = consent_view(q, status="ASKED", answered_at=None)
    assert asked == {
        "purpose": "doctor_verification",
        "status": "ASKED",
        "precheck_id": "PC-000001",
        "doctor_name": "Dr S. Rao",
        "hospital_name": "KEM Hospital, Parel",
        "question_hi": q.text_hi,
        "question_en": q.text_en,
        "answered_at": None,
    }
    at = datetime(2025, 8, 21, 5, 52, tzinfo=START.tzinfo).astimezone(START.tzinfo)
    assert consent_view(q, status="GIVEN", answered_at=at)["answered_at"] == at.isoformat()
