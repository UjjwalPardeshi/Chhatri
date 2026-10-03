"""The merchant's open next step, and the yes / no / "team" words and buttons that answer it (demo-day L1 to L3).

A typed "yes" while a read slip waits for "Yes, this is right" must confirm it, not answer the old check-in question
(L2); a Telegram merchant taps the same actions as inline buttons (L1); and when a message is not about the open step
the reply says what to do next instead of the generic help line (L3). Order, first match wins:

| step            | when                                                              | a reply that is not about it says |
|-----------------|-------------------------------------------------------------------|-----------------------------------|
| CONSENT         | the latest open pre-check waits for the doctor question (AWAITING_CONSENT) | DOCTOR_CONSENT_REMIND |
| PRECHECK_READY  | it is READY                                                       | SLIP_PRECHECK_REMIND              |
| PRECHECK_TEAM   | it is RETAKE or NEEDS_TEAM                                        | SLIP_TEAM_REMIND (_ONLY_ without retakes) |
| SLIP_WANTED     | a check-in is open and no pre-check waits                         | ASK_SLIP                          |
| DOCTOR_WAITING  | the latest decision still waits for the doctor (`DoctorCheckPort`) | DOCTOR_WAITING                   |
| CLAIM_WITH_TEAM | a claim review or dispute case of the merchant is open             | CLAIM_WITH_TEAM                   |

Button data (≤ 64 bytes): ``pc:<PC-id>:confirm|team`` and ``cs:<PC-id>:yes|no``. ``yes_no`` keeps the word lists of
``intents.classify``: an AFFIRM or DENY message answers, an UNKNOWN or GREETING one answers only when its first word is a
yes or no word ("Yes, this is right"), and any other intent ("yes why did I get only 1500") is a question, not an answer.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from chhatri.conversation.intents import Intent, classify, normalise
from chhatri.conversation.messages import bilingual
from chhatri.conversation.outbox import Outgoing
from chhatri.conversation.ports import ConversationStore, DoctorCheckPort
from chhatri.domain.enums import CaseKind, CaseStatus
from chhatri.precheck.model import Action, Precheck, PrecheckStatus

__all__ = [
    "CHOICE_ACTIONS",
    "Choice",
    "ChoiceKind",
    "PendingStep",
    "StepKind",
    "choice_button",
    "choice_data",
    "choice_label",
    "parse_choice",
    "resolve_step",
    "step_reminder",
    "wants_team",
    "yes_no",
]


class StepKind(StrEnum):
    CONSENT = "CONSENT"
    PRECHECK_READY = "PRECHECK_READY"
    PRECHECK_TEAM = "PRECHECK_TEAM"
    SLIP_WANTED = "SLIP_WANTED"
    DOCTOR_WAITING = "DOCTOR_WAITING"
    CLAIM_WITH_TEAM = "CLAIM_WITH_TEAM"


@dataclass(frozen=True, slots=True)
class PendingStep:
    kind: StepKind
    precheck_id: str | None = None
    case_id: str | None = None
    retakes_left: int = 0


class ChoiceKind(StrEnum):
    PRECHECK = "pc"
    CONSENT = "cs"


@dataclass(frozen=True, slots=True)
class Choice:
    kind: ChoiceKind
    precheck_id: str
    answer: str  # "confirm" | "team" for PRECHECK, "yes" | "no" for CONSENT


_CHOICE: Final = {
    ChoiceKind.PRECHECK: re.compile(r"^pc:(PC-\d{6,}):(confirm|team)$"),
    ChoiceKind.CONSENT: re.compile(r"^cs:(PC-\d{6,}):(yes|no)$"),
}
CHOICE_ACTIONS: Final = {
    (ChoiceKind.PRECHECK, "confirm"): Action.CONFIRM,
    (ChoiceKind.PRECHECK, "team"): Action.SEND_TO_TEAM,
    (ChoiceKind.CONSENT, "yes"): Action.CONSENT_YES,
    (ChoiceKind.CONSENT, "no"): Action.CONSENT_NO,
}
# The catalogue line each button shows (Telegram title "hi / en"; the inbound message records the English one).
_LABEL_KEYS: Final = {
    (ChoiceKind.PRECHECK, "confirm"): "SLIP_ACTION_CONFIRM",
    (ChoiceKind.PRECHECK, "team"): "SLIP_ACTION_TEAM",
    (ChoiceKind.CONSENT, "yes"): "DOCTOR_CONSENT_YES",
    (ChoiceKind.CONSENT, "no"): "DOCTOR_CONSENT_NO",
}
YES_WORDS: Final = frozenset(
    {"yes", "y", "haan", "han", "ha", "haa", "ji", "jee", "ok", "okay", "sure", "हां", "हा", "जी", "सही"}
)
NO_WORDS: Final = frozenset({"no", "n", "nahi", "nahin", "nhi", "na", "mat", "नहीं", "नही", "ना", "मत"})
TEAM_WORDS: Final = frozenset({"team", "टीम"})
_OPEN_CASE_KINDS: Final = frozenset({CaseKind.PERSONAL_CLAIM_REVIEW, CaseKind.DISPUTE})


def parse_choice(data: str) -> Choice | None:
    """The choice a Telegram button stands for, or None for any other callback data."""
    for kind, pattern in _CHOICE.items():
        match = pattern.match(data)
        if match:
            return Choice(kind, match.group(1), match.group(2))
    return None


def choice_data(choice: Choice) -> str:
    return f"{choice.kind.value}:{choice.precheck_id}:{choice.answer}"


def choice_label(choice: Choice) -> tuple[str, str]:
    """(Hindi, English) words of the button."""
    return bilingual(_LABEL_KEYS[(choice.kind, choice.answer)])


def choice_button(kind: ChoiceKind, precheck_id: str, answer: str) -> tuple[str, str]:
    """(callback data, "hi / en" title) for one Telegram button."""
    choice = Choice(kind, precheck_id, answer)
    hi, en = choice_label(choice)
    return choice_data(choice), f"{hi} / {en}"


def yes_no(text: str) -> bool | None:
    """True for a yes, False for a no, None when the message is about something else."""
    intent = classify(text)
    if intent is Intent.AFFIRM:
        return True
    if intent is Intent.DENY:
        return False
    if intent not in (Intent.UNKNOWN, Intent.GREETING):
        return None
    tokens = normalise(text).split()
    first = tokens[0] if tokens else ""
    if first in YES_WORDS:
        return True
    if first in NO_WORDS:
        return False
    return None


def wants_team(text: str) -> bool:
    """ "team", "टीम", "send to team", "हमारी टीम को भेजें"."""
    return any(token in TEAM_WORDS for token in normalise(text).split())


def resolve_step(
    merchant_id: str,
    *,
    precheck: Precheck | None,
    checkin_open: bool,
    store: ConversationStore,
    doctor: DoctorCheckPort | None = None,
    latest_decision_id: Callable[[str], str | None] | None = None,
) -> PendingStep | None:
    """The merchant's open next step (module docstring), or None."""
    if precheck is not None:
        if precheck.status is PrecheckStatus.AWAITING_CONSENT:
            return PendingStep(StepKind.CONSENT, precheck.id)
        if precheck.status is PrecheckStatus.READY:
            return PendingStep(StepKind.PRECHECK_READY, precheck.id)
        return PendingStep(StepKind.PRECHECK_TEAM, precheck.id, retakes_left=precheck.retakes_left)
    if checkin_open:
        return PendingStep(StepKind.SLIP_WANTED)
    decision_id = latest_decision_id(merchant_id) if latest_decision_id is not None else None
    if doctor is not None and decision_id is not None and doctor.doctor_check_pending(decision_id):
        return PendingStep(StepKind.DOCTOR_WAITING)
    case = next(
        (
            c
            for c in sorted(store.cases(), key=lambda c: c.opened_at, reverse=True)
            if c.merchant_id == merchant_id and c.kind in _OPEN_CASE_KINDS and c.status is CaseStatus.OPEN
        ),
        None,
    )
    return None if case is None else PendingStep(StepKind.CLAIM_WITH_TEAM, case_id=case.id)


def step_reminder(step: PendingStep) -> Outgoing:
    """What to say when a message is not about the open step: the step's own line, with its buttons on Telegram."""
    if step.kind is StepKind.CONSENT and step.precheck_id:
        buttons = tuple(choice_button(ChoiceKind.CONSENT, step.precheck_id, a) for a in ("yes", "no"))
        return _with_buttons(Outgoing.text("DOCTOR_CONSENT_REMIND"), buttons)
    if step.kind is StepKind.PRECHECK_READY and step.precheck_id:
        button = choice_button(ChoiceKind.PRECHECK, step.precheck_id, "confirm")
        return _with_buttons(Outgoing.text("SLIP_PRECHECK_REMIND"), (button,))
    if step.kind is StepKind.PRECHECK_TEAM and step.precheck_id:
        key = "SLIP_TEAM_REMIND" if step.retakes_left > 0 else "SLIP_TEAM_ONLY_REMIND"
        button = choice_button(ChoiceKind.PRECHECK, step.precheck_id, "team")
        return _with_buttons(Outgoing.text(key), (button,))
    if step.kind is StepKind.CLAIM_WITH_TEAM and step.case_id:
        return Outgoing.text("CLAIM_WITH_TEAM", case_id=step.case_id)
    if step.kind is StepKind.DOCTOR_WAITING:
        return Outgoing.text("DOCTOR_WAITING")
    return Outgoing.text("ASK_SLIP")


def _with_buttons(out: Outgoing, buttons: tuple[tuple[str, str], ...]) -> Outgoing:
    return replace(out, buttons=buttons)
