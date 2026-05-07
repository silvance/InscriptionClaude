"""Filesystem path resolution for CaseForge.

Mirrors Inscription's layout via the shared
:func:`suite_common.paths.default_data_root` helper:

- Windows: ``%LOCALAPPDATA%\\CaseForge\\``
- Linux / macOS dev fallback: ``~/.local/share/CaseForge``

The workspace directory is the default parent for new case folders;
the user can override it in Settings.
"""

from __future__ import annotations

from typing import Final

from suite_common import default_data_root
from suite_common.paths import ensure_dirs as _ensure_dirs

DATA_ROOT: Final = default_data_root("CaseForge")
CONFIG_FILE: Final = DATA_ROOT / "config.ini"
LOG_DIR: Final = DATA_ROOT / "logs"
WORKSPACE_DIR: Final = DATA_ROOT / "workspace"
CACHE_DIR: Final = DATA_ROOT / "cache"
TEMPLATES_DIR: Final = DATA_ROOT / "templates"


def ensure_dirs() -> None:
    """Create all CaseForge data directories if they don't exist yet."""
    _ensure_dirs(DATA_ROOT, LOG_DIR, WORKSPACE_DIR, CACHE_DIR, TEMPLATES_DIR)
