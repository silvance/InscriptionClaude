"""Session picker + new-session dialogs.

The picker is the user's main entry point when they hit "Open Session…"
from the welcome page or from the File menu. It needs to scale to
hundreds of sessions, so the list has a search filter and the items are
roomy enough to scan at a glance.
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
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
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
        self.resize(640, 480)

        self._choice: SessionListChoice = SessionListChoice()
        # Newest first so the most-likely target tops the list.
        self._sessions: list[tuple[str, SessionManifest]] = sorted(
            sessions, key=lambda pair: pair[1].started_at, reverse=True
        )

        heading = QLabel("Existing sessions", self)
        heading_font = heading.font()
        heading_font.setBold(True)
        heading_font.setPointSize(heading_font.pointSize() + 1)
        heading.setFont(heading_font)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Filter by name…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)

        self._list = QListWidget(self)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setUniformItemSizes(False)
        self._list.itemDoubleClicked.connect(lambda _i: self._accept_open())
        self._list.currentItemChanged.connect(self._update_open_button)

        self._empty = QLabel(
            "No sessions yet — start a new one to begin.",
            self,
        )
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet("color: #6e6e73; padding: 32px;")
        self._empty.setProperty("role", "card")

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._list)
        self._stack.addWidget(self._empty)

        new_btn = QPushButton("New session…", self)
        new_btn.clicked.connect(self._accept_new)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._open_btn = self._buttons.button(QDialogButtonBox.StandardButton.Open)
        self._open_btn.setProperty("role", "primary")
        self._open_btn.clicked.connect(self._accept_open)
        self._buttons.rejected.connect(self.reject)

        row = QHBoxLayout()
        row.addWidget(new_btn)
        row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(heading)
        layout.addWidget(self._search)
        layout.addWidget(self._stack, 1)
        layout.addLayout(row)
        layout.addWidget(self._buttons)

        self._populate(self._sessions)
        self._update_open_button()

    def choice(self) -> SessionListChoice:
        return self._choice

    # ------------------------------------------------------------- population

    def _populate(self, sessions: list[tuple[str, SessionManifest]]) -> None:
        self._list.clear()
        for slug, manifest in sessions:
            item = QListWidgetItem(_format_session_label(manifest))
            item.setData(Qt.ItemDataRole.UserRole, slug)
            self._list.addItem(item)
        self._stack.setCurrentIndex(0 if sessions else 1)

    def _apply_filter(self, query: str) -> None:
        q = query.strip().lower()
        if not q:
            self._populate(self._sessions)
            return
        filtered = [
            (slug, m)
            for slug, m in self._sessions
            if q in m.name.lower() or q in slug.lower()
        ]
        self._populate(filtered)

    def _update_open_button(self, *_args: object) -> None:
        self._open_btn.setEnabled(self._list.currentItem() is not None)

    # ----------------------------------------------------------------- accept

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
        self.resize(440, 140)

        heading = QLabel("Session name", self)
        heading_font = heading.font()
        heading_font.setBold(True)
        heading.setFont(heading_font)

        self._name = QLineEdit(self)
        self._name.setPlaceholderText("e.g. Reset AWS password")

        hint = QLabel(
            "Pick something you'll recognise later. You can rename later "
            "by editing the manifest.",
            self,
        )
        hint.setStyleSheet("color: #6e6e73;")
        hint.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self._ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setProperty("role", "primary")
        self._ok_btn.setEnabled(False)
        self._name.textChanged.connect(lambda text: self._ok_btn.setEnabled(bool(text.strip())))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(heading)
        layout.addWidget(self._name)
        layout.addWidget(hint)
        layout.addStretch(1)
        layout.addWidget(buttons)

    def name(self) -> str:
        return self._name.text().strip()


def _format_session_label(manifest: SessionManifest) -> str:
    """Two-line label rendered in the session picker rows."""
    started = manifest.started_at.strftime("%Y-%m-%d %H:%M")
    plural = "s" if manifest.step_count != 1 else ""
    return f"{manifest.name}\n{started}  ·  {manifest.step_count} step{plural}"
