"""The backend half of the contract test (data-model 6.3, card 3.8): the examples under frontend/src/api/contract/ against the real app.

Every example is replayed through the real app (``create_app`` lifespan, real engine, ``make data`` artefacts). The
answer must have the same shape as the stored one (keys and value types, recursively) and agree on the fields the example
lists under ``exact``. The frontend half (src/mock/contract.test.ts) replays the same files against the in-browser mock,
so the mock cannot drift from the product without one of the two failing.

``CHHATRI_UPDATE_CONTRACT=1`` rewrites each file's ``response`` from the real app (and drops any ``exact`` path the real
answer does not have). The other keys are the hand-written case and are never touched.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Final

import pytest
from httpx import ASGITransport, AsyncClient

from chhatri.api.app import create_app
from tests.api.fakes import make_settings

pytestmark = pytest.mark.slow

CONTRACT_DIR: Final = Path(__file__).resolve().parents[3] / "frontend" / "src" / "api" / "contract"
UPDATE: Final = os.environ.get("CHHATRI_UPDATE_CONTRACT") == "1"
KEYS: Final = ("name", "description", "scenario", "at", "setup", "request", "exact", "response")
CASES: Final = sorted(CONTRACT_DIR.glob("*.json"))
OFFLINE: Final = {
    "whatsapp_access_token": None,
    "whatsapp_phone_number_id": None,
    "whatsapp_app_secret": None,
    "whatsapp_verify_token": None,
    "whatsapp_demo_recipient": None,
}


@pytest.fixture
async def http() -> AsyncIterator[AsyncClient]:
    app = create_app(make_settings(**OFFLINE))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client,
    ):
        yield client


def pick(body: Any, path: str) -> tuple[bool, Any]:
    """The value at a dotted path (list indexes are numbers), and whether the path exists."""
    node = body
    for part in path.split("."):
        if isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return False, None
    return True, node


def kind_of(value: Any) -> str:
    return "null" if value is None else "array" if isinstance(value, list) else type(value).__name__


def shape_diff(a: Any, b: Any, path: str = "$") -> list[str]:
    """Differences in keys and value types; lists are compared pairwise and must be empty together."""
    if kind_of(a) != kind_of(b):
        return [f"{path}: {kind_of(a)} against {kind_of(b)}"]
    if isinstance(a, list):
        if bool(a) != bool(b):
            return [f"{path}: one list is empty"]
        return [
            d for i, (x, y) in enumerate(zip(a, b, strict=False)) for d in shape_diff(x, y, f"{path}.{i}")
        ]
    if isinstance(a, dict):
        keys = sorted(set(a) ^ set(b))
        return [f"{path}: key {k} on one side only" for k in keys] + [
            d for k in sorted(set(a) & set(b)) for d in shape_diff(a[k], b[k], f"{path}.{k}")
        ]
    return []


async def send(http: AsyncClient, step: dict[str, Any], token: str, link_id: str | None) -> tuple[int, Any]:
    """One step. A Paytm callback names the link the case created, so a link id baked into the file cannot go stale."""
    body = step.get("body")
    if link_id is not None and step["path"] == "/api/webhooks/paytm" and body is not None:
        body = {**body, "link_id": link_id, "txn_id": f"SIM-{link_id}"}
    headers = {"Authorization": f"Bearer {token}"} if step.get("auth") == "officer" else {}
    response = await http.request(step["method"], step["path"], headers=headers, json=body)
    return response.status_code, response.json()


async def replay(http: AsyncClient, case: dict[str, Any]) -> tuple[int, Any]:
    token = (await http.get("/api/session")).json()["data"]["officer_token"]
    for path, payload in (
        ("/api/replay/load", {"scenario": case["scenario"]}),
        ("/api/replay/seek", {"to": case["at"]}),
    ):
        assert (await http.post(path, json=payload)).status_code == 200, path
    link_id: str | None = None
    for step in case["setup"]:
        status, body = await send(http, step, token, link_id)
        assert status == 200, f"setup {step['method']} {step['path']}: {body}"
        data = body.get("data") if isinstance(body, dict) else None
        link_id = data.get("link_id", link_id) if isinstance(data, dict) else link_id
    return await send(http, case["request"], token, link_id)


def write(path: Path, case: dict[str, Any], status: int, body: Any) -> None:
    kept = [p for p in case["exact"] if pick(body, p)[0]]
    updated = {
        **{k: case[k] for k in KEYS if k != "response"},
        "exact": kept,
        "response": {"status": status, "body": body},
    }
    path.write_text(
        json.dumps({k: updated[k] for k in KEYS}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def test_the_eleven_cases_are_present() -> None:
    names = {p.stem for p in CASES}
    assert names >= {
        "cover.anil-active", "cover.ramesh-none", "cover.ramesh-waiting", "cover.unknown-merchant",
        "claims.anil-paid", "claims.anil-dispute", "claims.ramesh-empty",
        "receipt.anil-area", "receipt.unknown-decision",
        "premium-link.ramesh-blocked", "paytm-webhook.ramesh-paid",
    }  # fmt: skip


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.stem)
async def test_the_example_matches_the_real_app(http: AsyncClient, path: Path) -> None:
    case = json.loads(path.read_text(encoding="utf-8"))
    assert tuple(case) == KEYS and case["name"] == path.stem
    status, body = await replay(http, case)
    if UPDATE:
        write(path, case, status, body)
        return
    stored = case["response"]
    assert status == stored["status"], body
    assert shape_diff(stored["body"], body) == []
    for field in case["exact"]:
        found, expected = pick(stored["body"], field)
        assert found, f"{field} is not in the stored answer"
        assert pick(body, field) == (True, expected), field
