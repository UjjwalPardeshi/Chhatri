"""n8n workflow engine client (SPEC §14.5, §24.5; binding decision B1).

`start(workflow, payload)` POSTs `{"run_id", "workflow", "payload"}` to
`{N8N_BASE_URL}/webhook/chhatri-{workflow}` with header `X-Chhatri-Secret`. n8n then calls back
`POST {CHHATRI_PUBLIC_URL}/internal/workflows/{step}` for each step in WORKFLOWS order, and the
backend schedules each effect at decision time + offset — n8n orders the steps but never decides and
never sets the timing.

If n8n cannot be reached (connect failure) or rejects the start (non-2xx), the run is handed to the
`fallback` engine (the in-process runner — same steps, same timeline) and the returned WorkflowRun says
so; the failure is logged at ERROR. A timeout is *not* handed over, because n8n may already be running
the workflow and a second run could double-notify.

Like the in-process engine, a run is started at most once per engine (run ids are deterministic,
`{workflow}:{subject}`): a repeated start returns `accepted=False, detail="already started"` without
posting again. The run id is claimed before the POST so concurrent starts cannot both post. A start
that definitely did not reach n8n (connect failure or non-2xx) and has no fallback releases the claim
so it can be retried; after a timeout the claim is kept, because n8n may already be running it.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

import httpx

from chhatri.integrations.base import IntegrationError, WorkflowEngine, WorkflowRun
from chhatri.integrations.retry import (
    DEFAULT_RETRY,
    DEFAULT_TIMEOUT_S,
    ConnectionFailed,
    HttpStatusError,
    RetryPolicy,
    Sleep,
    http_request,
)
from chhatri.workflows.callbacks import SECRET_HEADER
from chhatri.workflows.definitions import run_id_for, validate_payload

logger = logging.getLogger(__name__)

INTEGRATION = "n8n"
ENGINE = "n8n"
ALREADY_STARTED = "already started"


def webhook_url(base_url: str, workflow: str) -> str:
    return f"{base_url.rstrip('/')}/webhook/chhatri-{workflow}"


class N8nWorkflowEngine:
    """WorkflowEngine that hands workflows to n8n (optionally falling back to in-process)."""

    def __init__(
        self,
        base_url: str,
        internal_secret: str,
        *,
        fallback: WorkflowEngine | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        transport: httpx.AsyncBaseTransport | None = None,
        policy: RetryPolicy = DEFAULT_RETRY,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("N8N_BASE_URL must be an http(s) URL")
        if not internal_secret:
            raise ValueError("CHHATRI_INTERNAL_SECRET is required for n8n")
        self._base_url = base_url
        self._secret = internal_secret
        self._fallback = fallback
        self._timeout_s = timeout_s
        self._transport = transport
        self._policy = policy
        self._sleep = sleep
        self._started: set[str] = set()
        self._lock = threading.Lock()

    async def start(self, workflow: str, payload: dict[str, Any]) -> WorkflowRun:
        checked = validate_payload(workflow, payload)
        run_id = run_id_for(workflow, checked)
        if not self._claim(run_id):
            logger.info("n8n: %s already started; ignored", run_id)
            return WorkflowRun(workflow, run_id, ENGINE, False, ALREADY_STARTED)
        body = {"run_id": run_id, "workflow": workflow, "payload": dict(checked)}
        try:
            await self._post(webhook_url(self._base_url, workflow), body)
        except (ConnectionFailed, HttpStatusError) as exc:
            if self._fallback is None:
                self._release(run_id)
                raise
            return await self._hand_over(self._fallback, workflow, payload, run_id, exc)
        logger.info("n8n: started %s", run_id)
        return WorkflowRun(
            workflow=workflow, run_id=run_id, engine=ENGINE, accepted=True, detail="started on n8n"
        )

    def _claim(self, run_id: str) -> bool:
        with self._lock:
            if run_id in self._started:
                return False
            self._started.add(run_id)
            return True

    def _release(self, run_id: str) -> None:
        with self._lock:
            self._started.discard(run_id)

    @staticmethod
    async def _hand_over(
        fallback: WorkflowEngine,
        workflow: str,
        payload: dict[str, Any],
        run_id: str,
        exc: IntegrationError,
    ) -> WorkflowRun:
        logger.error("n8n: could not start %s (%s); running in-process instead", run_id, exc.safe_message)
        run = await fallback.start(workflow, payload)
        return WorkflowRun(
            workflow=run.workflow,
            run_id=run.run_id,
            engine=run.engine,
            accepted=run.accepted,
            detail=f"n8n unavailable ({exc.safe_message}); {run.detail}",
        )

    async def _post(self, url: str, body: dict[str, Any]) -> None:
        async with httpx.AsyncClient(timeout=self._timeout_s, transport=self._transport) as client:
            await http_request(
                client,
                "POST",
                url,
                integration=INTEGRATION,
                policy=self._policy,
                sleep=self._sleep,
                json=body,
                headers={SECRET_HEADER: self._secret},
            )
