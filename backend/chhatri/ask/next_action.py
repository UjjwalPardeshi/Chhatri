"""H21: the one next action of an answer, chosen by the backend from the answer type and the merchant's state.

The set is closed (`ACTION_LABELS`); a model never chooses it (fs-05 section 9). Until N5 (grievances) is on,
TALK_TO_TEAM opens the dispute button, which needs a decision, so a merchant with none gets ASK_AGAIN instead. Until N6
(consents) is on, a clause C11 answer gets ASK_AGAIN.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from chhatri.ask.copy import ACTION_LABELS
from chhatri.ask.types import NextAction
from chhatri.conversation.intents import Intent

__all__ = ["action", "for_clauses", "for_intent", "talk_to_team"]

_CLAIM_CLAUSES: Final = frozenset({"C2", "C3", "C4", "C8", "C10"})
_COVER_CLAUSES: Final = frozenset({"C5", "C6", "C7", "C12"})
_BY_INTENT: Final = {
    Intent.WHY_AMOUNT: "SEE_CLAIM",
    Intent.COVER_STATUS: "SEE_COVER",
    Intent.BUY_COVER: "GET_COVER",
}


def action(kind: str) -> NextAction:
    label_hi, label_en = ACTION_LABELS[kind]
    return NextAction(kind, label_hi, label_en)


def talk_to_team(*, has_decision: bool, grievances_on: bool) -> NextAction:
    """TALK_TO_TEAM where it has a destination (the dispute button, or the N5 ladder), else ASK_AGAIN."""
    return action("TALK_TO_TEAM" if grievances_on or has_decision else "ASK_AGAIN")


def for_intent(intent: Intent, *, case_opened: bool, check_in_open: bool) -> NextAction:
    """The next action of a known intent answered by the rules."""
    if intent is Intent.DISPUTE_AMOUNT:
        return action("TRACK_CASE" if case_opened else "ASK_AGAIN")
    if intent is Intent.REPORT_ILLNESS:
        return action("SEND_SLIP" if check_in_open else "ASK_AGAIN")
    return action(_BY_INTENT.get(intent, "ASK_AGAIN"))


def _base(clause_id: str) -> str:
    return clause_id.split(".", maxsplit=1)[0]


def for_clauses(
    clause_ids: Sequence[str],
    *,
    has_decision: bool,
    check_in_open: bool,
    consents_on: bool,
    grievances_on: bool,
) -> NextAction:
    """The next action of a model answer from the clauses it cites (the first one decides, C9 always hands off)."""
    bases = [_base(clause_id) for clause_id in clause_ids]
    if "C9" in bases:
        return talk_to_team(has_decision=has_decision, grievances_on=grievances_on)
    if check_in_open:
        return action("SEND_SLIP")
    for base in bases:
        if base in _CLAIM_CLAUSES:
            return action("SEE_CLAIM" if has_decision else "SEE_COVER")
        if base in _COVER_CLAUSES:
            return action("SEE_COVER")
        if base == "C11":
            return action("OPEN_CONSENTS" if consents_on else "ASK_AGAIN")
    return action("ASK_AGAIN")
