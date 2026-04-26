"""Programmatic application icon for Inscription.

Drawn at runtime from a small QPainter program rather than shipped as
binary asset, so palette tweaks flow into the icon without an asset
roundtrip and the bundle size stays tiny.

The mark is a rounded accent square with two complementary white
elements:

- A heavy slab-serif "I" centred — the slab serifs read as the
  chiselled, archival aesthetic the name evokes.
- A small recording dot tucked into the upper-right — the visual
  reminder that Inscription is *the recorder* in the suite.

The shell carries a subtle vertical gradient + inner top highlight to
give the icon a finished feel at large sizes (taskbars, dock previews,
about dialogs); both effects fade out below 32px so the small-sized
icon stays legible against busy backgrounds.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from inscription.ui.style import LIGHT, Palette

#: Sizes we render the icon at. Covers Windows taskbar (16, 24, 32, 48,
#: 256) and macOS dock (32, 64, 128, 256, 512).
_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

#: Below this we skip the inner highlight + gradient — they look muddy
#: at small sizes where every pixel counts.
_DETAIL_MIN_SIZE = 32


def build_app_icon(palette: Palette | None = None) -> QIcon:
    """Return a multi-resolution :class:`QIcon` rendered from scratch."""
    p = palette or LIGHT
    icon = QIcon()
    for size in _SIZES:
        icon.addPixmap(_render(size, p))
    return icon


def _render(size: int, p: Palette) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    try:
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
        )
        _draw_shell(painter, size, accent=p.accent, accent_hover=p.accent_hover)
        _draw_emblem(painter, size)
    finally:
        painter.end()
    return pm


def _draw_shell(painter: QPainter, size: int, *, accent: str, accent_hover: str) -> None:
    """Rounded accent square with gradient + top highlight."""
    radius = size * 0.22
    body = QRectF(0.5, 0.5, size - 1, size - 1)
    path = QPainterPath()
    path.addRoundedRect(body, radius, radius)

    if size >= _DETAIL_MIN_SIZE:
        # Vertical gradient: lighter at top, the configured accent at
        # bottom. Reads as ambient lighting, not a colour shift.
        gradient = QLinearGradient(QPointF(0, 0), QPointF(0, size))
        top = QColor(accent_hover)
        bottom = QColor(accent)
        gradient.setColorAt(0.0, top)
        gradient.setColorAt(1.0, bottom)
        painter.fillPath(path, QBrush(gradient))
    else:
        painter.fillPath(path, QBrush(QColor(accent)))

    if size >= _DETAIL_MIN_SIZE:
        # Inner highlight along the top: a thin lighter band that
        # gives the icon a slight 3D feel without the gradient
        # carrying that work alone.
        highlight = QColor(255, 255, 255, 38)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(highlight)
        painter.drawRoundedRect(
            QRectF(size * 0.06, size * 0.06, size * 0.88, size * 0.20),
            radius * 0.5,
            radius * 0.5,
        )


def _draw_emblem(painter: QPainter, size: int) -> None:
    """Slab-serif ``I`` plus a recording dot in the upper-right."""
    # The "I". Bold serif font reads as carved / archival rather than a
    # generic sans I. Centred slightly above the geometric centre to
    # leave visual room for the recording dot above it.
    painter.setPen(QColor("white"))
    font = QFont("Georgia", max(8, int(size * 0.58)))
    font.setBold(True)
    painter.setFont(font)
    text_rect = QRectF(0, size * 0.04, size, size)
    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, "I")

    if size < _DETAIL_MIN_SIZE:
        # Skip the recording dot at small sizes; it muddies the I.
        return

    # Recording dot — solid white circle with a faint outer ring so
    # it reads against the gradient rather than blending in. Sits in
    # the upper-right quadrant.
    dot_diameter = size * 0.16
    dot_x = size * 0.72
    dot_y = size * 0.16
    dot_rect = QRectF(dot_x, dot_y, dot_diameter, dot_diameter)

    ring = QColor(255, 255, 255, 90)
    painter.setPen(QPen(ring, max(1.0, size * 0.012)))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(dot_rect.adjusted(-size * 0.02, -size * 0.02, size * 0.02, size * 0.02))

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("white"))
    painter.drawEllipse(dot_rect)
