"""The deck's demo end to end over HTTP, for every scenario (SPEC §13.6, §17.2, §22; B1, B2, B5).

The flows of `chhatri.api.demo` drive the real app (`create_app` on a real `AppState`, httpx
``ASGITransport``) through the SPEC §19 routes only — load, seek and step the clock, talk as the
merchant through ``/messages``, ``/voice-demo`` and ``/photo``, approve as the officer with the
bearer token, pay the premium through the Paytm callback — and every observed string, time and
count is compared with `chhatri.api.demo.golden.expectations`.

- Fast (always runs): the small city with a quickly trained model. It is not calibrated, so its
  numbers (`DemoNumbers`) are derived here straight from the world data and the pure policy
  functions — `evaluate_hour` at 17:00, `publish_expected_day`, `area_amount`, `personal_amount` —
  never from the replay's own records, and the HTTP story must reproduce them.
- Slow: the committed full artefacts (`make data`) must reproduce the SPEC §17.2 `GOLDEN` numbers,
  and the same derivation applied to the full city must give exactly `GOLDEN`.
"""

from __future__ import annotations

import importlib.util
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import Any, Final

import httpx
import pytest

from chhatri.api.app import create_app
from chhatri.api.demo import FLOWS, GOLDEN, CheckRow, DemoApi, DemoNumbers, compare, expectations, rehearse
from chhatri.api.demo.local import in_process_client, offline_settings
from chhatri.clock import at
from chhatri.config import BACKEND_DIR
from chhatri.detect.triggers import evaluate_hour
from chhatri.policy.engine import area_amount, personal_amount, publish_expected_day
from chhatri.replay.state import AppState
from chhatri.replay.static import StaticContext, load_static
from chhatri.replay.world import ScenarioData, build_world
from tests.replay import small_world
from tests.replay.helpers import make_static
from tests.replay.helpers import offline_settings as replay_settings

ANIL: Final = "S-0142"
MONSOON_DAY: Final = date(2025, 8, 19)
SILENT_DAY: Final = date(2025, 8, 20)  # SPEC §17.2 illness: Anil silent all of Wed 2025-08-20
BUY_COVER_DAY: Final = date(2025, 8, 18)
TRIGGER_HOUR: Final = 17
MAP_ZONES: Final = ("Z3", "Z7", "Z9", "Z12")
TIMEOUT_S: Final = 120.0
BASE_URL: Final = "http://demo-flows.test"
DEMO_CHECK: Final = BACKEND_DIR / "scripts" / "demo_check.py"


# ------------------------------------------------------------------------------------ numbers


def _monsoon_numbers(static: StaticContext, world: ScenarioData) -> dict[str, Any]:
    """Zone indices, shop counts and money of the 17:00 trigger, from the data and policy alone."""
    city, rules = static.city, static.rules
    fired = at(MONSOON_DAY, TRIGGER_HOUR)
    window = rules.area.consecutive_hours * timedelta(hours=1)
    alerts = world.shocks.alerts_between(fired - window, fired)
    triggers, states = evaluate_hour(
        fired, city, world.visible(fired), world.p50, alerts, world.lower_bounds, rules, frozenset()
    )
    index = {t.zone_id: t.index_pct for t in triggers}
    paid: dict[str, int] = {}
    for trigger in triggers:
        for merchant in city.merchants_in_zone(trigger.zone_id):
            if merchant.id in city.covers:
                expected = publish_expected_day(world.expected_day_paise(city.row(merchant.id), MONSOON_DAY))
                paid[merchant.id] = area_amount(expected, trigger.drop_pct, rules)[0]
    anil_expected = publish_expected_day(world.expected_day_paise(city.row(ANIL), MONSOON_DAY))
    return {
        "zone_index": MappingProxyType(index),
        "z9_index": states["Z9"].index_pct,
        "shops_paid": len(paid),
        "anil_expected_paise": anil_expected,
        "anil_payout_paise": paid[ANIL],
        "z7_total_paise": sum(v for mid, v in paid.items() if city.merchant(mid).zone_id == "Z7"),
    }


def derive_numbers(static: StaticContext) -> DemoNumbers:
    """The story's free numbers for `static`, computed without the replay's orchestrator."""
    city, rules = static.city, static.rules
    illness = build_world(static, "illness")
    assert static.model is not None
    wednesday = static.model.day_range_paise(city, illness.history, ANIL, SILENT_DAY)[1]
    shops = {z: sum(city.merchant(mid).zone_id == z for mid in city.covers) for z in MAP_ZONES}
    return DemoNumbers(
        **_monsoon_numbers(static, build_world(static, "monsoon")),
        zone_shops=MappingProxyType(shops),
        instalment_paise=city.loans[ANIL].daily_instalment_paise,
        personal_paise=personal_amount(publish_expected_day(wednesday), 1, rules)[0],
        cover_starts_on=BUY_COVER_DAY + timedelta(days=rules.cover.waiting_period_days),
    )


# ----------------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="session")
def small_static(tmp_path_factory: pytest.TempPathFactory) -> StaticContext:
    var_dir = tmp_path_factory.mktemp("demo-flows")
    settings = replay_settings(var_dir, chhatri_demo_mode=True)
    return make_static(settings, small_world.small_city(), small_world.small_model(), var_dir / "artifacts")


@pytest.fixture(scope="session")
def small_numbers(small_static: StaticContext) -> DemoNumbers:
    return derive_numbers(small_static)


@asynccontextmanager
async def small_client(static: StaticContext) -> AsyncIterator[httpx.AsyncClient]:
    """The real app on a real AppState of the small city (nothing loaded until a flow loads)."""
    app = create_app(static.settings, state=AppState(static))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=BASE_URL, timeout=TIMEOUT_S
        ) as client,
    ):
        yield client


def problems(rows: tuple[CheckRow, ...]) -> list[str]:
    return [
        f"{r.scenario} / {r.check}: expected {r.expected!r}, got {r.actual!r}"
        for r in rows
        if r.status != "PASS"
    ]


def only(expected: Mapping[str, Mapping[str, Any]], scenario: str) -> Mapping[str, Mapping[str, Any]]:
    return {scenario: expected[scenario]}


# --------------------------------------------------------------------------------- fast suite


def test_small_city_numbers_have_the_story_shape(small_numbers: DemoNumbers) -> None:
    """The small city tells the same story: three zones trigger, Z9 is a slow day, Anil is capped."""
    assert set(small_numbers.zone_index) == {"Z3", "Z7", "Z12"}
    assert small_numbers.z9_index is not None and small_numbers.z9_index >= 50
    assert small_numbers.anil_payout_paise > 0 and small_numbers.personal_paise == 150_000
    assert small_numbers.shops_paid == sum(small_numbers.zone_shops[z] for z in ("Z3", "Z7", "Z12"))


@pytest.mark.parametrize("scenario", tuple(FLOWS))
async def test_small_city_demo_flow_over_http(
    scenario: str, small_static: StaticContext, small_numbers: DemoNumbers
) -> None:
    expected = only(expectations(small_numbers), scenario)
    async with small_client(small_static) as client:
        runs = await rehearse(DemoApi(client), {scenario: FLOWS[scenario]})
    rows = compare(runs, expected)
    assert runs[0].error is None, runs[0].error
    assert len(rows) == len(expected[scenario])
    assert problems(rows) == []


# ----------------------------------------------------------------------- demo_check.py script


def load_demo_check() -> ModuleType:
    spec = importlib.util.spec_from_file_location("demo_check_under_test", DEMO_CHECK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(("numbers_are_golden", "exit_code"), [(False, 0), (True, 1)])
async def test_demo_check_script_passes_only_when_every_number_matches(
    numbers_are_golden: bool,
    exit_code: int,
    small_static: StaticContext,
    small_numbers: DemoNumbers,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = load_demo_check()

    @asynccontextmanager
    async def fake_in_process(settings: object, *, timeout_s: float) -> AsyncIterator[httpx.AsyncClient]:
        async with small_client(small_static) as client:
            yield client

    monkeypatch.setattr(script, "in_process_client", fake_in_process)
    monkeypatch.setattr(script, "GOLDEN", GOLDEN if numbers_are_golden else small_numbers)
    assert await script.run(script.parse_args([])) == exit_code
    table = capsys.readouterr().out.splitlines()
    assert table[0].split() == ["result", "scenario", "check", "value"]
    assert table[-1].startswith("PASS: " if exit_code == 0 else "FAIL: ")


def test_demo_check_script_rejects_a_bad_timeout(capsys: pytest.CaptureFixture[str]) -> None:
    script = load_demo_check()
    with pytest.raises(SystemExit) as stopped:
        script.parse_args(["--timeout", "0"])
    assert stopped.value.code == 2
    assert "--timeout must be positive" in capsys.readouterr().err


# ------------------------------------------------------------------------ slow: full artefacts


@pytest.fixture(scope="module")
def full_static(tmp_path_factory: pytest.TempPathFactory) -> StaticContext:
    return load_static(offline_settings(chhatri_var_dir=tmp_path_factory.mktemp("demo-flows-full")))


@pytest.mark.slow
def test_full_artefacts_derive_exactly_the_golden_numbers(full_static: StaticContext) -> None:
    assert derive_numbers(full_static) == GOLDEN


@pytest.mark.slow
async def test_full_demo_matches_every_golden_number(tmp_path: Path) -> None:
    settings = offline_settings(chhatri_var_dir=tmp_path)
    async with in_process_client(settings, timeout_s=TIMEOUT_S) as client:
        runs = await rehearse(DemoApi(client))
    rows = compare(runs, expectations(GOLDEN))
    assert [run.scenario for run in runs] == list(FLOWS)
    assert [run.error for run in runs] == [None] * len(FLOWS)
    assert len(rows) == sum(len(checks) for checks in expectations(GOLDEN).values())
    assert problems(rows) == []


@pytest.mark.slow
def test_demo_check_script_exits_0_on_the_full_artefacts(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CHHATRI_VAR_DIR", str(tmp_path))
    script = load_demo_check()
    assert script.main(["--json"]) == 0, capsys.readouterr().out[-2000:]
    assert '"passed": true' in capsys.readouterr().out
