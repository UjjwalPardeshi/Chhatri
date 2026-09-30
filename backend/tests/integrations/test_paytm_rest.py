"""Direct Paytm REST links: signed body/head verified with PaytmChecksum (SPEC §14.3)."""

from __future__ import annotations

import json

import httpx
import pytest
from paytmchecksum import PaytmChecksum

from chhatri.domain.models import Merchant
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.paytm import RestPaytmLinks, signed_request

from .conftest import SIM_NOW, no_sleep

KEY = "abcdEFGH12345678"
BASE = "https://securestage.paytmpayments.com"


def split_signed(raw: bytes) -> tuple[str, dict]:
    """Recover the exact signed body text and the head from the raw request bytes."""
    text = raw.decode()
    assert text.startswith('{"body": ')
    head_at = text.rindex(', "head": ')
    return text[len('{"body": ') : head_at], json.loads(text[head_at + len(', "head": ') : -1])


class PaytmDouble:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = responses
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.pop(0)


def rest(double: PaytmDouble) -> RestPaytmLinks:
    return RestPaytmLinks(
        mid="MID123",
        key_secret=KEY,
        base_url=BASE,
        clock=lambda: SIM_NOW,
        transport=httpx.MockTransport(double),
        sleep=no_sleep,
    )


def success(**body: object) -> httpx.Response:
    return httpx.Response(200, json={"head": {}, "body": {"resultInfo": {"resultStatus": "SUCCESS"}, **body}})


async def test_create_link_signed_exactly(anil: Merchant) -> None:
    double = PaytmDouble([success(shortUrl="https://paytm.me/Ab1", linkId=204587)])
    link = await rest(double).create_premium_link(anil, 6000, "Chhatri cover · 30 days")
    assert (link.url, link.link_id, link.source, link.created_at) == (
        "https://paytm.me/Ab1",
        "204587",
        "paytm-rest",
        SIM_NOW,
    )
    request = double.requests[0]
    assert str(request.url) == f"{BASE}/link/create"
    assert request.headers["Content-Type"] == "application/json"
    body_text, head = split_signed(request.content)
    assert head["tokenType"] == "AES"
    assert PaytmChecksum.verifySignature(body_text, KEY, head["signature"])
    body = json.loads(body_text)
    assert body_text == json.dumps(body)
    assert body == {
        "mid": "MID123",
        "linkType": "FIXED",
        "linkDescription": "Chhatri cover · 30 days",
        "linkName": "Chhatri cover S 0142",
        "sendSms": False,
        "sendEmail": False,
        "maxPaymentsAllowed": 1,
        "amount": "60.00",
        "customerContact": {"customerName": "Anil Jadhav", "customerEmail": None, "customerMobile": None},
    }
    assert KEY not in request.content.decode()


async def test_create_link_retries_5xx_and_rejects_failure(anil: Merchant) -> None:
    double = PaytmDouble([httpx.Response(502), success(shortUrl="https://paytm.me/Ab1", linkId="L1")])
    assert (await rest(double).create_premium_link(anil, 6000, "p")).link_id == "L1"
    failed = PaytmDouble(
        [httpx.Response(200, json={"body": {"resultInfo": {"resultStatus": "FAILURE", "resultCode": "501"}}})]
    )
    with pytest.raises(IntegrationError, match="code 501"):
        await rest(failed).create_premium_link(anil, 6000, "p")
    denied = PaytmDouble([httpx.Response(401)])
    with pytest.raises(IntegrationError, match="authentication"):
        await rest(denied).create_premium_link(anil, 6000, "p")
    assert len(denied.requests) == 1


async def test_link_payment_signed_fetch() -> None:
    orders = [{"orderStatus": "SUCCESS", "txnId": "T1", "txnAmount": "60.00"}]
    double = PaytmDouble([success(orders=orders)])
    paid = await rest(double).link_payment("204587")
    assert paid.paid and paid.txn_id == "T1"
    body_text, head = split_signed(double.requests[0].content)
    assert str(double.requests[0].url) == f"{BASE}/link/fetchTransaction"
    assert json.loads(body_text) == {"mid": "MID123", "linkId": "204587"}
    assert PaytmChecksum.verifySignature(body_text, KEY, head["signature"])


def test_signing_failure_and_validation() -> None:
    with pytest.raises(IntegrationError, match="could not sign"):
        signed_request({"a": 1}, "short")
    with pytest.raises(ValueError):
        RestPaytmLinks(mid="", key_secret=KEY, base_url=BASE, clock=lambda: SIM_NOW)
    with pytest.raises(ValueError):
        RestPaytmLinks(mid="M", key_secret=KEY, base_url="http://insecure", clock=lambda: SIM_NOW)
