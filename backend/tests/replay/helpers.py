"""Builders and fakes shared by the replay tests (SPEC §24.6).

Everything runs offline: `offline_settings` pins every live integration off, whatever the process
environment says, so a developer's keys can never make a test call Sarvam, WhatsApp, Paytm or n8n.
"""

from __future__ import annotations

import asyncio
import dataclasses
from collections.abc import Callable, Coroutine
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from pydantic import SecretStr

from chhatri.clock import at
from chhatri.config import DATA_DIR, Settings
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.integrations.base import IntegrationError, WorkflowRun
from chhatri.integrations.registry import Integrations, build_integrations
from chhatri.policy.rules import PolicyRules, default_rules
from chhatri.replay.state import AppState, Runtime
from chhatri.replay.static import StaticContext
from chhatri.sim.types import Calibration, City

SEED: Final = 20251019
MONSOON_DAY: Final = date(2025, 8, 19)
ILLNESS_DAY: Final = date(2025, 8, 21)
BUY_COVER_DAY: Final = date(2025, 8, 18)
ANIL: Final = "S-0142"
RAMESH: Final = "S-0907"
INTERNAL_SECRET: Final = "replay-test-internal-secret"
OFFICER_TOKEN: Final = "replay-test-officer-token"
TEST_PREMIUMS: Final = MappingProxyType({"Z3": 250, "Z7": 300, "Z9": 220, "Z12": 275})


def offline_settings(var_dir: Path, **overrides: Any) -> Settings:
    """Settings with every live integration off and no .env file read (SPEC §0.1)."""
    values: dict[str, Any] = {
        "chhatri_seed": SEED,
        "chhatri_var_dir": var_dir,
        "chhatri_data_dir": DATA_DIR,
        "chhatri_internal_secret": SecretStr(INTERNAL_SECRET),
        "chhatri_officer_token": SecretStr(OFFICER_TOKEN),
        "sarvam_api_key": None,
        "whatsapp_access_token": None,
        "whatsapp_phone_number_id": None,
        "whatsapp_app_secret": None,
        "whatsapp_verify_token": None,
        "whatsapp_demo_recipient": None,
        "paytm_mcp_url": None,
        "paytm_mid": None,
        "paytm_key_secret": None,
        "n8n_base_url": None,
        "cognee_enabled": False,
        "openmeteo_live": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def make_static(
    settings: Settings,
    city: City,
    model: ExpectedSalesModel | None,
    artifacts_dir: Path,
    *,
    model_error: str | None = None,
    premiums: MappingProxyType[str, int] = TEST_PREMIUMS,
    rules: PolicyRules | None = None,
) -> StaticContext:
    """A StaticContext built directly (no artefact files needed)."""
    return StaticContext(
        settings=settings,
        rules=rules or default_rules(),
        data_dir=DATA_DIR,
        artifacts_dir=artifacts_dir,
        calibration=Calibration(),
        city=city,
        model=model,
        model_error=model_error,
        zones_geojson=city.geography.zones_geojson,
        hexes_geojson=city.geography.hexes_geojson,
        backtest_report=None,
        premiums=premiums,
    )


def run_in_thread[T](factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Run a coroutine to completion on a private event loop in a worker thread.

    Session fixtures use it to build read-only runtimes without touching the test's event loop.
    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(factory())).result()


async def loaded(static: StaticContext, scenario: str, *, seek: str | None = None, **kw: Any) -> Runtime:
    """A fresh AppState with `scenario` loaded (and optionally sought to HH:MM)."""
    state = AppState(static, **kw)
    runtime = await state.load(scenario)
    if seek is not None:
        await runtime.engine.seek(seek)
    return state.runtime


def slip_bytes(rt: Runtime) -> bytes:
    """The scenario's sample slip photo (SPEC §17.2: anil_admission_slip.png / mismatch_admission_slip.png)."""
    if rt.scenario.slip_sample is None:
        raise ValueError(f"scenario {rt.scenario.name} has no sample slip")
    return (DATA_DIR / "slips" / rt.scenario.slip_sample).read_bytes()


def hhmm(value: datetime) -> str:
    return value.strftime("%H:%M")


def monsoon_at(hh: int, mm: int = 0) -> datetime:
    return at(MONSOON_DAY, hh, mm)


class RecordingWorkflows:
    """A WorkflowEngine that only records starts, like n8n before it calls back (SPEC §14.5)."""

    def __init__(self) -> None:
        self.started: list[tuple[str, str, dict[str, Any]]] = []

    async def start(self, workflow: str, payload: dict[str, Any]) -> WorkflowRun:
        subject = payload.get("decision_id") or payload.get("case_id")
        run_id = f"{workflow}:{subject}"
        self.started.append((workflow, run_id, dict(payload)))
        return WorkflowRun(workflow, run_id, "n8n", True, "recorded")


class FailingWorkflows:
    """A WorkflowEngine whose every start fails (n8n down, no fallback)."""

    def __init__(self) -> None:
        self.attempts = 0

    async def start(self, workflow: str, payload: dict[str, Any]) -> WorkflowRun:
        self.attempts += 1
        raise IntegrationError("n8n", "connection refused")


class FailingLinks:
    """A PaymentLinks whose link creation fails (Paytm staging down)."""

    async def create_premium_link(self, merchant: Any, amount_paise: int, purpose: str) -> Any:
        raise IntegrationError("paytm", "staging unavailable")

    async def link_payment(self, link_id: str) -> Any:
        raise IntegrationError("paytm", "staging unavailable")


def integrations_with(**fields: Any) -> Callable[..., Integrations]:
    """An integrations factory: the real registry, with some members replaced by fakes."""

    def factory(settings: Settings, **kwargs: Any) -> Integrations:
        return dataclasses.replace(build_integrations(settings, **kwargs), **fields)

    return factory


class GateSleep:
    """Fake `asyncio.sleep` for the engine clock: returns at once `wakes` times, then blocks.

    `blocked` is set once the engine sleeps for the (wakes + 1)-th time, so a test knows exactly
    how many 250 ms wake-ups happened; `pause()` cancels the blocked sleep.
    """

    def __init__(self, wakes: int) -> None:
        self.calls: list[float] = []
        self.wakes = wakes
        self.blocked = asyncio.Event()
        self._never = asyncio.Event()

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        if len(self.calls) > self.wakes:
            self.blocked.set()
            await self._never.wait()
        await asyncio.sleep(0)


class StepClock:
    """Fake `time.monotonic`: advances `step` seconds on every call."""

    def __init__(self, step: float) -> None:
        self.step = step
        self.now = 0.0

    def __call__(self) -> float:
        self.now += self.step
        return self.now
