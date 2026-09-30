"""Process state and per-scenario runtime (SPEC §3, §24.6).

- `StaticContext` / `load_static` (re-exported from `chhatri.replay.static`): built once per process.
- `Runtime`: everything of one loaded scenario. SPEC §3: ids, store, audit log, clock, scheduler,
  zone board and feed are new on every load, so a scenario always replays to the same ids,
  amounts and audit hashes. The `EventBus` is the process-wide one: its history is cleared and a
  ``scenario`` event published on every load, so a reconnecting console only sees the new run.
- `AppState.load(name)`: ValueError for an unknown scenario (API 422); RuntimeError when the model
  artefacts are missing or the scenario cannot be built (API 503) — including an integration that
  cannot be configured; the previously loaded runtime then stays loaded (paused). The world
  (history and predictions) is built in a worker thread so the event loop keeps serving; the
  previous runtime's clock is paused first. The previous runtime is not closed: a request still
  holding it finishes on it, and it is released with its last reference.
- Channel name: WHATSAPP when the WhatsApp integration is LIVE, else SIMULATOR (the phone view).
- `AppState.preflight()`: see `chhatri.replay.preflight`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Protocol

import numpy as np

from chhatri.cases.service import CaseService
from chhatri.clock import ManualClock
from chhatri.config import Settings
from chhatri.conversation.service import ConversationService
from chhatri.domain.enums import Channel, IntegrationMode
from chhatri.events import EventBus
from chhatri.forecast.errors import ForecastError
from chhatri.ids import IdFactory
from chhatri.integrations.registry import Integrations, build_integrations
from chhatri.ledger.instalments import InstalmentService
from chhatri.ledger.payouts import PayoutService
from chhatri.ledger.premiums import PremiumService
from chhatri.policy.rules import PolicyRules
from chhatri.replay.audit_bus import PublishingAuditLog
from chhatri.replay.board import ZoneBoard
from chhatri.replay.engine import ReplayEngine
from chhatri.replay.feed import FeedLog
from chhatri.replay.live import HexIndex
from chhatri.replay.orchestrator import Orchestrator
from chhatri.replay.preflight import preflight_rows
from chhatri.replay.publish import Publisher, RuntimeLink
from chhatri.replay.scheduler import FailureRecorder, SimScheduler
from chhatri.replay.static import StaticContext, load_static
from chhatri.replay.world import ScenarioData, build_world
from chhatri.sim.scenarios import SCENARIOS
from chhatri.sim.types import SalesPanel, Scenario
from chhatri.sim.weather import ShockCalendar
from chhatri.store.repositories import Store
from chhatri.workflows import definitions as wf

__all__ = ["AppState", "Runtime", "StaticContext", "load_static"]

logger = logging.getLogger(__name__)

WHATSAPP_STATUS: Final = "whatsapp"
LOAD_ERRORS: Final = (ValueError, KeyError, IndexError, OSError, ForecastError)


class IntegrationsFactory(Protocol):
    """`chhatri.integrations.registry.build_integrations` (SPEC §24.5); injectable for tests."""

    def __call__(
        self,
        settings: Settings,
        *,
        scheduler: SimScheduler,
        step_handlers: Orchestrator,
        data_dir: Path,
        rules: PolicyRules,
    ) -> Integrations: ...


@dataclass(frozen=True, slots=True)
class Runtime:
    """One loaded scenario (SPEC §24.6)."""

    static: StaticContext
    world: ScenarioData
    clock: ManualClock
    ids: IdFactory
    store: Store
    audit: PublishingAuditLog
    bus: EventBus
    integrations: Integrations
    conversation: ConversationService
    orchestrator: Orchestrator
    engine: ReplayEngine
    scheduler: SimScheduler
    payouts: PayoutService
    instalments: InstalmentService
    premiums: PremiumService
    cases: CaseService
    board: ZoneBoard
    feed: FeedLog
    hex_index: HexIndex
    zone_shops: Mapping[str, int]

    @property
    def scenario(self) -> Scenario:
        return self.world.scenario

    @property
    def shocks(self) -> ShockCalendar:
        return self.world.shocks

    @property
    def history(self) -> SalesPanel:
        """history_start .. the last scenario day, full days (SPEC §24.6)."""
        return self.world.history

    @property
    def expected(self) -> np.ndarray:
        """(M, 24 × scenario days, 3) predictions from the scenario day's midnight (SPEC §24.6)."""
        return self.world.expected


@dataclass(frozen=True, slots=True)
class _Core:
    """The per-load pieces built before the integrations."""

    link: RuntimeLink
    publisher: Publisher
    clock: ManualClock
    ids: IdFactory
    store: Store
    audit: PublishingAuditLog
    feed: FeedLog
    failures: FailureRecorder
    scheduler: SimScheduler
    orchestrator: Orchestrator


def _zone_shops(static: StaticContext, store: Store) -> Mapping[str, int]:
    """Covered shops per zone at load (ZoneSnapshot ``shops``, SPEC §5.4)."""
    counts = Counter(static.city.merchant(mid).zone_id for mid in store.covers())
    return MappingProxyType({zone.id: counts.get(zone.id, 0) for zone in static.city.zones})


def _settle_minutes(rules: PolicyRules) -> int:
    """The payout workflow's last step offset: how long money decided at the end takes (B1)."""
    return max(step.delay_minutes_from_start for step in wf.build_workflows(rules)[wf.PAYOUT])


def _channel(integrations: Integrations) -> Channel:
    live = any(s.name == WHATSAPP_STATUS and s.mode is IntegrationMode.LIVE for s in integrations.statuses)
    return Channel.WHATSAPP if live else Channel.SIMULATOR


class AppState:
    """Stored at FastAPI ``app.state.chhatri`` (SPEC §24.6)."""

    def __init__(
        self,
        static: StaticContext,
        *,
        bus: EventBus | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        integrations_factory: IntegrationsFactory = build_integrations,
    ) -> None:
        self.static = static
        self.bus = bus if bus is not None else EventBus()
        self._sleep = sleep
        self._monotonic = monotonic
        self._build_integrations = integrations_factory
        self._hex_index = HexIndex.build(static.city)
        self._runtime: Runtime | None = None

    @property
    def runtime(self) -> Runtime:
        """The loaded scenario; RuntimeError when nothing is loaded."""
        if self._runtime is None:
            raise RuntimeError("no scenario is loaded")
        return self._runtime

    async def load(self, scenario: str) -> Runtime:
        """Load `scenario` paused at its start with fresh ids, store and audit (SPEC §3, §17)."""
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown scenario {scenario!r}; expected one of {', '.join(SCENARIOS)}")
        if self.static.model is None:
            raise RuntimeError(f"cannot load {scenario}: {self.static.model_error}")
        if self._runtime is not None:
            await self._runtime.engine.pause()
        try:
            world = await asyncio.to_thread(build_world, self.static, scenario)
            core = self._core(world)
            runtime = self._assemble(world, core)
        except LOAD_ERRORS as exc:
            logger.exception("scenario %s could not be built", scenario)
            raise RuntimeError(f"scenario {scenario} could not be built: {exc}") from exc
        core.link.bind(runtime)
        self._runtime = runtime
        self.bus.clear()
        core.publisher.scenario()
        await runtime.orchestrator.start()
        logger.info("scenario %s loaded, paused at %s", scenario, world.scenario.start.isoformat())
        return runtime

    def _core(self, world: ScenarioData) -> _Core:
        link = RuntimeLink()
        publisher = Publisher(self.bus, link)
        audit = PublishingAuditLog(self.bus)
        feed = FeedLog()
        failures = FailureRecorder(audit, feed)
        clock = ManualClock(world.scenario.start)
        return _Core(
            link=link,
            publisher=publisher,
            clock=clock,
            ids=IdFactory(),
            store=Store(self.static.city),
            audit=audit,
            feed=feed,
            failures=failures,
            scheduler=SimScheduler(clock, failures),
            orchestrator=Orchestrator(link, publisher),
        )

    def _assemble(self, world: ScenarioData, core: _Core) -> Runtime:
        static = self.static
        integrations = self._build_integrations(
            static.settings,
            scheduler=core.scheduler,
            step_handlers=core.orchestrator,
            data_dir=static.data_dir,
            rules=static.rules,
        )
        return Runtime(
            static=static,
            world=world,
            clock=core.clock,
            ids=core.ids,
            store=core.store,
            audit=core.audit,
            bus=self.bus,
            integrations=integrations,
            conversation=self._conversation(core, integrations),
            orchestrator=core.orchestrator,
            engine=self._engine(world, core),
            scheduler=core.scheduler,
            payouts=PayoutService(core.store, core.audit, core.ids, static.rules),
            instalments=InstalmentService(core.store, core.audit, core.ids),
            premiums=PremiumService(
                core.store,
                core.audit,
                core.ids,
                static.rules,
                integrations.payments,
                premiums=static.premiums,
            ),
            cases=CaseService(core.store, core.audit, core.ids, static.rules),
            board=ZoneBoard(),
            feed=core.feed,
            hex_index=self._hex_index,
            zone_shops=_zone_shops(static, core.store),
        )

    def _conversation(self, core: _Core, integrations: Integrations) -> ConversationService:
        return ConversationService(
            city=self.static.city,
            store=core.store,
            audit=core.audit,
            ids=core.ids,
            clock=core.clock,
            bus=self.bus,
            channel=integrations.channel,
            stt=integrations.stt,
            tts=integrations.tts,
            chat=integrations.chat,
            slips=integrations.slips,
            soundbox=integrations.soundbox,
            claims=core.orchestrator,
            channel_name=_channel(integrations),
        )

    def _engine(self, world: ScenarioData, core: _Core) -> ReplayEngine:
        name = world.scenario.name

        async def reload() -> ReplayEngine:
            return (await self.load(name)).engine

        return ReplayEngine(
            clock=core.clock,
            scheduler=core.scheduler,
            hooks=core.orchestrator,
            events=core.publisher,
            failures=core.failures,
            start=world.scenario.start,
            end=world.scenario.end,
            reload=reload,
            sleep=self._sleep,
            monotonic=self._monotonic,
            settle_minutes=_settle_minutes(self.static.rules),
        )

    async def shutdown(self) -> None:
        """Pause the clock and close the audit log of the loaded scenario."""
        runtime, self._runtime = self._runtime, None
        if runtime is None:
            return
        await runtime.engine.pause()
        runtime.audit.close()
        logger.info("replay state shut down (%s)", runtime.scenario.name)

    def preflight(self) -> list[dict[str, Any]]:
        """``[{name, ok, detail}]`` readiness rows (SPEC §19 /api/preflight)."""
        return preflight_rows(self.static, self._runtime)
