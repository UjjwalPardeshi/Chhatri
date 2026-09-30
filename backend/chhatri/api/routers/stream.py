"""GET /api/stream — Server-Sent Events (SPEC §19.1).

Resumes after ``Last-Event-ID`` (the header a browser ``EventSource`` sends on reconnect). A console
that opens a fresh ``EventSource`` after a drop cannot set headers, so the same value is also
accepted as the ``last_event_id`` query parameter; the header wins when both are present. The
stream uses the process-wide bus, so it works before any scenario is loaded.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query, Request
from sse_starlette import EventSourceResponse

from chhatri.api.deps import StateDep
from chhatri.api.sse import StreamHub, parse_last_event_id, stream_response

router = APIRouter(prefix="/api", tags=["stream"])


@router.get("/stream")
async def stream(
    request: Request,
    state: StateDep,
    last_event_id_header: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    last_event_id: Annotated[str | None, Query()] = None,
) -> EventSourceResponse:
    """Open the event stream (SPEC §19.1)."""
    hub: StreamHub = request.app.state.stream_hub
    raw = last_event_id_header if last_event_id_header is not None else last_event_id
    return stream_response(state.bus, hub, parse_last_event_id(raw))
