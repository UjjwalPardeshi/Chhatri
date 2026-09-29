"""Replay state management (SPEC §24.6, §17).

StaticContext: built once per process at startup; immutable.
Runtime: per-scenario state; fresh instance on each load.
AppState: FastAPI app state; manages lifecycle and scenario loading.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from chhatri.audit.log import AuditLog
from chhatri.clock import ManualClock, at, ist
from chhatri.config import Settings
from chhatri.domain.models import Alert
from chhatri.events import EventBus
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.ids import IdFactory
from chhatri.integrations.registry import build_integrations
from chhatri.policy.rules import PolicyRules, default_rules
from chhatri.sim.calibration import load_calibration
from chhatri.sim.city import build_city
from chhatri.sim.geo import build_geography
from chhatri.sim.sales import SalesSimulator
from chhatri.sim.scenarios import SCENARIOS, get_scenario
from chhatri.sim.weather import build_shocks
from chhatri.store.repositories import Store

if TYPE_CHECKING:
    from chhatri.cases.service import CaseService
    from chhatri.conversation.service import ConversationService
    from chhatri.ledger.instalments import InstalmentService
    from chhatri.ledger.payouts import PayoutService
    from chhatri.ledger.premiums import PremiumService
    from chhatri.replay.engine import ReplayEngine
    from chhatri.replay.orchestrator import Orchestrator
    from chhatri.replay.scheduler import SimScheduler
    from chhatri.sim.city import City
    from chhatri.sim.geo import Geography
    from chhatri.sim.sales import SalesPanel
    from chhatri.sim.scenarios import Scenario
    from chhatri.sim.weather import ShockCalendar

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StaticContext:
    """Build-once-per-process immutable context. SPEC §24.6."""

    settings: Settings
    rules: PolicyRules
    data_dir: Path
    artifacts_dir: Path
    calibration: "Calibration"
    city: City
    model: ExpectedSalesModel | None  # None if artefacts missing
    model_error: str | None
    zones_geojson: dict
    hexes_geojson: dict
    backtest_report: dict | None
    premiums: dict[str, int]  # zone_id → paise per day


def load_static(settings: Settings) -> StaticContext:
    """Load static context at startup (SPEC §24.6). SPEC §0.2: missing model artefacts
    do NOT crash; model=None + model_error is reported via preflight."""

    data_dir = settings.chhatri_data_dir
    artifacts_dir = data_dir.parent / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Load rules
    rules = default_rules()

    # Load calibration
    calibration = load_calibration(data_dir)

    # Load city
    city = build_city(settings.chhatri_seed, data_dir, calibration, scale="full")

    # Load geography
    wards_geojson_path = data_dir / "geo" / "bmc_wards.geojson"
    if not wards_geojson_path.exists():
        raise FileNotFoundError(f"BMC wards GeoJSON not found: {wards_geojson_path}")
    with open(wards_geojson_path) as f:
        wards_geojson = json.load(f)

    shops_per_zone = {zone.id: len(list(city.zone_rows(zone.id))) for zone in city.zones}
    geography = build_geography(wards_geojson_path, shops_per_zone)
    zones_geojson = geography.zones_geojson
    hexes_geojson = geography.hexes_geojson

    # Load model
    model = None
    model_error = None
    model_dir = artifacts_dir / "model"
    if model_dir.exists():
        try:
            model = ExpectedSalesModel.load(model_dir)
            logger.info("Loaded expected-sales model from %s", model_dir)
        except Exception as e:
            model_error = f"Failed to load model: {e}"
            logger.warning("Model load failed (will report in preflight): %s", model_error)
    else:
        model_error = f"Model artifacts not found at {model_dir}"
        logger.info(model_error)

    # Load backtest report
    backtest_report = None
    backtest_file = artifacts_dir / "backtest" / "report.json"
    if backtest_file.exists():
        try:
            with open(backtest_file) as f:
                backtest_report = json.load(f)
        except Exception as e:
            logger.warning("Failed to load backtest report: %s", e)

    # Load premiums
    premiums: dict[str, int] = {}
    premiums_file = artifacts_dir / "premiums.json"
    if premiums_file.exists():
        try:
            with open(premiums_file) as f:
                premiums = {k: int(v) for k, v in json.load(f).items()}
        except Exception as e:
            logger.warning("Failed to load premiums: %s", e)
    logger.info("Loaded premiums for %d zones", len(premiums))

    return StaticContext(
        settings=settings,
        rules=rules,
        data_dir=data_dir,
        artifacts_dir=artifacts_dir,
        calibration=calibration,
        city=city,
        model=model,
        model_error=model_error,
        zones_geojson=zones_geojson,
        hexes_geojson=hexes_geojson,
        backtest_report=backtest_report,
        premiums=premiums,
    )


@dataclass
class Runtime:
    """Per-scenario runtime state. Fresh instance on each load. SPEC §24.6.

    Attributes are populated during load(); most are initialized after init.
    """

    static: StaticContext
    bus: EventBus
    scenario: Scenario
    clock: ManualClock
    ids: IdFactory
    store: Store
    audit: AuditLog
    shocks: ShockCalendar
    history: SalesPanel
    expected: np.ndarray
    integrations: "Integrations"
    conversation: ConversationService
    orchestrator: Orchestrator
    engine: ReplayEngine
    scheduler: SimScheduler
    payouts: PayoutService
    instalments: InstalmentService
    premiums: PremiumService
    cases: CaseService


class AppState:
    """FastAPI app state (SPEC §24.6). Manages static load once and scenario loads.

    SPEC §3: ids, store, audit, and IdFactory are reset on each scenario load.
    SPEC design note: EventBus is shared across loads; its history is cleared and a
    "scenario" event is published on load.
    """

    def __init__(self, static: StaticContext) -> None:
        self.static = static
        self.bus = EventBus()
        self._runtime: Runtime | None = None

    @property
    def runtime(self) -> Runtime:
        """The currently loaded scenario's runtime. Raises RuntimeError if nothing loaded."""
        if self._runtime is None:
            raise RuntimeError("No scenario loaded")
        return self._runtime

    async def load(self, scenario_name: str) -> Runtime:
        """Load a scenario (SPEC §24.6; §3: resets ids/store/audit).

        Raises:
            ValueError: unknown scenario name.
            RuntimeError: model missing (required for decisions).
        """
        if scenario_name not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario_name}")

        if self.static.model is None:
            raise RuntimeError(
                f"Cannot load scenario without model: {self.static.model_error}"
            )

        logger.info("Loading scenario %s", scenario_name)

        # Fresh per-load instances
        scenario = get_scenario(scenario_name, self.static.city, self.static.calibration)
        clock = ManualClock(scenario.start)
        ids = IdFactory()
        store = Store(self.static.city)

        # Audit DB: per load, under var_dir/runs/ or in-memory
        audit_path = self.static.settings.var_dir / "runs"
        audit_path.mkdir(parents=True, exist_ok=True)
        # Use per-run audit DBs to avoid collision: named by scenario + timestamp-ish
        run_id = scenario.name
        audit_db = audit_path / f"{run_id}.db"
        audit = AuditLog(audit_db)

        # Shocks and sales history
        shocks = build_shocks(
            self.static.city,
            self.static.data_dir,
            self.static.settings.chhatri_seed,
            overrides=scenario.overrides,
        )
        simulator = SalesSimulator(self.static.city, shocks, self.static.settings.chhatri_seed)

        # History panel: [history_start, scenario.day + 1) — full days
        history = simulator.generate(scenario.history_start, scenario.day)

        # Expected sales for the scenario day(s)
        # (M, 24 * num_days, 3) for p10/p50/p90
        scenario_days = (scenario.end.date() - scenario.start.date()).days + 1
        expected = self.static.model.predict(
            self.static.city,
            history,
            scenario.start,
            24 * scenario_days,
        )

        # Clear bus history and publish scenario event
        self.bus.clear()
        self.bus.publish(
            "scenario",
            clock.now(),
            {"clock": {"now": clock.now().isoformat()}},
        )

        # Build integrations (scheduler = SimScheduler, step_handlers = orchestrator later)
        # For now, pass a dummy scheduler; orchestrator will inject itself
        from chhatri.replay.scheduler import SimScheduler
        from chhatri.replay.orchestrator import Orchestrator

        scheduler = SimScheduler()
        orchestrator = Orchestrator(
            static=self.static,
            runtime_getter=lambda: self._runtime,  # type: ignore
            ids=ids,
            store=store,
            audit=audit,
            clock=clock,
            bus=self.bus,
        )

        integrations = build_integrations(
            self.static.settings,
            scheduler=scheduler,
            step_handlers=orchestrator,
            data_dir=self.static.data_dir,
        )

        # Ledger services
        from chhatri.cases.service import CaseService
        from chhatri.conversation.service import ConversationService
        from chhatri.ledger.instalments import InstalmentService
        from chhatri.ledger.payouts import PayoutService
        from chhatri.ledger.premiums import PremiumService
        from chhatri.replay.engine import ReplayEngine

        payouts = PayoutService(store, audit, ids, self.static.rules)
        instalments = InstalmentService(store, audit, ids)
        premiums = PremiumService(
            store, audit, ids, self.static.rules, integrations.payments
        )
        cases = CaseService(store, audit, ids, self.static.rules)

        # Conversation service
        conversation = ConversationService(
            city=self.static.city,
            store=store,
            audit=audit,
            ids=ids,
            clock=clock,
            bus=self.bus,
            channel=integrations.channel,
            stt=integrations.stt,
            tts=integrations.tts,
            chat=integrations.chat,
            slips=integrations.slips,
            soundbox=integrations.soundbox,
            claims=orchestrator,
            channel_name="SIMULATOR",
        )

        # Replay engine
        engine = ReplayEngine(
            static=self.static,
            runtime_getter=lambda: self._runtime,  # type: ignore
            clock=clock,
            scheduler=scheduler,
            bus=self.bus,
        )

        # Wire orchestrator and engine
        orchestrator.conversation = conversation
        orchestrator.engine = engine
        scheduler.runtime_getter = lambda: self._runtime  # type: ignore
        engine.orchestrator = orchestrator

        # Create runtime
        runtime = Runtime(
            static=self.static,
            bus=self.bus,
            scenario=scenario,
            clock=clock,
            ids=ids,
            store=store,
            audit=audit,
            shocks=shocks,
            history=history,
            expected=expected,
            integrations=integrations,
            conversation=conversation,
            orchestrator=orchestrator,
            engine=engine,
            scheduler=scheduler,
            payouts=payouts,
            instalments=instalments,
            premiums=premiums,
            cases=cases,
        )
        self._runtime = runtime

        logger.info("Scenario %s loaded; ready at %s", scenario_name, clock.now())
        return runtime

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._runtime is not None:
            try:
                self._runtime.audit.verify()
            except Exception as e:
                logger.warning("Audit verification failed at shutdown: %s", e)
        logger.info("AppState shutdown")

    def preflight(self) -> list[dict]:
        """Preflight checks (SPEC §19; /api/preflight).

        Returns:
            [{name, ok, detail}] for each readiness check.
        """
        checks = []

        # Static context
        checks.append({"name": "rules", "ok": True, "detail": "loaded"})
        checks.append({"name": "calibration", "ok": True, "detail": "loaded"})
        checks.append(
            {
                "name": "model",
                "ok": self.static.model is not None,
                "detail": self.static.model_error or "loaded",
            }
        )
        checks.append({"name": "city", "ok": True, "detail": f"{len(self.static.city.merchants)} merchants"})

        # Scenario loadable
        try:
            _ = get_scenario("monsoon", self.static.city, self.static.calibration)
            checks.append({"name": "scenario", "ok": True, "detail": "monsoon loadable"})
        except Exception as e:
            checks.append({"name": "scenario", "ok": False, "detail": str(e)})

        # Integrations
        if self._runtime is not None:
            for status in self._runtime.integrations.statuses:
                checks.append(
                    {
                        "name": status.name,
                        "ok": status.mode == "LIVE",
                        "detail": status.mode,
                    }
                )

        # Clock
        checks.append({"name": "clock", "ok": True, "detail": "manual clock ready"})

        return checks
