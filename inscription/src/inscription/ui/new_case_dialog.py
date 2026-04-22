"""Dialog for creating a new case.

Collects case number, title, examiner, and optional agency/description.
Case number is validated against :attr:`Config.case_number_regex` before
the OK button enables. The dialog creates nothing itself; it returns a
:class:`NewCaseSpec` and the controller owns actual creation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class NewCaseSpec:
    """User-supplied data for a new case."""

    case_number: str
    title: str
    examiner: str
    agency: str
    description: str


class NewCaseDialog(QDialog):
    """Modal form for creating a new case."""

    def __init__(
        self,
        *,
        case_number_regex: str,
        default_examiner: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Case")
        self.setModal(True)
        self.resize(500, 360)

        self._regex = re.compile(case_number_regex)

        self._case_number = QLineEdit(self)
        self._case_number.setPlaceholderText("HSV-2026-0317")
        # Qt-compatible anchor-bound regex to feed the validator widget.
        validator = QRegularExpressionValidator(case_number_regex, self)
        self._case_number.setValidator(validator)

        self._title = QLineEdit(self)
        self._title.setPlaceholderText("Short description of the examination")

        self._examiner = QLineEdit(self)
        self._examiner.setText(default_examiner)

        self._agency = QLineEdit(self)

        self._description = QPlainTextEdit(self)
        self._description.setPlaceholderText("Longer notes about the case (optional)")

        self._status = QLabel("", self)
        self._status.setStyleSheet("color: palette(placeholder-text);")

        form = QFormLayout()
        form.addRow("Case number *", self._case_number)
        form.addRow("Title *", self._title)
        form.addRow("Examiner *", self._examiner)
        form.addRow("Agency", self._agency)
        form.addRow("Description", self._description)
        form.addRow("", self._status)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        ok = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert ok is not None
        ok.setEnabled(False)
        self._ok_button = ok

        layout = form
        # QFormLayout doesn't span buttons naturally; add via a wrapper widget.
        wrapper = QVBoxLayout(self)
        wrapper.addLayout(layout)
        wrapper.addWidget(self._buttons, alignment=Qt.AlignmentFlag.AlignRight)

        # Wire validation.
        self._case_number.textChanged.connect(self._validate)
        self._title.textChanged.connect(self._validate)
        self._examiner.textChanged.connect(self._validate)
        self._validate()

    # ---------------------------------------------------------- validation

    def _validate(self) -> None:
        case_number = self._case_number.text().strip()
        title = self._title.text().strip()
        examiner = self._examiner.text().strip()

        if not case_number:
            self._status.setText("Case number is required.")
            self._ok_button.setEnabled(False)
            return
        if not self._regex.match(case_number):
            self._status.setText(
                f"Case number does not match required format: {self._regex.pattern}"
            )
            self._ok_button.setEnabled(False)
            return
        if not title:
            self._status.setText("Title is required.")
            self._ok_button.setEnabled(False)
            return
        if not examiner:
            self._status.setText("Examiner is required.")
            self._ok_button.setEnabled(False)
            return

        self._status.setText("")
        self._ok_button.setEnabled(True)

    # ------------------------------------------------------------- result

    def spec(self) -> NewCaseSpec:
        """Return the user-supplied values. Only call after ``exec() == Accepted``."""
        return NewCaseSpec(
            case_number=self._case_number.text().strip(),
            title=self._title.text().strip(),
            examiner=self._examiner.text().strip(),
            agency=self._agency.text().strip(),
            description=self._description.toPlainText().strip(),
        )
