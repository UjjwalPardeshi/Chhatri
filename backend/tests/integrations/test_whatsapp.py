"""Tests for WhatsApp integration (SPEC §14.2)."""

import pytest

from chhatri.integrations.base import OutboundMessage
from chhatri.integrations.whatsapp import LiveWhatsAppChannel, SimulatorChannel


class TestSimulatorChannel:
    """Tests for SimulatorChannel (simulated WhatsApp)."""

    @pytest.mark.asyncio
    async def test_send_records_message(self):
        """Test that messages are recorded."""
        channel = SimulatorChannel()

        message = OutboundMessage(
            merchant_id="S-0142",
            to_phone="+919900000001",
            text="नमस्ते",
        )

        receipt = await channel.send(message)

        assert receipt.accepted is True
        assert receipt.channel == "simulator"
        assert len(channel.messages) == 1
        assert channel.messages[0] == message

    @pytest.mark.asyncio
    async def test_send_multiple_messages(self):
        """Test sending multiple messages."""
        channel = SimulatorChannel()

        for i in range(3):
            message = OutboundMessage(
                merchant_id=f"S-{i:04d}",
                to_phone=f"+9190000000{i}",
                text="Test",
            )
            await channel.send(message)

        assert len(channel.messages) == 3

    @pytest.mark.asyncio
    async def test_download_media_not_supported(self):
        """Test that media download is not available in simulator."""
        channel = SimulatorChannel()

        with pytest.raises(Exception, match="not available in simulator"):
            await channel.download_media("MEDIA123")


class TestLiveWhatsAppChannel:
    """Tests for LiveWhatsAppChannel."""

    def test_verify_signature_valid(self):
        """Test valid webhook signature."""
        channel = LiveWhatsAppChannel(
            access_token="test_token",
            phone_number_id="123456789",
            app_secret="test_secret",
        )

        raw_body = b'{"entry":[]}'
        import hmac
        import hashlib
        expected_sig = "sha256=" + hmac.new(
            "test_secret".encode(), raw_body, hashlib.sha256
        ).hexdigest()

        is_valid = channel.verify_signature(raw_body, expected_sig, "test_secret")
        assert is_valid is True

    def test_verify_signature_invalid(self):
        """Test invalid webhook signature."""
        channel = LiveWhatsAppChannel(
            access_token="test_token",
            phone_number_id="123456789",
            app_secret="test_secret",
        )

        raw_body = b'{"entry":[]}'
        invalid_sig = "sha256=" + "0" * 64

        is_valid = channel.verify_signature(raw_body, invalid_sig, "test_secret")
        assert is_valid is False

    def test_verify_challenge_valid(self):
        """Test valid webhook challenge."""
        channel = LiveWhatsAppChannel(
            access_token="test_token",
            phone_number_id="123456789",
            app_secret="test_secret",
        )

        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "my_token",
            "hub.challenge": "CHALLENGE123",
        }

        challenge = channel.verify_challenge(params, "my_token")
        assert challenge == "CHALLENGE123"

    def test_verify_challenge_invalid_token(self):
        """Test challenge with invalid token."""
        channel = LiveWhatsAppChannel(
            access_token="test_token",
            phone_number_id="123456789",
            app_secret="test_secret",
        )

        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "CHALLENGE123",
        }

        challenge = channel.verify_challenge(params, "my_token")
        assert challenge is None

    def test_verify_challenge_invalid_mode(self):
        """Test challenge with invalid mode."""
        channel = LiveWhatsAppChannel(
            access_token="test_token",
            phone_number_id="123456789",
            app_secret="test_secret",
        )

        params = {
            "hub.mode": "invalid",
            "hub.verify_token": "my_token",
            "hub.challenge": "CHALLENGE123",
        }

        challenge = channel.verify_challenge(params, "my_token")
        assert challenge is None

    def test_parse_webhook_text_message(self):
        """Test parsing text message from webhook."""
        channel = LiveWhatsAppChannel(
            access_token="test_token",
            phone_number_id="123456789",
            app_secret="test_secret",
        )

        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "MSG123",
                                        "timestamp": "1630000000",
                                        "from": "+919900000001",
                                        "type": "text",
                                        "text": {
                                            "body": "नमस्ते",
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        events = channel.parse_webhook(payload)

        assert len(events) == 1
        assert events[0].message_id == "MSG123"
        assert events[0].type == "text"
        assert events[0].text == "नमस्ते"

    def test_parse_webhook_audio_message(self):
        """Test parsing audio message from webhook."""
        channel = LiveWhatsAppChannel(
            access_token="test_token",
            phone_number_id="123456789",
            app_secret="test_secret",
        )

        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "MSG123",
                                        "timestamp": "1630000000",
                                        "from": "+919900000001",
                                        "type": "audio",
                                        "audio": {
                                            "id": "AUDIO123",
                                            "mime_type": "audio/ogg",
                                            "voice": True,
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        events = channel.parse_webhook(payload)

        assert len(events) == 1
        assert events[0].message_id == "MSG123"
        assert events[0].type == "audio"
        assert events[0].media_id == "AUDIO123"
        assert events[0].is_voice_note is True

    def test_parse_webhook_image_message(self):
        """Test parsing image message from webhook."""
        channel = LiveWhatsAppChannel(
            access_token="test_token",
            phone_number_id="123456789",
            app_secret="test_secret",
        )

        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "MSG123",
                                        "timestamp": "1630000000",
                                        "from": "+919900000001",
                                        "type": "image",
                                        "image": {
                                            "id": "IMG123",
                                            "mime_type": "image/jpeg",
                                            "caption": "Hospital slip",
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        events = channel.parse_webhook(payload)

        assert len(events) == 1
        assert events[0].type == "image"
        assert events[0].media_id == "IMG123"
        assert events[0].caption == "Hospital slip"

    def test_parse_webhook_status(self):
        """Test parsing delivery status from webhook."""
        channel = LiveWhatsAppChannel(
            access_token="test_token",
            phone_number_id="123456789",
            app_secret="test_secret",
        )

        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "statuses": [
                                    {
                                        "id": "MSG123",
                                        "timestamp": "1630000000",
                                        "recipient_id": "+919900000001",
                                        "status": "delivered",
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        events = channel.parse_webhook(payload)

        assert len(events) == 1
        assert events[0].type == "status"
        assert events[0].status == "delivered"
