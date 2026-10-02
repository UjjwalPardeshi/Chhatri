"""build_voice_service: the reason Sarvam speech is not used follows ADR 0009 when a key is set but the gate is closed."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from chhatri.ai.labels import FallbackReason
from chhatri.ask.wiring import build_voice_service
from chhatri.config import Settings
from chhatri.ids import IdFactory
from chhatri.integrations.free_tier import GATE_CLOSED_DETAIL
from chhatri.integrations.statuses import simulated


def _runtime() -> SimpleNamespace:
    statuses = (
        simulated("sarvam_stt", f"Sarvam key set; {GATE_CLOSED_DETAIL}"),
        simulated("sarvam_tts", f"Sarvam key set; {GATE_CLOSED_DETAIL}"),
    )
    integrations = SimpleNamespace(stt=None, tts=None, statuses=statuses, switch=None)
    return SimpleNamespace(
        integrations=integrations,
        store=SimpleNamespace(put_media=None),
        ids=IdFactory(),
        audit=None,
        clock=None,
    )


@pytest.mark.parametrize(
    ("key", "expected"),
    [("sk-sarvam-SECRET", FallbackReason.FREE_TIER_BLOCKED), (None, FallbackReason.NO_KEY)],
)
def test_a_closed_gate_with_a_key_is_free_tier_blocked_and_no_key_stays_no_key(
    key: str | None, expected: FallbackReason
) -> None:
    settings = Settings(_env_file=None, sarvam_api_key=key, chhatri_data_is_synthetic=False)  # type: ignore[call-arg]
    service = build_voice_service(runtime=_runtime(), settings=settings)
    assert service._unavailable() is expected  # noqa: SLF001
