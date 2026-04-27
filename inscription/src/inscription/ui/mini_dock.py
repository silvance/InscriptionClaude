"""Compact always-on-top step-tracker overlay.

Inscription is normally a full-window tool, but during a long workflow
the examiner often wants the recorder out of the way while still seeing
that recording is live and what was just captured. :class:`MiniDock` is
a small frameless widget that:

- Stays on top of every other window (via ``Qt.WindowStaysOnTopHint``).
- Shows a recording indicator, the session name, and the most recent
  step's clock time + action text.
- Can be dragged anywhere on screen; position is saved per-user.
- Click anywhere on the body to expand back to the main window.

The dock listens to the same Qt signals the main workspace does, so
its content updates within ~50ms of a new step landing in the
repository — no polling.

A note on full-screen apps: ``WindowStaysOnTopHint`` cannot raise above
true exclusive full-screen windows on Windows (games / video players in
exclusive mode). Borderless / windowed full-screen is fine. Documented
because forensic exam tools occasionally run inside a full-screen RDP
or Citrix session — we ship the most-portable hint and call it out.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from inscription.util import format_clock_time

if TYPE_CHECKING:
    from datetime import datetime

    from inscription.model import DraftStep

logger = logging.getLogger(__name__)

#: Manhattan-distance threshold separating a click (expand the window)
#: from a drag (just persist the new position). 8 px is forgiving enough
#: that a slight wobble doesn't unexpectedly expand the window.
_CLICK_VS_DRAG_PX = 8


class _PulsingDot(QWidget):
    """Mirror of recorder_bar's red dot, scaled down for the dock.

    Kept local to avoid importing Qt timer lifecycle into a module that
    ought to stay simple; the dot only animates while the dock is
    visible AND recording, which the parent toggles via show/hide.
    """

    DIAMETER = 8

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(self.DIAMETER + 4, self.DIAMETER + 4)
        self._on = False

    def set_recording(self, recording: bool) -> None:
        self._on = recording
        self.update()

    def paintEvent(self, _event: object) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        colour = QColor(215, 0, 21) if self._on else QColor(120, 120, 120, 90)
        painter.setBrush(colour)
        cx = self.width() / 2
        cy = self.height() / 2
        painter.drawEllipse(
            int(cx - self.DIAMETER / 2),
            int(cy - self.DIAMETER / 2),
            self.DIAMETER,
            self.DIAMETER,
        )
        painter.end()


class MiniDock(QWidget):
    """Floating compact step-tracker."""

    #: Click on the body (not a button) → user wants the full window back.
    expand_requested = Signal()
    #: Close button → hide the dock but keep recording.
    hide_requested = Signal()
    #: Emitted when the user drags the dock; payload is the new top-left
    #: in global screen coordinates so the main window can persist it.
    moved = Signal(int, int)

    _MIN_WIDTH = 280
    _MAX_WIDTH = 360

    def __init__(self, parent: QWidget | None = None) -> None:
        # ``Qt.Tool`` keeps the widget out of the OS's window list (it
        # won't appear in Alt-Tab, won't claim a taskbar entry).
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, on=False)
        self.setMinimumWidth(self._MIN_WIDTH)
        self.setMaximumWidth(self._MAX_WIDTH)

        self._drag_origin: QPoint | None = None
        self._press_screen_pos: QPoint | None = None
        self._dot = _PulsingDot(self)

        self._session_label = QLabel("No session", self)
        font = self._session_label.font()
        font.setBold(True)
        self._session_label.setFont(font)
        self._session_label.setStyleSheet("color: #f2f2f7;")

        self._time_label = QLabel("", self)
        self._time_label.setStyleSheet("color: #98989d; font-variant-numeric: tabular-nums;")

        self._step_label = QLabel("Awaiting first step…", self)
        self._step_label.setWordWrap(True)
        self._step_label.setStyleSheet("color: #f2f2f7;")
        self._step_label.setMaximumHeight(48)
        self._step_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._expand_btn = self._tiny_button("⤢", "Restore the main window")
        self._expand_btn.clicked.connect(self.expand_requested)
        self._close_btn = self._tiny_button("✕", "Hide the compact view")
        self._close_btn.clicked.connect(self.hide_requested)

        # Card frame so the dock reads as one solid object on top of any
        # background, instead of relying on the OS window decorations.
        card = QFrame(self)
        card.setObjectName("MiniDockCard")
        card.setStyleSheet(
            "QFrame#MiniDockCard {"
            "  background-color: rgba(28, 28, 30, 235);"
            "  border: 1px solid #3a3a3c;"
            "  border-radius: 8px;"
            "}"
        )

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)
        top_row.addWidget(self._dot)
        top_row.addWidget(self._session_label, 1)
        top_row.addWidget(self._time_label)
        top_row.addWidget(self._expand_btn)
        top_row.addWidget(self._close_btn)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 10)
        card_layout.setSpacing(4)
        card_layout.addLayout(top_row)
        card_layout.addWidget(self._step_label)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

    # -------------------------------------------------------- API

    def set_session_name(self, name: str | None) -> None:
        self._session_label.setText(name or "No session")

    def set_recording(self, recording: bool) -> None:
        self._dot.set_recording(recording)

    def show_step(self, step: DraftStep | None, started_at: datetime | None) -> None:
        """Update the body to reflect the latest captured step.

        ``started_at`` is positional (not keyword-only) because Qt
        invokes connected slots with positional arguments — declaring
        it kw-only made every emission silently raise ``TypeError`` and
        leave the dock stuck on "Awaiting first step…".
        """
        if step is None:
            self._step_label.setText("Awaiting first step…")
            self._time_label.setText("")
            return
        action = step.action.strip() or "(empty step)"
        self._step_label.setText(f"{step.sequence:02d}.  {action}")
        if started_at is not None:
            self._time_label.setText(format_clock_time(started_at))
        else:
            self._time_label.setText("")

    # -------------------------------------------------------- behaviour

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_screen_pos = event.globalPosition().toPoint()
            self._drag_origin = self._press_screen_pos - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if (
            self._drag_origin is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            new_pos = event.globalPosition().toPoint() - self._drag_origin
            self.move(new_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton and self._drag_origin is not None:
            release_pos = event.globalPosition().toPoint()
            press_pos = self._press_screen_pos
            self._drag_origin = None
            self._press_screen_pos = None
            top_left = self.frameGeometry().topLeft()
            self.moved.emit(top_left.x(), top_left.y())
            # If the release lands within a few pixels of the press, treat
            # it as a click and pop the main window back. Anything bigger
            # is a drag and the position update above is enough.
            if (
                press_pos is not None
                and (release_pos - press_pos).manhattanLength() < _CLICK_VS_DRAG_PX
            ):
                self.expand_requested.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # -------------------------------------------------------- internals

    def _tiny_button(self, glyph: str, tip: str) -> QPushButton:
        btn = QPushButton(glyph, self)
        btn.setToolTip(tip)
        btn.setFixedSize(20, 20)
        btn.setFlat(True)
        btn.setStyleSheet(
            "QPushButton { color: #f2f2f7; border: 0; background: transparent; }"
            "QPushButton:hover { background: rgba(255,255,255,0.08); border-radius: 4px; }"
        )
        # Keep the dock from accepting the press as a drag-start.
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return btn
