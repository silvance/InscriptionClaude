"""New-case form.

Three tabs (Case / Examiner / Scope) so the form doesn't read as one
intimidating wall. The Case tab carries the only required field —
the case name — so an examiner who only wants a placeholder folder
can hit Save after typing the name.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from caseforge.model import Case, ExaminerIdentity, ExamScope, utcnow


def _split_csv(text: str) -> list[str]:
    """Split a comma-separated free-form list field into trimmed entries."""
    return [chunk.strip() for chunk in text.split(",") if chunk.strip()]


def _join_csv(items: list[str]) -> str:
    return ", ".join(items)


class NewCaseDialog(QDialog):
    """Collect everything needed to populate ``case.json`` for a new case."""

    def __init__(
        self,
        *,
        examiner_defaults: ExaminerIdentity,
        scope_defaults: ExamScope,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New case")
        self.resize(620, 540)

        self._examiner_defaults = examiner_defaults
        self._scope_defaults = scope_defaults
        self._draft: Case | None = None

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._build_case_tab(), "Case")
        self._tabs.addTab(self._build_examiner_tab(), "Examiner")
        self._tabs.addTab(self._build_scope_tab(), "Scope")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setProperty("role", "primary")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(self._tabs, 1)
        layout.addWidget(buttons)

    # ----------------------------------------------------------- result

    def draft(self) -> Case | None:
        """The :class:`Case` to persist, or None if cancelled."""
        return self._draft

    # -------------------------------------------------------- builders

    def _build_case_tab(self) -> QWidget:
        page = QWidget(self)
        self._name_edit = QLineEdit(page)
        self._name_edit.setPlaceholderText("e.g. Operation Stardust")
        self._reference_edit = QLineEdit(page)
        self._reference_edit.setPlaceholderText("e.g. HSV-2026-0317")

        hint = QLabel(
            "The case name becomes the folder name (filesystem-safe).\n"
            "Case reference is the external case number you'll search by later.",
            page,
        )
        hint.setStyleSheet("color: #6e6e73;")
        hint.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Case name *", self._name_edit)
        form.addRow("Case reference", self._reference_edit)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addStretch(1)
        return page

    def _build_examiner_tab(self) -> QWidget:
        page = QWidget(self)
        self._examiner_name_edit = QLineEdit(self._examiner_defaults.name, page)
        self._examiner_name_edit.setPlaceholderText("e.g. Alex Smith")
        self._examiner_org_edit = QLineEdit(self._examiner_defaults.organisation, page)
        self._examiner_org_edit.setPlaceholderText("e.g. Cyber Crimes Unit")
        self._examiner_badge_edit = QLineEdit(self._examiner_defaults.badge_id, page)
        self._examiner_badge_edit.setPlaceholderText("e.g. CCU-0421")

        hint = QLabel(
            "Pre-filled from your saved defaults (Edit → Settings). "
            "Inscription's forensic-notes header reads from these fields.",
            page,
        )
        hint.setStyleSheet("color: #6e6e73;")
        hint.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Name", self._examiner_name_edit)
        form.addRow("Organisation", self._examiner_org_edit)
        form.addRow("Badge / ID", self._examiner_badge_edit)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addStretch(1)
        return page

    def _build_scope_tab(self) -> QWidget:
        page = QWidget(self)
        self._exam_type_edit = QLineEdit(self._scope_defaults.exam_type, page)
        self._exam_type_edit.setPlaceholderText("e.g. CSAM possession")

        self._device_classes_edit = QLineEdit(_join_csv(self._scope_defaults.device_classes), page)
        self._device_classes_edit.setPlaceholderText(
            "comma-separated, e.g. windows-laptop, mobile-android"
        )

        self._evidence_items_edit = QLineEdit(_join_csv(self._scope_defaults.evidence_items), page)
        self._evidence_items_edit.setPlaceholderText(
            "comma-separated, e.g. E01 image, Cellebrite extraction"
        )

        self._agencies_edit = QLineEdit(_join_csv(self._scope_defaults.agencies), page)
        self._agencies_edit.setPlaceholderText("comma-separated, e.g. FBI, ICAC")

        self._summary_edit = QPlainTextEdit(self._scope_defaults.summary, page)
        self._summary_edit.setPlaceholderText(
            "Short paragraph the report builder pulls into the executive summary."
        )
        self._summary_edit.setMaximumHeight(80)

        self._notes_edit = QPlainTextEdit(self._scope_defaults.notes, page)
        self._notes_edit.setPlaceholderText("Free-form intake notes for the examiner.")
        self._notes_edit.setMaximumHeight(120)

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

    # ------------------------------------------------------------- accept

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            self._tabs.setCurrentIndex(0)
            self._name_edit.setFocus()
            return
        now = utcnow()
        self._draft = Case(
            name=name,
            case_reference=self._reference_edit.text().strip(),
            created_at=now,
            updated_at=now,
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
        self.accept()
