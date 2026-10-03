"""Plain words on the n8n canvas: node names, node notes and sticky-note text (SPEC §14.5, §15; B1).

Every sentence here must stay true of the code it describes:

- `chhatri.replay.runs` / `area` / `personal` / `officer` / `cases_flow`: what starts each workflow;
- `chhatri.replay.orchestrator.handle_callback` and `chhatri.replay.steps`: what each step does, and
  that each report is re-checked and run at the run's start + the step's simulated offset;
- `chhatri.integrations.n8n` and `chhatri.workflows.runner`: what happens when a run fails;
- `scripts/n8n_workflows.py`: the secret check and the callback retry settings.

Times are derived from the StepSpec offsets, never written by hand. A step without a plain-words text
makes the generator fail (`UnknownStepError`), so a new backend step cannot reach n8n unexplained.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, NamedTuple

MINUTES_PER_HOUR: Final = 60
CALLBACK_PATH: Final = "/internal/workflows"
BACKEND_WAIT_S: Final = 30  # chhatri.integrations.n8n.RUN_TIMEOUT_S (a test keeps them equal)

# The monsoon replay (SPEC §17.2): decisions at 17:00; Anil (Z7) is paid ₹1,380. Checked against
# chhatri.api.demo.golden by the tests; the step times are computed from the offsets.
MONSOON_DECIDED: Final = "17:00"
MONSOON_MERCHANT: Final = "Anil"
MONSOON_AMOUNT: Final = "₹1,380"
MONSOON_STEPS: Final = ("credit_payout", "notify_merchant", "request_holiday")


class Step(NamedTuple):
    """One workflow step: its backend key and its offset from the run's start, in simulated minutes."""

    name: str
    offset_minutes: int


class UnknownStepError(ValueError):
    """A workflow or step has no plain-words text for the canvas."""


@dataclass(frozen=True, slots=True)
class StepText:
    label: str  # the node name after "N · "; short enough for two canvas lines
    does: str  # what the step does, in plain words (the checklist line)


@dataclass(frozen=True, slots=True)
class WorkflowText:
    display_name: str
    anchor: str  # what the offsets count from, e.g. "the decision"
    anchor_short: str  # the same in a node note, e.g. "decision"
    starts: str
    decides: str


WORKFLOW_TEXT: Final[Mapping[str, WorkflowText]] = MappingProxyType(
    {
        "payout": WorkflowText(
            display_name="Chhatri · Payout (approved claim)",
            anchor="the decision",
            anchor_short="decision",
            starts="**What starts it:** Chhatri approved a claim: an area claim from a weather trigger "
            "such as the monsoon storm, a personal claim, or a referred claim a claims officer approved.",
            decides="**n8n never decides money.** Chhatri's policy engine made the decision, amount included, "
            "before this run starts. n8n runs the checklist and reports every step back to Chhatri, "
            "which re-checks each report.",
        ),
        "human-review": WorkflowText(
            display_name="Chhatri · Human review (referred claim or dispute)",
            anchor="the case opened",
            anchor_short="case opened",
            starts="**What starts it:** Chhatri opened a case for a claims officer: its policy engine "
            "referred a personal claim to a person, or a merchant disputed a decision.",
            decides="**n8n never decides.** The officer approves or declines the case in Chhatri's console. "
            "n8n runs the checklist and reports every step back to Chhatri, which re-checks each report.",
        ),
        "follow-up": WorkflowText(
            display_name="Chhatri · Follow-up (case deadline)",
            anchor="the case opened",
            anchor_short="case opened",
            starts="**What starts it:** the same case opening as Human review: Chhatri starts this run "
            "right after that one, for the same case.",
            decides="**n8n never decides.** It reports the steps back to Chhatri, which re-checks each "
            "report and runs it at its due time.",
        ),
    }
)

STEP_TEXT: Final[Mapping[tuple[str, str], StepText]] = MappingProxyType(
    {
        ("payout", "execute_payout"): StepText(
            "Prepare the payout", "Chhatri re-checks the approved decision and records the payout."
        ),
        ("payout", "credit_payout"): StepText(
            "Credit ₹ to merchant", "the payout is credited on the Paytm settlement rail."
        ),
        ("payout", "notify_merchant"): StepText(
            "Tell merchant: WhatsApp + Soundbox",
            "the merchant gets the payout message and a Soundbox announcement.",
        ),
        ("payout", "request_holiday"): StepText(
            "Ask lender to pause next instalment",
            "the lender decides on the next day's instalment (with x4_lender_request off, Chhatri "
            "pauses it).",
        ),
        ("human-review", "open_case"): StepText(
            "Queue for an officer",
            "Chhatri publishes the case to the console's officer queue; the live feed shows its due time.",
        ),
        ("human-review", "notify_officer"): StepText(
            "Notify the officer", "Chhatri records the alert in the audit log (case.officer_notified)."
        ),
        ("follow-up", "check_case_sla"): StepText(
            "Check the deadline",
            "Chhatri records whether the case is still open at its due time (case.sla_checked); "
            "if it is, the live feed says it is past its SLA.",
        ),
        ("follow-up", "notify_officer"): StepText(
            "Remind officer if open",
            "only if the case is still open, Chhatri records a reminder in the audit log "
            "(case.officer_reminded).",
        ),
    }
)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """The step callbacks' n8n settings (timeout per try, tries in all, wait between tries)."""

    timeout_ms: int
    max_tries: int
    wait_ms: int

    @property
    def worst_case_ms(self) -> int:
        """How long a callback that times out on every try keeps the run busy."""
        return self.max_tries * self.timeout_ms + (self.max_tries - 1) * self.wait_ms


def workflow_text(workflow: str) -> WorkflowText:
    text = WORKFLOW_TEXT.get(workflow)
    if text is None:
        raise UnknownStepError(f"no plain-words text for workflow {workflow!r}: add it to WORKFLOW_TEXT")
    return text


def step_text(workflow: str, step: str) -> StepText:
    text = STEP_TEXT.get((workflow, step))
    if text is None:
        raise UnknownStepError(
            f"no plain-words label for step {step!r} of workflow {workflow!r}: "
            "add it to STEP_TEXT in scripts/n8n_canvas_text.py"
        )
    return text


def step_node_name(workflow: str, index: int, step: str) -> str:
    """The canvas name of a step node, e.g. ``2 · Credit ₹ to merchant``."""
    return f"{index} · {step_text(workflow, step).label}"


def format_offset(minutes: int) -> str:
    """``+0 min``, ``+4 min``, ``+24 h`` (whole hours from 60 minutes on)."""
    if minutes < 0:
        raise ValueError("step offsets are non-negative")
    if minutes >= MINUTES_PER_HOUR and minutes % MINUTES_PER_HOUR == 0:
        return f"+{minutes // MINUTES_PER_HOUR} h"
    return f"+{minutes} min"


def _seconds(milliseconds: int) -> str:
    return f"{milliseconds / 1000:g} s"


def step_notes(workflow: str, step: Step, retry: RetryPolicy) -> str:
    """Node notes: the step key and simulated time first (shown under the node), then the callback."""
    anchor, offset = workflow_text(workflow).anchor_short, format_offset(step.offset_minutes)
    return (
        f"{step.name} ({offset})\n"
        f"POST {CALLBACK_PATH}/{step.name}\n"
        f"{retry.max_tries} tries, {_seconds(retry.wait_ms)} wait between, {_seconds(retry.timeout_ms)} timeout each\n"
        f"Runs at {anchor} {offset}, simulated time (Chhatri schedules it)"
    )


def title_markdown(workflow: str) -> str:
    text = workflow_text(workflow)
    return f"## {text.display_name}\n\n{text.starts}\n\n{text.decides}"


def security_markdown(header: str) -> str:
    return (
        "### Security check\n\n"
        f"Every run must carry the shared secret in its {header} header. A wrong or missing secret is "
        "refused with 403 and n8n calls no step. If n8n has no secret set, every run is refused.\n\n"
        "Each step report carries the same secret, and Chhatri checks it."
    )


def clock_after(start: str, minutes: int) -> str:
    """``HH:MM`` that many minutes after ``start`` (``HH:MM``), on a 24-hour clock."""
    hours, mins = (int(part) for part in start.split(":"))
    total = hours * MINUTES_PER_HOUR + mins + minutes
    return f"{total // MINUTES_PER_HOUR % 24:02d}:{total % MINUTES_PER_HOUR:02d}"


def monsoon_line(steps: Sequence[Step]) -> str:
    """The SPEC §17.2 storm as this workflow's offsets time it (payout only)."""
    offsets = {step.name: step.offset_minutes for step in steps}
    missing = [name for name in MONSOON_STEPS if name not in offsets]
    if missing:
        raise UnknownStepError(f"the monsoon example needs the payout steps {', '.join(missing)}")
    credit, notify, pause = (clock_after(MONSOON_DECIDED, offsets[name]) for name in MONSOON_STEPS)
    paid = f"{MONSOON_AMOUNT} credited to {MONSOON_MERCHANT} at {credit}"
    told = (
        f"{paid} with WhatsApp + Soundbox" if notify == credit else f"{paid}; WhatsApp + Soundbox at {notify}"
    )
    return (
        f"**Monsoon replay:** decided {MONSOON_DECIDED} → {told} → tomorrow's instalment paused at {pause}."
    )


def checklist_markdown(workflow: str, steps: Sequence[Step], done_node: str) -> str:
    anchor = workflow_text(workflow).anchor
    lines = [
        f"{index}. **{step_text(workflow, step.name).label}** · {format_offset(step.offset_minutes)}: "
        f"{step_text(workflow, step.name).does}"
        for index, step in enumerate(steps, start=1)
    ]
    blocks = [
        "### Checklist: n8n reports each step, Chhatri does it",
        "No Wait nodes: n8n reports the steps right away, one after another; Chhatri runs each one at "
        f"its simulated time after {anchor}.",
        "\n".join(lines),
        f"Then **{done_node}** answers Chhatri, only after the last step was reported.",
    ]
    if workflow == "payout":
        blocks += [
            monsoon_line(steps),
            "*Simulated in this prototype: the settlement rail and the Soundbox; WhatsApp is live only "
            "with its keys and a demo recipient.*",
        ]
    return "\n\n".join(blocks)


def failure_markdown(retry: RetryPolicy) -> str:
    tries, wait, timeout = retry.max_tries, _seconds(retry.wait_ms), _seconds(retry.timeout_ms)
    return (
        "### If a step fails\n\n"
        f"- A step report that errors, times out after {timeout} or gets a non-2xx answer is tried again "
        f"after a {wait} wait: {tries} tries in all.\n"
        f"- If all {tries} fail, the run stops there: later steps are not called and the webhook "
        "answers 500.\n"
        "- If the webhook answers with an error or without the completion, or n8n cannot be reached, "
        "Chhatri hands the run to its built-in runner. It schedules only the steps n8n did not report, "
        "so no step runs twice.\n"
        f"- Chhatri waits at most {BACKEND_WAIT_S} s for the answer ({tries} timed-out tries take "
        f"{_seconds(retry.worst_case_ms)}). If none comes, it does not take over, because n8n may still be "
        "running: it records workflow.start_failed in the audit log."
    )
