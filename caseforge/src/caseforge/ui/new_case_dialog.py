"""New-case form.

Three tabs (Case / Examiner / Scope) so the form doesn't read as one
intimidating wall. The Case tab carries the only required field —
the case name — so an examiner who only wants a placeholder folder
can hit Save after typing the name.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from caseforge.model import Case, CustodyRecord, ExaminerIdentity, ExamScope, utcnow
from caseforge.templates import is_no_template, list_templates
from caseforge.ui.custody_tab import CustodyTab
from caseforge.ui.widgets import (
    build_exam_type_combo,
    build_primary_tool_combo,
    exam_type_value,
    primary_tool_value,
    select_exam_type,
    select_primary_tool,
)


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

        self._custody_tab = CustodyTab(self)
        self._custody_tab.set_record(CustodyRecord())

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._build_case_tab(), "Case")
        self._tabs.addTab(self._build_examiner_tab(), "Examiner")
        self._scope_tab_index = self._tabs.addTab(self._build_scope_tab(), "Scope")
        self._tabs.addTab(self._custody_tab, "Custody")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setProperty("role", "primary")
        # Enter saves; explicit setDefault rather than relying on
        # creation-order heuristics inside QDialogButtonBox.
        save_btn.setDefault(True)
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
        hint.setProperty("muted", "true")
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
        hint.setProperty("muted", "true")
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
        self._exam_type_combo = build_exam_type_combo(page)
        select_exam_type(self._exam_type_combo, self._scope_defaults.exam_type)

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

        self._primary_tool_combo = build_primary_tool_combo(page)
        select_primary_tool(self._primary_tool_combo, self._scope_defaults.primary_tool)

        self._summary_edit = QPlainTextEdit(self._scope_defaults.summary, page)
        self._summary_edit.setPlaceholderText(
            "Short paragraph the report builder pulls into the executive summary."
        )
        self._summary_edit.setMaximumHeight(80)

        self._notes_edit = QPlainTextEdit(self._scope_defaults.notes, page)
        self._notes_edit.setPlaceholderText("Free-form intake notes for the examiner.")
        self._notes_edit.setMaximumHeight(120)

        self._use_caseguide_check = QCheckBox(
            "This case will use CaseGuide for procedural guidance",
            page,
        )
        self._use_caseguide_check.setChecked(self._scope_defaults.use_caseguide)
        self._use_caseguide_check.setToolTip(
            "Enables CaseGuide playbook matching for this case. "
            "Saving requires Exam type and Primary tool to be set when "
            "this is checked, since the matcher silently filters playbooks "
            "out otherwise."
        )

        # Template picker drives all six fields below; selecting one
        # overwrites whatever the user has typed so far.
        self._templates = list_templates()
        self._template_combo = QComboBox(page)
        for template in self._templates:
            self._template_combo.addItem(template.label, template.id)
        self._template_combo.currentIndexChanged.connect(self._on_template_changed)

        template_hint = QLabel(
            "Picking a template fills the fields below -- edit freely after.",
            page,
        )
        template_hint.setProperty("muted", "true")
        template_hint.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Apply template", self._template_combo)
        form.addRow("", template_hint)
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

    def _on_template_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._templates):
            return
        template = self._templates[index]
        if is_no_template(template):
            return
        self._apply_scope(template.scope)

    def _apply_scope(self, scope: ExamScope) -> None:
        select_exam_type(self._exam_type_combo, scope.exam_type)
        select_primary_tool(self._primary_tool_combo, scope.primary_tool)
        self._device_classes_edit.setText(_join_csv(scope.device_classes))
        self._evidence_items_edit.setText(_join_csv(scope.evidence_items))
        self._agencies_edit.setText(_join_csv(scope.agencies))
        self._summary_edit.setPlainText(scope.summary)
        self._notes_edit.setPlainText(scope.notes)
        self._use_caseguide_check.setChecked(scope.use_caseguide)

    # ------------------------------------------------------------- accept

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            self._tabs.setCurrentIndex(0)
            self._name_edit.setFocus()
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
                # Jump the user to the Scope tab so the field that needs
                # filling is right there, rather than a vague modal alert
                # followed by them hunting for the tab.
                self._tabs.setCurrentIndex(self._scope_tab_index)
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
        self.accept()
