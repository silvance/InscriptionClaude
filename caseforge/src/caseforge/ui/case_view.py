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
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from caseforge.model import Case, ExaminerIdentity, ExamScope
from caseforge.ui.custody_tab import CustodyTab
from caseforge.ui.sessions_view import SessionsView
from caseforge.ui.widgets import (
    build_exam_type_combo,
    build_primary_tool_combo,
    display_label,
    exam_type_value,
    primary_tool_value,
    select_exam_type,
    select_primary_tool,
)

if TYPE_CHECKING:
    from pathlib import Path

    from caseforge.inscription_sessions import InscriptionSession


def _split_csv(text: str) -> list[str]:
    return [chunk.strip() for chunk in text.split(",") if chunk.strip()]


def _join_csv(items: list[str]) -> str:
    return ", ".join(items)


class CaseView(QWidget):
    """Editable view onto an open :class:`Case`."""

    save_requested = Signal(object)  # Case
    launch_inscription_requested = Signal()
    launch_caseguide_requested = Signal()
    close_requested = Signal()
    refresh_sessions_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._case: Case | None = None
        self._case_dir: Path | None = None

        self._title_label = display_label("", self)

        self._reference_label = QLabel("", self)
        self._reference_label.setProperty("muted", "true")

        self._path_label = QLabel("", self)
        self._path_label.setProperty("role", "caption")
        # Allow click-and-copy of the case path from the header.
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._launch_btn, self._caseguide_btn, self._save_btn, self._close_btn = (
            self._build_action_buttons()
        )

        header_left = QVBoxLayout()
        header_left.setSpacing(2)
        header_left.addWidget(self._title_label)
        header_left.addWidget(self._reference_label)
        header_left.addWidget(self._path_label)

        header_strip = QFrame(self)
        header_strip.setProperty("role", "page-header")
        header_row = QHBoxLayout(header_strip)
        header_row.setContentsMargins(20, 14, 20, 14)
        header_row.setSpacing(10)
        header_row.addLayout(header_left, 1)
        header_row.addWidget(self._save_btn)
        header_row.addWidget(self._caseguide_btn)
        header_row.addWidget(self._launch_btn)
        header_row.addWidget(self._close_btn)

        self._sessions_view = SessionsView(self)
        self._sessions_view.refresh_requested.connect(self.refresh_sessions_requested)
        self._custody_tab = CustodyTab(self)

        self._tabs = QTabWidget(self)
        # Sessions first so opening a case lands on "what work has been
        # done?" rather than the rarely-edited Case metadata tab.
        self._tabs.addTab(self._sessions_view, "Sessions")
        self._tabs.addTab(self._build_case_tab(), "Case")
        self._tabs.addTab(self._build_examiner_tab(), "Examiner")
        self._tabs.addTab(self._build_scope_tab(), "Scope")
        self._tabs.addTab(self._custody_tab, "Custody")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header_strip)

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 16, 20, 16)
        body_layout.setSpacing(12)
        body_layout.addWidget(self._tabs, 1)
        layout.addWidget(body, 1)

    # ------------------------------------------------------------ API

    def show_sessions(self, sessions: list[InscriptionSession]) -> None:
        """Update the Sessions tab with a fresh listing."""
        self._sessions_view.show_sessions(sessions)

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
            (self._device_classes_edit, _join_csv(case.scope.device_classes)),
            (self._evidence_items_edit, _join_csv(case.scope.evidence_items)),
            (self._agencies_edit, _join_csv(case.scope.agencies)),
        ):
            edit.setText(value)
        select_exam_type(self._exam_type_combo, case.scope.exam_type)
        select_primary_tool(self._primary_tool_combo, case.scope.primary_tool)
        self._use_caseguide_check.setChecked(case.scope.use_caseguide)
        self._summary_edit.setPlainText(case.scope.summary)
        self._notes_edit.setPlainText(case.scope.notes)
        self._custody_tab.set_record(case.custody)

    # -------------------------------------------------------- builders

    def _build_action_buttons(
        self,
    ) -> tuple[QPushButton, QPushButton, QPushButton, QPushButton]:
        launch = QPushButton("Launch Inscription", self)
        launch.setProperty("role", "primary")
        launch.setMinimumHeight(34)
        launch.setMinimumWidth(180)
        launch.clicked.connect(self.launch_inscription_requested)

        caseguide = QPushButton("Open in CaseGuide", self)
        caseguide.setMinimumHeight(34)
        caseguide.setMinimumWidth(160)
        caseguide.setToolTip(
            "Open this case in CaseGuide to draft scope-tailored exam suggestions."
        )
        caseguide.clicked.connect(self.launch_caseguide_requested)

        save = QPushButton("Save changes", self)
        save.clicked.connect(self._on_save)
        close_ = QPushButton("Close", self)
        close_.clicked.connect(self.close_requested)
        return launch, caseguide, save, close_

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
        self._exam_type_combo = build_exam_type_combo(page)
        self._primary_tool_combo = build_primary_tool_combo(page)
        self._device_classes_edit = QLineEdit(page)
        self._evidence_items_edit = QLineEdit(page)
        self._agencies_edit = QLineEdit(page)
        self._summary_edit = QPlainTextEdit(page)
        self._summary_edit.setMaximumHeight(80)
        self._notes_edit = QPlainTextEdit(page)
        self._notes_edit.setMaximumHeight(140)
        self._use_caseguide_check = QCheckBox(
            "This case will use CaseGuide for procedural guidance",
            page,
        )
        self._use_caseguide_check.setToolTip(
            "Enables CaseGuide playbook matching for this case. "
            "Saving the case requires Exam type and Primary tool to be "
            "set when this is checked, since the matcher silently filters "
            "playbooks out when those fields are blank or off-vocabulary."
        )

        form = QFormLayout()
        form.addRow("Exam type", self._exam_type_combo)
        form.addRow("Primary tool", self._primary_tool_combo)
        form.addRow("Device classes", self._device_classes_edit)
        form.addRow("Evidence items", self._evidence_items_edit)
        form.addRow("Agencies", self._agencies_edit)
        form.addRow("Summary", self._summary_edit)
        form.addRow("Notes", self._notes_edit)
        form.addRow("", self._use_caseguide_check)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(form)
        return page

    # -------------------------------------------------------- internals

    def _on_save(self) -> None:
        if self._case is None:
            return
        exam_type = exam_type_value(self._exam_type_combo)
        primary_tool = primary_tool_value(self._primary_tool_combo)
        use_caseguide = self._use_caseguide_check.isChecked()
        if use_caseguide:
            missing: list[str] = []
            if not exam_type:
                missing.append("Exam type")
            if not primary_tool:
                missing.append("Primary tool")
            if missing:
                QMessageBox.warning(
                    self,
                    "CaseGuide fields incomplete",
                    "These fields are required while "
                    "'This case will use CaseGuide for procedural guidance' "
                    "is checked, because the playbook matcher would silently "
                    "filter every suggestion out otherwise:\n\n  - "
                    + "\n  - ".join(missing)
                    + "\n\nFill them in or uncheck the option.",
                )
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
                exam_type=exam_type,
                primary_tool=primary_tool,
                device_classes=_split_csv(self._device_classes_edit.text()),
                evidence_items=_split_csv(self._evidence_items_edit.text()),
                agencies=_split_csv(self._agencies_edit.text()),
                summary=self._summary_edit.toPlainText().strip(),
                notes=self._notes_edit.toPlainText().strip(),
                use_caseguide=use_caseguide,
            ),
            custody=self._custody_tab.to_record(),
        )
        self.save_requested.emit(updated)
