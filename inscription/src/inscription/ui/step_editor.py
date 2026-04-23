"""Step detail / editor panel.

Edits to the text field are debounced — we emit a single
``text_edited(step_id, text)`` signal per calm interval so the repository
isn't hammered on every keystroke. ``flush_pending()`` forces an immediate
emission (used on close and on step selection change).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from pathlib import Path

    from inscription.model import DraftStep, ScreenshotArtifact


DEBOUNCE_MS = 600


class StepEditorPanel(QWidget):
    """Step text editor + screenshot preview."""

    text_edited = Signal(int, str)  # step_id, text
    step_suppressed = Signal(int, bool)  # step_id, suppressed

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._current_step_id: int | None = None
        self._current_text: str = ""

        self._text = QTextEdit(self)
        self._text.setPlaceholderText("Describe this step…")
        self._text.textChanged.connect(self._on_text_changed)

        self._screenshot = QLabel(self)
        self._screenshot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._screenshot.setMinimumHeight(240)
        self._screenshot.setStyleSheet("border: 1px solid #ccc; background: #fafafa;")
        self._screenshot.setText("No screenshot")

        self._suppress_btn = QPushButton("Remove step", self)
        self._suppress_btn.setToolTip("Hide this step from the export")
        self._suppress_btn.clicked.connect(self._emit_suppressed)
        self._suppress_btn.setEnabled(False)

        controls = QHBoxLayout()
        controls.addStretch(1)
        controls.addWidget(self._suppress_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Step description", self))
        layout.addWidget(self._text, 1)
        layout.addLayout(controls)
        layout.addWidget(QLabel("Screenshot", self))
        layout.addWidget(self._screenshot, 2)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._flush)

        self.clear()

    # ------------------------------------------------------------ API

    def show_step(
        self,
        step: DraftStep,
        *,
        screenshot: ScreenshotArtifact | None,
        session_root: Path,
    ) -> None:
        self.flush_pending()
        self._current_step_id = step.id
        self._current_text = step.text
        blocked = self._text.blockSignals(True)
        self._text.setPlainText(step.text)
        self._text.blockSignals(blocked)
        self._suppress_btn.setEnabled(True)
        self._suppress_btn.setText("Restore step" if step.suppressed else "Remove step")
        self._load_screenshot(screenshot, session_root)

    def clear(self) -> None:
        self.flush_pending()
        self._current_step_id = None
        self._current_text = ""
        blocked = self._text.blockSignals(True)
        self._text.clear()
        self._text.blockSignals(blocked)
        self._screenshot.clear()
        self._screenshot.setText("No screenshot")
        self._suppress_btn.setEnabled(False)

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
        new_text = self._text.toPlainText()
        if new_text == self._current_text:
            return
        self._current_text = new_text
        self.text_edited.emit(self._current_step_id, new_text)

    def _emit_suppressed(self) -> None:
        if self._current_step_id is None:
            return
        suppressed = self._suppress_btn.text() == "Remove step"
        self.step_suppressed.emit(self._current_step_id, suppressed)
        self._suppress_btn.setText("Restore step" if suppressed else "Remove step")
