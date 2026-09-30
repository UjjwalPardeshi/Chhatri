"""Paytm parsing, formatting and simulated links (SPEC §14.3)."""

from __future__ import annotations

import pytest

from chhatri.domain.models import Merchant
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.paytm import (
    SIM_URL_PREFIX,
    SimulatedPaytmLinks,
    format_amount,
    parse_link_payment,
    parse_mcp_link,
    parse_rest_link,
)
from chhatri.integrations.paytm_common import link_name, parse_json_text, rupees_to_paise, validate_link_id

from .conftest import SIM_NOW


@pytest.mark.parametrize(
    ("paise", "text"), [(6000, "60.00"), (1, "0.01"), (138000, "1380.00"), (199, "1.99")]
)
def test_format_amount(paise: int, text: str) -> None:
    assert format_amount(paise) == text


@pytest.mark.parametrize("bad", [0, -5, True, 1.5])
def test_format_amount_rejects(bad: object) -> None:
    with pytest.raises(ValueError):
        format_amount(bad)  # type: ignore[arg-type]


def test_rupees_to_paise() -> None:
    assert rupees_to_paise("60.00") == 6000 and rupees_to_paise(1.005) == 101
    assert rupees_to_paise("abc") is None and rupees_to_paise("NaN") is None


def test_parse_mcp_link_is_strict() -> None:
    assert parse_mcp_link("url =https://paytm.me/X1\nlinkId=123\n") == ("https://paytm.me/X1", "123")
    for bad in (
        "url=https://paytm.me/X1\nlinkId=1",
        "url =http://paytm.me/X\nlinkId=1",
        "Error: bad",
        "url =https://p.me/x\nlinkId=1\nextra",
        None,
    ):
        with pytest.raises(IntegrationError):
            parse_mcp_link(bad)


def ok_body(**extra: object) -> dict:
    return {"body": {"resultInfo": {"resultStatus": "SUCCESS", "resultCode": "200"}, **extra}}


def test_parse_rest_link() -> None:
    assert parse_rest_link(ok_body(shortUrl="https://paytm.me/Ab1", linkId=204587)) == (
        "https://paytm.me/Ab1",
        "204587",
    )
    with pytest.raises(IntegrationError, match="code 5001"):
        parse_rest_link(
            {
                "body": {
                    "resultInfo": {
                        "resultStatus": "FAILURE",
                        "resultCode": "5001",
                        "resultMsg": "secret stuff",
                    }
                }
            }
        )
    with pytest.raises(IntegrationError, match="code unknown"):
        parse_rest_link({"body": {"resultInfo": {"resultStatus": "FAILURE", "resultCode": "x y"}}})
    with pytest.raises(IntegrationError, match="no body"):
        parse_rest_link({"head": {}})
    with pytest.raises(IntegrationError, match="no link"):
        parse_rest_link(ok_body(shortUrl="javascript:alert(1)", linkId=1))
    with pytest.raises(IntegrationError, match="no link"):
        parse_rest_link(ok_body(shortUrl="https://paytm.me/a", linkId=True))


def test_parse_link_payment() -> None:
    orders = [{"orderStatus": "PENDING"}, {"orderStatus": "SUCCESS", "txnId": 77, "txnAmount": "60.00"}]
    paid = parse_link_payment("L1", ok_body(orders=orders))
    assert (paid.paid, paid.txn_id, paid.paid_amount_paise) == (True, "77", 6000)
    assert parse_link_payment("L1", ok_body(orders=[])).paid is False
    with pytest.raises(IntegrationError, match="orders"):
        parse_link_payment("L1", ok_body())
    assert parse_json_text('{"a": 1}') == {"a": 1}
    for bad in ("nope", "[1]", None):
        with pytest.raises(IntegrationError):
            parse_json_text(bad)


def test_link_name_and_id_validation() -> None:
    assert link_name("Chhatri cover S-0142 (30 days)!") == "Chhatri cover S 0142 30 days"
    assert link_name("***") == "Chhatri cover"
    assert validate_link_id("204587") == "204587"
    with pytest.raises(ValueError):
        validate_link_id("../x")


async def test_simulated_links_are_deterministic(anil: Merchant) -> None:
    first = SimulatedPaytmLinks(clock=lambda: SIM_NOW)
    second = SimulatedPaytmLinks(clock=lambda: SIM_NOW)
    a1 = await first.create_premium_link(anil, 6000, "Chhatri cover · 30 days")
    a2 = await first.create_premium_link(anil, 6000, "Chhatri cover · 30 days")
    b1 = await second.create_premium_link(anil, 6000, "Chhatri cover · 30 days")
    assert a1 == b1 and a1 != a2
    assert a1.url.startswith(SIM_URL_PREFIX) and len(a1.url) == len(SIM_URL_PREFIX) + 6
    assert a1.link_id == "sim-" + a1.url.removeprefix(SIM_URL_PREFIX)
    assert a1.source == "simulated" and a1.created_at == SIM_NOW
    assert (await first.link_payment(a1.link_id)).paid is False
    with pytest.raises(IntegrationError, match="unknown"):
        await first.link_payment("sim-FFFFFF")
