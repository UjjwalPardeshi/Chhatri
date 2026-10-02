"""FakeAppState for API tests (SPEC §24.6 AppState / Runtime / StaticContext shape).

``FakeAppState`` loads one of the four scenarios into a ``FakeRuntime`` holding a real ``ManualClock``
and ``IdFactory`` plus the fake services in ``fake_services.py``. The views are replaced by
``fake_views.py`` (canned §19.2 data), so these tests exercise only the HTTP layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Final

from pydantic import SecretStr

from chhatri.clock import IST, ManualClock, at
from chhatri.config import DATA_DIR, Settings
from chhatri.domain.enums import IntegrationMode, Language, ShopType
from chhatri.domain.models import Merchant, Zone
from chhatri.events import EventBus
from chhatri.ids import IdFactory
from chhatri.integrations.base import IntegrationError, IntegrationStatus, RainSeries
from tests.api import canned
from tests.api.fake_services import (
    FakeAudit,
    FakeChannel,
    FakeConversation,
    FakeEngine,
    FakeOrchestrator,
    FakeStore,
    area_decision,
    dispute_case,
    payout,
)

OFFICER_TOKEN: Final = "officer-token-7Qx9"
INTERNAL_SECRET: Final = "internal-secret-4Kd2"
WA_APP_SECRET: Final = "wa-app-secret-8Hs1"
WA_VERIFY_TOKEN: Final = "wa-verify-token-2Lm5"
WA_ACCESS_TOKEN: Final = "wa-access-token-9Pz3"
PAYTM_KEY: Final = "paytmkey16chars!"
DEMO_RECIPIENT: Final = "+919800000001"
CONSOLE_ORIGIN: Final = "http://console.test"
SECRETS: Final = (INTERNAL_SECRET, WA_APP_SECRET, WA_VERIFY_TOKEN, WA_ACCESS_TOKEN, PAYTM_KEY)
DEMO_MERCHANT: Final = {
    "monsoon": "S-0142",
    "illness": "S-0142",
    "illness_mismatch": "S-0142",
    "buy_cover": "S-0907",
}
SCENARIO_TIMES: Final = {
    "monsoon": (date(2025, 8, 19), 8, 20),
    "illness": (date(2025, 8, 21), 10, 13),
    "illness_mismatch": (date(2025, 8, 21), 10, 13),
    "buy_cover": (date(2025, 8, 18), 18, 19),
}
SLIPS: Final = {"illness": "anil_admission_slip.png", "illness_mismatch": "mismatch_admission_slip.png"}
INTEGRATION_NAMES: Final = (
    "sarvam_stt",
    "sarvam_tts",
    "sarvam_chat",
    "sarvam_vision",
    "whatsapp",
    "paytm",
    "n8n",
    "memory",
    "weather",
    "soundbox",
    "sales_data",
    "alerts",
    "payout_rail",
    "lender",
    "kyc",
)


def make_settings(*, omit: tuple[str, ...] = (), **overrides: Any) -> Settings:
    """Settings isolated from any .env / environment, with known secrets (SPEC §21).

    ``omit`` leaves fields unset so their defaults apply (e.g. a generated officer token).
    """
    values: dict[str, Any] = {
        "chhatri_officer_token": SecretStr(OFFICER_TOKEN),
        "chhatri_internal_secret": SecretStr(INTERNAL_SECRET),
        "chhatri_demo_mode": True,
        "chhatri_features": "",
        "chhatri_console_origin": CONSOLE_ORIGIN,
        "chhatri_data_dir": DATA_DIR,
        "sarvam_api_key": None,
        "whatsapp_access_token": SecretStr(WA_ACCESS_TOKEN),
        "whatsapp_phone_number_id": "1234567890",
        "whatsapp_app_secret": SecretStr(WA_APP_SECRET),
        "whatsapp_verify_token": SecretStr(WA_VERIFY_TOKEN),
        "whatsapp_demo_recipient": DEMO_RECIPIENT,
        "paytm_mcp_url": None,
        "paytm_mid": None,
        "paytm_key_secret": None,
        "n8n_base_url": None,
        "openmeteo_live": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **{key: value for key, value in values.items() if key not in omit})


def _merchant(merchant_id: str, zone_id: str, shop: str, owner: str, owner_hi: str) -> Merchant:
    return Merchant(
        id=merchant_id,
        shop_name=shop,
        owner_name=owner,
        owner_name_hi=owner_hi,
        kyc_name=owner.upper(),
        phone=f"+9199000{merchant_id[-4:]}1",
        language=Language.HI,
        zone_id=zone_id,
        lat=19.0,
        lng=72.84,
        h3_cell="883c9e0a21fffff",
        shop_type=ShopType.TEA_STALL,
        weekly_off=None,
        is_demo=True,
    )


@dataclass(frozen=True, slots=True)
class FakeCity:
    zones: tuple[Zone, ...] = tuple(
        Zone(id=zone_id, ward=values[0], name=values[1], centroid_lat=19.0, centroid_lng=72.84)
        for zone_id, values in canned.ZONES.items()
    )
    merchants: tuple[Merchant, ...] = (
        _merchant("S-0142", "Z7", "Anil's Tea Stall", "Anil Jadhav", "अनिल"),
        _merchant("S-0907", "Z3", "Ramesh Kirana", "Ramesh Patil", "रमेश"),
        _merchant("S-0311", "Z12", "Byculla Fruits", "Sunita More", "सुनीता"),
    )

    def merchant(self, merchant_id: str) -> Merchant:
        for merchant in self.merchants:
            if merchant.id == merchant_id:
                return merchant
        raise KeyError(merchant_id)


@dataclass(frozen=True, slots=True)
class FakeStatic:
    settings: Settings
    rules: Any = "rules"
    data_dir: Path = DATA_DIR
    city: FakeCity = field(default_factory=FakeCity)
    zones_geojson: dict[str, Any] = field(default_factory=lambda: canned.geojson("zones"))
    hexes_geojson: dict[str, Any] = field(default_factory=lambda: canned.geojson("hexes"))
    backtest_report: dict[str, Any] | None = field(default_factory=canned.backtest_report)


@dataclass(frozen=True, slots=True)
class FakeScenario:
    name: str
    title: str
    day: date
    start: datetime
    end: datetime
    demo_merchant_id: str
    slip_sample: str | None


@dataclass
class FakeWeather:
    fail: bool = False

    async def hourly_rain(self, latitude: float, longitude: float, start: date, end: date) -> RainSeries:
        if self.fail:
            raise IntegrationError("openmeteo", "timeout")
        first = datetime(start.year, start.month, start.day, tzinfo=IST)
        times = tuple(first + timedelta(hours=hour) for hour in range(24))
        return RainSeries(latitude, longitude, times, tuple(0.5 * hour for hour in range(24)), "open-meteo")


@dataclass
class FakeIntegrations:
    channel: FakeChannel = field(default_factory=FakeChannel)
    weather: FakeWeather = field(default_factory=FakeWeather)
    statuses: tuple[IntegrationStatus, ...] = tuple(
        IntegrationStatus(
            name, IntegrationMode.LIVE if name == "whatsapp" else IntegrationMode.SIMULATED, "fake"
        )
        for name in INTEGRATION_NAMES
    )


def make_scenario(name: str) -> FakeScenario:
    day, start, end = SCENARIO_TIMES[name]
    return FakeScenario(
        name=name,
        title=f"{name.replace('_', ' ')} replay",
        day=day,
        start=at(day, start),
        end=at(day, end),
        demo_merchant_id=DEMO_MERCHANT[name],
        slip_sample=SLIPS.get(name),
    )


class FakeRuntime:
    def __init__(self, state: FakeAppState, scenario: str) -> None:
        self.scenario = make_scenario(scenario)
        self.clock = ManualClock(self.scenario.start)
        self.ids = IdFactory()
        self.bus = state.bus
        zone_of = {m.id: m.zone_id for m in state.static.city.merchants}
        self.store = FakeStore(zone_of=zone_of)
        self.audit = FakeAudit()
        self.integrations = FakeIntegrations()
        self.engine = FakeEngine(runtime=self, state=state)
        self.orchestrator = FakeOrchestrator(runtime=self)
        self.conversation = FakeConversation(runtime=self)
        self._seed_records()

    def _seed_records(self) -> None:
        decision = area_decision(self.ids.next("decision"))
        self.store.decisions_by_id[decision.id] = decision
        self.store.payout_list.extend(
            [payout(self.ids.next("payout")), payout(self.ids.next("payout"), "S-0907")]
        )
        case = dispute_case(self.ids.next_case())
        self.store.cases_by_id[case.id] = case


class FakeAppState:
    """AppState double: ``runtime`` raises RuntimeError before a load; ``load`` validates the name."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.static = FakeStatic(settings=settings or make_settings())
        self.bus = EventBus()
        self._runtime: FakeRuntime | None = None
        self.loads: list[str] = []
        self.shut_down = False

    @property
    def runtime(self) -> FakeRuntime:
        if self._runtime is None:
            raise RuntimeError("no scenario loaded")
        return self._runtime

    async def load(self, scenario: str) -> FakeRuntime:
        if scenario not in SCENARIO_TIMES:
            raise ValueError(f"unknown scenario {scenario!r}")
        self.loads.append(scenario)
        self._runtime = FakeRuntime(self, scenario)
        self.bus.publish("scenario", self._runtime.clock.now(), {"scenario": scenario})
        return self._runtime

    async def shutdown(self) -> None:
        if self._runtime is not None:
            await self._runtime.engine.pause()
        self.shut_down = True

    def preflight(self) -> list[dict[str, Any]]:
        return canned.preflight()
