"""CaseForge application bootstrap."""

from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from caseforge.logging_setup import configure_logging
from caseforge.paths import ensure_dirs
from caseforge.ui.app_icon import build_app_icon
from caseforge.ui.main_window import MainWindow
from caseforge.ui.style import apply_global_style
from caseforge.version import __version__

logger = logging.getLogger(__name__)


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        prog="caseforge",
        description="Case intake and scope tool for the Inscription forensic-exam suite.",
    )
    parser.add_argument("--version", action="version", version=f"CaseForge {__version__}")
    return parser.parse_known_args(argv[1:])


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    _, remaining = _parse_args(argv)

    ensure_dirs()
    configure_logging(console=not _is_frozen())
    logger.info("Starting CaseForge %s", __version__)

    QCoreApplication.setOrganizationName("Silvance")
    QCoreApplication.setApplicationName("CaseForge")
    QCoreApplication.setApplicationVersion(__version__)

    qt_argv = [argv[0], *remaining]
    app = QApplication(qt_argv)
    app.setStyle("Fusion")
    palette = apply_global_style(app)
    app.setWindowIcon(build_app_icon(palette))

    MainWindow()
    rc = app.exec()
    logger.info("CaseForge exited with code %d", rc)
    return rc


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
