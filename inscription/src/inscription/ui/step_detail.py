"""Side panel showing the selected step's details.

Displays the full screenshot and lets the examiner edit the title and
body. Edits are debounced — the panel emits a save signal 500ms after
the last keystroke so we're not hammering SQLite on every character.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from pathlib import Path

    from inscription.cases.models import Step


_SAVE_DEBOUNCE_MS = 500


class StepDetailPanel(QWidget):
    """Editor for one step's title, body, and a preview of its screenshot."""

    #: Emitted with (step_id, title, body_markdown) after the debounce.
    step_edited = Signal(int, str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._current_step_id: int | None = None
        self._suppress_emit = False

        self._title = QLineEdit(self)
        self._title.setPlaceholderText("Step title")
        self._title.textEdited.connect(self._schedule_save)

        self._body = QPlainTextEdit(self)
        self._body.setPlaceholderText("Notes, context, reasoning…")
        self._body.textChanged.connect(self._schedule_save)

        self._timestamp = QLabel("", self)
        self._timestamp.setStyleSheet("color: palette(placeholder-text);")

        self._screenshot_label = QLabel("Select a step to view its screenshot.", self)
        self._screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._screenshot_label.setMinimumHeight(200)
        self._screenshot_label.setStyleSheet(
            "border: 1px solid palette(mid); background: palette(dark);"
        )

        screenshot_scroll = QScrollArea(self)
        screenshot_scroll.setWidget(self._screenshot_label)
        screenshot_scroll.setWidgetResizable(True)
        screenshot_scroll.setMinimumHeight(240)

        layout = QVBoxLayout(self)
        layout.addWidget(self._title)
        layout.addWidget(self._timestamp)
        layout.addWidget(screenshot_scroll, 1)
        layout.addWidget(self._body, 1)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(_SAVE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._emit_save)

        self.clear()

    # ---------------------------------------------------------------- API

    def show_step(self, step: Step, case_root: Path) -> None:
        """Populate the panel with the given step. Does not emit edit signals."""
        self._suppress_emit = True
        try:
            self._current_step_id = step.id
            self._title.setText(step.title)
            self._body.setPlainText(step.body_markdown)
            self._timestamp.setText(
                f"Captured: {step.captured_at.strftime('%Y-%m-%d %H:%M:%S')} "
                f"·  Step #{step.sequence}"
            )
            if step.screenshot_path:
                path = case_root / step.screenshot_path
                if path.exists():
                    pix = QPixmap(str(path))
                    if not pix.isNull():
                        self._screenshot_label.setPixmap(pix)
                        self._screenshot_label.setText("")
                        return
            self._screenshot_label.setPixmap(QPixmap())
            self._screenshot_label.setText("(no screenshot)")
        finally:
            self._suppress_emit = False

    def clear(self) -> None:
        """Reset the panel to its empty state."""
        self._suppress_emit = True
        try:
            self._current_step_id = None
            self._title.clear()
            self._body.clear()
            self._timestamp.setText("")
            self._screenshot_label.setPixmap(QPixmap())
            self._screenshot_label.setText("Select a step to view its screenshot.")
        finally:
            self._suppress_emit = False

    def flush_pending_save(self) -> None:
        """Force-emit any pending edit immediately. Call before closing."""
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._emit_save()

    # ------------------------------------------------------------ internals

    def _schedule_save(self) -> None:
        if self._suppress_emit or self._current_step_id is None:
            return
        self._save_timer.start()

    def _emit_save(self) -> None:
        if self._current_step_id is None:
            return
        self.step_edited.emit(
            self._current_step_id,
            self._title.text(),
            self._body.toPlainText(),
        )
