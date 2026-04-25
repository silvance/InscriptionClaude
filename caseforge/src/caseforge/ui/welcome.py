"""The "no case open" landing page.

Shown when CaseForge launches and whenever the user closes the open
case. Offers a primary "New case…" CTA, a search box, and a list of
recent cases on disk so the examiner can jump back into yesterday's
work — or filter to one of yesterday's three hundred.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from caseforge.version import __version__

if TYPE_CHECKING:
    from caseforge.model import CaseSummary


class WelcomePage(QWidget):
    """Card with a New CTA, an Open-anywhere button, and a filtered recents list."""

    new_case_requested = Signal()
    open_case_requested = Signal(str)  # case directory path
    open_anywhere_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._all_summaries: list[CaseSummary] = []

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Filter by name, reference, or examiner…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search_changed)

        self._count_label = QLabel("", self)
        self._count_label.setStyleSheet("color: #6e6e73;")
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._list = QListWidget(self)
        self._list.setMinimumHeight(220)
        self._list.itemActivated.connect(self._on_activated)

        self._empty_label = QLabel("No cases yet — start one with the button above.", self)
        self._empty_label.setStyleSheet("color: #6e6e73; padding: 8px;")
        self._empty_label.setVisible(False)

        card = QFrame(self)
        card.setProperty("role", "card")
        card.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Expanding)
        card.setMaximumWidth(620)
        card.setMinimumWidth(460)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        search_row.addWidget(self._search, 1)
        search_row.addWidget(self._count_label)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(14)
        layout.addWidget(self._title())
        layout.addWidget(self._subtitle())
        layout.addSpacing(4)
        layout.addLayout(self._cta_row())
        layout.addSpacing(8)
        layout.addWidget(self._heading("Recent cases"))
        layout.addLayout(search_row)
        layout.addWidget(self._list, 1)
        layout.addWidget(self._empty_label)

        outer = QHBoxLayout(self)
        outer.addStretch(1)
        outer.addWidget(card, 1)
        outer.addStretch(1)

    # ----------------------------------------------------------- API

    def refresh(self, summaries: list[CaseSummary]) -> None:
        self._all_summaries = summaries
        self._render()

    # -------------------------------------------------------- internals

    def _on_search_changed(self, _text: str) -> None:
        self._render()

    def _render(self) -> None:
        query = self._search.text().strip().lower()
        if query:
            visible = [s for s in self._all_summaries if _matches(s, query)]
        else:
            visible = list(self._all_summaries)

        self._list.clear()
        for summary in visible:
            item = QListWidgetItem(self._format_summary(summary))
            item.setData(Qt.ItemDataRole.UserRole, summary.path)
            item.setToolTip(summary.path)
            self._list.addItem(item)

        if not self._all_summaries:
            self._list.setVisible(False)
            self._empty_label.setVisible(True)
            self._empty_label.setText("No cases yet — start one with the button above.")
            self._count_label.setText("")
            return

        if not visible:
            self._list.setVisible(False)
            self._empty_label.setVisible(True)
            self._empty_label.setText(f"No cases match {query!r}.")
        else:
            self._list.setVisible(True)
            self._empty_label.setVisible(False)

        total = len(self._all_summaries)
        if query:
            self._count_label.setText(f"{len(visible)} of {total}")
        else:
            self._count_label.setText(f"{total} case{'s' if total != 1 else ''}")

    def _on_activated(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(path, str):
            self.open_case_requested.emit(path)

    def _title(self) -> QLabel:
        title = QLabel("CaseForge", self)
        font = title.font()
        font.setPointSize(28)
        font.setBold(True)
        title.setFont(font)
        return title

    def _subtitle(self) -> QLabel:
        label = QLabel(
            f"Version {__version__} — set up a case folder, then launch "
            "Inscription pointed straight at it.",
            self,
        )
        label.setStyleSheet("color: #6e6e73;")
        label.setWordWrap(True)
        return label

    def _heading(self, text: str) -> QLabel:
        label = QLabel(text, self)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        label.setStyleSheet("margin-top: 8px;")
        return label

    def _cta_row(self) -> QHBoxLayout:
        new_btn = QPushButton("New case…", self)
        new_btn.setProperty("role", "primary")
        new_btn.setMinimumHeight(36)
        new_btn.setMinimumWidth(160)
        new_btn.clicked.connect(self.new_case_requested)

        open_btn = QPushButton("Open elsewhere…", self)
        open_btn.setMinimumHeight(36)
        open_btn.clicked.connect(self.open_anywhere_requested)

        row = QHBoxLayout()
        row.addWidget(new_btn)
        row.addWidget(open_btn)
        row.addStretch(1)
        return row

    @staticmethod
    def _format_summary(summary: CaseSummary) -> str:
        when = summary.updated_at.astimezone().strftime("%Y-%m-%d %H:%M")
        ref = f" · {summary.case_reference}" if summary.case_reference else ""
        examiner = f" · {summary.examiner_name}" if summary.examiner_name else ""
        return f"{summary.name}{ref}\n{when}{examiner}"


def _matches(summary: CaseSummary, query: str) -> bool:
    """Case-insensitive substring across the user-visible identifiers."""
    haystacks = (
        summary.name,
        summary.case_reference,
        summary.examiner_name,
    )
    return any(query in field.lower() for field in haystacks if field)
