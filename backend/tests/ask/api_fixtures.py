"""Shared app fixtures of the Ask and voice route tests: the real routes over the fake app state and a service rig."""

from __future__ import annotations

from collections.abc import AsyncIterator, Collection
from typing import Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from chhatri.api.app import create_app
from chhatri.api.routers.ask import get_ask_service
from chhatri.api.routers.voice import get_voice_service
from chhatri.ask.ledger import ledger_for
from chhatri.ask.voice import VoiceService
from chhatri.integrations.base import SynthesizedAudio, Transcript
from tests.api.fakes import FakeAppState, make_settings
from tests.ask.fakes import GOOD_REPLY, Rig, ScriptedChat
from tests.ask.test_voice_service import FakeStt, FakeTts

BASE_URL = "http://testserver"
__all__ = ["BASE_URL", "GOOD_REPLY", "Rig", "ScriptedChat", "build_client", "make_voice"]


def make_voice(
    rig: Rig,
    *,
    stt: Any = None,
    tts: Any = None,
    live: Collection[str] = (),
    gate: bool = True,
    forced: Collection[str] = (),
) -> VoiceService:
    """A voice service that shares the rig's ids, audit and clock (so an stt id is known to the Ask service)."""
    media: dict[str, tuple[bytes, str]] = {}
    return VoiceService(
        stt=stt or FakeStt(Transcript("", None, 0.0, "simulated")),
        tts=tts or FakeTts(SynthesizedAudio(None, None, "simulated")),
        live=lambda: set(live),
        gate=lambda _name: gate,
        forced=lambda: set(forced),
        put_media=lambda data, mime, media_id: media.__setitem__(media_id, (data, mime)),
        ids=rig.ids,
        audit=rig.audit,
        clock=rig.clock,
        ledger=ledger_for(rig.ids),
        stt_model="saaras:v3",
        tts_model="bulbul:v3",
    )


async def build_client(
    rig: Rig | None,
    voice: VoiceService | None,
    *,
    features: str,
    load: bool = True,
) -> AsyncIterator[AsyncClient]:
    state = FakeAppState(make_settings(chhatri_features=features))
    app: FastAPI = create_app(state.static.settings, state=state)
    if rig is not None:
        app.dependency_overrides[get_ask_service] = lambda: rig.service
    if voice is not None:
        app.dependency_overrides[get_voice_service] = lambda: voice
    if load:
        await state.load("monsoon")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as http:
        yield http
