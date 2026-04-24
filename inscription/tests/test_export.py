"""HTML export."""

from __future__ import annotations

import io
import struct
import zlib
from typing import TYPE_CHECKING

from PIL import Image

from inscription.export import export_html
from inscription.model import EventKind, ResolvedElement, utcnow
from inscription.steps import generate_steps
from inscription.storage import SessionRepository

if TYPE_CHECKING:
    from pathlib import Path


def _solid_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Build a minimal PNG of a solid colour."""
    img = Image.new("RGB", (width, height), rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


_TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000b49444154789c6360000200000500017a5eab3f0000000049454e44ae"
    "426082"
)


def _seed_click(
    repo: SessionRepository,
    *,
    png_bytes: bytes = _TINY_PNG,
    width: int = 1,
    height: int = 1,
    bounding_rect: tuple[int, int, int, int] | None = None,
    click_xy: tuple[int, int] = (1, 1),
) -> None:
    shot_dir = repo.session.screenshots_dir
    shot_dir.mkdir(exist_ok=True)
    shot_path = shot_dir / "click.png"
    shot_path.write_bytes(png_bytes)
    shot = repo.add_screenshot(
        relative_path="screenshots/click.png",
        captured_at=utcnow(),
        width=width,
        height=height,
        sha256="abc",
    )
    resolved = repo.add_resolved_element(
        ResolvedElement(
            id=None,
            name="Save",
            control_type="Button",
            confidence=0.9,
            method="uia",
            bounding_rect=bounding_rect,
        )
    )
    repo.append_event(
        kind=EventKind.CLICK,
        button="left",
        x=click_xy[0],
        y=click_xy[1],
        window_title="App",
        process_name="app.exe",
        screenshot_id=shot.id,
        resolved_element_id=resolved.id,
    )


def test_export_html_writes_self_contained_document(tmp_path: Path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="Exportable")
    try:
        _seed_click(repo)
        generate_steps(repo)
        doc = export_html(repo)
    finally:
        repo.close()

    assert doc.path.exists()
    text = doc.path.read_text(encoding="utf-8")
    assert "<!doctype html>" in text
    assert "Exportable" in text
    assert "Save" in text
    assets = doc.path.parent / "assets"
    assert assets.exists()
    assert any(assets.iterdir())


def test_export_crops_screenshot_when_bounding_rect_available(tmp_path: Path) -> None:
    repo = SessionRepository.create(workspace_root=tmp_path, name="CropMe")
    try:
        full = _solid_png(800, 600, (255, 255, 255))
        _seed_click(
            repo,
            png_bytes=full,
            width=800,
            height=600,
            bounding_rect=(300, 250, 400, 310),
            click_xy=(350, 280),
        )
        generate_steps(repo)
        doc = export_html(repo)
    finally:
        repo.close()

    # The staged asset should be smaller than the source screenshot and
    # should not byte-match it (the ring was drawn on top).
    assets = list((doc.path.parent / "assets").glob("step-*.png"))
    assert assets, "expected at least one step asset"
    staged = assets[0]
    assert staged.read_bytes() != full
    with Image.open(staged) as img:
        w, h = img.size
    assert w < 800
    assert h < 600


def _png_dimensions(data: bytes) -> tuple[int, int]:
    # Lightweight sanity helper independent of Pillow — PNG IHDR at offset 8.
    _ = zlib  # keep the import used (zlib is stdlib, safe)
    w, h = struct.unpack(">II", data[16:24])
    return w, h


def test_png_dimensions_helper_works() -> None:
    data = _solid_png(7, 5, (0, 0, 0))
    assert _png_dimensions(data) == (7, 5)
