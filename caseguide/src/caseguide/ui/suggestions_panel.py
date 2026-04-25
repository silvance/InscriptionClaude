"""Editable suggestions list for the right half of the main window.

A QListWidget shows one row per suggestion; selecting a row opens an
inline detail editor below for the action / expected_result /
rationale fields. Reorder + add + remove buttons sit above the list.
The panel emits ``changed()`` on every mutation so the host can drive
"Save" enablement and unsaved-changes warnings.
"""

from __future__ import annotations

import dataclasses
import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from caseguide.model import (
    PRIORITY_CHOICES,
    PRIORITY_RECOMMENDED,
    Suggestion,
)

logger = logging.getLogger(__name__)

#: Truncate the inline action preview at this length so list rows
#: stay one line each.
_ACTION_PREVIEW_LIMIT = 110
_ACTION_PREVIEW_ELLIPSIS_AT = 107


def _muted(text: str, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("muted", "true")
    label.setWordWrap(True)
    return label


class SuggestionsPanel(QWidget):
    """Editable list of :class:`caseguide.model.Suggestion` rows."""

    changed = Signal()

    _NEW_PREFIX = "new-"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._suggestions: list[Suggestion] = []
        self._suppress_signals = False
        self._new_counter = 0

        self._summary_label = _muted("No suggestions yet.", self)

        self._list = QListWidget(self)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)

        self._add_btn = QPushButton("Add", self)
        self._add_btn.clicked.connect(self._on_add)
        self._remove_btn = QPushButton("Remove", self)
        self._remove_btn.clicked.connect(self._on_remove)
        self._up_btn = QPushButton("Move up", self)
        self._up_btn.clicked.connect(lambda: self._on_move(-1))
        self._down_btn = QPushButton("Move down", self)
        self._down_btn.clicked.connect(lambda: self._on_move(+1))
        for btn in (self._remove_btn, self._up_btn, self._down_btn):
            btn.setEnabled(False)

        button_row = QHBoxLayout()
        button_row.addWidget(self._add_btn)
        button_row.addWidget(self._remove_btn)
        button_row.addStretch(1)
        button_row.addWidget(self._up_btn)
        button_row.addWidget(self._down_btn)

        self._editor = self._build_editor()
        self._empty_editor = _muted("Select a suggestion above to edit.", self)
        self._empty_editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_editor.setProperty("role", "card")
        self._empty_editor.setStyleSheet("padding: 24px;")

        self._editor_stack = QStackedWidget(self)
        self._editor_stack.addWidget(self._empty_editor)
        self._editor_stack.addWidget(self._editor)
        self._editor_stack.setCurrentIndex(0)

        rule = QFrame(self)
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setProperty("muted", "true")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addWidget(self._summary_label)
        layout.addLayout(button_row)
        layout.addWidget(self._list, 2)
        layout.addWidget(rule)
        layout.addWidget(self._editor_stack, 1)

    # ------------------------------------------------------------- API

    def set_suggestions(self, suggestions: list[Suggestion]) -> None:
        """Replace the list. Used after Generate or after loading from disk."""
        self._suggestions = list(suggestions)
        self._render(select_index=0 if suggestions else None)

    def suggestions(self) -> list[Suggestion]:
        """Return the current edited list (does not include in-flight typing)."""
        self._commit_pending_edits()
        return list(self._suggestions)

    # -------------------------------------------------------- builders

    def _build_editor(self) -> QWidget:
        page = QWidget(self)

        self._priority_combo = QComboBox(page)
        for priority in PRIORITY_CHOICES:
            self._priority_combo.addItem(priority.title(), priority)
        self._priority_combo.currentIndexChanged.connect(self._on_field_changed)

        self._category_edit = QLineEdit(page)
        self._category_edit.setPlaceholderText("e.g. acquisition, verification, analysis")
        self._category_edit.editingFinished.connect(self._on_field_changed)

        self._action_edit = QPlainTextEdit(page)
        self._action_edit.setPlaceholderText("Imperative: what the examiner should do.")
        self._action_edit.setMaximumHeight(120)
        self._action_edit.textChanged.connect(self._on_field_changed)

        self._expected_edit = QPlainTextEdit(page)
        self._expected_edit.setPlaceholderText(
            "What success looks like. The examiner overwrites this with the actual result."
        )
        self._expected_edit.setMaximumHeight(80)
        self._expected_edit.textChanged.connect(self._on_field_changed)

        self._rationale_edit = QPlainTextEdit(page)
        self._rationale_edit.setPlaceholderText(
            "Why this step matters; cite standards or SOPs where relevant."
        )
        self._rationale_edit.setMaximumHeight(80)
        self._rationale_edit.textChanged.connect(self._on_field_changed)

        form = QFormLayout()
        form.addRow("Priority", self._priority_combo)
        form.addRow("Category", self._category_edit)
        form.addRow("Action", self._action_edit)
        form.addRow("Expected result", self._expected_edit)
        form.addRow("Rationale", self._rationale_edit)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(form)
        return page

    # -------------------------------------------------------- internals

    def _render(self, *, select_index: int | None = None) -> None:
        self._suppress_signals = True
        self._list.clear()
        for suggestion in self._suggestions:
            self._list.addItem(_make_item(suggestion))
        self._suppress_signals = False
        self._update_summary()
        if select_index is not None and 0 <= select_index < self._list.count():
            self._list.setCurrentRow(select_index)
        else:
            self._show_empty_editor()
        self._update_button_state()

    def _update_summary(self) -> None:
        if not self._suggestions:
            self._summary_label.setText("No suggestions yet.")
            return
        plural = "s" if len(self._suggestions) != 1 else ""
        required = sum(1 for s in self._suggestions if s.priority == "required")
        self._summary_label.setText(
            f"{len(self._suggestions)} suggestion{plural} · {required} required"
        )

    def _update_button_state(self) -> None:
        has_selection = self._list.currentRow() >= 0
        self._remove_btn.setEnabled(has_selection)
        idx = self._list.currentRow()
        self._up_btn.setEnabled(has_selection and idx > 0)
        self._down_btn.setEnabled(
            has_selection and 0 <= idx < self._list.count() - 1
        )

    def _on_selection_changed(self) -> None:
        if self._suppress_signals:
            return
        idx = self._list.currentRow()
        if 0 <= idx < len(self._suggestions):
            self._populate_editor(self._suggestions[idx])
            self._editor_stack.setCurrentIndex(1)
        else:
            self._show_empty_editor()
        self._update_button_state()

    def _show_empty_editor(self) -> None:
        self._editor_stack.setCurrentIndex(0)

    def _populate_editor(self, suggestion: Suggestion) -> None:
        self._suppress_signals = True
        for index in range(self._priority_combo.count()):
            if self._priority_combo.itemData(index) == suggestion.priority:
                self._priority_combo.setCurrentIndex(index)
                break
        self._category_edit.setText(suggestion.category)
        self._action_edit.setPlainText(suggestion.action)
        self._expected_edit.setPlainText(suggestion.expected_result)
        self._rationale_edit.setPlainText(suggestion.rationale)
        self._suppress_signals = False

    def _on_field_changed(self) -> None:
        if self._suppress_signals:
            return
        idx = self._list.currentRow()
        if not (0 <= idx < len(self._suggestions)):
            return
        priority = self._priority_combo.currentData() or PRIORITY_RECOMMENDED
        updated = dataclasses.replace(
            self._suggestions[idx],
            priority=str(priority),
            category=self._category_edit.text().strip(),
            action=self._action_edit.toPlainText().strip(),
            expected_result=self._expected_edit.toPlainText().strip(),
            rationale=self._rationale_edit.toPlainText().strip(),
        )
        self._suggestions[idx] = updated
        item = self._list.item(idx)
        if item is not None:
            _refresh_item(item, updated)
        self._update_summary()
        self.changed.emit()

    def _commit_pending_edits(self) -> None:
        # Force any in-flight QLineEdit signal to fire so the current
        # row reflects what's typed before callers read suggestions().
        if self._category_edit.hasFocus():
            self._category_edit.clearFocus()

    def _on_add(self) -> None:
        self._new_counter += 1
        new = Suggestion(
            id=f"{self._NEW_PREFIX}{self._new_counter}",
            action="(describe the new action)",
            priority=PRIORITY_RECOMMENDED,
        )
        self._suggestions.append(new)
        self._render(select_index=len(self._suggestions) - 1)
        self.changed.emit()

    def _on_remove(self) -> None:
        idx = self._list.currentRow()
        if not (0 <= idx < len(self._suggestions)):
            return
        del self._suggestions[idx]
        next_select = min(idx, len(self._suggestions) - 1) if self._suggestions else None
        self._render(select_index=next_select)
        self.changed.emit()

    def _on_move(self, delta: int) -> None:
        idx = self._list.currentRow()
        target = idx + delta
        if not (0 <= idx < len(self._suggestions)):
            return
        if not (0 <= target < len(self._suggestions)):
            return
        self._suggestions[idx], self._suggestions[target] = (
            self._suggestions[target],
            self._suggestions[idx],
        )
        self._render(select_index=target)
        self.changed.emit()


def _make_item(suggestion: Suggestion) -> QListWidgetItem:
    item = QListWidgetItem(_format_label(suggestion))
    item.setData(Qt.ItemDataRole.UserRole, suggestion.id)
    return item


def _refresh_item(item: QListWidgetItem, suggestion: Suggestion) -> None:
    item.setText(_format_label(suggestion))
    item.setData(Qt.ItemDataRole.UserRole, suggestion.id)


def _format_label(suggestion: Suggestion) -> str:
    badge = suggestion.priority.upper()
    body = suggestion.action.strip().splitlines()[0] if suggestion.action else "(empty)"
    if len(body) > _ACTION_PREVIEW_LIMIT:
        body = body[:_ACTION_PREVIEW_ELLIPSIS_AT] + "…"
    category = f"  ·  {suggestion.category}" if suggestion.category else ""
    return f"[{badge}] {body}{category}"
