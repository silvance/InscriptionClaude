"""Main application window — skeleton.

The actual two-pane layout (scope on the left, suggestions on the
right, generate button) lands in a follow-up commit. This skeleton
exists so the bootstrap (``python -m caseguide`` + the PyInstaller
build) has something to open.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QMainWindow

from caseguide.config import Config
from caseguide.version import __version__

if TYPE_CHECKING:
    from pathlib import Path

    from PySide6.QtGui import QCloseEvent

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Top-level CaseGuide window."""

    def __init__(self, *, case_dir: Path | None = None, auto_show: bool = True) -> None:
        super().__init__()
        self._config = Config()
        self._case_dir = case_dir
        self.setWindowTitle(f"CaseGuide {__version__}")
        self.resize(1100, 720)

        placeholder = QLabel(
            "CaseGuide v0.1 — UI lands in a follow-up commit.",
            self,
        )
        # Tag for the QSS muted-text selector (defined in style.py).
        placeholder.setProperty("muted", "true")
        self.setCentralWidget(placeholder)

        message = "No case open" if case_dir is None else f"Case: {case_dir}"
        self.statusBar().showMessage(message)
        self._restore_geometry()

        if auto_show:
            self.show()

    # -------------------------------------------------------- geometry

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

    # -------------------------------------------------------- events

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        self._save_geometry()
        super().closeEvent(event)
