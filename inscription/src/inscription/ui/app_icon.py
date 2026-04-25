"""Programmatic application icon.

We don't ship a binary asset; the icon is drawn at runtime from a tiny
QPainter program. The mark is a rounded square in the accent blue with a
white "I" carved out of it — a nod to "Inscription" and the chiseled-in
look that fits the forensic / archival framing.

A multi-resolution :class:`QIcon` is built so the OS picks the right
size for window decorations, the taskbar, and Alt+Tab switchers.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap

from inscription.ui.style import LIGHT, Palette

#: Sizes we render the icon at. Covers Windows taskbar (16, 24, 32, 48,
#: 256) and macOS dock (32, 64, 128, 256, 512).
_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

#: Below this we skip the inner highlight; it just looks muddy.
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

        # Rounded-square background in the accent colour.
        radius = size * 0.22
        body = QRectF(0.5, 0.5, size - 1, size - 1)
        path = QPainterPath()
        path.addRoundedRect(body, radius, radius)

        painter.fillPath(path, QBrush(QColor(p.accent)))

        # Subtle inner highlight along the top edge — gives the mark a
        # slight 3D feel at larger sizes without looking dated.
        if size >= _HIGHLIGHT_MIN_SIZE:
            highlight = QColor(255, 255, 255, 40)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(highlight)
            painter.drawRoundedRect(
                QRectF(size * 0.08, size * 0.08, size * 0.84, size * 0.18),
                radius * 0.5,
                radius * 0.5,
            )

        # White "I" centered. Use a serif glyph so it reads as
        # "Inscription / inscribed" rather than a generic sans I.
        painter.setPen(QColor("white"))
        font = QFont("Georgia", max(8, int(size * 0.62)))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(body, Qt.AlignmentFlag.AlignCenter, "I")
    finally:
        painter.end()
    return pm
