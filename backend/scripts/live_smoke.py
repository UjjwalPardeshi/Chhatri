#!/usr/bin/env python3
"""Live smoke tests for integrations (SPEC §14, §0.1).

Optional manual script that exercises each LIVE integration when its env keys exist.
Never run in automated tests.

Usage:
    cd backend
    . .venv/bin/activate
    python scripts/live_smoke.py
"""

import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from chhatri.config import get_settings
from chhatri.domain.enums import Language
from chhatri.domain.models import Merchant
from chhatri.integrations.sarvam import LiveSarvamChat, LiveSarvamSlipReader, LiveSarvamSTT, LiveSarvamTTS
from chhatri.integrations.paytm import McpPaytmLinks, RestPaytmLinks
from chhatri.integrations.whatsapp import LiveWhatsAppChannel
from chhatri.integrations.openmeteo import LiveOpenMeteo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def smoke_sarvam_stt(api_key: str) -> None:
    """Test Sarvam STT."""
    logger.info("Testing Sarvam STT...")

    # Create a simple audio file (silence in OGG format) for testing
    # For real testing, you'd provide actual audio
    stt = LiveSarvamSTT(api_key)

    # Dummy audio bytes (won't actually transcribe but will test connectivity)
    test_audio = b"dummy_audio_data"

    try:
        result = await stt.transcribe(test_audio, "audio/ogg", language_hint="hi-IN")
        logger.info(f"  ✓ STT working: {result.source}")
    except Exception as e:
        logger.error(f"  ✗ STT failed: {e}")


async def smoke_sarvam_tts(api_key: str) -> None:
    """Test Sarvam TTS."""
    logger.info("Testing Sarvam TTS...")

    tts = LiveSarvamTTS(api_key)

    try:
        result = await tts.synthesize("नमस्ते", Language.HI)
        if result.audio:
            logger.info(f"  ✓ TTS working: {result.source}, audio {len(result.audio)} bytes")
        else:
            logger.info(f"  ✓ TTS working: {result.source}, no audio")
    except Exception as e:
        logger.error(f"  ✗ TTS failed: {e}")


async def smoke_sarvam_chat(api_key: str) -> None:
    """Test Sarvam Chat."""
    logger.info("Testing Sarvam Chat...")

    chat = LiveSarvamChat(api_key)
    schema = {
        "type": "object",
        "properties": {
            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
        },
        "required": ["sentiment"],
    }

    try:
        result = await chat.complete_json(
            system="You are a sentiment analyzer.",
            user="I love this!",
            schema=schema,
            schema_name="Sentiment",
        )
        logger.info(f"  ✓ Chat working: {result}")
    except Exception as e:
        logger.error(f"  ✗ Chat failed: {e}")


async def smoke_sarvam_slip(api_key: str) -> None:
    """Test Sarvam slip reader (doc-ai)."""
    logger.info("Testing Sarvam slip reader...")

    reader = LiveSarvamSlipReader(api_key)

    # Create a minimal PNG for testing
    # This will fail but tests the API connectivity
    png_header = b"\x89PNG\r\n\x1a\n"

    try:
        result = await reader.read_slip(png_header, "image/png")
        logger.info(f"  ✓ Slip reader working: {result.source}")
    except Exception as e:
        logger.error(f"  ✗ Slip reader failed: {e}")


async def smoke_whatsapp(token: str, phone_id: str, app_secret: str) -> None:
    """Test WhatsApp Cloud API."""
    logger.info("Testing WhatsApp Cloud API...")

    _channel = LiveWhatsAppChannel(
        access_token=token,
        phone_number_id=phone_id,
        app_secret=app_secret,
    )

    # Test without actually sending (no demo_recipient set)
    logger.info("  (Skipping actual send - set WHATSAPP_DEMO_RECIPIENT to test)")


async def smoke_paytm_mcp(url: str) -> None:
    """Test Paytm MCP server."""
    logger.info("Testing Paytm MCP server...")

    paytm = McpPaytmLinks(url)

    # Create a test merchant
    test_merchant = Merchant(
        id="S-0001",
        shop_name="Test Shop",
        owner_name="Test Owner",
        owner_name_hi="टेस्ट",
        kyc_name="TEST OWNER",
        phone="+919900000001",
        language=Language.HI,
        zone_id="Z7",
        lat=19.0,
        lng=72.8,
        h3_cell="test",
        shop_type="TEA_STALL",
    )

    try:
        result = await paytm.create_premium_link(test_merchant, 100000, "Test Premium")
        logger.info(f"  ✓ MCP working: {result.url}")
    except Exception as e:
        logger.error(f"  ✗ MCP failed: {e}")


async def smoke_paytm_rest(mid: str, key_secret: str) -> None:
    """Test Paytm REST API."""
    logger.info("Testing Paytm REST API...")

    paytm = RestPaytmLinks(mid, key_secret, "https://securestage.paytmpayments.com")

    # Create a test merchant
    test_merchant = Merchant(
        id="S-0001",
        shop_name="Test Shop",
        owner_name="Test Owner",
        owner_name_hi="टेस्ट",
        kyc_name="TEST OWNER",
        phone="+919900000001",
        language=Language.HI,
        zone_id="Z7",
        lat=19.0,
        lng=72.8,
        h3_cell="test",
        shop_type="TEA_STALL",
    )

    try:
        result = await paytm.create_premium_link(test_merchant, 100000, "Test Premium")
        logger.info(f"  ✓ REST API working: {result.url}")
    except Exception as e:
        logger.error(f"  ✗ REST API failed: {e}")


async def smoke_openmeteo() -> None:
    """Test Open-Meteo live API."""
    logger.info("Testing Open-Meteo live API...")

    weather = LiveOpenMeteo()

    try:
        # Test with Mumbai coordinates for a small date range
        result = await weather.hourly_rain(19.08, 72.88, date(2024, 9, 1), date(2024, 9, 2))
        logger.info(f"  ✓ Open-Meteo working: {len(result.precipitation_mm)} data points")
    except Exception as e:
        logger.error(f"  ✗ Open-Meteo failed: {e}")


async def main() -> None:
    """Run all smoke tests for live integrations."""
    settings = get_settings()

    logger.info("=== Chhatri Live Integration Smoke Tests ===\n")

    # Sarvam
    if settings.sarvam_live:
        api_key = settings.sarvam_api_key.get_secret_value()
        await smoke_sarvam_stt(api_key)
        await smoke_sarvam_tts(api_key)
        await smoke_sarvam_chat(api_key)
        await smoke_sarvam_slip(api_key)
    else:
        logger.info("Sarvam: skipped (no SARVAM_API_KEY)")

    # WhatsApp
    if settings.whatsapp_live:
        await smoke_whatsapp(
            settings.whatsapp_access_token.get_secret_value(),
            settings.whatsapp_phone_number_id or "",
            settings.whatsapp_app_secret.get_secret_value(),
        )
    else:
        logger.info("WhatsApp: skipped (no WHATSAPP_* keys)")

    # Paytm
    if settings.paytm_mode == "mcp":
        await smoke_paytm_mcp(settings.paytm_mcp_url or "")
    elif settings.paytm_mode == "rest":
        await smoke_paytm_rest(
            settings.paytm_mid or "",
            settings.paytm_key_secret.get_secret_value(),
        )
    else:
        logger.info("Paytm: using simulated links")

    # Open-Meteo
    if settings.openmeteo_live:
        await smoke_openmeteo()
    else:
        logger.info("Open-Meteo: using fixture data")

    logger.info("\n=== Smoke tests complete ===")


if __name__ == "__main__":
    asyncio.run(main())
