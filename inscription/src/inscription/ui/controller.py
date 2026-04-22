"""Application controller.

The controller is the only place that mutates application state. Dialogs,
views, and the capture engine emit signals/results; the controller
translates those into repository operations and UI updates.

It owns the lifetime of:

- The :class:`CaseRepository` (one at a time).
- The :class:`CaptureEngine` and its sources/sinks.
- The :class:`QtCaptureBridge` that marshals engine results to Qt.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from inscription.capture.engine import CaptureEngine, CaptureResult
from inscription.capture.hotkey_source import HotkeySource
from inscription.capture.repository_sink import CaseRepositorySink
from inscription.config import Config
from inscription.paths import WORKSPACE_DIR
from inscription.platform import (
    create_foreground_inspector,
    create_hotkey_manager,
    create_screen_capturer,
)
from inscription.storage import CaseAlreadyExistsError, CaseLockedError, CaseRepository
from inscription.storage.repository import list_cases
from inscription.ui.case_list_dialog import CaseListDialog
from inscription.ui.new_case_dialog import NewCaseSpec
from inscription.ui.qt_capture_bridge import QtCaptureBridge

if TYPE_CHECKING:
    from pathlib import Path

    from inscription.ui.case_workspace import CaseWorkspaceWidget


logger = logging.getLogger(__name__)


class CaseController(QObject):
    """Top-level controller.

    The main window constructs one of these, gives it a reference to the
    case workspace widget, and calls :meth:`start` on application launch.
    """

    #: Emitted whenever a case is opened; payload is the case number.
    case_opened = Signal(str)
    #: Emitted whenever a case is closed (or swapped for another).
    case_closed = Signal()

    def __init__(
        self,
        *,
        workspace: CaseWorkspaceWidget,
        parent_widget: QWidget | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._parent_widget = parent_widget
        self._config = Config()

        self._repository: CaseRepository | None = None
        self._current_session_id: int | None = None

        # Capture engine wiring is lazy; we build it on first case-open so
        # hotkeys aren't registered before the user has a case loaded.
        self._engine: CaptureEngine | None = None
        self._bridge: QtCaptureBridge | None = None
        self._sink: CaseRepositorySink | None = None
        self._source: HotkeySource | None = None

        self._workspace.step_edit_requested.connect(self._on_step_edit)

    # ------------------------------------------------------------ lifecycle

    def start(self) -> None:
        """Entry point: show the case picker and open whatever the user chooses.

        Returns without error if the user cancels; the main window is left
        visible but empty.
        """
        self._show_case_picker()

    def shutdown(self) -> None:
        """Clean shutdown. Called from the main window's close event."""
        self._workspace.flush_pending_edits()
        self._teardown_engine()
        self._close_repository()

    # ------------------------------------------------------------ case picker

    def _show_case_picker(self) -> None:
        workspace_root = self._workspace_root()
        workspace_root.mkdir(parents=True, exist_ok=True)
        manifests = list_cases(workspace_root)
        dialog = CaseListDialog(
            manifests=manifests,
            case_number_regex=self._config.case_number_regex,
            default_examiner="",
            parent=self._parent_widget,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        choice = dialog.choice()
        if choice.open_case_number is not None:
            self._open_case(choice.open_case_number)
        elif choice.new_case is not None:
            self._create_case(choice.new_case)

    # ------------------------------------------------------------ open/create

    def _workspace_root(self) -> Path:
        return self._config.workspace_root or WORKSPACE_DIR

    def _open_case(self, case_number: str) -> None:
        self._close_repository()
        try:
            repo = CaseRepository.open_existing(
                workspace_root=self._workspace_root(),
                case_number=case_number,
            )
        except CaseLockedError as exc:
            QMessageBox.warning(self._parent_widget, "Case locked", str(exc))
            self._show_case_picker()
            return
        except Exception:
            logger.exception("Failed to open case %s", case_number)
            QMessageBox.critical(
                self._parent_widget,
                "Open failed",
                f"Could not open case {case_number}. See logs for details.",
            )
            return
        self._activate_repository(repo)

    def _create_case(self, spec: object) -> None:
        assert isinstance(spec, NewCaseSpec)
        self._close_repository()
        try:
            repo = CaseRepository.create(
                workspace_root=self._workspace_root(),
                case_number=spec.case_number,
                title=spec.title,
                examiner=spec.examiner,
                agency=spec.agency or None,
                description=spec.description or None,
            )
        except CaseAlreadyExistsError as exc:
            QMessageBox.warning(self._parent_widget, "Case exists", str(exc))
            self._show_case_picker()
            return
        except Exception:
            logger.exception("Failed to create case %s", spec.case_number)
            QMessageBox.critical(
                self._parent_widget,
                "Create failed",
                "Could not create the case. See logs for details.",
            )
            return
        self._activate_repository(repo)

    def _activate_repository(self, repo: CaseRepository) -> None:
        self._repository = repo
        self._workspace.set_repository(repo)
        session = repo.start_session()
        assert session.id is not None
        self._current_session_id = session.id
        self._start_engine(repo, session.id)
        self.case_opened.emit(repo.case.info.case_number)
        logger.info("Activated case %s", repo.case.info.case_number)

    def _close_repository(self) -> None:
        if self._repository is None:
            return
        self._teardown_engine()
        if self._current_session_id is not None:
            try:
                self._repository.end_session(self._current_session_id)
            except Exception:
                logger.exception("Failed to end session on close")
            self._current_session_id = None
        try:
            self._repository.close()
        except Exception:
            logger.exception("Failed to close repository cleanly")
        self._repository = None
        self._workspace.clear_repository()
        self.case_closed.emit()

    # ------------------------------------------------------------ capture

    def _start_engine(self, repo: CaseRepository, session_id: int) -> None:
        screen = create_screen_capturer()
        foreground = create_foreground_inspector()
        engine = CaptureEngine(screen_capturer=screen, foreground_inspector=foreground)

        bridge = QtCaptureBridge(parent=self)
        bridge.result_ready.connect(self._on_capture_result)
        engine.add_sink(bridge)

        sink = CaseRepositorySink(repo)
        sink.set_session(session_id)
        engine.add_sink(sink)

        engine.start()

        hotkeys = create_hotkey_manager()
        source = HotkeySource(hotkey_manager=hotkeys)
        engine.add_source(source)

        self._engine = engine
        self._bridge = bridge
        self._sink = sink
        self._source = source
        logger.info("Capture engine running for session %d", session_id)

    def _teardown_engine(self) -> None:
        if self._engine is None:
            return
        try:
            self._engine.stop()
        except Exception:
            logger.exception("Error stopping capture engine")
        self._engine = None
        self._bridge = None
        self._sink = None
        self._source = None

    # ------------------------------------------------------------ slots

    @Slot(object)
    def _on_capture_result(self, result: object) -> None:
        """Receive a capture result on the Qt main thread."""
        if not isinstance(result, CaptureResult):
            return
        self._on_capture_result_main_thread(result)

    def _on_capture_result_main_thread(self, result: CaptureResult) -> None:
        # The repository sink has already persisted; we re-read the latest
        # step from the repo to make sure the UI and DB agree.
        if self._repository is None or self._current_session_id is None:
            return
        steps = self._repository.list_steps(self._current_session_id)
        if not steps:
            return
        self._workspace.append_step(steps[-1])

    @Slot(int, str, str)
    def _on_step_edit(self, step_id: int, title: str, body: str) -> None:
        if self._repository is None:
            return
        try:
            self._repository.update_step_text(step_id, title=title, body_markdown=body)
        except Exception:
            logger.exception("Failed to persist step edit (step_id=%d)", step_id)
