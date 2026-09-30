"""No response ever contains a configured secret (SPEC §21), except the officer token from /api/session in demo mode."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient, Response

from chhatri.api.app import create_app
from chhatri.replay import views
from tests.api.conftest import signed
from tests.api.fakes import (
    INTERNAL_SECRET,
    OFFICER_TOKEN,
    PAYTM_KEY,
    SECRETS,
    WA_VERIFY_TOKEN,
    FakeAppState,
    make_settings,
)

OFFICER = {"Authorization": f"Bearer {OFFICER_TOKEN}"}
GETS = (
    "/api/health",
    "/api/integrations",
    "/api/preflight",
    "/api/weather/now",
    "/api/geo/zones",
    "/api/geo/hexes",
    "/api/state",
    "/api/zones/Z7",
    "/api/zones/Z99",
    "/api/merchants",
    "/api/merchants/S-0142",
    "/api/merchants/S-0142/messages",
    "/api/cases",
    "/api/cases/C-2291",
    "/api/decisions/D-000001",
    "/api/payouts",
    "/api/audit",
    "/api/audit/verify",
    "/api/policy",
    "/api/backtest",
    "/api/media/MD-000001",
    "/api/nope",
    "/api/stream?last_event_id=x",
    f"/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token={WA_VERIFY_TOKEN}x",
)
POSTS = (
    ("/api/replay/play", {"speed": 6}, {}),
    ("/api/replay/step", {"minutes": "x"}, {}),
    ("/api/merchants/S-0142/messages", {"text": "hi"}, {}),
    ("/api/merchants/S-0142/voice-demo", {"key": "why"}, {}),
    ("/api/merchants/S-0142/photo", {"sample": "anil_admission_slip.png"}, {}),
    ("/api/cases/C-2291/approve", {"note": "ok"}, OFFICER),
    ("/api/cases/C-2291/decline", {}, {"Authorization": f"Bearer {INTERNAL_SECRET}"}),
    ("/api/premium/link", {"merchant_id": "S-0907"}, OFFICER),
    ("/api/webhooks/paytm", {"linkId": "sim-000001", "STATUS": "TXN_SUCCESS", "CHECKSUMHASH": "x"}, {}),
    ("/internal/workflows/execute_payout", {"run_id": "r"}, {"X-Chhatri-Secret": INTERNAL_SECRET}),
    ("/internal/workflows/execute_payout", {}, {"X-Chhatri-Secret": OFFICER_TOKEN}),
    ("/api/replay/reset", None, {}),
)


def assert_clean(response: Response, *, allow_officer_token: bool = False) -> None:
    text = response.text + " ".join(f"{k}: {v}" for k, v in response.headers.items())
    for secret in SECRETS:
        assert secret not in text, response.request.url
    if not allow_officer_token:
        assert OFFICER_TOKEN not in text, response.request.url


@pytest.mark.parametrize("paytm_mode", ["simulated", "rest"])
async def test_no_response_leaks_a_secret(
    patched_views: None, monkeypatch: pytest.MonkeyPatch, paytm_mode: str
) -> None:
    rest = {"paytm_mid": "MID1", "paytm_key_secret": PAYTM_KEY} if paytm_mode == "rest" else {}
    state = FakeAppState(make_settings(openmeteo_live=True, **rest))
    await state.load("monsoon")
    app = create_app(state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
        session = await http.get("/api/session")
        assert OFFICER_TOKEN in session.text
        assert_clean(session, allow_officer_token=True)
        for path in GETS:
            assert_clean(await http.get(path))
        for path, body, headers in POSTS:
            assert_clean(await http.post(path, json=body, headers=headers))
        raw, headers = signed({"entry": []})
        assert_clean(await http.post("/webhooks/whatsapp", content=raw, headers=headers))

        def leak(_rt: object) -> None:
            raise RuntimeError(" ".join(SECRETS) + OFFICER_TOKEN)

        monkeypatch.setattr(views, "snapshot", leak)
        failed = await http.get("/api/state")
        assert failed.status_code == 500
        assert_clean(failed)
