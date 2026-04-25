"""Application controller.

Owns the :class:`SessionRepository`, the :class:`CaptureEngine`, and the
session lifecycle. Dialogs and widgets emit Qt signals; the controller
translates those into repository mutations and UI updates.

Global hotkeys also live here:

- Ctrl+Shift+R — toggle recording. Registered while a session is open so
  the user can stop recording without touching the Inscription window
  (which would otherwise land in the final screenshot).
- Ctrl+Shift+M — drop a marker during recording. Registered only while
  recording is active.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox, QWidget

from inscription.capture import (
    CaptureEngine,
    ClickSource,
    EnrichedEvent,
    KeyboardMilestoneSource,
    RawCaptureEvent,
    ScrollSource,
    SessionSink,
    WindowFocusSource,
)
from inscription.config import Config
from inscription.export import export_html, export_markdown
from inscription.llm import LLMClient, LLMError, StepRewriter
from inscription.model import EventKind, utcnow
from inscription.paths import WORKSPACE_DIR
from inscription.platform import (
    HotkeyBinding,
    HotkeyManager,
    create_foreground_inspector,
    create_hotkey_manager,
    create_screen_capturer,
    safe_close,
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
from inscription.ui.rewrite_dialog import RewriteProgressDialog, RewriteWorker
from inscription.ui.session_dialogs import SessionListDialog
from inscription.version import __version__

if TYPE_CHECKING:
    from collections.abc import Callable

    from inscription.model import ExportDocument
    from inscription.ui.recorder_bar import RecorderBar
    from inscription.ui.workspace import SessionWorkspaceWidget

logger = logging.getLogger(__name__)

TOGGLE_RECORD_HOTKEY = "<ctrl>+<shift>+r"
MARKER_HOTKEY = "<ctrl>+<shift>+m"
SNAPSHOT_HOTKEY = "<ctrl>+<shift>+p"


class SessionController(QObject):
    """Coordinates the open session, the capture engine, and the UI."""

    session_opened = Signal(str)  # session name
    session_closed = Signal()
    event_counted = Signal(int)  # total events in current session

    #: Queued across threads so the pynput hotkey callback can flip state
    #: on the Qt main thread without race conditions.
    _toggle_requested = Signal()
    _marker_requested = Signal()
    _snapshot_requested = Signal()

    def __init__(
        self,
        *,
        workspace: SessionWorkspaceWidget,
        recorder_bar: RecorderBar,
        parent_widget: QWidget | None = None,
        parent: QObject | None = None,
        case_dir: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._recorder_bar = recorder_bar
        self._parent_widget = parent_widget
        self._config = Config()
        # Per-run override; doesn't persist to config. Used by CaseForge
        # integration: when CaseForge launches Inscription with --case-dir,
        # all sessions for this run land inside that directory.
        self._case_dir = case_dir

        self._repository: SessionRepository | None = None
        self._engine: CaptureEngine | None = None
        self._bridge: QtCaptureBridge | None = None
        self._sink: SessionSink | None = None
        self._event_count = 0
        self._hotkeys: HotkeyManager = create_hotkey_manager()

        self._workspace.step_text_edited.connect(self._on_step_text_edited)
        self._workspace.step_suppressed.connect(self._on_step_suppressed)
        self._workspace.step_evidentiary_toggled.connect(self._on_step_evidentiary_toggled)
        self._workspace.steps_reordered.connect(self._on_steps_reordered)
        self._workspace.merge_requested.connect(self._on_merge_requested)
        self._workspace.split_requested.connect(self._on_split_requested)
        self._recorder_bar.record_toggled.connect(self._on_record_toggled)
        self._recorder_bar.marker_requested.connect(self._on_marker_requested)
        self._toggle_requested.connect(self._on_toggle_hotkey)
        self._marker_requested.connect(self._on_marker_hotkey)
        self._snapshot_requested.connect(self._on_snapshot_hotkey)

    # ------------------------------------------------------------ lifecycle

    def start(self) -> None:
        """Show the session picker. Called from the main window on launch."""
        self._show_session_picker()

    def shutdown(self) -> None:
        self._workspace.flush_pending()
        self._stop_recording()
        self._close_session()
        self._hotkeys.unregister_all()

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
        if self._case_dir is not None:
            return self._case_dir
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
        self._register_toggle_hotkey()
        self.session_opened.emit(repo.session.info.name)

    def _register_toggle_hotkey(self) -> None:
        self._hotkeys.register(
            HotkeyBinding(sequence=TOGGLE_RECORD_HOTKEY, name="toggle-record"),
            self._toggle_requested.emit,
        )

    def _close_session(self) -> None:
        if self._repository is None:
            return
        self._stop_recording()
        self._hotkeys.unregister_all()
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

        engine = CaptureEngine(
            foreground_factory=create_foreground_inspector,
            resolver_factory=create_element_resolver,
        )

        bridge = QtCaptureBridge(parent=self)
        bridge.event_ready.connect(self._on_engine_event)
        engine.add_sink(bridge)

        sink = SessionSink(self._repository)
        engine.add_sink(sink)

        engine.start()

        auto = self._config.auto_screenshot
        engine.add_source(ClickSource(auto_screenshot=auto))
        engine.add_source(KeyboardMilestoneSource())
        engine.add_source(ScrollSource())
        engine.add_source(
            WindowFocusSource(
                inspector=create_foreground_inspector(),
                auto_screenshot=auto,
            )
        )

        self._hotkeys.register(
            HotkeyBinding(sequence=MARKER_HOTKEY, name="marker"),
            self._marker_requested.emit,
        )
        self._hotkeys.register(
            HotkeyBinding(sequence=SNAPSHOT_HOTKEY, name="snapshot"),
            self._snapshot_requested.emit,
        )

        self._engine = engine
        self._bridge = bridge
        self._sink = sink
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
        # Re-register just the toggle binding so Ctrl+Shift+R still works.
        self._hotkeys.unregister_all()
        if self._repository is not None:
            self._register_toggle_hotkey()
        self._recorder_bar.set_recording(False)

    @Slot()
    def _on_toggle_hotkey(self) -> None:
        # Queued connection from the pynput listener thread. Flip the
        # button, which fires ``record_toggled`` and runs the same path
        # as a click on the bar.
        self._recorder_bar.toggle_record()

    @Slot()
    def _on_marker_hotkey(self) -> None:
        self._submit_marker(note="")

    def _on_marker_requested(self) -> None:
        if self._engine is None:
            return
        text, ok = QInputDialog.getText(self._parent_widget, "Marker", "Note (optional):")
        if ok:
            self._submit_marker(note=text.strip())

    def _submit_marker(self, *, note: str) -> None:
        engine = self._engine
        if engine is None:
            return
        engine.submit(
            RawCaptureEvent(
                kind=EventKind.MARKER,
                occurred_at=utcnow(),
                text=note or None,
            )
        )

    @Slot()
    def _on_snapshot_hotkey(self) -> None:
        """Capture the current screen and submit it as a marker event.

        Works in either auto- or manual-screenshot mode — handy when the
        examiner wants to mark *this* exact moment with a frozen frame
        even if the surrounding events would normally produce screenshots
        anyway.
        """
        engine = self._engine
        if engine is None:
            return
        # mss must be owned by the calling thread; the queued signal puts
        # this on the Qt main thread, where a fresh capturer is fine.
        capturer = create_screen_capturer()
        try:
            image = capturer.capture()
        except Exception:
            logger.exception("Snapshot hotkey failed to capture screen")
            return
        finally:
            safe_close(capturer)
        engine.submit(
            RawCaptureEvent(
                kind=EventKind.MARKER,
                occurred_at=utcnow(),
                text="Manual snapshot.",
                png_bytes=image.png_bytes,
                png_width=image.width,
                png_height=image.height,
            )
        )

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

    def auto_screenshot_enabled(self) -> bool:
        return self._config.auto_screenshot

    def set_auto_screenshot(self, enabled: bool) -> None:
        """Persist the auto-screenshot preference.

        Takes effect the next time recording starts; an in-flight session
        keeps whatever mode it was started under so the source threads
        stay consistent.
        """
        self._config.auto_screenshot = enabled
        self._config.sync()

    def rewrite_with_llm(self) -> None:
        """Send the session to the configured LLM and replace draft_steps
        with the model's rewritten version. Preserves manual edits.

        Shows a modal progress dialog and runs the request on a worker
        thread so the UI stays responsive. Any failure — connection,
        timeout, malformed response — leaves the existing steps in place
        and shows the error to the user.
        """
        if self._repository is None:
            return
        self._workspace.flush_pending()
        try:
            client = LLMClient(
                base_url=self._config.llm_base_url,
                model=self._config.llm_model,
                timeout_s=self._config.llm_timeout_s,
                api_key=self._config.llm_api_key,
            )
        except LLMError as exc:
            QMessageBox.warning(self._parent_widget, "LLM not configured", str(exc))
            return

        rewriter = StepRewriter(repository=self._repository, client=client)
        worker = RewriteWorker(rewriter)
        dialog = RewriteProgressDialog(worker, parent=self._parent_widget)
        dialog.succeeded.connect(lambda _steps: self._workspace.reload())
        dialog.failed.connect(
            lambda msg: QMessageBox.warning(self._parent_widget, "LLM rewrite failed", msg)
        )
        dialog.start()
        dialog.exec()

    def export_html(self) -> None:
        self._export(
            kind="HTML",
            extension="html",
            file_filter="HTML (*.html)",
            renderer=export_html,
        )

    def export_markdown(self) -> None:
        self._export(
            kind="Markdown",
            extension="md",
            file_filter="Markdown (*.md)",
            renderer=export_markdown,
        )

    def _export(
        self,
        *,
        kind: str,
        extension: str,
        file_filter: str,
        renderer: Callable[..., ExportDocument],
    ) -> None:
        if self._repository is None:
            return
        suggested = str(
            self._repository.session.exports_dir
            / f"{self._repository.session.root.name}.{extension}"
        )
        target, _ = QFileDialog.getSaveFileName(
            self._parent_widget,
            f"Export as {kind}",
            suggested,
            file_filter,
        )
        if not target:
            return
        try:
            doc = renderer(self._repository, destination=Path(target))
        except Exception:
            logger.exception("%s export failed", kind)
            QMessageBox.critical(
                self._parent_widget,
                "Export failed",
                f"Inscription could not export the guide as {kind}. See logs for details.",
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

    @Slot(int, bool)
    def _on_step_evidentiary_toggled(self, step_id: int, evidentiary: bool) -> None:
        if self._repository is None:
            return
        try:
            self._repository.set_step_evidentiary(step_id, evidentiary=evidentiary)
        except Exception:
            logger.exception("Failed to persist evidentiary flag (step_id=%d)", step_id)
        # No reload — the editor's checkbox is already in the right state
        # and reloading would re-trigger selection logic for no benefit.

    @Slot(list)
    def _on_steps_reordered(self, ordered_ids: list[int]) -> None:
        if self._repository is None:
            return
        try:
            self._repository.reorder_steps(ordered_ids)
        except Exception:
            logger.exception("Failed to persist reorder")
            self._workspace.reload()  # snap UI back to truth on failure
            return
        # Re-derive the manifest so the session picker reflects the new
        # ordering on next launch.
        self._repository.flush_manifest()

    @Slot(int, int)
    def _on_merge_requested(self, primary_id: int, other_id: int) -> None:
        if self._repository is None:
            return
        try:
            self._repository.merge_steps(primary_id=primary_id, other_id=other_id)
        except Exception:
            logger.exception("Failed to merge steps %d and %d", primary_id, other_id)
            QMessageBox.warning(
                self._parent_widget,
                "Merge failed",
                "Could not merge those two steps. See logs for details.",
            )
            return
        self._repository.flush_manifest()
        self._workspace.reload()

    @Slot(int)
    def _on_split_requested(self, step_id: int) -> None:
        if self._repository is None:
            return
        try:
            self._repository.split_step(step_id)
        except Exception:
            logger.exception("Failed to split step %d", step_id)
            QMessageBox.warning(
                self._parent_widget,
                "Split failed",
                "Could not split that step. See logs for details.",
            )
            return
        self._repository.flush_manifest()
        self._workspace.reload()
