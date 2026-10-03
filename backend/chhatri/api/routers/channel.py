"""The merchant's preferred channel (Telegram channel; data-model-and-api section 5.0, row 19 and 20).

`GET /api/merchants/{id}/channel` says where this merchant's notifications go (`whatsapp`, the default, or `telegram`), the
mode of each channel (LIVE, SIMULATED or FALLBACK while X6 forces it) and, for Telegram, whether a chat is linked and the
deep link `https://t.me/<bot>?start=S-0142` once the bot's username is known. `POST` sets it (`{"channel": "telegram"}`,
officer token, as the other demo writes; group `messages`; audit `channel.preference_set`). A repeat changes and audits
nothing. The choice lives in the scenario run (a load starts again on the merchant's default). Behind the flag
`telegram_channel`: 404 `not_found` while it is off. Telegram is a messaging channel only: it never changes what a merchant is paid.
"""

from __future__ import annotations

from typing import Annotated, Any, Final, Literal

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, ConfigDict

from chhatri.api.deps import (
    OFFICER_ID,
    RuntimeDep,
    StateDep,
    merchant_or_404,
    rate_limit,
    require_feature,
    require_officer,
)
from chhatri.api.envelope import ok
from chhatri.api.ports import RuntimePort
from chhatri.domain.enums import IntegrationMode, PreferredChannel
from chhatri.integrations.base import IntegrationStatus
from chhatri.integrations.switch import PROCESS_SWITCH
from chhatri.store.telegram_bindings import LIVE_TELEGRAM_BINDINGS

FEATURE: Final = "telegram_channel"
AUDIT_ACTION: Final = "channel.preference_set"
MERCHANT_ID_PATTERN: Final = r"^S-\d{4}$"
MerchantId = Annotated[str, Path(pattern=MERCHANT_ID_PATTERN)]

router = APIRouter(
    prefix="/api/merchants", tags=["channel"], dependencies=[Depends(require_feature(FEATURE))]
)


class ChannelBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    channel: Literal["whatsapp", "telegram"]


def _mode(runtime: RuntimePort, name: str) -> str:
    """LIVE or SIMULATED from the status rows; FALLBACK while the X6 switch forces a live channel off."""
    statuses: tuple[IntegrationStatus, ...] = (
        *runtime.integrations.statuses,
        *getattr(runtime.integrations, "telegram_statuses", ()),
    )
    mode = next((s.mode for s in statuses if s.name == name), IntegrationMode.SIMULATED)
    if mode is IntegrationMode.LIVE and PROCESS_SWITCH.is_forced(name):
        return IntegrationMode.FALLBACK.value
    return mode.value


def _view(runtime: RuntimePort, merchant_id: str) -> dict[str, Any]:
    bindings = getattr(runtime.integrations, "telegram_bindings", LIVE_TELEGRAM_BINDINGS)
    return {
        "merchant_id": merchant_id,
        "preferred_channel": runtime.store.preferred_channel(merchant_id).value,
        "channels": [
            {"channel": "whatsapp", "mode": _mode(runtime, "whatsapp")},
            {
                "channel": "telegram",
                "mode": _mode(runtime, "telegram"),
                "linked": bindings.chat_for(merchant_id) is not None,
                "bot_username": bindings.bot_username,
                "deep_link": bindings.deep_link(merchant_id),
            },
        ],
    }


@router.get("/{merchant_id}/channel")
async def get_channel(state: StateDep, runtime: RuntimeDep, merchant_id: MerchantId) -> dict[str, Any]:
    """The preferred channel and the state of both channels for one merchant."""
    merchant_or_404(state, merchant_id)
    return ok(_view(runtime, merchant_id))


@router.post("/{merchant_id}/channel", dependencies=[Depends(rate_limit("messages"))])
async def set_channel(
    body: ChannelBody,
    officer: Annotated[str, Depends(require_officer)],
    state: StateDep,
    runtime: RuntimeDep,
    merchant_id: MerchantId,
) -> dict[str, Any]:
    """Choose where this merchant's notifications go. Idempotent: choosing the current channel audits nothing."""
    merchant_or_404(state, merchant_id)
    channel = PreferredChannel(body.channel)
    if runtime.store.preferred_channel(merchant_id) is not channel:
        runtime.store.set_preferred_channel(merchant_id, channel)
        runtime.audit.append(
            at=runtime.clock.now(),
            actor=f"officer:{officer or OFFICER_ID}",
            action=AUDIT_ACTION,
            subject_type="merchant",
            subject_id=merchant_id,
            data={"merchant_id": merchant_id, "channel": channel.value},
        )
    return ok(_view(runtime, merchant_id))
