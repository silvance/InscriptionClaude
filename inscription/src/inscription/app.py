"""Application bootstrap for Inscription."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from inscription.logging_setup import configure_logging
from inscription.paths import ensure_dirs
from inscription.ui.main_window import MainWindow
from inscription.version import __version__

logger = logging.getLogger(__name__)


def _is_frozen() -> bool:
    """Return True when running from a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def main(argv: list[str] | None = None) -> int:
    """Application entry point. Returns the Qt event-loop exit code."""
    argv = list(sys.argv if argv is None else argv)

    ensure_dirs()
    configure_logging(console=not _is_frozen())
    logger.info("Starting Inscription %s", __version__)

    QCoreApplication.setOrganizationName("Inscription")
    QCoreApplication.setApplicationName("Inscription")
    QCoreApplication.setApplicationVersion(__version__)

    app = QApplication(argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    rc = app.exec()
    logger.info("Inscription exited with code %d", rc)
    return rc


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
