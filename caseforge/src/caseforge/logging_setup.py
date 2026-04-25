"""Rotating-file logging for CaseForge."""

from __future__ import annotations

import logging
import logging.handlers

from caseforge.paths import LOG_DIR


def configure_logging(*, console: bool = True) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.handlers.RotatingFileHandler(
            LOG_DIR / "caseforge.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=10,
            encoding="utf-8",
        )
    ]
    if console:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
