"""Strip hidden metadata from a slip photo before any provider sees it (fs-02 7.3.1 step 2, ADR 0009).

The pixels are decoded and written again with no EXIF, XMP, ICC profile or PNG text chunk. The committed sample slips
carry a text chunk (`chhatri:slip`) with their answer key, and a phone photo carries the place and time it was taken:
neither may leave the machine. The camera's rotation is applied first so a portrait photo stays upright. The cleaned copy
is what is stored for the officer and what a live reader receives. Only the simulated reader gets the original, because it
reads that chunk and its input never leaves the machine.
"""

from __future__ import annotations

import io
from typing import Final

from PIL import Image, ImageOps

JPEG_QUALITY: Final = 92
_SAVE_FORMAT: Final = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
_KEEP_MODES: Final = frozenset({"L", "RGB", "RGBA"})


class UncleanableImage(ValueError):
    """The bytes could not be decoded or written again."""


def clean_image(data: bytes, mime: str) -> tuple[bytes, str]:
    """`(bytes, mime)` of the same picture with every metadata block removed. Raises `UncleanableImage`."""
    save_format = _SAVE_FORMAT.get(mime)
    if save_format is None:
        raise UncleanableImage(f"unsupported image type {mime}")
    try:
        with Image.open(io.BytesIO(data)) as opened:
            upright = ImageOps.exif_transpose(opened)
            pixels = _plain(upright, jpeg=save_format == "JPEG")
            fresh = Image.new(pixels.mode, pixels.size)
            fresh.paste(pixels)
            out = io.BytesIO()
            options = {"quality": JPEG_QUALITY} if save_format == "JPEG" else {}
            fresh.save(out, format=save_format, **options)
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise UncleanableImage(type(exc).__name__) from exc
    return out.getvalue(), mime


def _plain(image: Image.Image, *, jpeg: bool) -> Image.Image:
    has_alpha = "A" in image.getbands() or "transparency" in image.info
    if jpeg:
        return image if image.mode in {"L", "RGB"} else image.convert("RGB")
    if image.mode in _KEEP_MODES:
        return image
    return image.convert("RGBA" if has_alpha else "RGB")
