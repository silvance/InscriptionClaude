"""Programmatic application icon for CaseGuide.

The shell (rounded accent square + gradient + top highlight) is
shared across the suite via :func:`suite_common.ui.app_icon.build_app_icon`.
This module supplies the per-app emblem: three checklist rows in
white with a leading checkmark on row one. Beside Inscription
(I + recording dot) and CaseForge (case folder), the checklist
reads immediately as the suggestion-coach tool of the suite.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen
from suite_common.ui.app_icon import DETAIL_MIN_SIZE
from suite_common.ui.app_icon import build_app_icon as _build

if TYPE_CHECKING:
    from suite_common.ui.style import Palette

#: A neutral darker tone for the checkmark stroke. Reads as "marked"
#: against the white box without needing access to the live palette
#: accent — picked once to harmonise with both the LIGHT and DARK
#: shell variants the rest of the QSS supports.
_CHECK_STROKE = QColor(20, 60, 110)


def build_app_icon(palette: Palette | None = None) -> QIcon:
    """Return CaseGuide's multi-resolution :class:`QIcon`."""
    return _build(_draw_checklist, palette=palette)


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
        # checked top row first — the implicit reading order of the mark.
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

    if size < DETAIL_MIN_SIZE:
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
    # upper-right. Coordinates expressed as a fraction of box_size so
    # the tick scales with the row height.
    tick = QPainterPath()
    tick.moveTo(inset_x + box_size * 0.18, box_y + box_size * 0.55)
    tick.lineTo(inset_x + box_size * 0.42, box_y + box_size * 0.78)
    tick.lineTo(inset_x + box_size * 0.84, box_y + box_size * 0.28)
    painter.drawPath(tick)
