"""Application-wide logging configuration.

Inscription never transmits logs anywhere — they exist only as local rotating
files for troubleshooting.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from typing import TYPE_CHECKING

from inscription.paths import LOG_DIR

if TYPE_CHECKING:
    from pathlib import Path

_MAX_BYTES = 5 * 1024 * 1024  # 5 MiB per file
_BACKUP_COUNT = 10

_FORMAT = "%(asctime)s %(levelname)-8s %(name)-30s %(message)s"


def configure_logging(*, console: bool = False, level: int = logging.INFO) -> Path:
    """Configure the root logger with a rotating file handler.

    Args:
        console: If True, also emit to stderr. The packaged GUI build should
            leave this False so nothing goes to a (nonexistent) console.
        level: Minimum log level for handlers.

    Returns:
        Path to the active log file.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "inscription.log"

    root = logging.getLogger()
    root.setLevel(level)

    # Idempotent: wipe any previously attached handlers before adding ours.
    for h in list(root.handlers):
        root.removeHandler(h)

    formatter = logging.Formatter(_FORMAT)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    root.addHandler(file_handler)

    if console:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(formatter)
        stream.setLevel(level)
        root.addHandler(stream)

    # Quiet chatty dependencies.
    logging.getLogger("PIL").setLevel(logging.INFO)

    logging.getLogger(__name__).debug("Logging initialised; writing to %s", log_file)
    return log_file
