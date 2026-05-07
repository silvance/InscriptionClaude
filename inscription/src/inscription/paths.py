"""Filesystem paths used by Inscription.

All path constants are resolved at import time. Call :func:`ensure_dirs`
once at startup to create any missing directories.

The data-root convention (LOCALAPPDATA on Windows, ~/.local/share on
other platforms) is shared with CaseForge / CaseGuide via
:func:`suite_common.paths.default_data_root`. Each app pins its own
sub-paths under that root.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from suite_common import default_data_root
from suite_common.paths import ensure_dirs as _ensure_dirs

if TYPE_CHECKING:
    from pathlib import Path

APP_NAME = "Inscription"

#: Root directory for all Inscription data on this machine.
APP_DIR: Path = default_data_root(APP_NAME)

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
    _ensure_dirs(APP_DIR, LOG_DIR, WORKSPACE_DIR, CACHE_DIR)
