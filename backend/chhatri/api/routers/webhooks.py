"""Inbound webhooks: Paytm payment callback and WhatsApp Cloud API (SPEC §19, §14.2, §14.3, §21).

Both are rate limited (60/min). WhatsApp: the GET handshake echoes ``hub.challenge`` as text/plain
for the right verify token (403 otherwise); a POST is verified over the raw bytes before parsing
(403 on mismatch), acknowledged immediately, and processed in order in the background
(``chhatri.api.whatsapp_inbox``). Paytm: form or JSON; checksum-verified in REST mode (SPEC §14.3);
idempotent on the Paytm transaction id.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from chhatri.api.deps import SettingsDep, StateDep, get_runtime, rate_limit
from chhatri.api.envelope import ok
from chhatri.api.errors import ApiError
from chhatri.api.paytm_callback import PaidTransactions, checksum_valid, parse_callback, read_callback_params
from chhatri.api.security import verify_whatsapp_challenge, verify_whatsapp_signature
from chhatri.api.whatsapp_inbox import WhatsAppInbox, inbound_channel
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.whatsapp import StatusEvent, parse_webhook

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"], dependencies=[Depends(rate_limit("webhooks"))])


@router.post("/api/webhooks/paytm")
async def paytm_callback(request: Request, settings: SettingsDep, state: StateDep) -> dict[str, Any]:
    """Mark a premium paid (activates or extends cover via the orchestrator, SPEC §9.7)."""
    params = await read_callback_params(request)
    if settings.paytm_mode == "rest":
        key = settings.paytm_key_secret.get_secret_value() if settings.paytm_key_secret else ""
        if not checksum_valid(params, key):
            logger.warning("Paytm callback rejected: checksum mismatch")
            raise ApiError(403, "invalid checksum")
    callback = parse_callback(params)
    if not callback.paid:
        logger.info("Paytm callback for %s with status %s ignored", callback.link_id, callback.status)
        return ok({"status": "ignored", "link_id": callback.link_id})
    runtime = get_runtime(state)
    seen: PaidTransactions = request.app.state.paid_transactions
    if callback.txn_id is not None and not seen.first_time(callback.txn_id, runtime.store):
        return ok({"status": "duplicate", "link_id": callback.link_id})
    try:
        await runtime.orchestrator.paytm_paid(callback.link_id, callback.txn_id)
    except Exception as exc:
        if callback.txn_id is not None:
            seen.forget(callback.txn_id)
        if isinstance(exc, KeyError):
            raise ApiError(404, f"payment link {callback.link_id} not found") from exc
        raise
    logger.info("premium link %s paid", callback.link_id)
    return ok({"status": "paid", "link_id": callback.link_id})


@router.get("/webhooks/whatsapp", response_model=None)
async def whatsapp_challenge(request: Request, settings: SettingsDep) -> PlainTextResponse:
    """Meta's subscription handshake (SPEC §14.2)."""
    token = settings.whatsapp_verify_token.get_secret_value() if settings.whatsapp_verify_token else ""
    challenge = verify_whatsapp_challenge(dict(request.query_params), token)
    if challenge is None:
        raise ApiError(403, "verification failed")
    return PlainTextResponse(challenge)


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request, settings: SettingsDep, state: StateDep) -> dict[str, Any]:
    """Signed inbound messages → background processing; always a quick 200 once verified."""
    raw = await request.body()
    secret = settings.whatsapp_app_secret.get_secret_value() if settings.whatsapp_app_secret else ""
    if not verify_whatsapp_signature(secret, raw, request.headers.get("x-hub-signature-256")):
        logger.warning("WhatsApp webhook rejected: bad signature")
        raise ApiError(403, "invalid signature")
    try:
        events = parse_webhook(json.loads(raw))
    except (json.JSONDecodeError, UnicodeDecodeError, IntegrationError) as exc:
        raise ApiError(422, "invalid request", fields={"body": "expected a WhatsApp webhook object"}) from exc
    try:
        runtime = state.runtime
    except RuntimeError:
        logger.warning("WhatsApp webhook with %d item(s) while no scenario is loaded; dropped", len(events))
        return ok({"accepted": 0, "duplicates": 0, "ignored": len(events)})
    channel = inbound_channel(runtime)
    fresh = [event for event in events if channel.accept_inbound(event)]
    messages = [event for event in fresh if not isinstance(event, StatusEvent)]
    inbox: WhatsAppInbox = request.app.state.whatsapp_inbox
    inbox.submit(messages)
    ignored = len(fresh) - len(messages)
    return ok({"accepted": len(messages), "duplicates": len(events) - len(fresh), "ignored": ignored})
