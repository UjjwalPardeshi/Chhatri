"""H21: the next action is decided by the backend from the answer type and the merchant's state (fs-05 section 9)."""

from __future__ import annotations

import pytest

from chhatri.ask import next_action as na
from chhatri.ask.copy import ACTION_LABELS
from chhatri.conversation.intents import Intent


@pytest.mark.parametrize(
    ("intent", "kwargs", "kind"),
    [
        (Intent.WHY_AMOUNT, {}, "SEE_CLAIM"),
        (Intent.COVER_STATUS, {}, "SEE_COVER"),
        (Intent.BUY_COVER, {}, "GET_COVER"),
        (Intent.REPORT_ILLNESS, {"check_in_open": True}, "SEND_SLIP"),
        (Intent.REPORT_ILLNESS, {"check_in_open": False}, "ASK_AGAIN"),
        (Intent.DISPUTE_AMOUNT, {"case_opened": True}, "TRACK_CASE"),
        (Intent.DISPUTE_AMOUNT, {"case_opened": False}, "ASK_AGAIN"),
        (Intent.GREETING, {}, "ASK_AGAIN"),
        (Intent.AFFIRM, {}, "ASK_AGAIN"),
        (Intent.UNKNOWN, {}, "ASK_AGAIN"),
    ],
)
def test_a_known_intent_has_its_action(intent: Intent, kwargs: dict[str, bool], kind: str) -> None:
    flags = {"case_opened": False, "check_in_open": False} | kwargs
    assert na.for_intent(intent, **flags).kind == kind


def clauses(
    *ids: str, decision: bool = True, check_in: bool = False, consents: bool = False, ladder: bool = False
) -> str:
    return na.for_clauses(
        ids, has_decision=decision, check_in_open=check_in, consents_on=consents, grievances_on=ladder
    ).kind


@pytest.mark.parametrize("clause", ["C2", "C3", "C4", "C4.3", "C8", "C10"])
def test_claim_clauses_see_the_claim_when_there_is_a_decision_else_the_cover(clause: str) -> None:
    assert clauses(clause) == "SEE_CLAIM" and clauses(clause, decision=False) == "SEE_COVER"


@pytest.mark.parametrize("clause", ["C5", "C6", "C7", "C12"])
def test_cover_clauses_see_the_cover(clause: str) -> None:
    assert clauses(clause) == "SEE_COVER"


def test_c11_opens_the_consents_once_n6_is_on_and_asks_again_before() -> None:
    assert clauses("C11") == "ASK_AGAIN" and clauses("C11", consents=True) == "OPEN_CONSENTS"


def test_c9_hands_off_where_there_is_a_destination() -> None:
    assert clauses("C9") == "TALK_TO_TEAM" and clauses("C9", decision=False) == "ASK_AGAIN"
    assert clauses("C9", decision=False, ladder=True) == "TALK_TO_TEAM"
    assert clauses("C2", "C9") == "TALK_TO_TEAM"


def test_an_open_check_in_asks_for_the_slip() -> None:
    assert clauses("C5", check_in=True) == "SEND_SLIP"


def test_no_clause_asks_again_and_every_label_is_in_the_closed_set() -> None:
    assert clauses() == "ASK_AGAIN"
    assert set(ACTION_LABELS) == {
        "SEE_CLAIM", "SEE_COVER", "GET_COVER", "SEND_SLIP", "TRACK_CASE", "OPEN_CONSENTS", "TALK_TO_TEAM", "ASK_AGAIN"
    }  # fmt: skip
    action = na.action("SEE_CLAIM")
    assert (action.label_hi, action.label_en) == ("मेरा दावा देखें", "See my claim")
