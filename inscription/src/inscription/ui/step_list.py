"""Step list view displayed in the case workspace.

Each row shows a thumbnail, step title, timestamp, and a short body
preview. Selection changes emit a signal the workspace wires to the
detail panel.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from inscription.cases.models import Step
    from inscription.storage import CaseRepository


_THUMBNAIL_SIZE = QSize(160, 100)
_ROW_HEIGHT = 120
_STEP_ID_ROLE = Qt.ItemDataRole.UserRole + 1


class StepRowWidget(QWidget):
    """One row in the step list. Thumbnail + metadata stacked horizontally."""

    def __init__(
        self,
        *,
        step: Step,
        thumbnail: QPixmap | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(12)

        thumb = QLabel(self)
        thumb.setFixedSize(_THUMBNAIL_SIZE)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet("border: 1px solid palette(mid); background: palette(dark);")
        if thumbnail is not None and not thumbnail.isNull():
            thumb.setPixmap(
                thumbnail.scaled(
                    _THUMBNAIL_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            thumb.setText("(no preview)")

        seq = QLabel(f"#{step.sequence}", self)
        seq_font = seq.font()
        seq_font.setBold(True)
        seq.setFont(seq_font)

        title = QLabel(step.title or "(untitled)", self)
        title_font = title.font()
        title_font.setPointSizeF(title_font.pointSizeF() + 1)
        title.setFont(title_font)

        timestamp = QLabel(step.captured_at.strftime("%Y-%m-%d %H:%M:%S"), self)
        timestamp.setStyleSheet("color: palette(placeholder-text);")

        preview = QLabel((step.body_markdown or "").split("\n", 1)[0][:120] or "", self)
        preview.setStyleSheet("color: palette(text);")
        preview.setWordWrap(False)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(2)
        info.addWidget(seq)
        info.addWidget(title)
        info.addWidget(timestamp)
        info.addWidget(preview)
        info.addStretch(1)

        layout.addWidget(thumb)
        layout.addLayout(info, 1)


class StepListWidget(QListWidget):
    """Scrollable list of steps for the active case/session."""

    step_selected = Signal(int)  # emits the step id
    step_deselected = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setUniformItemSizes(False)
        self.setAlternatingRowColors(True)
        self.setSpacing(2)
        self.currentItemChanged.connect(self._on_current_changed)

    def load_steps(
        self,
        *,
        steps: list[Step],
        repository: CaseRepository,
    ) -> None:
        """Replace the list contents with the given steps."""
        self.clear()
        for step in steps:
            self._add_row(step, repository)

    def append_step(self, step: Step, repository: CaseRepository) -> None:
        """Add a single step row (typically after a new capture)."""
        self._add_row(step, repository)
        # Auto-scroll to the new row so the examiner sees it.
        self.scrollToBottom()

    def _add_row(self, step: Step, repository: CaseRepository) -> None:
        pixmap: QPixmap | None = None
        if step.screenshot_path:
            path = repository.case.root / step.screenshot_path
            if path.exists():
                candidate = QPixmap(str(path))
                if not candidate.isNull():
                    pixmap = candidate

        row = StepRowWidget(step=step, thumbnail=pixmap)
        item = QListWidgetItem(self)
        item.setSizeHint(QSize(row.sizeHint().width(), _ROW_HEIGHT))
        item.setData(_STEP_ID_ROLE, step.id)
        self.addItem(item)
        self.setItemWidget(item, row)

    def _on_current_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            self.step_deselected.emit()
            return
        step_id = current.data(_STEP_ID_ROLE)
        if isinstance(step_id, int):
            self.step_selected.emit(step_id)
