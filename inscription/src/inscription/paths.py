"""Filesystem paths used by Inscription.

All path constants are resolved at import time. Call :func:`ensure_dirs` once
at startup to create any missing directories.

On Windows (the primary target), paths are rooted at ``%LOCALAPPDATA%``. On
other platforms a sensible fallback under ``~/.local/share`` is used so the
package remains importable for development and CI on Linux/macOS.
"""

from __future__ import annotations

import os
from pathlib import Path


def _local_appdata() -> Path:
    """Return the Windows ``%LOCALAPPDATA%`` directory, or a dev fallback."""
    env = os.environ.get("LOCALAPPDATA")
    if env:
        return Path(env)
    return Path.home() / ".local" / "share"


APP_NAME = "Inscription"

#: Root directory for all Inscription data on this machine.
APP_DIR: Path = _local_appdata() / APP_NAME

#: Rotating log files.
LOG_DIR: Path = APP_DIR / "logs"

#: Local working copy of cases currently being edited. The canonical case
#: store is on the NAS; this is a performance cache and crash-safety buffer.
WORKSPACE_DIR: Path = APP_DIR / "workspace"

#: Arbitrary caches: thumbnails, buffered captures awaiting promotion, etc.
CACHE_DIR: Path = APP_DIR / "cache"

#: Per-user configuration file (INI format, written by QSettings).
CONFIG_FILE: Path = APP_DIR / "config.ini"


def ensure_dirs() -> None:
    """Create all application directories if they do not already exist."""
    for d in (APP_DIR, LOG_DIR, WORKSPACE_DIR, CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)
