"""Main application window.

Phase 1: hosts the :class:`CaseWorkspaceWidget` and delegates all case
management to :class:`CaseController`. Menus gain an "Open Case" action
for switching cases mid-session.
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
from inscription.ui.case_workspace import CaseWorkspaceWidget
from inscription.ui.controller import CaseController
from inscription.version import __version__

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self, *, auto_start_controller: bool = True) -> None:
        super().__init__()
        self._config = Config()

        self.setWindowTitle(f"Inscription {__version__}")
        self.resize(1200, 800)

        self._workspace = CaseWorkspaceWidget(self)
        self._stack = self._build_central(self._workspace)
        self.setCentralWidget(self._stack)

        self._controller = CaseController(
            workspace=self._workspace,
            parent_widget=self,
            parent=self,
        )
        self._controller.case_opened.connect(self._on_case_opened)
        self._controller.case_closed.connect(self._on_case_closed)

        self._build_menus()
        self._build_statusbar()
        self._restore_geometry()

        if auto_start_controller:
            # Deferred so tests that construct a MainWindow don't immediately
            # pop a modal case picker.
            self.show()
            self._controller.start()

    # ------------------------------------------------------------------ UI

    def _build_central(self, workspace: CaseWorkspaceWidget) -> QStackedWidget:
        stack = QStackedWidget(self)

        placeholder = QWidget(self)
        ph_layout = QVBoxLayout(placeholder)
        ph_layout.setContentsMargins(48, 48, 48, 48)
        title = QLabel("Inscription", placeholder)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPointSize(24)
        font.setBold(True)
        title.setFont(font)
        hint = QLabel("No case open. Use File → Open Case to begin.", placeholder)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.addStretch(1)
        ph_layout.addWidget(title)
        ph_layout.addWidget(hint)
        ph_layout.addStretch(2)

        stack.addWidget(placeholder)  # index 0
        stack.addWidget(workspace)  # index 1
        return stack

    def _build_menus(self) -> None:
        menubar = self.menuBar()

        # --- File ---
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open Case…", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.setStatusTip("Open or create a case")
        open_action.triggered.connect(self._controller.start)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.setStatusTip("Exit Inscription")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # --- Edit (populated in Phase 2 with preferences) ---
        menubar.addMenu("&Edit")

        # --- View (populated in Phase 4 with HUD toggles) ---
        menubar.addMenu("&View")

        # --- Help ---
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About Inscription", self)
        about_action.setStatusTip("About this application")
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
                "<p>Offline forensic examination notes and step-logging tool.</p>"
                "<p>Phase 1 &mdash; capture MVP.</p>"
            ),
        )

    # ------------------------------------------------------------- Slots

    def _on_case_opened(self, case_number: str) -> None:
        self.setWindowTitle(f"Inscription {__version__} — {case_number}")
        self.statusBar().showMessage(f"Case {case_number} open")
        self._stack.setCurrentIndex(1)

    def _on_case_closed(self) -> None:
        self.setWindowTitle(f"Inscription {__version__}")
        self.statusBar().showMessage("No case open")
        self._stack.setCurrentIndex(0)

    # -------------------------------------------------------------- Events

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802  (Qt API)
        self._controller.shutdown()
        self._save_geometry()
        logger.info("Main window closing")
        super().closeEvent(event)
