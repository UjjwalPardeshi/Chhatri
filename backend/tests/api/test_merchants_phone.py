"""Merchant routes and the phone simulator (SPEC §19, §13, §20)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from chhatri.api.schemas import MerchantDetail, MerchantSummary, Message
from chhatri.config import DATA_DIR
from chhatri.integrations.demo_voice import DEMO_UTTERANCES, demo_key_of
from tests.api import media_samples as media
from tests.api.fakes import FakeAppState
from tests.api.helpers import data_of, error_of, list_of


async def test_list_merchants_with_paging(client: AsyncClient) -> None:
    items, meta = list_of(await client.get("/api/merchants"), MerchantSummary)
    assert [m.id for m in items] == ["S-0142", "S-0907", "S-0311"]
    assert (meta.total, meta.limit, meta.offset) == (3, 50, 0)
    page, meta = list_of(await client.get("/api/merchants?limit=1&offset=1"), MerchantSummary)
    assert [m.id for m in page] == ["S-0907"]
    assert (meta.total, meta.limit, meta.offset) == (3, 1, 1)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("zone_id=Z7", ["S-0142"]),
        ("q=ANIL", ["S-0142"]),
        ("q=kirana", ["S-0907"]),
        ("q=s-0311", ["S-0311"]),
        ("zone_id=Z3&q=anil", []),
    ],
)
async def test_list_merchants_filters(client: AsyncClient, query: str, expected: list[str]) -> None:
    items, meta = list_of(await client.get(f"/api/merchants?{query}"), MerchantSummary)
    assert [m.id for m in items] == expected
    assert meta.total == len(expected)


@pytest.mark.parametrize("query", ["zone_id=7", "limit=0", "limit=501", "offset=-1", "q=" + "x" * 65])
async def test_list_merchants_validates_query(client: AsyncClient, query: str) -> None:
    error_of(await client.get(f"/api/merchants?{query}"), 422, "validation_error")


async def test_merchant_detail(client: AsyncClient) -> None:
    detail = data_of(await client.get("/api/merchants/S-0142"), MerchantDetail)
    assert (detail.owner_name_hi, detail.expected_today_label) == ("अनिल", "₹4,380")
    assert [p.amount_label for p in detail.payouts] == ["₹1,380"]


async def test_unknown_and_malformed_merchant_ids(client: AsyncClient) -> None:
    error_of(await client.get("/api/merchants/S-9999"), 404, "not_found")
    error_of(await client.get("/api/merchants/anil"), 422, "validation_error")
    error_of(await client.post("/api/merchants/S-9999/messages", json={"text": "hi"}), 404, "not_found")


async def test_text_message_goes_to_the_conversation(client: AsyncClient, fake_state: FakeAppState) -> None:
    items, meta = list_of(
        await client.post("/api/merchants/S-0142/messages", json={"text": "  मुझे इतने ही पैसे क्यों मिले?  "}),
        Message,
    )
    assert [(m.direction, m.kind) for m in items] == [("INBOUND", "TEXT"), ("OUTBOUND", "TEXT")]
    assert fake_state.runtime.conversation.calls == [("text", ("S-0142", "मुझे इतने ही पैसे क्यों मिले?"))]
    history, meta = list_of(await client.get("/api/merchants/S-0142/messages?limit=1&offset=1"), Message)
    assert [m.id for m in history] == [items[1].id]
    assert (meta.total, meta.limit, meta.offset) == (2, 1, 1)


@pytest.mark.parametrize(
    "body", [{"text": ""}, {"text": "   "}, {"text": "x" * 1001}, {}, {"text": "hi", "x": 1}]
)
async def test_text_message_validation(client: AsyncClient, body: dict[str, object]) -> None:
    error_of(await client.post("/api/merchants/S-0142/messages", json=body), 422, "validation_error")


async def test_phone_routes_need_a_scenario(bare_client: AsyncClient) -> None:
    error_of(
        await bare_client.post("/api/merchants/S-0142/messages", json={"text": "hi"}), 409, "no_scenario"
    )


async def test_voice_upload_is_validated_then_transcribed(
    client: AsyncClient, fake_state: FakeAppState
) -> None:
    files = {"file": ("note.ogg", media.ogg_opus_bytes(4), "application/octet-stream")}
    items, _ = list_of(await client.post("/api/merchants/S-0142/voice", files=files), Message)
    assert items[0].kind == "VOICE"
    call = fake_state.runtime.conversation.calls[-1]
    assert call[0] == "voice" and call[1][2] == "audio/ogg" and call[1][3] is None


@pytest.mark.parametrize(
    ("payload", "status", "code"),
    [
        (media.ogg_opus_bytes(45), 413, "payload_too_large"),
        (b"MZ\x90\x00 not audio", 415, "unsupported_media_type"),
        (b"OggS" + b"\x00" * (5 * 1024 * 1024), 413, "payload_too_large"),
    ],
    ids=["too-long", "not-audio", "too-big"],
)
async def test_voice_upload_rejections(client: AsyncClient, payload: bytes, status: int, code: str) -> None:
    files = {"file": ("note.ogg", payload, "audio/ogg")}
    error_of(await client.post("/api/merchants/S-0142/voice", files=files), status, code)


async def test_voice_upload_needs_a_file(client: AsyncClient) -> None:
    error = error_of(
        await client.post("/api/merchants/S-0142/voice", data={"x": "1"}), 422, "validation_error"
    )
    assert set(error.fields) == {"file"}


@pytest.mark.parametrize("key", ["why", "dispute", "ill", "cover"])
async def test_voice_demo_sends_the_canned_note(
    client: AsyncClient, fake_state: FakeAppState, key: str
) -> None:
    items, _ = list_of(await client.post("/api/merchants/S-0142/voice-demo", json={"key": key}), Message)
    assert items[0].meta.transcript == DEMO_UTTERANCES[key].transcript
    _, (merchant_id, audio, mime, hint) = fake_state.runtime.conversation.calls[-1]
    assert (merchant_id, demo_key_of(audio), mime, hint) == (
        "S-0142",
        key,
        "audio/wav",
        DEMO_UTTERANCES[key].transcript,
    )


async def test_voice_demo_rejects_unknown_keys(client: AsyncClient) -> None:
    error_of(
        await client.post("/api/merchants/S-0142/voice-demo", json={"key": "sing"}), 422, "validation_error"
    )


async def test_photo_upload_is_stored_and_served(client: AsyncClient, fake_state: FakeAppState) -> None:
    png = media.image_bytes("PNG")
    files = {"file": ("slip.jpg", png, "image/jpeg")}
    items, _ = list_of(await client.post("/api/merchants/S-0142/photo", files=files), Message)
    assert items[0].media_url == "/api/media/MD-000001"
    assert fake_state.runtime.conversation.calls[-1][1][2:] == ("image/png", "MD-000001")
    served = await client.get("/api/media/MD-000001")
    assert served.status_code == 200 and served.content == png
    assert (served.headers["content-type"], served.headers["cache-control"]) == ("image/png", "no-store")
    assert served.headers["x-content-type-options"] == "nosniff"


async def test_photo_sample_by_name(client: AsyncClient, fake_state: FakeAppState) -> None:
    response = await client.post(
        "/api/merchants/S-0142/photo", json={"sample": "mismatch_admission_slip.png"}
    )
    list_of(response, Message)
    sent = fake_state.runtime.conversation.calls[-1][1][1]
    assert sent == (DATA_DIR / "slips" / "mismatch_admission_slip.png").read_bytes()


async def test_photo_without_sample_uses_the_scenarios_slip(
    client: AsyncClient, fake_state: FakeAppState
) -> None:
    await client.post("/api/replay/load", json={"scenario": "illness"})
    list_of(await client.post("/api/merchants/S-0142/photo", json={}), Message)
    sent = fake_state.runtime.conversation.calls[-1][1][1]
    assert sent == (DATA_DIR / "slips" / "anil_admission_slip.png").read_bytes()


@pytest.mark.parametrize(
    ("kwargs", "status", "code"),
    [
        ({"json": {}}, 422, "validation_error"),
        ({"json": {"sample": "nope.png"}}, 404, "not_found"),
        ({"json": {"sample": "../config.png"}}, 422, "validation_error"),
        ({"content": b"{bad", "headers": {"Content-Type": "application/json"}}, 422, "validation_error"),
        ({"content": b"raw", "headers": {"Content-Type": "image/png"}}, 415, "unsupported_media_type"),
        ({"files": {"other": ("a.png", b"x", "image/png")}}, 422, "validation_error"),
        ({"files": {"file": ("a.png", b"GIF89a....", "image/png")}}, 415, "unsupported_media_type"),
    ],
)
async def test_photo_rejections(
    client: AsyncClient, kwargs: dict[str, object], status: int, code: str
) -> None:
    error_of(await client.post("/api/merchants/S-0142/photo", **kwargs), status, code)  # type: ignore[arg-type]


async def test_unknown_and_malformed_media(client: AsyncClient) -> None:
    error_of(await client.get("/api/media/MD-999999"), 404, "not_found")
    error_of(await client.get("/api/media/../../etc"), 404, "not_found")
    error_of(await client.get("/api/media/secret"), 422, "validation_error")


async def test_message_rate_limit(client: AsyncClient) -> None:
    for _ in range(60):
        assert (await client.post("/api/merchants/S-0142/voice-demo", json={"key": "why"})).status_code == 200
    limited = await client.post("/api/merchants/S-0142/messages", json={"text": "hi"})
    error_of(limited, 429, "rate_limited")
    assert 1 <= int(limited.headers["retry-after"]) <= 60


async def test_upload_rate_limit(client: AsyncClient) -> None:
    for _ in range(20):
        await client.post("/api/merchants/S-0142/photo", json={"sample": "anil_admission_slip.png"})
    error_of(
        await client.post("/api/merchants/S-0142/voice", files={"file": ("a", b"x")}), 429, "rate_limited"
    )
