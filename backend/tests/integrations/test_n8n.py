"""n8n engine: POST {run_id, workflow, payload} with X-Chhatri-Secret, return once n8n completed (SPEC §14.5, B1)."""

from __future__ import annotations

import json

import httpx
import pytest

from chhatri.clock import ist
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.n8n import (
    RUN_TIMEOUT_S,
    N8nWorkflowEngine,
    RunIncomplete,
    check_completion,
    webhook_url,
)
from chhatri.workflows.runner import InProcessWorkflowEngine

from ..workflows.fakes import FakeScheduler, RecordingHandlers
from .conftest import no_sleep

PAYOUT = {"decision_id": "D-000001", "merchant_id": "S-0142"}
DECIDED = ist(2025, 8, 19, 17, 0)


def completed(run_id: str, status: str = "completed") -> httpx.Response:
    return httpx.Response(200, json={"ok": True, "data": {"run_id": run_id, "status": status, "steps": []}})


def completes(request: httpx.Request) -> httpx.Response:
    return completed(json.loads(request.content)["run_id"])


def engine(handler, *, fallback=None) -> N8nWorkflowEngine:  # type: ignore[no-untyped-def]
    return N8nWorkflowEngine(
        "http://n8n.local:5679/",
        "shh",
        fallback=fallback,
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
    )


def in_process() -> tuple[FakeScheduler, InProcessWorkflowEngine]:
    scheduler = FakeScheduler(DECIDED)
    return scheduler, InProcessWorkflowEngine(scheduler, RecordingHandlers())


async def test_start_posts_contract_body_and_secret_and_waits_for_completion() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return completes(request)

    run = await engine(handler).start("payout", dict(PAYOUT))
    assert (run.run_id, run.engine, run.accepted, run.detail) == (
        "payout:D-000001",
        "n8n",
        True,
        "completed on n8n",
    )
    request = seen[0]
    assert str(request.url) == "http://n8n.local:5679/webhook/chhatri-payout"
    assert request.headers["X-Chhatri-Secret"] == "shh"
    assert json.loads(request.content) == {
        "run_id": "payout:D-000001",
        "workflow": "payout",
        "payload": PAYOUT,
    }


async def test_server_errors_are_not_retried_and_hand_over() -> None:
    """n8n answers 500 when a callback was refused (after its own 3 tries): no second start."""
    posts: list[httpx.Request] = []

    def failing(request: httpx.Request) -> httpx.Response:
        posts.append(request)
        return httpx.Response(500, json={"message": "Error in workflow"})

    scheduler, fallback = in_process()
    run = await engine(failing, fallback=fallback).start("payout", dict(PAYOUT))
    assert len(posts) == 1
    assert run.engine == "in-process" and "HTTP 500" in run.detail and len(scheduler.jobs) == 4


async def test_unreachable_or_rejecting_n8n_falls_back_in_process() -> None:
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    scheduler, fallback = in_process()
    run = await engine(refused, fallback=fallback).start("payout", dict(PAYOUT))
    assert run.engine == "in-process" and run.accepted and "n8n unavailable" in run.detail
    assert len(scheduler.jobs) == 4
    rejected = await engine(lambda r: httpx.Response(404), fallback=fallback).start(
        "follow-up", {"case_id": "C-1"}
    )
    assert rejected.engine == "in-process" and "HTTP 404" in rejected.detail


async def test_partial_run_hands_over_only_unreported_steps() -> None:
    """n8n reported execute_payout, then failed: the fallback schedules the three remaining steps."""
    scheduler, fallback = in_process()

    async def reported() -> None:
        return None

    def partial(request: httpx.Request) -> httpx.Response:
        scheduler.schedule(DECIDED, "payout:D-000001:execute_payout", reported)
        return httpx.Response(500)

    run = await engine(partial, fallback=fallback).start("payout", dict(PAYOUT))
    assert run.engine == "in-process" and run.detail.endswith("3 steps scheduled from 17:00")
    assert [name.rsplit(":", 1)[1] for _, name, _ in scheduler.jobs] == [
        "execute_payout",
        "credit_payout",
        "notify_merchant",
        "pause_instalment",
    ]


async def test_answer_without_completion_is_a_failed_start() -> None:
    """An outdated workflow that answers 202 first and calls back later would break the timeline."""
    accepted = httpx.Response(
        202, json={"ok": True, "data": {"run_id": "payout:D-000001", "status": "accepted"}}
    )
    with pytest.raises(RunIncomplete, match="'accepted'"):
        await engine(lambda r: accepted).start("payout", dict(PAYOUT))
    scheduler, fallback = in_process()
    run = await engine(lambda r: accepted, fallback=fallback).start("payout", dict(PAYOUT))
    assert run.engine == "in-process" and "run not reported completed" in run.detail


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (httpx.Response(200, content=b"<html>"), "not JSON"),
        (httpx.Response(200, json=["ok"]), "no ok/data"),
        (httpx.Response(200, json={"ok": False, "data": {}}), "no ok/data"),
        (httpx.Response(200, json={"ok": True, "data": "done"}), "no ok/data"),
        (completed("payout:D-000002"), "status 'completed'"),
        (completed("payout:D-000001", "running"), "status 'running'"),
    ],
)
def test_check_completion_rejects(response: httpx.Response, reason: str) -> None:
    with pytest.raises(RunIncomplete, match=reason):
        check_completion(response, "payout:D-000001")


def test_check_completion_accepts_the_generated_answer() -> None:
    check_completion(completed("payout:D-000001"), "payout:D-000001")


async def test_without_fallback_errors_surface_and_timeouts_never_fall_back() -> None:
    with pytest.raises(IntegrationError, match="HTTP 500"):
        await engine(lambda r: httpx.Response(500)).start("payout", dict(PAYOUT))

    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    scheduler, fallback = in_process()
    with pytest.raises(IntegrationError, match="timed out"):
        await engine(slow, fallback=fallback).start("payout", dict(PAYOUT))
    assert scheduler.jobs == []


async def test_validation() -> None:
    with pytest.raises(ValueError):
        await engine(completes).start("payout", {"decision_id": "D-1"})
    with pytest.raises(ValueError):
        N8nWorkflowEngine("n8n:5678", "s")
    with pytest.raises(ValueError):
        N8nWorkflowEngine("http://n8n", "")
    with pytest.raises(ValueError, match="timeout"):
        N8nWorkflowEngine("http://n8n", "s", timeout_s=0)
    assert webhook_url("http://h/", "human-review") == "http://h/webhook/chhatri-human-review"
    assert RUN_TIMEOUT_S > 0


async def test_repeated_start_posts_once() -> None:
    """Same contract as the in-process engine: one run per subject, a repeat is not re-posted."""
    posts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        posts.append(request)
        return completes(request)

    n8n = engine(handler)
    first = await n8n.start("payout", dict(PAYOUT))
    again = await n8n.start("payout", dict(PAYOUT))
    assert first.accepted and (again.accepted, again.detail, again.engine) == (
        False,
        "already started",
        "n8n",
    )
    assert len(posts) == 1


async def test_failed_start_can_be_retried() -> None:
    outcomes = iter([httpx.Response(404), completed("follow-up:C-2291")])
    n8n = engine(lambda r: next(outcomes))
    with pytest.raises(IntegrationError, match="HTTP 404"):
        await n8n.start("follow-up", {"case_id": "C-2291"})
    assert (await n8n.start("follow-up", {"case_id": "C-2291"})).accepted


async def test_timed_out_start_is_not_posted_twice() -> None:
    posts: list[httpx.Request] = []

    def slow(request: httpx.Request) -> httpx.Response:
        posts.append(request)
        raise httpx.ReadTimeout("slow", request=request)

    n8n = engine(slow)
    with pytest.raises(IntegrationError, match="timed out"):
        await n8n.start("payout", dict(PAYOUT))
    again = await n8n.start("payout", dict(PAYOUT))
    assert again.accepted is False and len(posts) == 1
