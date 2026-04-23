"""The central widget shown while a session is open.

Splits horizontally: step list on the left, step editor on the right.
Exposes signals the controller listens on and does not hold repository
state itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from inscription.ui.step_editor import StepEditorPanel
from inscription.ui.step_list import StepListWidget

if TYPE_CHECKING:
    from inscription.storage import SessionRepository


class SessionWorkspaceWidget(QWidget):
    """Step list + step editor panel."""

    step_text_edited = Signal(int, str)
    step_suppressed = Signal(int, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._repository: SessionRepository | None = None

        self._list = StepListWidget(self)
        self._editor = StepEditorPanel(self)

        self._list.step_selected.connect(self._on_step_selected)
        self._list.step_deselected.connect(self._editor.clear)
        self._editor.text_edited.connect(self.step_text_edited)
        self._editor.step_suppressed.connect(self.step_suppressed)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._list)
        splitter.addWidget(self._editor)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    # ------------------------------------------------------------ API

    def set_repository(self, repository: SessionRepository) -> None:
        self._repository = repository
        self.reload()

    def clear_repository(self) -> None:
        self._repository = None
        self._list.clear_steps()
        self._editor.clear()

    def reload(self) -> None:
        if self._repository is None:
            return
        steps = self._repository.list_steps()
        screenshots = {s.id: s for s in self._repository.list_screenshots() if s.id is not None}
        self._list.load(
            steps=steps,
            screenshots=screenshots,
            session_root=self._repository.session.root,
        )
        self._editor.clear()

    def flush_pending(self) -> None:
        self._editor.flush_pending()

    # --------------------------------------------------------- internals

    def _on_step_selected(self, step_id: int) -> None:
        if self._repository is None:
            return
        step = next(
            (s for s in self._repository.list_steps(include_suppressed=True) if s.id == step_id),
            None,
        )
        if step is None:
            self._editor.clear()
            return
        shot = self._repository.get_screenshot(step.screenshot_id) if step.screenshot_id else None
        self._editor.show_step(
            step,
            screenshot=shot,
            session_root=self._repository.session.root,
        )
