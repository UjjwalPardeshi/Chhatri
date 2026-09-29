"""Tests for n8n integration (SPEC §14.5)."""

import hmac
import hashlib

import pytest

from chhatri.integrations.base import IntegrationError
from chhatri.integrations.n8n import N8nWorkflowEngine


class TestN8nWorkflowEngine:
    """Tests for N8nWorkflowEngine."""

    @pytest.mark.asyncio
    async def test_verify_callback_valid_signature(self):
        """Test valid callback signature verification."""
        raw_body = b'{"run_id":"test"}'
        secret = "test_secret"
        expected_sig = hmac.new(
            secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()

        is_valid = N8nWorkflowEngine.verify_callback(raw_body, expected_sig, secret)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_callback_invalid_signature(self):
        """Test invalid callback signature."""
        raw_body = b'{"run_id":"test"}'
        is_valid = N8nWorkflowEngine.verify_callback(raw_body, "invalid_sig", "test_secret")
        assert is_valid is False

    def test_parse_callback_valid(self):
        """Test parsing valid callback payload."""
        payload = {
            "run_id": "run-123",
            "workflow": "payout",
            "step": "execute_payout",
            "payload": {"decision_id": "D-000001"},
        }

        run_id, workflow, step, callback_payload = N8nWorkflowEngine.parse_callback(payload)

        assert run_id == "run-123"
        assert workflow == "payout"
        assert step == "execute_payout"
        assert callback_payload == {"decision_id": "D-000001"}

    def test_parse_callback_missing_run_id(self):
        """Test parsing callback with missing run_id."""
        payload = {
            "workflow": "payout",
            "step": "execute_payout",
            "payload": {},
        }

        with pytest.raises(IntegrationError, match="Missing required fields"):
            N8nWorkflowEngine.parse_callback(payload)

    def test_parse_callback_missing_workflow(self):
        """Test parsing callback with missing workflow."""
        payload = {
            "run_id": "run-123",
            "step": "execute_payout",
            "payload": {},
        }

        with pytest.raises(IntegrationError, match="Missing required fields"):
            N8nWorkflowEngine.parse_callback(payload)

    def test_parse_callback_missing_step(self):
        """Test parsing callback with missing step."""
        payload = {
            "run_id": "run-123",
            "workflow": "payout",
            "payload": {},
        }

        with pytest.raises(IntegrationError, match="Missing required fields"):
            N8nWorkflowEngine.parse_callback(payload)

    def test_parse_callback_empty_payload(self):
        """Test parsing callback with empty payload dict."""
        payload = {
            "run_id": "run-123",
            "workflow": "payout",
            "step": "execute_payout",
            "payload": {},
        }

        run_id, workflow, step, callback_payload = N8nWorkflowEngine.parse_callback(payload)
        assert callback_payload == {}

    def test_parse_callback_missing_payload_field(self):
        """Test parsing callback without payload field (defaults to {})."""
        payload = {
            "run_id": "run-123",
            "workflow": "payout",
            "step": "execute_payout",
        }

        run_id, workflow, step, callback_payload = N8nWorkflowEngine.parse_callback(payload)
        assert callback_payload == {}
