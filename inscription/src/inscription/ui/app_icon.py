"""Programmatic application icon for Inscription.

The shell (rounded accent square + gradient + top highlight) is
shared across the suite via :func:`suite_common.ui.app_icon.build_app_icon`.
This module supplies the per-app emblem: a heavy slab-serif "I"
centred — the slab serifs read as the chiselled, archival aesthetic
the name evokes — plus a small recording dot in the upper-right
that signals Inscription's role as *the recorder* in the suite.

The recording dot fades out below 32px so the small-sized icon
stays legible against busy backgrounds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen
from suite_common.ui.app_icon import DETAIL_MIN_SIZE
from suite_common.ui.app_icon import build_app_icon as _build

if TYPE_CHECKING:
    from suite_common.ui.style import Palette


def build_app_icon(palette: Palette | None = None) -> QIcon:
    """Return Inscription's multi-resolution :class:`QIcon`."""
    return _build(_draw_emblem, palette=palette)


def _draw_emblem(painter: QPainter, size: int) -> None:
    """Slab-serif ``I`` plus a recording dot in the upper-right."""
    # The "I". Bold serif font reads as carved / archival rather than
    # a generic sans I. Centred slightly above the geometric centre
    # to leave visual room for the recording dot above it.
    painter.setPen(QColor("white"))
    font = QFont("Georgia", max(8, int(size * 0.58)))
    font.setBold(True)
    painter.setFont(font)
    text_rect = QRectF(0, size * 0.04, size, size)
    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, "I")

    if size < DETAIL_MIN_SIZE:
        # Skip the recording dot at small sizes; it muddies the I.
        return

    # Recording dot — solid white circle with a faint outer ring so it
    # reads against the gradient rather than blending in. Sits in the
    # upper-right quadrant.
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
