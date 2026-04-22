"""The central widget shown while a case is open.

Splits horizontally between the step list (left) and the step detail
panel (right). Delegates all mutations to the controller via signals;
this widget owns no state beyond what's needed for display.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from inscription.ui.step_detail import StepDetailPanel
from inscription.ui.step_list import StepListWidget

if TYPE_CHECKING:
    from inscription.cases.models import Step
    from inscription.storage import CaseRepository


class CaseWorkspaceWidget(QWidget):
    """Case workspace: step list on the left, step detail on the right."""

    #: Emitted with (step_id, title, body_markdown) when the detail panel
    #: has a debounced edit to persist.
    step_edit_requested = Signal(int, str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._repository: CaseRepository | None = None

        self._list = StepListWidget(self)
        self._detail = StepDetailPanel(self)

        self._list.step_selected.connect(self._on_step_selected)
        self._list.step_deselected.connect(self._detail.clear)
        self._detail.step_edited.connect(self.step_edit_requested)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._list)
        splitter.addWidget(self._detail)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    # ----------------------------------------------------------- API

    def set_repository(self, repository: CaseRepository) -> None:
        """Bind the workspace to a case. Reloads the step list."""
        self._repository = repository
        steps = repository.list_steps()
        self._list.load_steps(steps=steps, repository=repository)
        self._detail.clear()

    def clear_repository(self) -> None:
        """Release the current case binding and reset the UI."""
        self._repository = None
        self._list.clear()
        self._detail.clear()

    def append_step(self, step: Step) -> None:
        """Called when a new step arrives (e.g. after a hotkey capture)."""
        if self._repository is None:
            return
        self._list.append_step(step, self._repository)

    def flush_pending_edits(self) -> None:
        """Force any debounced edit to emit immediately. Call on case close."""
        self._detail.flush_pending_save()

    # ----------------------------------------------------------- internals

    def _on_step_selected(self, step_id: int) -> None:
        if self._repository is None:
            return
        for step in self._repository.list_steps():
            if step.id == step_id:
                self._detail.show_step(step, self._repository.case.root)
                return
