"""The shared what-if vectors (fs-08 section 11.4): the backend rule and the mock's own trigger function agree.

`frontend/src/mock/whatif.vectors.json` lists inputs and the expected verdict of the trigger rule: each of the
five conditions, whether the zone fires and the zone status. The mock weighs the hours of a window equally and
the backend weighs them by the zone's expected sales, so the two compare verdicts and not window decimals: a
one-point difference in the window index must change nothing. This file proves that for every vector, and that
`trigger_verdict` gives what the file says. The mock's test reads the same file.
"""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final

import pytest

from chhatri.config import BACKEND_DIR
from chhatri.detect.triggers import CONDITION_ORDER, VerdictInputs, trigger_verdict
from chhatri.policy.rules import default_rules

VECTORS_FILE: Final = BACKEND_DIR.parent / "frontend" / "src" / "mock" / "whatif.vectors.json"
COUNTING: Final = ("RAIN", "CIVIC")
STATUSES: Final = {"triggered", "watch", "slow_day", "normal", "no_data"}


def load() -> dict[str, Any]:
    assert VECTORS_FILE.is_file(), f"the shared vectors file is missing: {VECTORS_FILE}"
    return json.loads(VECTORS_FILE.read_text(encoding="utf-8"))


DOC: Final = load()
VECTORS: Final = DOC["vectors"]


def verdict_inputs(vector: dict[str, Any]) -> VerdictInputs:
    raw = vector["inputs"]
    counts = raw["alert"] in COUNTING
    return VerdictInputs(
        hourly_pct=tuple(raw["hourly_index_pct"]),
        window_pct=raw["window_index_pct"],
        lower_bound_pct=raw["lower_bound_pct"],
        shops_in_index=raw["shops_in_index"],
        alert_covers_window=counts,
        alert_covers_last_hour=counts,
        already_triggered_today=raw["already_triggered_today"],
    )


def test_the_file_states_the_rule_it_was_written_for() -> None:
    area = default_rules().area
    assert DOC["rules"] == {
        "index_floor_pct": area.index_floor_pct,
        "consecutive_hours": area.consecutive_hours,
        "min_shops_in_index": area.min_shops_in_index,
    }
    assert len(VECTORS) >= 20 and len({v["name"] for v in VECTORS}) == len(VECTORS)
    for vector in VECTORS:
        assert set(vector) == {"name", "inputs", "expected"}, vector["name"]
        assert set(vector["inputs"]) == {
            "alert",
            "hourly_index_pct",
            "window_index_pct",
            "lower_bound_pct",
            "shops_in_index",
            "already_triggered_today",
        }
        assert len(vector["inputs"]["hourly_index_pct"]) == area.consecutive_hours, vector["name"]


@pytest.mark.parametrize("vector", VECTORS, ids=[v["name"] for v in VECTORS])
def test_trigger_verdict_gives_the_verdict_the_file_states(vector: dict[str, Any]) -> None:
    verdict = trigger_verdict(verdict_inputs(vector), default_rules())
    expected = vector["expected"]
    assert {c.code.value: c.met for c in verdict.conditions} == expected["conditions"]
    assert list(expected["conditions"]) == [code.value for code in CONDITION_ORDER]
    assert verdict.fires is expected["fires"] is all(expected["conditions"].values())
    assert (verdict.status, verdict.hours_below) == (expected["status"], expected["hours_below"])


@pytest.mark.parametrize("vector", VECTORS, ids=[v["name"] for v in VECTORS])
def test_a_one_point_window_difference_changes_no_verdict(vector: dict[str, Any]) -> None:
    """The mock's equal-weight window may differ from the backend's by a point: conditions and fires stay."""
    base = verdict_inputs(vector)
    rules = default_rules()
    reference = trigger_verdict(base, rules)
    if base.window_pct is None:
        return
    for shift in (-1, 1):
        moved = trigger_verdict(replace(base, window_pct=base.window_pct + shift), rules)
        assert [c.met for c in moved.conditions] == [c.met for c in reference.conditions], (
            vector["name"],
            shift,
        )
        assert (moved.fires, moved.status) == (reference.fires, reference.status), (vector["name"], shift)


@pytest.mark.parametrize("vector", VECTORS, ids=[v["name"] for v in VECTORS])
def test_the_window_is_within_a_point_of_the_equal_weight_mean(vector: dict[str, Any]) -> None:
    hourly, window = vector["inputs"]["hourly_index_pct"], vector["inputs"]["window_index_pct"]
    if window is None or any(h is None for h in hourly):
        return
    mean = int((Decimal(sum(hourly)) / len(hourly)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    assert abs(window - mean) <= 1, vector["name"]


def test_every_condition_is_met_and_unmet_somewhere_and_every_status_appears() -> None:
    for code in CONDITION_ORDER:
        seen = {v["expected"]["conditions"][code.value] for v in VECTORS}
        assert seen == {True, False}, code.value
    assert {v["expected"]["status"] for v in VECTORS} == STATUSES
    assert {v["inputs"]["alert"] for v in VECTORS} == {"NONE", "RAIN", "CIVIC", "HEATWAVE"}
    assert any(None in v["inputs"]["hourly_index_pct"] for v in VECTORS)  # an hour with nothing expected
    assert any(v["expected"]["fires"] for v in VECTORS) and any(not v["expected"]["fires"] for v in VECTORS)
