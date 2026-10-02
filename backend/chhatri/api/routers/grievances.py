"""The grievance ladder (N5, H22): list, and open, escalate or resolve (data-model-and-api section 5.4, fs-06).

Behind the flag ``n5_grievances``: while it is off both routes answer the ordinary 404 ``not_found``. There is no
merchant login in the prototype, so the routes need no token, like the chat route they sit beside; they share its
``messages`` rate limit on the write. A dispute opens the same DISPUTE case the chat path opens.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Final, Literal, cast

from fastapi import APIRouter, Depends, Path, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from chhatri.api.deps import RuntimeDep, StateDep, merchant_or_404, rate_limit, require_feature
from chhatri.api.envelope import ok, ok_list
from chhatri.api.errors import ApiError
from chhatri.cases.grievances import GrievanceConflict, GrievanceInvalid, GrievanceService
from chhatri.domain.models import Case

router = APIRouter(
    prefix="/api/merchants", tags=["grievances"], dependencies=[Depends(require_feature("n5_grievances"))]
)

MERCHANT_ID_PATTERN: Final = r"^S-\d{4}$"
MAX_TEXT_CHARS: Final = 500
MerchantId = Annotated[str, Path(pattern=MERCHANT_ID_PATTERN)]
REQUIRED: Final[dict[str, tuple[str, ...]]] = {
    "OPEN": ("topic",),
    "ESCALATE": ("grievance_id", "escalate_from"),
    "RESOLVE": ("grievance_id",),
}


class GrievanceRequest(BaseModel):
    """One body for the three actions; the fields each action needs are checked below (422 with ``fields``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: Literal["OPEN", "ESCALATE", "RESOLVE"]
    topic: str | None = Field(default=None, max_length=40)
    text: str = Field(default="", max_length=MAX_TEXT_CHARS)
    lang: str = Field(default="hi", pattern=r"^[a-z]{2}$")
    decision_id: str | None = Field(default=None, pattern=r"^D-\d{6,}$")
    grievance_id: str | None = Field(default=None, pattern=r"^GR-\d{6,}$")
    escalate_from: str | None = Field(default=None, max_length=40)
    filed_on: date | None = None

    @model_validator(mode="after")
    def _needs_its_fields(self) -> GrievanceRequest:
        missing = [name for name in REQUIRED[self.action] if getattr(self, name) is None]
        if missing:
            raise ValueError(f"{', '.join(missing)} required for {self.action}")
        return self


def _service(runtime: Any) -> GrievanceService:
    return GrievanceService(
        store=runtime.store,
        audit=runtime.audit,
        ids=runtime.ids,
        sla_hours=runtime.static.rules.dispute_sla_hours,
    )


@router.get("/{merchant_id}/grievances")
async def list_grievances(state: StateDep, runtime: RuntimeDep, merchant_id: MerchantId) -> dict[str, Any]:
    """The merchant's grievances, newest first, each with its ladder, clocks and next action."""
    merchant_or_404(state, merchant_id)
    items = _service(runtime).list_for(merchant_id, now=runtime.clock.now())
    return ok_list(items, total=len(items), limit=len(items), offset=0)


@router.post("/{merchant_id}/grievances", dependencies=[Depends(rate_limit("messages"))])
async def act_on_grievance(
    state: StateDep, runtime: RuntimeDep, merchant_id: MerchantId, body: GrievanceRequest, response: Response
) -> dict[str, Any]:
    """OPEN (201, or 200 for a repeat), ESCALATE or RESOLVE; the grievance comes back."""
    merchant_or_404(state, merchant_id)
    service = _service(runtime)
    now = runtime.clock.now()
    try:
        if body.action == "OPEN":
            return await _open(service, runtime, merchant_id, body, response, now)
        if body.action == "ESCALATE":
            updated = service.escalate(
                merchant_id=merchant_id,
                grievance_id=cast(str, body.grievance_id),
                escalate_from=cast(str, body.escalate_from),
                filed_on=body.filed_on,
                now=now,
            )
        else:
            updated = service.resolve(
                merchant_id=merchant_id, grievance_id=cast(str, body.grievance_id), now=now
            )
    except GrievanceInvalid as exc:
        raise ApiError(422, str(exc), fields=exc.fields) from exc
    except GrievanceConflict as exc:
        raise ApiError(409, str(exc)) from exc
    except KeyError as exc:
        raise ApiError(404, "grievance not found") from exc
    return ok(service.get_view(updated.id, now=now))


async def _open(
    service: GrievanceService,
    runtime: Any,
    merchant_id: str,
    body: GrievanceRequest,
    response: Response,
    now: Any,
) -> dict[str, Any]:
    async def notify(case: Case, already_open: bool) -> None:
        await runtime.conversation.notify_dispute_opened(case, already_open=already_open)

    result = await service.open(
        merchant_id=merchant_id,
        topic=cast(str, body.topic),
        text=body.text,
        lang=body.lang,
        decision_id=body.decision_id,
        now=now,
        open_dispute=runtime.orchestrator.open_dispute,
        notify=notify,
    )
    response.status_code = 201 if result.created else 200
    return ok(service.get_view(result.grievance.id, now=now))
