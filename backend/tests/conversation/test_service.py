"""Tests for ConversationService (SPEC §13.5, §13.6, §24.4)."""

import asyncio
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from chhatri.clock import IST, ManualClock
from chhatri.conversation.service import ConversationService
from chhatri.domain.enums import (
    Channel,
    ClaimKind,
    CoverQuoteOutcome,
    DecisionOutcome,
    Direction,
    Language,
    MessageKind,
    PremiumMethod,
    PremiumStatus,
)
from chhatri.domain.models import (
    Case,
    CaseKind,
    CaseStatus,
    CoverQuote,
    Decision,
    InstalmentPause,
    Merchant,
    Message,
    Payout,
    PayoutStatus,
    PremiumPayment,
    SlipExtraction,
    Zone,
)
from chhatri.events import EventBus, Event
from chhatri.ids import IdFactory
from chhatri.integrations.base import (
    ChatModel,
    DeliveryReceipt,
    InboundMedia,
    MessagingChannel,
    OutboundMessage,
    SpeechToText,
    SynthesizedAudio,
    TextToSpeech,
    Transcript,
    SlipReader,
    Soundbox,
)
from chhatri.policy.facts import PersonalClaimFacts
from chhatri.sim.city import City
from chhatri.store.repositories import Store


# Test fixtures
@pytest.fixture
def ist_clock():
    """Manual IST clock starting at a fixed time."""
    return ManualClock(datetime(2025, 8, 19, 17, 0, 0, tzinfo=IST))


@pytest.fixture
def ids():
    """Fresh IdFactory."""
    return IdFactory()


@pytest.fixture
def event_bus():
    """Fresh EventBus."""
    return EventBus()


@pytest.fixture
def demo_merchant() -> Merchant:
    """Demo merchant S-0142 (Anil)."""
    return Merchant(
        id="S-0142",
        shop_name="Anil's Tea Stall",
        owner_name="Anil Jadhav",
        owner_name_hi="अनिल",
        kyc_name="ANIL RAMESH JADHAV",
        phone="+919900001111",
        language=Language.HI,
        zone_id="Z7",
        lat=19.0046,
        lng=72.8424,
        h3_cell="test_h3",
        shop_type="TEA_STALL",
        is_demo=True,
    )


@pytest.fixture
def demo_zone() -> Zone:
    """Demo zone Z7."""
    return Zone(
        id="Z7",
        ward="F/S",
        name="Parel · Lalbaug",
        centroid_lat=19.0,
        centroid_lng=72.84,
        waterlogging_prone=True,
    )


@pytest.fixture
def mock_city(demo_merchant, demo_zone):
    """Minimal mock City."""

    class MockCity:
        def __init__(self):
            self.seed = 20251019
            self.merchants = (demo_merchant,)
            self.covers = {}
            self.loans = {}

        def merchant(self, merchant_id: str) -> Merchant:
            if merchant_id == demo_merchant.id:
                return demo_merchant
            raise KeyError(merchant_id)

    return MockCity()


@pytest.fixture
def mock_store(mock_city):
    """Minimal mock Store."""

    class MockStore:
        def __init__(self):
            self._messages_list = []
            self._media = {}

        def add_message(self, msg: Message) -> None:
            self._messages_list.append(msg)

        def messages(self, merchant_id: str):
            return tuple(m for m in self._messages_list if m.merchant_id == merchant_id)

        def put_media(self, data: bytes, mime: str, media_id: str):
            self._media[media_id] = (data, mime)

        def media(self, media_id: str):
            return self._media[media_id]

        # Property for backward compatibility with tests
        @property
        def messages_list(self):
            """List of all messages for testing."""
            return self._messages_list

    return MockStore()


@pytest.fixture
def mock_audit():
    """Minimal mock AuditLog."""

    class MockAudit:
        def __init__(self):
            self.entries = []

        def append(self, *, at, actor, action, subject_type, subject_id, data):
            self.entries.append(
                {
                    "at": at,
                    "actor": actor,
                    "action": action,
                    "subject_type": subject_type,
                    "subject_id": subject_id,
                    "data": data,
                }
            )

    return MockAudit()


@pytest.fixture
def fake_channel():
    """Fake MessagingChannel that records sends."""

    class FakeChannel:
        def __init__(self):
            self.sent = []

        async def send(self, message: OutboundMessage) -> DeliveryReceipt:
            self.sent.append(message)
            return DeliveryReceipt(
                provider_message_id="fake_msg_id",
                channel="simulator",
                accepted=True,
            )

        async def download_media(self, media_id: str) -> InboundMedia:
            return InboundMedia(b"fake_image_data", "image/png")

    return FakeChannel()


@pytest.fixture
def fake_stt():
    """Fake SpeechToText."""

    class FakeSTT:
        async def transcribe(
            self, audio: bytes, mime_type: str, *, language_hint: str | None = None
        ) -> Transcript:
            # Simple mock: return a fixed transcript
            return Transcript(
                text="I'm in hospital with a fever.",
                language_code="en",
                confidence=0.95,
                source="simulated",
            )

    return FakeSTT()


@pytest.fixture
def fake_tts():
    """Fake TextToSpeech."""

    class FakeTTS:
        async def synthesize(self, text: str, language, *, for_whatsapp: bool = False):
            # Return simulated audio (no actual bytes when simulated)
            return SynthesizedAudio(
                audio=None, mime_type=None, source="browser-simulated"
            )

    return FakeTTS()


@pytest.fixture
def fake_slips():
    """Fake SlipReader."""

    class FakeSlips:
        async def read_slip(self, image: bytes, mime_type: str) -> SlipExtraction:
            return SlipExtraction(
                patient_name="Anil R. Jadhav",
                admission_date=date(2025, 8, 20),
                discharge_date=None,
                hospital_name="KEM Hospital",
                document_type="admission_slip",
                confidence=0.92,
                source="simulated",
            )

    return FakeSlips()


@pytest.fixture
def fake_soundbox():
    """Fake Soundbox."""

    class FakeSoundbox:
        def __init__(self):
            self.announcements = []

        async def announce(self, merchant_id: str, text: str, amount_paise: int):
            self.announcements.append(
                {"merchant_id": merchant_id, "text": text, "amount": amount_paise}
            )

    return FakeSoundbox()


@pytest.fixture
def fake_claims_port():
    """Fake ClaimsPort for testing."""

    class FakeClaimsPort:
        def __init__(self):
            self.submitted_slips = []

        async def submit_personal_claim(
            self, merchant_id: str, slip: SlipExtraction, media_id: str
        ) -> Decision:
            self.submitted_slips.append((merchant_id, slip, media_id))
            # Return an APPROVED decision for the test
            return Decision(
                id="D-000001",
                claim_id="CL-000001",
                merchant_id=merchant_id,
                outcome=DecisionOutcome.APPROVED,
                amount_paise=150000,  # ₹1,500
                checks=(),
                rules_version="pilot-0.1",
                decided_at=datetime(2025, 8, 21, 10, 30, tzinfo=IST),
                decided_by="policy-engine",
            )

        async def open_dispute(self, merchant_id: str, text: str) -> Case:
            return Case(
                id="C-2291",
                kind=CaseKind.DISPUTE,
                merchant_id=merchant_id,
                claim_id=None,
                decision_id=None,
                status=CaseStatus.OPEN,
                opened_at=datetime(2025, 8, 19, 17, 12, tzinfo=IST),
                due_by=datetime(2025, 8, 20, 17, 12, tzinfo=IST),
                summary_en="Merchant disputes payout amount",
                summary_hi="व्यापारी ने रकम पर विवाद किया",
                evidence={"merchant_text": text},
            )

        async def quote_cover(self, merchant_id: str):
            quote = CoverQuote(
                id="Q-000001",
                merchant_id=merchant_id,
                outcome=CoverQuoteOutcome.OK,
                requested_at=datetime(2025, 8, 18, 18, 10, tzinfo=IST),
                starts_on=date(2025, 8, 25),
                premium_per_day_paise=200,
                first_payment_paise=6000,  # 30 days
                days_prepaid=30,
                reason_en="Cover available",
                reason_hi="कवर उपलब्ध है",
            )
            payment = PremiumPayment(
                id="PR-000001",
                cover_id=None,
                merchant_id=merchant_id,
                amount_paise=6000,
                method=PremiumMethod.PAYMENT_LINK,
                covers_from=date(2025, 8, 25),
                covers_to=date(2025, 9, 24),
                status=PremiumStatus.PENDING,
                link_id="paytm_link_001",
                link_url="https://paytm.me/sim-test",
                source="simulated",
                created_at=datetime(2025, 8, 18, 18, 10, tzinfo=IST),
            )
            return quote, payment

        def latest_paid_decision(self, merchant_id: str) -> Decision | None:
            # Return a recent payout decision for WHY_AMOUNT flow (SPEC §13.6 golden values)
            from chhatri.domain.models import Explanation
            return Decision(
                id="D-000001",
                claim_id="CL-000001",
                merchant_id=merchant_id,
                outcome=DecisionOutcome.APPROVED,
                amount_paise=138000,  # ₹1,380
                checks=(),
                rules_version="pilot-0.1",
                decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
                decided_by="policy-engine",
                explanation=Explanation(
                    weekday_en="Tuesday",
                    weekday_hi="मंगलवार",
                    expected_day_paise=438000,  # ₹4,380 (golden value per SPEC §17.4)
                    drop_pct=63,  # 63% drop (golden value)
                    share_pct=50,
                    days=1,
                    cap_paise=250000,
                    capped=False,
                    amount_paise=138000,
                    formula_en="½ × ₹4,380 × 63% = ₹1,380",
                    formula_hi="₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380",
                ),
            )

        def open_silence(self, merchant_id: str) -> date | None:
            return date(2025, 8, 20)

    return FakeClaimsPort()


@pytest.fixture
async def service(
    mock_city,
    mock_store,
    mock_audit,
    ids,
    ist_clock,
    event_bus,
    fake_channel,
    fake_stt,
    fake_tts,
    fake_slips,
    fake_soundbox,
    fake_claims_port,
):
    """Create a ConversationService for testing."""
    return ConversationService(
        city=mock_city,
        store=mock_store,
        audit=mock_audit,
        ids=ids,
        clock=ist_clock,
        bus=event_bus,
        channel=fake_channel,
        stt=fake_stt,
        tts=fake_tts,
        chat=None,  # No LLM for these tests
        slips=fake_slips,
        soundbox=fake_soundbox,
        claims=fake_claims_port,
        channel_name=Channel.SIMULATOR,
    )


@pytest.mark.asyncio
async def test_handle_text_inbound(service, demo_merchant, mock_store):
    """Test handle_text stores inbound message."""
    messages = await service.handle_text(demo_merchant.id, "नमस्ते")
    # Should return tuple of messages (inbound + replies)
    assert len(messages) > 0
    # Check inbound was stored
    assert len(mock_store.messages_list) > 0
    inbound = mock_store.messages_list[0]
    assert inbound.direction == Direction.INBOUND
    assert inbound.merchant_id == demo_merchant.id
    # Hindi greeting should be in text_hi
    assert inbound.text_hi is not None
    assert "नमस्ते" in inbound.text_hi


@pytest.mark.asyncio
async def test_handle_voice(service, demo_merchant, mock_store):
    """Test handle_voice processes audio."""
    audio_bytes = b"fake_audio_data"
    messages = await service.handle_voice(
        demo_merchant.id, audio_bytes, "audio/ogg"
    )
    # Should have at least inbound (voice) message
    assert len(messages) > 0
    # Check voice message was stored
    voice_msgs = [
        m for m in mock_store.messages_list if m.kind == MessageKind.VOICE
    ]
    assert len(voice_msgs) > 0


@pytest.mark.asyncio
async def test_notify_area_payout(
    service, demo_merchant, mock_store, event_bus
):
    """Test area payout notification."""
    payout = Payout(
        id="P-000001",
        decision_id="D-000001",
        merchant_id=demo_merchant.id,
        amount_paise=138000,  # ₹1,380
        status=PayoutStatus.CREDITED,
        rail="Paytm settlement (simulated)",
        created_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
        credited_at=datetime(2025, 8, 19, 17, 4, tzinfo=IST),
        reference="test_ref",
    )

    from chhatri.domain.models import AreaTrigger

    trigger = AreaTrigger(
        id="E-Z7-20250819",
        zone_id="Z7",
        alert_id="A-20250818-01",
        window_start=datetime(2025, 8, 19, 14, 0, tzinfo=IST),
        window_end=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
        index_pct=37,
        drop_pct=63,
        hourly_index_pct=(41, 38, 37),
        lower_bound_pct=25,
        shops_in_index=46,
        fired_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
    )

    decision = Decision(
        id="D-000001",
        claim_id="CL-000001",
        merchant_id=demo_merchant.id,
        outcome=DecisionOutcome.APPROVED,
        amount_paise=138000,
        checks=(),
        rules_version="pilot-0.1",
        decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
        decided_by="policy-engine",
    )

    messages = await service.notify_area_payout(decision, payout, trigger)
    assert len(messages) > 0
    # Should have payout card message
    assert any(m.kind == MessageKind.PAYOUT_CARD for m in messages)


@pytest.mark.asyncio
async def test_checkin_silent(service, demo_merchant, mock_store):
    """Test silent check-in."""
    message = await service.checkin_silent(demo_merchant.id, date(2025, 8, 20))
    assert message is not None
    assert message.merchant_id == demo_merchant.id
    assert message.direction == Direction.OUTBOUND
    # Check message was stored
    assert len(mock_store.messages_list) > 0


@pytest.mark.asyncio
async def test_handle_text_why_amount(service, demo_merchant, mock_store):
    """Test WHY_AMOUNT intent handling."""
    messages = await service.handle_text(demo_merchant.id, "मुझे इतने पैसे क्यों मिले?")
    assert len(messages) > 0
    # Should have inbound and at least one reply
    assert messages[0].direction == Direction.INBOUND


@pytest.mark.asyncio
async def test_handle_text_dispute(service, demo_merchant, mock_store):
    """Test DISPUTE_AMOUNT intent handling."""
    messages = await service.handle_text(demo_merchant.id, "मेरा नुकसान ज़्यादा हुआ")
    assert len(messages) > 0
    assert any(m.kind == MessageKind.CASE_CHIP for m in messages)


@pytest.mark.asyncio
async def test_handle_text_report_illness(service, demo_merchant, mock_store):
    """Test REPORT_ILLNESS intent handling."""
    messages = await service.handle_text(demo_merchant.id, "बुखार है")
    assert len(messages) > 0


@pytest.mark.asyncio
async def test_handle_text_buy_cover(service, demo_merchant, mock_store):
    """Test BUY_COVER intent handling."""
    messages = await service.handle_text(demo_merchant.id, "cover do")
    assert len(messages) > 0


@pytest.mark.asyncio
async def test_handle_text_greeting(service, demo_merchant, mock_store):
    """Test GREETING intent handling."""
    messages = await service.handle_text(demo_merchant.id, "नमस्ते")
    assert len(messages) > 0


@pytest.mark.asyncio
async def test_handle_voice_with_transcript(service, demo_merchant, mock_store):
    """Test handle_voice processes audio and transcript."""
    audio_bytes = b"fake_audio_data"
    messages = await service.handle_voice(
        demo_merchant.id, audio_bytes, "audio/ogg"
    )
    # Should have voice message and transcribed text handling
    assert len(messages) > 0
    # Check that a VOICE message was stored
    voice_msgs = [
        m for m in mock_store.messages_list if m.kind == MessageKind.VOICE
    ]
    assert len(voice_msgs) > 0


@pytest.mark.asyncio
async def test_handle_image_approved(service, demo_merchant, mock_store):
    """Test handle_image with approved claim."""
    image_bytes = b"fake_image_data"
    messages = await service.handle_image(
        demo_merchant.id, image_bytes, "image/png", "media_001"
    )
    # Should have image and decision messages
    assert len(messages) > 0
    assert any(m.kind == MessageKind.IMAGE for m in messages)


@pytest.mark.asyncio
async def test_notify_personal_paid(service, demo_merchant, mock_store, ist_clock):
    """Test personal paid notification."""
    decision = Decision(
        id="D-000001",
        claim_id="CL-000001",
        merchant_id=demo_merchant.id,
        outcome=DecisionOutcome.APPROVED,
        amount_paise=150000,
        checks=(),
        rules_version="pilot-0.1",
        decided_at=ist_clock.now(),
        decided_by="policy-engine",
    )
    payout = Payout(
        id="P-000001",
        decision_id="D-000001",
        merchant_id=demo_merchant.id,
        amount_paise=150000,
        status=PayoutStatus.CREDITED,
        rail="Paytm settlement (simulated)",
        created_at=ist_clock.now(),
        credited_at=ist_clock.now(),
        reference="test_ref",
    )
    messages = await service.notify_personal_paid(decision, payout)
    assert len(messages) > 0


@pytest.mark.asyncio
async def test_notify_instalment_paused(service, demo_merchant, ist_clock):
    """Test instalment paused notification."""
    pause = InstalmentPause(
        id="IP-000001",
        loan_id="LN-000001",
        merchant_id=demo_merchant.id,
        instalment_date=date(2025, 8, 20),
        amount_paise=60000,
        reason="Area payout triggered",
        decision_id="D-000001",
        created_at=ist_clock.now(),
    )
    message = await service.notify_instalment_paused(pause)
    assert message is not None
    assert message.direction == Direction.OUTBOUND


@pytest.mark.asyncio
async def test_notify_officer_result_approved(service, demo_merchant, ist_clock):
    """Test officer result notification (approved)."""
    decision = Decision(
        id="D-000002",
        claim_id="CL-000002",
        merchant_id=demo_merchant.id,
        outcome=DecisionOutcome.APPROVED,
        amount_paise=150000,
        checks=(),
        rules_version="pilot-0.1",
        decided_at=ist_clock.now(),
        decided_by="officer",
    )
    case = Case(
        id="C-000001",
        kind=CaseKind.PERSONAL_CLAIM_REVIEW,
        merchant_id=demo_merchant.id,
        claim_id="CL-000002",
        decision_id="D-000002",
        status=CaseStatus.APPROVED,
        opened_at=ist_clock.now(),
        due_by=ist_clock.now() + timedelta(days=1),
        summary_en="Personal claim with slip",
        summary_hi="पर्ची के साथ व्यक्तिगत दावा",
        evidence={},
    )
    messages = await service.notify_officer_result(decision, case)
    assert len(messages) > 0
    assert any(m.kind == MessageKind.CASE_CHIP for m in messages)


@pytest.mark.asyncio
async def test_notify_officer_result_declined(service, demo_merchant, ist_clock):
    """Test officer result notification (declined)."""
    decision = Decision(
        id="D-000003",
        claim_id="CL-000003",
        merchant_id=demo_merchant.id,
        outcome=DecisionOutcome.DECLINED,
        amount_paise=0,
        checks=(),
        rules_version="pilot-0.1",
        decided_at=ist_clock.now(),
        decided_by="officer",
        referral_reason="Insufficient evidence",
    )
    case = Case(
        id="C-000002",
        kind=CaseKind.PERSONAL_CLAIM_REVIEW,
        merchant_id=demo_merchant.id,
        claim_id="CL-000003",
        decision_id="D-000003",
        status=CaseStatus.DECLINED,
        opened_at=ist_clock.now(),
        due_by=ist_clock.now() + timedelta(days=1),
        summary_en="Personal claim declined",
        summary_hi="व्यक्तिगत दावा अस्वीकृत",
        evidence={},
    )
    messages = await service.notify_officer_result(decision, case)
    assert len(messages) > 0


# ---- SPEC §13.6 Live Tests ----


@pytest.mark.asyncio
async def test_live_explained_flow(service, demo_merchant, ist_clock, mock_store, fake_claims_port):
    """EXPLAINED (slide 8): Anil asks WHY_AMOUNT, receives EXPLAIN_AREA with ₹4,380/63%, then disputes and gets case C-2291."""
    # First message: "मुझे इतने ही पैसे क्यों मिले?" → EXPLAIN_AREA
    messages = await service.handle_text(demo_merchant.id, "मुझे इतने ही पैसे क्यों मिले?")
    assert len(messages) > 0
    # Should have explanation message
    explain_msgs = [m for m in messages if m.text_en and "usual" in m.text_en]
    assert len(explain_msgs) > 0, "Should send EXPLAIN_AREA"

    # Second message: "मेरा नुकसान ज़्यादा हुआ।" → DISPUTE_ACK + CASE_CHIP with case C-2291
    messages = await service.handle_text(demo_merchant.id, "मेरा नुकसान ज़्यादा हुआ।")
    assert len(messages) > 0
    # Should have dispute acknowledgement
    ack_msgs = [m for m in messages if m.text_en and "sending this to our team" in m.text_en]
    assert len(ack_msgs) > 0, "Should send DISPUTE_ACK"
    # Should have case chip with C-2291
    case_msgs = [m for m in messages if m.kind == MessageKind.CASE_CHIP]
    assert len(case_msgs) > 0, "Should send CASE_CHIP"
    assert any("C-2291" in m.text_en for m in case_msgs), "Case should be C-2291"


@pytest.mark.asyncio
async def test_live_human_flow(service, demo_merchant, ist_clock, mock_store):
    """HUMAN (slide 8): Slip 'Sunil Pawar' fails NAME_MATCHES_KYC check → REFERRED → SLIP_TO_HUMAN."""
    # Mock claims port that returns REFERRED with NAME_MATCHES_KYC fail
    class ReferredClaimsPort:
        async def submit_personal_claim(self, merchant_id: str, slip: SlipExtraction, media_id: str):
            from chhatri.domain.models import CheckResult, Explanation
            return Decision(
                id="D-000002",
                claim_id="CL-000002",
                merchant_id=merchant_id,
                outcome=DecisionOutcome.REFERRED,
                amount_paise=150000,
                checks=(
                    CheckResult(
                        code="NAME_MATCHES_KYC",
                        status="FAIL",
                        severity="SOFT",
                        label_en="Name matches KYC",
                        detail_en="Patient name does not match KYC records",
                        observed="Sunil Pawar",
                        required="Match with ANIL RAMESH JADHAV",
                    ),
                ),
                rules_version="pilot-0.1",
                decided_at=ist_clock.now(),
                decided_by="policy-engine",
                explanation=None,
                referral_reason="Name mismatch",
            )

        def latest_paid_decision(self, merchant_id: str):
            return None

        async def open_dispute(self, merchant_id: str, text: str):
            return None

        async def quote_cover(self, merchant_id: str):
            return None, None

        def open_silence(self, merchant_id: str):
            return None

    # Create service with referred claims port
    service_referred = ConversationService(
        city=service.city,
        store=service.store,
        audit=service.audit,
        ids=service.ids,
        clock=service.clock,
        bus=service.bus,
        channel=service.channel,
        stt=service.stt,
        tts=service.tts,
        chat=service.chat,
        slips=service.slips,
        soundbox=service.soundbox,
        claims=ReferredClaimsPort(),
        channel_name=service.channel_name,
    )

    # Submit slip image → REFERRED
    image_bytes = b"fake_slip_image"
    messages = await service_referred.handle_image(demo_merchant.id, image_bytes, "image/png", "media_002")
    assert len(messages) > 0

    # Should have SLIP_TO_HUMAN message with name variant
    slip_msgs = [m for m in messages if m.text_en and "doesn't match" in m.text_en]
    assert len(slip_msgs) > 0, "Should send SLIP_TO_HUMAN (name variant)"


@pytest.mark.asyncio
async def test_live_blocked_flow(service, demo_merchant, ist_clock, mock_store):
    """BLOCKED (slide 8): Ramesh 'Red alert tomorrow. Cover me today.' → COVER_BLOCKED → starts_on = purchase date + 7 days."""
    # Mock claims port that returns BLOCKED
    class BlockedCoverPort:
        async def submit_personal_claim(self, merchant_id: str, slip: SlipExtraction, media_id: str):
            return None

        def latest_paid_decision(self, merchant_id: str):
            return None

        async def open_dispute(self, merchant_id: str, text: str):
            return None

        async def quote_cover(self, merchant_id: str):
            return (
                CoverQuote(
                    id="Q-000002",
                    merchant_id=merchant_id,
                    outcome=CoverQuoteOutcome.BLOCKED,
                    requested_at=ist_clock.now(),
                    starts_on=date(2025, 8, 25),  # purchase date + 7 days
                    premium_per_day_paise=200,
                    first_payment_paise=6000,
                    days_prepaid=30,
                    reason_en="Alert in effect; waiting period applies",
                    reason_hi="अलर्ट सक्रिय है; प्रतीक्षा अवधि लागू है",
                ),
                None,
            )

        def open_silence(self, merchant_id: str):
            return None

    # Create service with blocked cover port
    service_blocked = ConversationService(
        city=service.city,
        store=service.store,
        audit=service.audit,
        ids=service.ids,
        clock=service.clock,
        bus=service.bus,
        channel=service.channel,
        stt=service.stt,
        tts=service.tts,
        chat=service.chat,
        slips=service.slips,
        soundbox=service.soundbox,
        claims=BlockedCoverPort(),
        channel_name=service.channel_name,
    )

    # "Red alert tomorrow. Cover me today." → BUY_COVER flow
    messages = await service_blocked.handle_text(demo_merchant.id, "Red alert tomorrow. Cover me today.")
    assert len(messages) > 0

    # Should have COVER_BLOCKED message with starts_on = 2025-08-25
    blocked_msgs = [m for m in messages if m.text_en and "waiting period" in m.text_en]
    assert len(blocked_msgs) > 0, "Should send COVER_BLOCKED"
    assert any("2025-08-25" in m.text_en or "25 Aug" in m.text_en for m in blocked_msgs), "Should show starts_on date"


@pytest.mark.asyncio
async def test_slip_to_human_dates_variant(service, demo_merchant, ist_clock, mock_store):
    """Test SLIP_TO_HUMAN_DATES variant when DATES_MATCH fails."""
    # Mock claims port returning REFERRED with DATES_MATCH fail
    class DatesMismatchPort:
        async def submit_personal_claim(self, merchant_id: str, slip: SlipExtraction, media_id: str):
            from chhatri.domain.models import CheckResult
            return Decision(
                id="D-000003",
                claim_id="CL-000003",
                merchant_id=merchant_id,
                outcome=DecisionOutcome.REFERRED,
                amount_paise=0,
                checks=(
                    CheckResult(
                        code="DATES_MATCH",
                        status="FAIL",
                        severity="SOFT",
                        label_en="Dates match",
                        detail_en="Admission/discharge dates do not cover all silent days",
                        observed="Admission 2025-08-25",
                        required="Cover all silent days",
                    ),
                ),
                rules_version="pilot-0.1",
                decided_at=ist_clock.now(),
                decided_by="policy-engine",
                referral_reason="Dates mismatch",
            )

        def latest_paid_decision(self, merchant_id: str):
            return None

        async def open_dispute(self, merchant_id: str, text: str):
            return None

        async def quote_cover(self, merchant_id: str):
            return None, None

        def open_silence(self, merchant_id: str):
            return None

    service_dates = ConversationService(
        city=service.city,
        store=service.store,
        audit=service.audit,
        ids=service.ids,
        clock=service.clock,
        bus=service.bus,
        channel=service.channel,
        stt=service.stt,
        tts=service.tts,
        chat=service.chat,
        slips=service.slips,
        soundbox=service.soundbox,
        claims=DatesMismatchPort(),
        channel_name=service.channel_name,
    )

    messages = await service_dates.handle_image(demo_merchant.id, b"image", "image/png", "media_003")
    assert len(messages) > 0

    # Should have SLIP_TO_HUMAN_DATES message
    dates_msgs = [m for m in messages if m.text_en and "dates on the slip" in m.text_en]
    assert len(dates_msgs) > 0, "Should send SLIP_TO_HUMAN_DATES variant"


@pytest.mark.asyncio
async def test_slip_to_human_unreadable_variant(service, demo_merchant, ist_clock, mock_store):
    """Test SLIP_TO_HUMAN_UNREADABLE variant when SLIP_READABLE fails."""
    # Mock claims port returning REFERRED with SLIP_READABLE fail
    class UnreadableSlipPort:
        async def submit_personal_claim(self, merchant_id: str, slip: SlipExtraction, media_id: str):
            from chhatri.domain.models import CheckResult
            return Decision(
                id="D-000004",
                claim_id="CL-000004",
                merchant_id=merchant_id,
                outcome=DecisionOutcome.REFERRED,
                amount_paise=0,
                checks=(
                    CheckResult(
                        code="SLIP_READABLE",
                        status="FAIL",
                        severity="SOFT",
                        label_en="Slip readable",
                        detail_en="Slip confidence below threshold",
                        observed="confidence=0.60",
                        required="confidence >= 0.80",
                    ),
                ),
                rules_version="pilot-0.1",
                decided_at=ist_clock.now(),
                decided_by="policy-engine",
                referral_reason="Slip unclear",
            )

        def latest_paid_decision(self, merchant_id: str):
            return None

        async def open_dispute(self, merchant_id: str, text: str):
            return None

        async def quote_cover(self, merchant_id: str):
            return None, None

        def open_silence(self, merchant_id: str):
            return None

    service_unreadable = ConversationService(
        city=service.city,
        store=service.store,
        audit=service.audit,
        ids=service.ids,
        clock=service.clock,
        bus=service.bus,
        channel=service.channel,
        stt=service.stt,
        tts=service.tts,
        chat=service.chat,
        slips=service.slips,
        soundbox=service.soundbox,
        claims=UnreadableSlipPort(),
        channel_name=service.channel_name,
    )

    messages = await service_unreadable.handle_image(demo_merchant.id, b"image", "image/png", "media_004")
    assert len(messages) > 0

    # Should have SLIP_TO_HUMAN_UNREADABLE message
    unreadable_msgs = [m for m in messages if m.text_en and "unclear" in m.text_en]
    assert len(unreadable_msgs) > 0, "Should send SLIP_TO_HUMAN_UNREADABLE variant"
