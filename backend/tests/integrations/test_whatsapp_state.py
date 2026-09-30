"""Idempotency, 24-hour window and recipient routing (SPEC §14.2) + the simulator channel."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from chhatri.clock import ist
from chhatri.integrations.base import IntegrationError, OutboundMessage
from chhatri.integrations.whatsapp import (
    InboundGate,
    SimulatorChannel,
    StatusEvent,
    TextEvent,
    phone_digits,
    route_inbound,
)

AT = ist(2025, 8, 19, 17, 2)


def text(message_id: str = "w1", phone: str = "919812345678", at: datetime = AT) -> TextEvent:
    return TextEvent(message_id, at, phone, "hi")


def test_accept_is_idempotent_on_message_id() -> None:
    gate = InboundGate()
    assert gate.accept(text()) is True
    assert gate.accept(text()) is False
    delivered = StatusEvent("w1", AT, "919812345678", "delivered")
    read = StatusEvent("w1", AT, "919812345678", "read")
    assert gate.accept(delivered) and gate.accept(read) and not gate.accept(read)


def test_seen_set_is_bounded() -> None:
    gate = InboundGate(capacity=2)
    for n in range(3):
        assert gate.accept(text(f"w{n}"))
    assert gate.accept(text("w0")) is True  # evicted, oldest first
    with pytest.raises(ValueError):
        InboundGate(capacity=0)


def test_window_tracks_latest_inbound_per_phone() -> None:
    gate = InboundGate()
    gate.accept(text("w1", "+91 98123 45678", AT))
    gate.note_inbound("919812345678", AT - timedelta(hours=1))  # older: ignored
    assert gate.last_inbound("+919812345678") == AT
    assert gate.within_window("919812345678", AT + timedelta(hours=23, minutes=59))
    assert not gate.within_window("919812345678", AT + timedelta(hours=24))
    assert not gate.within_window("919800000000", AT)
    assert not gate.within_window("919812345678", AT - timedelta(minutes=1))
    with pytest.raises(ValueError):
        gate.note_inbound("91", datetime(2025, 8, 19))  # noqa: DTZ001 — naive on purpose


def test_statuses_do_not_open_the_window() -> None:
    gate = InboundGate()
    gate.accept(StatusEvent("w1", AT, "919812345678", "read"))
    assert gate.last_inbound("919812345678") is None


def test_demo_notice_once_per_day() -> None:
    gate = InboundGate()
    assert gate.claim_demo_notice("+919800000001", date(2025, 8, 19))
    assert not gate.claim_demo_notice("919800000001", date(2025, 8, 19))
    assert gate.claim_demo_notice("919800000001", date(2025, 8, 20))


def test_routing_only_from_the_demo_recipient() -> None:
    assert (
        route_inbound("919812345678", demo_recipient="+91 98123-45678", demo_merchant_id="S-0142") == "S-0142"
    )
    assert route_inbound("919800000001", demo_recipient="+919812345678", demo_merchant_id="S-0142") is None
    assert route_inbound("919812345678", demo_recipient=None, demo_merchant_id="S-0142") is None
    assert route_inbound("919812345678", demo_recipient="+919812345678", demo_merchant_id=None) is None
    assert phone_digits("+91 (98) 123") == "9198123"


async def test_simulator_channel_records_and_never_sends() -> None:
    channel = SimulatorChannel()
    first = await channel.send(OutboundMessage("S-0142", "+919900012345", text="नमस्ते\nHello"))
    second = await channel.send(OutboundMessage("S-0001", "+919900000001", template_name="chhatri_checkin"))
    assert (first.provider_message_id, second.provider_message_id) == ("sim-000001", "sim-000002")
    assert first.channel == "simulator" and first.accepted
    assert [m.merchant_id for m in channel.sent] == ["S-0142", "S-0001"]
    with pytest.raises(ValueError):
        await channel.send(OutboundMessage("S-0142", "+91"))
    with pytest.raises(IntegrationError):
        await channel.download_media("123")


def test_demo_merchants_are_the_simulators_demo_shops() -> None:
    """SPEC §14.2 recipient safety + B5: only Anil (S-0142) and Ramesh (S-0907) may go live."""
    from chhatri.integrations.whatsapp import DEMO_MERCHANT_IDS
    from chhatri.sim.city import ANIL_ID, RAMESH_ID

    assert frozenset({ANIL_ID, RAMESH_ID}) == DEMO_MERCHANT_IDS
