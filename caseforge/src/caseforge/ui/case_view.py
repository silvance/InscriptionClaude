"""Open-case view: examiner can edit metadata and launch Inscription.

Shares its three-tab layout with :class:`NewCaseDialog`. The header
strip carries the case name + reference, the on-disk path, and a
primary "Launch Inscription" button — the workflow most cases need
once they're set up.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from caseforge.model import Case, ExaminerIdentity, ExamScope

if TYPE_CHECKING:
    from pathlib import Path


def _split_csv(text: str) -> list[str]:
    return [chunk.strip() for chunk in text.split(",") if chunk.strip()]


def _join_csv(items: list[str]) -> str:
    return ", ".join(items)


class CaseView(QWidget):
    """Editable view onto an open :class:`Case`."""

    save_requested = Signal(object)  # Case
    launch_inscription_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._case: Case | None = None
        self._case_dir: Path | None = None

        self._title_label = QLabel("", self)
        title_font = self._title_label.font()
        title_font.setPointSize(title_font.pointSize() + 4)
        title_font.setBold(True)
        self._title_label.setFont(title_font)

        self._reference_label = QLabel("", self)
        self._reference_label.setStyleSheet("color: #6e6e73;")

        self._path_label = QLabel("", self)
        self._path_label.setStyleSheet("color: #6e6e73; font-size: 11px;")
        # Allow click-and-copy of the case path from the header.
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._launch_btn = QPushButton("Launch Inscription", self)
        self._launch_btn.setProperty("role", "primary")
        self._launch_btn.setMinimumHeight(34)
        self._launch_btn.setMinimumWidth(180)
        self._launch_btn.clicked.connect(self.launch_inscription_requested)

        self._save_btn = QPushButton("Save changes", self)
        self._save_btn.clicked.connect(self._on_save)

        self._close_btn = QPushButton("Close", self)
        self._close_btn.clicked.connect(self.close_requested)

        header_left = QVBoxLayout()
        header_left.setSpacing(2)
        header_left.addWidget(self._title_label)
        header_left.addWidget(self._reference_label)
        header_left.addWidget(self._path_label)

        header = QHBoxLayout()
        header.addLayout(header_left, 1)
        header.addWidget(self._save_btn)
        header.addWidget(self._launch_btn)
        header.addWidget(self._close_btn)

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._build_case_tab(), "Case")
        self._tabs.addTab(self._build_examiner_tab(), "Examiner")
        self._tabs.addTab(self._build_scope_tab(), "Scope")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)
        layout.addLayout(header)
        layout.addWidget(self._tabs, 1)

    # ------------------------------------------------------------ API

    def show_case(self, case: Case, *, case_dir: Path) -> None:
        self._case = case
        self._case_dir = case_dir
        self._title_label.setText(case.name or "(unnamed case)")
        ref = case.case_reference or "no reference"
        when = case.updated_at.astimezone().strftime("%Y-%m-%d %H:%M")
        self._reference_label.setText(f"{ref} · last edited {when}")
        self._path_label.setText(str(case_dir))

        # Block signals while we populate so editing flags don't fire.
        for edit, value in (
            (self._name_edit, case.name),
            (self._reference_edit, case.case_reference),
            (self._examiner_name_edit, case.examiner.name),
            (self._examiner_org_edit, case.examiner.organisation),
            (self._examiner_badge_edit, case.examiner.badge_id),
            (self._exam_type_edit, case.scope.exam_type),
            (self._device_classes_edit, _join_csv(case.scope.device_classes)),
            (self._evidence_items_edit, _join_csv(case.scope.evidence_items)),
            (self._agencies_edit, _join_csv(case.scope.agencies)),
        ):
            edit.setText(value)
        self._summary_edit.setPlainText(case.scope.summary)
        self._notes_edit.setPlainText(case.scope.notes)

    # -------------------------------------------------------- builders

    def _build_case_tab(self) -> QWidget:
        page = QWidget(self)
        self._name_edit = QLineEdit(page)
        self._reference_edit = QLineEdit(page)
        form = QFormLayout()
        form.addRow("Case name", self._name_edit)
        form.addRow("Case reference", self._reference_edit)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_examiner_tab(self) -> QWidget:
        page = QWidget(self)
        self._examiner_name_edit = QLineEdit(page)
        self._examiner_org_edit = QLineEdit(page)
        self._examiner_badge_edit = QLineEdit(page)
        form = QFormLayout()
        form.addRow("Name", self._examiner_name_edit)
        form.addRow("Organisation", self._examiner_org_edit)
        form.addRow("Badge / ID", self._examiner_badge_edit)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_scope_tab(self) -> QWidget:
        page = QWidget(self)
        self._exam_type_edit = QLineEdit(page)
        self._device_classes_edit = QLineEdit(page)
        self._evidence_items_edit = QLineEdit(page)
        self._agencies_edit = QLineEdit(page)
        self._summary_edit = QPlainTextEdit(page)
        self._summary_edit.setMaximumHeight(80)
        self._notes_edit = QPlainTextEdit(page)
        self._notes_edit.setMaximumHeight(140)
        form = QFormLayout()
        form.addRow("Exam type", self._exam_type_edit)
        form.addRow("Device classes", self._device_classes_edit)
        form.addRow("Evidence items", self._evidence_items_edit)
        form.addRow("Agencies", self._agencies_edit)
        form.addRow("Summary", self._summary_edit)
        form.addRow("Notes", self._notes_edit)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(form)
        return page

    # -------------------------------------------------------- internals

    def _on_save(self) -> None:
        if self._case is None:
            return
        updated = dataclasses.replace(
            self._case,
            name=self._name_edit.text().strip() or self._case.name,
            case_reference=self._reference_edit.text().strip(),
            examiner=ExaminerIdentity(
                name=self._examiner_name_edit.text().strip(),
                organisation=self._examiner_org_edit.text().strip(),
                badge_id=self._examiner_badge_edit.text().strip(),
            ),
            scope=ExamScope(
                exam_type=self._exam_type_edit.text().strip(),
                device_classes=_split_csv(self._device_classes_edit.text()),
                evidence_items=_split_csv(self._evidence_items_edit.text()),
                agencies=_split_csv(self._agencies_edit.text()),
                summary=self._summary_edit.toPlainText().strip(),
                notes=self._notes_edit.toPlainText().strip(),
            ),
        )
        self.save_requested.emit(updated)
