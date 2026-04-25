"""Step detail / editor panel.

A draft step has two editable fields, mirroring the columns on a
forensic-style notes table: **Action** (what the examiner did) and
**Result** (what was observed). The panel exposes one debounced text
area per field. Edits are debounced — we emit a single
``fields_edited(step_id, action, result)`` per calm interval so the
repository isn't hammered on every keystroke.
``flush_pending()`` forces an immediate emission (used on close and on
step selection change).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from inscription.model import DraftStep, ScreenshotArtifact


DEBOUNCE_MS = 600


def _section_label(text: str, parent: QWidget) -> QLabel:
    """A small bold heading used to title the editor's sections."""
    label = QLabel(text, parent)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    label.setStyleSheet("color: #6e6e73; letter-spacing: 0.4px;")
    return label


def _heading_for(step: DraftStep, started_at: datetime | None) -> str:
    """Build the editor's main heading, including the step time."""
    base = f"Step {step.sequence:02d}"
    if started_at is None:
        return base
    local = started_at.astimezone().strftime("%H:%M:%S")
    return f"{base} · {local}"


class StepEditorPanel(QWidget):
    """Action + Result editor with screenshot preview."""

    fields_edited = Signal(int, str, str)  # step_id, action, result
    step_suppressed = Signal(int, bool)  # step_id, suppressed
    evidentiary_toggled = Signal(int, bool)  # step_id, evidentiary

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._current_step_id: int | None = None
        self._current_action: str = ""
        self._current_result: str = ""

        self._action = self._build_text_edit("What the examiner did…")
        self._result = self._build_text_edit("What was observed (optional)")
        self._screenshot = self._build_screenshot_label()
        self._evidentiary_cb = self._build_evidentiary_cb()
        self._suppress_btn = self._build_suppress_btn()

        self._heading_label = _section_label("Step", self)
        self._action_label = _section_label("Action", self)
        self._result_label = _section_label("Result", self)
        self._screenshot_label = _section_label("Screenshot", self)

        self._build_layout()

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._flush)

        self.clear()

    def _build_text_edit(self, placeholder: str) -> QTextEdit:
        edit = QTextEdit(self)
        edit.setPlaceholderText(placeholder)
        edit.setAcceptRichText(False)
        edit.textChanged.connect(self._on_text_changed)
        return edit

    def _build_screenshot_label(self) -> QLabel:
        label = QLabel(self)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumHeight(200)
        # Stylesheet selector: picks up the "card" role from the global QSS.
        label.setObjectName("StepScreenshot")
        label.setProperty("role", "card")
        label.setText("No screenshot")
        return label

    def _build_evidentiary_cb(self) -> QCheckBox:
        cb = QCheckBox("Mark as evidentiary", self)
        cb.setToolTip(
            "Flag this step for inclusion in the downstream forensic report."
        )
        cb.toggled.connect(self._emit_evidentiary)
        cb.setEnabled(False)
        return cb

    def _build_suppress_btn(self) -> QPushButton:
        btn = QPushButton("Remove step", self)
        btn.setToolTip("Hide this step from the export")
        btn.clicked.connect(self._emit_suppressed)
        btn.setEnabled(False)
        return btn

    def _build_layout(self) -> None:
        controls = QHBoxLayout()
        controls.addWidget(self._evidentiary_cb)
        controls.addStretch(1)
        controls.addWidget(self._suppress_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._heading_label)
        layout.addSpacing(2)
        layout.addWidget(self._action_label)
        layout.addWidget(self._action, 2)
        layout.addSpacing(4)
        layout.addWidget(self._result_label)
        layout.addWidget(self._result, 1)
        layout.addLayout(controls)
        layout.addSpacing(4)
        layout.addWidget(self._screenshot_label)
        layout.addWidget(self._screenshot, 2)

    # ------------------------------------------------------------ API

    def show_step(
        self,
        step: DraftStep,
        *,
        screenshot: ScreenshotArtifact | None,
        started_at: datetime | None = None,
        session_root: Path,
    ) -> None:
        self.flush_pending()
        self._current_step_id = step.id
        self._current_action = step.action
        self._current_result = step.result
        action_blocked = self._action.blockSignals(True)
        self._action.setPlainText(step.action)
        self._action.blockSignals(action_blocked)
        result_blocked = self._result.blockSignals(True)
        self._result.setPlainText(step.result)
        self._result.blockSignals(result_blocked)
        self._suppress_btn.setEnabled(True)
        self._suppress_btn.setText("Restore step" if step.suppressed else "Remove step")
        # Set the checkbox without firing the toggled signal — otherwise
        # selecting a step would write its current state right back to the
        # repository and mark every selection as a "user action".
        cb_blocked = self._evidentiary_cb.blockSignals(True)
        self._evidentiary_cb.setChecked(step.evidentiary)
        self._evidentiary_cb.blockSignals(cb_blocked)
        self._evidentiary_cb.setEnabled(True)
        self._heading_label.setText(_heading_for(step, started_at))
        self._load_screenshot(screenshot, session_root)

    def clear(self) -> None:
        self.flush_pending()
        self._current_step_id = None
        self._current_action = ""
        self._current_result = ""
        action_blocked = self._action.blockSignals(True)
        self._action.clear()
        self._action.blockSignals(action_blocked)
        result_blocked = self._result.blockSignals(True)
        self._result.clear()
        self._result.blockSignals(result_blocked)
        self._screenshot.clear()
        self._screenshot.setText("No screenshot")
        self._suppress_btn.setEnabled(False)
        cb_blocked = self._evidentiary_cb.blockSignals(True)
        self._evidentiary_cb.setChecked(False)
        self._evidentiary_cb.blockSignals(cb_blocked)
        self._evidentiary_cb.setEnabled(False)
        self._heading_label.setText("Step")

    def flush_pending(self) -> None:
        if self._debounce.isActive():
            self._debounce.stop()
            self._flush()

    # -------------------------------------------------------- internals

    def _load_screenshot(self, screenshot: ScreenshotArtifact | None, session_root: Path) -> None:
        if screenshot is None:
            self._screenshot.setText("No screenshot")
            return
        path = session_root / screenshot.relative_path
        if not path.exists():
            self._screenshot.setText("Screenshot missing")
            return
        pix = QPixmap(str(path))
        if pix.isNull():
            self._screenshot.setText("Could not render screenshot")
            return
        scaled = pix.scaledToWidth(
            self._screenshot.width() or 640,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._screenshot.setPixmap(scaled)

    def _on_text_changed(self) -> None:
        if self._current_step_id is None:
            return
        self._debounce.start()

    def _flush(self) -> None:
        if self._current_step_id is None:
            return
        new_action = self._action.toPlainText()
        new_result = self._result.toPlainText()
        if new_action == self._current_action and new_result == self._current_result:
            return
        self._current_action = new_action
        self._current_result = new_result
        self.fields_edited.emit(self._current_step_id, new_action, new_result)

    def _emit_suppressed(self) -> None:
        if self._current_step_id is None:
            return
        suppressed = self._suppress_btn.text() == "Remove step"
        self.step_suppressed.emit(self._current_step_id, suppressed)
        self._suppress_btn.setText("Restore step" if suppressed else "Remove step")

    def _emit_evidentiary(self, checked: bool) -> None:
        if self._current_step_id is None:
            return
        self.evidentiary_toggled.emit(self._current_step_id, checked)
