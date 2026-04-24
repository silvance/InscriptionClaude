"""Top-of-window recorder controls.

A single horizontal strip with a Record/Stop button, a Marker button,
the session name, and a live event counter. The bar is purely presentational
— it emits Qt signals and lets the controller own all state transitions.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class RecorderBar(QWidget):
    """Recorder control strip."""

    record_toggled = Signal(bool)  # True -> start, False -> stop
    marker_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._record_btn = QPushButton("● Record", self)
        self._record_btn.setCheckable(True)
        self._record_btn.toggled.connect(self.record_toggled)

        self._marker_btn = QPushButton("Mark", self)
        self._marker_btn.setToolTip("Drop a marker (Ctrl+Shift+M)")
        self._marker_btn.clicked.connect(self.marker_requested)
        self._marker_btn.setEnabled(False)

        self._name_label = QLabel("No session open", self)
        font = self._name_label.font()
        font.setBold(True)
        self._name_label.setFont(font)

        self._count_label = QLabel("0 events", self)
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(self._record_btn)
        layout.addWidget(self._marker_btn)
        layout.addSpacing(12)
        layout.addWidget(self._name_label, 1)
        layout.addWidget(self._count_label)

    # ----------------------------------------------------------- API

    def set_session_name(self, name: str | None) -> None:
        self._name_label.setText(name or "No session open")
        self._marker_btn.setEnabled(name is not None)

    def set_recording(self, recording: bool) -> None:
        """Force the record button state without emitting ``record_toggled``."""
        blocked = self._record_btn.blockSignals(True)
        self._record_btn.setChecked(recording)
        self._record_btn.blockSignals(blocked)
        self._record_btn.setText("■ Stop" if recording else "● Record")

    def set_event_count(self, count: int) -> None:
        self._count_label.setText(f"{count} event{'s' if count != 1 else ''}")

    def toggle_record(self) -> None:
        """Flip the record button and fire ``record_toggled``.

        Used by the global Ctrl+Shift+R hotkey so the user can start and
        stop recording without clicking on Inscription's own window.
        """
        self._record_btn.setChecked(not self._record_btn.isChecked())
