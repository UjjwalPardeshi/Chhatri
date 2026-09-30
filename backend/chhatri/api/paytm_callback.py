"""Paytm payment-link callback parsing and checksum verification (SPEC §14.3, §19, §21).

Paytm posts a flat set of string parameters, as ``application/x-www-form-urlencoded`` or JSON.
When the direct REST integration is configured (``PAYTM_MID`` + ``PAYTM_KEY_SECRET``) every callback
must carry ``CHECKSUMHASH`` and is verified with ``PaytmChecksum.verifySignature`` over the other
parameters; in MCP or simulated mode there is no merchant key in this process, so the callback is
trusted as the simulated/staging flow it is (SPEC §0.1). Accepted spellings: link id ``linkId`` /
``LINKID`` / ``link_id``; transaction id ``TXNID`` / ``txnId`` / ``txn_id``; status ``STATUS`` /
``status``. Only ``TXN_SUCCESS`` (or ``SUCCESS`` / ``PAID``) marks a premium paid.
"""

from __future__ import annotations

import json
import logging
from collections import OrderedDict
from dataclasses import dataclass
from typing import Final

from fastapi import Request
from paytmchecksum import PaytmChecksum
from starlette.datastructures import UploadFile

from chhatri.api.errors import ApiError

logger = logging.getLogger(__name__)

__all__ = ["PaidTransactions", "PaytmCallback", "checksum_valid", "parse_callback", "read_callback_params"]

CHECKSUM_KEY: Final = "CHECKSUMHASH"
LINK_ID_KEYS: Final = ("linkId", "LINKID", "link_id")
TXN_ID_KEYS: Final = ("TXNID", "txnId", "txn_id")
STATUS_KEYS: Final = ("STATUS", "status")
PAID_STATUSES: Final = frozenset({"TXN_SUCCESS", "SUCCESS", "PAID"})
MAX_PARAMS: Final = 64
MAX_VALUE_CHARS: Final = 512
FORM_TYPES: Final = ("application/x-www-form-urlencoded", "multipart/form-data")
MAX_SEEN_TXNS: Final = 10_000


@dataclass(frozen=True, slots=True)
class PaytmCallback:
    link_id: str
    txn_id: str | None
    status: str
    paid: bool


def _first(params: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = params.get(key, "").strip()
        if value:
            return value
    return None


def _check_params(raw: dict[str, object]) -> dict[str, str]:
    if len(raw) > MAX_PARAMS:
        raise ApiError(422, "invalid request", fields={"body": f"at most {MAX_PARAMS} parameters"})
    params: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(value, bool) or not isinstance(value, str | int | float):
            raise ApiError(422, "invalid request", fields={key: "must be a string"})
        text = str(value)
        if len(text) > MAX_VALUE_CHARS:
            raise ApiError(422, "invalid request", fields={key: "value is too long"})
        params[key] = text
    return params


async def read_callback_params(request: Request) -> dict[str, str]:
    """Read the callback as a flat ``{name: string}`` map from a form or JSON body."""
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type == "application/json":
        try:
            raw = json.loads(await request.body())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ApiError(422, "invalid request", fields={"body": "invalid JSON"}) from exc
        if not isinstance(raw, dict):
            raise ApiError(422, "invalid request", fields={"body": "expected a JSON object"})
        return _check_params(raw)
    if content_type in FORM_TYPES:
        form = await request.form()
        if any(isinstance(value, UploadFile) for value in form.values()):
            raise ApiError(422, "invalid request", fields={"body": "file parts are not accepted"})
        return _check_params(dict(form.items()))
    raise ApiError(415, "callback must be form-encoded or JSON")


def parse_callback(params: dict[str, str]) -> PaytmCallback:
    """Extract link id, transaction id and status; 422 when the link id or status is missing."""
    link_id = _first(params, LINK_ID_KEYS)
    status = _first(params, STATUS_KEYS)
    missing = {name: "required" for name, value in (("linkId", link_id), ("STATUS", status)) if value is None}
    if link_id is None or status is None:
        raise ApiError(422, "invalid request", fields=missing)
    txn_id = _first(params, TXN_ID_KEYS)
    return PaytmCallback(link_id=link_id, txn_id=txn_id, status=status, paid=status.upper() in PAID_STATUSES)


def checksum_valid(params: dict[str, str], merchant_key: str) -> bool:
    """Verify ``CHECKSUMHASH`` over every other parameter (SPEC §14.3); never raises."""
    checksum = params.get(CHECKSUM_KEY, "").strip()
    if not checksum:
        return False
    signed = {key: value for key, value in params.items() if key != CHECKSUM_KEY}
    try:
        return bool(PaytmChecksum.verifySignature(signed, merchant_key, checksum))
    except (ValueError, IndexError, TypeError) as exc:
        logger.warning("Paytm checksum could not be verified: %s", type(exc).__name__)
        return False


class PaidTransactions:
    """Bounded memory of Paytm transaction ids already applied (globally unique per payment)."""

    def __init__(self, capacity: int = MAX_SEEN_TXNS) -> None:
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._capacity = capacity

    def first_time(self, txn_id: str) -> bool:
        """Reserve ``txn_id``; False when it was already applied (or is being applied)."""
        if txn_id in self._seen:
            return False
        self._seen[txn_id] = None
        if len(self._seen) > self._capacity:
            self._seen.popitem(last=False)
        return True

    def forget(self, txn_id: str) -> None:
        """Release a reservation whose payment could not be applied, so a retry is processed."""
        self._seen.pop(txn_id, None)
