"""Step list panel.

Shows draft steps as an ordered list with a thumbnail for each step that
has an associated screenshot. Selecting a step emits a signal the editor
panel listens on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QWidget

if TYPE_CHECKING:
    from pathlib import Path

    from inscription.model import DraftStep, ScreenshotArtifact

THUMBNAIL_SIZE = QSize(96, 64)


class StepListWidget(QListWidget):
    """Ordered list of draft steps for the current session."""

    step_selected = Signal(int)  # step id
    step_deselected = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setIconSize(THUMBNAIL_SIZE)
        self.setSpacing(2)
        self.itemSelectionChanged.connect(self._on_selection_changed)

    # -------------------------------------------------------- API

    def load(
        self,
        *,
        steps: list[DraftStep],
        screenshots: dict[int, ScreenshotArtifact],
        session_root: Path,
    ) -> None:
        self.clear()
        for step in steps:
            self.addItem(self._build_item(step, screenshots, session_root))

    def clear_steps(self) -> None:
        self.clear()

    # -------------------------------------------------------- internals

    def _build_item(
        self,
        step: DraftStep,
        screenshots: dict[int, ScreenshotArtifact],
        session_root: Path,
    ) -> QListWidgetItem:
        label_text = f"{step.sequence:02d}. {step.text or '(empty step)'}"
        item = QListWidgetItem(label_text)
        item.setData(Qt.ItemDataRole.UserRole, step.id)
        if step.screenshot_id and step.screenshot_id in screenshots:
            shot = screenshots[step.screenshot_id]
            icon = self._load_thumbnail(session_root / shot.relative_path)
            if icon is not None:
                item.setIcon(icon)
        return item

    @staticmethod
    def _load_thumbnail(path: Path) -> QIcon | None:
        if not path.exists():
            return None
        pix = QPixmap(str(path))
        if pix.isNull():
            return None
        scaled = pix.scaled(
            THUMBNAIL_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return QIcon(scaled)

    def _on_selection_changed(self) -> None:
        items = self.selectedItems()
        if not items:
            self.step_deselected.emit()
            return
        step_id = items[0].data(Qt.ItemDataRole.UserRole)
        if isinstance(step_id, int):
            self.step_selected.emit(step_id)
