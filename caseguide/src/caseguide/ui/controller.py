"""Application controller for CaseGuide.

Owns the open case + the playbook library; bridges the panels to the
storage / generator modules. Panels emit Qt signals; the controller
translates them into ``case.json`` / ``suggestions.json`` mutations.

The controller is deliberately lean — there's no event loop or
queued cross-thread work yet. The LLM augmentation pass (commit 5)
introduces a worker thread; until then everything runs synchronously
on the main thread.
"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox

from caseguide.case_reader import CaseReadError, read_case
from caseguide.config import Config
from caseguide.generator import generate_suggestions
from caseguide.model import SuggestionsDocument, utcnow
from caseguide.playbooks import PlaybookMatcher, load_playbooks
from caseguide.storage import StorageError, read_suggestions, write_suggestions
from caseguide.version import __version__

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from caseguide.case_reader import CaseHandle

logger = logging.getLogger(__name__)


class CaseGuideController(QObject):
    """Coordinates the open case, the playbook library, and the panels."""

    case_opened = Signal(object, str)  # CaseHandle, case_dir str
    case_closed = Signal()
    suggestions_loaded = Signal(object)  # SuggestionsDocument

    def __init__(self, *, parent_widget: QWidget | None = None) -> None:
        super().__init__()
        self._parent_widget = parent_widget
        self._config = Config()
        self._case_dir: Path | None = None
        self._case: CaseHandle | None = None
        self._playbooks = load_playbooks()
        self._matcher = PlaybookMatcher(self._playbooks)
        logger.info("Loaded %d playbooks", len(self._playbooks))

    # ------------------------------------------------------- access

    @property
    def config(self) -> Config:
        return self._config

    @property
    def matcher(self) -> PlaybookMatcher:
        return self._matcher

    def current_case_dir(self) -> Path | None:
        return self._case_dir

    def current_case(self) -> CaseHandle | None:
        return self._case

    # ------------------------------------------------------- open / close

    def open_from_picker(self) -> bool:
        directory = QFileDialog.getExistingDirectory(
            self._parent_widget,
            "Open case folder",
        )
        if not directory:
            return False
        return self.open_existing(Path(directory))

    def open_existing(self, case_dir: Path) -> bool:
        try:
            handle = read_case(case_dir)
        except CaseReadError as exc:
            QMessageBox.warning(self._parent_widget, "Open failed", str(exc))
            return False
        self._case = handle
        self._case_dir = case_dir
        self._config.remember_case(str(case_dir.resolve()))
        self._config.sync()
        self.case_opened.emit(handle, str(case_dir))
        # Auto-load saved suggestions if they exist; otherwise emit None
        # so the panel shows its empty state until Generate runs.
        try:
            doc = read_suggestions(case_dir)
        except StorageError as exc:
            QMessageBox.warning(self._parent_widget, "Suggestions read failed", str(exc))
            doc = None
        self.suggestions_loaded.emit(doc)
        return True

    def close_current(self) -> None:
        if self._case is None:
            return
        self._case = None
        self._case_dir = None
        self.case_closed.emit()

    # ------------------------------------------------------- generate

    def generate(self) -> SuggestionsDocument | None:
        """Run the deterministic playbook matcher; LLM augmentation arrives later."""
        if self._case is None or self._case_dir is None:
            QMessageBox.information(
                self._parent_widget,
                "No case open",
                "Open a case directory first.",
            )
            return None
        return generate_suggestions(scope=self._case.scope, matcher=self._matcher)

    # ------------------------------------------------------- save

    def save(self, doc: SuggestionsDocument) -> bool:
        if self._case_dir is None:
            return False
        # Refresh metadata on the in-memory copy so the saved file's
        # generated_at reflects this save, not whichever value the UI
        # was last handed.
        bumped = dataclasses.replace(
            doc,
            generated_at=utcnow(),
            caseguide_version=__version__,
        )
        try:
            write_suggestions(self._case_dir, bumped)
        except StorageError as exc:
            logger.exception("Save failed")
            QMessageBox.critical(self._parent_widget, "Save failed", str(exc))
            return False
        return True
