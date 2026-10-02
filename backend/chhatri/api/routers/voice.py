"""POST /api/voice/stt and /api/voice/tts: N4 voice (data-model 5.11; fs-05 section 11).

Behind the flag `n4_voice` (404 `not_found` while it is off). Both routes are in the `uploads` rate group. STT takes
audio (multipart, validated by content) or a transcript the browser made (JSON); the audio is not stored. TTS voices
only the answer of an earlier ask of the same merchant, so it is not a general speech proxy.
"""

from __future__ import annotations

import logging
import re
from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError
from starlette.datastructures import UploadFile as FormFile

from chhatri.api.deps import RuntimeDep, SettingsDep, StateDep, merchant_or_404, rate_limit, require_feature
from chhatri.api.envelope import ok
from chhatri.api.errors import ApiError, validation_fields
from chhatri.api.schemas.ask import (
    MERCHANT_ID_PATTERN,
    SttBrowserRequest,
    TtsRequest,
    stt_response,
    tts_response,
)
from chhatri.api.uploads import MAX_AUDIO_BYTES, read_limited, validate_audio
from chhatri.ask.voice import UnknownAsk, VoiceService
from chhatri.ask.wiring import build_voice_service

logger = logging.getLogger(__name__)

FEATURE: Final = "n4_voice"
MAX_FORM_FIELDS: Final = 4
LANG_HINTS: Final = frozenset({"hi-IN", "en-IN", "unknown"})

router = APIRouter(
    prefix="/api/voice",
    tags=["voice"],
    dependencies=[Depends(require_feature(FEATURE)), Depends(rate_limit("uploads"))],
)


def get_voice_service(runtime: RuntimeDep, settings: SettingsDep) -> VoiceService:
    """The voice service of the loaded scenario (tests override this dependency)."""
    return build_voice_service(runtime=runtime, settings=settings)


VoiceServiceDep = Annotated[VoiceService, Depends(get_voice_service)]


def _invalid(fields: dict[str, str]) -> ApiError:
    return ApiError(422, "invalid request", fields=fields)


def _body[T](model: type[T], raw: bytes) -> T:
    try:
        return model.model_validate_json(raw or b"{}")  # type: ignore[attr-defined, no-any-return]
    except ValidationError as exc:
        raise ApiError(422, "invalid request", fields=validation_fields(list(exc.errors()))) from exc


@router.post("/stt")
async def speech_to_text(request: Request, state: StateDep, voice: VoiceServiceDep) -> dict[str, Any]:
    """A transcript, one chip per amount and date, and the H26 label."""
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type == "multipart/form-data":
        return ok(stt_response(await _from_audio(request, state, voice)))
    if content_type == "application/json":
        body = _body(SttBrowserRequest, await request.body())
        merchant_or_404(state, body.merchant_id)
        return ok(stt_response(voice.from_browser(body.merchant_id, body.transcript, body.language_code)))
    raise ApiError(415, "send multipart/form-data with a file, or JSON with a browser transcript")


async def _from_audio(request: Request, state: Any, voice: VoiceService) -> Any:
    async with request.form(max_files=1, max_fields=MAX_FORM_FIELDS) as form:
        merchant_id = form.get("merchant_id")
        upload = form.get("file")
        hint = form.get("lang_hint")
        if not isinstance(merchant_id, str) or not re.fullmatch(MERCHANT_ID_PATTERN, merchant_id.strip()):
            raise _invalid({"merchant_id": "a merchant id like S-0142 is required"})
        if not isinstance(upload, FormFile):
            raise _invalid({"file": "an audio file is required"})
        if hint is not None and (not isinstance(hint, str) or hint.strip() not in LANG_HINTS):
            raise _invalid({"lang_hint": "must be hi-IN, en-IN or unknown"})
        merchant_or_404(state, merchant_id.strip())
        audio = validate_audio(await read_limited(upload, MAX_AUDIO_BYTES))
        return await voice.transcribe_audio(
            merchant_id.strip(),
            audio.data,
            audio.mime,
            duration_s=audio.duration_s,
            lang_hint=hint.strip() if hint else None,
        )


@router.post("/tts")
async def text_to_speech(body: TtsRequest, state: StateDep, voice: VoiceServiceDep) -> dict[str, Any]:
    """Speak the answer of an earlier ask: Sarvam audio, or `audio_url` null so the client speaks it."""
    merchant = merchant_or_404(state, body.merchant_id)
    try:
        return ok(tts_response(await voice.speak(merchant, body.ask_id, body.lang)))
    except UnknownAsk as exc:
        raise ApiError(404, f"ask {body.ask_id} not found") from exc
