"""The two slip pre-check routes on the real app (data-model 5.3, fs-02 section 8; AC-SLIP-01 to 05, 09)."""

from __future__ import annotations

import io
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Final

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from PIL import Image

from chhatri.api.app import create_app
from chhatri.config import DATA_DIR
from chhatri.events import EventBus
from chhatri.replay.state import AppState
from tests.api.helpers import error_of
from tests.api.rights_rig import check_schema
from tests.replay import small_world
from tests.replay.helpers import make_static, offline_settings

ANIL: Final = "S-0142"
FLAG: Final = "n3_slip_precheck"
URL: Final = f"/api/merchants/{ANIL}/slip-precheck"
SAMPLE: Final = {"sample": "anil_admission_slip.png"}


def sample(name: str) -> bytes:
    return (DATA_DIR / "slips" / name).read_bytes()


@pytest.fixture
def make_client(tmp_path_factory: pytest.TempPathFactory):
    async def build(features: str, **settings: Any) -> tuple[FastAPI, AsyncClient]:
        var_dir: Path = tmp_path_factory.mktemp("precheck-api")
        static = make_static(
            offline_settings(var_dir, chhatri_features=features, **settings),
            small_world.small_city(),
            small_world.small_model(),
            var_dir / "artifacts",
        )
        app = create_app(static.settings, state=AppState(static, bus=EventBus(history_size=50_000)))
        return app, AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            timeout=60.0,
            event_hooks={"response": [check_schema]},
        )

    return build


async def started(
    make_client, features: str = FLAG, scenario: str = "illness", at: str = "11:21"
) -> AsyncIterator[AsyncClient]:
    app, http = await make_client(features)
    async with app.router.lifespan_context(app), http:
        assert (await http.post("/api/replay/load", json={"scenario": scenario})).status_code == 200
        assert (await http.post("/api/replay/seek", json={"to": at})).status_code == 200
        yield http


@pytest.fixture
async def client(make_client) -> AsyncIterator[AsyncClient]:
    async for http in started(make_client):
        yield http


@pytest.fixture
async def flag_off(make_client) -> AsyncIterator[AsyncClient]:
    async for http in started(make_client, features=""):
        yield http


def data(response) -> dict[str, Any]:  # noqa: ANN001
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    return body["data"]


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(out, format="PNG")
    return out.getvalue()


# ------------------------------------------------------------------------------------------------ flag off


async def test_both_routes_answer_the_ordinary_404_while_the_flag_is_off(flag_off: AsyncClient) -> None:
    assert error_of(await flag_off.post(URL, json=SAMPLE), 404, "not_found").message == "not found"
    error_of(await flag_off.post(f"{URL}/PC-000001/confirm", json={"action": "CONFIRM"}), 404, "not_found")


async def test_the_photo_route_still_decides_in_one_step_while_the_flag_is_off(flag_off: AsyncClient) -> None:
    messages = (await flag_off.post(f"/api/merchants/{ANIL}/photo", json={})).json()["data"]
    assert [m["kind"] for m in messages] == ["IMAGE"]  # APPROVED: no reply until credit time
    detail = (await flag_off.get(f"/api/merchants/{ANIL}")).json()["data"]
    assert detail["decisions"][0]["outcome"] == "APPROVED"


# ------------------------------------------------------------------------------------------------ read


async def test_a_sample_is_read_ready_with_the_contract_shape(client: AsyncClient) -> None:
    body = data(await client.post(URL, json={**SAMPLE, "lang": "hi"}))
    assert body["precheck_id"] == "PC-000001" and body["merchant_id"] == ANIL
    assert (body["status"], body["attempt"], body["retakes_left"], body["reason"], body["guidance"]) == (
        "READY",
        1,
        2,
        None,
        None,
    )
    assert body["document"] == {"type": "admission_slip", "accepted": True}
    assert body["slots"] == [
        {"key": "patient_name", "value": "Anil R. Jadhav", "state": "READ", "note": None},
        {"key": "admission_date", "value": "2025-08-20", "state": "READ", "note": None},
        {"key": "discharge_date", "value": None, "state": "NOT_ON_SLIP", "note": None},
        {"key": "hospital_name", "value": "KEM Hospital, Parel", "state": "READ", "note": None},
    ]
    assert body["checklist"] == [
        {"id": "photo_readable", "state": "PASS"},
        {"id": "name_on_slip", "state": "PASS"},
        {"id": "dates_on_slip", "state": "PASS"},
    ]
    assert body["gate"] == {"passed": True, "confidence": 0.94, "minimum": 0.8}
    assert body["next_action"] == {
        "kind": "CONFIRM_FIELDS",
        "label_hi": "हाँ, सही है",
        "label_en": "Yes, this is right",
    }
    assert (body["mode"], body["provider"], body["model"], body["fallback_reason"], body["attempts"]) == (
        "SIMULATED",
        "simulated",
        None,
        "NO_KEY",
        [],
    )
    source = body["source"]
    assert (source["kind"], source["ref"], source["origin"], source["clause"]) == (
        "SLIP",
        f"slip:{body['media_id']}",
        "SIMULATED",
        "C3",
    )
    assert (
        await client.get(f"/api/media/{body['media_id']}")
    ).status_code == 200  # the stored (cleaned) copy


async def test_the_scenarios_own_sample_is_used_for_an_empty_body(client: AsyncClient) -> None:
    assert data(await client.post(URL, json={}))["status"] == "READY"


async def test_a_blurry_slip_is_a_retake_with_one_reason(client: AsyncClient) -> None:
    body = data(await client.post(URL, json={"sample": "blurry_slip.png"}))
    assert (body["status"], body["reason"]) == ("RETAKE", "LOW_CONFIDENCE")
    assert body["document"] == {"type": None, "accepted": False}
    assert body["gate"] == {"passed": False, "confidence": 0.22, "minimum": 0.8}
    assert [s["state"] for s in body["slots"]] == ["MISSING", "MISSING", "NOT_ON_SLIP", "NOT_ON_SLIP"]
    assert [c["state"] for c in body["checklist"]] == ["WARN", "WARN", "WARN"]
    assert body["guidance"]["key"] == "SLIP_RETAKE_CLEAR" and body["guidance"]["text_en"].startswith(
        "The photo is not clear."
    )
    assert body["next_action"]["kind"] == "RETAKE_PHOTO" and body["source"] is not None


async def test_an_upload_is_read_the_same_way(client: AsyncClient) -> None:
    files = {"file": ("slip.png", sample("anil_admission_slip.png"), "image/png")}
    assert data(await client.post(URL, files=files, data={"lang": "en"}))["status"] == "READY"


@pytest.mark.parametrize(
    ("kwargs", "status", "code"),
    [
        ({"json": {"sample": "nope.png"}}, 404, "not_found"),
        ({"json": {"sample": "../x.png"}}, 422, "validation_error"),
        ({"json": {"lang": "fr"}}, 422, "validation_error"),
        ({"json": {"extra": 1}}, 422, "validation_error"),
        ({"files": {"file": ("a.txt", b"hello", "text/plain")}}, 415, "unsupported_media_type"),
        (
            {"files": {"file": ("a.png", b"\x89PNG\r\n\x1a\nbroken", "image/png")}},
            415,
            "unsupported_media_type",
        ),
        (
            {"files": {"file": ("a.png", b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024), "image/jpeg")}},
            413,
            "payload_too_large",
        ),
        ({"files": {"other": ("a.png", b"x", "image/png")}}, 422, "validation_error"),
        ({"data": {"lang": "fr"}, "files": {"file": ("a.png", b"x", "image/png")}}, 422, "validation_error"),
        ({"content": b"x", "headers": {"content-type": "text/plain"}}, 415, "unsupported_media_type"),
    ],
)
async def test_bad_requests_get_clean_errors(
    client: AsyncClient, kwargs: dict[str, Any], status: int, code: str
) -> None:
    error_of(await client.post(URL, **kwargs), status, code)


async def test_unknown_and_malformed_merchants(client: AsyncClient) -> None:
    error_of(await client.post("/api/merchants/S-9999/slip-precheck", json=SAMPLE), 404, "not_found")
    error_of(await client.post("/api/merchants/S-12/slip-precheck", json=SAMPLE), 422, "validation_error")


async def test_no_open_check_in_is_a_409_and_nothing_is_stored(make_client) -> None:
    async for http in started(make_client, at="11:19"):
        error_of(await http.post(URL, json=SAMPLE), 409, "conflict")
        assert (await http.get("/api/media/MD-000001")).status_code == 404


async def test_the_photo_limit_is_a_409(client: AsyncClient) -> None:
    for _ in range(3):
        data(await client.post(URL, json={"sample": "blurry_slip.png"}))
    error_of(await client.post(URL, json={"sample": "blurry_slip.png"}), 409, "conflict")


async def test_the_uploads_rate_limit_applies(client: AsyncClient) -> None:
    codes = {(await client.post(URL, json={"sample": "../x.png"})).status_code for _ in range(25)}
    assert 429 in codes


# ------------------------------------------------------------------------------------------------ confirm


async def test_confirm_files_the_claim_and_the_engine_decides(client: AsyncClient) -> None:
    pc = data(await client.post(URL, json=SAMPLE))
    body = data(await client.post(f"{URL}/{pc['precheck_id']}/confirm", json={"action": "CONFIRM"}))
    assert body["precheck_id"] == pc["precheck_id"] and body["status"] == "CONFIRMED"
    assert (body["confirmed_as"], body["outcome"], body["case_id"], body["messages"]) == (
        "FIELDS_CONFIRMED",
        "APPROVED",
        None,
        [],
    )
    assert body["claim_id"].startswith("CL-") and body["decision_id"].startswith("D-")
    decision = data(await client.get(f"/api/decisions/{body['decision_id']}"))
    assert decision["outcome"] == "APPROVED" and decision["amount_paise"] == 150_000
    error_of(
        await client.post(f"{URL}/{pc['precheck_id']}/confirm", json={"action": "CONFIRM"}), 409, "conflict"
    )
    error_of(await client.post(URL, json=SAMPLE), 409, "conflict")


async def test_a_blurry_slip_sent_to_the_team_is_referred_with_a_case(client: AsyncClient) -> None:
    pc = data(await client.post(URL, json={"sample": "blurry_slip.png"}))
    body = data(await client.post(f"{URL}/{pc['precheck_id']}/confirm", json={"action": "SEND_TO_TEAM"}))
    assert (body["confirmed_as"], body["outcome"], body["case_id"]) == ("SENT_TO_TEAM", "REFERRED", "C-2291")
    assert [m["kind"] for m in body["messages"]] == ["TEXT", "CASE_CHIP"] and body["messages"][1]["meta"][
        "case_id"
    ] == "C-2291"


@pytest.mark.parametrize(
    ("first", "action"),
    [("anil_admission_slip.png", "SEND_TO_TEAM"), ("blurry_slip.png", "CONFIRM")],
)
async def test_the_wrong_action_for_the_status_is_a_409(client: AsyncClient, first: str, action: str) -> None:
    pc = data(await client.post(URL, json={"sample": first}))
    error_of(
        await client.post(f"{URL}/{pc['precheck_id']}/confirm", json={"action": action}), 409, "conflict"
    )


async def test_a_superseded_pre_check_cannot_be_confirmed(client: AsyncClient) -> None:
    old = data(await client.post(URL, json={"sample": "blurry_slip.png"}))
    data(await client.post(URL, json=SAMPLE))
    error_of(
        await client.post(f"{URL}/{old['precheck_id']}/confirm", json={"action": "SEND_TO_TEAM"}),
        409,
        "conflict",
    )


@pytest.mark.parametrize(
    ("path", "body", "status", "code"),
    [
        ("PC-000099", {"action": "CONFIRM"}, 404, "not_found"),
        ("PC-000001", {"action": "APPROVE"}, 422, "validation_error"),
        ("PC-000001", {}, 422, "validation_error"),
        ("PC-1", {"action": "CONFIRM"}, 422, "validation_error"),
    ],
)
async def test_confirm_errors(
    client: AsyncClient, path: str, body: dict[str, Any], status: int, code: str
) -> None:
    data(await client.post(URL, json=SAMPLE))
    error_of(await client.post(f"{URL}/{path}/confirm", json=body), status, code)


async def test_a_pre_check_of_another_merchant_is_not_found(client: AsyncClient) -> None:
    pc = data(await client.post(URL, json=SAMPLE))
    other = (await client.get("/api/merchants?zone_id=Z7")).json()["data"]
    other_id = next(m["id"] for m in other if m["id"] != ANIL)
    error_of(
        await client.post(
            f"/api/merchants/{other_id}/slip-precheck/{pc['precheck_id']}/confirm", json={"action": "CONFIRM"}
        ),
        404,
        "not_found",
    )


# ------------------------------------------------------------------------------------------------ chat and reset


async def test_the_photo_route_goes_through_the_pre_check_while_the_flag_is_on(client: AsyncClient) -> None:
    messages = data_list(await client.post(f"/api/merchants/{ANIL}/photo", json={}))
    card = messages[-1]
    assert card["card"]["status"] == "READY" and card["meta"]["precheck_id"] == "PC-000001"
    detail = (await client.get(f"/api/merchants/{ANIL}")).json()["data"]
    assert detail["decisions"] == []  # nothing is decided until the merchant confirms
    confirmed = data(await client.post(f"{URL}/PC-000001/confirm", json={"action": "CONFIRM"}))
    assert confirmed["outcome"] == "APPROVED"


async def test_a_scenario_reload_clears_the_pre_checks_and_restarts_the_ids(client: AsyncClient) -> None:
    assert data(await client.post(URL, json=SAMPLE))["precheck_id"] == "PC-000001"
    await client.post("/api/replay/load", json={"scenario": "illness"})
    await client.post("/api/replay/seek", json={"to": "11:21"})
    assert data(await client.post(URL, json=SAMPLE))["precheck_id"] == "PC-000001"
    error_of(await client.post(f"{URL}/PC-000002/confirm", json={"action": "CONFIRM"}), 404, "not_found")


def data_list(response) -> list[dict[str, Any]]:  # noqa: ANN001
    assert response.status_code == 200, response.text
    return response.json()["data"]
