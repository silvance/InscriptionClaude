"""Main application window.

Hosts the recorder bar on top, the session workspace below, and the menus
that drive the controller.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from inscription.config import Config
from inscription.ui.controller import SessionController
from inscription.ui.recorder_bar import RecorderBar
from inscription.ui.welcome import WelcomePage
from inscription.ui.workspace import SessionWorkspaceWidget
from inscription.version import __version__

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(
        self,
        *,
        auto_start_controller: bool = True,
        case_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self._config = Config()
        self._case_dir = case_dir

        title = f"Inscription {__version__}"
        if case_dir is not None:
            title = f"Inscription {__version__} — Case: {case_dir.name}"
        self.setWindowTitle(title)
        self.resize(1200, 800)

        self._recorder_bar = RecorderBar(self)
        self._workspace = SessionWorkspaceWidget(self)
        self._welcome = WelcomePage(self)
        central = self._build_central()
        self.setCentralWidget(central)

        self._controller = SessionController(
            workspace=self._workspace,
            recorder_bar=self._recorder_bar,
            parent_widget=self,
            parent=self,
            case_dir=case_dir,
        )
        self._controller.session_opened.connect(self._on_session_opened)
        self._controller.session_closed.connect(self._on_session_closed)
        self._welcome.open_session_requested.connect(self._controller.start)
        self._welcome.open_existing_requested.connect(self._controller.open_session_by_slug)

        self._build_menus()
        self._build_statusbar()
        self._restore_geometry()
        self._welcome.refresh(self._controller.workspace_root())

        if auto_start_controller:
            self.show()

    # ------------------------------------------------------------------ UI

    def _build_central(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._recorder_bar)

        self._stack = QStackedWidget(container)
        self._stack.addWidget(self._welcome)
        self._stack.addWidget(self._workspace)

        layout.addWidget(self._stack, 1)
        return container

    def _build_menus(self) -> None:
        menubar = self.menuBar()
        self._build_file_menu(menubar)
        self._build_edit_menu(menubar)
        self._build_view_menu(menubar)
        self._build_help_menu(menubar)

    def _build_file_menu(self, menubar: QMenuBar) -> None:
        file_menu = menubar.addMenu("&File")
        self._add_action(
            file_menu, "&Open Session…", self._controller.start,
            shortcut="Ctrl+O", tip="Open or create a session",
        )
        self._add_action(
            file_menu, "&Regenerate Steps", self._controller.regenerate_steps,
            shortcut="Ctrl+R", tip="Rebuild draft steps from raw events",
        )
        # No keyboard shortcut — Ctrl+Shift+R is the global "toggle recording"
        # hotkey registered by SessionController, and this action would
        # collide with it.
        self._add_action(
            file_menu, "Rewrite with &AI…", self._controller.rewrite_with_llm,
            tip="Rewrite draft steps using the configured local LLM",
        )
        file_menu.addSeparator()
        self._add_action(
            file_menu, "Export as &HTML…", self._controller.export_html,
            shortcut="Ctrl+E", tip="Export the current session as HTML",
        )
        self._add_action(
            file_menu, "Export as &Markdown…", self._controller.export_markdown,
            tip="Export the current session as Markdown (paste into tickets, wikis, PRs)",
        )
        self._add_action(
            file_menu, "Export &Forensic notes…", self._controller.export_forensic_notes,
            tip="Export a printable Time/Date · Action · Result notes table",
        )
        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _build_edit_menu(self, menubar: QMenuBar) -> None:
        edit_menu = menubar.addMenu("&Edit")
        self._add_action(
            edit_menu, "&Settings…", self._controller.open_settings,
            shortcut="Ctrl+,", tip="Examiner identity and LLM endpoint",
        )

    def _build_view_menu(self, menubar: QMenuBar) -> None:
        view_menu = menubar.addMenu("&View")
        self._auto_screenshot_action = QAction("Auto-screenshot every action", self)
        self._auto_screenshot_action.setCheckable(True)
        self._auto_screenshot_action.setChecked(self._controller.auto_screenshot_enabled())
        self._auto_screenshot_action.setStatusTip(
            "When off, only the Ctrl+Shift+P snapshot hotkey produces images. "
            "Takes effect on the next recording."
        )
        self._auto_screenshot_action.toggled.connect(self._controller.set_auto_screenshot)
        view_menu.addAction(self._auto_screenshot_action)

    def _build_help_menu(self, menubar: QMenuBar) -> None:
        help_menu = menubar.addMenu("&Help")
        self._add_action(help_menu, "&About Inscription", self._show_about)
        self._add_action(
            help_menu, "About &Qt", lambda: QMessageBox.aboutQt(self, "About Qt"),
        )

    def _add_action(
        self,
        menu: QMenu,
        title: str,
        slot: object,
        *,
        shortcut: str | None = None,
        tip: str | None = None,
    ) -> QAction:
        action = QAction(title, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if tip:
            action.setStatusTip(tip)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _build_statusbar(self) -> None:
        self.statusBar().showMessage("Ready")

    # --------------------------------------------------------------- State

    def _restore_geometry(self) -> None:
        geom = self._config.window_geometry
        if geom is not None:
            self.restoreGeometry(geom)
        state = self._config.window_state
        if state is not None:
            self.restoreState(state)

    def _save_geometry(self) -> None:
        self._config.window_geometry = self.saveGeometry()
        self._config.window_state = self.saveState()
        self._config.sync()

    # ------------------------------------------------------------- Actions

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Inscription",
            (
                f"<h3>Inscription {__version__}</h3>"
                "<p>Record a workflow, review the draft, export a polished guide.</p>"
            ),
        )

    # ------------------------------------------------------------- Slots

    def _on_session_opened(self, name: str) -> None:
        case_prefix = f"Case: {self._case_dir.name} — " if self._case_dir else ""
        self.setWindowTitle(f"Inscription {__version__} — {case_prefix}{name}")
        self.statusBar().showMessage(f"Session {name!r} open")
        self._stack.setCurrentIndex(1)

    def _on_session_closed(self) -> None:
        title = f"Inscription {__version__}"
        if self._case_dir is not None:
            title = f"{title} — Case: {self._case_dir.name}"
        self.setWindowTitle(title)
        self.statusBar().showMessage("No session open")
        self._welcome.refresh(self._controller.workspace_root())
        self._stack.setCurrentIndex(0)

    # -------------------------------------------------------------- Events

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802  (Qt API)
        self._controller.shutdown()
        self._save_geometry()
        logger.info("Main window closing")
        super().closeEvent(event)
