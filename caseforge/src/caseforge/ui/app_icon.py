"""Programmatic application icon for CaseForge.

Drawn at runtime so palette tweaks flow into the icon without an
asset roundtrip and the bundle size stays tiny.

The mark is a rounded accent square with a stylised case-folder
silhouette in white — a literal "case file" so the tool reads
immediately as the case-intake tool of the suite. Beside Inscription
(I + recording dot) and CaseGuide (checklist), the folder is the
visually distinct emblem.

Cohesion: same shell shape and accent colour as the sibling apps; same
gradient + top highlight at sizes >= 32px so the suite reads as one
family in a taskbar.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
)

from caseforge.ui.style import LIGHT, Palette

_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
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
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        _draw_shell(painter, size, accent=p.accent, accent_hover=p.accent_hover)
        _draw_folder(painter, size)
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
        gradient = QLinearGradient(QPointF(0, 0), QPointF(0, size))
        gradient.setColorAt(0.0, QColor(accent_hover))
        gradient.setColorAt(1.0, QColor(accent))
        painter.fillPath(path, QBrush(gradient))
    else:
        painter.fillPath(path, QBrush(QColor(accent)))

    if size >= _DETAIL_MIN_SIZE:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 38))
        painter.drawRoundedRect(
            QRectF(size * 0.06, size * 0.06, size * 0.88, size * 0.20),
            radius * 0.5,
            radius * 0.5,
        )


def _draw_folder(painter: QPainter, size: int) -> None:
    """White case-folder silhouette: tab on the upper-left, body below."""
    # Folder geometry: roughly 64% of the icon, centred, with a tab
    # cut into the top-left quadrant. Coordinates are normalised to
    # ``size`` so the mark scales cleanly.
    margin_x = size * 0.18
    body_top = size * 0.34
    body_bottom = size * 0.78
    body_left = margin_x
    body_right = size - margin_x

    tab_top = size * 0.26
    tab_left = body_left
    tab_right = size * 0.50
    tab_bottom = body_top
    corner = size * 0.06

    path = QPainterPath()
    # Start at the tab's top-left, traced clockwise around the whole
    # silhouette — top of tab, tab's right slope, top of body, right
    # of body, bottom, back up the left side.
    path.moveTo(tab_left + corner, tab_top)
    path.lineTo(tab_right - corner, tab_top)
    # Diagonal slope from the tab down to the body — gives the
    # silhouette its "manilla folder" rhythm rather than a stack of
    # rectangles.
    path.lineTo(tab_right + corner, tab_bottom - corner * 0.2)
    path.lineTo(body_right - corner, body_top)
    path.quadTo(body_right, body_top, body_right, body_top + corner)
    path.lineTo(body_right, body_bottom - corner)
    path.quadTo(body_right, body_bottom, body_right - corner, body_bottom)
    path.lineTo(body_left + corner, body_bottom)
    path.quadTo(body_left, body_bottom, body_left, body_bottom - corner)
    path.lineTo(body_left, tab_top + corner)
    path.quadTo(body_left, tab_top, tab_left + corner, tab_top)
    path.closeSubpath()

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("white"))
    painter.drawPath(path)

    if size < _DETAIL_MIN_SIZE:
        return

    # Two horizontal divider lines on the folder body — gestures at
    # case structure (name, reference, examiner, scope) without
    # cluttering the silhouette.
    line_color = QColor(0, 0, 0, 38)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(line_color)
    line_height = max(1.0, size * 0.025)
    line_inset = size * 0.06
    line_x = body_left + line_inset
    line_w = (body_right - body_left) - 2 * line_inset
    for offset in (size * 0.10, size * 0.18):
        painter.drawRoundedRect(
            QRectF(line_x, body_top + offset, line_w, line_height),
            line_height / 2,
            line_height / 2,
        )
