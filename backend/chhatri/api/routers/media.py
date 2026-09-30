"""GET /api/media/{id} — stored slip images and voice notes (SPEC §19).

Bytes are served with the MIME type recorded when they were stored (derived from their content at
upload time), ``nosniff`` and inline disposition. They are never cached: ids restart on every
scenario load (SPEC §3), so ``MD-000001`` can be a different slip after a reload.
"""

from __future__ import annotations

from typing import Annotated, Final

from fastapi import APIRouter, Path
from fastapi.responses import Response

from chhatri.api.deps import RuntimeDep
from chhatri.api.errors import ApiError

router = APIRouter(prefix="/api", tags=["media"])

MEDIA_ID_PATTERN: Final = r"^MD-\d{6,}$"
CACHE_CONTROL: Final = "no-store"


@router.get("/media/{media_id}")
async def get_media(
    runtime: RuntimeDep, media_id: Annotated[str, Path(pattern=MEDIA_ID_PATTERN)]
) -> Response:
    """Raw media bytes (not an envelope: the console uses the URL in ``<img>``/``<audio>``)."""
    try:
        data, mime = runtime.store.media(media_id)
    except KeyError as exc:
        raise ApiError(404, f"media {media_id} not found") from exc
    headers = {
        "Cache-Control": CACHE_CONTROL,
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline",
    }
    return Response(content=data, media_type=mime, headers=headers)
