"""Validated request bodies for the SPEC §19 routes (SPEC §21: validate every input with pydantic)."""

from __future__ import annotations

from typing import Annotated, Any, Final, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool

from chhatri.api.schemas import ScenarioName, WorkflowName, WorkflowStep
from chhatri.api.schemas.live import PERCENT_MAX

__all__ = [
    "LoadRequest",
    "MAX_STEP_MINUTES",
    "MAX_SPEED",
    "MIN_SPEED",
    "OfficerNoteRequest",
    "PhotoSampleRequest",
    "PlayRequest",
    "PremiumLinkRequest",
    "SeekRequest",
    "StepRequest",
    "TextMessageRequest",
    "VoiceDemoKey",
    "VoiceDemoRequest",
    "WhatIfOverrides",
    "WhatIfRequest",
    "WorkflowCallbackRequest",
]

MIN_SPEED: Final = 1.0  # SPEC §24.6: speed = sim minutes per real second (1..120)
MAX_SPEED: Final = 120.0
MAX_STEP_MINUTES: Final = 24 * 60
MAX_TEXT_CHARS: Final = 1000
MAX_NOTE_CHARS: Final = 500
MAX_ID_CHARS: Final = 128
MERCHANT_ID_PATTERN: Final = r"^S-\d{4}$"
ZONE_ID_PATTERN: Final = r"^Z\d{1,2}$"
MAX_WINDOW_HOURS: Final = 12  # `area.consecutive_hours` is at most 12 (policy rules)
MAX_SHOPS_IN_INDEX: Final = 100_000  # a guard against garbage, like PERCENT_MAX
HHMM_PATTERN: Final = r"^([01]\d|2[0-3]):[0-5]\d$"
SAMPLE_PATTERN: Final = r"^[a-z0-9_]{1,64}\.png$"
VoiceDemoKey = Literal["why", "dispute", "ill", "cover"]


class _Body(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class LoadRequest(_Body):
    """POST /api/replay/load ``{scenario}``."""

    scenario: ScenarioName


class PlayRequest(_Body):
    """POST /api/replay/play ``{speed?}``."""

    speed: float | None = Field(default=None, ge=MIN_SPEED, le=MAX_SPEED)


class StepRequest(_Body):
    """POST /api/replay/step ``{minutes}``."""

    minutes: int = Field(ge=1, le=MAX_STEP_MINUTES)


class SeekRequest(_Body):
    """POST /api/replay/seek ``{to: "HH:MM"}``."""

    to: str = Field(pattern=HHMM_PATTERN)


class TextMessageRequest(_Body):
    """POST /api/merchants/{id}/messages ``{text}`` (phone simulator)."""

    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)


class VoiceDemoRequest(_Body):
    """POST /api/merchants/{id}/voice-demo ``{key}``."""

    key: VoiceDemoKey


class PhotoSampleRequest(_Body):
    """POST /api/merchants/{id}/photo ``{sample}``; omitted = the scenario's sample slip."""

    sample: str | None = Field(default=None, pattern=SAMPLE_PATTERN)


class OfficerNoteRequest(_Body):
    """POST /api/cases/{id}/approve|decline ``{note}``."""

    note: str = Field(default="", max_length=MAX_NOTE_CHARS)


class PremiumLinkRequest(_Body):
    """POST /api/premium/link ``{merchant_id, consents?, notice_version?}``; the last two matter only with `n6_consents`."""

    merchant_id: str = Field(pattern=MERCHANT_ID_PATTERN)
    consents: (
        tuple[Literal["SALES_DATA_FOR_CLAIM", "SLIP_DATA_FOR_HOSPITAL_CLAIM", "SETTLEMENT_DEDUCTION"], ...]
        | None
    ) = Field(default=None, max_length=3)
    notice_version: str | None = Field(default=None, max_length=32)


class WorkflowCallbackRequest(_Body):
    """POST /internal/workflows/{step} body from n8n (SPEC §14.5), payload passed through unchanged."""

    run_id: str = Field(min_length=1, max_length=MAX_ID_CHARS)
    workflow: WorkflowName
    step: WorkflowStep
    payload: dict[str, Any]


class WhatIfOverrides(_Body):
    """The inputs a judge changes in the what-if drawer (fs-08 section 11.1); a missing key keeps the real value."""

    alert: Literal["NONE", "RAIN", "CIVIC", "HEATWAVE"] | None = None
    hourly_index_pct: list[Annotated[int, Field(strict=True, ge=0, le=PERCENT_MAX)]] | None = Field(
        default=None, min_length=1, max_length=MAX_WINDOW_HOURS
    )
    shops_in_index: Annotated[int, Field(strict=True, ge=0, le=MAX_SHOPS_IN_INDEX)] | None = None
    already_triggered_today: StrictBool | None = None


class WhatIfRequest(_Body):
    """POST /api/whatif/area ``{zone_id, at?, overrides?, example_merchant_id?}``; read-only (H24)."""

    zone_id: str = Field(pattern=ZONE_ID_PATTERN)
    at: AwareDatetime | None = None
    overrides: WhatIfOverrides = Field(default_factory=WhatIfOverrides)
    example_merchant_id: str | None = Field(default=None, pattern=MERCHANT_ID_PATTERN)
