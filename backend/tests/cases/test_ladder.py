"""N5 (fs-06 sections 7 and 8): the respondent router, the ladders and the response clocks. Pure code, no store."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from chhatri.cases import ladder
from chhatri.clock import ist

OPENED = ist(2025, 8, 19, 17, 12)


@pytest.mark.parametrize(
    ("topic", "respondent"),
    [
        ("PAYOUT_AMOUNT", "INSURER"),
        ("CLAIM_DECLINED", "INSURER"),
        ("CLAIM_SLOW", "INSURER"),
        ("EDI_HOLIDAY", "LENDER"),
        ("PAYMENT_NOT_RECEIVED", "PAYTM"),
        ("PREMIUM_CHARGE", "PAYTM"),
        ("DATA_OR_CONSENT", "PAYTM"),
        ("APP_ISSUE", "PAYTM"),
        ("OTHER", "PAYTM"),
    ],
)
def test_the_router_is_a_fixed_lookup(topic: str, respondent: str) -> None:
    assert ladder.respondent_for(topic) == respondent


def test_every_topic_has_a_respondent_and_only_listed_topics_route() -> None:
    assert set(ladder.TOPICS) == set(ladder.RESPONDENT_BY_TOPIC)
    with pytest.raises(KeyError):
        ladder.respondent_for("WEATHER")


def test_dispute_is_about_a_decision_and_the_rest_are_complaints() -> None:
    assert [t for t in ladder.TOPICS if ladder.kind_for(t) == "DISPUTE"] == [
        "PAYOUT_AMOUNT",
        "CLAIM_DECLINED",
    ]


def test_the_insurer_ladder_has_four_levels_and_the_others_one() -> None:
    assert [s.id for s in ladder.ladder_for("INSURER")] == [
        "PAYTM_DISPUTE",
        "INSURER_GRO",
        "BIMA_BHAROSA",
        "OMBUDSMAN",
    ]
    assert [s.id for s in ladder.ladder_for("LENDER")] == ["LENDER_GRIEVANCE"]
    assert [s.id for s in ladder.ladder_for("PAYTM")] == ["PAYTM_SUPPORT"]
    assert [s.delivery for s in ladder.ladder_for("INSURER")] == [
        "IN_CHHATRI",
        "SIMULATED",
        "SELF_REPORTED",
        "SELF_REPORTED",
    ]


def test_own_sla_clock_runs_then_is_overdue() -> None:
    due = OPENED + timedelta(hours=24)
    running = ladder.clock_view(
        "PAYTM_DISPUTE", entered_at=OPENED, now=OPENED + timedelta(hours=3), due_by=due, sla_hours=24
    )
    assert running == {"kind": "OWN_SLA", "hours": 24, "due_by": due.isoformat(), "state": "RUNNING"}
    late = ladder.clock_view(
        "PAYTM_DISPUTE", entered_at=OPENED, now=due + timedelta(minutes=1), due_by=due, sla_hours=24
    )
    assert late["state"] == "OVERDUE"


def test_a_step_that_has_not_started_has_no_running_clock() -> None:
    own = ladder.clock_view("PAYTM_DISPUTE", entered_at=None, now=OPENED, due_by=None, sla_hours=24)
    assert own["state"] == "NOT_STARTED"
    portal = ladder.clock_view("BIMA_BHAROSA", entered_at=None, now=OPENED, due_by=None, sla_hours=24)
    assert portal == {
        "kind": "PORTAL_STATED",
        "days": 14,
        "started_at": None,
        "statement_en": "The portal says complaints are attended within 14 days",
        "state": "NOT_STARTED",
        "day": None,
    }


def test_the_portal_clock_counts_days_from_the_filing_date() -> None:
    filed = ist(2025, 8, 20)
    day5 = ladder.clock_view(
        "BIMA_BHAROSA", entered_at=filed, now=ist(2025, 8, 24, 9), due_by=None, sla_hours=24
    )
    assert (day5["state"], day5["day"], day5["started_at"]) == ("RUNNING", 5, filed.isoformat())
    past = ladder.clock_view(
        "BIMA_BHAROSA", entered_at=filed, now=ist(2025, 9, 4, 9), due_by=None, sla_hours=24
    )
    assert (past["state"], past["day"]) == ("PAST_STATED_DAYS", 16)


@pytest.mark.parametrize("step", ["INSURER_GRO", "OMBUDSMAN", "LENDER_GRIEVANCE", "PAYTM_SUPPORT"])
def test_steps_with_no_source_say_to_confirm_and_show_no_time(step: str) -> None:
    clock = ladder.clock_view(step, entered_at=OPENED, now=OPENED, due_by=None, sla_hours=24)
    assert clock["kind"] == "TO_CONFIRM" and clock["note_en"]
    assert not {"hours", "days", "due_by"} & set(clock)


def test_the_next_action_follows_the_ladder() -> None:
    assert ladder.next_action("INSURER", "PAYTM_DISPUTE") == {
        "id": "ESCALATE_TO_INSURER_GRO",
        "label_en": "Send this to the insurer's grievance officer",
    }
    assert ladder.next_action("INSURER", "INSURER_GRO")["id"] == "ESCALATE_TO_BIMA_BHAROSA"
    assert ladder.next_action("INSURER", "BIMA_BHAROSA")["id"] == "ESCALATE_TO_OMBUDSMAN"
    for respondent, step in (
        ("INSURER", "OMBUDSMAN"),
        ("LENDER", "LENDER_GRIEVANCE"),
        ("PAYTM", "PAYTM_SUPPORT"),
    ):
        assert ladder.next_action(respondent, step) == {"id": "MARK_SOLVED", "label_en": "Mark as solved"}


def test_filed_on_becomes_the_start_of_that_day_in_ist() -> None:
    assert ladder.filed_on_start(date(2025, 8, 20)) == ist(2025, 8, 20)
