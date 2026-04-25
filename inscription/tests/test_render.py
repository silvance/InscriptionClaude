"""Crop + highlight renderer."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from inscription.render import (
    DEFAULT_PAD_PX,
    RING_STROKE_RGBA,
    crop_highlight,
)


def _checker(width: int = 400, height: int = 300) -> bytes:
    """Solid white PNG (cheap to decode, easy to diff)."""
    img = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _open(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png))


def test_no_bounding_rect_returns_input_unchanged() -> None:
    png = _checker()
    out = crop_highlight(png, bounding_rect=None, click_point=None)
    assert out is png  # same object, not just equal


def test_crop_is_smaller_than_source() -> None:
    png = _checker(1920, 1080)
    out = crop_highlight(png, bounding_rect=(100, 100, 200, 160), click_point=(150, 130))
    with _open(out) as img:
        w, h = img.size
    assert w < 1920
    assert h < 1080


def test_crop_pads_around_element() -> None:
    png = _checker(1000, 1000)
    rect = (400, 400, 500, 500)  # 100x100 element in the middle
    out = crop_highlight(png, bounding_rect=rect, click_point=(450, 450))
    with _open(out) as img:
        w, h = img.size
    # Expect roughly 100 + 2*DEFAULT_PAD_PX in each dimension.
    assert 100 + DEFAULT_PAD_PX <= w <= 100 + 2 * DEFAULT_PAD_PX + 40
    assert 100 + DEFAULT_PAD_PX <= h <= 100 + 2 * DEFAULT_PAD_PX + 40


def test_crop_is_clamped_to_image_bounds() -> None:
    png = _checker(400, 300)
    # Element at top-left corner; padding would go negative without clamp.
    out = crop_highlight(png, bounding_rect=(0, 0, 80, 60), click_point=(40, 30))
    with _open(out) as img:
        w, h = img.size
    # Clamp means no image dimension larger than the source.
    assert w <= 400
    assert h <= 300


def test_marker_pixel_is_drawn_on_the_crop() -> None:
    png = _checker(400, 300)
    # Click at (200, 150) inside a small rect around it.
    out = crop_highlight(png, bounding_rect=(180, 130, 220, 170), click_point=(200, 150))
    with _open(out) as img:
        # Scan a horizontal slice through the click point and confirm that
        # at least one pixel carries the ring's stroke colour.
        rgba = img.convert("RGBA")
        w, h = rgba.size
        row = rgba.crop((0, h // 2, w, h // 2 + 1))
        colors: set[tuple[int, ...]] = {
            c for c in (row.getpixel((x, 0)) for x in range(w)) if isinstance(c, tuple)
        }
    # We just need some ring pixel. Exact count depends on Pillow's
    # antialiasing; asserting presence of a reddish pixel is robust.
    assert any(
        len(c) >= 4 and c[0] > 200 and c[1] < 130 and c[2] < 130 and c[3] > 150 for c in colors
    ), f"expected a red ring pixel among {len(colors)} colours"


def test_degenerate_crop_falls_back_to_input() -> None:
    png = _checker(400, 300)
    # Rect fully off-image: clamping collapses it to <4 px, triggers fallback.
    out = crop_highlight(png, bounding_rect=(500, 500, 510, 510), click_point=(505, 505))
    assert out is png


def test_ring_stroke_colour_is_configurable() -> None:
    # Sanity check that the constant is exposed and a 4-tuple.
    assert len(RING_STROKE_RGBA) == 4
    with pytest.raises(TypeError):
        _ = RING_STROKE_RGBA + "x"  # type: ignore[operator]
