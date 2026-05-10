"""The central widget shown while a session is open.

Splits horizontally: step list on the left, step editor in the
middle, optional CaseGuide suggestions panel on the right. The
suggestions panel is hidden whenever the case directory has no
``.caseguide/suggestions.json`` so a session running without the
sibling tool just looks like the original two-pane layout.

Exposes signals the controller listens on and does not hold
repository state itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from inscription.ui.step_editor import StepEditorPanel
from inscription.ui.step_list import StepListWidget
from inscription.ui.suggestions_panel import SuggestionsPanel
from inscription.util import format_local

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from inscription.storage import SessionRepository, SubmittedMarker


class SessionWorkspaceWidget(QWidget):
    """Step list + step editor + optional CaseGuide suggestions panel."""

    step_fields_edited = Signal(int, str, str)  # step_id, action, result
    step_suppressed = Signal(int, bool)
    step_evidentiary_toggled = Signal(int, bool)
    steps_reordered = Signal(list)
    merge_requested = Signal(int, int)
    split_requested = Signal(int)
    #: Forwarded from the suggestions panel; controller catches it
    #: and inserts a new draft step from the chosen suggestion.
    draft_step_requested = Signal(object)  # CaseguideSuggestion
    #: Emitted when the operator clicks "Reopen for editing" on the
    #: submitted-session banner. Controller catches it, prompts to
    #: confirm, and on confirm clears the on-disk marker.
    reopen_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._repository: SessionRepository | None = None
        self._event_times: dict[int, datetime] = {}

        self._list = StepListWidget(self)
        self._editor = StepEditorPanel(self)
        self._suggestions = SuggestionsPanel(self)

        self._list.step_selected.connect(self._on_step_selected)
        self._list.step_deselected.connect(self._editor.clear)
        self._list.steps_reordered.connect(self.steps_reordered)
        self._list.merge_requested.connect(self.merge_requested)
        self._list.split_requested.connect(self.split_requested)
        self._editor.fields_edited.connect(self.step_fields_edited)
        self._editor.step_suppressed.connect(self.step_suppressed)
        self._editor.evidentiary_toggled.connect(self.step_evidentiary_toggled)
        self._suggestions.draft_step_requested.connect(self.draft_step_requested)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._list)
        splitter.addWidget(self._editor)
        splitter.addWidget(self._suggestions)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)

        # Submitted-session banner: hidden by default, shown when the
        # controller calls show_submitted_banner(). Sits above the
        # splitter so it never gets occluded by the step list / editor.
        self._submitted_banner = _SubmittedBanner(self)
        self._submitted_banner.reopen_clicked.connect(self.reopen_requested)
        self._submitted_banner.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self._submitted_banner)
        layout.addWidget(splitter)

    # ------------------------------------------------------------ API

    def set_repository(self, repository: SessionRepository) -> None:
        self._repository = repository
        self._suggestions.set_session_open(open_=True)
        self.reload()

    def clear_repository(self) -> None:
        self._repository = None
        self._suggestions.set_session_open(open_=False)
        self._list.clear_steps()
        self._editor.clear()

    def set_case_dir(self, case_dir: Path | None) -> None:
        """Tell the suggestions panel which case directory to watch."""
        self._suggestions.set_case_dir(case_dir)

    def reload_suggestions(self) -> None:
        """Refresh the suggestions panel from disk."""
        self._suggestions.reload()

    def reload(self) -> None:
        if self._repository is None:
            return
        steps = self._repository.list_steps()
        screenshots = {s.id: s for s in self._repository.list_screenshots() if s.id is not None}
        self._event_times = {
            e.id: e.occurred_at for e in self._repository.list_events() if e.id is not None
        }
        self._list.load(
            steps=steps,
            screenshots=screenshots,
            event_times=self._event_times,
            session_root=self._repository.session.root,
        )
        self._editor.clear()

    def flush_pending(self) -> None:
        self._editor.flush_pending()

    # --------------------------------------------------------- internals

    def _on_step_selected(self, step_id: int) -> None:
        if self._repository is None:
            return
        step = self._repository.get_step(step_id)
        if step is None:
            self._editor.clear()
            return
        shot = self._repository.get_screenshot(step.screenshot_id) if step.screenshot_id else None
        started_at = next(
            (self._event_times[eid] for eid in step.source_event_ids if eid in self._event_times),
            None,
        )
        self._editor.show_step(
            step,
            screenshot=shot,
            started_at=started_at,
            session_root=self._repository.session.root,
        )

    # ---------------------------------------------------------- banner

    def set_submitted_marker(self, marker: SubmittedMarker | None) -> None:
        """Show or hide the read-only banner and toggle child widgets.

        ``marker`` carries the timestamp + optional examiner / format
        strings the banner renders. ``None`` hides the banner.

        Also forwards the read-only state to the step list, step editor,
        and suggestions panel so their *appearance* matches what the
        controller's slot gates already enforce -- closes the seam
        where the banner says read-only but the fields still look
        interactive. The controller's gates remain the source of truth
        for rejecting writes; this is purely visual.
        """
        if marker is None:
            self._submitted_banner.hide()
            self._set_children_read_only(False)
        else:
            self._submitted_banner.show_marker(marker)
            self._submitted_banner.show()
            self._set_children_read_only(True)

    def _set_children_read_only(self, read_only: bool) -> None:
        self._list.set_read_only(read_only)
        self._editor.set_read_only(read_only)
        self._suggestions.set_read_only(read_only)


class _SubmittedBanner(QWidget):
    """Yellow-tinted banner shown when the open session is submitted.

    Two-line summary on the left ("Submitted as evidence on …") and a
    "Reopen for editing" button on the right. The button emits the
    ``reopen_clicked`` signal; the workspace forwards it as
    ``reopen_requested`` and the controller catches that, prompts to
    confirm, and clears the marker.
    """

    reopen_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Tinted background + thin border so the banner reads as a
        # status notice rather than competing with the step editor.
        # Picked to render legibly in both LIGHT and DARK palettes.
        self.setStyleSheet(
            "_SubmittedBanner {"
            "  background-color: #fdf6d8;"
            "  border: 1px solid #d6c97a;"
            "  border-radius: 4px;"
            "}"
            "QLabel { color: #5c4a00; }"
        )
        self._title = QLabel("Submitted as evidence", self)
        font = self._title.font()
        font.setBold(True)
        self._title.setFont(font)

        self._detail = QLabel("", self)
        self._detail.setWordWrap(True)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        text_col.addWidget(self._title)
        text_col.addWidget(self._detail)

        self._reopen_btn = QPushButton("Reopen for editing…", self)
        self._reopen_btn.clicked.connect(self.reopen_clicked)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        layout.addLayout(text_col, 1)
        layout.addWidget(self._reopen_btn, 0, Qt.AlignmentFlag.AlignVCenter)

    def show_marker(self, marker: SubmittedMarker) -> None:
        # %Z renders the timezone abbreviation so an operator on a
        # different machine can't misread a UTC marker as local time
        # (or vice versa). Required for forensic-grade timestamping.
        when = format_local(marker.submitted_at, "%Y-%m-%d %H:%M %Z")
        parts = [f"Marked submitted on {when}"]
        if marker.examiner:
            parts.append(f"by {marker.examiner}")
        if marker.export_format:
            parts.append(f"after {marker.export_format} export")
        parts_str = " · ".join(parts) + "."
        self._detail.setText(
            parts_str + "  Edits are disabled. "
            "Click \"Reopen for editing\" to make changes."
        )
