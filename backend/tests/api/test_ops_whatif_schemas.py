"""The strict mirrors of the H8 and H24 responses: the examples of the contract pass, broken ones do not."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from chhatri.api.schemas import OpsSummary, WhatIfArea

STAMP = "2025-08-19T17:06:00+05:30"


def ops_payload() -> dict[str, Any]:
    """The example of data-model-and-api section 5.7 (the monsoon at 17:06 after Anil's dispute, X4 on)."""
    return {
        "as_of": STAMP,
        "day": "2025-08-19",
        "open_cases": 1,
        "cases_by_kind": {"PERSONAL_CLAIM_REVIEW": 0, "DISPUTE": 1, "AREA_REVIEW": 0},
        "overdue_cases": 0,
        "next_due_case": {
            "id": "C-2291",
            "kind": "DISPUTE",
            "merchant_id": "S-0142",
            "opened_at": STAMP,
            "due_by": "2025-08-20T17:06:00+05:30",
            "due_in_minutes": 1440,
        },
        "claims_today": {"automatic": 312, "human": 0, "waiting": 0, "automatic_share_pct": 100},
        "payouts_today": {
            "credited_count": 312,
            "credited_paise": 42_542_000,
            "credited_label": "₹4,25,420",
            "pending_count": 0,
            "failed_count": 0,
            "by_zone": {
                "Z3": {"count": 141, "paise": 20_671_900, "label": "₹2,06,719"},
                "Z7": {"count": 46, "paise": 5_890_000, "label": "₹58,900"},
                "Z12": {"count": 125, "paise": 15_980_100, "label": "₹1,59,801"},
            },
        },
        "holiday_requests_today": {"GRANTED": 123, "REFUSED": 0, "NO_RESPONSE": 0, "REQUESTED": 0},
    }


def whatif_payload() -> dict[str, Any]:
    """Z9 at 17:00 with a rain alert and every hour at 49 (section 5.9)."""
    clause = {
        "kind": "CLAUSE",
        "label": "Area income loss",
        "ref": "clause:C2",
        "as_of": None,
        "origin": "CONFIG",
        "clause": "C2",
    }
    codes = (
        ("ALERT_COVERS_WINDOW", False),
        ("HOURS_BELOW_FLOOR", False),
        ("WINDOW_BELOW_BOUND", True),
        ("SHOPS_QUORUM", True),
        ("FIRST_TRIGGER_TODAY", True),
    )
    side = {
        "alert": "NONE",
        "alert_id": None,
        "hourly_index_pct": [59, 58, 67],
        "window_index_pct": 61,
        "shops_in_index": 62,
        "already_triggered_today": False,
        "fires": False,
        "status": "slow_day",
    }
    return {
        "read_only": True,
        "zone_id": "Z9",
        "zone_name": "Chembur",
        "at": "2025-08-19T17:00:00+05:30",
        "window": {"start": "2025-08-19T14:00:00+05:30", "end": "2025-08-19T17:00:00+05:30"},
        "rules_version": "pilot-0.1",
        "fixed": {
            "index_floor_pct": 50,
            "consecutive_hours": 3,
            "min_shops_in_index": 20,
            "lower_bound_pct": 90,
        },
        "baseline": side,
        "scenario": {
            **side,
            "alert": "RAIN",
            "hourly_index_pct": [49, 49, 49],
            "window_index_pct": 49,
            "fires": True,
            "status": "triggered",
            "drop_pct": 51,
        },
        "changed": ["alert", "hourly_index_pct"],
        "conditions": [
            {
                "code": code,
                "label_en": code.lower(),
                "required": "a rule",
                "baseline": {"met": met, "observed": "seen"},
                "scenario": {"met": True, "observed": "seen"},
                "sources": [clause],
            }
            for code, met in codes
        ],
        "counterfactual": None,
        "example": None,
        "computed_by": "policy engine, deterministic",
        "stored": False,
    }


def broken(payload: dict[str, Any], *path: str | int, value: Any) -> dict[str, Any]:
    changed = copy.deepcopy(payload)
    node: Any = changed
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return changed


def test_the_contract_examples_validate() -> None:
    assert OpsSummary.model_validate(ops_payload()).payouts_today.by_zone["Z7"].label == "₹58,900"
    assert WhatIfArea.model_validate(whatif_payload()).scenario.drop_pct == 51


def test_ops_summary_allows_nothing_open_and_x4_off() -> None:
    quiet = {
        **ops_payload(),
        "open_cases": 0,
        "cases_by_kind": {"PERSONAL_CLAIM_REVIEW": 0, "DISPUTE": 0, "AREA_REVIEW": 0},
        "next_due_case": None,
        "holiday_requests_today": None,
    }
    parsed = OpsSummary.model_validate(quiet)
    assert parsed.next_due_case is None and parsed.holiday_requests_today is None
    none = broken(
        quiet, "claims_today", value={"automatic": 0, "human": 0, "waiting": 0, "automatic_share_pct": None}
    )
    assert OpsSummary.model_validate(none).claims_today.automatic_share_pct is None


@pytest.mark.parametrize(
    "payload",
    [
        {**ops_payload(), "extra": 1},
        broken(ops_payload(), "open_cases", value=2),  # the kinds add up to 1
        broken(ops_payload(), "next_due_case", value=None),  # one case is open
        broken(ops_payload(), "overdue_cases", value=2),
        broken(ops_payload(), "claims_today", "automatic_share_pct", value=99),  # 312 of 312 is 100
        broken(ops_payload(), "claims_today", "automatic_share_pct", value=None),
        broken(ops_payload(), "payouts_today", "credited_label", value="₹4,25,421"),
        broken(ops_payload(), "payouts_today", "credited_count", value=311),  # the zones add up to 312
        broken(ops_payload(), "payouts_today", "by_zone", "Z7", "label", value="₹58,901"),
        broken(ops_payload(), "payouts_today", "by_zone", "Z7", "count", value=0),
        broken(ops_payload(), "as_of", value="2025-08-19T11:36:00+00:00"),  # not IST
        broken(ops_payload(), "day", value="19 Aug 2025"),
        broken(ops_payload(), "cases_by_kind", "DISPUTE", value=-1),
        broken(ops_payload(), "next_due_case", "kind", value="REFUND"),
        broken(ops_payload(), "holiday_requests_today", "GRANTED", value="123"),  # strict: no coercion
    ],
)
def test_a_broken_ops_summary_is_refused(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        OpsSummary.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {**whatif_payload(), "mode": "LIVE"},  # nothing here is AI-backed
        broken(whatif_payload(), "read_only", value=False),
        broken(whatif_payload(), "stored", value=True),
        broken(whatif_payload(), "computed_by", value="a model"),
        broken(whatif_payload(), "conditions", value=whatif_payload()["conditions"][:4]),
        broken(whatif_payload(), "conditions", value=list(reversed(whatif_payload()["conditions"]))),
        broken(whatif_payload(), "baseline", "fires", value=True),  # two conditions fail
        broken(whatif_payload(), "scenario", "fires", value=False),  # every condition is met
        broken(whatif_payload(), "scenario", "drop_pct", value=None),  # omitted, never null
        broken(whatif_payload(), "scenario", "status", value="red"),
        broken(whatif_payload(), "scenario", "alert", value="SNOW"),
        broken(whatif_payload(), "changed", value=["colour"]),
        broken(whatif_payload(), "conditions", 0, "sources", value=[]),  # every condition has its sources
        broken(
            whatif_payload(), "conditions", 0, "sources", 0, "extra", value=1
        ),  # the Source shape is closed
        broken(whatif_payload(), "conditions", 0, "sources", 0, "clause", value="C13"),
        broken(whatif_payload(), "conditions", 0, "sources", 0, "origin", value="REAL"),
        broken(whatif_payload(), "example", value={"merchant_id": "S-0142"}),
        broken(whatif_payload(), "at", value="2025-08-19T11:30:00+00:00"),
    ],
)
def test_a_broken_whatif_response_is_refused(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        WhatIfArea.model_validate(payload)


def test_an_example_shop_checks_its_label() -> None:
    example = {
        "merchant_id": "S-0142",
        "shop_name": "Anil's Tea Stall",
        "expected_day_paise": 438_000,
        "drop_pct": 55,
        "lost_paise": 240_900,
        "share_paise": 120_500,
        "cap_paise": 250_000,
        "capped": False,
        "amount_paise": 120_500,
        "amount_label": "₹1,205",
        "formula_en": "½ × ₹4,380 × 55% = ₹1,205",
        "scope": "amount arithmetic only",
    }
    assert WhatIfArea.model_validate(broken(whatif_payload(), "example", value=example)).example is not None
    for bad in (
        broken(example, "amount_label", value="₹1,206"),
        broken(example, "scope", value="a claim decision"),
    ):
        with pytest.raises(ValidationError):
            WhatIfArea.model_validate(broken(whatif_payload(), "example", value=bad))
