"""Validated request bodies for the SPEC §19 routes (SPEC §21: validate every input with pydantic)."""

from __future__ import annotations

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from chhatri.api.schemas import ScenarioName, WorkflowName, WorkflowStep

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
    "WorkflowCallbackRequest",
]

MIN_SPEED: Final = 1.0  # SPEC §24.6: speed = sim minutes per real second (1..120)
MAX_SPEED: Final = 120.0
MAX_STEP_MINUTES: Final = 24 * 60
MAX_TEXT_CHARS: Final = 1000
MAX_NOTE_CHARS: Final = 500
MAX_ID_CHARS: Final = 128
MERCHANT_ID_PATTERN: Final = r"^S-\d{4}$"
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
    """POST /api/premium/link ``{merchant_id}``."""

    merchant_id: str = Field(pattern=MERCHANT_ID_PATTERN)


class WorkflowCallbackRequest(_Body):
    """POST /internal/workflows/{step} body from n8n (SPEC §14.5), payload passed through unchanged."""

    run_id: str = Field(min_length=1, max_length=MAX_ID_CHARS)
    workflow: WorkflowName
    step: WorkflowStep
    payload: dict[str, Any]
