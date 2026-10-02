"""H24 over HTTP: `POST /api/whatif/area` (data-model-and-api section 5.9). The flag, the errors, the limit.

The numbers and rules of the recompute are in tests/replay/test_whatif.py; this file holds the route to them:
absent while `h24_whatif` is off, the §19 error envelope for every bad input, a rate-limit group of its own,
and the promise that a call writes nothing.
"""

from __future__ import annotations

from typing import Any, Final

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from chhatri.api.app import create_app
from chhatri.api.schemas import WhatIfArea, ZonePanel
from chhatri.api.security import RATE_LIMITS, RateLimiter
from chhatri.money import format_inr
from chhatri.replay.state import AppState
from chhatri.replay.static import StaticContext
from chhatri.replay.whatif import NoCompletedWindow
from tests.api.helpers import data_of, error_of
from tests.replay import small_world
from tests.replay.fingerprint import fingerprint
from tests.replay.helpers import ANIL, RAMESH, make_static, offline_settings, run_in_thread

BASE: Final = "http://testserver"
URL: Final = "/api/whatif/area"
STORM: Final = {"alert": "RAIN", "hourly_index_pct": [49, 49, 49]}


@pytest.fixture(scope="module")
def static(tmp_path_factory: pytest.TempPathFactory) -> StaticContext:
    var_dir = tmp_path_factory.mktemp("whatif-var")
    settings = offline_settings(var_dir, chhatri_features="h24_whatif")
    return make_static(settings, small_world.small_city(), small_world.small_model(), var_dir / "artifacts")


async def _monsoon_1705(static: StaticContext) -> AppState:
    state = AppState(static)
    rt = await state.load("monsoon")
    await rt.engine.seek("17:05")
    return state


@pytest.fixture(scope="module")
def state(static: StaticContext) -> AppState:
    return run_in_thread(lambda: _monsoon_1705(static))


def app_for(state: AppState, features: str = "h24_whatif") -> FastAPI:
    settings = state.static.settings.model_copy(update={"chhatri_features": features})
    return create_app(settings, state=state)


async def post(app: FastAPI, body: Any, path: str = URL) -> Response:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as http:
        if isinstance(body, bytes):
            return await http.post(path, content=body, headers={"Content-Type": "application/json"})
        return await http.post(path, json=body)


async def test_the_route_is_absent_while_the_flag_is_off(state: AppState, static: StaticContext) -> None:
    """A valid body, a body that would be a 422, and no scenario at all: the flag answers first, always 404."""
    for target in (state, AppState(static)):
        app = app_for(target, features="h8_ops_strip")
        for body in ({"zone_id": "Z9"}, {"zone_id": "nope", "overrides": {"colour": 1}}):
            error_of(await post(app, body), 404, "not_found")


async def test_before_a_scenario_is_409_no_scenario(static: StaticContext) -> None:
    error_of(await post(app_for(AppState(static)), {"zone_id": "Z9"}), 409, "no_scenario")


async def test_it_answers_the_envelope_and_the_schema_without_a_token(state: AppState) -> None:
    response = await post(app_for(state), {"zone_id": "Z9", "overrides": STORM, "example_merchant_id": None})
    view = data_of(response, WhatIfArea)
    assert "authorization" not in response.request.headers
    assert (view.scenario.fires, view.scenario.drop_pct, view.changed) == (
        True,
        51,
        ["alert", "hourly_index_pct"],
    )
    assert view.baseline.fires is False and view.read_only is True and view.stored is False
    bare = data_of(await post(app_for(state), {"zone_id": "Z7"}), WhatIfArea)  # only zone_id is required
    assert bare.changed == [] and bare.baseline == bare.scenario and bare.example is None


async def test_the_baseline_is_what_the_zone_card_shows(state: AppState) -> None:
    """The what-if and `GET /api/zones/{id}` read the same detector: window, status and alert agree."""
    app = app_for(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as http:
        for zone in ("Z3", "Z7", "Z9", "Z12"):
            panel = data_of(await http.get(f"/api/zones/{zone}"), ZonePanel)
            view = data_of(await http.post(URL, json={"zone_id": zone}), WhatIfArea)
            assert view.baseline.window_index_pct == panel.zone.index_pct, zone
            assert view.baseline.status == panel.zone.status, zone
            assert view.baseline.alert_id == (panel.zone.alert.id if panel.zone.alert else None), zone
            assert view.fixed.lower_bound_pct == panel.zone.lower_bound_pct, zone


async def test_an_example_shop_is_priced_over_http(state: AppState) -> None:
    body = {"zone_id": "Z7", "overrides": {"hourly_index_pct": [45, 45, 45]}, "example_merchant_id": ANIL}
    view = data_of(await post(app_for(state), body), WhatIfArea)
    assert view.example is not None and view.example.drop_pct == 55 == view.scenario.drop_pct
    assert (
        view.example.amount_label == format_inr(view.example.amount_paise) and view.example.amount_paise > 0
    )


async def test_an_unknown_zone_is_404_and_a_malformed_one_is_422(state: AppState) -> None:
    app = app_for(state)
    error_of(await post(app, {"zone_id": "Z99"}), 404, "not_found")
    for bad in ("z9", "Q1", "Z", "Z123", "", None, 9):
        error = error_of(await post(app, {"zone_id": bad}), 422, "validation_error")
        assert "zone_id" in (error.fields or {}), bad


BAD_BODIES: Final[list[tuple[dict[str, Any], str]]] = [
    ({"zone_id": "Z9", "colour": "red"}, "colour"),  # unknown key
    ({"zone_id": "Z9", "overrides": {"colour": "red"}}, "overrides.colour"),  # unknown override
    ({"zone_id": "Z9", "overrides": {"alert": "SNOW"}}, "overrides.alert"),
    ({"zone_id": "Z9", "overrides": {"alert": "rain"}}, "overrides.alert"),  # exact names only
    ({"zone_id": "Z9", "overrides": {"hourly_index_pct": [49, 49]}}, "overrides.hourly_index_pct"),
    ({"zone_id": "Z9", "overrides": {"hourly_index_pct": [49, 49, 49, 49]}}, "overrides.hourly_index_pct"),
    ({"zone_id": "Z9", "overrides": {"hourly_index_pct": []}}, "overrides.hourly_index_pct"),
    ({"zone_id": "Z9", "overrides": {"hourly_index_pct": [49] * 13}}, "overrides.hourly_index_pct"),
    ({"zone_id": "Z9", "overrides": {"hourly_index_pct": [-1, 49, 49]}}, "overrides.hourly_index_pct.0"),
    ({"zone_id": "Z9", "overrides": {"hourly_index_pct": [49, 1001, 49]}}, "overrides.hourly_index_pct.1"),
    ({"zone_id": "Z9", "overrides": {"hourly_index_pct": [49, 49, 49.5]}}, "overrides.hourly_index_pct.2"),
    ({"zone_id": "Z9", "overrides": {"hourly_index_pct": ["49", 49, 49]}}, "overrides.hourly_index_pct.0"),
    ({"zone_id": "Z9", "overrides": {"hourly_index_pct": [True, 49, 49]}}, "overrides.hourly_index_pct.0"),
    ({"zone_id": "Z9", "overrides": {"hourly_index_pct": None}}, None),  # null means no override: accepted
    ({"zone_id": "Z9", "overrides": {"shops_in_index": -1}}, "overrides.shops_in_index"),
    ({"zone_id": "Z9", "overrides": {"shops_in_index": 2.5}}, "overrides.shops_in_index"),
    ({"zone_id": "Z9", "overrides": {"shops_in_index": "20"}}, "overrides.shops_in_index"),
    ({"zone_id": "Z9", "overrides": {"already_triggered_today": "yes"}}, "overrides.already_triggered_today"),
    ({"zone_id": "Z9", "overrides": {"already_triggered_today": 1}}, "overrides.already_triggered_today"),
    ({"zone_id": "Z9", "at": "2025-08-19T17:30:00+05:30"}, "at"),  # not an hour boundary
    ({"zone_id": "Z9", "at": "2025-08-19T18:00:00+05:30"}, "at"),  # after the replay clock
    ({"zone_id": "Z9", "at": "2025-08-19T02:00:00+05:30"}, "at"),  # before one whole window
    ({"zone_id": "Z9", "at": "2025-08-19T17:00:00"}, "at"),  # no time zone
    ({"zone_id": "Z9", "at": "noon"}, "at"),
    ({"zone_id": "Z9", "example_merchant_id": RAMESH}, "example_merchant_id"),  # not covered
    ({"zone_id": "Z9", "example_merchant_id": ANIL}, "example_merchant_id"),  # covered, but in Z7
    ({"zone_id": "Z9", "example_merchant_id": "S-12"}, "example_merchant_id"),  # malformed
    ({"zone_id": "Z9", "example_merchant_id": "S-9999"}, "example_merchant_id"),  # unknown
]


@pytest.mark.parametrize(("body", "field"), BAD_BODIES)
async def test_whatif_validation(state: AppState, body: dict[str, Any], field: str | None) -> None:
    """Each bad input is a 422 with its field named and its value never echoed; a null override is no override."""
    response = await post(app_for(state), body)
    if field is None:
        assert response.status_code == 200, response.text
        return
    error = error_of(response, 422, "validation_error")
    assert error.fields is not None and field in error.fields, error.fields


@pytest.mark.parametrize(
    "body",
    [
        {"zone_id": "Z9", "overrides": {"alert": "zzSNOWzz"}},
        {"zone_id": "Z9", "overrides": {"zzcolourzz": 1}},
        {"zone_id": "Z9", "overrides": {"already_triggered_today": "zzyeszz"}},
        {"zone_id": "Z9", "at": "zznoonzz"},
        {"zone_id": "Z9", "example_merchant_id": "S-zz99"},
        {"zone_id": "Z9", "example_merchant_id": "S-9999"},
        {"zone_id": "Zzzz9"},
    ],
)
async def test_bad_values_are_never_echoed(state: AppState, body: dict[str, Any]) -> None:
    response = await post(app_for(state), body)
    assert response.status_code in (404, 422)
    for probe in ("zzSNOWzz", "zzyeszz", "zznoonzz", "S-zz99", "S-9999", "Zzzz9"):
        assert probe not in response.text


@pytest.mark.parametrize("raw", [b"{not json", b"", b"[1, 2]", b'"Z9"'])
async def test_a_body_that_is_not_an_object_is_422(state: AppState, raw: bytes) -> None:
    error_of(await post(app_for(state), raw), 422, "validation_error")


async def test_no_completed_window_is_a_409_conflict(
    state: AppState, monkeypatch: pytest.MonkeyPatch
) -> None:
    def too_early(*args: object, **kwargs: object) -> None:
        raise NoCompletedWindow("no completed 3-hour window yet")

    monkeypatch.setattr("chhatri.api.routers.whatif.what_if", too_early)
    error = error_of(await post(app_for(state), {"zone_id": "Z9"}), 409, "conflict")
    assert error.message == "no completed 3-hour window yet"


async def test_the_wrong_method_is_405_and_the_route_is_in_the_schema(state: AppState) -> None:
    app = app_for(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as http:
        error_of(await http.get(URL), 405, "method_not_allowed")
    assert "post" in app.openapi()["paths"][URL]


async def test_the_whatif_group_has_its_own_limit(state: AppState) -> None:
    """A slider sends many requests: its group limits it, and the other groups are not touched."""
    assert RATE_LIMITS["whatif"] > RATE_LIMITS["messages"]
    app = app_for(state)
    app.state.rate_limiter = RateLimiter({**RATE_LIMITS, "whatif": 3})
    for _ in range(3):
        assert (await post(app, {"zone_id": "Z9"})).status_code == 200
    limited = await post(app, {"zone_id": "Z9"})
    error_of(limited, 429, "rate_limited")
    assert int(limited.headers["retry-after"]) >= 1
    assert app.state.rate_limiter.check("testclient", "messages").allowed  # another group is unaffected


async def test_a_flag_that_is_off_does_not_use_up_the_limit(state: AppState) -> None:
    app = app_for(state, features="")
    app.state.rate_limiter = RateLimiter({**RATE_LIMITS, "whatif": 1})
    for _ in range(3):
        error_of(await post(app, {"zone_id": "Z9"}), 404, "not_found")


async def test_a_call_over_http_writes_nothing(state: AppState) -> None:
    """AC-H24-04: after a burst of calls the audit log, ids, store, feed, event bus and board are as they were."""
    before = fingerprint(state.runtime)
    app = app_for(state)
    bodies = [
        {"zone_id": "Z9", "overrides": STORM},
        {"zone_id": "Z7", "overrides": {"alert": "NONE"}, "example_merchant_id": ANIL},
        {"zone_id": "Z12", "at": "2025-08-19T16:00:00+05:30"},
        {"zone_id": "Z3", "overrides": {"shops_in_index": 0, "already_triggered_today": True}},
        {
            "zone_id": "Z9",
            "overrides": {"hourly_index_pct": [1, 2, 3]},
            "at": "2025-08-19T11:00:00Z",
        },  # 16:30 IST
    ]
    codes = [(await post(app, body)).status_code for body in bodies for _ in range(6)]
    assert codes.count(200) == 24 and codes.count(422) == 6  # the last body is not on the hour in IST
    assert fingerprint(state.runtime) == before
