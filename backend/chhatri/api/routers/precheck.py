"""The slip pre-check routes (N3; data-model 5.3, fs-02 section 8).

Behind the flag ``n3_slip_precheck``: while it is off every route answers the ordinary 404 ``not_found``. The first route
reads one photo (multipart ``file`` or JSON ``{sample}``) and shows what was read, and nothing is decided. The second takes
the merchant's action: CONFIRM the fields (with the doctor rule on this asks "may we ask your doctor?" and files nothing),
CONSENT_YES / CONSENT_NO (the answer, then the claim is filed) or SEND_TO_TEAM; the policy engine alone decides the claim.
The third (``GET …/slip-precheck/open``) says what is open for the merchant now: the check-in, the pre-check that waits
for them, or the doctor question. A provider failure is never an HTTP error: it is a 200 with status NEEDS_TEAM and a
label. Every 409 carries a specific ``code`` (``PrecheckConflict.code``) so the app can say a true, friendly sentence.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Final, Literal, cast

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.datastructures import UploadFile as FormFile

from chhatri.api.deps import RuntimeDep, StateDep, merchant_or_404, rate_limit, require_feature
from chhatri.api.envelope import ok
from chhatri.api.errors import ApiError, validation_fields
from chhatri.api.ports import AppStatePort, RuntimePort
from chhatri.api.requests import SAMPLE_PATTERN
from chhatri.api.uploads import MAX_IMAGE_BYTES, ValidatedImage, read_limited, validate_image
from chhatri.consent.errors import ConsentConflict
from chhatri.consent.slip_gate import require_slip_consent
from chhatri.precheck.clean import UncleanableImage
from chhatri.precheck.consent_step import consent_question, consent_view
from chhatri.precheck.model import Action, PrecheckStatus
from chhatri.precheck.registry import FLAG, precheck_service
from chhatri.precheck.service import PrecheckConflict, PrecheckNotFound, SlipPrecheckService
from chhatri.precheck.view import confirmation_view, precheck_view
from chhatri.replay import views

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/merchants",
    tags=["precheck"],
    dependencies=[Depends(require_feature(FLAG))],
)

MERCHANT_ID_PATTERN: Final = r"^S-\d{4}$"
PRECHECK_ID_PATTERN: Final = r"^PC-\d{6,}$"
SLIPS_DIR_NAME: Final = "slips"
MAX_FORM_FIELDS: Final = 4  # file, lang, consent, notice_version
MerchantId = Annotated[str, Path(pattern=MERCHANT_ID_PATTERN)]
PrecheckId = Annotated[str, Path(pattern=PRECHECK_ID_PATTERN)]
Lang = Literal["hi", "en"]


class PrecheckSampleRequest(BaseModel):
    """JSON body of the read route: a sample slip by name (``{}`` is the scenario's own) and the guidance language."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    sample: Annotated[str | None, Field(pattern=SAMPLE_PATTERN)] = None
    lang: Lang | None = None
    consent: bool | None = None  # N6: the merchant's OK to read the slip, with the notice version they saw
    notice_version: Annotated[str | None, Field(max_length=32)] = None


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    action: Action


def _service(runtime: RuntimePort) -> SlipPrecheckService:
    service = precheck_service(cast(Any, runtime))
    if service is None:  # the flag is on (the route dependency checked it), so this is a wiring error
        raise ApiError(404, "not found")
    return service


@router.post("/{merchant_id}/slip-precheck", dependencies=[Depends(rate_limit("uploads"))])
async def read_slip(
    request: Request, state: StateDep, runtime: RuntimeDep, merchant_id: MerchantId
) -> dict[str, Any]:
    """Read one photo and run the gate: READY, RETAKE or NEEDS_TEAM."""
    merchant_or_404(state, merchant_id)
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type == "multipart/form-data":
        image, consent = await _uploaded(request)
    elif content_type == "application/json":
        body = _sample_request(await request.body())
        image, consent = _sample_image(state, runtime, body), (body.consent, body.notice_version)
    else:
        raise ApiError(415, "send multipart/form-data with a file, or JSON {sample}")
    try:  # both languages are always in the answer: the sheet picks one (data-model 5.3)
        require_slip_consent(runtime, merchant_id, consent=consent[0], notice_version=consent[1])
    except ConsentConflict as exc:
        raise ApiError(409, str(exc), code=exc.code) from exc
    service = _service(runtime)
    try:
        created = await service.precheck(merchant_id, image.data, image.mime)
    except PrecheckConflict as exc:
        raise ApiError(409, str(exc), code=exc.code) from exc
    except UncleanableImage as exc:
        raise ApiError(415, "image file is damaged or unreadable") from exc
    return ok(precheck_view(created, minimum=service.minimum))


@router.post(
    "/{merchant_id}/slip-precheck/{precheck_id}/confirm", dependencies=[Depends(rate_limit("messages"))]
)
async def confirm_slip(
    body: ConfirmRequest,
    state: StateDep,
    runtime: RuntimeDep,
    merchant_id: MerchantId,
    precheck_id: PrecheckId,
) -> dict[str, Any]:
    """Confirm the fields, answer the doctor question, or send the slip to the team. The engine decides the claim."""
    merchant_or_404(state, merchant_id)
    service = _service(runtime)
    try:
        done = await service.confirm(merchant_id, precheck_id, body.action, source="APP")
    except PrecheckNotFound as exc:
        raise ApiError(404, f"pre-check {precheck_id} not found") from exc
    except PrecheckConflict as exc:
        raise ApiError(409, str(exc), code=exc.code) from exc
    messages = [views.message_view(message) for message in done.messages]
    return ok(
        confirmation_view(
            done.precheck,
            outcome=done.outcome,
            case_id=done.case_id,
            messages=messages,
            consent=done.consent,
            doctor_pending=done.doctor_pending,
        )
    )


@router.get("/{merchant_id}/slip-precheck/open")
async def open_precheck(state: StateDep, runtime: RuntimeDep, merchant_id: MerchantId) -> dict[str, Any]:
    """What waits for the merchant now: the open check-in, its open pre-check, or the doctor question."""
    merchant_or_404(state, merchant_id)
    service = _service(runtime)
    first = runtime.orchestrator.open_silence(merchant_id)
    pc = service.open_for(merchant_id)
    waiting = pc is not None and pc.status is PrecheckStatus.AWAITING_CONSENT
    return ok(
        {
            "merchant_id": merchant_id,
            "checkin_open": first is not None,
            "first_silent_day": None if first is None else first.isoformat(),
            "precheck": None if pc is None or waiting else precheck_view(pc, minimum=service.minimum),
            "awaiting_consent": consent_view(consent_question(pc), status="ASKED", answered_at=None)
            if pc is not None and waiting
            else None,
        }
    )


async def _uploaded(request: Request) -> tuple[ValidatedImage, tuple[bool | None, str | None]]:
    async with request.form(max_files=1, max_fields=MAX_FORM_FIELDS) as form:
        upload = form.get("file")
        if not isinstance(upload, FormFile):
            raise ApiError(422, "invalid request", fields={"file": "an image file is required"})
        lang = form.get("lang")
        if lang not in (None, "hi", "en"):
            raise ApiError(422, "invalid request", fields={"lang": "must be hi or en"})
        consent = form.get("consent")
        if consent not in (None, "true", "false"):
            raise ApiError(422, "invalid request", fields={"consent": "must be true or false"})
        version = form.get("notice_version")
        agreed = None if consent is None else consent == "true"
        return validate_image(await read_limited(upload, MAX_IMAGE_BYTES)), (
            agreed,
            version if isinstance(version, str) else None,
        )


def _sample_request(raw: bytes) -> PrecheckSampleRequest:
    try:
        return PrecheckSampleRequest.model_validate_json(raw or b"{}")
    except ValidationError as exc:
        raise ApiError(422, "invalid request", fields=validation_fields(list(exc.errors()))) from exc


def _sample_image(state: AppStatePort, runtime: RuntimePort, body: PrecheckSampleRequest) -> ValidatedImage:
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
