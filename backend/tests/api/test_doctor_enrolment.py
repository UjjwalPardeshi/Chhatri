"""The officer's doctor enrolment links (design 2.9): POST /api/doctors/enrolment-links and …/enrolment-link/reset.

A real AppState whose integrations use a local desk and local chat bindings, so nothing leaks into the process-wide ones.
"""

from __future__ import annotations

import logging
import re
from functools import partial
from typing import Any, Final

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from chhatri.api.app import create_app
from chhatri.events import EventBus
from chhatri.integrations.registry import build_integrations
from chhatri.integrations.switch import PROCESS_SWITCH
from chhatri.replay.state import AppState
from chhatri.replay.static import StaticContext
from chhatri.store.doctor_chats import DoctorDesk
from chhatri.store.telegram_bindings import TelegramBindings
from tests.api.helpers import error_of
from tests.replay.helpers import OFFICER_TOKEN

BASE: Final = "http://testserver"
LINKS: Final = "/api/doctors/enrolment-links"
RAO: Final = "MMC-2011-45817"
RESET: Final = f"/api/doctors/{RAO}/enrolment-link/reset"
OFFICER: Final = {"Authorization": f"Bearer {OFFICER_TOKEN}"}
FLAG: Final = "telegram_channel"
BOT: Final = "chaatri_paytm_bot"
LINK: Final = re.compile(rf"^https://t\.me/{BOT}\?start=(DOC-[0-9A-F]{{16}})$")
ITEM_KEYS: Final = {
    "registration_no",
    "doctor_name",
    "hospital_id",
    "hospital_name",
    "enrolled",
    "deep_link",
    "answers",
}


class Rig:
    def __init__(self, static: StaticContext) -> None:
        self.desk = DoctorDesk()
        self.bindings = TelegramBindings()
        factory = partial(build_integrations, telegram_bindings=self.bindings, doctor_desk=self.desk)
        self.state = AppState(static, bus=EventBus(history_size=5000), integrations_factory=factory)

    def app(self, features: str = FLAG) -> FastAPI:
        settings = self.state.static.settings.model_copy(update={"chhatri_features": features})
        return create_app(settings, state=self.state)

    def audits(self, action: str) -> list[Any]:
        return [e for e in self.state.runtime.audit.entries(after=0, limit=5000) if e.action == action]


async def call(app: FastAPI, method: str, path: str, **kwargs: Any) -> Any:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE, timeout=30.0) as http:
        return await http.request(method, path, **kwargs)


@pytest.fixture(autouse=True)
def _clean_switch() -> Any:
    PROCESS_SWITCH.clear()
    yield
    PROCESS_SWITCH.clear()


@pytest.fixture
async def rig(real_static: StaticContext) -> Rig:
    rig = Rig(real_static)
    await rig.state.load("monsoon")
    return rig


async def test_flag_off_is_404_before_the_token_is_asked(rig: Rig) -> None:
    app = rig.app(features="")
    error_of(await call(app, "POST", LINKS, json={}), 404, "not_found")
    error_of(await call(app, "POST", RESET, json={}, headers=OFFICER), 404, "not_found")


async def test_the_links_need_the_officer_token(rig: Rig) -> None:
    app = rig.app()
    for path in (LINKS, RESET):
        error_of(await call(app, "POST", path, json={}), 401, "unauthorized")
        error_of(
            await call(app, "POST", path, json={}, headers={"Authorization": "Bearer nope"}), 403, "forbidden"
        )
    assert rig.desk.enrolled() == ()


async def test_one_item_per_directory_doctor_rao_first_never_cached(rig: Rig) -> None:
    response = await call(rig.app(), "POST", LINKS, json={}, headers=OFFICER)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    body = response.json()
    items = body["data"]
    assert body["meta"] == {"total": 3, "limit": 3, "offset": 0}
    assert all(set(item) == ITEM_KEYS for item in items)
    assert [item["registration_no"] for item in items][0] == RAO
    assert items[0] | {"deep_link": None} == {
        "registration_no": RAO,
        "doctor_name": "Dr S. Rao",
        "hospital_id": "H-KEM",
        "hospital_name": "KEM Hospital, Parel",
        "enrolled": False,
        "deep_link": None,
        "answers": "SIMULATED",
    }
    assert items[0]["deep_link"] is None  # the bot's username is not known yet


async def test_the_deep_link_carries_the_doctors_token_once_the_bot_is_known(rig: Rig) -> None:
    rig.bindings.set_bot_username(BOT)
    app = rig.app()
    first = (await call(app, "POST", LINKS, json={}, headers=OFFICER)).json()["data"][0]
    match = LINK.match(first["deep_link"])
    assert match is not None and rig.desk.registration_for(match[1]) == RAO
    again = (await call(app, "POST", LINKS, json={}, headers=OFFICER)).json()["data"][0]
    assert again["deep_link"] == first["deep_link"]  # stable within the run


async def test_an_enrolled_doctor_shows_enrolled_and_forced_shows_forced(rig: Rig) -> None:
    rig.desk.enrol(42, RAO)
    app = rig.app()
    item = (await call(app, "POST", LINKS, json={}, headers=OFFICER)).json()["data"][0]
    assert (item["enrolled"], item["answers"]) == (True, "SIMULATED")  # Telegram is not live in tests
    PROCESS_SWITCH.force("doctor")
    item = (await call(app, "POST", LINKS, json={}, headers=OFFICER)).json()["data"][0]
    assert item["answers"] == "FORCED"


async def test_reset_changes_the_link_unenrols_and_is_audited(
    rig: Rig, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    rig.bindings.set_bot_username(BOT)
    app = rig.app()
    before = (await call(app, "POST", LINKS, json={}, headers=OFFICER)).json()["data"][0]["deep_link"]
    rig.desk.enrol(42, RAO)
    response = await call(app, "POST", RESET, json={}, headers=OFFICER)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    item = response.json()["data"]
    assert set(item) == ITEM_KEYS and item["registration_no"] == RAO
    assert item["deep_link"] != before and LINK.match(item["deep_link"])
    assert item["enrolled"] is False and rig.desk.chat_for(RAO) is None
    [entry] = rig.audits("doctor.enrolment_reset")
    assert (entry.actor, entry.subject_type, entry.subject_id, dict(entry.data)) == (
        "officer:officer",
        "doctor",
        RAO,
        {"registration_no": RAO},
    )
    for link in (before, item["deep_link"]):
        token = link.rsplit("=", 1)[1]
        assert token not in caplog.text and token not in repr(entry)


async def test_reset_of_an_unknown_doctor_is_404(rig: Rig) -> None:
    app = rig.app()
    error_of(
        await call(app, "POST", "/api/doctors/MMC-1999-00000/enrolment-link/reset", json={}, headers=OFFICER),
        404,
        "not_found",
    )
    error_of(
        await call(app, "POST", "/api/doctors/bad%20number/enrolment-link/reset", json={}, headers=OFFICER),
        422,
        "validation_error",
    )
