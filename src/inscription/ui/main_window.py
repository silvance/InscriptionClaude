"""Main application window.

Phase 0 deliverable: a placeholder window with menu bar, status bar, and an
About dialog. Real content lands in Phase 1 (case management) and Phase 2
(review UI).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from inscription.config import Config
from inscription.version import __version__

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self) -> None:
        super().__init__()
        self._config = Config()

        self.setWindowTitle(f"Inscription {__version__}")
        self.resize(1200, 800)

        self._build_central()
        self._build_menus()
        self._build_statusbar()
        self._restore_geometry()

    # ------------------------------------------------------------------ UI

    def _build_central(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Inscription", central)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPointSize(24)
        font.setBold(True)
        title.setFont(font)

        subtitle = QLabel(
            "Phase 0 scaffolding. Case management lands in Phase 1.",
            central,
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch(2)

        self.setCentralWidget(central)

    def _build_menus(self) -> None:
        menubar = self.menuBar()

        # --- File ---
        file_menu = menubar.addMenu("&File")

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
                "<p>Phase 0 &mdash; scaffolding only.</p>"
            ),
        )

    # -------------------------------------------------------------- Events

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802  (Qt API)
        self._save_geometry()
        logger.info("Main window closing")
        super().closeEvent(event)
