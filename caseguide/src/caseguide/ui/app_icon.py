"""Programmatic application icon for CaseGuide.

Drawn at runtime so palette tweaks flow into the icon without an
asset roundtrip and the bundle size stays tiny.

The mark is a rounded accent square with a small white checklist —
three rows whose top row carries a leading checkmark. CaseGuide is
the suggestions / coach tool of the suite, so a checklist reads
immediately while staying visually distinct from Inscription's "I"
plus recording dot and CaseForge's case-folder silhouette.

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
    QPen,
    QPixmap,
)

from caseguide.ui.style import LIGHT, Palette

_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
_DETAIL_MIN_SIZE = 32

#: A neutral darker tone for the checkmark stroke. Reads as "marked"
#: against the white box without needing access to the live palette
#: accent — picked once to harmonise with both the LIGHT and DARK
#: shell variants the rest of the QSS supports.
_CHECK_STROKE = QColor(20, 60, 110)


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
        _draw_checklist(painter, size)
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


def _draw_checklist(painter: QPainter, size: int) -> None:
    """Three white rows (box + label) with a leading checkmark on row one."""
    rows = 3
    row_height = size * 0.10
    row_gap = size * 0.07
    block_height = rows * row_height + (rows - 1) * row_gap
    start_y = (size - block_height) / 2

    box_size = row_height
    inset_x = size * 0.20
    label_left = inset_x + box_size + size * 0.07
    label_right = size - inset_x
    label_height = row_height * 0.78
    label_y_offset = (row_height - label_height) / 2

    painter.setPen(Qt.PenStyle.NoPen)

    for i in range(rows):
        row_y = start_y + i * (row_height + row_gap)
        radius = max(1.0, size * 0.018)
        painter.setBrush(QColor("white"))
        painter.drawRoundedRect(
            QRectF(inset_x, row_y, box_size, box_size), radius, radius
        )
        # Label brightness drops on lower rows so the eye lands on the
        # checked top row first — the implicit reading order of the
        # mark.
        opacity = (1.0, 0.78, 0.62)[i]
        painter.setBrush(QColor(255, 255, 255, int(255 * opacity)))
        painter.drawRoundedRect(
            QRectF(
                label_left,
                row_y + label_y_offset,
                label_right - label_left,
                label_height,
            ),
            label_height / 2,
            label_height / 2,
        )

    if size < _DETAIL_MIN_SIZE:
        # Below 32px the check stroke fights the box edge and the row
        # spacing collapses; the bare three rows still read as
        # "checklist" without it.
        return

    box_y = start_y
    pen = QPen(_CHECK_STROKE)
    pen.setWidthF(max(1.2, size * 0.030))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Tick: from lower-left of the box, down to the elbow, up to
    # upper-right. Coordinates expressed as a fraction of box_size
    # so the tick scales with the row height.
    tick = QPainterPath()
    tick.moveTo(inset_x + box_size * 0.18, box_y + box_size * 0.55)
    tick.lineTo(inset_x + box_size * 0.42, box_y + box_size * 0.78)
    tick.lineTo(inset_x + box_size * 0.84, box_y + box_size * 0.28)
    painter.drawPath(tick)
