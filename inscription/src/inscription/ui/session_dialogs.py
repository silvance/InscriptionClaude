"""Session picker + new-session dialogs."""

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
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from inscription.model import SessionManifest


@dataclass(frozen=True, slots=True)
class SessionListChoice:
    """What the user picked in :class:`SessionListDialog`."""

    open_slug: str | None = None
    new_name: str | None = None


class SessionListDialog(QDialog):
    """Pick an existing session or start a new one."""

    def __init__(
        self,
        *,
        sessions: list[tuple[str, SessionManifest]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Open session")
        self.resize(560, 420)

        self._choice: SessionListChoice = SessionListChoice()

        self._list = QListWidget(self)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        for slug, manifest in sessions:
            started = manifest.started_at.strftime("%Y-%m-%d %H:%M")
            item = QListWidgetItem(f"{manifest.name}\n{started} · {manifest.step_count} steps")
            item.setData(Qt.ItemDataRole.UserRole, slug)
            self._list.addItem(item)
        self._list.itemDoubleClicked.connect(lambda _i: self._accept_open())

        new_btn = QPushButton("New session…", self)
        new_btn.clicked.connect(self._accept_new)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Open).clicked.connect(self._accept_open)
        buttons.rejected.connect(self.reject)

        row = QHBoxLayout()
        row.addWidget(new_btn)
        row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Existing sessions", self))
        layout.addWidget(self._list, 1)
        layout.addLayout(row)
        layout.addWidget(buttons)

    def choice(self) -> SessionListChoice:
        return self._choice

    def _accept_open(self) -> None:
        items = self._list.selectedItems()
        if not items:
            return
        slug = items[0].data(Qt.ItemDataRole.UserRole)
        if isinstance(slug, str):
            self._choice = SessionListChoice(open_slug=slug)
            self.accept()

    def _accept_new(self) -> None:
        dialog = NewSessionDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = dialog.name()
        if name:
            self._choice = SessionListChoice(new_name=name)
            self.accept()


class NewSessionDialog(QDialog):
    """Collect a name for a new session."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New session")
        self.resize(420, 120)

        self._name = QLineEdit(self)
        self._name.setPlaceholderText("e.g. Reset AWS password")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self._ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setEnabled(False)
        self._name.textChanged.connect(lambda text: self._ok_btn.setEnabled(bool(text.strip())))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Session name", self))
        layout.addWidget(self._name)
        layout.addStretch(1)
        layout.addWidget(buttons)

    def name(self) -> str:
        return self._name.text().strip()
