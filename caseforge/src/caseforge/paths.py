"""Filesystem path resolution for CaseForge.

Mirrors Inscription's layout: per-user state under
``%LOCALAPPDATA%\\CaseForge\\`` on Windows, ``~/.local/share/CaseForge``
on Linux/macOS for development. The workspace directory is the default
parent for new case folders; the user can override it in Settings.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Final


def _default_data_root() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "CaseForge"
    return Path.home() / ".local" / "share" / "CaseForge"


DATA_ROOT: Final = _default_data_root()
CONFIG_FILE: Final = DATA_ROOT / "config.ini"
LOG_DIR: Final = DATA_ROOT / "logs"
WORKSPACE_DIR: Final = DATA_ROOT / "workspace"
CACHE_DIR: Final = DATA_ROOT / "cache"
TEMPLATES_DIR: Final = DATA_ROOT / "templates"


def ensure_dirs() -> None:
    """Create all CaseForge data directories if they don't exist yet."""
    for path in (DATA_ROOT, LOG_DIR, WORKSPACE_DIR, CACHE_DIR, TEMPLATES_DIR):
        path.mkdir(parents=True, exist_ok=True)
