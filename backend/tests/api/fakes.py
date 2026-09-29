"""Fake AppState and Runtime for testing when replay module is not yet available (SPEC §24.6).

Implements the same interface as chhatri.replay.state.AppState and Runtime,
returning canned §19.2-shaped data for testing routes without the full orchestration.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
from chhatri.config import Settings
from chhatri.events import EventBus
from chhatri.domain.models import Merchant, Zone, Loan, Cover
from chhatri.domain.enums import Language, ShopType, CoverStatus, PayoutStatus
from chhatri.money import format_inr

IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class FakeStatic:
    """Mimics StaticContext (SPEC §24.6)."""

    settings: Settings
    rules: dict[str, Any] = field(default_factory=dict)
    data_dir: Path = field(default_factory=lambda: Path("/tmp/fake"))
    artifacts_dir: Path = field(default_factory=lambda: Path("/tmp/fake"))
    calibration: dict[str, Any] = field(default_factory=dict)
    city: Any = None
    model: Any = None
    model_error: str | None = None
    zones_geojson: dict[str, Any] = field(default_factory=dict)
    hexes_geojson: dict[str, Any] = field(default_factory=dict)
    backtest_report: dict[str, Any] | None = None
    premiums: dict[str, int] = field(default_factory=dict)


@dataclass
class FakeClock:
    """Fake ManualClock (SPEC §24.6)."""

    now: datetime = field(default_factory=lambda: datetime(2025, 8, 19, 17, 0, tzinfo=IST))

    def start(self, scenario_start: datetime) -> None:
        self.now = scenario_start

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@dataclass
class FakeRuntime:
    """Mimics Runtime (SPEC §24.6)."""

    scenario: dict[str, Any] = field(
        default_factory=lambda: {"name": "monsoon", "day": "2025-08-19"}
    )
    clock: FakeClock = field(default_factory=FakeClock)
    ids: Any = None
    store: Any = None
    audit: Any = None
    bus: EventBus = field(default_factory=EventBus)
    shocks: Any = None
    history: Any = None
    expected: Any = None
    integrations: dict[str, Any] = field(default_factory=dict)
    conversation: Any = None
    orchestrator: Any = None
    engine: Any = None
    scheduler: Any = None
    payouts: Any = None
    instalments: Any = None
    premiums: Any = None
    cases: Any = None
    _merchants: list[Merchant] = field(default_factory=list)
    _zones: list[Zone] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Initialize fake merchants and zones."""
        if not self._merchants:
            self._merchants = [
                Merchant(
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
                    h3_cell="881f025b3ffffff",
                    shop_type=ShopType.TEA_STALL,
                    weekly_off=None,
                    is_demo=True,
                ),
            ]
        if not self._zones:
            self._zones = [
                Zone(id="Z7", ward="F/S", name="Parel · Lalbaug", centroid_lat=19.00, centroid_lng=72.84),
                Zone(id="Z3", ward="G/S", name="Worli · Lower Parel", centroid_lat=18.98, centroid_lng=72.82),
                Zone(id="Z12", ward="E", name="Byculla", centroid_lat=18.96, centroid_lng=72.83),
            ]

    def merchant(self, merchant_id: str) -> Merchant | None:
        """Get a merchant by ID."""
        for m in self._merchants:
            if m.id == merchant_id:
                return m
        return None

    def zone(self, zone_id: str) -> Zone | None:
        """Get a zone by ID."""
        for z in self._zones:
            if z.id == zone_id:
                return z
        return None


class FakeAppState:
    """Mimics AppState (SPEC §24.6).

    Used for testing when the replay module is not available.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings_obj = settings or Settings()
        self.static = FakeStatic(settings=self.settings_obj)
        self.bus = EventBus()
        self._runtime: FakeRuntime | None = None

    @property
    def runtime(self) -> FakeRuntime:
        """Get runtime (RuntimeError if not loaded, SPEC §24.6)."""
        if self._runtime is None:
            raise RuntimeError("no scenario loaded")
        return self._runtime

    async def load(self, scenario: str) -> FakeRuntime:
        """Load a scenario, reset state (SPEC §24.6)."""
        if scenario not in ("monsoon", "illness", "illness_mismatch", "buy_cover"):
            raise ValueError(f"unknown scenario: {scenario}")

        self.bus.clear()
        self._runtime = FakeRuntime(scenario={"name": scenario, "day": "2025-08-19"})
        self.bus.publish("scenario", self._runtime.clock.now, {"scenario": scenario})
        return self._runtime

    async def shutdown(self) -> None:
        """Shutdown AppState."""
        pass

    def preflight(self) -> list[dict[str, Any]]:
        """Preflight checks (SPEC §19)."""
        return [
            {"name": "artifacts", "ok": True, "detail": "loaded"},
            {"name": "scenario", "ok": self._runtime is not None, "detail": "ready to load"},
            {"name": "integrations", "ok": True, "detail": "initialized"},
            {"name": "clock", "ok": self._runtime is not None, "detail": "running"},
        ]

    @property
    def static(self) -> FakeStatic:
        """Get static context."""
        return self._static

    @static.setter
    def static(self, value: FakeStatic) -> None:
        self._static = value


# Helper functions for generating canned response data


def fake_clock_state(runtime: FakeRuntime) -> dict[str, Any]:
    """Generate fake ClockState (§19.2)."""
    return {
        "now": runtime.clock.now.isoformat(),
        "scenario": runtime.scenario.get("name"),
        "scenario_title": "monsoon replay",
        "running": False,
        "speed": 1.0,
        "start": (runtime.clock.now - timedelta(hours=8)).isoformat(),
        "end": (runtime.clock.now + timedelta(hours=8)).isoformat(),
        "label": f"Mumbai · {runtime.scenario.get('name')} · 17:00 · simulated",
    }


def fake_zone_snapshot(zone: Zone, index_pct: int | None = None) -> dict[str, Any]:
    """Generate fake ZoneSnapshot (§19.2)."""
    return {
        "zone_id": zone.id,
        "ward": zone.ward,
        "name": zone.name,
        "shops": 46 if zone.id == "Z7" else 141 if zone.id == "Z3" else 125,
        "index_pct": index_pct,
        "live_index_pct": index_pct,
        "lower_bound_pct": 70,
        "status": "triggered" if index_pct and index_pct < 70 else "normal",
        "hours_below": 3 if index_pct and index_pct < 70 else 0,
        "alert": {
            "id": "A-20250819-01",
            "level": "RED",
            "kind": "RAIN",
            "valid_from": "2025-08-19T14:00:00+05:30",
            "valid_to": "2025-08-19T20:00:00+05:30",
            "headline_en": "Heavy rainfall expected",
        } if index_pct and index_pct < 70 else None,
        "label": f"{zone.id} · {index_pct or 100}% · {46 if zone.id == 'Z7' else 141 if zone.id == 'Z3' else 125} shops",
    }


def fake_payout() -> dict[str, Any]:
    """Generate fake Payout (§19.2)."""
    amount_paise = 138000
    return {
        "id": "P-000001",
        "decision_id": "D-000001",
        "merchant_id": "S-0142",
        "amount_paise": amount_paise,
        "amount_label": format_inr(amount_paise),
        "status": "CREDITED",
        "rail": "simulated",
        "created_at": "2025-08-19T17:00:00+05:30",
        "credited_at": "2025-08-19T17:04:00+05:30",
        "reference": "SIM-20250819-001",
    }
