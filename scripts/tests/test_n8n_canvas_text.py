"""Plain words on the n8n canvas: derived from the step offsets and true of the backend (SPEC §14.5, §17.2)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from typing import Any

import httpx
import pytest
from chhatri.api.demo.golden import CREDIT_TIME, GOLDEN, PAUSE_TIME, TRIGGER_TIME
from chhatri.detect.triggers import TRIGGER_ALERT_KINDS
from chhatri.integrations.base import IntegrationError, WorkflowRun
from chhatri.integrations.n8n import RUN_TIMEOUT_S, N8nWorkflowEngine
from chhatri.integrations.retry import ConnectionFailed
from chhatri.integrations.statuses import ALWAYS_SIMULATED
from chhatri.money import format_inr
from chhatri.workflows.definitions import WORKFLOWS, job_name
from chhatri.workflows.runner import InProcessWorkflowEngine

import n8n_canvas_text as text

RETRY = text.RetryPolicy(timeout_ms=10_000, max_tries=3, wait_ms=1_000)
PAYOUT = tuple(text.Step(s.name, s.delay_minutes_from_start) for s in WORKFLOWS["payout"])


def test_every_backend_step_has_plain_words() -> None:
    for workflow, specs in WORKFLOWS.items():
        assert text.workflow_text(workflow).display_name.startswith("Chhatri · ")
        for index, spec in enumerate(specs, start=1):
            label = text.step_text(workflow, spec.name).label
            assert text.step_node_name(workflow, index, spec.name) == f"{index} · {label}"
            assert len(label) <= 40, label  # two canvas lines at most
    assert set(text.STEP_TEXT) == {(w, s.name) for w, specs in WORKFLOWS.items() for s in specs}
    assert set(text.WORKFLOW_TEXT) == set(WORKFLOWS)


def test_unknown_steps_and_workflows_fail_loudly() -> None:
    with pytest.raises(text.UnknownStepError, match="add it to STEP_TEXT"):
        text.step_text("payout", "pay_twice")
    with pytest.raises(text.UnknownStepError, match="add it to WORKFLOW_TEXT"):
        text.workflow_text("refund")
    assert issubclass(text.UnknownStepError, ValueError)


@pytest.mark.parametrize(
    ("minutes", "shown"),
    [(0, "+0 min"), (4, "+4 min"), (59, "+59 min"), (60, "+1 h"), (90, "+90 min"), (1440, "+24 h")],
)
def test_format_offset(minutes: int, shown: str) -> None:
    assert text.format_offset(minutes) == shown


def test_format_offset_rejects_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        text.format_offset(-1)


def test_clock_after() -> None:
    assert text.clock_after("17:00", 4) == "17:04"
    assert text.clock_after("23:58", 5) == "00:03"


def test_monsoon_line_follows_the_offsets_and_the_golden_numbers() -> None:
    line = text.monsoon_line(PAYOUT)
    assert text.MONSOON_DECIDED == TRIGGER_TIME
    assert format_inr(GOLDEN.anil_payout_paise) == text.MONSOON_AMOUNT
    assert f"decided {TRIGGER_TIME}" in line
    assert f"{text.MONSOON_AMOUNT} credited to Anil at {CREDIT_TIME} with WhatsApp + Soundbox" in line
    assert line.endswith(f"tomorrow's instalment paused at {PAUSE_TIME}.")


def test_monsoon_line_splits_credit_and_message_when_their_times_differ() -> None:
    steps = (text.Step("credit_payout", 4), text.Step("notify_merchant", 6), text.Step("request_holiday", 7))
    line = text.monsoon_line(steps)
    assert "credited to Anil at 17:04; WhatsApp + Soundbox at 17:06" in line
    assert "paused at 17:07" in line
    with pytest.raises(text.UnknownStepError, match="request_holiday"):
        text.monsoon_line(steps[:2])


def test_backend_wait_matches_the_n8n_client() -> None:
    assert text.BACKEND_WAIT_S == RUN_TIMEOUT_S


def test_failure_note_is_derived_from_the_retry_settings() -> None:
    note = text.failure_markdown(RETRY)
    assert "times out after 10 s" in note and "tried again after a 1 s wait: 3 tries in all" in note
    assert "If all 3 fail, the run stops there" in note and "webhook answers 500" in note
    assert f"at most {RUN_TIMEOUT_S:g} s" in note and "(3 timed-out tries take 32 s)" in note
    assert RETRY.worst_case_ms / 1000 > RUN_TIMEOUT_S  # why the timeout case is not handed over
    assert "only the steps Chhatri has not already accepted from n8n" in note
    assert "steps n8n did not report" not in note and "workflow.start_failed" in note


def test_failure_note_hands_over_exactly_what_the_n8n_client_hands_over() -> None:
    """chhatri.integrations.n8n hands over ConnectionFailed (httpx.ConnectError: refused, unknown host),
    HttpStatusError (>= 400) and RunIncomplete; a timeout (httpx.TimeoutException, connecting included) or
    another transport error is a plain IntegrationError, audited as workflow.start_failed (retry.py)."""
    bullets = text.failure_markdown(RETRY).split("\n- ")[1:]
    assert len(bullets) == 4
    handover, timeout = bullets[2], bullets[3]
    assert "error status or without the completion" in handover
    assert "connecting to n8n fails outright (refused, unknown host)" in handover
    assert "built-in runner" in handover and "cannot be reached" not in handover
    assert "On a timeout (connecting included)" in timeout and "transport error" in timeout
    assert "does not take over" in timeout and "workflow.start_failed" in timeout
    # n8n can only still be running a request that reached it (not after a connect timeout)
    assert "(if the request reached n8n, n8n may still be running it)" in timeout
    assert "because n8n may still be running" not in timeout
    assert "non-2xx" not in text.failure_markdown(RETRY)  # n8n follows redirects; only 4xx/5xx fail a try


@pytest.mark.parametrize(
    ("raised", "handed_over"),
    [
        (httpx.ConnectError("refused"), True),
        (httpx.ConnectTimeout("connect timed out"), False),
        (httpx.ReadTimeout("no answer"), False),
        (httpx.RemoteProtocolError("connection dropped"), False),
    ],
)
def test_failure_handover_cases_match_the_n8n_client(raised: Exception, handed_over: bool) -> None:
    """What the failure note says about connecting and timeouts, checked against the real client."""

    def fail(request: httpx.Request) -> httpx.Response:
        raise raised

    class Fallback:
        started: list[str] = []

        async def start(self, workflow: str, payload: dict[str, str]) -> WorkflowRun:
            self.started.append(workflow)
            return WorkflowRun(workflow, "payout:D-1", "in-process", True, "4 steps scheduled")

    fallback = Fallback()
    engine = N8nWorkflowEngine(
        "http://n8n.invalid", "secret", fallback=fallback, transport=httpx.MockTransport(fail)
    )
    payload = {"decision_id": "D-1", "merchant_id": "S-0142"}
    if handed_over:
        run = asyncio.run(engine.start("payout", payload))
        assert run.engine == "in-process" and fallback.started == ["payout"]
    else:
        with pytest.raises(IntegrationError) as caught:
            asyncio.run(engine.start("payout", payload))
        assert not isinstance(caught.value, ConnectionFailed) and fallback.started == []


class _Scheduler:
    """The simulated scheduler as the built-in runner sees it; `accepted` = steps Chhatri took from n8n."""

    def __init__(self, accepted: set[str]) -> None:
        self.names = set(accepted)

    def schedule(self, at: datetime, name: str, fn: Callable[[], Awaitable[None]]) -> None:
        self.names.add(name)

    def now(self) -> datetime:
        return datetime(2025, 8, 19, 17, 0)

    def was_scheduled(self, name: str) -> bool:
        return name in self.names


class _Handlers:
    async def run_step(self, workflow: str, step: str, payload: Mapping[str, Any]) -> None:
        raise AssertionError("not run in this test")


def test_handover_schedules_only_the_steps_chhatri_has_not_accepted() -> None:
    """A step whose report Chhatri refused (404/409) was reported but never scheduled: the runner takes it."""
    payload = {"decision_id": "D-1", "merchant_id": "S-0142"}
    run_id = "payout:D-1"
    accepted = {job_name(run_id, "execute_payout")}  # credit_payout was reported but refused
    scheduler = _Scheduler(accepted)
    run = asyncio.run(InProcessWorkflowEngine(scheduler, _Handlers()).start("payout", payload))
    assert run.run_id == run_id and run.detail.startswith("3 steps scheduled")
    assert scheduler.names == {job_name(run_id, s.name) for s in PAYOUT}
    assert "only the steps Chhatri has not already accepted from n8n" in text.failure_markdown(RETRY)


def test_simulated_line_names_every_simulated_payout_party() -> None:
    simulated = {status.name for status in ALWAYS_SIMULATED}
    assert {"payout_rail", "lender"} <= simulated  # step 2 and step 4 (the 17:05 pause) are simulated
    checklist = text.checklist_markdown("payout", PAYOUT, "Completed (200)")
    assert "Simulated in this prototype: the settlement rail, the lender and the Soundbox;" in checklist


def test_merchant_message_names_telegram_for_merchants_who_chose_it() -> None:
    """With the telegram_channel flag on, a merchant who prefers Telegram gets the payout message there."""
    does = text.step_text("payout", "notify_merchant").does
    assert does.startswith("a payout message on WhatsApp (or Telegram, if chosen)")
    assert "Soundbox announcement" in does


def test_payout_starts_from_a_rain_or_bandh_area_trigger() -> None:
    kinds = {kind.value for kind in TRIGGER_ALERT_KINDS}
    assert kinds == {"RAIN", "CIVIC"}  # CIVIC = bandh / shutdown (chhatri.domain.enums.AlertKind)
    starts = text.WORKFLOW_TEXT["payout"].starts
    assert "rain or bandh alert" in starts and "weather trigger" not in starts
    assert "a personal claim" in starts and "a referred claim a claims officer approved" in starts


def test_human_review_names_both_officer_choices() -> None:
    decides = text.WORKFLOW_TEXT["human-review"].decides
    assert "approve or decline a referred claim" in decides
    assert "confirm or reject a dispute (either closes it; the disputed decision stands)" in decides
    assert "approves or declines the case" not in decides
    other = text.failure_markdown(text.RetryPolicy(timeout_ms=5_000, max_tries=2, wait_ms=500))
    assert "times out after 5 s" in other and "after a 0.5 s wait: 2 tries in all" in other
    assert "(2 timed-out tries take 10.5 s)" in other


def test_step_notes() -> None:
    notes = text.step_notes("payout", text.Step("credit_payout", 4), RETRY)
    assert notes.splitlines() == [
        "credit_payout (+4 min)",
        "POST /internal/workflows/credit_payout",
        "3 tries, 1 s wait between, 10 s timeout each",
        "Runs at decision +4 min, simulated time (Chhatri schedules it)",
    ]
    case = text.step_notes("follow-up", text.Step("check_case_sla", 1440), RETRY)
    assert case.splitlines()[-1] == "Runs at case opened +24 h, simulated time (Chhatri schedules it)"


def test_checklist_lists_each_step_with_its_time() -> None:
    checklist = text.checklist_markdown("payout", PAYOUT, "Completed (200)")
    for index, step in enumerate(PAYOUT, start=1):
        label = text.step_text("payout", step.name).label
        assert f"{index}. **{label}** · {text.format_offset(step.offset_minutes)}: " in checklist
    assert "after the decision" in checklist and "**Completed (200)**" in checklist
    assert "only after the last one was reported" in checklist
    assert "Monsoon replay" in checklist and "Simulated in this prototype" in checklist
    review = tuple(text.Step(s.name, s.delay_minutes_from_start) for s in WORKFLOWS["human-review"])
    case_list = text.checklist_markdown("human-review", review, "Completed (200)")
    assert "after the case opened" in case_list and "Monsoon" not in case_list


def test_title_and_security_notes() -> None:
    for workflow in WORKFLOWS:
        title = text.title_markdown(workflow)
        assert title.startswith(f"## {text.WORKFLOW_TEXT[workflow].display_name}\n\n**What starts it:**")
        assert "never decides" in title
    security = text.security_markdown("X-Chhatri-Secret", "Secret OK?")
    assert "X-Chhatri-Secret header" in security and "refused with 403 and n8n calls no step" in security
    assert "**Secret OK?** checks it" in security
