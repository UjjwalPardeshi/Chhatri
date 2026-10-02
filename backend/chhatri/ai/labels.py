"""The H26 label every AI-backed result carries (data-model 5.0, fs-05 section 10, fs-02 section 7.3.8).

`mode` says how the chain went: LIVE (it worked as designed), FALLBACK (a configured link failed, was blocked or was
forced off, and a later link or a template answered) or SIMULATED (no live path was configured or allowed). `provider`
and `model` say who answered, `fallback_reason` says why it was not the first choice, and `attempts` lists one row per
link tried, for the console. The model id is echoed from the configuration and is never hard-coded.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final


class AiMode(StrEnum):
    LIVE = "LIVE"
    FALLBACK = "FALLBACK"
    SIMULATED = "SIMULATED"


class AiProvider(StrEnum):
    RULES = "rules"
    GEMINI = "gemini"
    SARVAM = "sarvam"
    TEMPLATE = "template"
    SIMULATED = "simulated"
    MOCK = "mock"
    BROWSER = "browser"
    NONE = "none"


class FallbackReason(StrEnum):
    # no live path was configured or allowed: the label is SIMULATED
    NO_KEY = "NO_KEY"
    MODEL_NOT_SET = "MODEL_NOT_SET"
    MOCK_BACKEND = "MOCK_BACKEND"
    FREE_TIER_BLOCKED = "FREE_TIER_BLOCKED"
    # a configured link failed, was blocked or was switched off: the label is FALLBACK
    FORCED = "FORCED"
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INVALID_REPLY = "INVALID_REPLY"
    GUARD_BLOCKED = "GUARD_BLOCKED"
    INJECTION_SUSPECTED = "INJECTION_SUSPECTED"


SIMULATED_REASONS: Final = frozenset(
    {
        FallbackReason.NO_KEY,
        FallbackReason.MODEL_NOT_SET,
        FallbackReason.MOCK_BACKEND,
        FallbackReason.FREE_TIER_BLOCKED,
    }
)
ATTEMPT_OK: Final = "OK"  # the outcome of a link that answered; every other outcome is a FallbackReason value


def mode_for(reason: FallbackReason) -> AiMode:
    """The mode of a result that ended on `reason`. FORCED counts as FALLBACK, so the panel and the label agree (5.6)."""
    return AiMode.SIMULATED if reason in SIMULATED_REASONS else AiMode.FALLBACK


@dataclass(frozen=True, slots=True)
class Attempt:
    """One link tried: who, how it ended (`OK` or a reason) and how long it took."""

    provider: AiProvider
    outcome: str
    ms: int

    def __post_init__(self) -> None:
        if self.ms < 0:
            raise ValueError("ms must not be negative")

    def to_wire(self) -> dict[str, Any]:
        return {"provider": self.provider.value, "outcome": self.outcome, "ms": self.ms}


@dataclass(frozen=True, slots=True)
class AiLabel:
    mode: AiMode
    provider: AiProvider
    model: str | None = None
    fallback_reason: FallbackReason | None = None
    attempts: tuple[Attempt, ...] = ()

    def __post_init__(self) -> None:
        if self.mode is AiMode.LIVE and self.fallback_reason is not None:
            raise ValueError("a LIVE label carries no fallback reason")
        if self.mode is not AiMode.LIVE and self.fallback_reason is None:
            raise ValueError(f"a {self.mode.value} label needs a fallback reason")

    def to_wire(self) -> dict[str, Any]:
        """The JSON shape of an API response and of an audit row: plain strings, one object per attempt."""
        return {
            "mode": self.mode.value,
            "provider": self.provider.value,
            "model": self.model,
            "fallback_reason": None if self.fallback_reason is None else self.fallback_reason.value,
            "attempts": [attempt.to_wire() for attempt in self.attempts],
        }
