"""Read-only scope summary for the left half of the main window.

Mirrors the field layout examiners see on CaseForge's Scope tab so
context shifts cleanly when they Open in CaseGuide. CaseGuide doesn't
edit the case scope — that's CaseForge's job — so every field is
read-only label text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from caseguide.ui.widgets import horizontal_separator

if TYPE_CHECKING:
    from caseguide.case_reader import CaseHandle


def _muted(text: str, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("muted", "true")
    label.setWordWrap(True)
    return label


def _value_label(parent: QWidget) -> QLabel:
    """Read-only value cell next to a form row label.

    Word-wrap is on so a long evidence-items list doesn't shove the
    panel wider than the splitter handle allows.
    """
    label = QLabel("—", parent)
    label.setWordWrap(True)
    return label


class ScopePanel(QWidget):
    """Renders a :class:`caseguide.case_reader.CaseHandle` as read-only text."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._title_label = QLabel("No case open", self)
        title_font = self._title_label.font()
        title_font.setPointSize(title_font.pointSize() + 4)
        title_font.setBold(True)
        self._title_label.setFont(title_font)

        self._reference_label = _muted("", self)
        self._examiner_label = _muted("", self)
        self._path_label = _muted("", self)
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._exam_type_value = _value_label(self)
        self._primary_tool_value = _value_label(self)
        self._devices_value = _value_label(self)
        self._evidence_value = _value_label(self)
        self._agencies_value = _value_label(self)

        self._summary_box = QPlainTextEdit(self)
        self._summary_box.setReadOnly(True)
        self._summary_box.setMaximumHeight(110)
        self._notes_box = QPlainTextEdit(self)
        self._notes_box.setReadOnly(True)
        self._notes_box.setMaximumHeight(160)

        rule = horizontal_separator(self)

        form = QFormLayout()
        form.addRow("Exam type", self._exam_type_value)
        form.addRow("Primary tool", self._primary_tool_value)
        form.addRow("Device classes", self._devices_value)
        form.addRow("Evidence items", self._evidence_value)
        form.addRow("Agencies", self._agencies_value)
        form.addRow("Summary", self._summary_box)
        form.addRow("Notes", self._notes_box)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addWidget(self._title_label)
        layout.addWidget(self._reference_label)
        layout.addWidget(self._examiner_label)
        layout.addWidget(self._path_label)
        layout.addWidget(rule)
        layout.addLayout(form)
        layout.addStretch(1)

    # -------------------------------------------------------- API

    def show_case(self, handle: CaseHandle, *, case_dir: str) -> None:
        self._title_label.setText(handle.name or "(unnamed case)")
        ref = handle.case_reference or "no reference"
        self._reference_label.setText(f"Reference: {ref}")
        self._examiner_label.setText(
            f"Examiner: {handle.examiner_name or '—'}"
        )
        self._path_label.setText(case_dir)

        scope = handle.scope
        self._exam_type_value.setText(scope.exam_type or "—")
        self._primary_tool_value.setText(scope.primary_tool or "—")
        self._devices_value.setText(", ".join(scope.device_classes) or "—")
        self._evidence_value.setText(", ".join(scope.evidence_items) or "—")
        self._agencies_value.setText(", ".join(scope.agencies) or "—")
        self._summary_box.setPlainText(scope.summary)
        self._notes_box.setPlainText(scope.notes)

    def clear(self) -> None:
        self._title_label.setText("No case open")
        for label in (self._reference_label, self._examiner_label, self._path_label):
            label.setText("")
        for value_label in (
            self._exam_type_value,
            self._primary_tool_value,
            self._devices_value,
            self._evidence_value,
            self._agencies_value,
        ):
            value_label.setText("—")
        self._summary_box.clear()
        self._notes_box.clear()
