"""Read-only side panel that surfaces CaseGuide's suggestions feed.

CaseGuide writes :file:`<case-root>/.caseguide/suggestions.json`;
this panel reads that file and renders a checklist alongside the
session workspace. Inscription does not mutate the file — completion
is owned by CaseGuide. We just visualise it (greying completed rows)
and offer a "Draft as step" button that pushes a suggestion's action
into the open session as a new draft step.

The panel auto-hides itself when no case directory is set, when the
file is absent, or when the file is unparseable, so a case run
without CaseGuide just looks like normal Inscription.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QFileSystemWatcher, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from inscription.caseguide_link import (
    CaseguideDocument,
    CaseguideSuggestion,
    SuggestionsReadError,
    read_suggestions,
    suggestions_path,
)
from inscription.ui.widgets import (
    caption_label,
    horizontal_separator,
    muted_label,
    section_label,
)

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_SUGGESTION_ROLE = Qt.ItemDataRole.UserRole + 1
_PANEL_MIN_WIDTH = 280


class SuggestionsPanel(QWidget):
    """Renders CaseGuide's suggestions and emits "draft as step" requests."""

    #: Emitted when the examiner clicks "Draft as step" on a row. The
    #: controller catches it, builds a :class:`DraftStep`, and appends
    #: it to the open session.
    draft_step_requested = Signal(object)  # CaseguideSuggestion

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._case_dir: Path | None = None
        self._document: CaseguideDocument | None = None
        self._has_session = False
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_watch_event)
        self._watcher.directoryChanged.connect(self._on_watch_event)
        self._watched_paths: set[str] = set()
        # Atomic-rename writes (CaseGuide uses .tmp + replace) trip both
        # fileChanged and directoryChanged in the same event loop tick;
        # coalesce them so we only re-render once per actual write.
        self._reload_pending = False

        self.setMinimumWidth(_PANEL_MIN_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self._title = section_label("CaseGuide Suggestions", self)
        self._summary = muted_label("", self)
        self._scope = caption_label("", self)

        self._list = QListWidget(self)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setUniformItemSizes(False)
        self._list.setSpacing(2)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)

        self._detail_card = QFrame(self)
        self._detail_card.setProperty("role", "card")
        detail_layout = QVBoxLayout(self._detail_card)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.setSpacing(6)

        self._detail_action = QLabel("", self._detail_card)
        self._detail_action.setWordWrap(True)
        self._detail_expected = muted_label("", self._detail_card)
        self._detail_rationale = caption_label("", self._detail_card)
        self._draft_button = QPushButton("Draft as step", self._detail_card)
        self._draft_button.setProperty("role", "primary")
        self._draft_button.setEnabled(False)
        self._draft_button.clicked.connect(self._on_draft_clicked)

        detail_layout.addWidget(self._detail_action)
        detail_layout.addWidget(self._detail_expected)
        detail_layout.addWidget(self._detail_rationale)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self._draft_button)
        detail_layout.addLayout(button_row)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self._title)
        layout.addWidget(self._summary)
        layout.addWidget(self._scope)
        layout.addWidget(horizontal_separator(self))
        layout.addWidget(self._list, 1)
        layout.addWidget(self._detail_card)

        self.setVisible(False)

    # --------------------------------------------------------------- API

    def set_case_dir(self, case_dir: Path | None) -> None:
        """Tell the panel which case directory to watch."""
        self._case_dir = case_dir
        self._refresh_watcher()
        self.reload()

    def set_session_open(self, open_: bool) -> None:
        """Track whether a session is open so 'Draft as step' is gate-able."""
        self._has_session = open_
        self._update_draft_button_state()

    def reload(self) -> None:
        """Re-read suggestions.json and refresh the UI.

        Public so the controller can trigger a refresh after CaseGuide
        likely just wrote (e.g. after a session close that may have
        produced verification artefacts).
        """
        document: CaseguideDocument | None
        if self._case_dir is None:
            document = None
        else:
            try:
                document = read_suggestions(self._case_dir)
            except SuggestionsReadError:
                logger.exception(
                    "Could not read CaseGuide suggestions for %s; hiding panel",
                    self._case_dir,
                )
                document = None
        self._document = document
        self._render()

    # ---------------------------------------------------------- internals

    def _refresh_watcher(self) -> None:
        if self._watched_paths:
            self._watcher.removePaths(list(self._watched_paths))
            self._watched_paths.clear()
        if self._case_dir is None:
            return
        target = suggestions_path(self._case_dir)
        # Watch the directory unconditionally so we notice the file
        # being created later. Watch the file too when it already
        # exists — QFileSystemWatcher won't fire fileChanged otherwise.
        directory = target.parent
        if directory.exists():
            self._watcher.addPath(str(directory))
            self._watched_paths.add(str(directory))
        if target.exists():
            self._watcher.addPath(str(target))
            self._watched_paths.add(str(target))

    def _on_watch_event(self, path: str) -> None:
        logger.debug("CaseGuide suggestions watch event: %s", path)
        if self._reload_pending:
            return
        self._reload_pending = True
        QTimer.singleShot(0, self._flush_pending_reload)

    def _flush_pending_reload(self) -> None:
        self._reload_pending = False
        self._refresh_watcher()
        self.reload()

    def _render(self) -> None:
        document = self._document
        if document is None or not document.suggestions:
            self.setVisible(False)
            return

        self.setVisible(True)
        total = len(document.suggestions)
        completed = sum(1 for s in document.suggestions if s.completed)
        plural = "s" if total != 1 else ""
        self._summary.setText(
            f"{total} suggestion{plural} · {completed} completed"
        )
        if document.scope_summary:
            self._scope.setText(document.scope_summary)
            self._scope.setVisible(True)
        else:
            self._scope.setVisible(False)

        self._list.clear()
        for suggestion in document.suggestions:
            item = _build_item(suggestion)
            self._list.addItem(item)

        self._show_detail(None)

    def _on_selection_changed(self) -> None:
        item = self._list.currentItem()
        suggestion = item.data(_SUGGESTION_ROLE) if item is not None else None
        if isinstance(suggestion, CaseguideSuggestion):
            self._show_detail(suggestion)
        else:
            self._show_detail(None)

    def _show_detail(self, suggestion: CaseguideSuggestion | None) -> None:
        if suggestion is None:
            self._detail_action.setText("Select a suggestion above to see details.")
            self._detail_expected.setText("")
            self._detail_rationale.setText("")
            self._detail_expected.setVisible(False)
            self._detail_rationale.setVisible(False)
            self._draft_button.setEnabled(False)
            return
        self._detail_action.setText(suggestion.action)
        if suggestion.expected_result:
            self._detail_expected.setText(f"Expected: {suggestion.expected_result}")
            self._detail_expected.setVisible(True)
        else:
            self._detail_expected.setVisible(False)
        if suggestion.rationale:
            self._detail_rationale.setText(suggestion.rationale)
            self._detail_rationale.setVisible(True)
        else:
            self._detail_rationale.setVisible(False)
        self._update_draft_button_state()

    def _update_draft_button_state(self) -> None:
        item = self._list.currentItem()
        suggestion = item.data(_SUGGESTION_ROLE) if item is not None else None
        has_pick = isinstance(suggestion, CaseguideSuggestion)
        self._draft_button.setEnabled(has_pick and self._has_session)
        if has_pick and not self._has_session:
            self._draft_button.setToolTip("Open a session to draft this as a step.")
        else:
            self._draft_button.setToolTip("")

    def _on_draft_clicked(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        suggestion = item.data(_SUGGESTION_ROLE)
        if not isinstance(suggestion, CaseguideSuggestion):
            return
        self.draft_step_requested.emit(suggestion)


_COMPLETED_TEXT_COLOR = QColor(140, 140, 140)


def _build_item(suggestion: CaseguideSuggestion) -> QListWidgetItem:
    """Build a list item that visually communicates priority + completion.

    Lightweight on purpose: the priority sits in a leading bracket
    label and completed rows get a strikeout font + muted foreground.
    A custom delegate would be richer but Inscription is a consumer
    here — CaseGuide owns the designed view of this list.
    """
    item = QListWidgetItem(_row_label(suggestion))
    item.setData(_SUGGESTION_ROLE, suggestion)
    if suggestion.completed:
        font = item.font()
        font.setStrikeOut(True)
        item.setFont(font)
        item.setForeground(QBrush(_COMPLETED_TEXT_COLOR))
    return item


def _row_label(suggestion: CaseguideSuggestion) -> str:
    badge = (suggestion.priority or "").upper() or "RECOMMENDED"
    body = suggestion.action.strip().splitlines()[0] if suggestion.action else "(empty)"
    prefix = "✓ " if suggestion.completed else ""
    return f"{prefix}[{badge}] {body}"


__all__ = ["SuggestionsPanel"]
