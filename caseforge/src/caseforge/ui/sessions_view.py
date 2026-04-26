"""Sessions panel for the open-case view.

Read-only listing of every Inscription session inside the case
directory: name, started/ended, event count, step count. Refreshes on
demand (the user clicks the button after running an Inscription
session, or just on case re-open).

Empty state is intentional and friendly — most cases start with zero
sessions, and seeing "No recordings yet" with a hint is the right UX.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from caseforge.inscription_sessions import InscriptionSession


class SessionsView(QWidget):
    """Renders a list of :class:`InscriptionSession` entries."""

    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._summary_label = QLabel("No recordings yet.", self)
        self._summary_label.setProperty("muted", "true")

        self._refresh_btn = QPushButton("Refresh", self)
        self._refresh_btn.clicked.connect(self.refresh_requested)

        header = QHBoxLayout()
        header.addWidget(self._summary_label, 1)
        header.addWidget(self._refresh_btn)

        self._list = QListWidget(self)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setUniformItemSizes(False)

        self._empty_label = QLabel(
            "No Inscription sessions in this case yet.\n"
            "Click Launch Inscription above to start your first recording.",
            self,
        )
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setProperty("role", "card")
        self._empty_label.setProperty("muted", "true")
        self._empty_label.setStyleSheet("padding: 36px;")

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._list)
        self._stack.addWidget(self._empty_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addWidget(self._stack, 1)

    # ------------------------------------------------------------- API

    def show_sessions(self, sessions: list[InscriptionSession]) -> None:
        self._list.clear()
        if not sessions:
            self._summary_label.setText("No recordings yet.")
            self._stack.setCurrentIndex(1)
            return
        total_events = sum(s.event_count for s in sessions)
        total_steps = sum(s.step_count for s in sessions)
        plural = "s" if len(sessions) != 1 else ""
        self._summary_label.setText(
            f"{len(sessions)} session{plural} · "
            f"{total_events} event{'s' if total_events != 1 else ''} · "
            f"{total_steps} step{'s' if total_steps != 1 else ''}"
        )
        for session in sessions:
            item = QListWidgetItem(_format_session(session))
            item.setData(Qt.ItemDataRole.UserRole, session.path)
            tip_lines = [
                f"Started: {session.started_at.astimezone():%Y-%m-%d %H:%M:%S}",
            ]
            if session.ended_at is not None:
                tip_lines.append(f"Ended:   {session.ended_at.astimezone():%Y-%m-%d %H:%M:%S}")
            else:
                tip_lines.append("Ended:   in progress")
            tip_lines.append(f"Path:    {session.path}")
            item.setToolTip("\n".join(tip_lines))
            self._list.addItem(item)
        self._stack.setCurrentIndex(0)


def _format_session(session: InscriptionSession) -> str:
    started = session.started_at.astimezone().strftime("%Y-%m-%d %H:%M")
    if session.ended_at is None:
        duration_text = "in progress"
    else:
        seconds = max(0, int((session.ended_at - session.started_at).total_seconds()))
        mm, ss = divmod(seconds, 60)
        hh, mm = divmod(mm, 60)
        duration_text = f"{hh:d}h {mm:02d}m" if hh else f"{mm:d}m {ss:02d}s"
    plural = "s" if session.step_count != 1 else ""
    return (
        f"{session.name}\n"
        f"{started}  ·  {duration_text}  ·  "
        f"{session.event_count} event{'s' if session.event_count != 1 else ''}  ·  "
        f"{session.step_count} step{plural}"
    )
