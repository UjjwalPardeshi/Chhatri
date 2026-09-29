"""Server-Sent Events streaming (SPEC §19.1).

SSE endpoint at GET /api/stream using sse-starlette EventSourceResponse.
Frames: "event: <type>", "id: <id>", "data: {id,type,at,data}".
Keep-alive ping every 15s.
Last-Event-ID header resumes from history after that id.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, AsyncGenerator

from sse_starlette import EventSourceResponse

if TYPE_CHECKING:
    from chhatri.replay.state import Runtime

logger = logging.getLogger(__name__)


async def event_stream(runtime: Runtime, last_event_id: int = 0) -> AsyncGenerator[str, None]:
    """Generate SSE event stream.

    Yields lines in sse-starlette format:
      event: <type>\n
      id: <event_id>\n
      data: <json>\n
      \n

    Resumes from history after last_event_id.
    """
    bus = runtime.bus

    # Replay history after last_event_id
    history = bus.history(after_id=last_event_id)
    for event in history:
        line = f"event: {event.type}\n"
        line += f"id: {event.id}\n"
        line += f"data: {json.dumps(event.to_wire())}\n\n"
        yield line

    # Live subscription
    async for event in bus.subscribe(after_id=last_event_id):
        line = f"event: {event.type}\n"
        line += f"id: {event.id}\n"
        line += f"data: {json.dumps(event.to_wire())}\n\n"
        yield line


async def sse_endpoint(
    runtime: Runtime, last_event_id: str | None = None
) -> EventSourceResponse:
    """SSE endpoint handler (SPEC §19.1).

    Returns EventSourceResponse with ping=15 (keep-alive ping every 15s).
    """
    after_id = 0
    if last_event_id:
        try:
            after_id = int(last_event_id)
        except ValueError:
            pass

    return EventSourceResponse(
        event_stream(runtime, last_event_id=after_id),
        ping=15,
        ping_message_factory=lambda: ":\n\n",  # SSE keep-alive comment
    )
