"""Shared fixtures for the integrations tests (offline: fakes, httpx.MockTransport, local stubs)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import pytest

from chhatri.clock import ist
from chhatri.domain.enums import Language, ShopType
from chhatri.domain.models import Merchant

ANIL = Merchant(
    id="S-0142",
    shop_name="Anil's Tea Stall",
    owner_name="Anil Jadhav",
    owner_name_hi="अनिल",
    kyc_name="ANIL RAMESH JADHAV",
    phone="+919900012345",
    language=Language.HI,
    zone_id="Z7",
    lat=19.0046,
    lng=72.8424,
    h3_cell="883c...",
    shop_type=ShopType.TEA_STALL,
    is_demo=True,
)
OTHER = ANIL.model_copy(update={"id": "S-0001", "owner_name": "Suresh Patil", "is_demo": False})
SIM_NOW = ist(2025, 8, 19, 17, 0)


async def no_sleep(_: float) -> None:
    """Backoff sleeps recorded nowhere: tests stay fast and deterministic."""


class SleepRecorder:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


AMBIENT_AI_ENV = ("GOOGLE_API_KEY", "GEMINI_MODEL", "GEMINI_VISION_MODEL", "CHHATRI_DATA_IS_SYNTHETIC")


@pytest.fixture(autouse=True)
def _no_ambient_ai_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """A key or a gate flag exported in the developer's shell must never reach `Settings(_env_file=None)` here."""
    for name in AMBIENT_AI_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def anil() -> Merchant:
    return ANIL


@pytest.fixture
def other_merchant() -> Merchant:
    return OTHER


@pytest.fixture
def sim_clock() -> Callable[[], datetime]:
    return lambda: SIM_NOW


@pytest.fixture
def sleeps() -> SleepRecorder:
    return SleepRecorder()
