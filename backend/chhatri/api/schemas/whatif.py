"""§19.2 type of the H24 what-if call: `POST /api/whatif/area` (fs-08 section 11, data-model-and-api 5.9).

Beyond the shape, the types check what the panel relies on: five conditions in the rule's order, and a side
`fires` exactly when all of its five conditions are met.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from chhatri.api.schemas.base import IstTimestamp, Schema, absent
from chhatri.api.schemas.live import PERCENT_MAX, ZoneStatusName

__all__ = [
    "WhatIfArea",
    "WhatIfCondition",
    "WhatIfConditionSide",
    "WhatIfExample",
    "WhatIfFixed",
    "WhatIfSide",
    "WhatIfSource",
    "WhatIfWindow",
]

ConditionCode = Literal[
    "ALERT_COVERS_WINDOW", "HOURS_BELOW_FLOOR", "WINDOW_BELOW_BOUND", "SHOPS_QUORUM", "FIRST_TRIGGER_TODAY"
]
CONDITION_CODES: tuple[str, ...] = (
    "ALERT_COVERS_WINDOW",
    "HOURS_BELOW_FLOOR",
    "WINDOW_BELOW_BOUND",
    "SHOPS_QUORUM",
    "FIRST_TRIGGER_TODAY",
)
SourceKind = Literal[
    "RULES",
    "CLAUSE",
    "ALERT",
    "SALES_INDEX",
    "FORECAST",
    "ZONE_BOUND",
    "COVER",
    "PREMIUM",
    "KYC",
    "SLIP",
    "SALES_DAY",
    "PAYOUT_HISTORY",
    "LENDER",
]
OverrideKey = Literal["alert", "hourly_index_pct", "shops_in_index", "already_triggered_today"]
CLAUSE_PATTERN = r"^C(?:1[0-2]|[1-9])(?:\.[1-4])?$"


class WhatIfSource(Schema):
    """The closed Source object of fs-09 section 8.2: exactly these six fields."""

    kind: SourceKind
    label: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    as_of: IstTimestamp | None
    origin: Literal["LIVE", "SIMULATED", "CONFIG"]
    clause: str | None = Field(pattern=CLAUSE_PATTERN)


class WhatIfConditionSide(Schema):
    met: bool
    observed: str = Field(min_length=1)


class WhatIfCondition(Schema):
    code: ConditionCode
    label_en: str = Field(min_length=1)
    required: str = Field(min_length=1)
    baseline: WhatIfConditionSide
    scenario: WhatIfConditionSide
    sources: list[WhatIfSource] = Field(min_length=1)


class WhatIfWindow(Schema):
    start: IstTimestamp
    end: IstTimestamp


class WhatIfFixed(Schema):
    index_floor_pct: int = Field(ge=1, le=100)
    consecutive_hours: int = Field(ge=1, le=12)
    min_shops_in_index: int = Field(ge=1)
    lower_bound_pct: int = Field(ge=0, le=PERCENT_MAX)


class WhatIfSide(Schema):
    alert: Literal["NONE", "RAIN", "CIVIC", "HEATWAVE"]
    alert_id: str | None
    hourly_index_pct: list[int | None]
    window_index_pct: int | None = Field(ge=0, le=PERCENT_MAX)
    shops_in_index: int = Field(ge=0)
    already_triggered_today: bool
    fires: bool
    status: ZoneStatusName
    drop_pct: absent(int) = None  # only a side that fires has a drop


class WhatIfExample(Schema):
    merchant_id: str = Field(pattern=r"^S-\d{4}$")
    shop_name: str
    expected_day_paise: int = Field(ge=0)
    drop_pct: int = Field(ge=0, le=100)
    lost_paise: int = Field(ge=0)
    share_paise: int = Field(ge=0)
    cap_paise: int = Field(ge=0)
    capped: bool
    amount_paise: int = Field(ge=0)
    amount_label: str
    formula_en: str
    scope: Literal["amount arithmetic only"]


class WhatIfArea(Schema):
    read_only: Literal[True]
    zone_id: str = Field(pattern=r"^Z\d{1,2}$")
    zone_name: str
    at: IstTimestamp
    window: WhatIfWindow
    rules_version: str
    fixed: WhatIfFixed
    baseline: WhatIfSide
    scenario: WhatIfSide
    changed: list[OverrideKey]
    conditions: list[WhatIfCondition] = Field(min_length=5, max_length=5)
    counterfactual: dict[str, Any] | None
    example: WhatIfExample | None
    computed_by: Literal["policy engine, deterministic"]
    stored: Literal[False]

    @model_validator(mode="after")
    def _conditions_decide_the_verdict(self) -> WhatIfArea:
        if tuple(c.code for c in self.conditions) != CONDITION_CODES:
            raise ValueError("conditions must be the five trigger conditions in the rule's order")
        if self.baseline.fires != all(c.baseline.met for c in self.conditions):
            raise ValueError("baseline.fires must be true exactly when every condition is met")
        if self.scenario.fires != all(c.scenario.met for c in self.conditions):
            raise ValueError("scenario.fires must be true exactly when every condition is met")
        return self
