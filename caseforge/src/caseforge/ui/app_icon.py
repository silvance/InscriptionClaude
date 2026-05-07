"""Programmatic application icon for CaseForge.

The shell (rounded accent square + gradient + top highlight) is
shared across the suite via :func:`suite_common.ui.app_icon.build_app_icon`.
This module supplies the per-app emblem: a stylised case-folder
silhouette in white — a literal "case file" so the tool reads
immediately as the case-intake tool of the suite. Beside Inscription
(I + recording dot) and CaseGuide (checklist), the folder is the
visually distinct emblem.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath
from suite_common.ui.app_icon import DETAIL_MIN_SIZE
from suite_common.ui.app_icon import build_app_icon as _build

if TYPE_CHECKING:
    from suite_common.ui.style import Palette


def build_app_icon(palette: Palette | None = None) -> QIcon:
    """Return CaseForge's multi-resolution :class:`QIcon`."""
    return _build(_draw_folder, palette=palette)


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

    if size < DETAIL_MIN_SIZE:
        return

    # Two horizontal divider lines on the folder body — gestures at
    # case structure (name, reference, examiner, scope) without
    # cluttering the silhouette.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 38))
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
