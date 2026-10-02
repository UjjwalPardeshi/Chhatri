"""H26 label vocabulary and mode rules (data-model 5.0, fs-05 section 10, fs-02 section 7.3.8)."""

from __future__ import annotations

import dataclasses

import pytest

from chhatri.ai.labels import (
    ATTEMPT_OK,
    SIMULATED_REASONS,
    AiLabel,
    AiMode,
    AiProvider,
    Attempt,
    FallbackReason,
    mode_for,
)


def test_the_vocabularies_are_the_documented_ones() -> None:
    assert {mode.value for mode in AiMode} == {"LIVE", "FALLBACK", "SIMULATED"}
    assert {provider.value for provider in AiProvider} == {
        "rules",
        "gemini",
        "sarvam",
        "template",
        "simulated",
        "mock",
        "browser",
        "none",
    }
    assert {reason.value for reason in FallbackReason} == {
        "NO_KEY",
        "MODEL_NOT_SET",
        "FORCED",
        "MOCK_BACKEND",
        "FREE_TIER_BLOCKED",
        "TIMEOUT",
        "RATE_LIMITED",
        "PROVIDER_ERROR",
        "INVALID_REPLY",
        "GUARD_BLOCKED",
        "INJECTION_SUSPECTED",
    }


def test_these_reasons_give_simulated_and_every_other_gives_fallback() -> None:
    assert {
        FallbackReason.NO_KEY,
        FallbackReason.MODEL_NOT_SET,
        FallbackReason.MOCK_BACKEND,
        FallbackReason.FREE_TIER_BLOCKED,
    } == SIMULATED_REASONS
    for reason in FallbackReason:
        expected = AiMode.SIMULATED if reason in SIMULATED_REASONS else AiMode.FALLBACK
        assert mode_for(reason) is expected


def test_a_forced_link_counts_as_fallback_not_simulated() -> None:
    """data-model 5.6: the panel and the reply label must agree, so FORCED is FALLBACK (the specs said SIMULATED)."""
    assert mode_for(FallbackReason.FORCED) is AiMode.FALLBACK


def test_wire_shape_has_plain_strings_and_one_row_per_attempt() -> None:
    label = AiLabel(
        mode=AiMode.FALLBACK,
        provider=AiProvider.SARVAM,
        model="sarvam-105b",
        fallback_reason=FallbackReason.TIMEOUT,
        attempts=(
            Attempt(AiProvider.GEMINI, FallbackReason.TIMEOUT.value, 3004),
            Attempt(AiProvider.SARVAM, ATTEMPT_OK, 812),
        ),
    )
    wire = label.to_wire()
    assert wire == {
        "mode": "FALLBACK",
        "provider": "sarvam",
        "model": "sarvam-105b",
        "fallback_reason": "TIMEOUT",
        "attempts": [
            {"provider": "gemini", "outcome": "TIMEOUT", "ms": 3004},
            {"provider": "sarvam", "outcome": "OK", "ms": 812},
        ],
    }
    assert all(type(value) in (str, list, type(None)) for value in wire.values())


def test_an_empty_chain_label_has_no_attempts_and_no_model() -> None:
    label = AiLabel(AiMode.SIMULATED, AiProvider.TEMPLATE, None, FallbackReason.NO_KEY)
    assert label.to_wire() == {
        "mode": "SIMULATED",
        "provider": "template",
        "model": None,
        "fallback_reason": "NO_KEY",
        "attempts": [],
    }


def test_a_live_label_carries_no_reason_and_the_others_must() -> None:
    AiLabel(AiMode.LIVE, AiProvider.RULES)
    with pytest.raises(ValueError, match="LIVE"):
        AiLabel(AiMode.LIVE, AiProvider.GEMINI, "m", FallbackReason.TIMEOUT)
    for mode in (AiMode.FALLBACK, AiMode.SIMULATED):
        with pytest.raises(ValueError, match="reason"):
            AiLabel(mode, AiProvider.TEMPLATE)


def test_an_attempt_is_not_negative_and_labels_are_frozen() -> None:
    with pytest.raises(ValueError, match="ms"):
        Attempt(AiProvider.GEMINI, ATTEMPT_OK, -1)
    label = AiLabel(AiMode.LIVE, AiProvider.GEMINI, "m")
    with pytest.raises(dataclasses.FrozenInstanceError):
        label.mode = AiMode.FALLBACK  # type: ignore[misc]
