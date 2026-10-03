"""Plain words on the n8n canvas: derived from the step offsets and true of the backend (SPEC §14.5, §17.2)."""

from __future__ import annotations

import pytest
from chhatri.api.demo.golden import CREDIT_TIME, GOLDEN, PAUSE_TIME, TRIGGER_TIME
from chhatri.integrations.n8n import RUN_TIMEOUT_S
from chhatri.money import format_inr
from chhatri.workflows.definitions import WORKFLOWS

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
    assert "only the steps n8n did not report" in note and "workflow.start_failed" in note
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
    assert "Monsoon replay" in checklist and "Simulated in this prototype" in checklist
    review = tuple(text.Step(s.name, s.delay_minutes_from_start) for s in WORKFLOWS["human-review"])
    case_list = text.checklist_markdown("human-review", review, "Completed (200)")
    assert "after the case opened" in case_list and "Monsoon" not in case_list


def test_title_and_security_notes() -> None:
    for workflow in WORKFLOWS:
        title = text.title_markdown(workflow)
        assert title.startswith(f"## {text.WORKFLOW_TEXT[workflow].display_name}\n\n**What starts it:**")
        assert "never decides" in title
    security = text.security_markdown("X-Chhatri-Secret")
    assert "X-Chhatri-Secret header" in security and "refused with 403 and n8n calls no step" in security
