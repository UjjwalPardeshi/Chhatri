"""Tests for integration registry (SPEC §0.1, §14)."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from chhatri.config import Settings
from chhatri.integrations.registry import DEMO_UTTERANCES, build_integrations
from chhatri.workflows.definitions import Scheduler, StepHandlers


class MockScheduler:
    """Mock scheduler."""
    def schedule(self, at, name, fn): pass
    def now(self): from datetime import datetime, timezone, timedelta; return datetime.now(tz=timezone(timedelta(hours=5, minutes=30)))


class MockStepHandlers:
    """Mock step handlers."""
    async def run_step(self, workflow, step, payload): pass


class TestDemoUtterances:
    """Tests for demo utterance registry."""

    def test_demo_utterances_keys(self):
        """Test demo utterances has expected keys."""
        assert "why" in DEMO_UTTERANCES
        assert "dispute" in DEMO_UTTERANCES
        assert "ill" in DEMO_UTTERANCES
        assert "cover" in DEMO_UTTERANCES

    def test_demo_utterances_format(self):
        """Test demo utterances have correct format."""
        for key, (hi, en) in DEMO_UTTERANCES.items():
            assert isinstance(hi, str)
            assert isinstance(en, str)
            assert len(hi) > 0
            assert len(en) > 0


class TestBuildIntegrations:
    """Tests for build_integrations function."""

    def test_build_integrations_simulated(self):
        """Test building all-simulated integrations."""
        settings = Settings(
            sarvam_api_key=None,
            whatsapp_access_token=None,
            paytm_mcp_url=None,
            paytm_mid=None,
            n8n_base_url=None,
            openmeteo_live=False,
            cognee_enabled=False,
        )

        scheduler = MockScheduler()
        handlers = MockStepHandlers()

        with tempfile.TemporaryDirectory() as tmpdir:
            integrations = build_integrations(
                settings,
                scheduler=scheduler,
                step_handlers=handlers,
                data_dir=Path(tmpdir),
            )

        assert integrations.stt is not None
        assert integrations.tts is not None
        assert integrations.chat is not None
        assert integrations.slips is not None
        assert integrations.channel is not None
        assert integrations.payments is not None
        assert integrations.weather is not None
        assert integrations.workflows is not None
        assert integrations.memory is not None
        assert integrations.soundbox is not None

    def test_build_integrations_statuses(self):
        """Test that statuses are reported for all components."""
        settings = Settings()

        scheduler = MockScheduler()
        handlers = MockStepHandlers()

        with tempfile.TemporaryDirectory() as tmpdir:
            integrations = build_integrations(
                settings,
                scheduler=scheduler,
                step_handlers=handlers,
                data_dir=Path(tmpdir),
            )

        status_names = [s.name for s in integrations.statuses]

        # Check required statuses are present
        assert "sarvam_stt" in status_names
        assert "sarvam_tts" in status_names
        assert "sarvam_chat" in status_names
        assert "sarvam_vision" in status_names
        assert "whatsapp" in status_names
        assert "paytm" in status_names
        assert "weather" in status_names
        assert "n8n" in status_names
        assert "memory" in status_names
        assert "soundbox" in status_names

    def test_build_integrations_always_simulated(self):
        """Test that always-simulated components are reported."""
        settings = Settings()

        scheduler = MockScheduler()
        handlers = MockStepHandlers()

        with tempfile.TemporaryDirectory() as tmpdir:
            integrations = build_integrations(
                settings,
                scheduler=scheduler,
                step_handlers=handlers,
                data_dir=Path(tmpdir),
            )

        status_names = [s.name for s in integrations.statuses]

        # Check always-simulated components
        assert "sales_data" in status_names
        assert "alerts" in status_names
        assert "payout_rail" in status_names
        assert "lender" in status_names
        assert "kyc" in status_names

    def test_build_integrations_with_paytm_mcp(self):
        """Test building with Paytm MCP configured (skips creation without real MCP server)."""
        settings = Settings(
            paytm_mcp_url="http://localhost:8080/sse",
        )

        scheduler = MockScheduler()
        handlers = MockStepHandlers()

        with tempfile.TemporaryDirectory() as tmpdir:
            integrations = build_integrations(
                settings,
                scheduler=scheduler,
                step_handlers=handlers,
                data_dir=Path(tmpdir),
            )

        # Check that paytm status reflects MCP mode
        paytm_status = [s for s in integrations.statuses if s.name == "paytm"][0]
        assert "MCP" in paytm_status.detail

    def test_build_integrations_n8n_workflow_engine(self):
        """Test that n8n workflow engine is selected when configured."""
        settings = Settings(
            n8n_base_url="http://localhost:5678",
        )

        scheduler = MockScheduler()
        handlers = MockStepHandlers()

        with tempfile.TemporaryDirectory() as tmpdir:
            integrations = build_integrations(
                settings,
                scheduler=scheduler,
                step_handlers=handlers,
                data_dir=Path(tmpdir),
            )

        n8n_status = [s for s in integrations.statuses if s.name == "n8n"][0]
        assert n8n_status.detail == "webhook-based orchestration"

    def test_build_integrations_with_paytm_rest(self):
        """Test building with Paytm REST configured."""
        settings = Settings(
            paytm_mid="TEST_MID",
            paytm_key_secret="test_secret",
            paytm_mcp_url=None,
        )

        scheduler = MockScheduler()
        handlers = MockStepHandlers()

        with tempfile.TemporaryDirectory() as tmpdir:
            integrations = build_integrations(
                settings,
                scheduler=scheduler,
                step_handlers=handlers,
                data_dir=Path(tmpdir),
            )

        paytm_status = [s for s in integrations.statuses if s.name == "paytm"][0]
        assert "direct REST" in paytm_status.detail

    def test_build_integrations_with_cognee(self):
        """Test building with cognee enabled (falls back to simulated if not installed)."""
        settings = Settings(
            cognee_enabled=True,
        )

        scheduler = MockScheduler()
        handlers = MockStepHandlers()

        with tempfile.TemporaryDirectory() as tmpdir:
            integrations = build_integrations(
                settings,
                scheduler=scheduler,
                step_handlers=handlers,
                data_dir=Path(tmpdir),
            )

        memory_status = [s for s in integrations.statuses if s.name == "memory"][0]
        # Should be simulated since cognee is not installed in test environment
        assert "networkx" in memory_status.detail or "Cognee" in memory_status.detail

    def test_build_integrations_with_openmeteo_live(self):
        """Test building with live Open-Meteo."""
        settings = Settings(
            openmeteo_live=True,
        )

        scheduler = MockScheduler()
        handlers = MockStepHandlers()

        with tempfile.TemporaryDirectory() as tmpdir:
            integrations = build_integrations(
                settings,
                scheduler=scheduler,
                step_handlers=handlers,
                data_dir=Path(tmpdir),
            )

        weather_status = [s for s in integrations.statuses if s.name == "weather"][0]
        assert "live" in weather_status.detail
