"""n8n workflow engine client (SPEC §14.5, §24.5; binding decision B1).

`start(workflow, payload)` POSTs `{"run_id", "workflow", "payload"}` to
`{N8N_BASE_URL}/webhook/chhatri-{workflow}` with header `X-Chhatri-Secret`. n8n then calls back
`POST {CHHATRI_PUBLIC_URL}/internal/workflows/{step}` for each step in WORKFLOWS order, and the
backend (`Orchestrator.handle_callback`) schedules each effect at decision time + offset on the
simulated scheduler: n8n orders the steps but never decides and never sets the timing.

**A start returns only when n8n has finished the run.** The generated workflows
(`scripts/n8n_workflows.py`) answer the webhook from their last node, after every step's callback
was acknowledged, with ``{"ok": true, "data": {"run_id", "status": "completed", "steps": [...]}}``.
So when `start` returns, every step of the run is already on the simulated scheduler, and the
simulated clock cannot pass a step's due minute before n8n reported it: credits at 17:04 and
pauses at 17:05 exactly as in process (SPEC §17.2). An answer without that completion body (an
older workflow that answers first and calls back later) is treated like a failed start.

Failures:
- connect failure, a non-2xx answer (n8n answers 500 when a callback was refused, after its own
  three tries per callback) or a missing completion body: the run is handed to the `fallback`
  engine (the in-process runner), which schedules only the steps n8n did not already report
  (`Scheduler.was_scheduled`), and the returned WorkflowRun says so; logged at ERROR. The start
  itself is not retried: n8n already retried each callback, and a repeated start would only replay
  the same refusal.
- a timeout (`RUN_TIMEOUT_S`) is *not* handed over, because n8n may still be running the workflow
  and a second run could double-notify; the IntegrationError reaches the caller
  (`replay.runs.start_workflow` audits ``workflow.start_failed``).

Like the in-process engine, a run is started at most once per engine (run ids are deterministic,
`{workflow}:{subject}`): a repeated start returns `accepted=False, detail="already started"` without
posting again. The run id is claimed before the POST so concurrent starts cannot both post. A start
that definitely did not complete (connect failure, non-2xx, no completion) and has no fallback
releases the claim so it can be retried; after a timeout the claim is kept.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Mapping
from typing import Any, Final

import httpx

from chhatri.integrations.base import IntegrationError, WorkflowEngine, WorkflowRun
from chhatri.integrations.retry import (
    ConnectionFailed,
    HttpStatusError,
    RetryPolicy,
    Sleep,
    http_request,
)
from chhatri.workflows.callbacks import SECRET_HEADER
from chhatri.workflows.definitions import run_id_for, validate_payload

logger = logging.getLogger(__name__)

INTEGRATION: Final = "n8n"
ENGINE: Final = "n8n"
ALREADY_STARTED: Final = "already started"
COMPLETED: Final = "completed"
# One n8n run = up to 4 callbacks, each bounded by the workflow's 10 s HTTP timeout (SPEC §14).
RUN_TIMEOUT_S: Final = 30.0
# The start is not retried (see the module docstring); n8n retries each callback itself.
START_POLICY: Final = RetryPolicy(max_attempts=1)


class RunIncomplete(IntegrationError):
    """n8n answered 2xx without reporting this run as completed (e.g. an outdated workflow)."""

    def __init__(self, detail: str) -> None:
        super().__init__(INTEGRATION, f"run not reported completed ({detail})")


def webhook_url(base_url: str, workflow: str) -> str:
    return f"{base_url.rstrip('/')}/webhook/chhatri-{workflow}"


def check_completion(response: httpx.Response, run_id: str) -> None:
    """Raise RunIncomplete unless the body is ``{"ok": true, "data": {"run_id", "status": "completed"}}``."""
    try:
        body = response.json()
    except ValueError as exc:
        raise RunIncomplete("answer was not JSON") from exc
    data = body.get("data") if isinstance(body, Mapping) else None
    if not isinstance(data, Mapping) or body.get("ok") is not True:
        raise RunIncomplete("answer has no ok/data")
    if data.get("run_id") != run_id or data.get("status") != COMPLETED:
        raise RunIncomplete(f"status {data.get('status')!r}")


class N8nWorkflowEngine:
    """WorkflowEngine that runs workflows on n8n (optionally falling back to in-process)."""

    def __init__(
        self,
        base_url: str,
        internal_secret: str,
        *,
        fallback: WorkflowEngine | None = None,
        timeout_s: float = RUN_TIMEOUT_S,
        transport: httpx.AsyncBaseTransport | None = None,
        policy: RetryPolicy = START_POLICY,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("N8N_BASE_URL must be an http(s) URL")
        if not internal_secret:
            raise ValueError("CHHATRI_INTERNAL_SECRET is required for n8n")
        if timeout_s <= 0:
            raise ValueError("the n8n run timeout must be positive")
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
        """Run `workflow` on n8n and return once n8n reported every step (see the module docstring)."""
        checked = validate_payload(workflow, payload)
        run_id = run_id_for(workflow, checked)
        if not self._claim(run_id):
            logger.info("n8n: %s already started; ignored", run_id)
            return WorkflowRun(workflow, run_id, ENGINE, False, ALREADY_STARTED)
        body = {"run_id": run_id, "workflow": workflow, "payload": dict(checked)}
        try:
            response = await self._post(webhook_url(self._base_url, workflow), body)
            check_completion(response, run_id)
        except (ConnectionFailed, HttpStatusError, RunIncomplete) as exc:
            if self._fallback is None:
                self._release(run_id)
                raise
            return await self._hand_over(self._fallback, workflow, payload, run_id, exc)
        logger.info("n8n: completed %s", run_id)
        return WorkflowRun(
            workflow=workflow, run_id=run_id, engine=ENGINE, accepted=True, detail="completed on n8n"
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
        logger.error("n8n: could not run %s (%s); running in-process instead", run_id, exc.safe_message)
        run = await fallback.start(workflow, payload)
        return WorkflowRun(
            workflow=run.workflow,
            run_id=run.run_id,
            engine=run.engine,
            accepted=run.accepted,
            detail=f"n8n unavailable ({exc.safe_message}); {run.detail}",
        )

    async def _post(self, url: str, body: dict[str, Any]) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self._timeout_s, transport=self._transport) as client:
            return await http_request(
                client,
                "POST",
                url,
                integration=INTEGRATION,
                policy=self._policy,
                sleep=self._sleep,
                json=body,
                headers={SECRET_HEADER: self._secret},
            )
