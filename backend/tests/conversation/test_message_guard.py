"""X8 / H9 (fs-03 section 9): offers are held back in distress, proactive messages are capped per IST day."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta

import pytest

from chhatri.clock import ist
from chhatri.conversation.message_guard import (
    DEFAULT_MAX_PROACTIVE_PER_DAY,
    MESSAGE_KINDS,
    DistressReason,
    MessageGuard,
    MessageSuppressed,
    SendKind,
    StoreDistressProbe,
    guard_for,
    kind_of,
)
from chhatri.conversation.messages import CATALOGUE
from chhatri.conversation.outbox import Outbox, Outgoing
from chhatri.domain.enums import (
    CaseKind,
    CaseStatus,
    Channel,
    ClaimKind,
    DecisionOutcome,
    Direction,
    MessageKind,
)
from chhatri.domain.models import Alert, Case, Claim, Decision
from chhatri.integrations.soundbox import SimulatedSoundbox
from chhatri.sim.city import ANIL
from tests.api.fakes import make_settings
from tests.conversation.conftest import World, make_world

NOW = ist(2025, 8, 19, 17, 0)
FAKE_OFFER = "TEST_LOAN_TOPUP_OFFER"
KINDS = {**MESSAGE_KINDS, FAKE_OFFER: SendKind.OFFER}


@dataclass
class FakeProbe:
    active: tuple[DistressReason, ...] = ()
    calls: list[str] = field(default_factory=list)

    def reasons(self, merchant, now):  # noqa: ANN001
        self.calls.append(merchant.id)
        return self.active


def _history(world: World, count: int, *, at=NOW, key: str = "CHECKIN_SILENT"):  # noqa: ANN001, ANN202
    from chhatri.domain.models import Message

    return tuple(
        Message(
            id=f"M-9{i:05d}",
            merchant_id=ANIL.id,
            direction=Direction.OUTBOUND,
            channel=Channel.SIMULATOR,
            kind=MessageKind.TEXT,
            text_hi="x",
            created_at=at,
            meta={"send_kind": "PROACTIVE", "key": key},
        )
        for i in range(count)
    )


def test_every_catalogue_key_has_a_kind_and_only_the_checkin_is_proactive() -> None:
    assert set(CATALOGUE) <= set(MESSAGE_KINDS)
    assert {k for k, v in MESSAGE_KINDS.items() if v is SendKind.PROACTIVE} == {"CHECKIN_SILENT"}
    assert [k for k, v in MESSAGE_KINDS.items() if v is SendKind.OFFER] == []
    assert kind_of("PERSONAL_PAID") is SendKind.TRANSACTIONAL
    assert kind_of("NOT_A_KEY") is SendKind.TRANSACTIONAL  # unknown keys are never held back


@pytest.mark.parametrize("reason", list(DistressReason))
def test_offer_suppressed_for_each_distress_reason(reason: DistressReason) -> None:
    guard = MessageGuard(distress=FakeProbe((reason,)), kinds=KINDS)
    verdict = guard.verdict(ANIL, FAKE_OFFER, (), NOW)
    assert verdict is not None and verdict.reason == reason.value and verdict.kind is SendKind.OFFER


def test_offer_allowed_without_distress() -> None:
    assert MessageGuard(distress=FakeProbe(), kinds=KINDS).verdict(ANIL, FAKE_OFFER, (), NOW) is None


def test_transactional_is_never_suppressed_or_capped() -> None:
    probe = FakeProbe(tuple(DistressReason))
    guard = MessageGuard(distress=probe, kinds=KINDS)
    assert guard.verdict(ANIL, "PERSONAL_PAID", _history(make_world(), 10), NOW) is None
    assert probe.calls == []  # a transactional message does not even ask


def test_proactive_cap_is_per_ist_calendar_day() -> None:
    guard = MessageGuard(distress=FakeProbe())
    world = make_world()
    assert DEFAULT_MAX_PROACTIVE_PER_DAY == 3
    assert guard.verdict(ANIL, "CHECKIN_SILENT", _history(world, 2), NOW) is None
    capped = guard.verdict(ANIL, "CHECKIN_SILENT", _history(world, 3), NOW)
    assert capped is not None and capped.reason == "DAILY_CAP" and capped.kind is SendKind.PROACTIVE
    yesterday_late = ist(2025, 8, 18, 23, 59)
    assert guard.verdict(ANIL, "CHECKIN_SILENT", _history(world, 3, at=yesterday_late), NOW) is None
    just_after_midnight = ist(2025, 8, 20, 0, 1)
    assert guard.verdict(ANIL, "CHECKIN_SILENT", _history(world, 3), just_after_midnight) is None


def test_proactive_is_not_held_for_distress() -> None:
    guard = MessageGuard(distress=FakeProbe(tuple(DistressReason)))
    assert guard.verdict(ANIL, "CHECKIN_SILENT", (), NOW) is None


def test_cap_setting_is_validated() -> None:
    with pytest.raises(ValueError):
        MessageGuard(distress=FakeProbe(), max_proactive_per_day=0)


# ---------------------------------------------------------------- the probe over real records


def _alert(
    zone: str, *, issued: timedelta, start: timedelta, length: timedelta = timedelta(hours=6)
) -> Alert:
    from chhatri.domain.enums import AlertKind, AlertLevel

    return Alert(
        id="A-1",
        kind=AlertKind.RAIN,
        level=AlertLevel.RED,
        zone_ids=(zone,),
        issued_at=NOW + issued,
        valid_from=NOW + start,
        valid_to=NOW + start + length,
        source="test",
        headline_en="Heavy rain",
        headline_hi="भारी बारिश",
    )


class _Store:
    def __init__(self, world: World) -> None:
        self._real = world.store

    def __getattr__(self, name: str):  # noqa: ANN204
        return getattr(self._real, name)


def _probe(world: World, alerts=(), grievance=False) -> StoreDistressProbe:  # noqa: ANN001
    return StoreDistressProbe(
        store=world.store,
        alerts_between=lambda start, end: tuple(
            a for a in alerts if a.valid_from < end and start < a.valid_to
        ),
        grievance_open=lambda merchant_id: grievance,
    )


def test_probe_is_quiet_for_a_calm_merchant() -> None:
    assert _probe(make_world()).reasons(ANIL, NOW) == ()


def test_probe_alert_valid_now_or_starting_within_72_hours() -> None:
    world = make_world()
    now_alert = _alert(ANIL.zone_id, issued=-timedelta(hours=1), start=-timedelta(hours=1))
    soon = _alert(ANIL.zone_id, issued=-timedelta(hours=1), start=timedelta(hours=71))
    far = _alert(ANIL.zone_id, issued=-timedelta(hours=1), start=timedelta(hours=73))
    other_zone = _alert("Z-OTHER", issued=-timedelta(hours=1), start=-timedelta(hours=1))
    not_issued = _alert(ANIL.zone_id, issued=timedelta(hours=1), start=timedelta(hours=2))
    assert _probe(world, (now_alert,)).reasons(ANIL, NOW) == (DistressReason.ALERT_IN_ZONE,)
    assert _probe(world, (soon,)).reasons(ANIL, NOW) == (DistressReason.ALERT_IN_ZONE,)
    assert _probe(world, (far,)).reasons(ANIL, NOW) == ()
    assert _probe(world, (other_zone,)).reasons(ANIL, NOW) == ()
    assert _probe(world, (not_issued,)).reasons(ANIL, NOW) == ()


def test_probe_grievance() -> None:
    assert _probe(make_world(), grievance=True).reasons(ANIL, NOW) == (DistressReason.GRIEVANCE_OPEN,)


def _claim(world: World, claim_id: str = "CL-1") -> Claim:
    claim = Claim(
        id=claim_id,
        kind=ClaimKind.PERSONAL,
        merchant_id=ANIL.id,
        created_at=NOW,
        event_date=NOW.date(),
        expected_day_paise=438_000,
    )
    world.store.add_claim(claim)
    return claim


def _decision(world: World, claim: Claim, outcome: DecisionOutcome, decision_id: str = "D-1") -> Decision:
    decision = Decision(
        id=decision_id,
        claim_id=claim.id,
        merchant_id=ANIL.id,
        outcome=outcome,
        amount_paise=0,
        checks=(),
        rules_version="test",
        decided_at=NOW,
        decided_by="test",
    )
    world.store.add_decision(decision)
    return decision


def _case(world: World, status: CaseStatus, decision_id: str | None = None) -> Case:
    case = Case(
        id="C-000001",
        kind=CaseKind.PERSONAL_CLAIM_REVIEW,
        merchant_id=ANIL.id,
        decision_id=decision_id,
        status=status,
        opened_at=NOW,
        due_by=NOW + timedelta(hours=24),
        summary_en="review",
    )
    world.store.add_case(case)
    return case


def test_probe_claim_waiting_for_a_decision_then_decided() -> None:
    world = make_world()
    claim = _claim(world)
    assert _probe(world).reasons(ANIL, NOW) == (DistressReason.CLAIM_BEING_DECIDED,)
    _decision(world, claim, DecisionOutcome.APPROVED)
    assert _probe(world).reasons(ANIL, NOW) == ()


def test_probe_open_case_and_referred_decision() -> None:
    world = make_world()
    claim = _claim(world)
    decision = _decision(world, claim, DecisionOutcome.REFERRED)
    assert _probe(world).reasons(ANIL, NOW) == (DistressReason.DECISION_REFERRED,)
    _case(world, CaseStatus.OPEN, decision.id)
    assert set(_probe(world).reasons(ANIL, NOW)) == {
        DistressReason.DECISION_REFERRED,
        DistressReason.CASE_OPEN,
    }


def test_probe_resolved_referral_is_not_distress() -> None:
    world = make_world()
    claim = _claim(world)
    decision = _decision(world, claim, DecisionOutcome.REFERRED)
    _case(world, CaseStatus.APPROVED, decision.id)
    assert _probe(world).reasons(ANIL, NOW) == ()


# ---------------------------------------------------------------- the outbox


def _outbox(world: World, guard: MessageGuard | None) -> Outbox:
    return Outbox(
        store=world.store,
        audit=world.audit,
        ids=world.ids,
        clock=world.clock,
        bus=world.bus,
        channel=world.channel,
        tts=world.tts,
        soundbox=SimulatedSoundbox(world.tts),
        channel_name=Channel.SIMULATOR,
        guard=guard,
    )


def _offer() -> Outgoing:
    return Outgoing(key=FAKE_OFFER, kind=MessageKind.TEXT, text_hi="ऑफर", text_en="offer", voiced=False)


async def test_suppressed_offer_is_not_stored_sent_or_published_and_is_audited_without_text() -> None:
    world = make_world()
    outbox = _outbox(world, MessageGuard(distress=FakeProbe((DistressReason.CASE_OPEN,)), kinds=KINDS))
    with pytest.raises(MessageSuppressed) as raised:
        await outbox.send(ANIL, _offer())
    assert raised.value.reason == "CASE_OPEN"
    assert not world.store.messages(ANIL.id) and not world.channel.sent and not world.events("message")
    (entry,) = world.audit.entries()
    assert (entry.actor, entry.action, entry.subject_id) == ("system", "message.suppressed", ANIL.id)
    assert entry.data == {"merchant_id": ANIL.id, "kind": "OFFER", "reason": "CASE_OPEN", "key": FAKE_OFFER}


async def test_proactive_messages_stop_at_the_cap_while_transactional_still_goes() -> None:
    world = make_world()
    outbox = _outbox(world, MessageGuard(distress=FakeProbe(), max_proactive_per_day=2))
    checkin = Outgoing.text("CHECKIN_SILENT", name_hi="अनिल")
    for _ in range(2):
        sent = await outbox.send(ANIL, checkin)
        assert sent.meta["send_kind"] == "PROACTIVE"
    with pytest.raises(MessageSuppressed) as raised:
        await outbox.send(ANIL, checkin)
    assert raised.value.reason == "DAILY_CAP"
    paid = await outbox.send(ANIL, Outgoing.text("FALLBACK_HELP"))
    assert "send_kind" not in paid.meta
    assert len(world.store.messages(ANIL.id)) == 3
    assert [e.action for e in world.audit.entries()].count("message.suppressed") == 1


async def test_without_a_guard_nothing_changes() -> None:
    world = make_world()
    outbox = _outbox(world, None)
    for _ in range(5):
        message = await outbox.send(ANIL, Outgoing.text("CHECKIN_SILENT", name_hi="अनिल"))
        assert "send_kind" not in message.meta


# ---------------------------------------------------------------- wiring


def test_guard_for_follows_the_flag() -> None:
    probe: Callable[..., object] = FakeProbe()
    off = make_settings(chhatri_features="")
    on = make_settings(chhatri_features="x8_distress_guard")
    assert guard_for(off, probe) is None  # type: ignore[arg-type]
    assert isinstance(guard_for(on, probe), MessageGuard)  # type: ignore[arg-type]
