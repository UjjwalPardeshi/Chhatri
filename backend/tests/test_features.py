"""Feature flags (Wave 0): every flag is off unless CHHATRI_FEATURES names it."""

from __future__ import annotations

import re

import pytest

import chhatri.features as features
from chhatri.config import Settings
from chhatri.features import FEATURE_NAMES, enabled_features, is_enabled, parse_features, unknown_features

WAVE0_FLAGS = (
    "n1_miniapp",
    "n2_ask_chhatri",
    "n3_slip_precheck",
    "n4_voice",
    "n5_grievances",
    "n6_consents",
    "n8_marathi",
    "x4_lender_request",
    "x6_provider_panel",
    "x8_distress_guard",
    "h8_ops_strip",
    "h24_whatif",
    "h25_evals",
    "console_polish",
    "telegram_channel",
)


def settings_with(raw: str) -> Settings:
    return Settings(_env_file=None, chhatri_features=raw)


def test_the_flag_names_are_the_wave0_list() -> None:
    assert FEATURE_NAMES == WAVE0_FLAGS
    assert len(set(FEATURE_NAMES)) == len(FEATURE_NAMES)
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", name) for name in FEATURE_NAMES)


def test_every_flag_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHHATRI_FEATURES", raising=False)
    settings = Settings(_env_file=None)
    assert settings.chhatri_features == ""
    assert enabled_features(settings) == frozenset()
    assert [name for name in FEATURE_NAMES if is_enabled(name, settings)] == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, set()),
        ("", set()),
        (" , ,\n\t", set()),
        ("n1_miniapp", {"n1_miniapp"}),
        ("N1_MINIAPP, n2_ask_chhatri", {"n1_miniapp", "n2_ask_chhatri"}),
        ("n1_miniapp n2_ask_chhatri\nn4_voice", {"n1_miniapp", "n2_ask_chhatri", "n4_voice"}),
        ("n1_miniapp,n1_miniapp", {"n1_miniapp"}),
        ("n1_miniapp,typo_flag", {"n1_miniapp"}),
    ],
)
def test_parse_reads_the_known_names_only(raw: str | None, expected: set[str]) -> None:
    assert parse_features(raw) == frozenset(expected)


def test_unknown_names_are_listed_once_in_order() -> None:
    assert unknown_features("n1_miniapp, n1_minapp,wat,N1_MINAPP") == ("n1_minapp", "wat")
    assert unknown_features("n1_miniapp") == ()
    assert unknown_features(None) == ()


def test_the_environment_turns_flags_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHHATRI_FEATURES", "n1_miniapp, H24_WHATIF")
    settings = Settings(_env_file=None)
    assert enabled_features(settings) == {"n1_miniapp", "h24_whatif"}
    assert is_enabled("h24_whatif", settings)
    assert not is_enabled("n2_ask_chhatri", settings)


def test_is_enabled_defaults_to_the_cached_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(features, "get_settings", lambda: settings_with("n4_voice"))
    assert is_enabled("n4_voice") is True
    assert is_enabled("n1_miniapp") is False
    assert enabled_features() == {"n4_voice"}


def test_a_name_that_is_not_a_flag_in_code_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="unknown feature flag 'n9_nothing'"):
        is_enabled("n9_nothing", settings_with("n9_nothing"))
