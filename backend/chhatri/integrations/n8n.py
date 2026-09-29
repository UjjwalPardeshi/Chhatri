"""n8n workflow integration (SPEC §14.5).

Communicates with n8n via webhooks. The backend POSTs workflow payloads to n8n,
which calls back to the backend with step results.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from chhatri.integrations.base import IntegrationError, WorkflowRun

logger = logging.getLogger(__name__)


class N8nWorkflowEngine:
    """n8n workflow execution via webhooks."""

    def __init__(self, base_url: str, internal_secret: str, timeout: float = 5.0) -> None:
        """Initialize n8n workflow engine.

        Args:
            base_url: n8n base URL (e.g., http://localhost:5678).
            internal_secret: Shared secret for callbacks from n8n.
            timeout: HTTP request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.internal_secret = internal_secret
        self.timeout = timeout

    async def start(self, workflow: str, payload: dict[str, Any]) -> WorkflowRun:
        """Start a workflow on n8n.

        POSTs to {N8N_BASE_URL}/webhook/chhatri-{workflow} with header X-Chhatri-Secret
        and body {"run_id", "workflow", "payload"}.

        Args:
            workflow: Workflow name (e.g., "payout", "human-review", "follow-up").
            payload: Workflow payload dict.

        Returns:
            WorkflowRun with run_id and engine name.

        Raises:
            IntegrationError: If the request fails.
        """
        import uuid
        run_id = str(uuid.uuid4())

        request_body = {
            "run_id": run_id,
            "workflow": workflow,
            "payload": payload,
        }

        try:
            headers = {"X-Chhatri-Secret": self.internal_secret}
            url = f"{self.base_url}/webhook/chhatri-{workflow}"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=request_body, headers=headers)

            if response.status_code >= 400:
                raise IntegrationError(
                    "n8n",
                    f"Workflow start failed: HTTP {response.status_code}",
                    retryable=response.status_code >= 500,
                )

            return WorkflowRun(
                workflow=workflow,
                run_id=run_id,
                engine="n8n",
                accepted=True,
                detail="Started on n8n",
            )
        except IntegrationError:
            raise
        except TimeoutError:
            raise IntegrationError(
                "n8n",
                "Workflow start request timed out",
                retryable=True,
            ) from None
        except Exception as e:
            raise IntegrationError(
                "n8n",
                f"Failed to start workflow: {type(e).__name__}",
                retryable=True,
            ) from e

    @staticmethod
    def verify_callback(raw_body: bytes, signature_header: str,
                        internal_secret: str) -> bool:
        """Verify n8n callback signature.

        Uses HMAC-SHA256 with constant-time comparison.

        Args:
            raw_body: Raw callback body bytes.
            signature_header: Value of X-Chhatri-Secret header.
            internal_secret: Shared secret.

        Returns:
            True if signature is valid, False otherwise.
        """
        import hashlib
        import hmac
        expected = hmac.new(
            internal_secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature_header, expected)

    @staticmethod
    def parse_callback(payload: dict[str, Any]) -> tuple[str, str, str, dict[str, Any]]:
        """Parse n8n callback payload.

        Args:
            payload: Callback JSON payload.

        Returns:
            Tuple of (run_id, workflow, step, payload) from the request.

        Raises:
            IntegrationError: If payload is invalid.
        """
        try:
            run_id = payload.get("run_id", "")
            workflow = payload.get("workflow", "")
            step = payload.get("step", "")
            callback_payload = payload.get("payload", {})

            if not all([run_id, workflow, step]):
                raise IntegrationError(
                    "n8n",
                    "Missing required fields in callback payload",
                )

            return run_id, workflow, step, callback_payload
        except KeyError as e:
            raise IntegrationError(
                "n8n",
                f"Invalid callback payload structure: {e}",
            ) from e
