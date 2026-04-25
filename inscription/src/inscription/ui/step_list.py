"""Step list panel.

Shows draft steps as an ordered list with a thumbnail for each step that
has an associated screenshot. Three editing affordances live here:

- Selecting a step emits ``step_selected``, which the editor panel uses
  to render the step's text + screenshot.
- Drag-and-drop within the list emits ``steps_reordered`` with the new
  order of step IDs.
- Right-clicking a step opens a context menu with Merge / Split actions
  emitting ``merge_requested`` / ``split_requested``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem, QMenu, QWidget

if TYPE_CHECKING:
    from pathlib import Path

    from inscription.model import DraftStep, ScreenshotArtifact

THUMBNAIL_SIZE = QSize(96, 64)

#: Minimum source-event count for the Split action to be enabled.
_MIN_SOURCE_IDS_TO_SPLIT = 2


class StepListWidget(QListWidget):
    """Ordered list of draft steps for the current session."""

    step_selected = Signal(int)  # step id
    step_deselected = Signal()
    steps_reordered = Signal(list)  # new ordered list of step ids
    merge_requested = Signal(int, int)  # primary id, other id (the next step)
    split_requested = Signal(int)  # step id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setIconSize(THUMBNAIL_SIZE)
        self.setSpacing(2)
        self.itemSelectionChanged.connect(self._on_selection_changed)

        # Drag-and-drop reorder. We want internal moves only (no copy from
        # other widgets, no drop into nested items).
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.model().rowsMoved.connect(self._on_rows_moved)

        # Source-event-id payloads on each item, keyed by step id, so the
        # context menu can decide which actions are valid (e.g. Split is
        # only meaningful when the step covers more than one event).
        self._source_ids: dict[int, tuple[int, ...]] = {}

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    # -------------------------------------------------------- API

    def load(
        self,
        *,
        steps: list[DraftStep],
        screenshots: dict[int, ScreenshotArtifact],
        session_root: Path,
    ) -> None:
        self.clear()
        self._source_ids = {}
        for step in steps:
            self.addItem(self._build_item(step, screenshots, session_root))
            if step.id is not None:
                self._source_ids[step.id] = step.source_event_ids

    def clear_steps(self) -> None:
        self.clear()
        self._source_ids = {}

    def ordered_step_ids(self) -> list[int]:
        """Return step IDs in the order they currently appear in the list."""
        out: list[int] = []
        for row in range(self.count()):
            item = self.item(row)
            if item is None:
                continue
            sid = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(sid, int):
                out.append(sid)
        return out

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

    def _on_rows_moved(self, *_args: object) -> None:
        # Qt fires rowsMoved with positional args we don't need; just read
        # the new order off the widget.
        ordered = self.ordered_step_ids()
        if ordered:
            self.steps_reordered.emit(ordered)

    # ----------------------------------------------------- context menu

    def _on_context_menu(self, pos: QPoint) -> None:
        item = self.itemAt(pos)
        if item is None:
            return
        step_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(step_id, int):
            return

        row = self.row(item)
        next_item = self.item(row + 1) if row + 1 < self.count() else None
        next_id = next_item.data(Qt.ItemDataRole.UserRole) if next_item is not None else None

        menu = QMenu(self)

        merge = QAction("Merge with next step", menu)
        merge.setEnabled(isinstance(next_id, int))
        if isinstance(next_id, int):
            merge.triggered.connect(
                lambda _checked=False, a=step_id, b=next_id: self.merge_requested.emit(a, b)
            )
        menu.addAction(merge)

        split = QAction("Split off first event", menu)
        can_split = len(self._source_ids.get(step_id, ())) >= _MIN_SOURCE_IDS_TO_SPLIT
        split.setEnabled(can_split)
        if can_split:
            split.triggered.connect(
                lambda _checked=False, sid=step_id: self.split_requested.emit(sid)
            )
        menu.addAction(split)

        menu.exec(self.viewport().mapToGlobal(pos))
