"""Main application window.

Hosts the recorder bar on top, the session workspace below, and the menus
that drive the controller.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from inscription.config import Config
from inscription.ui.controller import SessionController
from inscription.ui.recorder_bar import RecorderBar
from inscription.ui.workspace import SessionWorkspaceWidget
from inscription.version import __version__

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self, *, auto_start_controller: bool = True) -> None:
        super().__init__()
        self._config = Config()

        self.setWindowTitle(f"Inscription {__version__}")
        self.resize(1200, 800)

        self._recorder_bar = RecorderBar(self)
        self._workspace = SessionWorkspaceWidget(self)
        central = self._build_central()
        self.setCentralWidget(central)

        self._controller = SessionController(
            workspace=self._workspace,
            recorder_bar=self._recorder_bar,
            parent_widget=self,
            parent=self,
        )
        self._controller.session_opened.connect(self._on_session_opened)
        self._controller.session_closed.connect(self._on_session_closed)

        self._build_menus()
        self._build_statusbar()
        self._restore_geometry()

        if auto_start_controller:
            self.show()
            self._controller.start()

    # ------------------------------------------------------------------ UI

    def _build_central(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._recorder_bar)

        self._stack = QStackedWidget(container)

        placeholder = QWidget(container)
        ph_layout = QVBoxLayout(placeholder)
        ph_layout.setContentsMargins(48, 48, 48, 48)
        title = QLabel("Inscription", placeholder)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPointSize(24)
        font.setBold(True)
        title.setFont(font)
        hint = QLabel("No session open. Use File → Open Session to begin.", placeholder)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.addStretch(1)
        ph_layout.addWidget(title)
        ph_layout.addWidget(hint)
        ph_layout.addStretch(2)

        self._stack.addWidget(placeholder)
        self._stack.addWidget(self._workspace)

        layout.addWidget(self._stack, 1)
        return container

    def _build_menus(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open Session…", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.setStatusTip("Open or create a session")
        open_action.triggered.connect(self._controller.start)
        file_menu.addAction(open_action)

        regen_action = QAction("&Regenerate Steps", self)
        regen_action.setShortcut(QKeySequence("Ctrl+R"))
        regen_action.setStatusTip("Rebuild draft steps from raw events")
        regen_action.triggered.connect(self._controller.regenerate_steps)
        file_menu.addAction(regen_action)

        # No keyboard shortcut — Ctrl+Shift+R is the global "toggle recording"
        # hotkey registered by SessionController, and this action would
        # collide with it.
        rewrite_action = QAction("Rewrite with &AI…", self)
        rewrite_action.setStatusTip("Rewrite draft steps using the configured local LLM")
        rewrite_action.triggered.connect(self._controller.rewrite_with_llm)
        file_menu.addAction(rewrite_action)

        file_menu.addSeparator()

        export_html_action = QAction("Export as &HTML…", self)
        export_html_action.setShortcut(QKeySequence("Ctrl+E"))
        export_html_action.setStatusTip("Export the current session as HTML")
        export_html_action.triggered.connect(self._controller.export_html)
        file_menu.addAction(export_html_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        menubar.addMenu("&Edit")
        menubar.addMenu("&View")

        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About Inscription", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        about_qt_action = QAction("About &Qt", self)
        about_qt_action.triggered.connect(lambda: QMessageBox.aboutQt(self, "About Qt"))
        help_menu.addAction(about_qt_action)

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
        self.setWindowTitle(f"Inscription {__version__} — {name}")
        self.statusBar().showMessage(f"Session {name!r} open")
        self._stack.setCurrentIndex(1)

    def _on_session_closed(self) -> None:
        self.setWindowTitle(f"Inscription {__version__}")
        self.statusBar().showMessage("No session open")
        self._stack.setCurrentIndex(0)

    # -------------------------------------------------------------- Events

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802  (Qt API)
        self._controller.shutdown()
        self._save_geometry()
        logger.info("Main window closing")
        super().closeEvent(event)
