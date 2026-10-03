"""GET /api/media/{id} — stored slip images and voice notes (SPEC §19).

Bytes are served with the MIME type recorded when they were stored (derived from their content at
upload time), ``nosniff`` and inline disposition. They are never cached: ids restart on every
scenario load (SPEC §3), so ``MD-000001`` can be a different slip after a reload.

The route has no token (the console's ``<img>`` uses the URL), so an image is always served as a metadata-free copy
(`precheck.clean.clean_image`): no EXIF (a phone photo's place and time), XMP, ICC profile or PNG text chunk (a sample
slip's answer key), whichever path stored it. An image that cannot be cleaned (undecodable, or a kind other than
JPEG, PNG or WebP) is not served. Audio is served as stored.
"""

from __future__ import annotations

import asyncio
import hashlib
import threading
from collections import OrderedDict
from typing import Annotated, Final

from fastapi import APIRouter, Path
from fastapi.responses import Response

from chhatri.api.deps import RuntimeDep
from chhatri.api.errors import ApiError
from chhatri.precheck.clean import UncleanableImage, clean_image

router = APIRouter(prefix="/api", tags=["media"])

MEDIA_ID_PATTERN: Final = r"^MD-\d{6,}$"
CACHE_CONTROL: Final = "no-store"
IMAGE_PREFIX: Final = (
    "image/"  # every image is cleaned; a kind clean_image cannot write (HEIC, GIF) is not served
)
CLEAN_CACHE_SIZE: Final = 64


class _CleanCache:
    """The last few cleaned copies, keyed by the content's hash (a re-render of the chat does not re-encode)."""

    def __init__(self, size: int) -> None:
        self._size = size
        self._items: OrderedDict[tuple[str, str], bytes] = OrderedDict()
        self._lock = threading.Lock()

    def cleaned(self, data: bytes, mime: str) -> bytes:
        key = (hashlib.sha256(data).hexdigest(), mime)
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return self._items[key]
        clean, _ = clean_image(data, mime)
        with self._lock:
            self._items[key] = clean
            while len(self._items) > self._size:
                self._items.popitem(last=False)
        return clean


_CLEANED: Final = _CleanCache(CLEAN_CACHE_SIZE)


@router.get("/media/{media_id}")
async def get_media(
    runtime: RuntimeDep, media_id: Annotated[str, Path(pattern=MEDIA_ID_PATTERN)]
) -> Response:
    """Media bytes (not an envelope: the console uses the URL in ``<img>``/``<audio>``); images metadata-free."""
    try:
        data, mime = runtime.store.media(media_id)
    except KeyError as exc:
        raise ApiError(404, f"media {media_id} not found") from exc
    if mime.startswith(IMAGE_PREFIX):
        try:
            data = await asyncio.to_thread(_CLEANED.cleaned, data, mime)
        except UncleanableImage as exc:
            raise ApiError(404, f"media {media_id} not available") from exc
    headers = {
        "Cache-Control": CACHE_CONTROL,
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline",
    }
    return Response(content=data, media_type=mime, headers=headers)
