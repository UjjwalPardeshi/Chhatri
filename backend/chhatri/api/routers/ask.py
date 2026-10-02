"""POST /api/merchants/{merchant_id}/ask: Ask Chhatri (N2; data-model 5.2; fs-05).

Behind the flag `n2_ask_chhatri` (404 `not_found` while it is off). Rate group `messages`. The question is untrusted
text (H16). A voice question names its `stt_id` and the chips the merchant tapped; an amount or a date that was not
confirmed is 409 `mentions_unconfirmed` and nothing is answered or written. A model failure is never an HTTP error:
the answer is 200 with a template and a FALLBACK or SIMULATED label.
"""

from __future__ import annotations

from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends, Path

from chhatri.api.deps import RuntimeDep, SettingsDep, StateDep, merchant_or_404, rate_limit, require_feature
from chhatri.api.envelope import ok
from chhatri.api.errors import ApiError
from chhatri.api.schemas.ask import AskRequest, ask_response
from chhatri.ask.service import AskService, MentionsUnconfirmed, UnknownSpeechResult, VoiceQuestion
from chhatri.ask.wiring import build_ask_service

FEATURE: Final = "n2_ask_chhatri"
MERCHANT_ID_PATTERN: Final = r"^S-\d{4}$"
MerchantId = Annotated[str, Path(pattern=MERCHANT_ID_PATTERN)]

router = APIRouter(
    prefix="/api/merchants",
    tags=["ask"],
    dependencies=[Depends(require_feature(FEATURE)), Depends(rate_limit("messages"))],
)


def get_ask_service(state: StateDep, runtime: RuntimeDep, settings: SettingsDep) -> AskService:
    """The Ask service of the loaded scenario (tests override this dependency)."""
    return build_ask_service(static=state.static, runtime=runtime, settings=settings)


AskServiceDep = Annotated[AskService, Depends(get_ask_service)]


@router.post("/{merchant_id}/ask")
async def ask(
    body: AskRequest, state: StateDep, service: AskServiceDep, merchant_id: MerchantId
) -> dict[str, Any]:
    """Answer one question: rules for known intents, the model chain for the rest, always labelled."""
    merchant_or_404(state, merchant_id)
    voice = None
    if body.stt_id is not None:
        voice = VoiceQuestion(body.stt_id, tuple(body.confirmed_mentions or ()))
    try:
        answer = await service.answer(merchant_id, body.question, body.lang, voice=voice)
    except MentionsUnconfirmed as exc:
        raise ApiError(
            409,
            "confirm every amount and date before sending",
            code="mentions_unconfirmed",
            fields={"mentions": ",".join(exc.ids)},
        ) from exc
    except UnknownSpeechResult as exc:
        raise ApiError(
            422, "invalid request", fields={"stt_id": "unknown speech result for this merchant"}
        ) from exc
    return ok(ask_response(answer))
