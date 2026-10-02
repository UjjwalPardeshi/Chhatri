"""Feature flags (Wave 0): every new feature ships behind a flag that is OFF until the environment turns it on.

``CHHATRI_FEATURES`` holds a comma- or space-separated list of flag names, for example
``CHHATRI_FEATURES="n1_miniapp,n2_ask_chhatri"``. The console reads the same names from ``VITE_FEATURES``
(``frontend/src/features.ts``); ``scripts/tests/test_feature_flags.py`` keeps the two lists identical.

Off means absent. A flagged route answers the ordinary 404 ``not_found`` envelope through the
``chhatri.api.deps.require_feature`` dependency, and the console hides the feature. Names in the environment
that are not flags are ignored (the API logs them once at start-up), so a typo can never stop the backend;
a name that is not a flag *in code* is a programming error and raises ``ValueError``.
"""

from __future__ import annotations

import re
from typing import Final

from chhatri.config import Settings, get_settings

__all__ = ["FEATURE_NAMES", "enabled_features", "is_enabled", "parse_features", "unknown_features"]

# Keep this tuple identical to FEATURE_NAMES in frontend/src/features.ts (a test compares them).
FEATURE_NAMES: Final[tuple[str, ...]] = (
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
)
_KNOWN: Final = frozenset(FEATURE_NAMES)
_SEPARATORS: Final = re.compile(r"[\s,]+")


def _tokens(raw: str | None) -> tuple[str, ...]:
    return tuple(token for token in _SEPARATORS.split((raw or "").lower()) if token)


def parse_features(raw: str | None) -> frozenset[str]:
    """The known flags named in ``raw`` (case, spacing and repeats do not matter)."""
    return frozenset(token for token in _tokens(raw) if token in _KNOWN)


def unknown_features(raw: str | None) -> tuple[str, ...]:
    """Names in ``raw`` that are not flags (typos), each once, in the order written."""
    return tuple(dict.fromkeys(token for token in _tokens(raw) if token not in _KNOWN))


def enabled_features(settings: Settings | None = None) -> frozenset[str]:
    """The flags that are on for ``settings`` (the cached process settings when omitted)."""
    return parse_features((settings or get_settings()).chhatri_features)


def is_enabled(name: str, settings: Settings | None = None) -> bool:
    """True when the flag ``name`` is on. ``ValueError`` when ``name`` is not a flag: a typo in code must be loud."""
    if name not in _KNOWN:
        raise ValueError(f"unknown feature flag {name!r}")
    return name in enabled_features(settings)
