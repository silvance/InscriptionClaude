"""Application controller.

Owns the :class:`SessionRepository`, the :class:`CaptureEngine`, and the
session lifecycle. Dialogs and widgets emit Qt signals; the controller
translates those into repository mutations and UI updates.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox, QWidget

from inscription.capture import (
    CaptureEngine,
    ClickSource,
    EnrichedEvent,
    KeyboardMilestoneSource,
    MarkerSource,
    SessionSink,
    WindowFocusSource,
)
from inscription.config import Config
from inscription.export import export_html
from inscription.paths import WORKSPACE_DIR
from inscription.platform import (
    create_foreground_inspector,
    create_hotkey_manager,
    create_screen_capturer,
)
from inscription.resolve import create_element_resolver
from inscription.steps import generate_steps
from inscription.storage import (
    SessionAlreadyExistsError,
    SessionLockedError,
    SessionRepository,
    list_sessions,
)
from inscription.ui.qt_capture_bridge import QtCaptureBridge
from inscription.ui.session_dialogs import SessionListDialog
from inscription.version import __version__

if TYPE_CHECKING:
    from pathlib import Path

    from inscription.platform import ForegroundInspector, HotkeyManager
    from inscription.resolve import ElementResolver
    from inscription.ui.recorder_bar import RecorderBar
    from inscription.ui.workspace import SessionWorkspaceWidget

logger = logging.getLogger(__name__)


class SessionController(QObject):
    """Coordinates the open session, the capture engine, and the UI."""

    session_opened = Signal(str)  # session name
    session_closed = Signal()
    event_counted = Signal(int)  # total events in current session

    def __init__(
        self,
        *,
        workspace: SessionWorkspaceWidget,
        recorder_bar: RecorderBar,
        parent_widget: QWidget | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._recorder_bar = recorder_bar
        self._parent_widget = parent_widget
        self._config = Config()

        self._repository: SessionRepository | None = None
        self._engine: CaptureEngine | None = None
        self._bridge: QtCaptureBridge | None = None
        self._sink: SessionSink | None = None
        self._event_count = 0
        self._hotkeys: HotkeyManager | None = None
        self._marker_source: MarkerSource | None = None

        self._workspace.step_text_edited.connect(self._on_step_text_edited)
        self._workspace.step_suppressed.connect(self._on_step_suppressed)
        self._recorder_bar.record_toggled.connect(self._on_record_toggled)
        self._recorder_bar.marker_requested.connect(self._on_marker_requested)

    # ------------------------------------------------------------ lifecycle

    def start(self) -> None:
        """Show the session picker. Called from the main window on launch."""
        self._show_session_picker()

    def shutdown(self) -> None:
        self._workspace.flush_pending()
        self._stop_recording()
        self._close_session()

    # --------------------------------------------------------- session picker

    def _show_session_picker(self) -> None:
        workspace_root = self._workspace_root()
        workspace_root.mkdir(parents=True, exist_ok=True)
        sessions = list_sessions(workspace_root)
        dialog = SessionListDialog(sessions=sessions, parent=self._parent_widget)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        choice = dialog.choice()
        if choice.open_slug is not None:
            self._open_session(choice.open_slug)
        elif choice.new_name is not None:
            self._create_session(choice.new_name)

    def _workspace_root(self) -> Path:
        return self._config.workspace_root or WORKSPACE_DIR

    def _open_session(self, slug: str) -> None:
        self._close_session()
        try:
            repo = SessionRepository.open_existing(workspace_root=self._workspace_root(), slug=slug)
        except SessionLockedError as exc:
            QMessageBox.warning(self._parent_widget, "Session locked", str(exc))
            return
        except Exception:
            logger.exception("Failed to open session %s", slug)
            QMessageBox.critical(
                self._parent_widget,
                "Open failed",
                f"Could not open session {slug!r}. See logs for details.",
            )
            return
        self._activate(repo)

    def _create_session(self, name: str) -> None:
        self._close_session()
        try:
            repo = SessionRepository.create(
                workspace_root=self._workspace_root(),
                name=name,
                recorder_version=__version__,
            )
        except SessionAlreadyExistsError as exc:
            QMessageBox.warning(self._parent_widget, "Session exists", str(exc))
            return
        except Exception:
            logger.exception("Failed to create session %s", name)
            QMessageBox.critical(
                self._parent_widget,
                "Create failed",
                "Could not create the session. See logs for details.",
            )
            return
        self._activate(repo)

    def _activate(self, repo: SessionRepository) -> None:
        self._repository = repo
        self._workspace.set_repository(repo)
        self._event_count = len(repo.list_events())
        self._recorder_bar.set_session_name(repo.session.info.name)
        self._recorder_bar.set_event_count(self._event_count)
        self._recorder_bar.set_recording(False)
        self.session_opened.emit(repo.session.info.name)

    def _close_session(self) -> None:
        if self._repository is None:
            return
        self._stop_recording()
        try:
            self._repository.end_session()
            self._repository.close()
        except Exception:
            logger.exception("Failed to close session cleanly")
        self._repository = None
        self._workspace.clear_repository()
        self._recorder_bar.set_session_name(None)
        self._recorder_bar.set_event_count(0)
        self._recorder_bar.set_recording(False)
        self.session_closed.emit()

    # ------------------------------------------------------------ recording

    def _on_record_toggled(self, recording: bool) -> None:
        if recording:
            self._start_recording()
        else:
            self._stop_recording()
            if self._repository is not None:
                self._regenerate_steps()

    def _start_recording(self) -> None:
        if self._repository is None:
            QMessageBox.information(
                self._parent_widget,
                "No session",
                "Open or create a session before starting a recording.",
            )
            self._recorder_bar.set_recording(False)
            return
        if self._engine is not None:
            return

        self._hotkeys = create_hotkey_manager()
        inspector_for_window = create_foreground_inspector()

        engine = CaptureEngine(
            screen_factory=create_screen_capturer,
            foreground_factory=create_foreground_inspector,
            resolver_factory=_resolver_factory,
        )

        bridge = QtCaptureBridge(parent=self)
        bridge.event_ready.connect(self._on_engine_event)
        engine.add_sink(bridge)

        sink = SessionSink(self._repository)
        engine.add_sink(sink)

        engine.start()

        engine.add_source(ClickSource())
        engine.add_source(KeyboardMilestoneSource())
        engine.add_source(WindowFocusSource(inspector=inspector_for_window))
        marker = MarkerSource(hotkey_manager=self._hotkeys)
        engine.add_source(marker)

        self._engine = engine
        self._bridge = bridge
        self._sink = sink
        self._marker_source = marker
        self._recorder_bar.set_recording(True)
        logger.info("Recording started for session %r", self._repository.session.info.name)

    def _stop_recording(self) -> None:
        if self._engine is None:
            return
        try:
            self._engine.stop()
        except Exception:
            logger.exception("Error stopping capture engine")
        self._engine = None
        self._bridge = None
        self._sink = None
        self._marker_source = None
        self._hotkeys = None
        self._recorder_bar.set_recording(False)

    def _on_marker_requested(self) -> None:
        if self._marker_source is None:
            return
        text, ok = QInputDialog.getText(self._parent_widget, "Marker", "Note (optional):")
        if ok:
            self._marker_source.fire(text.strip())

    # ---------------------------------------------------------- step actions

    def _regenerate_steps(self) -> None:
        if self._repository is None:
            return
        try:
            generate_steps(self._repository)
        except Exception:
            logger.exception("Step generation failed")
            QMessageBox.warning(
                self._parent_widget,
                "Step generation failed",
                "Inscription could not rebuild draft steps. See logs for details.",
            )
            return
        self._workspace.reload()

    def regenerate_steps(self) -> None:
        """Public entry point for the File > Regenerate menu item."""
        self._regenerate_steps()

    def export_html(self) -> None:
        if self._repository is None:
            return
        suggested = str(
            self._repository.session.exports_dir / f"{self._repository.session.root.name}.html"
        )
        target, _ = QFileDialog.getSaveFileName(
            self._parent_widget,
            "Export as HTML",
            suggested,
            "HTML (*.html)",
        )
        if not target:
            return
        try:
            doc = export_html(self._repository, destination=_as_path(target))
        except Exception:
            logger.exception("HTML export failed")
            QMessageBox.critical(
                self._parent_widget,
                "Export failed",
                "Inscription could not export the guide. See logs for details.",
            )
            return
        QMessageBox.information(
            self._parent_widget,
            "Export complete",
            f"Exported to:\n{doc.path}",
        )

    # ----------------------------------------------------------- slots

    @Slot(object)
    def _on_engine_event(self, event: object) -> None:
        if not isinstance(event, EnrichedEvent):
            return
        if self._repository is None:
            return
        self._event_count += 1
        self._recorder_bar.set_event_count(self._event_count)
        self.event_counted.emit(self._event_count)

    @Slot(int, str)
    def _on_step_text_edited(self, step_id: int, text: str) -> None:
        if self._repository is None:
            return
        try:
            self._repository.update_step_text(step_id, text)
        except Exception:
            logger.exception("Failed to persist step edit (step_id=%d)", step_id)

    @Slot(int, bool)
    def _on_step_suppressed(self, step_id: int, suppressed: bool) -> None:
        if self._repository is None:
            return
        try:
            self._repository.set_step_suppressed(step_id, suppressed=suppressed)
        except Exception:
            logger.exception("Failed to persist step suppression (step_id=%d)", step_id)
        self._workspace.reload()


def _resolver_factory(inspector: ForegroundInspector) -> ElementResolver:
    """Indirection so the capture engine's factory signature stays typed."""
    return create_element_resolver(inspector)


def _as_path(text: str) -> Path:
    from pathlib import Path as _Path  # noqa: PLC0415

    return _Path(text)
