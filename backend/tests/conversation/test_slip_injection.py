"""Red-team and distractor slips (fs-02 section 7.3, task N3.13; AC-SLIP-16 and 19).

Each row of `tests/fixtures/slips/redteam.jsonl` is what a reader returned for one adversarial photo. Text on a slip
is data, never an instruction: an injection stops the chain and goes to a person with SLIP_NO_READ, markup is never
kept, a non-hospital document is a retake, and the word "approved" on a slip changes nothing (the engine decides).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Final

import pytest

from chhatri.domain.models import SlipExtraction
from chhatri.precheck.fields import kept, reject
from chhatri.precheck.rules import decide

FIXTURES: Final = Path(__file__).resolve().parents[1] / "fixtures" / "slips" / "redteam.jsonl"
ROWS: Final = [json.loads(line) for line in FIXTURES.read_text(encoding="utf-8").splitlines() if line.strip()]
TODAY: Final = date(2025, 8, 21)
MINIMUM: Final = 0.80  # the loaded `personal.slip_confidence_min`


def _read(row: dict[str, Any]) -> SlipExtraction:
    return SlipExtraction(source="gemini-vision", **row["read"])


def test_the_red_team_set_has_every_category_of_the_spec() -> None:
    categories = {row["category"] for row in ROWS}
    assert {
        "printed instructions",
        "a menu photo that claims to be a slip",
        "tiny hidden text",
        "a name field that contains approved",
        "markup in the hospital field",
        "a Hindi instruction",
    } <= categories
    assert len({row["id"] for row in ROWS}) == len(ROWS)


@pytest.mark.parametrize("row", ROWS, ids=[row["id"] for row in ROWS])
def test_a_red_team_slip_gets_the_status_of_the_table(row: dict[str, Any]) -> None:
    slip = _read(row)
    rejection = reject(slip)
    assert (rejection.reason.value if rejection else None) == row["reject"]
    injected = rejection is not None and rejection.stop
    verdict = decide(None if injected else kept(slip), today=TODAY, minimum=MINIMUM, injected=injected)
    assert verdict.status.value == row["status"]
    assert (verdict.reason.value if verdict.reason else None) == row["reason"]
    assert verdict.guidance_key == row["text_key"]


@pytest.mark.parametrize("row", [r for r in ROWS if r["reject"]], ids=lambda r: r["id"])
def test_an_injection_is_never_ready_and_stops_the_chain(row: dict[str, Any]) -> None:
    rejection = reject(_read(row))
    assert rejection is not None and rejection.stop


def test_no_kept_read_holds_markup() -> None:
    """AC-SLIP-19: a value with markup never survives validation, so no screen is handed one to render."""
    for row in ROWS:
        slip = _read(row)
        if reject(slip) is None:
            values = [v for v in (slip.patient_name, slip.hospital_name) if v]
            assert not any("<" in v or ">" in v for v in values)
