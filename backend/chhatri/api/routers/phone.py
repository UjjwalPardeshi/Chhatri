"""Phone-simulator inbound routes: text, voice, canned voice, slip photo (SPEC §19, §13, §20).

Each route hands the input to the same ``ConversationService`` the live WhatsApp channel uses and
answers with the messages it produced (the inbound message first, then the replies). Uploads are
validated by content (``chhatri.api.uploads``) before they reach the conversation.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends, File, Path, Request, UploadFile
from pydantic import ValidationError
from starlette.datastructures import UploadFile as FormFile

from chhatri.api.deps import RuntimeDep, StateDep, merchant_or_404, rate_limit
from chhatri.api.envelope import ok_list
from chhatri.api.errors import ApiError, validation_fields
from chhatri.api.ports import AppStatePort, RuntimePort
from chhatri.api.requests import PhotoSampleRequest, TextMessageRequest, VoiceDemoRequest
from chhatri.api.uploads import (
    MAX_AUDIO_BYTES,
    MAX_IMAGE_BYTES,
    ValidatedImage,
    read_limited,
    validate_audio,
    validate_image,
)
from chhatri.domain.models import Message
from chhatri.integrations.demo_voice import DEMO_UTTERANCES, DEMO_VOICE_MIME, demo_voice_note
from chhatri.replay import views

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/merchants", tags=["phone"])

MERCHANT_ID_PATTERN: Final = r"^S-\d{4}$"
SLIPS_DIR_NAME: Final = "slips"
MAX_FORM_FIELDS: Final = 4
MerchantId = Annotated[str, Path(pattern=MERCHANT_ID_PATTERN)]
MessagesLimited = Depends(rate_limit("messages"))
UploadsLimited = Depends(rate_limit("uploads"))


def _reply(messages: tuple[Message, ...]) -> dict[str, Any]:
    items = [views.message_view(message) for message in messages]
    return ok_list(items, total=len(items), limit=len(items), offset=0)


@router.post("/{merchant_id}/messages", dependencies=[MessagesLimited])
async def post_text(
    body: TextMessageRequest, state: StateDep, runtime: RuntimeDep, merchant_id: MerchantId
) -> dict[str, Any]:
    """Inbound text from the phone simulator (SPEC §13.1)."""
    merchant_or_404(state, merchant_id)
    return _reply(await runtime.conversation.handle_text(merchant_id, body.text))


@router.post("/{merchant_id}/voice", dependencies=[UploadsLimited])
async def post_voice(
    state: StateDep, runtime: RuntimeDep, merchant_id: MerchantId, file: Annotated[UploadFile, File()]
) -> dict[str, Any]:
    """Inbound voice note (multipart ``file``): ≤ 5 MB, ≤ 30 s, validated by content (SPEC §19)."""
    merchant_or_404(state, merchant_id)
    audio = validate_audio(await read_limited(file, MAX_AUDIO_BYTES))
    return _reply(await runtime.conversation.handle_voice(merchant_id, audio.data, audio.mime))


@router.post("/{merchant_id}/voice-demo", dependencies=[MessagesLimited])
async def post_voice_demo(
    body: VoiceDemoRequest, state: StateDep, runtime: RuntimeDep, merchant_id: MerchantId
) -> dict[str, Any]:
    """Canned voice note for a deck utterance: ``why``, ``dispute``, ``ill`` or ``cover`` (SPEC §13.6)."""
    merchant_or_404(state, merchant_id)
    utterance = DEMO_UTTERANCES[body.key]
    messages = await runtime.conversation.handle_voice(
        merchant_id, demo_voice_note(body.key), DEMO_VOICE_MIME, transcript_hint=utterance.transcript
    )
    return _reply(messages)


@router.post("/{merchant_id}/photo", dependencies=[UploadsLimited])
async def post_photo(
    request: Request, state: StateDep, runtime: RuntimeDep, merchant_id: MerchantId
) -> dict[str, Any]:
    """Inbound slip photo: multipart ``file``, or JSON ``{sample}`` naming a sample slip (SPEC §19).

    ``{}`` / ``{"sample": null}`` sends the loaded scenario's own sample slip (SPEC §17.2).
    """
    merchant_or_404(state, merchant_id)
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type == "multipart/form-data":
        image = await _uploaded_image(request)
    elif content_type == "application/json":
        image = _sample_image(state, runtime, _sample_request(await request.body()))
    else:
        raise ApiError(415, "send multipart/form-data with a file, or JSON {sample}")
    media_id = runtime.ids.next("media")
    return _reply(await runtime.conversation.handle_image(merchant_id, image.data, image.mime, media_id))


async def _uploaded_image(request: Request) -> ValidatedImage:
    async with request.form(max_files=1, max_fields=MAX_FORM_FIELDS) as form:
        upload = form.get("file")
        if not isinstance(upload, FormFile):
            raise ApiError(422, "invalid request", fields={"file": "an image file is required"})
        return validate_image(await read_limited(upload, MAX_IMAGE_BYTES))


def _sample_request(raw: bytes) -> PhotoSampleRequest:
    try:
        return PhotoSampleRequest.model_validate_json(raw or b"{}")
    except ValidationError as exc:
        raise ApiError(422, "invalid request", fields=validation_fields(list(exc.errors()))) from exc


def _sample_image(state: AppStatePort, runtime: RuntimePort, body: PhotoSampleRequest) -> ValidatedImage:
    name = body.sample or runtime.scenario.slip_sample
    if name is None:
        raise ApiError(
            422, "invalid request", fields={"sample": "this scenario has no sample slip; name one"}
        )
    slips_dir = (state.static.data_dir / SLIPS_DIR_NAME).resolve()
    path = (slips_dir / name).resolve()
    if path.parent != slips_dir or not path.is_file():
        raise ApiError(404, f"sample slip {name} not found")
    return validate_image(path.read_bytes())
