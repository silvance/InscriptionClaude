"""Screenshot post-processing: crop around the clicked element + marker.

The HTML exporter and the UI editor both want a tighter, annotated image
rather than the full-screen PNG we capture. This module does that work
purely in-memory with Pillow — it does not touch Qt so it runs in any
context (export pipeline, CLI, future headless render).

Inputs:

- the full-screen PNG bytes,
- the UIA bounding rect of the clicked element (screen-space pixels),
- the click point (also screen-space),
- optional padding around the element.

Output: PNG bytes of a cropped image with a click ring drawn on it. If
no bounding rect is supplied or something else goes wrong, we return the
original bytes — a worse-looking fallback is better than a broken export.
"""

from __future__ import annotations

import io
import logging

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

#: Extra pixels around the resolved element's bbox. Enough to keep the
#: surrounding widget/label legible without dominating the crop.
DEFAULT_PAD_PX = 60

#: Below this width or height, the crop is degenerate enough that falling
#: back to the full screenshot looks better than a smudge.
MIN_CROP_DIMENSION_PX = 4

#: Click ring geometry. An outer stroke with a translucent fill makes the
#: click point visible without obscuring the target underneath.
RING_RADIUS_PX = 18
RING_STROKE_PX = 3
RING_STROKE_RGBA = (255, 68, 68, 255)
RING_FILL_RGBA = (255, 68, 68, 90)


def crop_highlight(
    png_bytes: bytes,
    *,
    bounding_rect: tuple[int, int, int, int] | None,
    click_point: tuple[int, int] | None,
    pad_px: int = DEFAULT_PAD_PX,
) -> bytes:
    """Return PNG bytes cropped around ``bounding_rect`` with a click ring.

    The click ring is only drawn when ``click_point`` is supplied; falls
    back to returning ``png_bytes`` unchanged when no rect is supplied or
    when cropping/drawing fails.
    """
    if bounding_rect is None:
        return png_bytes
    try:
        with Image.open(io.BytesIO(png_bytes)) as img:
            img.load()
            rgba = img.convert("RGBA")
    except Exception:
        logger.exception("crop_highlight: failed to decode PNG")
        return png_bytes

    crop_box = _compute_crop_box(
        bounding_rect=bounding_rect,
        image_size=rgba.size,
        click_point=click_point,
        pad_px=pad_px,
    )
    if crop_box is None:
        return png_bytes

    cropped = rgba.crop(crop_box)
    if click_point is not None:
        _draw_click_ring(cropped, crop_origin=(crop_box[0], crop_box[1]), click_point=click_point)

    out = io.BytesIO()
    cropped.save(out, format="PNG")
    return out.getvalue()


def _compute_crop_box(
    *,
    bounding_rect: tuple[int, int, int, int],
    image_size: tuple[int, int],
    click_point: tuple[int, int] | None,
    pad_px: int,
) -> tuple[int, int, int, int] | None:
    """Pad the element rect, include the click point, clamp to the image."""
    img_w, img_h = image_size
    left, top, right, bottom = bounding_rect
    # Pad outward.
    left -= pad_px
    top -= pad_px
    right += pad_px
    bottom += pad_px
    # Include the click point (it can fall just outside the reported bbox
    # on widgets whose hit-test region is larger than the visual).
    if click_point is not None:
        cx, cy = click_point
        left = min(left, cx - RING_RADIUS_PX)
        top = min(top, cy - RING_RADIUS_PX)
        right = max(right, cx + RING_RADIUS_PX)
        bottom = max(bottom, cy + RING_RADIUS_PX)
    # Clamp to image bounds.
    left = max(0, left)
    top = max(0, top)
    right = min(img_w, right)
    bottom = min(img_h, bottom)
    if right - left < MIN_CROP_DIMENSION_PX or bottom - top < MIN_CROP_DIMENSION_PX:
        return None
    return (left, top, right, bottom)


def _draw_click_ring(
    image: Image.Image,
    *,
    crop_origin: tuple[int, int],
    click_point: tuple[int, int],
) -> None:
    """Draw a translucent ring on ``image`` at the translated click point."""
    ox, oy = crop_origin
    cx, cy = click_point
    rx, ry = cx - ox, cy - oy
    r = RING_RADIUS_PX
    bbox = (rx - r, ry - r, rx + r, ry + r)
    draw = ImageDraw.Draw(image, mode="RGBA")
    draw.ellipse(bbox, fill=RING_FILL_RGBA, outline=RING_STROKE_RGBA, width=RING_STROKE_PX)
