"""The fixed Ask lines never promise money, fill their facts strictly, and the ledger is bounded and per scenario load."""

from __future__ import annotations

import pytest

from chhatri.ask.copy import ACTION_LABELS, LINES, render_ask, render_pair
from chhatri.ask.ledger import MAX_RECORDS, AskLedger, AskRecord, SttRecord, ledger_for
from chhatri.conversation.guard import PROMISE
from chhatri.conversation.intents import normalise
from chhatri.ids import IdFactory


def test_no_fixed_line_or_label_has_a_promise_stem() -> None:
    texts = [text for pair in (*LINES.values(), *ACTION_LABELS.values()) for text in pair]
    assert [t for t in texts if PROMISE.found_in(normalise(t))] == []


def test_lines_fill_their_facts_and_refuse_a_missing_or_unknown_one() -> None:
    assert render_ask("ASK_MENTION_CHIP", "en", value="₹1,500") == "₹1,500 — is that right?"
    assert render_pair("ASK_TOO_LONG") == ("सवाल थोड़ा छोटा रखिए।", "Please keep the question shorter.")
    with pytest.raises(KeyError):
        render_ask("ASK_MENTION_CHIP", "en")
    with pytest.raises(KeyError):
        render_ask("ASK_TOO_LONG", "en", extra="x")
    with pytest.raises(KeyError):
        render_ask("NOPE", "en")


def test_the_ledger_is_per_id_factory_and_bounded() -> None:
    ids_a, ids_b = IdFactory(), IdFactory()
    ledger_for(ids_a).add_ask(AskRecord("AQ-000001", "S-0142", "hi", "en"))
    assert ledger_for(ids_a).ask("AQ-000001") is not None and ledger_for(ids_b).ask("AQ-000001") is None
    assert ledger_for(ids_a) is ledger_for(ids_a)
    ledger = AskLedger()
    for number in range(MAX_RECORDS + 5):
        ledger.add_stt(SttRecord(f"ST-{number:06d}", "S-0142", "browser"))
    assert ledger.stt("ST-000000") is None and ledger.stt(f"ST-{MAX_RECORDS + 4:06d}") is not None
