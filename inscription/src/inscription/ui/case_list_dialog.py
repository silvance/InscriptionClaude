"""Case picker shown at application startup.

Lists all cases in the configured workspace, with a ``New`` button that
opens the :class:`NewCaseDialog`. The picker is owned by the controller;
it returns either a case number to open, a :class:`NewCaseSpec` to create,
or ``None`` if the user cancels.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from inscription.ui.new_case_dialog import NewCaseDialog, NewCaseSpec

if TYPE_CHECKING:
    from inscription.cases.models import CaseManifest


@dataclass(frozen=True, slots=True, kw_only=True)
class CaseListChoice:
    """The outcome of the case list dialog.

    Exactly one of ``open_case_number`` or ``new_case`` is set; both are
    ``None`` if the user cancelled.
    """

    open_case_number: str | None = None
    new_case: NewCaseSpec | None = None


class CaseListDialog(QDialog):
    """Modal case picker."""

    def __init__(
        self,
        *,
        manifests: list[CaseManifest],
        case_number_regex: str,
        default_examiner: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Open Case")
        self.setModal(True)
        self.resize(640, 420)

        self._manifests = manifests
        self._regex = case_number_regex
        self._default_examiner = default_examiner
        self._choice = CaseListChoice()

        heading = QLabel("Select a case to open, or create a new one.", self)

        self._list = QListWidget(self)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setAlternatingRowColors(True)
        self._populate()

        self._new_button = QPushButton("New Case…", self)
        self._new_button.clicked.connect(self._on_new_case)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self._buttons.accepted.connect(self._on_open)
        self._buttons.rejected.connect(self.reject)

        open_button = self._buttons.button(QDialogButtonBox.StandardButton.Open)
        assert open_button is not None
        open_button.setEnabled(False)
        self._open_button = open_button

        self._list.itemSelectionChanged.connect(self._update_open_enabled)
        self._list.itemDoubleClicked.connect(lambda _: self._on_open())

        button_row = QHBoxLayout()
        button_row.addWidget(self._new_button)
        button_row.addStretch(1)
        button_row.addWidget(self._buttons)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(self._list, 1)
        layout.addLayout(button_row)

    # ------------------------------------------------------------ population

    def _populate(self) -> None:
        self._list.clear()
        if not self._manifests:
            placeholder = QListWidgetItem("(no cases yet — click New Case)")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(placeholder)
            return
        for manifest in self._manifests:
            item = QListWidgetItem(
                f"{manifest.case_number}    {manifest.title}\n"
                f"    examiner: {manifest.examiner}    steps: {manifest.step_count}"
            )
            item.setData(Qt.ItemDataRole.UserRole, manifest.case_number)
            self._list.addItem(item)

    def _update_open_enabled(self) -> None:
        item = self._list.currentItem()
        self._open_button.setEnabled(
            item is not None and bool(item.flags() & Qt.ItemFlag.ItemIsSelectable)
        )

    # ------------------------------------------------------------ actions

    def _on_open(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        case_number = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(case_number, str):
            return
        self._choice = CaseListChoice(open_case_number=case_number)
        self.accept()

    def _on_new_case(self) -> None:
        dialog = NewCaseDialog(
            case_number_regex=self._regex,
            default_examiner=self._default_examiner,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._choice = CaseListChoice(new_case=dialog.spec())
        self.accept()

    # ------------------------------------------------------------ result

    def choice(self) -> CaseListChoice:
        """Return the user's choice after ``exec()``."""
        return self._choice
