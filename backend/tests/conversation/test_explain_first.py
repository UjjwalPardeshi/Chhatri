"""Explain-first routing (fs-05 section 2.2, task N2.7; AC-ASK-03).

A question about a rule goes to the grounded path even when a keyword rule matches it, so a coverage question is not
answered with the illness reply and a question about buying never makes a payment link. `classify()` is unchanged:
every labelled utterance keeps its intent, and none of them is turned into an explain-first question.
"""

from __future__ import annotations

import pytest

from chhatri.conversation.explain_first import explain_first
from chhatri.conversation.intents import Intent, classify
from tests.conversation import test_intents as labelled

# fs-05 section 2.2: the six questions the rules misroute today
SEEDED = [
    "क्या अस्पताल का खर्च भी मिलेगा?",
    "Will hospital bills be covered?",
    "What is the daily limit for hospital cash?",
    "Is cover active if I move to Bangalore?",
    "Why was my claim not paid?",
    "Can I buy cover during an alert?",
]
LABELLED = [text for text, _ in labelled.DECK] + [
    text
    for group in (
        labelled.WHY,
        labelled.DISPUTE,
        labelled.ILLNESS,
        labelled.BUY,
        labelled.COVER_STATUS,
        labelled.GREETING,
        labelled.AFFIRM,
        labelled.DENY,
        labelled.NEGATIVES,
    )
    for text in group
]


@pytest.mark.parametrize("text", SEEDED)
def test_the_six_seeded_questions_reach_the_grounded_path(text: str) -> None:
    intent = classify(text)
    assert intent is not Intent.UNKNOWN  # a keyword rule matches them
    assert explain_first(text, intent)


def test_all_128_labelled_utterances_keep_their_intents() -> None:
    assert len(LABELLED) == 128
    flipped = [text for text in LABELLED if explain_first(text, classify(text))]
    assert flipped == []


@pytest.mark.parametrize(
    "text",
    [
        "मुझे इतने ही पैसे क्यों मिले?",  # the deck's WHY_AMOUNT: explained by the rules, no model
        "मेरा नुकसान ज़्यादा हुआ।",  # a dispute opens a case by rule
        "Red alert tomorrow. Cover me today.",  # a request, not a question
        "मेरा कवर चालू है क्या?",  # the merchant's own state
    ],
)
def test_the_demo_lines_stay_with_the_rules(text: str) -> None:
    assert not explain_first(text, classify(text))


def test_unknown_and_small_talk_intents_are_never_explain_first() -> None:
    assert not explain_first("What is the daily limit?", Intent.UNKNOWN)  # already the grounded path
    assert not explain_first("is the limit ok?", Intent.AFFIRM)
    assert not explain_first("", Intent.WHY_AMOUNT)


def test_a_dispute_question_about_the_process_is_grounded_and_opens_no_case() -> None:
    text = "how long does the officer take to answer a dispute"
    assert classify(text) is Intent.DISPUTE_AMOUNT and explain_first(text, Intent.DISPUTE_AMOUNT)
