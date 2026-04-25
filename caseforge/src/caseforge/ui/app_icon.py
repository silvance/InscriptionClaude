"""Programmatic application icon for CaseForge.

Same drawing technique as Inscription's icon — rounded accent square
with a serif glyph — but the letter is **C** so the two apps are
distinguishable in the taskbar at a glance.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap

from caseforge.ui.style import LIGHT, Palette

_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
_HIGHLIGHT_MIN_SIZE = 32


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

        radius = size * 0.22
        body = QRectF(0.5, 0.5, size - 1, size - 1)
        path = QPainterPath()
        path.addRoundedRect(body, radius, radius)
        painter.fillPath(path, QBrush(QColor(p.accent)))

        if size >= _HIGHLIGHT_MIN_SIZE:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 40))
            painter.drawRoundedRect(
                QRectF(size * 0.08, size * 0.08, size * 0.84, size * 0.18),
                radius * 0.5,
                radius * 0.5,
            )

        painter.setPen(QColor("white"))
        font = QFont("Georgia", max(8, int(size * 0.62)))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(body, Qt.AlignmentFlag.AlignCenter, "C")
    finally:
        painter.end()
    return pm
